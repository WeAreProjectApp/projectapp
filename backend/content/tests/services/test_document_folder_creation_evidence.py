"""Evidence-backed provenance for the Littigio folder repair."""
from datetime import timedelta

import pytest
from accounts.models import UserProfile
from django.utils import timezone

from content.models import (
    Document,
    DocumentFolder,
    DocumentType,
    McpConnector,
    McpCredential,
    McpRequestLog,
)
from content.services.document_folder_repair import (
    FolderRepairError,
    apply_repair,
    fingerprint,
    prepare_repair,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def evidence_case(django_user_model):
    client_user = django_user_model.objects.create_user(username='littigio-client')
    client = UserProfile.objects.create(user=client_user, role=UserProfile.ROLE_CLIENT)
    source = DocumentFolder.objects.create(name='Littigio', creation_source='unknown')
    target = DocumentFolder.objects.create(
        name='Littigio', managed_client=client_user, client_user=client_user,
    )
    now = timezone.now()
    DocumentFolder.objects.filter(pk=target.pk).update(created_at=now - timedelta(minutes=5))
    DocumentFolder.objects.filter(pk=source.pk).update(created_at=now)
    source.refresh_from_db()
    kind = DocumentType.objects.create(code='evidence-markdown', name='Evidence Markdown')
    document = Document.objects.create(title='Littigio evidence', folder=source, document_type=kind)
    connector, _ = McpConnector.objects.get_or_create(
        slug='documents', defaults={'name': 'Documents', 'is_active': True},
    )
    return source, target, client, document, connector, now


def test_matching_mcp_evidence_attributes_the_archived_source(evidence_case, superuser):
    """Falla si una reparación probada no conserva el actor y la operación MCP de origen."""
    source, target, client, document, connector, now = evidence_case
    credential = McpCredential.objects.create(
        connector=connector, label='Evidence', token_hash='evidence-token', actor=superuser,
    )
    log = McpRequestLog.objects.create(
        connector=connector, credential=credential, request_id='request-124', event='tool_call',
        ok=True, tool_name='create_folder',
    )
    McpRequestLog.objects.filter(pk=log.pk).update(created_at=now)

    manifest = prepare_repair(
        source.pk, target.pk, client.pk, [document.pk], creation_request_id='request-124',
    )
    result = apply_repair(
        manifest, expected_hash=fingerprint(manifest), actor=superuser, backup_ref='backup-124.sql.gz',
    )

    source.refresh_from_db()
    document.refresh_from_db()
    assert manifest['creation_evidence'] == {
        'request_id': 'request-124', 'log_id': log.pk,
        'actor_id': superuser.pk, 'source': 'mcp', 'operation': 'create_folder',
    }
    assert result == {'changed': True, 'document_ids': [document.pk]}
    assert source.is_archived is True
    assert source.creation_source == 'mcp'
    assert source.creation_operation == 'create_folder'
    assert source.created_by_id == superuser.pk
    assert document.folder_id == target.pk


def test_mismatched_mcp_request_leaves_the_source_untouched(evidence_case, superuser):
    """Falla si evidencia MCP de otra solicitud atribuye o mueve una carpeta desconocida."""
    source, target, client, document, connector, now = evidence_case
    credential = McpCredential.objects.create(
        connector=connector, label='Evidence', token_hash='evidence-token', actor=superuser,
    )
    log = McpRequestLog.objects.create(
        connector=connector, credential=credential, request_id='request-124', event='tool_call',
        ok=True, tool_name='create_folder',
    )
    McpRequestLog.objects.filter(pk=log.pk).update(created_at=now)

    with pytest.raises(FolderRepairError, match='evidencia de creación'):
        prepare_repair(
            source.pk, target.pk, client.pk, [document.pk], creation_request_id='wrong-request',
        )

    source.refresh_from_db()
    document.refresh_from_db()
    assert source.creation_source == 'unknown'
    assert source.creation_operation == 'orm.create'
    assert source.created_by_id is None
    assert source.is_archived is False
    assert document.folder_id == source.pk


def test_second_folder_in_evidence_window_leaves_the_source_untouched(
    evidence_case, superuser,
):
    """Falla si dos carpetas en la ventana permiten atribuir o mover una carpeta desconocida."""
    source, target, client, document, connector, now = evidence_case
    credential = McpCredential.objects.create(
        connector=connector, label='Evidence', token_hash='evidence-token', actor=superuser,
    )
    log = McpRequestLog.objects.create(
        connector=connector, credential=credential, request_id='request-124', event='tool_call',
        ok=True, tool_name='create_folder',
    )
    McpRequestLog.objects.filter(pk=log.pk).update(created_at=now)
    other = DocumentFolder.objects.create(name='Other folder')
    DocumentFolder.objects.filter(pk=other.pk).update(created_at=now)

    with pytest.raises(FolderRepairError, match='evidencia de creación'):
        prepare_repair(
            source.pk, target.pk, client.pk, [document.pk], creation_request_id='request-124',
        )

    source.refresh_from_db()
    document.refresh_from_db()
    assert source.creation_source == 'unknown'
    assert source.creation_operation == 'orm.create'
    assert source.created_by_id is None
    assert source.is_archived is False
    assert document.folder_id == source.pk
