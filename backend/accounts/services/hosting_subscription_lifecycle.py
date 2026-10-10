"""Previewed subscription decisions, with append-only financial evidence."""

import hashlib
import json
from datetime import date, datetime

from content.models import Document, HostingCycle, HostingRecord, IncomeRecord
from content.services.project_state_service import project_allows_billing
from dateutil.relativedelta import relativedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from accounts.models import (
    BillingContextEvent,
    HostingSubscription,
    Payment,
    PaymentHistory,
    Project,
    ProjectHosting,
)
from accounts.services.billing_access import require_billing_admin
from accounts.services.payment_history import record_payment_status_change
from accounts.services.wompi_payment_binding import WompiPaymentBindingError

LIFECYCLE_OPERATIONS = tuple(
    f'hosting_subscription.{action}' for action in ('pause', 'cancel', 'resume')
)
OPEN_STATUSES = (
    Payment.STATUS_PENDING, Payment.STATUS_FAILED, Payment.STATUS_OVERDUE,
    Payment.STATUS_PROCESSING,
)


class PaymentChargeSkipped(WompiPaymentBindingError):
    """A no-charge rejection also skips the scheduler's retry bookkeeping."""

    def __init__(self):
        super().__init__('payment-not-payable')


class SubscriptionLifecycleError(APIException):
    status_code = 409
    default_code = 'subscription_change_blocked'

    def __init__(self, message, *, code='subscription_change_blocked', blockers=None):
        detail = {'code': code, 'detail': message}
        if blockers is not None:
            detail.update(blockers=blockers, can_apply=False)
        super().__init__(detail, code=code)
        self.code = code
        if blockers is not None:
            self.detail.update(blockers=blockers, can_apply=False)


def latest_lifecycle_event(subscription, *, lock=False):
    """Settlements are audit events, but do not consume a paired manual pause."""
    events = BillingContextEvent.objects.filter(
        operation__in=LIFECYCLE_OPERATIONS,
        after__subscription_id=subscription.pk,
    )
    if lock:
        # MySQL's consistent-read snapshot may predate a committed pause.
        # A locked caller must use a current read for the paired lifecycle.
        events = events.select_for_update()
    return events.order_by('-pk').first()


def is_manually_paused(subscription, *, lock=False):
    if subscription.status != HostingSubscription.STATUS_SUSPENDED:
        return False
    event = latest_lifecycle_event(subscription, lock=lock)
    return bool(event and event.operation == 'hosting_subscription.pause')


def _effective_date(value):
    if value is None:
        return timezone.now().date()
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError as exc:
            raise ValidationError({'effective_date': 'Usa una fecha válida (AAAA-MM-DD).'}) from exc
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValidationError({'effective_date': 'Usa una fecha válida (AAAA-MM-DD).'})
    return value


