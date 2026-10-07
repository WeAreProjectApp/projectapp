"""
Automatic recurring billing tasks for hosting subscriptions.

auto_charge_due_subscriptions runs daily and charges every open payment past
its due date using the subscription's stored Wompi payment source. Failed
charges are retried a fixed number of times before the subscription is
suspended and the client + admins are notified.
"""

import logging
from functools import partial

from huey import crontab
from huey.contrib.djhuey import periodic_task, task

logger = logging.getLogger(__name__)

MAX_CHARGE_ATTEMPTS = 3
RETRY_INTERVAL_DAYS = 2


@task()
def send_delivery_notification_task(attempt_id):
    from accounts.services.delivery_notifications import send_attempt
    return send_attempt(attempt_id)


@periodic_task(crontab(minute='*/5'))
def dispatch_delivery_notifications_task():
    from accounts.services.delivery_notifications import dispatch_pending
    dispatch_pending()


@task()
def send_payment_status_team_email_task(payment_id, to_status, source=''):
    """Async wrapper: email the team a payment outcome (approved/failed)."""
    from accounts.services.payment_notifications import send_payment_status_team_email

    return send_payment_status_team_email(payment_id, to_status, source)


@task()
def notify_team_client_first_login_task(user_id):
    """Async wrapper: notify the team that a client logged in for the first time."""
    from accounts.services.client_flow_notifications import (
        send_client_first_login_notification,
    )

    return send_client_first_login_notification(user_id)


@task()
def notify_team_email_validated_task(user_id):
    """Async wrapper: notify the team that a client validated their email."""
    from accounts.services.client_flow_notifications import (
        send_client_email_validated_notification,
    )

    return send_client_email_validated_notification(user_id)


@task()
def notify_team_document_signed_task(document_id):
    """Async wrapper: notify the team that a client signed a document."""
    from accounts.services.client_flow_notifications import (
        send_document_signed_notification,
    )

    return send_document_signed_notification(document_id)


@periodic_task(crontab(hour='6', minute='0'))
def auto_charge_due_subscriptions():
    """
    Daily: charge open payments whose billing period has expired, using each
    subscription's stored card. Reschedules retries on failure and suspends
    the subscription once the attempt limit is exhausted.
    """
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone

    from accounts.models import HostingSubscription, Payment, PaymentHistory
    from accounts.services.wompi_payment_binding import WompiPaymentBindingError
    from accounts.views import _charge_payment_with_source

    # Incorporate phases whose hosting_start_date arrived (prorated) before
    # charging, so their catch-up payments are billed in the same run.
    _onboard_due_phases()
    # Resolve charges left in PROCESSING by a missed settling webhook.
    _reverify_processing_payments()

    today = timezone.now().date()

    due = Payment.objects.select_related('subscription__project__client').filter(
        status__in=[Payment.STATUS_PENDING, Payment.STATUS_OVERDUE, Payment.STATUS_FAILED],
        is_archived=False,
        due_date__lte=today,
        charge_attempts__lt=MAX_CHARGE_ATTEMPTS,
        # ACTIVE for recurring cycles; PENDING covers the first charge after a
        # free-month gift (subscription activates when that charge settles).
        subscription__retention_context__isnull=True,
        subscription__project__isnull=False,
        subscription__status__in=[
            HostingSubscription.STATUS_ACTIVE,
            HostingSubscription.STATUS_PENDING,
        ],
    ).filter(
        Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=today),
    ).exclude(
        subscription__project__current_state__operational_effect__in=(
            'suspended', 'completed', 'decommissioned',
        ),
    ).exclude(
        subscription__project__current_state__isnull=True,
        subscription__project__state_review_required=True,
    ).exclude(
        subscription__wompi_payment_source_id='',
    )

    charged = 0
    failed = 0
    for payment in due:
        try:
            _charge_payment_with_source(payment, PaymentHistory.SOURCE_SYSTEM)
        except WompiPaymentBindingError as exc:
            logger.warning('Auto-charge binding rejected for payment %s: %s', payment.id, exc.reason)
            continue
        except Exception as e:
            logger.error('Auto-charge error for payment %s: %s', payment.id, e)
            payment.status = Payment.STATUS_FAILED
            payment.last_charge_error = str(e)[:300]

        payment.charge_attempts += 1
        if payment.status in (Payment.STATUS_PAID, Payment.STATUS_PROCESSING):
            payment.next_retry_at = None
            payment.save(update_fields=['charge_attempts', 'next_retry_at'])
            charged += 1
            continue

        failed += 1
        if payment.charge_attempts >= MAX_CHARGE_ATTEMPTS:
            payment.next_retry_at = None
            payment.save(update_fields=[
                'charge_attempts', 'next_retry_at', 'status', 'last_charge_error',
            ])
            _suspend_subscription_on_failure(payment)
        else:
            payment.next_retry_at = today + timedelta(days=RETRY_INTERVAL_DAYS)
            payment.save(update_fields=[
                'charge_attempts', 'next_retry_at', 'status', 'last_charge_error',
            ])
            _notify_charge_retry(payment)

    logger.info('auto_charge_due_subscriptions: %s charged, %s failed', charged, failed)
    return {'charged': charged, 'failed': failed}


