"""MCP schema, confirmation, ownership, and audit-trail behavior coverage."""

import json

import pytest
from content.models import McpConnector, McpCredential
from procurement.models import Activity, Classification, SavedSearch, Settings

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
