"""Secure-link tools on the communications MCP connector."""

import json

import pytest
from content.models import McpActionIntent, McpConnector, McpRequestLog

from secure_links.models import SecureLink

from .conftest import CREDENTIALS, token_from

pytestmark = pytest.mark.django_db


@pytest.fixture
def mcp_token():
    """Return an active communications connector token."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='communications', defaults={'name': 'Gestor de Comunicaciones'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def call_tool(api_client, token, name, arguments):
    """Call one communications MCP tool through JSON-RPC."""
    return api_client.post(
        f'/api/mcp/communications/{token}/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}},
        format='json',
    )


def result(response):
    """Return the JSON-RPC result payload."""
    return response.data['result']


def text(response):
    """Return the MCP text representation of a tool response."""
    return result(response)['content'][0]['text']


def list_tools(api_client, token):
    """Discover tools visible to a communications credential."""
    return api_client.post(
        f'/api/mcp/communications/{token}/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
        format='json',
    )


def error_code(response):
    """Return a structured tool error code."""
    return result(response)['structuredContent']['error']['code']


def grant_secret_read(connector):
    """Enable only the explicit secure-link read permission."""
    credential = connector.credentials.get(label='Default')
    credential.allowed_tools = ['reveal_secure_link_content']
    credential.save(update_fields=['allowed_tools'])
    return credential


def test_create_returns_url_once_and_reads_never_expose_it(api_client, mcp_token, client_profile, project):
    """Falla si el MCP puede recuperar la URL o el contenido después de crear."""
    created = call_tool(api_client, mcp_token, 'create_secure_link', {
        'secret_type': 'credentials', 'title': 'Admin portal', 'fields': CREDENTIALS,
        'client_id': client_profile.pk, 'project_id': project.pk,
    })
    data = json.loads(text(created))
    listed = call_tool(api_client, mcp_token, 'list_secure_links', {'client_id': client_profile.pk})
    detail = call_tool(api_client, mcp_token, 'get_secure_link', {'link_id': data['id']})

    token = token_from(data['url'])
    link = SecureLink.objects.get(pk=data['id'])
    assert link.origin == SecureLink.Origin.MCP
    assert link.project == project
    assert token not in text(listed)
    assert CREDENTIALS['password'] not in text(listed)
    assert token not in text(detail)
    assert CREDENTIALS['password'] not in text(detail)
    assert json.loads(text(listed))['count'] == 1


def test_create_requires_content(api_client, mcp_token):
    """Falla si el asistente puede crear un enlace sin el secreto."""
    response = call_tool(api_client, mcp_token, 'create_secure_link', {
        'secret_type': 'credentials', 'title': 'Sin contenido', 'fields': {},
    })

    assert result(response)['isError'] is True
    assert 'pídeselo al operador' in text(response)
    assert not SecureLink.objects.exists()


def test_secret_values_are_not_copied_to_request_logs(api_client, mcp_token):
    """Falla si la contraseña queda registrada en la bitácora del conector."""
    call_tool(api_client, mcp_token, 'create_secure_link', {
        'secret_type': 'credentials', 'title': 'Log check', 'fields': CREDENTIALS,
    })

    assert CREDENTIALS['password'] not in str(list(McpRequestLog.objects.values()))
    assert not McpActionIntent.objects.exists()


def test_reactivation_requires_confirmation_and_hides_url(api_client, mcp_token, make_link):
    """Falla si el asistente reactiva sin confirmación o si la URL queda persistida."""
    from secure_links import services

    link, url = make_link()
    services.reveal(token_from(url))

    preview = call_tool(api_client, mcp_token, 'reactivate_secure_link', {'link_id': link.pk})
    confirmation_id = result(preview)['structuredContent']['confirmation_id']
    link.refresh_from_db()
    assert link.status == 'consumed'

    confirmed = call_tool(api_client, mcp_token, 'confirm_action', {'confirmation_id': confirmation_id})

    link.refresh_from_db()
    assert link.status == 'active'
    assert token_from(url) not in text(confirmed)
    assert token_from(url) not in str(list(McpActionIntent.objects.values()))


def test_revoke_tool_blocks_link(api_client, mcp_token, make_link):
    """Falla si revocar desde el asistente deja el enlace abrible."""
    link, _url = make_link()

    response = call_tool(api_client, mcp_token, 'revoke_secure_link', {'link_id': link.pk})

    assert json.loads(text(response))['status'] == 'revoked'


def test_mcp_marks_manual_sharing_without_revealing_secrets(api_client, mcp_token, make_link):
    """La marca de envío conserva la privacidad del enlace disponible."""
    link, url = make_link()

    response = call_tool(api_client, mcp_token, 'mark_secure_link_sent', {'link_id': link.pk})

    data = json.loads(text(response))
    assert data['lifecycle_status'] == 'sent'
    assert data['status'] == 'active'
    assert data['sent_at'] is not None
    assert url not in text(response)
    assert CREDENTIALS['password'] not in text(response)


def test_mcp_filters_manually_sent_links(api_client, mcp_token, make_link, staff_user):
    """El filtro nuevo distingue enviados sin cambiar los estados anteriores."""
    from secure_links import services

    make_link(title='Not shared')
    link, _ = make_link(title='Shared')
    services.mark_sent(link, actor=staff_user)

    response = call_tool(api_client, mcp_token, 'list_secure_links', {'lifecycle_status': 'sent'})

    data = json.loads(text(response))
    assert [row['id'] for row in data['results']] == [link.pk]
    assert data['count'] == 1


def test_mcp_lists_only_consumed_links_for_the_selected_project(api_client, mcp_token, make_link, project, staff_user):
    """Falla si el filtro MCP mezcla enlaces consumidos de proyectos distintos o revela secretos."""
    from accounts.models import Project
    from secure_links import services

    selected, selected_url = make_link(project=project)
    other_project = Project.objects.create(name='Proyecto de enlace ajeno', client=project.client)
    other, other_url = make_link(project=other_project)
    services.reveal(token_from(selected_url))
    services.reveal(token_from(other_url))

    response = call_tool(api_client, mcp_token, 'list_secure_links', {
        'project_id': project.pk, 'status': 'consumed',
    })

    data = json.loads(text(response))
    assert (data['count'], [row['id'] for row in data['results']]) == (1, [selected.pk])
    assert token_from(selected_url) not in text(response)
    assert token_from(other_url) not in text(response)


def test_mcp_platform_reactivation_rejects_thirty_days(api_client, mcp_token, make_link, project, staff_user):
    """Falla si MCP permite una vigencia de treinta días para un enlace Platform."""
    from secure_links import services

    link, url = make_link(project=project, origin=SecureLink.Origin.PLATFORM)
    services.reveal(token_from(url), staff=True, actor=staff_user)
    link.refresh_from_db()
    before = (link.token_hash, link.expires_at, link.activation_count, link.events.count())

    response = call_tool(api_client, mcp_token, 'reactivate_secure_link', {
        'link_id': link.pk, 'validity_days': 30,
    })

    link.refresh_from_db()
    assert error_code(response) == 'invalid_validity'
    assert (link.token_hash, link.expires_at, link.activation_count, link.events.count()) == before
    assert url not in text(response)


def test_mcp_rejects_marking_received_links(api_client, mcp_token, make_link):
    """El MCP no permite marcar como enviado un enlace recibido del cliente."""
    link, _ = make_link(origin=SecureLink.Origin.PUBLIC)

    response = call_tool(api_client, mcp_token, 'mark_secure_link_sent', {'link_id': link.pk})

    assert result(response)['isError'] is True
    assert error_code(response) == 'invalid_send_state'
    link.refresh_from_db()
    assert link.sent_at is None
    assert not link.events.filter(kind='marked_sent').exists()


def test_custom_type_is_discoverable(api_client, mcp_token):
    """El asistente descubre los campos de Personalizado desde el catálogo."""
    response = call_tool(api_client, mcp_token, 'list_secure_link_types', {})

    types = {entry['key']: entry for entry in json.loads(text(response))['types']}
    assert types['custom']['label_es'] == 'Personalizado'
    assert [field['key'] for field in types['custom']['fields']] == ['custom_name', 'content']


def test_mcp_custom_creation_keeps_content_private(api_client, mcp_token):
    """El contenido personalizado no aparece en lecturas ni logs de MCP."""
    from secure_links import services

    fields = {'custom_name': 'Private instructions', 'content': '  secret details  '}
    created = call_tool(api_client, mcp_token, 'create_secure_link', {
        'secret_type': 'custom', 'title': 'Reference', 'fields': fields,
    })
    data = json.loads(text(created))

    detail = call_tool(api_client, mcp_token, 'get_secure_link', {'link_id': data['id']})

    assert data['type_label'] == 'Personalizado'
    assert fields['custom_name'] not in text(detail)
    assert fields['content'] not in str(list(McpRequestLog.objects.values()))
    link = SecureLink.objects.get(pk=data['id'])
    assert services.content_for(link)['fields'][1]['value'] == fields['content']


def test_mcp_custom_creation_rejects_missing_name(api_client, mcp_token):
    """Un personalizado sin nombre no se guarda desde el asistente."""
    response = call_tool(api_client, mcp_token, 'create_secure_link', {
        'secret_type': 'custom', 'title': 'Reference', 'fields': {'content': 'secret'},
    })

    assert result(response)['isError'] is True
    assert 'custom_name' in text(response)
    assert not SecureLink.objects.exists()


def test_secret_read_requires_explicit_credential_grant(api_client, mcp_token, make_link):
    """Falla si una credencial general descubre o inicia una lectura de secreto."""
    link, _url = make_link()

    hidden = list_tools(api_client, mcp_token)
    forbidden = call_tool(
        api_client, mcp_token, 'reveal_secure_link_content', {'link_id': link.pk},
    )
    connector = McpConnector.objects.get(slug='communications')
    grant_secret_read(connector)
    visible = list_tools(api_client, mcp_token)
    preview = call_tool(
        api_client, mcp_token, 'reveal_secure_link_content', {'link_id': link.pk},
    )

    hidden_names = {tool['name'] for tool in result(hidden)['tools']}
    visible_names = {tool['name'] for tool in result(visible)['tools']}
    assert 'reveal_secure_link_content' not in hidden_names
    assert error_code(forbidden) == 'FORBIDDEN'
    assert 'reveal_secure_link_content' in visible_names
    assert result(preview)['structuredContent']['confirmation_id']
    assert CREDENTIALS['password'] not in text(preview)


def test_mcp_update_preserves_the_public_url_without_returning_content(api_client, mcp_token, make_link):
    """Falla si editar por MCP cambia la URL, consume el enlace o devuelve el secreto."""
    from secure_links import services

    link, url = make_link()
    replacement = {**CREDENTIALS, 'password': 'Mcp-updated-password'}

    response = call_tool(api_client, mcp_token, 'update_secure_link', {
        'link_id': link.pk, 'fields': replacement,
    })

    link.refresh_from_db()
    assert link.status == 'active'
    assert services.link_url(link) == url
    assert {field['key']: field['value'] for field in services.content_for(link)['fields']}['password'] == replacement['password']
    assert replacement['password'] not in text(response)
    assert url not in text(response)
    assert replacement['password'] not in str(list(McpRequestLog.objects.values()))


def test_mcp_update_clears_associations_without_changing_content_or_token(
    api_client, mcp_token, make_link, client_profile, project,
):
    """Falla si limpiar asociaciones por MCP altera el secreto o la URL existente."""
    from secure_links import services

    link, url = make_link(client=client_profile, project=project)
    original_content = services.content_for(link)

    response = call_tool(api_client, mcp_token, 'update_secure_link', {
        'link_id': link.pk, 'client_id': None, 'project_id': None,
    })

    link.refresh_from_db()
    assert link.client_id is None
    assert link.project_id is None
    assert services.content_for(link) == original_content
    assert services.link_url(link) == url
    assert CREDENTIALS['password'] not in text(response)
    assert url not in text(response)
    assert CREDENTIALS['password'] not in str(list(McpRequestLog.objects.values()))


def test_mcp_delete_requires_confirmation_before_removing_the_link(api_client, mcp_token, make_link):
    """Falla si eliminar por MCP borra el enlace antes de confirmar la acción."""
    link, _url = make_link()

    preview = call_tool(api_client, mcp_token, 'delete_secure_link', {'link_id': link.pk})
    confirmation_id = result(preview)['structuredContent']['confirmation_id']
    pending = SecureLink.objects.filter(pk=link.pk).exists()
    confirmed = call_tool(
        api_client, mcp_token, 'confirm_action', {'confirmation_id': confirmation_id},
    )

    assert pending is True
    assert json.loads(text(confirmed))['result'] == {'id': link.pk, 'deleted': True}
    assert SecureLink.objects.filter(pk=link.pk).exists() is False


def test_invalid_delete_preview_does_not_create_an_intent(api_client, mcp_token):
    """Falla si una vista previa inválida queda persistida como acción confirmable."""
    response = call_tool(api_client, mcp_token, 'delete_secure_link', {'link_id': 'no-id'})

    assert error_code(response) == 'VALIDATION_ERROR'
    assert McpActionIntent.objects.exists() is False


def test_confirmation_rejects_a_link_modified_after_delete_preview(api_client, mcp_token, make_link, staff_user):
    """Falla si una confirmación antigua elimina un enlace modificado después de la vista previa."""
    from secure_links import services

    link, _url = make_link()
    preview = call_tool(api_client, mcp_token, 'delete_secure_link', {'link_id': link.pk})
    services.update_link(link, actor=staff_user, title='Título actualizado')

    confirmed = call_tool(
        api_client, mcp_token, 'confirm_action',
        {'confirmation_id': result(preview)['structuredContent']['confirmation_id']},
    )

    link.refresh_from_db()
    assert error_code(confirmed) == 'STALE_VERSION'
    assert link.title == 'Título actualizado'


def test_confirmation_rejects_a_link_removed_after_preview(api_client, mcp_token, make_link):
    """Falla si una confirmación de eliminación afecta otro enlace tras borrar su objetivo."""
    from secure_links import services

    link, _url = make_link(title='Original target')
    other, _other_url = make_link(title='Other target')
    preview = call_tool(api_client, mcp_token, 'delete_secure_link', {'link_id': link.pk})
    services.delete_link(link)

    confirmed = call_tool(
        api_client, mcp_token, 'confirm_action',
        {'confirmation_id': result(preview)['structuredContent']['confirmation_id']},
    )

    assert error_code(confirmed) == 'NOT_FOUND'
    assert SecureLink.objects.filter(pk=other.pk).exists() is True


def test_mcp_update_requires_content_when_changing_type(api_client, mcp_token, make_link):
    """Falla si cambiar el tipo por MCP conserva contenido con un esquema distinto."""
    link, _url = make_link()

    response = call_tool(api_client, mcp_token, 'update_secure_link', {
        'link_id': link.pk, 'secret_type': 'custom',
    })

    link.refresh_from_db()
    assert error_code(response) == 'VALIDATION_ERROR'
    assert link.secret_type == 'credentials'


def test_mcp_update_rejects_a_blank_title(api_client, mcp_token, make_link):
    """Falla si una actualización MCP guarda un título vacío."""
    link, _url = make_link()

    response = call_tool(
        api_client, mcp_token, 'update_secure_link', {'link_id': link.pk, 'title': ' '},
    )

    link.refresh_from_db()
    assert error_code(response) == 'VALIDATION_ERROR'
    assert link.title == 'Admin producción'


def test_mcp_update_rejects_a_project_from_another_client(
    api_client, mcp_token, make_link, client_profile, project,
):
    """Falla si una actualización MCP mezcla cliente y proyecto de distinto dueño."""
    from accounts.models import UserProfile
    from django.contrib.auth import get_user_model

    other_user = get_user_model().objects.create_user(username='mcp-other-client')
    other, _ = UserProfile.objects.get_or_create(
        user=other_user, defaults={'role': UserProfile.ROLE_CLIENT},
    )
    link, _url = make_link(client=client_profile, project=project)

    response = call_tool(api_client, mcp_token, 'update_secure_link', {
        'link_id': link.pk, 'client_id': other.pk, 'project_id': project.pk,
    })

    link.refresh_from_db()
    assert error_code(response) == 'project_client_mismatch'
    assert link.client_id == client_profile.pk
