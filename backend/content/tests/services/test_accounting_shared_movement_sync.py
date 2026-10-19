"""A legacy shared movement and its children obey stricter mirror rules.

movement.amount == Σ children has no DB constraint: these tests pin the
guards that keep historical abonos consistent even though they predate the
unified settlement operation: the abono reverses only as a unit (delete the
movement), one child can never fall alone, money fields are frozen on both
sides, and non-money edits stay local instead of mirroring.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from content.api_errors import ProposalActionError
from content.models import AccountingChangeLog, IncomeRecord, PocketMovement
from content.serializers.accounting import (
    IncomeRecordCreateUpdateSerializer,
    PocketMovementCreateUpdateSerializer,
)
from content.services import accounting_service
from content.services.accounting_settlement_service import income_payment_status

pytestmark = pytest.mark.django_db

EntityType = AccountingChangeLog.EntityType
Action = AccountingChangeLog.Action


@pytest.fixture(autouse=True)
def _mute_notifications():
    with patch.object(accounting_service, '_notify') as notify:
        yield notify


def make_expected(concept='Kore - Fase 2', total='500000.00'):
    half = (Decimal(total) / 2).quantize(Decimal('0.01'))
    return IncomeRecord.objects.create(
        concept=concept,
        kind=IncomeRecord.Kind.EXPECTED,
        period_date=date(2026, 6, 1),
        total_amount=Decimal(total),
        gustavo_amount=half,
        carlos_amount=Decimal(total) - half,
    )


def make_legacy_abono(superuser, allocations, total):
    """Build the pre-operation graph still present in accounting history."""
    movement = PocketMovement.objects.create(
        concept=f'Abono {len(allocations)} ingresos',
        movement_date=date(2026, 8, 15),
        direction=PocketMovement.Direction.IN,
        amount=Decimal(total),
        created_by=superuser,
    )
    source_ref = f'abono:{movement.pk}'
    movement.source_ref = source_ref
    movement.save(update_fields=['source_ref'])
    children = []
    for income, raw_amount in allocations:
        amount = Decimal(raw_amount)
        half = (amount / 2).quantize(Decimal('0.01'))
        children.append(IncomeRecord.objects.create(
            concept=income.concept,
            kind=IncomeRecord.Kind.LIQUID,
            period_date=date(2026, 8, 15),
            destination=IncomeRecord.Destination.POCKET,
            ledger=income.ledger,
            vat_rate=income.vat_rate,
            total_amount=amount,
            gustavo_amount=half,
            carlos_amount=amount - half,
            expected_income=income,
            pocket_movement=movement,
            client=income.client,
            project=income.project,
            origin=income.origin,
            source_ref=source_ref,
            created_by=superuser,
        ))
    return {
        'movement': movement,
        'incomes': [income for income, _ in allocations],
        'liquids': children,
        'credit': None,
    }


def shared_legacy_abono(superuser):
    first = make_expected()
    second = make_expected(concept='Kore - Fase 3')
    result = make_legacy_abono(
        superuser, [(first, '500000.00'), (second, '300000.00')], '800000.00',
    )
    return first, second, result


class TestAbonoReversal:
    def test_deleting_the_movement_reverses_the_whole_abono(self, superuser):
        first, second, result = shared_legacy_abono(superuser)

        accounting_service.delete_record(
            EntityType.POCKET, result['movement'], superuser,
        )

        assert PocketMovement.objects.count() == 0
        assert IncomeRecord.objects.filter(
            kind=IncomeRecord.Kind.LIQUID,
        ).count() == 0
        assert income_payment_status(first) == 'pending'
        assert income_payment_status(second) == 'pending'
        assert AccountingChangeLog.objects.filter(
            entity_type=EntityType.INCOME, action=Action.DELETED,
        ).count() == 2

    def test_deleting_one_shared_child_is_rejected(self, superuser):
        _, _, result = shared_legacy_abono(superuser)
        child = result['liquids'][0]

        with pytest.raises(ValueError, match='hace parte de un abono'):
            accounting_service.delete_record(
                EntityType.INCOME, child, superuser,
            )
        assert IncomeRecord.objects.filter(pk=child.pk).exists()
        assert PocketMovement.objects.count() == 1

    def test_a_single_child_movement_still_cascades_both_ways(self, superuser):
        parent = make_expected()
        result = make_legacy_abono(
            superuser, [(parent, '400000.00')], '400000.00',
        )
        child = result['liquids'][0]

        accounting_service.delete_record(EntityType.INCOME, child, superuser)

        assert PocketMovement.objects.count() == 0
        assert income_payment_status(parent) == 'pending'


class TestSharedChildEdits:
    def test_resizing_a_shared_child_is_rejected(self, superuser):
        _, _, result = shared_legacy_abono(superuser)
        child = result['liquids'][0]
        serializer = IncomeRecordCreateUpdateSerializer(
            instance=child, data={'total_amount': '999000.00'}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors

        with pytest.raises(ProposalActionError) as exc_info:
            accounting_service.update_record(
                EntityType.INCOME, child, serializer, superuser,
            )
        assert exc_info.value.code == 'abono_child_locked'

    def test_a_concept_edit_stays_on_the_child(self, superuser):
        _, _, result = shared_legacy_abono(superuser)
        child = result['liquids'][0]
        movement = result['movement']
        serializer = IncomeRecordCreateUpdateSerializer(
            instance=child, data={'concept': 'Kore - Fase 2 (ajustado)'},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

        accounting_service.update_record(
            EntityType.INCOME, child, serializer, superuser,
        )

        child.refresh_from_db()
        movement.refresh_from_db()
        assert child.concept == 'Kore - Fase 2 (ajustado)'
        assert movement.concept.startswith('Abono')
        assert movement.amount == Decimal('800000.00')

    def test_repointing_expected_income_stays_allowed(self, superuser):
        _, _, result = shared_legacy_abono(superuser)
        child = result['liquids'][0]
        new_parent = make_expected(concept='Kore - Fase 4', total='900000.00')
        serializer = IncomeRecordCreateUpdateSerializer(
            instance=child, data={'expected_income': new_parent.pk},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

        accounting_service.update_record(
            EntityType.INCOME, child, serializer, superuser,
        )

        child.refresh_from_db()
        assert child.expected_income_id == new_parent.pk
        assert income_payment_status(new_parent) == 'partial'


class TestSharedMovementEdits:
    def test_resizing_the_movement_is_rejected(self, superuser):
        _, _, result = shared_legacy_abono(superuser)
        movement = result['movement']
        serializer = PocketMovementCreateUpdateSerializer(
            instance=movement, data={'amount': '999000.00'}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors

        with pytest.raises(ProposalActionError) as exc_info:
            accounting_service.update_record(
                EntityType.POCKET, movement, serializer, superuser,
            )
        assert exc_info.value.code == 'abono_amount_locked'

    def test_a_movement_concept_edit_touches_no_child(self, superuser):
        _, _, result = shared_legacy_abono(superuser)
        movement = result['movement']
        original_concepts = sorted(
            movement.income_records.values_list('concept', flat=True),
        )
        serializer = PocketMovementCreateUpdateSerializer(
            instance=movement, data={'concept': 'Abono Kore (agosto)'},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

        accounting_service.update_record(
            EntityType.POCKET, movement, serializer, superuser,
        )

        movement.refresh_from_db()
        assert movement.concept == 'Abono Kore (agosto)'
        assert sorted(
            movement.income_records.values_list('concept', flat=True),
        ) == original_concepts

    def test_the_direction_lock_still_covers_shared_movements(self, superuser):
        _, _, result = shared_legacy_abono(superuser)
        movement = result['movement']
        serializer = PocketMovementCreateUpdateSerializer(
            instance=movement, data={'direction': 'out'}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors

        with pytest.raises(ProposalActionError) as exc_info:
            accounting_service.update_record(
                EntityType.POCKET, movement, serializer, superuser,
            )
        assert exc_info.value.code == 'linked_direction_locked'
