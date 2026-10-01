"""A permitted financial delete cannot turn a stale update into a new record."""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.views import exception_handler

from accounts.services.billing_access import BillingConflict
from content.models import (
    AccountingChangeLog, Document, EntityHistory, EntityRevision,
    HostingRecord, IncomeRecord, PocketMovement,
)
from content.serializers.accounting import (
    HostingRecordCreateUpdateSerializer, IncomeRecordCreateUpdateSerializer,
)
from content.services.accounting_service import EntityType, update_record


pytestmark = pytest.mark.django_db


@pytest.fixture
def missing_income(project):
    return IncomeRecord.objects.create(
        concept='Ingreso sin cobros ni pagos', kind=IncomeRecord.Kind.EXPECTED,
        client=project.client.profile, project=project,
        period_date=date(2026, 10, 1), total_amount=Decimal('120000'),
        gustavo_amount=Decimal('60000'), carlos_amount=Decimal('60000'),
    )


def financial_history_counts():
    return tuple(model.objects.count() for model in (
        IncomeRecord, HostingRecord, Document, PocketMovement,
        AccountingChangeLog, EntityHistory, EntityRevision,
    ))


@pytest.mark.parametrize(('fixture_name', 'entity_type', 'serializer_type', 'path'), [
    ('missing_income', EntityType.INCOME, IncomeRecordCreateUpdateSerializer, 'incomes'),
    ('hosting_record', EntityType.HOSTING, HostingRecordCreateUpdateSerializer, 'hostings'),
])
def test_deleted_financial_record_rejects_a_validated_stale_update(
    request, api_client, admin_user, fixture_name, entity_type, serializer_type, path,
):
    """Falla si un origen desaparecido produce 500, se recrea o añade historia parcial."""
    record = request.getfixturevalue(fixture_name)
    record_id = record.pk
    serializer = serializer_type(record, data={'notes': 'Cambio desde una lectura anterior'}, partial=True)
    assert serializer.is_valid(), serializer.errors
    admin_user.is_superuser = True
    admin_user.save(update_fields=['is_superuser'])
    api_client.force_authenticate(admin_user)

    deleted = api_client.delete(f'/api/accounting/{path}/{record_id}/delete/')

    assert deleted.status_code == 204
    assert AccountingChangeLog.objects.filter(
        entity_type=entity_type, object_id=record_id,
        action=AccountingChangeLog.Action.DELETED,
    ).exists()
    after_delete = financial_history_counts()

    with pytest.raises(BillingConflict) as conflict:
        update_record(entity_type, record, serializer, admin_user, notify=False)

    assert exception_handler(conflict.value, {}).status_code == 409
    assert financial_history_counts() == after_delete
    assert not type(record).objects.filter(pk=record_id).exists()
