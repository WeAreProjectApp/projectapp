"""The maintenance CLI defaults to a reviewable preview without DB writes."""
import json
from io import StringIO

import pytest
from accounts.models import UserProfile
from django.core.management import call_command

from content.models import Document, DocumentFolder, DocumentType
from content.services.document_folder_repair import fingerprint

pytestmark = pytest.mark.django_db


def test_command_preview_writes_reviewable_manifest(django_user_model, tmp_path):
    owner = django_user_model.objects.create_user(username='preview-owner')
    client = UserProfile.objects.create(user=owner, role=UserProfile.ROLE_CLIENT)
    source = DocumentFolder.objects.create(name='Littigio', creation_source='unknown')
    target = DocumentFolder.objects.create(name='Littigio', managed_client=owner, client_user=owner)
    kind = DocumentType.objects.create(code='markdown', name='Markdown')
    document = Document.objects.create(title='Review me', folder=source, document_type=kind)
    output = tmp_path / 'repair.json'
    stdout = StringIO()

    call_command(
        'repair_document_folder', source_folder_id=source.pk, target_folder_id=target.pk,
        client_profile_id=client.pk, document_ids=[document.pk], manifest=str(output), stdout=stdout,
    )

    manifest = json.loads(output.read_text())
    assert manifest['source_folder_id'] == source.pk
    assert manifest['target_folder_id'] == target.pk
    assert manifest['client_profile_id'] == client.pk
    assert manifest['document_ids'] == [document.pk]
    assert json.loads(stdout.getvalue()) == {
        'apply': False, 'manifest': str(output), 'sha256': fingerprint(manifest),
    }
    document.refresh_from_db()
    assert document.folder_id == source.pk
    source.refresh_from_db()
    assert source.is_archived is False