def _hash(value):
    # Wording changes do not invalidate an operator's confirmed financial plan.
    def without_messages(item):
        if isinstance(item, dict):
            return {key: without_messages(child) for key, child in item.items() if key != 'message'}
        if isinstance(item, list):
            return [without_messages(child) for child in item]
        return item

    canonical = json.dumps(
        without_messages(value), cls=DjangoJSONEncoder,
        sort_keys=True, separators=(',', ':'),
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _subscription_data(subscription):
    return {'status': subscription.status, 'next_billing_date': (
        subscription.next_billing_date.isoformat() if subscription.next_billing_date else None
    )}


def _payment_data(payment):
    return {
        'id': payment.pk, 'amount': str(payment.amount),
        'due_date': payment.due_date.isoformat(),
        'billing_period_start': payment.billing_period_start.isoformat(),
        'billing_period_end': payment.billing_period_end.isoformat(),
        'status_before': payment.status,
    }


def _resources(subscription, lock):
    """Acquire the same parent-first locks as payment approval and retention."""
    project_id = HostingSubscription.objects.values_list('project_id', flat=True).get(pk=subscription.pk)
    project = None
    if project_id:
        projects = Project.objects.all()
        if lock:
            projects = projects.select_for_update()
        project = projects.get(pk=project_id)
    subscriptions = HostingSubscription.objects.all()
    if lock:
        subscriptions = subscriptions.select_for_update()
    subscription = subscriptions.get(pk=subscription.pk)
    if subscription.project_id != project_id:
        raise SubscriptionLifecycleError(
            'La suscripción cambió de proyecto. Revisa nuevamente la vista previa.',
            code='stale_subscription_preview',
        )
    hostings = ProjectHosting.objects.filter(Q(subscription=subscription) | Q(project_id=project_id))
    if project_id is None:
        hostings = ProjectHosting.objects.filter(subscription=subscription)
    payments = Payment.objects.filter(subscription=subscription).order_by('pk')
    if lock:
        hostings = hostings.select_for_update()
        payments = payments.select_for_update()
    return subscription, project, list(hostings.order_by('pk')), list(payments)


def plan_change(subscription, action, effective_date=None, *, lock=False):
    """Return a stable preview; the unlocked path performs no SQL writes."""
    if action not in ('pause', 'cancel', 'resume'):
        raise ValidationError({'action': 'Elige pausar, cancelar o reanudar.'})
    effective = _effective_date(effective_date)
    subscription, project, hostings, payments = _resources(subscription, lock)
    event = latest_lifecycle_event(subscription, lock=lock)
    blockers, warnings = [], []

    def issue(target, code, message, resource_type='hosting_subscription', resource_id=None):
        target.append({
            'code': code, 'message': message, 'resource_type': resource_type,
            'resource_id': subscription.pk if resource_id is None else resource_id,
        })

    if subscription.retention_context_id:
        issue(blockers, 'subscription_retained', 'La suscripción se conserva como historial y no se puede modificar.')
    if not project:
        issue(blockers, 'subscription_without_project', 'La suscripción no tiene un proyecto asociado.')
    if subscription.is_archived:
        issue(blockers, 'subscription_archived', 'Desarchiva la suscripción antes de modificar su ciclo de vida.')
    if effective > timezone.now().date():
        issue(blockers, 'effective_date_in_future', 'La fecha efectiva no puede estar en el futuro.')
    allowed = {
        'pause': ('active', 'pending'),
        'cancel': ('active', 'pending', 'suspended'),
        'resume': ('suspended',),
    }
    if subscription.status not in allowed[action]:
        issue(blockers, 'invalid_transition', 'El estado actual de la suscripción no permite esta acción.')
    manual_pause = bool(event and event.operation == 'hosting_subscription.pause')
    if action == 'resume' and subscription.status == 'suspended' and not manual_pause:
        issue(blockers, 'suspended_by_payment_failure', 'La suspensión fue por cobros fallidos; no corresponde a una pausa manual.')
    state = getattr(project, 'current_state', None) if project else None
    if action == 'resume' and project and not project_allows_billing(project):
        issue(blockers, 'project_blocks_billing', 'El estado del proyecto impide reanudar la facturación.', 'project', project.pk)

    voided, restored = [], []
    due = []
    for payment in payments:
        if payment.status == Payment.STATUS_PROCESSING and payment.wompi_transaction_id:
            issue(blockers, 'payment_in_flight', 'Hay un cobro en proceso en Wompi. Espera su resultado.', 'payment', payment.pk)
        if payment.is_archived or payment.status not in OPEN_STATUSES:
            continue
        if payment.due_date <= effective:
            due.append(payment.pk)
        elif action in ('pause', 'cancel') and (
            payment.status != Payment.STATUS_PROCESSING or not payment.wompi_transaction_id
        ):
            voided.append(_payment_data(payment))
        if payment.wompi_payment_link_id or payment.wompi_payment_link_url:
            issue(warnings, 'payment_link_outstanding', 'El link de Wompi sigue publicado; un cobro tardío se registrará sin reactivar la suscripción.', 'payment', payment.pk)
    if due:
        issue(warnings, 'due_payments_remain_collectible', 'Los cobros ya causados siguen cobrables; la pausa o cancelación detiene el débito automático.')
        warnings[-1]['payment_ids'] = due
    if action == 'pause':
        issue(warnings, 'project_state_suggestion', 'El Panel puede sugerir suspender el proyecto; su estado no cambia automáticamente.', 'project', project.pk if project else subscription.pk)

    after = dict(_subscription_data(subscription))
    after['status'] = {'pause': 'suspended', 'cancel': 'cancelled', 'resume': 'active'}[action]
    generated = None
    if action == 'cancel':
        after['next_billing_date'] = None
    if action == 'resume' and manual_pause:
        paused_ids = set(event.after.get('voided_payment_ids', []))
        original = {row['id']: row['status_before'] for row in event.before.get('payments', [])}
        for payment in payments:
            if payment.pk in paused_ids and payment.status == Payment.STATUS_VOIDED and payment.is_archived and payment.due_date > effective:
                restored.append({**_payment_data(payment), 'status_after': original.get(payment.pk, Payment.STATUS_PENDING)})
        if not restored:
            end = effective + relativedelta(months=subscription.billing_months) - relativedelta(days=1)
            generated = {
                'amount': str(subscription.billing_amount), 'status': Payment.STATUS_PENDING,
                'due_date': effective.isoformat(), 'billing_period_start': effective.isoformat(),
                'billing_period_end': end.isoformat(),
                'description': f'Hosting {subscription.plan_label} — {effective} a {end}',
            }
            after['next_billing_date'] = effective.isoformat()

    hosting_ids = [hosting.pk for hosting in hostings]
    records = HostingRecord.objects.filter(project_id=project.pk) if project else HostingRecord.objects.none()
    linked_records = HostingRecord.objects.filter(billing_source__hosting_id__in=hosting_ids)
    cycles = list(HostingCycle.objects.filter(
        Q(hosting_record__in=records) | Q(hosting_record__in=linked_records),
    ).order_by('pk').values('id', 'hosting_record_id', 'amount', 'paid_at', 'period_from', 'period_to'))
    accounts = list(Document.objects.filter(
        billing_context__hosting_id__in=hosting_ids,
    ).order_by('pk').values('id', 'total', 'commercial_status'))
    future_incomes = list(IncomeRecord.objects.filter(
        project_id=project.pk if project else None,
        kind=IncomeRecord.Kind.EXPECTED, period_date__gt=effective,
    ).order_by('pk').values_list('pk', flat=True)) if project else []
    operational = records.filter(is_active=True).exists() or any(
        hosting.operational_accounting_source_id for hosting in hostings
    )
    if operational or future_incomes:
        issue(warnings, 'accounting_records_untouched', 'El hosting contable y los ingresos esperados se conservan; revísalos por separado.', 'project', project.pk)
        warnings[-1]['future_income_ids'] = future_incomes

    plan = {
        'can_apply': not blockers, 'blockers': blockers, 'warnings': warnings,
        'subscription': {'before': _subscription_data(subscription), 'after': after},
        'voided_payments': voided, 'restored_payments': restored, 'generated_payment': generated,
        'kept_history': {
            'paid_payments': [{**_payment_data(payment), 'paid_at': payment.paid_at} for payment in payments if payment.status == Payment.STATUS_PAID],
            'payment_history_count': PaymentHistory.objects.filter(payment__subscription=subscription).count(),
            'hosting_cycles': cycles, 'collection_accounts': accounts,
        },
        'effective_date': effective.isoformat(), 'action': action,
        'subscription_id': subscription.pk, 'project_id': subscription.project_id,
        # Catch changes outside the affected-payment list without exposing card
        # or provider identifiers in the conversational preview.
        'version_hash': _hash({
            'subscription': {'plan': subscription.plan, 'billing_amount': subscription.billing_amount,
                             'updated_at': subscription.updated_at},
            'project_state': {'id': project.current_state_id if project else None,
                              'effect': state.operational_effect if state else None},
            'hostings': [(hosting.pk, hosting.version) for hosting in hostings],
            'lifecycle_event_id': event.pk if event else None,
            'payments': [{field.attname: getattr(payment, field.attname)
                          for field in Payment._meta.concrete_fields} for payment in payments],
        }),
    }
    # The API, confirmation envelope and stored JSON event share this shape.
    plan = json.loads(json.dumps(plan, cls=DjangoJSONEncoder))
    plan['impact_hash'] = _hash(plan)
    return plan


@transaction.atomic
def apply_change(subscription_id, action, effective_date, reason, expected_impact_hash, actor):
    require_billing_admin(actor)
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
        raise ValidationError({'reason': 'Escribe un motivo de entre 3 y 500 caracteres.'})
    plan = plan_change(HostingSubscription(pk=subscription_id), action, effective_date, lock=True)
    if plan['impact_hash'] != expected_impact_hash:
        raise SubscriptionLifecycleError(
            'El impacto cambió. Revisa nuevamente la vista previa.', code='stale_subscription_preview',
        )
    if not plan['can_apply']:
        raise SubscriptionLifecycleError('La suscripción tiene bloqueos.', blockers=plan['blockers'])
    subscription = HostingSubscription.objects.select_for_update().get(pk=subscription_id)
    subscription.status = plan['subscription']['after']['status']
    subscription.next_billing_date = plan['subscription']['after']['next_billing_date']
    subscription.save(update_fields=['status', 'next_billing_date', 'updated_at'])
    generated = None
    if plan['generated_payment']:
        generated = Payment.objects.create(subscription=subscription, **plan['generated_payment'])
    event = BillingContextEvent.objects.create(
        project_id=plan['project_id'], actor=actor, operation=f'hosting_subscription.{action}',
        reason=reason.strip(),
        before={'subscription_id': subscription_id, 'subscription': plan['subscription']['before'],
                'payments': plan['voided_payments'] + plan['restored_payments']},
        after={'subscription_id': subscription_id, 'subscription': plan['subscription']['after'],
               'voided_payment_ids': [row['id'] for row in plan['voided_payments']],
               'restored_payment_ids': [row['id'] for row in plan['restored_payments']],
               'generated_payment_id': generated.pk if generated else None,
               'effective_date': plan['effective_date']},
    )
    metadata = {'event_id': event.pk, 'action': action}
    for row in plan['voided_payments']:
        payment = Payment.objects.get(pk=row['id'])
        payment.status = Payment.STATUS_VOIDED
        payment.is_archived = True
        payment.archived_at = timezone.now()
        payment.save(update_fields=['status', 'is_archived', 'archived_at'])
        record_payment_status_change(payment, row['status_before'], payment.status, PaymentHistory.SOURCE_MANUAL, metadata)
    for row in plan['restored_payments']:
        payment = Payment.objects.get(pk=row['id'])
        payment.status = row['status_after']
        payment.is_archived = False
        payment.archived_at = None
        payment.save(update_fields=['status', 'is_archived', 'archived_at'])
        record_payment_status_change(payment, Payment.STATUS_VOIDED, payment.status, PaymentHistory.SOURCE_MANUAL, metadata, defer_email=True)
    if generated:
        PaymentHistory.objects.create(
            payment=generated, from_status=Payment.STATUS_PENDING, to_status=Payment.STATUS_PENDING,
            source=PaymentHistory.SOURCE_MANUAL, metadata=metadata,
        )
    return {**plan, 'event_id': event.pk}
