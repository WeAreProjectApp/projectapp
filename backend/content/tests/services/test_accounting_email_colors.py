from datetime import date
from decimal import Decimal

import pytest
from django.template.loader import render_to_string
from django.utils import timezone

from content.models import AccountingChangeLog, PocketMovement
from content.serializers.accounting import (
    AccountingChangeLogSerializer,
    IncomeRecordCreateUpdateSerializer,
    PocketMovementCreateUpdateSerializer,
)
from content.services import accounting_service
from content.services.accounting_email_service import (
    NOTIFICATION_TONE_INCOME,
    NOTIFICATION_TONE_NEUTRAL,
    NOTIFICATION_TONE_OUTFLOW,
    build_accounting_change_context,
    resolve_accounting_notification_tone,
)


EntityType = AccountingChangeLog.EntityType
Action = AccountingChangeLog.Action


def make_change_log(
    entity_type,
    *,
    action=Action.CREATED,
    movement_direction=None,
    changes=None,
):
    return AccountingChangeLog(
        entity_type=entity_type,
        object_id=1,
        object_repr='Registro contable',
        action=action,
        movement_direction=movement_direction,
        changes=changes or [],
        actor_username='super_test',
        created_at=timezone.now(),
    )


@pytest.mark.parametrize(
    ('entity_type', 'expected_tone'),
    [
        (EntityType.INCOME, NOTIFICATION_TONE_INCOME),
        (EntityType.EXPENSE, NOTIFICATION_TONE_OUTFLOW),
        (EntityType.RECURRING, NOTIFICATION_TONE_OUTFLOW),
        (EntityType.ADS, NOTIFICATION_TONE_OUTFLOW),
        (EntityType.CARD_SNAPSHOT, NOTIFICATION_TONE_OUTFLOW),
        (EntityType.STATEMENT, NOTIFICATION_TONE_OUTFLOW),
        (EntityType.STATEMENT_TX, NOTIFICATION_TONE_OUTFLOW),
        (EntityType.HOSTING, NOTIFICATION_TONE_NEUTRAL),
        (EntityType.CREDIT_CARD, NOTIFICATION_TONE_NEUTRAL),
    ],
)
def test_entity_type_resolves_financial_tone(entity_type, expected_tone):
    log = make_change_log(entity_type)

    assert resolve_accounting_notification_tone(log) == expected_tone


@pytest.mark.parametrize(
    ('direction', 'expected_tone'),
    [
        (
            AccountingChangeLog.MovementDirection.IN,
            NOTIFICATION_TONE_INCOME,
        ),
        (
            AccountingChangeLog.MovementDirection.OUT,
            NOTIFICATION_TONE_OUTFLOW,
        ),
        (None, NOTIFICATION_TONE_NEUTRAL),
    ],
)
def test_pocket_direction_resolves_financial_tone(direction, expected_tone):
    log = make_change_log(EntityType.POCKET, movement_direction=direction)

    assert resolve_accounting_notification_tone(log) == expected_tone


def test_direction_snapshot_stays_out_of_change_log_payload():
    log = make_change_log(
        EntityType.POCKET,
        movement_direction=AccountingChangeLog.MovementDirection.OUT,
    )

    assert 'movement_direction' not in AccountingChangeLogSerializer(log).data


@pytest.mark.django_db
def test_complete_pocket_diff_recovers_direction_snapshot():
    log = accounting_service.log_accounting_change(
        entity_type=EntityType.POCKET,
        object_id=1,
        object_repr='Compra de equipo',
        action=Action.CREATED,
        changes=[{
            'field': 'direction',
            'label': 'Tipo',
            'old': '',
            'new': 'Egreso',
        }],
    )

    assert log.movement_direction == AccountingChangeLog.MovementDirection.OUT


@pytest.mark.django_db
def test_pocket_update_persists_unchanged_direction(superuser):
    movement = PocketMovement.objects.create(
        concept='Compra de equipo',
        movement_date=date(2026, 9, 2),
        direction=PocketMovement.Direction.OUT,
        amount=Decimal('200000.00'),
    )
    serializer = PocketMovementCreateUpdateSerializer(
        movement,
        data={'concept': 'Compra de portátil'},
        partial=True,
    )
    assert serializer.is_valid(), serializer.errors

    accounting_service.update_record(
        EntityType.POCKET,
        movement,
        serializer,
        superuser,
        notify=False,
    )

    log = AccountingChangeLog.objects.get(
        entity_type=EntityType.POCKET,
        object_id=movement.pk,
        action=Action.UPDATED,
    )
    assert log.movement_direction == AccountingChangeLog.MovementDirection.OUT