def _suspend_subscription_on_failure(payment):
    """Suspend the subscription after the charge attempt limit is exhausted."""
    from accounts.models import HostingSubscription, Notification
    from accounts.services.notifications import notify, notify_project_admins

    sub = payment.subscription
    sub.status = HostingSubscription.STATUS_SUSPENDED
    sub.save(update_fields=['status', 'updated_at'])

    project = sub.project
    try:
        notify(
            user=project.client,
            type=Notification.TYPE_GENERAL,
            title='Suscripción suspendida',
            message=(
                f'No pudimos cobrar el hosting de "{project.name}" después de '
                f'{payment.charge_attempts} intentos. Tu suscripción quedó suspendida; '
                f'actualiza tu tarjeta para reactivarla.'
            ),
            project=project,
            related_object_type='payment',
            related_object_id=payment.id,
        )
        notify_project_admins(
            project, Notification.TYPE_GENERAL,
            f'Suscripción suspendida: {project.name}',
            message=(
                f'El cobro automático del hosting de "{project.name}" falló '
                f'{payment.charge_attempts} veces. La suscripción quedó suspendida.'
            ),
            related_object_type='payment', related_object_id=payment.id,
        )
    except Exception:
        logger.warning('Failed to send suspension notifications for payment %s', payment.id)


def _notify_charge_retry(payment):
    """Tell the client an automatic charge failed and when it will be retried."""
    from accounts.models import Notification
    from accounts.services.notifications import notify

    project = payment.subscription.project
    try:
        notify(
            user=project.client,
            type=Notification.TYPE_GENERAL,
            title='Cobro de hosting fallido',
            message=(
                f'No pudimos cobrar el hosting de "{project.name}". '
                f'Reintentaremos el {payment.next_retry_at}. '
                f'Verifica que tu tarjeta tenga fondos o actualízala.'
            ),
            project=project,
            related_object_type='payment',
            related_object_id=payment.id,
        )
    except Exception:
        logger.warning('Failed to send retry notification for payment %s', payment.id)


def _onboard_due_phases():
    """
    Incorporate phases whose hosting_start_date has arrived into their
    project's active subscription. A phase joining mid-cycle is charged a
    prorated amount for the remaining days of the current billing cycle; the
    recurring billing_amount and the next-cycle pending payment are updated to
    include the new phase from the following cycle onward.
    """
    from datetime import date
    from decimal import Decimal

    from dateutil.relativedelta import relativedelta
    from django.db import transaction

    from accounts.models import HostingSubscription, Payment, ProjectPhase
    from accounts.services.hosting_billing import prorated_amount, project_billing_amount

    today = date.today()
    due_phases = ProjectPhase.objects.filter(project__isnull=False, retention_context__isnull=True).select_related(
        'project', 'business_proposal', 'project__hosting_subscription',
    ).filter(
        hosting_start_date__lte=today,
        hosting_activated_at__isnull=True,
        project__hosting_subscription__status=HostingSubscription.STATUS_ACTIVE,
    ).exclude(
        project__current_state__operational_effect__in=(
            'suspended', 'completed', 'decommissioned',
        ),
    ).exclude(
        project__current_state__isnull=True,
        project__state_review_required=True,
    )

    onboarded = 0
    for phase in due_phases:
        try:
            sub = phase.project.hosting_subscription
            if not sub.next_billing_date:
                continue

            months = sub.billing_months
            cycle_end = sub.next_billing_date - relativedelta(days=1)
            cycle_start = sub.next_billing_date - relativedelta(months=months)
            join_date = max(phase.hosting_start_date, cycle_start)

            prorated = prorated_amount(phase, sub.plan, join_date, cycle_start, cycle_end)

            with transaction.atomic():
                phase.hosting_activated_at = today
                phase.save(update_fields=['hosting_activated_at'])

                prorated_payment = None
                if prorated > 0:
                    prorated_payment = Payment.objects.create(
                        subscription=sub,
                        amount=prorated,
                        description=(
                            f'Hosting fase {phase.order} (prorrateado) — '
                            f'{join_date} a {cycle_end}'
                        ),
                        billing_period_start=join_date,
                        billing_period_end=cycle_end,
                        due_date=today,
                        status=Payment.STATUS_PENDING,
                    )

                new_amount = project_billing_amount(phase.project, sub.plan)
                sub.billing_amount = new_amount
                sub.effective_monthly_amount = round(new_amount / Decimal(months), 2)
                sub.save(update_fields=['billing_amount', 'effective_monthly_amount', 'updated_at'])

                # Recurring payments for the next cycle onward grow to the new total.
                Payment.objects.filter(
                    subscription=sub,
                    status=Payment.STATUS_PENDING,
                    billing_period_start__gte=sub.next_billing_date,
                ).update(amount=new_amount)

                transaction.on_commit(
                    partial(_notify_phase_onboarded, phase, sub, prorated_payment, new_amount),
                    robust=True,
                )
        except Exception as exc:
            logger.error(
                'Phase hosting onboarding failed phase_id=%s error_type=%s',
                phase.pk, type(exc).__name__,
            )
            continue
        onboarded += 1

    if onboarded:
        logger.info('_onboard_due_phases: %s phase(s) onboarded', onboarded)
    return onboarded


