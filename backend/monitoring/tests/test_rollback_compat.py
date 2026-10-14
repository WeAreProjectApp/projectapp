"""Database contracts that keep monitoring writable when the code is rolled back."""

import pytest
from django.db import connection

from monitoring.models import Delivery
from monitoring.tests.test_ingest import monitored_resource, monitored_source  # noqa: F401

# The INSERT behind the pre-0004 ingest(): that Delivery model never named heartbeat_hour or milestone.
PRE_0004_RECEIPT_INSERT = (
    'INSERT INTO monitoring_delivery '
    '(source_id, external_id, digest, kind, observed_at, received_at, case_id, report_id, evidence) '
    'VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, %s)'
)


@pytest.mark.django_db
def test_receipt_inserted_by_pre_0004_code_is_not_a_milestone(monitored_source):
    """Falla si `milestone` queda sin default en la base: el ingest() previo a 0004 inserta sin esa columna y, con el código revertido sobre la base ya migrada, MySQL lo rechaza con el error 1364."""
    with connection.cursor() as cursor:
        cursor.execute(PRE_0004_RECEIPT_INSERT, [
            monitored_source.pk, 'silk:rollback:1', 'a' * 64, 'detection',
            '2024-01-01 09:00:00', '2024-01-01 09:00:00', '{}',
        ])

    assert Delivery.objects.get(source=monitored_source, external_id='silk:rollback:1').milestone is False
