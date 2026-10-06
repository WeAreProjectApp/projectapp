"""Current-state guarantees for expected-income settlements."""
# quality: disable misplaced_file (billing is a bounded cross-layer domain test slice assigned by QA)
from datetime import date
from decimal import Decimal

import pytest

from accounts.models import Project, UserProfile
from content.models import AccountingChangeLog, Document, DocumentType, ExpenseRecord, IncomeRecord, PocketMovement
from content.serializers.accounting import IncomeRecordCreateUpdateSerializer
from content.services import accounting_service
from content.services.accounting_settlement_service import (
    bulk_settle_expected_incomes,
    income_payment_status,
    settle_expected_income,
)


pytestmark = pytest.mark.django_db


def _expected(*, concept='Entrega', amount='100.00', client=None, project=None, kind=None):
    total = Decimal(amount)
    return IncomeRecord.objects.create(
        concept=concept,
        kind=kind or IncomeRecord.Kind.EXPECTED,
        period_date=date(2026, 10, 1),
        total_amount=total,
        gustavo_amount=total / 2,
        carlos_amount=total / 2,
        client=client,
        project=project,
    )


def _settlement(amount='100.00'):
    return {
        'concept': 'Pago recibido',
        'period_date': date(2026, 10, 15),
        'destination': IncomeRecord.Destination.PARTNERS,
        'total_amount': Decimal(amount),
        'notes': '',
        'deductions': [],
        'expected_incomes': [],
    }


def _financial_counts():
    return (
        IncomeRecord.objects.count(),
        ExpenseRecord.objects.count(),
        PocketMovement.objects.count(),
        AccountingChangeLog.objects.count(),
    )


def _collection_account(income, status, *, client_user=None, project=None):
    return Document.objects.create(
        title=f'Cuenta para {income.concept}',
        document_type=DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0],
        commercial_status=status,
        income_record=income,
        client_user=client_user or income.client.user,
        project=income.project if project is None else project,
    )


@pytest.fixture
def settlement_admin(admin_user):
    """A real Panel administrator for settlement writes in this isolated test area."""
    admin_user.is_superuser = True
    admin_user.save(update_fields=['is_superuser'])
    return admin_user


def test_settlement_reloads_the_current_client_for_the_current_project_before_creating_liquid_child(
    settlement_admin, client_user, django_user_model,
):
    """Falla si una instancia vieja crea un pago con el cliente anterior tras reasignar el proyecto."""
    replacement_user = django_user_model.objects.create_user(username='replacement-client@example.test')
    replacement_profile = UserProfile.objects.create(user=replacement_user, role=UserProfile.ROLE_CLIENT)
    project = Project.objects.create(name='Proyecto reasignado', client=client_user)
    stale_income = _expected(client=client_user.profile, project=project)

    project.client = replacement_user
    project.save(update_fields=['client'])
    IncomeRecord.objects.filter(pk=stale_income.pk).update(client=replacement_profile)
    _collection_account(stale_income, Document.CommercialStatus.ISSUED,
                        client_user=replacement_user)

    result = settle_expected_income(stale_income, _settlement(), settlement_admin)

    assert result['liquid'].expected_income_id == stale_income.pk
    assert result['liquid'].client_id == replacement_profile.pk
    assert result['liquid'].project_id == project.pk


def test_settlement_rejects_an_expected_instance_changed_to_another_kind_without_writes(
    settlement_admin,
):
    """Falla si una instancia esperada obsoleta liquida un registro que ya cambió de naturaleza."""
    stale_income = _expected()
    IncomeRecord.objects.filter(pk=stale_income.pk).update(kind=IncomeRecord.Kind.LIQUID)
    before = _financial_counts()

    with pytest.raises(ValueError, match='ingreso esperado'):
        settle_expected_income(stale_income, _settlement(), settlement_admin)

    assert _financial_counts() == before


def test_settlement_rejects_a_parent_paid_since_the_instance_was_read_without_writes(
    settlement_admin,
):
    """Falla si una liquidación vieja ignora un pago posterior y duplica el cobro del saldo."""
    stale_income = _expected()
    IncomeRecord.objects.create(
        concept='Pago ya registrado', kind=IncomeRecord.Kind.LIQUID,
        period_date=date(2026, 10, 2), total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
        expected_income=stale_income,
    )
    before = _financial_counts()

    with pytest.raises(ValueError, match='completamente pagado'):
        settle_expected_income(stale_income, _settlement(), settlement_admin)

    assert _financial_counts() == before


