"""Conflicts that keep one hosting obligation from absorbing unrelated evidence."""
from datetime import date
from decimal import Decimal

import pytest

from accounts.models import (
    HostingEvidence,
    HostingEvidenceGroup,
    HostingSubscription,
    Payment,
    Project,
)
from accounts.services.hosting_context import reconcile_hosting
from accounts.tests.billing.hosting_payment_fixtures import billing
from content.models import (
    DocumentItem,
    HostingCycle,
    HostingIncomePeriod,
    IncomeRecord,
)
from content.services import hosting_periods
from content.services.hosting_periods import (
    AMBIGUOUS,
    EMPTY_PERIOD,
    MISSING_OWNER,
    UNLINKED_CASH,
    HostingPeriods,
    PeriodConflict,
    current_summary,
)


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fixed_business_date(monkeypatch):
    monkeypatch.setattr(hosting_periods, 'today_bogota', lambda: date(2026, 11, 26))


@pytest.fixture
def legacy_record(admin_user, hosting_record):
    reconcile_hosting(hosting_record.project_id, admin_user, {
        'expected_version': 0,
        'reason': 'Servicio histórico sin suscripción digital.',
        'hosting_record_ids': [hosting_record.pk],
        'operational_record_id': hosting_record.pk,
    })
    return hosting_record


def create_payment(subscription, *, start, end, amount=Decimal('233280.00'), status='pending'):
    return Payment.objects.create(
        subscription=subscription,
        amount=amount,
        status=status,
        billing_period_start=start,
        billing_period_end=end,
        due_date=start,
    )


def create_expected_income(record, *, start=date(2026, 4, 1), end=date(2026, 6, 30),
                           amount=Decimal('233280.00'), concept='Hosting histórico'):
    return IncomeRecord.objects.create(
        project=record.project,
        client=record.client,
        kind=IncomeRecord.Kind.EXPECTED,
        origin=IncomeRecord.Origin.HOSTING,
        concept=concept,
        period_start=start,
        period_end=end,
        period_cadence='quarterly' if start and end else '',
        period_date=start or date(2026, 5, 1),
        total_amount=amount,
    )


def create_cycle(record, *, start=date(2026, 4, 1), end=date(2026, 6, 30),
                 represented=1):
    return HostingCycle.objects.create(
        hosting_record=record,
        modality='quarterly',
        amount=Decimal('50000.00'),
        paid_at=date(2026, 5, 17),
        period_from=start,
        period_to=end,
        cycles_represented=represented,
    )


def test_archived_payment_is_not_an_active_subscription_obligation(billing):
    """Falla si un Payment archivado vuelve a habilitar un período para cobrar."""
    _, record, _ = billing
    Payment.objects.filter(subscription=record.project.hosting_subscription).update(is_archived=True)

    summary = current_summary(record.project_id)

    assert summary == {'blocker': EMPTY_PERIOD, 'state': 'blocked'}


def test_processing_payment_exposes_processing_blocker(billing):
    """Falla si un cobro automático en proceso permite emitir una cuenta ordinaria."""
    _, record, _ = billing
    Payment.objects.filter(subscription=record.project.hosting_subscription).update(status='processing')

    summary = current_summary(record.project_id)

    assert summary['state'] == 'processing'
    assert summary['blocker'] == 'El período está cubierto o su cobro requiere conciliación.'


def test_legacy_record_without_billing_identity_stays_blocked(hosting_record):
    """Falla si un HostingRecord histórico sin identidad conciliada se vuelve cobrable."""
    summary = current_summary(hosting_record.project_id)

    assert summary == {'blocker': MISSING_OWNER, 'state': 'blocked'}


def test_operational_record_from_another_project_is_rejected(billing):
    """Falla si el origen operativo de otro proyecto presta su período al proyecto actual."""
    _, record, _ = billing
    original_project_id = record.project_id
    foreign_project = Project.objects.create(
        name='Proyecto ajeno',
        client=record.project.client,
        status=Project.STATUS_ACTIVE,
        progress=0,
    )
    record.project = foreign_project
    record.save(update_fields=['project'])

    summary = current_summary(original_project_id)

    assert summary == {'blocker': MISSING_OWNER, 'state': 'blocked'}


def test_project_subscription_missing_from_context_requires_reconciliation(billing):
    """Falla si una suscripción del proyecto se usa sin asociarla al contexto de hosting."""
    _, record, _ = billing
    context = record.project.billing_hosting
    context.subscription = None
    context.save(update_fields=['subscription'])

    summary = current_summary(record.project_id)

    assert summary['state'] == 'blocked'
    assert summary['blocker'] == 'Concilia la suscripción pendiente de asociar al proyecto.'


