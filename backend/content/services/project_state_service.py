"""Project lifecycle transitions on top of the shared PA-88 state engine.

The catalog is user-managed, so business consequences are keyed by the
state's immutable ``operational_effect`` rather than by its editable name.
Every mutation is previewed first and applied against an impact token: if a
payment or income changes between both requests the transition refuses to
run instead of applying a stale financial decision.
"""

from __future__ import annotations

from content.services.entity_history import historical_write
import hashlib
import json
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import HostingSubscription, Payment, Project
from content.models import (
    DocumentState,
    DocumentStateEpisode,
    DocumentStateEpisodeEvent,
    DocumentStateGroup,
    HostingRecord,
    IncomeRecord,
)


class ProjectStateError(ValueError):
    def __init__(self, message, *, code='invalid_project_state'):
        super().__init__(message)
        self.code = code


LEGACY_STATUS_BY_EFFECT = {
    DocumentState.OperationalEffect.DEVELOPMENT: Project.STATUS_DEVELOPMENT,
    DocumentState.OperationalEffect.OPERATING: Project.STATUS_ACTIVE,
    DocumentState.OperationalEffect.SUSPENDED: Project.STATUS_SUSPENDED,
    DocumentState.OperationalEffect.COMPLETED: Project.STATUS_COMPLETED,
    DocumentState.OperationalEffect.DECOMMISSIONED: (
        Project.STATUS_DECOMMISSIONED
    ),
}

BLOCKS_BILLING_EFFECTS = {
    DocumentState.OperationalEffect.SUSPENDED,
    DocumentState.OperationalEffect.COMPLETED,
    DocumentState.OperationalEffect.DECOMMISSIONED,
}

TERMINAL_EFFECTS = {
    DocumentState.OperationalEffect.COMPLETED,
    DocumentState.OperationalEffect.DECOMMISSIONED,
}

OPEN_PAYMENT_STATUSES = (
    Payment.STATUS_PENDING,
    Payment.STATUS_PROCESSING,
    Payment.STATUS_FAILED,
    Payment.STATUS_OVERDUE,
)


def project_allows_billing(project):
    state = getattr(project, 'current_state', None)
    if state is None:
        # Legacy ``archived`` rows deliberately remain unclassified after the
        # migration.  Ambiguity must fail closed for money: an operator first
        # chooses the real lifecycle state before billing can resume.
        return not project.state_review_required
    return state.operational_effect not in BLOCKS_BILLING_EFFECTS


def project_state_suggestion(project):
    """Suggest, but never apply, the state implied by a suspended subscription."""
    state = getattr(project, 'current_state', None)
    if state and state.operational_effect in (
        DocumentState.OperationalEffect.SUSPENDED,
        DocumentState.OperationalEffect.DECOMMISSIONED,
    ):
        return None
    subscription = getattr(project, 'hosting_subscription', None)
    if not subscription or subscription.status != HostingSubscription.STATUS_SUSPENDED:
        return None
    target = DocumentState.objects.filter(
        catalog=DocumentStateGroup.Catalog.PROJECTS,
        operational_effect=DocumentState.OperationalEffect.SUSPENDED,
        is_active=True,
        merged_into__isnull=True,
    ).order_by('order', 'id').first()
    if not target:
        return None
    from accounts.services.hosting_subscription_lifecycle import is_manually_paused

    if is_manually_paused(subscription):
        return {
            'state_id': target.pk,
            'state_name': target.name,
            'reason': 'hosting_subscription_paused',
            'message': (
                'Suscripción pausada manualmente. Revisa y confirma '
                'si el proyecto también debe pasar a Suspendido.'
            ),
        }
    return {
        'state_id': target.pk,
        'state_name': target.name,
        'reason': 'hosting_payment_failed',
        'message': (
            'El hosting está suspendido por cobros fallidos. Revisa y confirma '
            'si el proyecto también debe pasar a Suspendido.'
        ),
    }


