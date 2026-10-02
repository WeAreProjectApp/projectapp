"""Compatibility and stale-scope rejection for financial client assignment."""
from datetime import date
from decimal import Decimal

import pytest

from content.models import (
    AccountingChangeLog, Document, EntityHistory, EntityRevision,
    HostingRecord, IncomeRecord, PocketMovement,
)
from content.services.accounting_service import EntityType, bulk_assign_client
from content.views import accounting as accounting_views


pytestmark = pytest.mark.django_db


@pytest.fixture
def unlinked_income():
    return IncomeRecord.objects.create(
        concept='Ingreso legado sin cliente', kind=IncomeRecord.Kind.EXPECTED,
        period_date=date(2026, 10, 1), total_amount=Decimal('120000'),
        gustavo_amount=Decimal('60000'), carlos_amount=Decimal('60000'),
    )


@pytest.fixture
def unlinked_hosting():
    return HostingRecord.objects.create(
        client_name='Hosting legado sin cliente', monthly_value=Decimal('50000'),
        payment_per_cycle=Decimal('150000'),
    )


@pytest.fixture
def assignment_admin(admin_user):
    admin_user.is_superuser = True
    admin_user.save(update_fields=['is_superuser'])
    return admin_user


def assignment_history_counts(record, entity_type):
    return (
        Document.objects.count(), PocketMovement.objects.count(),
        AccountingChangeLog.objects.filter(entity_type=entity_type, object_id=record.pk).count(),
        EntityHistory.objects.filter(entity_type=entity_type, object_id=record.pk).count(),
        EntityRevision.objects.filter(history__entity_type=entity_type, history__object_id=record.pk).count(),
    )


@pytest.mark.parametrize(('fixture_name', 'entity_type'), [
    ('unlinked_income', EntityType.INCOME),
    ('unlinked_hosting', EntityType.HOSTING),
])
def test_internal_client_assignment_skips_ids_absent_before_discovery(
    request, fixture_name, entity_type, client_user, assignment_admin,
):
    """Falla si un ID inexistente impide completar y auditar el registro real."""
    record = request.getfixturevalue(fixture_name)
    profile = client_user.profile

    updated = bulk_assign_client(
        entity_type, [record.pk, 999999], profile, assignment_admin,
    )

    record.refresh_from_db()
    assert [row.pk for row in updated] == [record.pk]
    assert record.client_id == profile.pk
    assert AccountingChangeLog.objects.filter(
        entity_type=entity_type, object_id=record.pk,
        action=AccountingChangeLog.Action.UPDATED,
    ).count() == 1
    assert not type(record).objects.filter(pk=999999).exists()
    assert not PocketMovement.objects.exists()


@pytest.mark.parametrize(('fixture_name', 'entity_type', 'path', 'ids_field'), [
    ('unlinked_income', EntityType.INCOME, 'incomes', 'income_ids'),
    ('unlinked_hosting', EntityType.HOSTING, 'hostings', 'hosting_ids'),
])
def test_client_assignment_endpoint_rejects_deletion_after_scope_validation(
    request, fixture_name, entity_type, path, ids_field,
    client_user, assignment_admin, api_client, monkeypatch,
):
    """Borra una fila tras el precheck real; exige 409 sin asignación ni historia parcial."""
    survivor = request.getfixturevalue(fixture_name)
    vanished = type(survivor).objects.get(pk=survivor.pk)
    vanished.pk = None
    vanished.save()
    vanished_id = vanished.pk
    before_check = accounting_views._missing_records_error

    def delete_after_scope_check(*args, **kwargs):
        result = before_check(*args, **kwargs)
        assert result is None
        type(survivor).objects.filter(pk=vanished_id).delete()
        return result

    monkeypatch.setattr(accounting_views, '_missing_records_error', delete_after_scope_check)
    api_client.force_authenticate(assignment_admin)
    before = assignment_history_counts(survivor, entity_type)

    response = api_client.post(
        f'/api/accounting/{path}/bulk-assign-client/',
        {ids_field: [survivor.pk, vanished_id], 'client': client_user.profile.pk},
        format='json',
    )

    survivor.refresh_from_db()
    assert response.status_code == 409
    assert response.data['detail'].code == 'billing_conflict'
    assert survivor.client_id is None
    assert assignment_history_counts(survivor, entity_type) == before