def test_evidence_group_rejects_payment_from_another_subscription(billing):
    """Falla si un grupo administrativo adopta un pago de otra suscripción."""
    _, record, _ = billing
    foreign_project = Project.objects.create(
        name='Proyecto del pago ajeno',
        client=record.project.client,
        status=Project.STATUS_ACTIVE,
        progress=0,
    )
    foreign_subscription = HostingSubscription.objects.create(
        project=foreign_project,
        plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal('77760.00'),
        effective_monthly_amount=Decimal('77760.00'),
        billing_amount=Decimal('233280.00'),
        start_date=date(2026, 1, 1),
        status=HostingSubscription.STATUS_ACTIVE,
    )
    foreign_payment = create_payment(
        foreign_subscription,
        start=date(2026, 4, 1),
        end=date(2026, 6, 30),
    )
    group = HostingEvidenceGroup.objects.create(
        hosting=record.project.billing_hosting,
        label='Pago importado por error',
    )
    HostingEvidence.objects.create(group=group, payment=foreign_payment)

    summary = current_summary(record.project_id)

    assert summary['state'] == 'blocked'
    assert summary['blocker'] == 'El grupo contiene un pago de otra suscripción. Concilia su origen.'


def test_evidence_group_rejects_multiple_obligation_windows(billing):
    """Falla si un solo grupo presenta pagos de dos obligaciones como equivalentes."""
    _, record, _ = billing
    subscription = record.project.hosting_subscription
    first = Payment.objects.get(subscription=subscription)
    second = create_payment(
        subscription,
        start=date(2026, 7, 1),
        end=date(2026, 9, 30),
    )
    group = HostingEvidenceGroup.objects.create(
        hosting=record.project.billing_hosting,
        label='Dos trimestres mezclados',
    )
    HostingEvidence.objects.create(group=group, payment=first)
    HostingEvidence.objects.create(group=group, payment=second)

    summary = current_summary(record.project_id)

    assert summary['state'] == 'blocked'
    assert summary['blocker'] == 'Un grupo de evidencias comprende varias obligaciones. Revisa la conciliación.'


def test_duplicate_payment_window_is_ambiguous(billing):
    """Falla si dos Payment del mismo trimestre se reducen silenciosamente a uno."""
    _, record, _ = billing
    create_payment(
        record.project.hosting_subscription,
        start=date(2026, 4, 1),
        end=date(2026, 6, 30),
    )

    summary = current_summary(record.project_id)

    assert summary == {'blocker': AMBIGUOUS, 'state': 'blocked'}


def test_nested_payment_window_is_ambiguous(billing):
    """Falla si una obligación contenida dentro de otra se presenta como un período confiable."""
    _, record, _ = billing
    create_payment(
        record.project.hosting_subscription,
        start=date(2026, 4, 15),
        end=date(2026, 5, 15),
        amount=Decimal('80000.00'),
    )

    summary = current_summary(record.project_id)

    assert summary == {'blocker': AMBIGUOUS, 'state': 'blocked'}


def test_unassigned_liquid_blocks_every_open_window(billing):
    """Falla si dinero recibido sin ventana explícita se imputa al período abierto por descarte."""
    _, record, _ = billing
    orphan = create_expected_income(
        record,
        start=None,
        end=None,
        amount=Decimal('50000.00'),
        concept='Cobro legacy sin ventana',
    )
    IncomeRecord.objects.create(
        project=record.project,
        client=record.client,
        kind=IncomeRecord.Kind.LIQUID,
        origin=IncomeRecord.Origin.HOSTING,
        concept='Dinero sin asignación de período',
        expected_income=orphan,
        period_date=date(2026, 5, 17),
        total_amount=Decimal('50000.00'),
        destination=IncomeRecord.Destination.POCKET,
    )

    summary = current_summary(record.project_id)

    assert summary == {'blocker': AMBIGUOUS, 'state': 'blocked'}


def test_consolidated_cycle_conflicts_with_single_obligation(billing):
    """Falla si un ciclo legacy consolidado acredita una obligación individual."""
    _, record, _ = billing
    create_cycle(record, represented=2)

    summary = current_summary(record.project_id)

    assert summary == {'blocker': AMBIGUOUS, 'state': 'blocked'}