@historical_write
@transaction.atomic
def merge_project_states(source, target, *, actor=None):
    source = DocumentState.objects.select_for_update().get(pk=source.pk)
    target = DocumentState.objects.select_for_update().get(pk=target.pk)
    if source.pk == target.pk:
        raise ProjectStateError(
            'El estado de origen y destino deben ser distintos.',
            code='same_merge_target',
        )
    if source.catalog != DocumentStateGroup.Catalog.PROJECTS or (
        target.catalog != DocumentStateGroup.Catalog.PROJECTS
    ):
        raise ProjectStateError(
            'Ambos estados deben pertenecer al catálogo de proyectos.',
            code='state_catalog_mismatch',
        )
    if source.group_id != target.group_id:
        raise ProjectStateError(
            'Sólo se pueden fusionar estados del mismo grupo.',
            code='merge_group_mismatch',
        )
    if source.system_key:
        raise ProjectStateError(
            'Los estados semilla no se fusionan; se pueden renombrar o retirar.',
            code='system_state_merge_blocked',
        )
    if not target.is_active or target.merged_into_id:
        raise ProjectStateError(
            'El estado de destino está retirado.',
            code='merge_target_retired',
        )
    if source.operational_effect != target.operational_effect:
        raise ProjectStateError(
            'Los estados deben tener el mismo efecto operativo para fusionarse.',
            code='merge_effect_mismatch',
        )

    now = timezone.now()
    active = list(
        DocumentStateEpisode.objects.select_for_update().filter(
            state=source,
            project__isnull=False,
            closed_at__isnull=True,
        )
    )
    for episode in active:
        episode.state = target
        episode.save(update_fields=('state', 'updated_at'))
        DocumentStateEpisodeEvent.objects.create(
            episode=episode,
            event_type=DocumentStateEpisodeEvent.EventType.MERGED,
            effective_at=now,
            actor=actor,
            details={
                'source_state_id': source.pk,
                'source_state_name': source.name,
                'target_state_id': target.pk,
                'target_state_name': target.name,
            },
        )
    Project.objects.filter(current_state=source).update(
        current_state=target,
        status=LEGACY_STATUS_BY_EFFECT[target.operational_effect],
        updated_at=now,
    )
    source.merged_into = target
    source.is_active = False
    source.updated_by = actor
    source.save(update_fields=(
        'merged_into', 'is_active', 'updated_by', 'updated_at',
    ))
    return source


