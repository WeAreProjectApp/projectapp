"""MCP schema, confirmation, ownership, and audit-trail behavior coverage."""

import base64
import json
from io import BytesIO

import pytest
from content.models import McpConnector, McpCredential
from openpyxl import load_workbook
from procurement.models import (
    Activity,
    Alert,
    Classification,
    Delivery,
    SavedSearch,
    Settings,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def mcp_token():
    """Return an active procurement capability token with the service actor."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='procurement', defaults={'name': 'Contratación estatal'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


@pytest.fixture
def staff_mcp_token(staff_user):
    """Return a procurement token constrained to a non-superuser staff actor."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='procurement', defaults={'name': 'Contratación estatal'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    credential = McpCredential.objects.create(
        connector=connector, label='Staff procurement test', token_hash='pending', actor=staff_user,
    )
    return credential.generate_token()


def call_tool(api_client, token, name, arguments):
    """Call one procurement MCP tool through its JSON-RPC transport."""
    return api_client.post(
        f'/api/mcp/procurement/{token}/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}},
        format='json',
    )


def result(response):
    """Return the JSON-RPC result object."""
    return response.data['result']


def content(response):
    """Decode the JSON result emitted in the MCP text content."""
    return json.loads(result(response)['content'][0]['text'])


def test_mcp_rejects_unknown_arguments_without_side_effect(api_client, mcp_token):
    """Falla si una herramienta MCP acepta argumentos fuera de su esquema declarado."""
    settings = Settings.current()
    rejected = call_tool(api_client, mcp_token, 'list_procurement_opportunities', {'unexpected': True})

    settings.refresh_from_db()
    assert result(rejected)['isError'] is True
    assert settings.email_enabled is False


def test_mcp_settings_change_requires_confirmation_before_mutating(api_client, mcp_token):
    """Falla si el MCP habilita envíos sin que el operador confirme el cambio sensible."""
    settings = Settings.current()
    preview = call_tool(api_client, mcp_token, 'update_procurement_settings', {'email_enabled': True})

    settings.refresh_from_db()
    confirmation_id = result(preview)['structuredContent']['confirmation_id']
    assert settings.email_enabled is False

    confirmed = call_tool(api_client, mcp_token, 'confirm_action', {'confirmation_id': confirmation_id})
    settings.refresh_from_db()

    assert settings.email_enabled is True
    assert content(confirmed)['result']['email_enabled'] is True


def test_mcp_records_external_analysis_without_returning_raw_source_data(api_client, mcp_token, opportunity, staff_user):
    """Falla si el asistente no deja trazabilidad de su descarte o recibe la respuesta cruda de SECOP."""
    record = opportunity('MCP-ANALYSIS', source_data={'internal': 'raw supplier response'})
    saved = call_tool(api_client, mcp_token, 'set_procurement_classification', {
        'id': record.pk, 'owner_id': staff_user.pk, 'state': 'discarded', 'notes': 'No cumple experiencia mínima.',
    })
    detail = call_tool(api_client, mcp_token, 'get_procurement_opportunity', {'id': record.pk})
    rejected = call_tool(api_client, mcp_token, 'get_procurement_opportunity', {
        'id': record.pk, 'source_data': True,
    })

    data = content(detail)
    assert content(saved)['state'] == 'discarded'
    assert data['classifications'][0]['notes'] == 'No cumple experiencia mínima.'
    assert data['activities'][0]['action'] == 'classify'
    assert Activity.objects.filter(classification__opportunity=record, action='classify').exists()
    assert 'source_data' not in data
    assert result(rejected)['isError'] is True


def test_staff_mcp_cannot_write_classifications_or_update_searches_for_another_owner(
        api_client, staff_mcp_token, opportunity, staff_user, other_staff_user):
    """Falla si una credencial de staff modifica análisis o búsquedas privadas de otro administrador."""
    record = opportunity('MCP-OWNER-GUARD')
    search = SavedSearch.objects.create(owner=other_staff_user, name='Privada', filters={})
    classification = call_tool(api_client, staff_mcp_token, 'set_procurement_classification', {
        'id': record.pk, 'owner_id': other_staff_user.pk, 'state': 'interesting', 'notes': 'Tomada.',
    })
    update = call_tool(api_client, staff_mcp_token, 'update_procurement_search', {
        'id': search.pk, 'owner_id': other_staff_user.pk, 'name': 'Tomada', 'filters': {},
    })

    assert result(classification)['isError'] is True
    assert result(update)['isError'] is True
    assert 'Sólo el principal administrador puede actuar para otro dueño.' in result(classification)['content'][0]['text']
    assert 'Sólo el principal administrador puede actuar para otro dueño.' in result(update)['content'][0]['text']
    assert Classification.objects.filter(opportunity=record).count() == 0
    assert Activity.objects.filter(classification__opportunity=record).count() == 0
    assert SavedSearch.objects.filter(pk=search.pk, owner=other_staff_user, name='Privada').exists()


