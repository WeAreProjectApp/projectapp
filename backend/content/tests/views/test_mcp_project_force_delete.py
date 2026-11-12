"""PA-248: a broad MCP credential never grants forced project deletion."""
import pytest

from accounts.models import BillingContextEvent, Project
from content.models import McpConnector
from content.tests.views.test_mcp_parity_refresh import call_tool, payload
from content.tests.views.test_panel_project_deletion import unused_project as unused_project

pytestmark = pytest.mark.django_db


@pytest.fixture
def force_token():
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    credential = connector.credentials.get(label='Default')
    credential.allowed_tools = ['preview_project_force_delete', 'force_delete_project']
    credential.save(update_fields=['allowed_tools'])
    return token


def test_general_credential_cannot_preview_forced_deletion(api_client, force_token, unused_project):
    """Falla si el permiso general hereda la nueva operación destructiva."""
    credential = McpConnector.objects.get(slug='projects').credentials.get(label='Default')
    credential.allowed_tools = []
    credential.save(update_fields=['allowed_tools'])

    response = call_tool(api_client, 'projects', force_token, 'preview_project_force_delete', {
        'project_id': unused_project.pk, 'delete_keys': [],
    })

    assert response.data['result']['isError'] is True
    assert Project.objects.filter(pk=unused_project.pk).exists()


def test_confirmed_forced_deletion_preserves_billing_history(api_client, force_token, unused_project, superuser):
    """Falla si la nueva herramienta borra evidencia o ejecuta antes de confirmar."""
    project_id = unused_project.pk
    event = BillingContextEvent.objects.create(project=unused_project, actor=superuser,
        operation='assign_billing_context', reason='Preservar decisión', before={'value': 1}, after={'value': 2})
    preview = payload(call_tool(api_client, 'projects', force_token, 'preview_project_force_delete', {
        'project_id': project_id, 'delete_keys': [],
    }))
    pending = payload(call_tool(api_client, 'projects', force_token, 'force_delete_project', {
        'project_id': project_id, 'delete_keys': [], 'confirmation': 'DELETE',
        'impact_token': preview['impact_token'],
    }))
    assert pending['confirmation_required'] is True
    assert Project.objects.filter(pk=project_id).exists()

    response = call_tool(api_client, 'projects', force_token, 'confirm_action', {
        'confirmation_id': pending['confirmation_id'],
    })

    assert payload(response)['result'] == {'deleted': True, 'project_id': project_id}
    event.refresh_from_db()
    assert not Project.objects.filter(pk=project_id).exists()
    assert event.retention_context.original_project_id == project_id
    assert (event.before, event.after) == ({'value': 1}, {'value': 2})


def test_forced_deletion_rejects_nonexact_confirmation(api_client, force_token, unused_project):
    """Falla si MCP acepta espacios que el formulario prohíbe."""
    preview = payload(call_tool(api_client, 'projects', force_token, 'preview_project_force_delete', {
        'project_id': unused_project.pk, 'delete_keys': [],
    }))

    response = call_tool(api_client, 'projects', force_token, 'force_delete_project', {
        'project_id': unused_project.pk, 'delete_keys': [], 'confirmation': 'DELETE ',
        'impact_token': preview['impact_token'],
    })

    assert response.data['result']['isError'] is True
    assert Project.objects.filter(pk=unused_project.pk).exists()
