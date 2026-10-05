"""Authorization and immutability contracts for document organization writes."""
import pytest
from accounts.models import Project
from django.urls import reverse

from content.models import (
    ContractTemplate,
    Document,
    DocumentFolder,
    DocumentType,
    McpConnector,
    McpCredential,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def markdown_type():
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown'},
    )
    return document_type


@pytest.fixture
def scoped_rpc(api_client, superuser):
    connector, _ = McpConnector.objects.get_or_create(
        slug='documents', defaults={'name': 'Documents'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    credential = McpCredential.objects.get(
        connector=connector, token_hash=McpCredential.hash_token(token),
    )

    def call(name, arguments):
        response = api_client.post(
            f'/api/mcp/documents/{token}/',
            {
                'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                'params': {'name': name, 'arguments': arguments},
            },
            format='json',
        )
        return response.data['result']

    return credential, call


def test_capabilities_hide_tools_outside_credential_scope(scoped_rpc):
    """Falla si describe_capabilities enumera una herramienta que la credencial no puede llamar."""
    credential, rpc = scoped_rpc
    credential.allowed_tools = ['list_documents']
    credential.save(update_fields=['allowed_tools'])

    result = rpc('describe_capabilities', {
        'tools': ['list_documents', 'move_documents'], 'summary': True,
    })
    tool, = result['structuredContent']['tools']

    assert result['isError'] is False
    assert tool['name'] == 'list_documents'
    assert set(tool) == {'name', 'title', 'risk', 'requires_confirmation'}


def test_scoped_credential_cannot_move_documents(scoped_rpc, markdown_type):
    """Falla si una credencial limitada puede usar move_documents para cambiar una carpeta."""
    credential, rpc = scoped_rpc
    credential.allowed_tools = ['list_documents']
    credential.save(update_fields=['allowed_tools'])
    document = Document.objects.create(
        title='Scoped', document_type=markdown_type, content_markdown='# Scoped',
    )
    destination = DocumentFolder.objects.create(name='Destination')

    result = rpc('move_documents', {
        'document_ids': [document.pk], 'folder_id': destination.pk,
    })
    document.refresh_from_db()

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'FORBIDDEN'
    assert document.folder_id is None


def test_move_request_rejects_a_selection_containing_a_mirror(
    admin_client, superuser, markdown_type,
):
    """Falla si un lote que contiene un espejo permite mover algún documento."""
    project = Project.objects.create(name='Original project', client=superuser)
    mirror = Document.objects.create(
        title='Contract window', document_type=markdown_type,
        content_markdown='# Stored pointer', client_user=superuser,
        client_name='Original client', project=project,
    )
    ContractTemplate.objects.create(name='Contract window', mirror_document=mirror)
    normal = Document.objects.create(
        title='Normal', document_type=markdown_type, content_markdown='# Normal',
    )
    destination = DocumentFolder.objects.create(name='Destination')

    response = admin_client.post(
        reverse('move-documents'),
        {'document_ids': [mirror.pk, normal.pk], 'folder_id': destination.pk},
        format='json',
    )
    mirror.refresh_from_db()
    normal.refresh_from_db()

    assert response.status_code == 409
    assert mirror.folder_id is None
    assert normal.folder_id is None
    assert mirror.content_markdown == '# Stored pointer'
    assert mirror.client_user_id == superuser.pk
    assert mirror.client_name == 'Original client'
    assert mirror.project_id == project.pk


def _generated_snapshot(markdown_type):
    return Document.objects.create(
        title='Generated', document_type=markdown_type,
        generated_file='snapshots/generated.pdf',
    )


def _issued_account(markdown_type):
    account_type, _ = DocumentType.objects.get_or_create(
        code='collection_account', defaults={'name': 'Cuenta de cobro'},
    )
    return Document.objects.create(
        title='Issued', document_type=account_type,
        commercial_status=Document.CommercialStatus.ISSUED,
    )


@pytest.mark.parametrize(
    ('make_blocked', 'expected_reason'),
    ((_generated_snapshot, 'generated_snapshot'), (_issued_account, 'collection_account_locked')),
)
def test_move_request_rolls_back_when_a_document_is_protected(
    admin_client, markdown_type, make_blocked, expected_reason,
):
    """Falla si una solicitud con un documento protegido mueve de todas formas al documento válido."""
    normal = Document.objects.create(
        title='Normal', document_type=markdown_type, content_markdown='# Normal',
    )
    blocked = make_blocked(markdown_type)
    destination = DocumentFolder.objects.create(name='Destination')

    response = admin_client.post(
        reverse('move-documents'),
        {'document_ids': [normal.pk, blocked.pk], 'folder_id': destination.pk},
        format='json',
    )
    normal.refresh_from_db()
    blocked.refresh_from_db()

    assert response.status_code == 409
    assert response.data['results'][0]['status'] == 'aborted'
    assert response.data['results'][1]['reason'] == expected_reason
    assert normal.folder_id is None
    assert blocked.folder_id is None