def test_staff_mcp_cannot_confirm_deletion_of_another_owners_search(
        api_client, staff_mcp_token, other_staff_user):
    """Falla si una confirmación sensible permite borrar la búsqueda privada de otro administrador."""
    search = SavedSearch.objects.create(owner=other_staff_user, name='Sólo de otra persona', filters={})
    preview = call_tool(api_client, staff_mcp_token, 'delete_procurement_search', {
        'id': search.pk, 'owner_id': other_staff_user.pk,
    })
    confirmed = call_tool(api_client, staff_mcp_token, 'confirm_action', {
        'confirmation_id': result(preview)['structuredContent']['confirmation_id'],
    })

    assert result(confirmed)['isError'] is True
    assert 'Sólo el principal administrador puede actuar para otro dueño.' in result(confirmed)['content'][0]['text']
    assert SavedSearch.objects.filter(pk=search.pk, owner=other_staff_user).exists()


def test_mcp_creates_search_for_selected_staff_owner(api_client, mcp_token, staff_user):
    """Falla si el asistente guarda los filtros en el usuario de servicio en vez del dueño indicado."""
    response = call_tool(api_client, mcp_token, 'create_procurement_search', {
        'owner_id': staff_user.pk, 'name': 'Consultoría', 'filters': {'keywords': ['consultoría']},
    })

    saved = SavedSearch.objects.get(pk=content(response)['id'])
    assert saved.owner_id == staff_user.pk
    assert saved.filters['keywords'] == ['consultoría']


def test_mcp_lists_only_selected_owners_searches(api_client, mcp_token, staff_user, other_staff_user):
    """Falla si el conector mezcla búsquedas de administradores distintos."""
    mine = SavedSearch.objects.create(owner=staff_user, name='Seleccionada')
    SavedSearch.objects.create(owner=other_staff_user, name='Ajena')

    response = call_tool(api_client, mcp_token, 'list_procurement_searches', {'owner_id': staff_user.pk})

    assert [item['id'] for item in content(response)['results']] == [mine.pk]


def test_mcp_updates_selected_owners_search(api_client, mcp_token, staff_user):
    """Falla si una edición válida del asistente pierde los nuevos filtros personales."""
    search = SavedSearch.objects.create(owner=staff_user, name='Anterior')

    response = call_tool(api_client, mcp_token, 'update_procurement_search', {
        'id': search.pk, 'owner_id': staff_user.pk, 'name': 'Actualizada',
        'filters': {'departments': ['Antioquia']}, 'is_favorite': True,
    })

    search.refresh_from_db()
    assert content(response)['name'] == 'Actualizada'
    assert search.filters['departments'] == ['Antioquia']
    assert search.is_favorite is True


def test_mcp_deletes_search_only_after_confirmation(api_client, mcp_token, staff_user):
    """Falla si borrar filtros personales omite la confirmación o elimina una alerta compartida."""
    search = SavedSearch.objects.create(owner=staff_user, name='Temporal')
    shared = Alert.objects.create(name='Independiente', created_by=staff_user, recipients=['carlos@example.com'])
    preview = call_tool(api_client, mcp_token, 'delete_procurement_search', {
        'id': search.pk, 'owner_id': staff_user.pk,
    })
    assert SavedSearch.objects.filter(pk=search.pk).count() == 1

    confirmed = call_tool(api_client, mcp_token, 'confirm_action', {
        'confirmation_id': result(preview)['structuredContent']['confirmation_id'],
    })

    assert content(confirmed)['result'] == {'deleted': True}
    assert SavedSearch.objects.filter(pk=search.pk).count() == 0
    assert Alert.objects.get(pk=shared.pk).name == 'Independiente'


def test_mcp_creates_inactive_alert_after_confirmation(api_client, mcp_token):
    """Falla si crear una alerta elude la confirmación o habilita envíos por defecto."""
    preview = call_tool(api_client, mcp_token, 'create_procurement_alert', {
        'name': 'Consultoría', 'filters': {'keywords': ['consultoría']},
        'recipients': ['Carlos@example.com'], 'frequency': 'weekly',
    })
    assert Alert.objects.count() == 0

    confirmed = call_tool(api_client, mcp_token, 'confirm_action', {
        'confirmation_id': result(preview)['structuredContent']['confirmation_id'],
    })

    saved = Alert.objects.get(pk=content(confirmed)['result']['id'])
    assert saved.recipients == ['carlos@example.com']
    assert saved.frequency == 'weekly'
    assert saved.is_active is False


def test_mcp_alert_edit_waits_for_confirmation(api_client, mcp_token, alert):
    """Falla si cambiar la frecuencia de una alerta compartida no exige confirmación."""
    shared = alert(is_active=False)
    preview = call_tool(api_client, mcp_token, 'update_procurement_alert', {
        'id': shared.pk, 'frequency': 'weekly',
    })
    shared.refresh_from_db()
    assert shared.frequency == 'daily'

    confirmed = call_tool(api_client, mcp_token, 'confirm_action', {
        'confirmation_id': result(preview)['structuredContent']['confirmation_id'],
    })

    shared.refresh_from_db()
    assert content(confirmed)['result']['frequency'] == 'weekly'
    assert shared.version == 2
    assert shared.recipients == ['carlos@example.com']