def test_settlement_rejects_an_amount_above_the_current_reduced_balance_without_writes(
    settlement_admin,
):
    """Falla si una instancia con saldo viejo acepta cobrar más que el monto vigente."""
    stale_income = _expected(amount='100.00')
    IncomeRecord.objects.filter(pk=stale_income.pk).update(total_amount=Decimal('60.00'))
    before = _financial_counts()

    with pytest.raises(ValueError, match='no puede superar el saldo pendiente'):
        settle_expected_income(stale_income, _settlement(), settlement_admin)

    assert _financial_counts() == before


def _bulk_case(settlement_admin, client_profile):
    first = _expected(concept='Primera', amount='100.00', client=client_profile)
    second = _expected(concept='Segunda', amount='80.00', client=client_profile)
    _collection_account(first, Document.CommercialStatus.ISSUED)
    _collection_account(second, Document.CommercialStatus.ISSUED)
    result = bulk_settle_expected_incomes({
        'allocations': [
            {'income_id': second.pk, 'amount': Decimal('80.00')},
            {'income_id': first.pk, 'amount': Decimal('100.00')},
        ],
        'total_amount': Decimal('210.00'),
        'period_date': date(2026, 10, 15),
        'notes': 'Abono único',
    }, settlement_admin)
    return first, second, result


def test_bulk_settlement_preserves_user_allocation_order(settlement_admin, client_user):
    """Falla si el abono devuelve las asignaciones en el orden del lock y no en el confirmado por el usuario."""
    first, second, result = _bulk_case(settlement_admin, client_user.profile)

    assert [income.pk for income in result['incomes']] == [second.pk, first.pk]
    assert [income.expected_income_id for income in result['liquids'][:2]] == [second.pk, first.pk]


def test_bulk_settlement_uses_one_shared_pocket_movement(settlement_admin, client_user):
    """Falla si un abono distribuido crea más de un movimiento de Bolsillo para el dinero recibido."""
    _, _, result = _bulk_case(settlement_admin, client_user.profile)

    assert PocketMovement.objects.filter(pk=result['movement'].pk).count() == 1
    assert result['liquids'][0].pocket_movement_id == result['movement'].pk
    assert result['liquids'][1].pocket_movement_id == result['movement'].pk


def test_bulk_settlement_records_the_client_credit_after_closing_allocations(
    settlement_admin, client_user,
):
    """Falla si el excedente del abono no queda como saldo a favor después de liquidar sus asignaciones."""
    first, second, result = _bulk_case(settlement_admin, client_user.profile)

    assert result['credit'].client_id == client_user.profile.pk
    assert result['credit'].total_amount == Decimal('30.00')
    assert income_payment_status(first) == 'paid'
    assert income_payment_status(second) == 'paid'


def test_settlement_endpoint_rejects_an_income_whose_project_owner_differs_without_financial_rows(
    api_client, admin_user, client_user, django_user_model,
):
    """Falla si la API acepta un ingreso cuyo cliente ya no coincide con el dueño vigente del proyecto."""
    other_user = django_user_model.objects.create_user(username='other-owner@example.test')
    other_profile = UserProfile.objects.create(user=other_user, role=UserProfile.ROLE_CLIENT)
    project = Project.objects.create(name='Proyecto incoherente', client=client_user)
    income = _expected(client=other_profile, project=project)
    admin_user.is_superuser = True
    admin_user.save(update_fields=['is_superuser'])
    api_client.force_authenticate(user=admin_user)
    before = _financial_counts()

    response = api_client.post(
        f'/api/accounting/incomes/{income.pk}/settle/',
        {
            'concept': 'Pago inválido',
            'period_date': '2026-10-15',
            'destination': 'partners',
            'total_amount': '100.00',
        },
        format='json',
    )

    assert response.status_code == 400
    assert _financial_counts() == before