def _notify_phase_onboarded(phase, sub, prorated_payment, new_amount):
    """Tell the client (and project admins) a phase joined the hosting billing."""
    from accounts.models import Notification
    from accounts.services.notifications import notify, notify_project_admins
    from content.utils import format_cop_email

    project = sub.project
    title = phase.business_proposal.title
    period = sub.plan_label.lower()
    related_type = 'payment' if prorated_payment else ''
    related_id = prorated_payment.id if prorated_payment else None

    if prorated_payment is not None:
        charge_line = (
            f' Se aplicó un cobro prorrateado de ${format_cop_email(prorated_payment.amount)} COP '
            f'por los días restantes del ciclo actual.'
        )
    else:
        charge_line = ''

    try:
        notify(
            user=project.client,
            type=Notification.TYPE_GENERAL,
            title='Nueva fase en tu hosting',
            message=(
                f'La fase "{title}" se incorporó a tu hosting.{charge_line} '
                f'Desde la próxima renovación tu hosting será de '
                f'${format_cop_email(new_amount)} COP / {period}.'
            ),
            project=project,
            related_object_type=related_type,
            related_object_id=related_id,
        )
        notify_project_admins(
            project, Notification.TYPE_GENERAL,
            f'Fase incorporada al hosting: {project.name}',
            message=(
                f'La fase "{title}" entró a la facturación de "{project.name}". '
                f'Nuevo cobro recurrente: ${format_cop_email(new_amount)} COP / {period}.'
            ),
            related_object_type=related_type,
            related_object_id=related_id,
        )
    except Exception:
        logger.warning('Failed to send phase-onboarded notification for phase %s', phase.id)


def _reverify_processing_payments():
    """
    Re-check payments stuck in PROCESSING by polling Wompi directly. Card
    transactions settle asynchronously; this covers cases where the settling
    webhook never arrived (always the case on localhost).
    """
    from accounts.models import Payment, PaymentHistory
    from accounts.services.payment_history import record_payment_status_change
    from accounts.services.wompi import verify_transaction
    from accounts.services.wompi_payment_binding import (
        WompiPaymentBindingError,
        validate_transaction_binding,
    )
    from accounts.views import _handle_payment_approved

    stuck = (
        Payment.objects.select_related('subscription__project__client')
        .filter(status=Payment.STATUS_PROCESSING, is_archived=False)
        .exclude(wompi_transaction_id='')
    )

    resolved = 0
    for payment in stuck:
        try:
            data = verify_transaction(payment.wompi_transaction_id)
            validate_transaction_binding(
                payment, data, expected_transaction_id=payment.wompi_transaction_id,
            )
        except WompiPaymentBindingError as exc:
            logger.warning('Re-verify binding rejected for payment %s: %s', payment.id, exc.reason)
            continue
        except Exception as e:
            logger.warning('Re-verify error for payment %s: %s', payment.id, e)
            continue

        txn_status = data.get('status', '')
        if txn_status == 'APPROVED':
            _handle_payment_approved(payment, PaymentHistory.SOURCE_WOMPI_VERIFY)
            resolved += 1
        elif txn_status in ('DECLINED', 'ERROR', 'VOIDED'):
            old_status = payment.status
            payment.status = Payment.STATUS_FAILED
            payment.save(update_fields=['status'])
            record_payment_status_change(
                payment, old_status, Payment.STATUS_FAILED, PaymentHistory.SOURCE_WOMPI_VERIFY,
            )
            resolved += 1

    if resolved:
        logger.info('_reverify_processing_payments: %s payment(s) resolved', resolved)
    return resolved