def test_created_change_uses_the_green_action_accent():
    """Falla si una creación deja de identificarse con el acento verde de acción."""
    log = make_change_log(
        EntityType.EXPENSE,
        changes=[{
            'field': 'total_amount',
            'label': 'Monto total',
            'old': '',
            'new': '$200.000',
        }],
    )

    html = render_to_string(
        'emails/accounting_change.html',
        build_accounting_change_context(log),
    )

    assert 'background-color:#15803d;' in html
    assert 'background-color:#f9fafb;' in html
    assert 'color:#374151;">$200.000' in html


def test_updated_change_uses_blue_accent_with_neutral_values():
    """Falla si actualizar un registro vuelve a colorear los valores como una alerta."""
    log = make_change_log(
        EntityType.INCOME,
        action=Action.UPDATED,
        changes=[{
            'field': 'total_amount',
            'label': 'Monto total',
            'old': '$100.000',
            'new': '$200.000',
        }],
    )

    html = render_to_string(
        'emails/accounting_change.html',
        build_accounting_change_context(log),
    )

    assert 'background-color:#1d4ed8;' in html
    assert 'color:#374151;">$100.000' in html
    assert 'color:#374151;">$200.000' in html


def test_deleted_change_uses_red_accent_and_omits_new_value_column():
    """Falla si eliminar un registro pierde su señal roja o muestra un valor nuevo ficticio."""
    log = make_change_log(
        EntityType.POCKET,
        action=Action.DELETED,
        movement_direction=AccountingChangeLog.MovementDirection.OUT,
        changes=[{
            'field': 'amount',
            'label': 'Valor',
            'old': '$200.000',
            'new': '',
        }],
    )

    html = render_to_string(
        'emails/accounting_change.html',
        build_accounting_change_context(log),
    )

    assert 'background-color:#b91c1c;' in html
    assert 'color:#374151;">$200.000' in html
    assert 'Valor nuevo' not in html


def test_change_email_text_body_preserves_the_old_to_new_transition():
    """Falla si el correo en texto pierde el contraste legible entre valor anterior y nuevo."""
    log = make_change_log(
        EntityType.INCOME,
        action=Action.UPDATED,
        changes=[{
            'field': 'total_amount',
            'label': 'Monto total',
            'old': '$100.000',
            'new': '$200.000',
        }],
    )

    text = render_to_string(
        'emails/accounting_change.txt',
        build_accounting_change_context(log),
    )

    assert 'Monto total: $100.000 → $200.000' in text


@pytest.mark.django_db
@pytest.mark.parametrize('rate,display', [('19', '19 %'), ('5.25', '5.25 %')])
def test_vat_update_audits_the_rate_as_a_percentage(superuser, make_income, rate, display):
    """Falla si cambiar el IVA vuelve a guardar el valor nuevo con signo de pesos."""
    income = make_income(vat_rate=Decimal('0'))
    serializer = IncomeRecordCreateUpdateSerializer(
        income, data={'vat_rate': rate}, partial=True,
    )
    assert serializer.is_valid(), serializer.errors

    accounting_service.update_record(EntityType.INCOME, income, serializer, superuser, notify=False)

    log = AccountingChangeLog.objects.get(object_id=income.pk, entity_type=EntityType.INCOME)
    change = next(row for row in log.changes if row['field'] == 'vat_rate')
    assert change == {'field': 'vat_rate', 'label': 'IVA (%)', 'old': '0 %', 'new': display}


@pytest.mark.django_db
def test_legacy_vat_email_projects_percentages_without_rewriting_the_audit():
    """Falla si los correos muestran pesos para IVA o alteran el historial ya registrado."""
    raw_changes = [{'field': 'vat_rate', 'label': 'IVA (%)', 'old': '$0', 'new': '$19'}]
    log = make_change_log(EntityType.INCOME, action=Action.UPDATED, changes=raw_changes)
    log.save()

    context = build_accounting_change_context(log)
    html = render_to_string('emails/accounting_change.html', context)
    plain = render_to_string('emails/accounting_change.txt', context)

    assert '19 %' in html
    assert 'IVA (%): 0 % → 19 %' in plain
    log.refresh_from_db()
    assert log.changes == raw_changes
