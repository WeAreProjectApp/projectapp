"""MCP contracts for human-managed requirement packages."""

from uuid import uuid4

import pytest
from accounts.models import Project, UserProfile
from accounts.models_requirement_packages import (
    PackageExampleRevision,
    PackageMovement,
    PackageRequest,
)

from content.mcp.principal import service_actor_for_connector
from content.models import McpConnector
from content.tests.mcp_confirmation_helpers import call_confirmed, confirmed_payload

pytestmark = pytest.mark.django_db


def tools_by_name(response):
    """Index MCP public tool declarations by their stable tool name."""
    return {row['name']: row for row in response.data['result']['tools']}


def capabilities_by_name(response):
    """Index detailed MCP capability metadata by tool name."""
    return {
        row['name']: row
        for row in response.data['result']['structuredContent']['tools']
    }


def projects_url(token):
    """Build the Projects MCP endpoint for one scoped capability token."""
    return f'/api/mcp/projects/{token}/'


def rpc(method, params=None, message_id=1):
    """Build one JSON-RPC request accepted by the Projects MCP endpoint."""
    payload = {'jsonrpc': '2.0', 'id': message_id, 'method': method}
    if params is not None:
        payload['params'] = params
    return payload


def call_project_tool(api_client, token, name, arguments):
    """Invoke one Projects MCP tool through its real connector boundary."""
    return api_client.post(
        projects_url(token),
        rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )


def publish_and_read_project_examples(api_client, token, arguments):
    """Confirm one examples revision and return its preview, result and public read."""
    preview = call_project_tool(
        api_client,
        token,
        'publish_project_package_examples',
        arguments,
    )
    confirmed = call_project_tool(
        api_client,
        token,
        'confirm_action',
        {'confirmation_id': preview.data['result']['structuredContent']['confirmation_id']},
    )
    read = call_project_tool(
        api_client,
        token,
        'get_project_package_examples',
        {'project_id': arguments['project_id'], 'language': arguments['language']},
    )
    return preview, confirmed, read


@pytest.fixture
def projects_token():
    """Create an active Projects credential bound to its real service actor."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='projects', defaults={'name': 'Projects'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    credential = connector.credential_for_token(token)
    credential.actor = service_actor_for_connector(connector)
    credential.save(update_fields=['actor', 'updated_at'])
    return token


@pytest.fixture
def package_project(django_user_model):
    """Create one client-owned project for Projects MCP package operations."""
    client = django_user_model.objects.create_user(
        username='mcp-package-client',
        email='mcp-package-client@example.test',
    )
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT)
    return Project.objects.create(name='MCP requirement packages', client=client)


def test_projects_catalog_exposes_human_package_administration_without_client_consent(
    api_client,
    projects_token,
):
    """Fails if the administrative MCP can impersonate a client's allowance consent."""
    response = api_client.post(
        projects_url(projects_token),
        rpc('tools/list'),
        format='json',
    )
    capabilities = call_project_tool(
        api_client,
        projects_token,
        'describe_capabilities',
        {},
    )

    tools = tools_by_name(response)
    capability_tools = capabilities_by_name(capabilities)
    assert response.status_code == 200
    assert {
        'get_project_requirement_packages',
        'get_project_package_examples',
        'confirm_external_package_payment',
        'begin_package_request_evaluation',
        'publish_package_size_proposal',
    } <= tools.keys()
    assert capability_tools['publish_package_size_proposal']['requires_confirmation'] is True
    assert 'decide_package_request' not in tools


def test_mcp_confirmed_project_examples_publish_creates_readable_revision(
    api_client,
    package_project,
    projects_token,
):
    """Fails if a confirmed MCP examples publish is absent from the next read."""
    arguments = {
        'project_id': package_project.pk,
        'request_id': str(uuid4()),
        'expected_revision': 0,
        'examples': {'XS': ['Cambiar el texto de una alerta existente.']},
        'note': 'Ejemplo propio del proyecto',
        'language': 'es',
    }

    preview, confirmed, read = publish_and_read_project_examples(
        api_client,
        projects_token,
        arguments,
    )

    revision = PackageExampleRevision.objects.get(project=package_project)
    credential = McpConnector.objects.get(slug='projects').credentials.get(label='Default')
    catalog = confirmed_payload(read)
    assert (
        preview.data['result']['isError'],
        'confirmation_id' in preview.data['result']['structuredContent'],
    ) == (False, True)
    assert (
        confirmed.data['result']['isError'],
        PackageExampleRevision.objects.filter(project=package_project).count(),
    ) == (False, 1)
    assert revision.author_id == credential.actor_id
    assert catalog['project_revision'] == revision.pk
    assert catalog['custom_examples'] == {
        'XS': ['Cambiar el texto de una alerta existente.'],
    }
    assert catalog['sizes'][0] == {
        'size': 'XS',
        'definition': 'Ajuste acotado de una capacidad que ya existe.',
        'examples': ['Cambiar el texto de una alerta existente.'],
        'source': 'project',
    }


def test_mcp_project_examples_reject_stale_revision_without_history_change(
    api_client,
    package_project,
    projects_token,
):
    """Fails if a stale MCP examples confirmation replaces the current revision."""
    first_arguments = {
        'project_id': package_project.pk,
        'request_id': str(uuid4()),
        'expected_revision': 0,
        'examples': {'S': ['Agregar una ventana sencilla al flujo actual.']},
        'note': 'Primera versión MCP',
        'language': 'es',
    }
    stale_arguments = {
        'project_id': package_project.pk,
        'request_id': str(uuid4()),
        'expected_revision': 0,
        'examples': {'S': ['Sobrescribir desde una revisión antigua.']},
        'note': 'Versión obsoleta MCP',
        'language': 'es',
    }

    first = call_confirmed(
        api_client,
        projects_url(projects_token),
        rpc,
        'publish_project_package_examples',
        first_arguments,
    )
    stale = call_confirmed(
        api_client,
        projects_url(projects_token),
        rpc,
        'publish_project_package_examples',
        stale_arguments,
    )

    revision = PackageExampleRevision.objects.get(project=package_project)
    assert first.data['result']['isError'] is False
    assert stale.data['result']['isError'] is True
    assert stale.data['result']['structuredContent']['error']['code'] == 'CONFLICT'
    assert PackageExampleRevision.objects.filter(project=package_project).count() == 1
    assert revision.examples == {
        'S': ['Agregar una ventana sencilla al flujo actual.'],
    }


def test_mcp_created_package_request_has_detail_without_debit(
    api_client,
    package_project,
    projects_token,
):
    """Fails if creating a request through MCP consumes an allowance before consent."""
    created = call_project_tool(
        api_client,
        projects_token,
        'create_package_request',
        {
            'project_id': package_project.pk,
            'request_id': str(uuid4()),
            'title': 'Agregar estado al tablero',
            'description': 'Mostrar el estado del requerimiento en la vista existente.',
        },
    )
    created_payload = confirmed_payload(created)
    detail = call_project_tool(
        api_client,
        projects_token,
        'get_package_request',
        {
            'project_id': package_project.pk,
            'package_request_id': created_payload['id'],
        },
    )

    request_row = PackageRequest.objects.get(pk=created_payload['id'])
    detail_payload = confirmed_payload(detail)
    assert created.data['result']['isError'] is False
    assert request_row.status == 'pending'
    assert detail_payload['description'] == (
        'Mostrar el estado del requerimiento en la vista existente.'
    )
    assert PackageMovement.objects.filter(
        order__project=package_project,
        kind='debit',
    ).count() == 0