def test_exact_unallocated_cycle_requires_explicit_cash_link(billing):
    """Falla si un ciclo real sin asignación se suma al Payment pendiente por coincidencia de fechas."""
    _, record, _ = billing
    create_cycle(record)

    summary = current_summary(record.project_id)

    assert summary == {'blocker': UNLINKED_CASH, 'state': 'blocked'}


def test_legacy_document_without_period_requires_reconciliation(billing, account):
    """Falla si una cuenta histórica sin fechas se adueña de una obligación por el hosting."""
    _, record, _ = billing
    account.hosting_record = record
    account.save(update_fields=['hosting_record'])

    summary = current_summary(record.project_id)

    assert summary['state'] == 'blocked'
    assert summary['blocker'] == f'Concilia el período de la cuenta #{account.pk} antes de emitir otra.'


def test_overlapping_document_marks_obligation_ambiguous(billing, account):
    """Falla si una cuenta con fechas parciales se trata como soporte exacto del trimestre."""
    _, record, _ = billing
    account.hosting_record = record
    account.save(update_fields=['hosting_record'])
    DocumentItem.objects.create(
        document=account,
        description='Cuenta histórica con fechas desplazadas',
        quantity=1,
        unit_price=Decimal('150000.00'),
        line_total=Decimal('150000.00'),
        period_start=date(2026, 3, 15),
        period_end=date(2026, 4, 15),
    )

    summary = current_summary(record.project_id)

    assert summary == {'blocker': AMBIGUOUS, 'state': 'blocked'}


def test_subscriptionless_service_accepts_exact_legacy_cycle(legacy_record):
    """Falla si un servicio legacy coherente no puede acreditar su ciclo exacto seleccionado."""
    income = create_expected_income(legacy_record)
    cycle = create_cycle(legacy_record)
    book = HostingPeriods(legacy_record.project_id)

    summary = book.settlement_window(income).summary(book)

    assert summary['state'] == 'partial'
    assert summary['received'] == '50000.00'
    assert summary['balance'] == '183280.00'
    assert summary['cycle_ids'] == [cycle.pk]


def test_overlapping_legacy_prospects_are_ambiguous(legacy_record):
    """Falla si dos esperados legacy solapados permiten elegir obligación por descarte."""
    selected = create_expected_income(legacy_record, concept='Trimestre seleccionado')
    create_expected_income(
        legacy_record,
        start=date(2026, 5, 1),
        end=date(2026, 7, 31),
        concept='Trimestre competidor',
    )
    book = HostingPeriods(legacy_record.project_id)

    with pytest.raises(PeriodConflict, match=AMBIGUOUS):
        book.settlement_window(selected)


def test_overlapping_legacy_cycle_is_ambiguous(legacy_record):
    """Falla si un ciclo legacy que cruza dos ventanas se adopta como coincidencia exacta."""
    income = create_expected_income(legacy_record)
    create_cycle(
        legacy_record,
        start=date(2026, 3, 1),
        end=date(2026, 4, 15),
    )
    book = HostingPeriods(legacy_record.project_id)

    with pytest.raises(PeriodConflict, match=AMBIGUOUS):
        book.settlement_window(income)


def test_subscriptionless_service_without_history_has_no_reference(legacy_record):
    """Falla si un servicio sin obligación histórica inventa el calendario del próximo cobro."""
    book = HostingPeriods(legacy_record.project_id)

    with pytest.raises(PeriodConflict, match=EMPTY_PERIOD):
        book.reference_window()


def test_expected_income_amount_conflicts_with_subscription_payment(billing):
    """Falla si Ingresos puede cambiar el importe contractual del Payment sin conciliación."""
    _, record, income = billing
    income.total_amount = Decimal('200000.00')
    income.save(update_fields=['total_amount'])

    summary = current_summary(record.project_id)

    assert summary == {'blocker': AMBIGUOUS, 'state': 'blocked'}


def test_linked_income_date_drift_requires_reconciliation(billing):
    """Falla si un vínculo contable conserva autoridad después de cambiar sus fechas impresas."""
    _, record, income = billing
    HostingIncomePeriod.objects.create(
        hosting=record.project.billing_hosting,
        income=income,
        start=date(2026, 4, 2),
        end=date(2026, 6, 30),
    )

    summary = current_summary(record.project_id)

    assert summary['state'] == 'blocked'
    assert summary['blocker'] == 'El esperado vinculado cambió de servicio, estado o fechas. Revisa la conciliación.'