def test_mcp_alert_preview_excludes_closed_matches(api_client, mcp_token, alert, opportunity):
    """Falla si previsualizar una alerta presenta contratos cerrados como oportunidades elegibles."""
    shared = alert(filters={'keywords': ['consultoría'], 'is_open': False}, is_active=False)
    eligible = opportunity('PREVIEW-OPEN', title='Consultoría tecnológica')
    opportunity('PREVIEW-CLOSED', title='Consultoría cerrada', source_status='Adjudicado')
    opportunity('PREVIEW-OTHER', title='Construcción de carretera')

    response = call_tool(api_client, mcp_token, 'preview_procurement_alert', {'id': shared.pk})

    assert [item['id'] for item in content(response)['results']] == [eligible.pk]


def test_mcp_lists_shared_alert_configuration(api_client, mcp_token, alert):
    """Falla si el asistente no puede consultar destinatarios y frecuencia de las alertas compartidas."""
    shared = alert(is_active=False, frequency='weekly')

    response = call_tool(api_client, mcp_token, 'list_procurement_alerts', {})

    assert content(response)['results'][0]['id'] == shared.pk
    assert content(response)['results'][0]['recipients'] == ['carlos@example.com']
    assert content(response)['results'][0]['frequency'] == 'weekly'


def test_mcp_delivery_list_keeps_snapshot_out_of_summary(api_client, mcp_token):
    """Falla si el listado del asistente descarga toda la evidencia de correo en cada fila."""
    delivery = Delivery.objects.create(recipient='carlos@example.com', frequency='daily',
                                       opportunity_count=2, snapshot={'evidence': 'preserved'})

    response = call_tool(api_client, mcp_token, 'list_procurement_deliveries', {'page': 1})

    assert content(response)['results'][0]['id'] == delivery.pk
    assert content(response)['results'][0]['opportunity_count'] == 2
    assert 'snapshot' not in content(response)['results'][0]


def test_mcp_delivery_detail_preserves_exact_sent_evidence(api_client, mcp_token):
    """Falla si el asistente no puede auditar la instantánea exacta de una entrega."""
    delivery = Delivery.objects.create(recipient='carlos@example.com', frequency='daily',
                                       snapshot={'filters': {'keywords': ['consultoría']}})

    response = call_tool(api_client, mcp_token, 'get_procurement_delivery', {'id': delivery.pk})

    assert content(response)['snapshot'] == {'filters': {'keywords': ['consultoría']}}


def test_mcp_export_contains_filtered_opportunity(api_client, mcp_token, opportunity):
    """Falla si el Excel que recibe el asistente incluye procesos fuera de sus filtros."""
    selected = opportunity('MCP-EXPORT', department='Antioquia')
    opportunity('MCP-EXCLUDED', department='Caldas')

    response = call_tool(api_client, mcp_token, 'export_procurement_opportunities', {
        'filters': {'departments': ['Antioquia']},
    })
    workbook = load_workbook(BytesIO(base64.b64decode(content(response)['base64'])), read_only=True)
    rows = list(workbook.active.iter_rows(values_only=True))

    assert content(response)['filename'] == 'oportunidades-secop.xlsx'
    assert len(rows) == 2
    assert rows[1][0] == selected.reference


@pytest.mark.parametrize('owner_kind', ['inactive', 'nonstaff'])
def test_mcp_rejects_ineligible_personal_owner(api_client, mcp_token, staff_user, owner_kind):
    """Falla si el asistente atribuye búsquedas a usuarios inactivos o sin acceso administrativo."""
    staff_user.is_active = owner_kind != 'inactive'
    staff_user.is_staff = owner_kind != 'nonstaff'
    staff_user.save(update_fields=['is_active', 'is_staff'])

    response = call_tool(api_client, mcp_token, 'create_procurement_search', {
        'owner_id': staff_user.pk, 'name': 'Inválida', 'filters': {},
    })

    assert result(response)['isError'] is True
    assert SavedSearch.objects.count() == 0
    assert 'Datos inválidos o registro no disponible.' in result(response)['content'][0]['text']


def test_mcp_restores_discarded_analysis_with_auditable_reason(api_client, mcp_token, opportunity, staff_user):
    """Falla si el asistente no puede revertir un descarte conservando su motivo e historial."""
    record = opportunity('MCP-RESTORE')
    saved = Classification.objects.create(opportunity=record, owner=staff_user, state='discarded',
                                          previous_state='reviewing', notes='Motivo conservado')

    response = call_tool(api_client, mcp_token, 'restore_procurement_classification', {
        'id': record.pk, 'owner_id': staff_user.pk,
    })

    saved.refresh_from_db()
    assert content(response)['state'] == 'reviewing'
    assert saved.notes == 'Motivo conservado'
    assert Activity.objects.get(classification=saved).snapshot == {
        'state': 'reviewing', 'notes': 'Motivo conservado', 'owner_id': staff_user.pk,
    }
