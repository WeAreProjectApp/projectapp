"""Normalization and resumable public-source synchronization coverage."""

from decimal import Decimal

import pytest
from procurement.models import Opportunity, SyncRun
from procurement.services.source import normalized_record
from procurement.services.sync import synchronize_page

pytestmark = pytest.mark.django_db


def source_row(source_id='SECOP-1', **changes):
    """Build one representative public SECOP response without network I/O."""
    row = {
        'id_del_proceso': source_id,
        'referencia_del_proceso': 'REF-001',
        'nombre_del_procedimiento': 'Servicios de apoyo',
        'entidad': 'Entidad Nacional',
        'departamento_entidad': 'Bogotá D.C.',
        'estado_del_procedimiento': 'Abierto',
        'codigo_principal_de_categoria': 'V1.80101500',
        'precio_base': '1250000.50',
        'urlproceso': 'https://community.secop.gov.co/Proceso/SECOP-1',
    }
    row.update(changes)
    return row


def test_normalized_record_keeps_source_identifier_and_unspsc_code():
    """Falla si normalizar SECOP pierde el identificador o el código UNSPSC usable."""
    source_id, complete = normalized_record(source_row())

    assert (source_id, complete['unspsc_code'], complete['budget']) == ('SECOP-1', '80101500', Decimal('1250000.50'))


def test_normalized_record_converts_invalid_budget_to_none():
    """Falla si un monto público corrupto rompe la sincronización en vez de quedar vacío."""
    _source_id, invalid_budget = normalized_record(source_row('SECOP-2', precio_base='no-es-un-monto'))

    assert invalid_budget['budget'] is None


def test_normalized_record_removes_non_official_source_url():
    """Falla si el panel puede enlazar una URL externa no autorizada por SECOP."""
    _source_id, unsafe_url = normalized_record(source_row('SECOP-3', urlproceso='https://example.test/proceso'))

    assert unsafe_url['source_url'] == ''


class PartialPageClient:
    """Return a valid and an invalid source row, then finish tracked refresh."""

    def page(self, *, ids=None, **_kwargs):
        """Provide deterministic page data for the synchronization boundary."""
        if ids is not None:
            return []
        return [source_row('VALID-1'), source_row('', nombre_del_procedimiento='Sin identificador')]


def test_sync_marks_partial_after_preserving_valid_records():
    """Falla si una fila defectuosa descarta la página completa o se reporta como éxito total."""
    run = SyncRun.objects.create(cursor={'offset': 0, 'since': None, 'phase': 'source'})
    client = PartialPageClient()

    synchronize_page(run.pk, client)
    synchronize_page(run.pk, client)

    run.refresh_from_db()
    assert Opportunity.objects.filter(source_id='VALID-1').exists()
    assert (run.processed, run.errors, run.status) == (1, 1, 'partial')
    assert run.finished_at is not None


class FailingClient:
    """Represent a public source that remains unavailable across retries."""

    def page(self, **_kwargs):
        """Raise the same source-boundary error for every request."""
        raise RuntimeError('Origen público temporalmente inaccesible')


def test_sync_stops_after_three_source_failures_without_deleting_existing_opportunity(opportunity):
    """Falla si una caída repetida queda en ciclo infinito o borra oportunidades locales previas."""
    existing = opportunity('KEEP-ON-FAILURE')
    run = SyncRun.objects.create(cursor={'offset': 0, 'since': None, 'phase': 'source'})
    client = FailingClient()

    synchronize_page(run.pk, client)
    synchronize_page(run.pk, client)
    synchronize_page(run.pk, client)

    run.refresh_from_db()
    assert (run.status, run.cursor['failures']) == ('failed', 3)
    assert run.finished_at is not None
    assert Opportunity.objects.filter(pk=existing.pk, source_id='KEEP-ON-FAILURE').exists()