def _paid_amount(income):
    liquid = income.liquid_records.filter(
        kind=IncomeRecord.Kind.LIQUID,
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    deductions = income.deduction_records.exclude(
        deduction_type='',
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    return liquid + deductions


def _income_payload(income, paid):
    pending = max(income.total_amount - paid, Decimal('0'))
    return {
        'id': income.pk,
        'concept': income.concept,
        'due_date': income.period_date.isoformat(),
        'total_amount': str(income.total_amount),
        'paid_amount': str(paid),
        'pending_amount': str(pending),
        'updated_at': income.updated_at.isoformat(),
    }


def _impact(project, target_state, effective_at):
    effective_date = timezone.localdate(effective_at)
    expected = list(
        IncomeRecord.objects.filter(
            project=project,
            kind=IncomeRecord.Kind.EXPECTED,
        ).order_by('period_date', 'id')
    )
    future_incomes = []
    pending_incomes = []
    for income in expected:
        paid = _paid_amount(income)
        if paid >= income.total_amount:
            continue
        payload = _income_payload(income, paid)
        if income.period_date > effective_date and paid == 0:
            future_incomes.append(payload)
        else:
            pending_incomes.append(payload)

    open_payments = list(
        Payment.objects.filter(
            subscription__project=project,
            status__in=OPEN_PAYMENT_STATUSES,
            is_archived=False,
            due_date__lte=effective_date,
        ).order_by('due_date', 'id')
    )
    future_payments = list(
        Payment.objects.filter(
            subscription__project=project,
            status__in=OPEN_PAYMENT_STATUSES,
            is_archived=False,
            due_date__gt=effective_date,
        ).order_by('due_date', 'id')
    )
    hosting = list(
        HostingRecord.objects.filter(project=project, is_active=True)
        .values('id', 'client_name', 'domain_url', 'updated_at')
        .order_by('id')
    )
    subscription = HostingSubscription.objects.filter(project=project).first()

    blockers = []
    effect = target_state.operational_effect
    if effect == DocumentState.OperationalEffect.COMPLETED:
        if pending_incomes:
            blockers.append({
                'code': 'pending_incomes',
                'message': 'Resuelve los ingresos pendientes antes de completar.',
            })
        if open_payments:
            blockers.append({
                'code': 'pending_hosting_payments',
                'message': 'Resuelve los cobros de hosting antes de completar.',
            })
    elif effect == DocumentState.OperationalEffect.DECOMMISSIONED and open_payments:
        blockers.append({
            'code': 'pending_hosting_payments',
            'message': (
                'Resuelve los cobros de hosting ya causados antes de dar de baja.'
            ),
        })

    return {
        'project_id': project.pk,
        'project_updated_at': project.updated_at.isoformat(),
        'current_state_id': project.current_state_id,
        'target_state_id': target_state.pk,
        'target_effect': effect,
        'effective_at': effective_at.isoformat(),
        'pending_incomes': pending_incomes,
        'future_incomes': future_incomes,
        'open_payments': [
            {
                'id': item.pk,
                'amount': str(item.amount),
                'due_date': item.due_date.isoformat(),
                'status': item.status,
            }
            for item in open_payments
        ],
        'future_payments': [item.pk for item in future_payments],
        'active_hostings': [
            {
                'id': item['id'],
                'label': item['domain_url'] or item['client_name'],
            }
            for item in hosting
        ],
        'subscription': None if subscription is None else {
            'id': subscription.pk,
            'status': subscription.status,
            'updated_at': subscription.updated_at.isoformat(),
        },
        'blockers': blockers,
    }


def _impact_token(impact):
    token_payload = dict(impact)
    # An omitted effective date means "now" in both requests.  Hashing the
    # exact timestamp would make every apply stale by construction, because
    # preview and apply happen a few milliseconds apart.  The financial split
    # is date-based, so the calendar date is the stable part of this token;
    # the affected row ids and their update timestamps still detect real
    # concurrent changes.
    token_payload['effective_at'] = impact['effective_at'][:10]
    canonical = json.dumps(
        token_payload,
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def preview_transition(project, target_state, *, effective_at=None):
    target_state = DocumentState.objects.select_related('group').get(
        pk=target_state.pk,
    )
    if target_state.catalog != DocumentStateGroup.Catalog.PROJECTS:
        raise ProjectStateError(
            'El estado pertenece a otro catálogo.',
            code='state_catalog_mismatch',
        )
    if not target_state.is_active or target_state.merged_into_id:
        raise ProjectStateError(
            'El estado está retirado y no se puede aplicar.',
            code='state_retired',
        )
    if project.current_state_id == target_state.pk and not project.state_review_required:
        raise ProjectStateError(
            'El proyecto ya tiene este estado.',
            code='state_already_active',
        )
    effective_at = effective_at or timezone.now()
    if effective_at > timezone.now():
        raise ProjectStateError(
            'La fecha efectiva no puede estar en el futuro.',
            code='effective_at_in_future',
        )
    impact = _impact(project, target_state, effective_at)
    return {**impact, 'impact_token': _impact_token(impact)}


def _proportional_amount(value, original_total, remaining_total):
    if not original_total:
        return Decimal('0')
    return (value * remaining_total / original_total).quantize(
        Decimal('0.01'),
        rounding=ROUND_DOWN,
    )


def _write_off_income(income, actor):
    paid = _paid_amount(income)
    pending = max(income.total_amount - paid, Decimal('0'))
    if pending <= 0:
        return
    if paid == 0:
        income.kind = IncomeRecord.Kind.LOST
        income.reminders_muted = True
        income.reminders_muted_until = None
        income.save(update_fields=(
            'kind', 'reminders_muted', 'reminders_muted_until', 'updated_at',
        ))
        return

    original_total = income.total_amount
    lost_gustavo = _proportional_amount(
        income.gustavo_amount, original_total, pending,
    )
    lost_carlos = _proportional_amount(
        income.carlos_amount, original_total, pending,
    )
    IncomeRecord.objects.create(
        concept=f'{income.concept} — saldo dado por perdido',
        kind=IncomeRecord.Kind.LOST,
        client=income.client,
        project=income.project,
        origin=income.origin,
        period_date=income.period_date,
        ledger=income.ledger,
        total_amount=pending,
        gustavo_amount=lost_gustavo,
        carlos_amount=lost_carlos,
        destination=IncomeRecord.Destination.PARTNERS,
        expected_income=income,
        reminders_muted=True,
        notes='Saldo resuelto al dar de baja el proyecto.',
        source_ref=f'project-state:{income.project_id}:decommission',
        created_by=actor,
    )
    income.total_amount = paid
    income.gustavo_amount = min(
        income.gustavo_amount - lost_gustavo,
        paid,
    )
    income.carlos_amount = min(
        income.carlos_amount - lost_carlos,
        paid - income.gustavo_amount,
    )
    income.reminders_muted = True
    income.reminders_muted_until = None
    income.save(update_fields=(
        'total_amount', 'gustavo_amount', 'carlos_amount',
        'reminders_muted', 'reminders_muted_until', 'updated_at',
    ))


def _cancel_future_billing(impact):
    future_ids = [item['id'] for item in impact['future_incomes']]
    if future_ids:
        IncomeRecord.objects.filter(
            pk__in=future_ids,
            kind=IncomeRecord.Kind.EXPECTED,
        ).update(
            kind=IncomeRecord.Kind.CANCELLED,
            reminders_muted=True,
            reminders_muted_until=None,
        )
    future_payment_ids = impact['future_payments']
    if future_payment_ids:
        Payment.objects.filter(pk__in=future_payment_ids).update(
            is_archived=True,
            archived_at=timezone.now(),
        )


def _apply_terminal_effects(project, impact, resolutions, actor):
    _cancel_future_billing(impact)
    HostingRecord.objects.filter(project=project, is_active=True).update(
        is_active=False,
    )
    HostingSubscription.objects.filter(project=project).update(
        status=HostingSubscription.STATUS_CANCELLED,
        updated_at=timezone.now(),
    )

    for item in impact['pending_incomes']:
        income = IncomeRecord.objects.select_for_update().get(pk=item['id'])
        action = resolutions.get(income.pk)
        if action == 'keep_receivable':
            income.reminders_muted = True
            income.reminders_muted_until = None
            income.save(update_fields=(
                'reminders_muted', 'reminders_muted_until', 'updated_at',
            ))
        elif action == 'write_off':
            _write_off_income(income, actor)


@historical_write
@transaction.atomic
def apply_transition(
    project,
    target_state,
    *,
    actor,
    impact_token,
    effective_at=None,
    note='',
    resolutions=None,
):
    locked = Project.objects.select_for_update().select_related(
        'current_state',
    ).get(pk=project.pk)
    preview = preview_transition(
        locked,
        target_state,
        effective_at=effective_at,
    )
    if preview['impact_token'] != impact_token:
        raise ProjectStateError(
            'El impacto cambió desde la vista previa. Revísalo de nuevo.',
            code='stale_transition_preview',
        )
    if preview['blockers']:
        raise ProjectStateError(
            preview['blockers'][0]['message'],
            code=preview['blockers'][0]['code'],
        )

    target_state = DocumentState.objects.select_for_update().get(
        pk=target_state.pk,
    )
    current_effect = (
        locked.current_state.operational_effect if locked.current_state else ''
    )
    if (
        target_state.operational_effect
        == DocumentState.OperationalEffect.DECOMMISSIONED
        and current_effect != DocumentState.OperationalEffect.SUSPENDED
        and not str(note or '').strip()
    ):
        raise ProjectStateError(
            'Explica por qué la baja omite el paso previo por Suspendido.',
            code='direct_decommission_note_required',
        )

    resolution_map = {
        int(item['income_id']): item['action']
        for item in (resolutions or [])
        if item.get('income_id') is not None
    }
    if target_state.operational_effect == DocumentState.OperationalEffect.DECOMMISSIONED:
        required = {item['id'] for item in preview['pending_incomes']}
        supplied = set(resolution_map)
        if supplied != required or any(
            action not in ('keep_receivable', 'write_off')
            for action in resolution_map.values()
        ):
            raise ProjectStateError(
                'Decide qué hacer con cada ingreso pendiente.',
                code='income_resolutions_required',
            )

    transition_at = datetime.fromisoformat(preview['effective_at'])
    active = list(
        DocumentStateEpisode.objects.select_for_update().filter(
            project=locked,
            closed_at__isnull=True,
            state__group=target_state.group,
        )
    )
    for episode in active:
        episode.closed_at = transition_at
        episode.closed_by = actor
        episode.outcome = DocumentStateEpisode.Outcome.TRANSITIONED
        episode.close_note = f'Transición a {target_state.name}'
        episode.save(update_fields=(
            'closed_at', 'closed_by', 'outcome', 'close_note', 'updated_at',
        ))
        DocumentStateEpisodeEvent.objects.create(
            episode=episode,
            event_type=DocumentStateEpisodeEvent.EventType.TRANSITIONED,
            effective_at=transition_at,
            actor=actor,
            details={
                'target_state_id': target_state.pk,
                'target_state_name': target_state.name,
                'note': str(note or '').strip(),
            },
        )

    episode = DocumentStateEpisode.objects.create(
        project=locked,
        state=target_state,
        opened_at=transition_at,
        opened_by=actor,
        origin=DocumentStateEpisode.Origin.MANUAL,
    )
    DocumentStateEpisodeEvent.objects.create(
        episode=episode,
        event_type=DocumentStateEpisodeEvent.EventType.OPENED,
        effective_at=transition_at,
        actor=actor,
        details={
            'origin': DocumentStateEpisode.Origin.MANUAL,
            'note': str(note or '').strip(),
            'impact': {
                'future_income_ids': [
                    item['id'] for item in preview['future_incomes']
                ],
                'pending_income_ids': [
                    item['id'] for item in preview['pending_incomes']
                ],
                'active_hosting_ids': [
                    item['id'] for item in preview['active_hostings']
                ],
            },
        },
    )

    if (
        target_state.operational_effect
        == DocumentState.OperationalEffect.SUSPENDED
    ):
        # The debt already caused remains collectible.  Only projections and
        # scheduled charges after the effective date disappear from the
        # figures; the hosting itself stays configured because suspension is
        # deliberately reversible.
        _cancel_future_billing(preview)
    elif target_state.operational_effect in TERMINAL_EFFECTS:
        _apply_terminal_effects(
            locked,
            preview,
            resolution_map,
            actor,
        )

    locked.current_state = target_state
    locked.status = LEGACY_STATUS_BY_EFFECT[target_state.operational_effect]
    locked.state_review_required = False
    locked.save(update_fields=(
        'current_state', 'status', 'state_review_required', 'updated_at',
    ))
    return locked, episode


def initialize_project_state(project, state, *, actor=None, opened_at=None):
    if state.catalog != DocumentStateGroup.Catalog.PROJECTS or not state.is_active:
        raise ProjectStateError(
            'El estado inicial no pertenece al catálogo vigente de proyectos.',
            code='invalid_initial_project_state',
        )
    now = opened_at or timezone.now()
    episode = DocumentStateEpisode.objects.create(
        project=project,
        state=state,
        opened_at=now,
        opened_by=actor,
        origin=DocumentStateEpisode.Origin.MANUAL,
    )
    DocumentStateEpisodeEvent.objects.create(
        episode=episode,
        event_type=DocumentStateEpisodeEvent.EventType.OPENED,
        effective_at=now,
        actor=actor,
        details={'origin': DocumentStateEpisode.Origin.MANUAL},
    )
    project.current_state = state
    project.status = LEGACY_STATUS_BY_EFFECT[state.operational_effect]
    project.state_review_required = False
    project.save(update_fields=(
        'current_state', 'status', 'state_review_required', 'updated_at',
    ))
    return state


def ensure_initial_project_state(project, *, actor=None):
    if project.current_state_id:
        return project.current_state
    state = DocumentState.objects.filter(
        catalog=DocumentStateGroup.Catalog.PROJECTS,
        system_key=Project.STATUS_DEVELOPMENT,
        is_active=True,
    ).first()
    if not state:
        raise ProjectStateError(
            'El catálogo no tiene un estado inicial En desarrollo.',
            code='project_initial_state_missing',
        )
    return initialize_project_state(project, state, actor=actor)
