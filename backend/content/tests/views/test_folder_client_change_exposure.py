"""Folder client changes expose portal audiences only under an explicit policy."""

from types import SimpleNamespace

import pytest
from accounts.document_views import _visible_docs_qs
from accounts.models import Project
from django.urls import reverse

from content.models import Document, DocumentFolder, McpConnector, McpCredential
from content.services.document_type_utils import get_collection_account_document_type
from content.tests.mcp_parity import (
    assert_no_writes,
    call_tool_inprocess,
    ownership_state,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def folder_change(make_client_profile, superuser):
    old = make_client_profile(company='Previous client')
    new = make_client_profile(company='New client')
    project = Project.objects.create(name='Previous project', client=old.user)
    folder = DocumentFolder.objects.create(name='Manual client folder', client_user=old.user)
    child = DocumentFolder.objects.create(name='Nested client folder', parent=folder, client_user=old.user)
    document = Document.objects.create(
        title='Visible inherited document', folder=child, project=project,
        client_user=None, is_client_visible=True,
    )
    connector, _ = McpConnector.objects.get_or_create(slug='documents', defaults={'name': 'Documents'})
    credential = McpCredential.objects.create(connector=connector, actor=superuser, label='Folder exposure review')
    return SimpleNamespace(
        old=old, new=new, folder=folder, child=child, document=document, credential=credential,
        preview_url=reverse('preview-document-folder-client-change', kwargs={'folder_id': folder.pk}),
        apply_url=reverse('change-document-folder-client', kwargs={'folder_id': folder.pk}),
        arguments={'folder_id': folder.pk, 'client_profile_id': new.pk, 'mode': 'propagate',
                   'document_ids': [document.pk], 'folder_ids': [child.pk]},
    )


def invoke(case, name, arguments):
    return call_tool_inprocess('documents', name, arguments, credential=case.credential)


def confirm_change(case, arguments):
    prepared = invoke(case, 'change_folder_client', arguments)
    assert 'error' not in prepared, prepared
    return invoke(case, 'confirm_action', {'confirmation_id': prepared['confirmation_id']})


def panel_arguments(case, **overrides):
    return {key: value for key, value in {**case.arguments, **overrides}.items() if key != 'folder_id'}


def test_preview_reports_only_new_portal_exposure(folder_change, admin_client):
    case = folder_change
    Document.objects.create(title='Hidden', folder=case.child, is_client_visible=False)
    Document.objects.create(title='Archived', folder=case.child, is_client_visible=True, is_archived=True)
    Document.objects.create(
        title='Collection account', folder=case.child, is_client_visible=True,
        document_type=get_collection_account_document_type(),
    )
    Document.objects.create(title='Already visible to target', folder=case.child, client_user=case.new.user, is_client_visible=True)
    initial = ownership_state()

    response = admin_client.get(case.preview_url, {'client_profile_id': case.new.pk})
    mcp = assert_no_writes(invoke, case, 'preview_folder_client_change', {
        'folder_id': case.folder.pk, 'client_profile_id': case.new.pk,
    })

    assert response.status_code == 200
    assert response.json()['portal_changes'] == mcp['portal_changes'] == [{
        'document_id': case.document.pk, 'before_audience': case.old.user_id, 'after_audience': case.new.user_id,
    }]
    assert ownership_state() == initial


@pytest.mark.parametrize('arguments_style', ['flat', 'data'])
def test_mcp_omitted_policy_refuses_exposure(folder_change, arguments_style):
    case = folder_change
    arguments = {
        'flat': case.arguments,
        'data': {'folder_id': case.folder.pk, 'data': panel_arguments(case)},
    }[arguments_style]
    initial = ownership_state()

    result = confirm_change(case, arguments)

    assert result['error']['code'] == 'PORTAL_EXPOSURE'
    assert result['error']['details']['blockers'] == [{
        'code': 'portal_exposure', 'message': 'El cambio daría acceso a un nuevo cliente en el portal.',
        'resource_type': 'document', 'resource_id': case.document.pk, 'document_id': case.document.pk,
        'before_audience': case.old.user_id, 'after_audience': case.new.user_id,
    }]
    assert ownership_state() == initial
    assert not _visible_docs_qs(SimpleNamespace(user=case.new.user)).filter(pk=case.document.pk).exists()


def test_hide_new_exposure_reassigns_a_private_document(folder_change, admin_client):
    case = folder_change
    response = admin_client.post(case.apply_url, panel_arguments(case, portal_policy='hide_new_exposure'), format='json')

    case.document.refresh_from_db()
    case.child.refresh_from_db()
    assert response.status_code == 200
    assert response.json()['moved'] == {'folders': 1, 'documents': 1}
    assert (case.document.client_user_id, case.document.project_id, case.document.is_client_visible) == (
        case.new.user_id, None, False,
    )
    assert case.child.client_user_id == case.new.user_id
    assert not _visible_docs_qs(SimpleNamespace(user=case.new.user)).filter(pk=case.document.pk).exists()


@pytest.mark.parametrize('arguments_style', ['flat', 'data'])
def test_mcp_allow_exposes_the_document(folder_change, arguments_style):
    case = folder_change
    arguments = {
        'flat': {**case.arguments, 'portal_policy': 'allow'},
        'data': {'folder_id': case.folder.pk, 'data': panel_arguments(case, portal_policy='allow')},
    }[arguments_style]

    result = confirm_change(case, arguments)

    case.document.refresh_from_db()
    assert result['result']['moved']['documents'] == 1
    assert (case.document.client_user_id, case.document.project_id, case.document.is_client_visible) == (
        case.new.user_id, None, True,
    )
    assert _visible_docs_qs(SimpleNamespace(user=case.new.user)).filter(pk=case.document.pk).exists()


def test_panel_without_policy_keeps_legacy_exposure(folder_change, admin_client):
    case = folder_change
    response = admin_client.post(case.apply_url, panel_arguments(case), format='json')

    case.document.refresh_from_db()
    assert response.status_code == 200
    assert response.json()['moved']['documents'] == 1
    assert case.document.is_client_visible is True
    assert _visible_docs_qs(SimpleNamespace(user=case.new.user)).filter(pk=case.document.pk).exists()


def test_panel_abort_returns_structured_conflict(folder_change, admin_client):
    case = folder_change
    initial = ownership_state()

    response = admin_client.post(case.apply_url, panel_arguments(case, portal_policy='abort'), format='json')

    assert response.status_code == 409
    assert response.json()['code'] == 'portal_exposure'
    assert response.json()['details']['blockers'][0]['document_id'] == case.document.pk
    assert ownership_state() == initial


def test_folder_only_does_not_transfer_portal_access(folder_change):
    case = folder_change
    result = confirm_change(case, {**case.arguments, 'mode': 'folder_only'})

    case.folder.refresh_from_db()
    case.document.refresh_from_db()
    assert result['result']['moved'] == {'folders': 0, 'documents': 0}
    assert case.folder.client_user_id == case.new.user_id
    assert case.document.project.client_id == case.old.user_id
    assert _visible_docs_qs(SimpleNamespace(user=case.old.user)).filter(pk=case.document.pk).exists()
    assert not _visible_docs_qs(SimpleNamespace(user=case.new.user)).filter(pk=case.document.pk).exists()


def test_invalid_portal_policy_is_rejected(folder_change, admin_client):
    case = folder_change
    initial = ownership_state()

    response = admin_client.post(case.apply_url, panel_arguments(case, portal_policy='invalid'), format='json')

    assert response.status_code == 400
    assert 'portal_policy' in response.json()
    assert ownership_state() == initial
