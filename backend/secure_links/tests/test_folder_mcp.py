"""End-to-end JSON-RPC coverage of the filing tools."""
import json
import pytest
from secure_links import folder_services as filing
from secure_links.models import SecureLinkFolder
from .test_mcp_tools import call_tool, text, result, mcp_token  # noqa: F401
from .conftest import CREDENTIALS

pytestmark = pytest.mark.django_db


def test_connector_discovers_hierarchy_tools(api_client, mcp_token):
    from .test_mcp_tools import list_tools
    names = {tool['name'] for tool in result(list_tools(api_client, mcp_token))['tools']}
    assert {'list_secure_link_folders', 'get_secure_link_folder', 'create_secure_link_folder',
            'update_secure_link_folder', 'move_secure_link_folder', 'reorder_secure_link_folders',
            'archive_secure_link_folder', 'restore_secure_link_folder', 'delete_secure_link_folder',
            'move_secure_link'} <= names


def test_mcp_creates_nested_folder(api_client, mcp_token):
    root = filing.save_folder(data={'name': 'Accesos'})
    response = call_tool(api_client, mcp_token, 'create_secure_link_folder', {'name': 'Servidores', 'parent': root.pk})
    data = json.loads(text(response))
    assert SecureLinkFolder.objects.get(pk=data['id']).parent_id == root.pk


def test_mcp_creates_link_in_folder(api_client, mcp_token, project):
    response = call_tool(api_client, mcp_token, 'create_secure_link', {
        'title': 'Admin', 'secret_type': 'credentials', 'fields': CREDENTIALS,
        'folder_id': project.secure_link_root_folder.pk,
    })
    data = json.loads(text(response))
    assert data['folder_id'] == project.secure_link_root_folder.pk
    assert data['project_id'] == project.pk


def test_mcp_moves_link_without_changing_project(api_client, mcp_token, project, make_link):
    folder = filing.save_folder(data={'name': 'Propia'})
    link, url = make_link(project=project)
    response = call_tool(api_client, mcp_token, 'move_secure_link', {'link_id': link.pk, 'folder_id': folder.pk})
    data = json.loads(text(response))
    assert (data['project_id'], data['folder_id']) == (project.pk, folder.pk)
    assert url not in text(response)
    assert CREDENTIALS['password'] not in text(response)


def test_mcp_search_counts_match_rest(api_client, staff_client, mcp_token, make_link):
    folder = filing.save_folder(data={'name': 'Accesos'})
    make_link(folder=folder, title='Servidor uno')
    make_link(title='Servidor externo')
    response = call_tool(api_client, mcp_token, 'list_secure_links', {'folder_id': folder.pk, 'search': 'Servidor'})
    rest = staff_client.get('/api/secure-links/', {'folder': folder.pk, 'search': 'Servidor'})
    data = json.loads(text(response))
    assert data['count'] == rest.data['count'] == 1
    assert data['lifecycle_counts'] == rest.data['lifecycle_counts']


def test_mcp_rejects_cyclic_move(api_client, mcp_token):
    root = filing.save_folder(data={'name': 'Raíz'})
    child = filing.save_folder(data={'name': 'Subcarpeta', 'parent': root})
    response = call_tool(api_client, mcp_token, 'move_secure_link_folder', {'folder_id': root.pk, 'parent': child.pk})
    assert result(response)['isError'] is True
    root.refresh_from_db()
    assert root.parent_id is None


def test_mcp_archives_live_link_without_revoking(api_client, mcp_token, make_link):
    folder = filing.save_folder(data={'name': 'Archivo'})
    link, _ = make_link(folder=folder)
    response = call_tool(api_client, mcp_token, 'archive_secure_link_folder', {'folder_id': folder.pk})
    link.refresh_from_db()
    assert json.loads(text(response))['links'] == 1
    assert link.is_archived is True
    assert link.status == 'active'


def test_mcp_restores_archived_subtree(api_client, mcp_token, make_link):
    folder = filing.save_folder(data={'name': 'Archivo'})
    link, _ = make_link(folder=folder)
    filing.archive_folder(folder)
    response = call_tool(api_client, mcp_token, 'restore_secure_link_folder', {'folder_id': folder.pk})
    link.refresh_from_db()
    assert json.loads(text(response))['links'] == 1
    assert link.is_archived is False


def test_mcp_folder_deletion_requires_confirmation(api_client, mcp_token):
    folder = filing.save_folder(data={'name': 'Vacía'})
    preview = call_tool(api_client, mcp_token, 'delete_secure_link_folder', {'folder_id': folder.pk})
    confirmation_id = result(preview)['structuredContent']['confirmation_id']
    assert SecureLinkFolder.objects.filter(pk=folder.pk).exists()
    call_tool(api_client, mcp_token, 'confirm_action', {'confirmation_id': confirmation_id})
    assert not SecureLinkFolder.objects.filter(pk=folder.pk).exists()


def test_mcp_rejects_stale_delete_confirmation(api_client, mcp_token):
    folder = filing.save_folder(data={'name': 'Antes'})
    preview = call_tool(api_client, mcp_token, 'delete_secure_link_folder', {'folder_id': folder.pk})
    confirmation_id = result(preview)['structuredContent']['confirmation_id']
    filing.save_folder(folder=folder, data={'name': 'Después'})
    response = call_tool(api_client, mcp_token, 'confirm_action', {'confirmation_id': confirmation_id})
    assert result(response)['isError'] is True
    assert SecureLinkFolder.objects.filter(pk=folder.pk, name='Después').exists()


def test_mcp_rejects_stale_folder_archive_without_archiving_content(api_client, mcp_token, make_link):
    """Falla si el MCP archiva una carpeta que cambió después de que el asistente la leyó."""
    folder = filing.save_folder(data={'name': 'Pendiente'})
    link, _ = make_link(folder=folder)
    old_revision = folder.updated_at.isoformat()
    filing.save_folder(folder=folder, data={'name': 'Revisada'})

    response = call_tool(
        api_client,
        mcp_token,
        'archive_secure_link_folder',
        {'folder_id': folder.pk, 'expected_updated_at': old_revision},
    )

    folder.refresh_from_db()
    link.refresh_from_db()
    assert result(response)['isError'] is True
    assert folder.is_archived is False
    assert link.is_archived is False


def test_mcp_accepts_current_folder_revision_from_its_listing(api_client, mcp_token):
    folder = filing.save_folder(data={'name': 'Archivo'})
    listed = call_tool(api_client, mcp_token, 'get_secure_link_folder', {'folder_id': folder.pk})
    revision = json.loads(text(listed))['updated_at']

    response = call_tool(api_client, mcp_token, 'archive_secure_link_folder', {
        'folder_id': folder.pk, 'expected_updated_at': revision,
    })

    assert result(response).get('isError', False) is False
    folder.refresh_from_db()
    assert folder.is_archived is True
