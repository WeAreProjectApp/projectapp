"""The operational initializer can safely be repeated."""
import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db

def test_mirror_initializer_is_idempotent_after_all_three_mirrors_are_current(
    initialized_contract_mirrors, superuser,
):
    """Falla si reinicializar espejos vigentes crea documentos, PDFs o notas duplicadas."""
    mirrors = {row.variant: row for row in initialized_contract_mirrors.mirrors.select_related('document')}
    folder_id = mirrors['combined'].document.folder_id
    document_ids_before = {key: row.document_id for key, row in mirrors.items()}
    pdfs_before = {key: bytes(row.pdf_content) for key, row in mirrors.items()}
    notes_before = {key: row.document.document_notes.count() for key, row in mirrors.items()}

    call_command(
        'initialize_contract_template_mirrors', '--apply', '--folder-id', str(folder_id),
        '--service-document-id', str(mirrors['service'].document_id), '--actor-id', str(superuser.pk),
    )
    after = {row.variant: row for row in initialized_contract_mirrors.mirrors.select_related('document')}

    assert {key: row.document_id for key, row in after.items()} == document_ids_before
    assert {key: bytes(row.pdf_content) for key, row in after.items()} == pdfs_before
    assert {key: row.document.document_notes.count() for key, row in after.items()} == notes_before
