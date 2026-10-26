import json

import pytest

from secure_links import folder_services as filing
from secure_links.models import SecureLinkFolder

from .test_mcp_tools import call_tool, error_code, mcp_token, result, text  # noqa: F401


pytestmark = pytest.mark.django_db


def test_mcp_lists_project_root_with_direct_link_count(api_client, mcp_token, project, make_link):
    root = project.secure_link_root_folder
    make_link(project=project)

    response = call_tool(api_client, mcp_token, 'list_secure_link_folders', {})

    data = json.loads(text(response))
    assert data['folders'][0]['id'] == root.pk
    assert data['folders'][0]['managed_project'] == project.pk
    assert data['folders'][0]['link_count'] == 1
    assert data['navigation']['projects'][0]['managed_root_id'] == root.pk


def test_mcp_folder_detail_counts_only_its_subtree(api_client, mcp_token, make_link):
    root = filing.save_folder(data={'name': 'Accesos'})
    child = filing.save_folder(data={'name': 'Servidores', 'parent': root})
    make_link(folder=child)
    make_link()

    response = call_tool(api_client, mcp_token, 'get_secure_link_folder', {'folder_id': root.pk})

    data = json.loads(text(response))
    assert data['descendant_ids'] == [child.pk]
    assert data['lifecycle_counts']['all'] == 1


def test_mcp_renames_folder_at_current_revision(api_client, mcp_token):
    folder = filing.save_folder(data={'name': 'Original'})

    response = call_tool(api_client, mcp_token, 'update_secure_link_folder', {
        'folder_id': folder.pk,
        'name': 'Entregas',
        'expected_updated_at': folder.updated_at.isoformat(),
    })

    folder.refresh_from_db()
    assert folder.name == 'Entregas'
    assert json.loads(text(response))['name'] == 'Entregas'


def test_mcp_reparenting_preserves_folder_project(api_client, mcp_token, project, make_link):
    folder = filing.save_folder(data={'name': 'Entregas', 'parent': project.secure_link_root_folder})
    destination = filing.save_folder(data={'name': 'Propia'})
    link, _ = make_link(folder=folder)

    response = call_tool(api_client, mcp_token, 'move_secure_link_folder', {
        'folder_id': folder.pk, 'parent': destination.pk,
    })

    folder.refresh_from_db()
    link.refresh_from_db()
    assert json.loads(text(response))['parent'] == destination.pk
    assert folder.parent_id == destination.pk
    assert folder.project_id == link.project_id == project.pk
    assert link.folder_id == folder.pk


def test_mcp_reorders_manual_siblings(api_client, mcp_token):
    first = filing.save_folder(data={'name': 'Primera'})
    second = filing.save_folder(data={'name': 'Segunda'})

    response = call_tool(api_client, mcp_token, 'reorder_secure_link_folders', {
        'ids': [second.pk, first.pk], 'parent': None,
    })

    assert json.loads(text(response)) == {'success': True}
    assert list(SecureLinkFolder.objects.order_by('order').values_list('pk', flat=True)) == [second.pk, first.pk]


def test_mcp_missing_folder_returns_structured_error(api_client, mcp_token):
    response = call_tool(api_client, mcp_token, 'get_secure_link_folder', {'folder_id': 999999})

    assert result(response)['isError'] is True
    assert error_code(response) == 'folder_not_found'
