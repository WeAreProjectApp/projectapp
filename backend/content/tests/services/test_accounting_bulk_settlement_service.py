"""One abono covering several expected incomes: ONE pocket movement plus one
liquid child per allocation sharing it. The child IS the per-income imputed
amount, so payment status keeps deriving from liquid children untouched.
Whatever the allocations leave of the total becomes the client's saldo a
favor as a parentless child on the same movement.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest

from content.models import (
    AccountingChangeLog, AccountingSettings, Document, DocumentType, IncomeRecord,
    NotificationRecipient, PocketMovement,
)
from content.services import accounting_service
from content.services.accounting_settlement_service import (
    _paid_total,
    bulk_settle_expected_incomes,
    income_payment_status,
)

pytestmark = pytest.mark.django_db

EntityType = AccountingChangeLog.EntityType
Action = AccountingChangeLog.Action


@pytest.fixture(autouse=True)
def _mute_notifications():
    with patch.object(accounting_service, '_notify') as notify:
        yield notify


def make_expected(**overrides):
    fields = {
        'concept': 'Kore - Fase 2 Entrega',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-06-01',
        'total_amount': Decimal('1000000.00'),
        'gustavo_amount': Decimal('500000.00'),
        'carlos_amount': Decimal('500000.00'),
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def abono(allocations, total, **overrides):
    data = {
        'allocations': [
            {'income_id': income.pk, 'amount': Decimal(amount)}
            for income, amount in allocations
        ],
        'total_amount': Decimal(total),
        'period_date': '2026-08-15',
        'notes': '',
    }
    data.update(overrides)
    return data


def issue_collection_account(income):
    return Document.objects.create(
        title=f'Cuenta de {income.concept}',
        document_type=DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0],
        commercial_status=Document.CommercialStatus.ISSUED,
        income_record=income,
        client_user=income.client.user,
        project=income.project,
    )


class TestAbonoHappyPath:
    def test_kore_case_two_full_and_one_partial_share_one_movement(
        self, superuser,
    ):
        fase2 = make_expected(total_amount=Decimal('500000.00'),
                              gustavo_amount=Decimal('250000.00'),
                              carlos_amount=Decimal('250000.00'))
        fase3 = make_expected(concept='Kore - Fase 3 Inicio',
                              total_amount=Decimal('300000.00'),
                              gustavo_amount=Decimal('150000.00'),
                              carlos_amount=Decimal('150000.00'))
        diseno = make_expected(concept='Kore - Fase 3 Diseño',
                               total_amount=Decimal('400000.00'),
                               gustavo_amount=Decimal('200000.00'),
                               carlos_amount=Decimal('200000.00'))

        result = bulk_settle_expected_incomes(
            abono([(fase2, '500000.00'), (fase3, '300000.00'),
                   (diseno, '200000.00')], '1000000.00'),
            superuser,
        )

        movement = result['movement']
        assert PocketMovement.objects.count() == 1
        assert movement.amount == Decimal('1000000.00')
        assert movement.income_records.count() == 3
        assert income_payment_status(fase2) == 'paid'
        assert income_payment_status(fase3) == 'paid'
        assert income_payment_status(diseno) == 'partial'
        assert diseno.total_amount - _paid_total(diseno) == Decimal('200000.00')

    def test_exact_cover_marks_every_parent_paid(self, superuser):
        first = make_expected(total_amount=Decimal('500000.00'),
                              gustavo_amount=Decimal('250000.00'),
                              carlos_amount=Decimal('250000.00'))
        second = make_expected(concept='Kore - Fase 3 Inicio',
                               total_amount=Decimal('300000.00'),
                               gustavo_amount=Decimal('150000.00'),
                               carlos_amount=Decimal('150000.00'))

        result = bulk_settle_expected_incomes(
            abono([(first, '500000.00'), (second, '300000.00')], '800000.00'),
            superuser,
        )

        assert result['movement'].amount == Decimal('800000.00')
        assert income_payment_status(first) == 'paid'
        assert income_payment_status(second) == 'paid'

    def test_single_income_abono_keeps_the_one_to_one_semantics(
        self, superuser,
    ):
        parent = make_expected()

        result = bulk_settle_expected_incomes(
            abono([(parent, '400000.00')], '400000.00'), superuser,
        )

        movement = result['movement']
        child = movement.income_records.get()
        assert movement.is_shared is False
        assert movement.linked_record == child
        assert child.expected_income_id == parent.pk
        assert income_payment_status(parent) == 'partial'

    def test_children_inherit_the_parent_and_ride_the_pocket(
        self, superuser, make_client_profile,
    ):
        profile = make_client_profile(company='Kore SAS')
        parent = make_expected(client=profile,
                               origin=IncomeRecord.Origin.DEVELOPMENT)
        issue_collection_account(parent)

        result = bulk_settle_expected_incomes(
            abono([(parent, '1000000.00')], '1000000.00'), superuser,
        )

        child = result['liquids'][0]
        assert child.concept == parent.concept
        assert child.client_id == profile.pk
        assert child.origin == IncomeRecord.Origin.DEVELOPMENT
        assert child.destination == IncomeRecord.Destination.POCKET
        assert child.gustavo_amount == child.carlos_amount
        assert child.source_ref == f'abono:{result["movement"].pk}'

    def test_paid_client_income_without_account_delivers_one_durable_notice(
        self, superuser, make_client_profile, django_capture_on_commit_callbacks, mailoutbox,
    ):
        """Falla si liquidar sin cuenta previa vuelve a bloquearse o duplica su aviso al rehacer el abono."""
        from content.models import IncomeCompletionNotice
        from content.services.accounting_abono_service import delete_income_abono

        parent = make_expected(client=make_client_profile(company='Kore SAS'))
        settings = AccountingSettings.load()
        settings.notifications_enabled = True
        settings.save(update_fields=['notifications_enabled'])
        NotificationRecipient.objects.create(email='contabilidad@example.test')

        with django_capture_on_commit_callbacks(execute=True):
            first = bulk_settle_expected_incomes(
                abono([(parent, '1000000.00')], '1000000.00'), superuser,
            )

        assert Document.objects.filter(income_record=parent).count() == 0
        assert income_payment_status(parent) == 'paid'
        assert IncomeCompletionNotice.objects.filter(income=parent).count() == 1

        delete_income_abono(first['movement'].pk, superuser)
        parent.refresh_from_db()
        assert income_payment_status(parent) == 'pending'

        with django_capture_on_commit_callbacks(execute=True):
            bulk_settle_expected_incomes(
                abono([(parent, '1000000.00')], '1000000.00'), superuser,
            )

        assert IncomeCompletionNotice.objects.filter(income=parent).count() == 1
        assert [message.to for message in mailoutbox] == [['contabilidad@example.test']]


class TestSaldoAFavor:
    def test_excess_becomes_a_parentless_credit_of_the_client(
        self, superuser, make_client_profile,
    ):
        profile = make_client_profile(company='Kore SAS')
        parent = make_expected(client=profile,
                               total_amount=Decimal('500000.00'),
                               gustavo_amount=Decimal('250000.00'),
                               carlos_amount=Decimal('250000.00'))
        issue_collection_account(parent)

        result = bulk_settle_expected_incomes(
            abono([(parent, '500000.00')], '700000.00'), superuser,
        )

        credit = result['credit']
        assert credit.expected_income_id is None
        assert credit.kind == IncomeRecord.Kind.LIQUID
        assert credit.client_id == profile.pk
        assert credit.concept.startswith('Saldo a favor')
        assert credit.total_amount == Decimal('200000.00')
        assert credit.pocket_movement_id == result['movement'].pk

    def test_excess_without_clients_creates_an_unassigned_credit(
        self, superuser,
    ):
        parent = make_expected(total_amount=Decimal('500000.00'),
                               gustavo_amount=Decimal('250000.00'),
                               carlos_amount=Decimal('250000.00'))

        result = bulk_settle_expected_incomes(
            abono([(parent, '500000.00')], '600000.00'), superuser,
        )

        assert result['credit'].client_id is None
        assert result['credit'].concept == 'Saldo a favor'
        assert result['movement'].amount == Decimal('600000.00')

    def test_excess_with_mixed_clients_is_rejected(
        self, superuser, make_client_profile,
    ):
        first = make_expected(client=make_client_profile(company='Kore SAS'))
        second = make_expected(client=make_client_profile(company='Globex'),
                               concept='Globex - Fase 1')
        issue_collection_account(first)
        issue_collection_account(second)

        with pytest.raises(ValueError, match='clientes mezclados'):
            bulk_settle_expected_incomes(
                abono([(first, '1000000.00'), (second, '1000000.00')],
                      '2500000.00'),
                superuser,
            )
        assert PocketMovement.objects.count() == 0


class TestAbonoValidation:
    def test_rejects_an_allocation_above_the_pending(self, superuser):
        parent = make_expected()
        IncomeRecord.objects.create(
            concept='Abono previo', kind=IncomeRecord.Kind.LIQUID,
            period_date='2026-07-01', total_amount=Decimal('700000.00'),
            gustavo_amount=Decimal('350000.00'),
            carlos_amount=Decimal('350000.00'), expected_income=parent,
        )

        with pytest.raises(ValueError, match='supera su saldo pendiente'):
            bulk_settle_expected_incomes(
                abono([(parent, '400000.00')], '400000.00'), superuser,
            )

    def test_rejects_a_non_expected_record(self, superuser):
        liquid = make_expected(kind=IncomeRecord.Kind.LIQUID)

        with pytest.raises(ValueError, match='ingresos esperados'):
            bulk_settle_expected_incomes(
                abono([(liquid, '100000.00')], '100000.00'), superuser,
            )

    def test_rejects_a_personal_ledger_income(self, superuser):
        personal = make_expected(
            ledger='gustavo', gustavo_amount=Decimal('1000000.00'),
            carlos_amount=Decimal('0'),
        )

        with pytest.raises(ValueError, match='contabilidad personal'):
            bulk_settle_expected_incomes(
                abono([(personal, '100000.00')], '100000.00'), superuser,
            )

    def test_rejects_an_already_paid_parent(self, superuser):
        parent = make_expected()
        IncomeRecord.objects.create(
            concept='Pago total', kind=IncomeRecord.Kind.LIQUID,
            period_date='2026-07-01', total_amount=Decimal('1000000.00'),
            gustavo_amount=Decimal('500000.00'),
            carlos_amount=Decimal('500000.00'), expected_income=parent,
        )

        with pytest.raises(ValueError, match='completamente pagado'):
            bulk_settle_expected_incomes(
                abono([(parent, '100000.00')], '100000.00'), superuser,
            )

    def test_a_failed_rule_writes_nothing(self, superuser):
        healthy = make_expected()
        overdrawn = make_expected(concept='Kore - Fase 3 Inicio',
                                  total_amount=Decimal('100000.00'),
                                  gustavo_amount=Decimal('50000.00'),
                                  carlos_amount=Decimal('50000.00'))

        with pytest.raises(ValueError):
            bulk_settle_expected_incomes(
                abono([(healthy, '500000.00'), (overdrawn, '200000.00')],
                      '700000.00'),
                superuser,
            )

        assert PocketMovement.objects.count() == 0
        assert IncomeRecord.objects.count() == 2


class TestAbonoAuditAndEmail:
    def test_audits_the_movement_and_every_child(self, superuser):
        first = make_expected()
        second = make_expected(concept='Kore - Fase 3 Inicio')

        result = bulk_settle_expected_incomes(
            abono([(first, '400000.00'), (second, '300000.00')], '700000.00'),
            superuser,
        )

        pocket_created = AccountingChangeLog.objects.filter(
            entity_type=EntityType.POCKET, action=Action.CREATED,
        )
        assert pocket_created.count() == 1
        assert pocket_created.get().object_id == result['movement'].pk
        assert AccountingChangeLog.objects.filter(
            entity_type=EntityType.INCOME, action=Action.CREATED,
        ).count() == 2

    def test_sends_exactly_one_email(self, superuser, _mute_notifications):
        first = make_expected()
        second = make_expected(concept='Kore - Fase 3 Inicio')

        bulk_settle_expected_incomes(
            abono([(first, '400000.00'), (second, '300000.00')], '700000.00'),
            superuser,
        )

        assert _mute_notifications.call_count == 1
