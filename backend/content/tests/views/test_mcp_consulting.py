"""Commercial MCP Consultation presentation preview, confirmation and restoration."""
import pytest

from content.models import ConsultingProgramRevision, McpActionIntent
from content.services import consulting_program_service as service
from content.tests.consulting_fixtures import (
    changed_consulting_program, consulting_mcp, consulting_program, hero_update, rpc_call,
)

pytestmark = pytest.mark.django_db


def test_commercial_catalog_exposes_consulting_writes_as_confirmed_actions(api_client, consulting_mcp):
    """Fails if Commercial hides Consulting controls or lets its public presentation mutate without confirmation."""
    token, _ = consulting_mcp
    catalog = rpc_call(api_client, token, 'describe_capabilities', {})['structuredContent']
    tools = {tool['name']: tool for tool in catalog['tools']}

    assert {'get_consulting_program', 'preview_consulting_program_update',
            'update_consulting_program', 'list_consulting_program_versions',
            'restore_consulting_program_version', 'render_consulting_program_pdf'} <= set(tools)
    assert tools['update_consulting_program']['requires_confirmation'] is True
    assert tools['restore_consulting_program_version']['requires_confirmation'] is True
    assert tools['render_consulting_program_pdf']['risk'] == 'read'


def test_confirmed_mcp_update_creates_history_after_a_nonmutating_preview(api_client, consulting_program, consulting_mcp, django_capture_on_commit_callbacks):
    """Fails if MCP preview writes early or confirmed publication does not expose the new public version."""
    token, credential = consulting_mcp
    before = service.read_program()
    arguments = hero_update(before)
    preview = rpc_call(api_client, token, 'preview_consulting_program_update', {'sections': arguments['sections']})['structuredContent']
    intent = rpc_call(api_client, token, 'update_consulting_program', arguments)['structuredContent']

    assert preview['changed'] is True
    assert service.read_program()['version'] == 1

    with django_capture_on_commit_callbacks(execute=True):
        confirmed = rpc_call(api_client, token, 'confirm_action', {'confirmation_id': intent['confirmation_id']}, msg_id=2)
    public = api_client.get('/api/consulting/public/').data

    assert confirmed['structuredContent']['result']['version'] == 2
    assert public['hero']['title'] == arguments['sections']['hero']['es']['title']
    assert public['version'] == 2
    assert ConsultingProgramRevision.objects.get(version=2).credential_id == credential.pk


def test_confirming_an_outdated_mcp_intent_preserves_newer_content(api_client, consulting_program, consulting_mcp, admin_user):
    """Fails if a confirmed stale intent overwrites a version published after its preview."""
    token, _ = consulting_mcp
    before = service.read_program()
    arguments = hero_update(before)
    intent = rpc_call(api_client, token, 'update_consulting_program', arguments)['structuredContent']
    service.apply_update(arguments, actor=admin_user)

    result = rpc_call(api_client, token, 'confirm_action', {'confirmation_id': intent['confirmation_id']}, msg_id=2)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert ConsultingProgramRevision.objects.count() == 2


def test_mcp_rejects_an_update_without_an_audit_note(api_client, consulting_program, consulting_mcp):
    """Fails if an untraceable publication reaches the durable confirmation queue."""
    token, credential = consulting_mcp
    arguments = hero_update(service.read_program())
    arguments.pop('change_note')

    result = rpc_call(api_client, token, 'update_consulting_program', arguments)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert McpActionIntent.objects.filter(credential=credential).count() == 0
    assert ConsultingProgramRevision.objects.count() == 1


def test_confirmed_mcp_restore_creates_a_version_linked_to_the_selected_source(api_client, changed_consulting_program, consulting_mcp):
    """Fails if MCP restoration overwrites history or does not reinstate the requested baseline."""
    token, _ = consulting_mcp
    current = service.read_program()
    intent = rpc_call(api_client, token, 'restore_consulting_program_version', {
        'version_id': changed_consulting_program['version_id'], 'if_match': current['etag'],
        'change_note': 'Restaurar la presentación inicial.',
    })['structuredContent']

    result = rpc_call(api_client, token, 'confirm_action', {'confirmation_id': intent['confirmation_id']}, msg_id=2)
    restored = ConsultingProgramRevision.objects.get(pk=result['structuredContent']['result']['version_id'])

    assert restored.version == 3
    assert restored.restored_from_id == changed_consulting_program['version_id']
    assert restored.content == changed_consulting_program['content']
    assert service.read_program()['content'] == changed_consulting_program['content']