@pytest.mark.parametrize('status', [
    Document.CommercialStatus.DRAFT,
    Document.CommercialStatus.CANCELLED,
])
def test_settlement_rejects_client_income_without_an_issued_collection_account_without_writes(
    settlement_admin, client_user, status,
):
    """Falla si una cuenta borrador o anulada permite liquidar dinero de un cliente."""
    income = _expected(client=client_user.profile)
    _collection_account(income, status)
    before = _financial_counts()

    with pytest.raises(ValueError, match='genera y emite una cuenta de cobro'):
        settle_expected_income(income, _settlement(), settlement_admin)

    assert _financial_counts() == before


def test_settlement_accepts_client_income_with_an_issued_matching_collection_account(
    settlement_admin, client_user,
):
    """Falla si una cuenta emitida para el mismo ingreso no desbloquea su liquidación."""
    income = _expected(client=client_user.profile)
    _collection_account(income, Document.CommercialStatus.ISSUED)

    result = settle_expected_income(income, _settlement(), settlement_admin)

    assert result['liquid'].expected_income_id == income.pk
    assert result['liquid'].total_amount == Decimal('100.00')


def test_settlement_rejects_issued_collection_account_of_another_client_without_writes(
    settlement_admin, client_user, django_user_model,
):
    """Falla si una cuenta emitida para otro cliente habilita el cobro del ingreso equivocado."""
    other_user = django_user_model.objects.create_user(username='foreign-account@example.test')
    other_profile = UserProfile.objects.create(user=other_user, role=UserProfile.ROLE_CLIENT)
    income = _expected(client=client_user.profile)
    _collection_account(income, Document.CommercialStatus.ISSUED, client_user=other_profile.user)
    before = _financial_counts()

    with pytest.raises(ValueError, match='genera y emite una cuenta de cobro'):
        settle_expected_income(income, _settlement(), settlement_admin)

    assert _financial_counts() == before


def test_bulk_settlement_rejects_client_income_without_issued_collection_account_without_writes(
    settlement_admin, client_user,
):
    """Falla si el abono masivo crea movimientos antes de verificar las cuentas emitidas."""
    income = _expected(client=client_user.profile)
    before = _financial_counts()

    with pytest.raises(ValueError, match='genera y emite una cuenta de cobro'):
        bulk_settle_expected_incomes({
            'allocations': [{'income_id': income.pk, 'amount': Decimal('100.00')}],
            'total_amount': Decimal('100.00'),
            'period_date': date(2026, 10, 15),
            'notes': '',
        }, settlement_admin)

    assert _financial_counts() == before


def test_generic_liquid_writer_rejects_client_expected_income_without_issued_account(
    settlement_admin, client_user,
):
    """Falla si el alta genérica crea un pago vinculado y evita la precondición de liquidación."""
    expected = _expected(client=client_user.profile)
    serializer = IncomeRecordCreateUpdateSerializer(data={
        'concept': 'Pago directo indebido',
        'kind': IncomeRecord.Kind.LIQUID,
        'period_date': '2026-10-15',
        'destination': IncomeRecord.Destination.PARTNERS,
        'total_amount': '100.00',
        'client': client_user.profile.pk,
        'expected_income': expected.pk,
        'origin': IncomeRecord.Origin.DEVELOPMENT,
    })
    assert serializer.is_valid(), serializer.errors
    before = _financial_counts()

    from rest_framework.exceptions import ValidationError
    with pytest.raises(ValidationError, match='genera y emite una cuenta de cobro'):
        accounting_service.create_record(
            accounting_service.EntityType.INCOME, serializer, settlement_admin,
            notify=False,
        )

    assert _financial_counts() == before


def test_generic_liquid_update_cannot_attach_an_unissued_client_expected_income(
    settlement_admin, client_user,
):
    """Falla si editar un pago permite liquidar un ingreso que aún no tiene cuenta emitida."""
    from rest_framework.exceptions import ValidationError
    expected = _expected(client=client_user.profile)
    liquid = _expected(kind=IncomeRecord.Kind.LIQUID)
    serializer = IncomeRecordCreateUpdateSerializer(
        liquid, data={'expected_income': expected.pk}, partial=True,
    )
    assert serializer.is_valid(), serializer.errors
    before = _financial_counts()

    with pytest.raises(ValidationError, match='genera y emite una cuenta de cobro'):
        accounting_service.update_record(
            accounting_service.EntityType.INCOME, liquid, serializer,
            settlement_admin, notify=False,
        )

    liquid.refresh_from_db()
    assert liquid.expected_income_id is None
    assert _financial_counts() == before
