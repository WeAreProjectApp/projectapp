"""MCP shares the panel dependency checks and confirms permanent deletion."""
import pytest
from accounts.models import Project

from content.models import McpActionIntent, McpConnector
from content.tests.views.test_mcp_parity_refresh import call_tool, payload
from content.tests.views.test_panel_project_deletion import add_income
from content.tests.views.test_panel_project_deletion import (
    unused_project as _unused_project,
)

pytestmark = pytest.mark.django_db
unused_project = _unused_project


@pytest.fixture
def token():
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def test_mcp_preview_returns_dependency_counts(api_client, token, unused_project):
    add_income(unused_project)

    response = call_tool(api_client, 'projects', token, 'preview_project_delete', {'project_id': unused_project.pk})

    assert payload(response)['can_delete'] is False
    assert payload(response)['blockers'] == [{'key': 'incomes', 'label': 'Ingresos', 'count': 1}]


def test_mcp_delete_requires_confirmation(api_client, token, unused_project):
    response = call_tool(api_client, 'projects', token, 'delete_project', {'project_id': unused_project.pk})

    assert payload(response)['confirmation_required'] is True
    assert payload(response)['impact']['can_delete'] is True
    assert Project.objects.filter(pk=unused_project.pk).exists()


def test_mcp_confirm_deletes_the_unused_project(api_client, token, unused_project):
    preview = call_tool(api_client, 'projects', token, 'delete_project', {'project_id': unused_project.pk})

    response = call_tool(api_client, 'projects', token, 'confirm_action', {
        'confirmation_id': payload(preview)['confirmation_id'],
    })

    assert payload(response)['result'] == {'deleted': True, 'project_id': unused_project.pk}
    assert not Project.objects.filter(pk=unused_project.pk).exists()


def test_mcp_confirm_rechecks_dependencies(api_client, token, unused_project):
    preview = call_tool(api_client, 'projects', token, 'delete_project', {'project_id': unused_project.pk})
    income = add_income(unused_project)

    response = call_tool(api_client, 'projects', token, 'confirm_action', {
        'confirmation_id': payload(preview)['confirmation_id'],
    })

    assert response.data['result']['isError'] is True
    result = payload(response)['error']
    assert result['code'] == 'PROJECT_DELETE_BLOCKED'
    assert result['details']['blockers'] == [{'key': 'incomes', 'label': 'Ingresos', 'count': 1}]
    income.refresh_from_db()
    assert income.project_id == unused_project.pk


@pytest.mark.parametrize('arguments', [{'force': 'true'}, {'query': {'force': 'true'}}], ids=['flat', 'query-alias'])
def test_mcp_cannot_request_forced_preview(api_client, token, unused_project, arguments):
    """The connector cannot inherit the panel superuser's destructive preview."""
    response = call_tool(api_client, 'projects', token, 'preview_project_delete', {
        'project_id': unused_project.pk, **arguments,
    })

    error = payload(response)['error']
    assert error['code'] == 'unknown_field'
    assert [item['field'] for item in error['details']['errors']] == ['force']
    assert not McpActionIntent.objects.exists()
    assert Project.objects.filter(pk=unused_project.pk).exists()


@pytest.mark.parametrize(('arguments', 'fields'), [
    ({'force': True}, ['force']),
    ({'delete_keys': ['incomes']}, ['delete_keys']),
    ({'data': {'force': True, 'confirmation': 'DELETE', 'impact_token': 'x' * 64}},
     ['data']),
], ids=['force', 'delete-keys', 'data-alias'])
def test_mcp_forced_delete_is_rejected_before_confirmation(api_client, token, unused_project, arguments, fields):
    """Unknown Panel deletion controls never create a confirmation intent."""
    income = add_income(unused_project)
    response = call_tool(api_client, 'projects', token, 'delete_project', {
        'project_id': unused_project.pk,
        **arguments,
    })

    error = payload(response)['error']
    assert error['code'] == 'unknown_field'
    assert sorted(item['field'] for item in error['details']['errors']) == fields
    assert not McpActionIntent.objects.exists()
    assert Project.objects.filter(pk=unused_project.pk).exists()
    income.refresh_from_db()
    assert income.project_id == unused_project.pk
