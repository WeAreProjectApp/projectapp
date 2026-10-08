"""Confirmed private packages become explicit, unsigned delivery sources."""
import hashlib

import pytest
from content.models import BusinessProposal, ProposalApprovalFile
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.models import ContractAmendment, Deliverable, Project, ProjectContract
from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_contract_sources import contract_source_file
from accounts.tests.delivery_authoring_helpers import docx_bytes, pdf_bytes
from accounts.tests.delivery_helpers import (
    build_delivery_context,
    prepare_prompt,
    version,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    """Build the isolated project with real delivery users and documents."""
    return build_delivery_context()


def confirmed_file(context, raw=None, filename='confirmed.pdf', *, project=None):
    """Create original bytes bound to a confirmed proposal manifest."""
    raw = pdf_bytes('The confirmed contract includes creating records.') if raw is None else raw
    project = project or context.project
    deliverable = Deliverable.objects.create(project=project, title='Confirmed package', uploaded_by=context.admin)
    proposal = BusinessProposal.objects.create(
        title='Approved proposal', client_name='Client', client=context.client.profile,
        status='accepted', deliverable=deliverable,
    )
    source = ProposalApprovalFile.objects.create(
        proposal=proposal, project=project, deliverable=deliverable, source_key='custom:0',
        title='Confirmed agreement', document_type='contract', filename=filename,
        file=ContentFile(raw, name=filename), size=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
        created_by=context.admin,
    )
    proposal.platform_approval_manifest = {
        'client_profile_id': context.client.profile.pk, 'project_id': project.pk,
        'files': [{'id': source.pk, 'source_key': source.source_key, 'sha256': source.sha256, 'size': source.size}],
    }
    proposal.save(update_fields=['platform_approval_manifest'])
    return source


def create_source(context, source, *, kind='contracts', **overrides):
    """Register a confirmed source through the real delivery mutation."""
    data = {'expected_version': version(context), 'request_id': f'create-{kind}-{source.pk}',
            'key': 'confirmed-package', 'title': 'Confirmed agreement', 'approval_file_id': source.pk}
    if kind == 'amendments':
        data['contract_id'] = context.contract.pk
    data.update(overrides)
    result = delivery.mutate_node(context.project.pk, context.admin, kind, data)
    model = ProjectContract if kind == 'contracts' else ContractAmendment
    return model.objects.get(pk=result['result']['id'])


@pytest.mark.parametrize('kind', ['contracts', 'amendments'])
def test_package_file_is_registered_without_a_signature(context, kind):
    """A signed-looking filename cannot supply signature evidence."""
    source = confirmed_file(context, filename='signed-contract.pdf')

    node = create_source(context, source, kind=kind)

    assert node.approval_file_id == source.pk
    assert delivery.signature_state(node)['signature_status'] == 'unsigned'
    assert not node.signature_evidence.exists()


def test_new_package_contract_stays_private(context):
    """A newly registered package remains absent from the client workspace."""
    node = create_source(context, confirmed_file(context))

    workspace = delivery.overview(context.project.pk, context.client)

    assert node.client_visible is False
    assert node.pk not in [contract['id'] for contract in workspace['contracts']]


def test_creation_cannot_publish_a_package_contract(context):
    """Creation rejects client visibility without changing project state."""
    source = confirmed_file(context)

    with pytest.raises(ValidationError, match='primero en privado'):
        create_source(context, source, client_visible=True)

    assert not ProjectContract.objects.filter(approval_file=source).exists()
    assert version(context) == 0


def test_package_file_cannot_be_combined_with_a_document(context):
    """A contractual node rejects simultaneous document and package sources."""
    source = confirmed_file(context)

    with pytest.raises(ValidationError, match='sola fuente'):
        create_source(context, source, document_id=context.document.pk)

    assert not ProjectContract.objects.filter(approval_file=source).exists()


def test_another_project_package_cannot_be_selected(context):
    """A confirmed source remains limited to its owning project."""
    other = Project.objects.create(name='Another project', client=context.client)
    source = confirmed_file(context, project=other)

    with pytest.raises(ValidationError, match='este proyecto y cliente'):
        create_source(context, source)

    assert version(context) == 0


def test_unconfirmed_file_is_omitted_from_options(context):
    """Removing manifest confirmation removes the source from valid options."""
    source = confirmed_file(context)
    source.proposal.platform_approval_manifest['files'] = []
    source.proposal.save(update_fields=['platform_approval_manifest'])

    options = delivery.document_options(context.project.pk, context.admin)

    assert options['approval_files'] == []


def test_options_do_not_publish_storage_paths(context):
    """Selectable source metadata does not expose private storage locations."""
    source = confirmed_file(context)

    options = delivery.document_options(context.project.pk, context.admin)

    assert options['approval_files'][0]['id'] == source.pk
    assert options['approval_files'][0]['sha256'] == source.sha256
    assert 'file' not in options['approval_files'][0]
    assert 'download_url' not in options['approval_files'][0]


def test_modified_package_bytes_are_rejected_before_creation(context):
    """Changed package bytes cannot create a contract from its old manifest."""
    source = confirmed_file(context)
    with source.file.open('wb') as stream:
        stream.write(pdf_bytes('Different unconfirmed terms.'))

    with pytest.raises(ValidationError, match='huella conservada'):
        create_source(context, source)

    assert not ProjectContract.objects.filter(approval_file=source).exists()
    assert version(context) == 0


def test_repeated_creation_preserves_the_same_contract(context):
    """Replaying one request keeps exactly one contractual node."""
    source = confirmed_file(context)
    data = {'expected_version': 0, 'request_id': 'repeat-contract', 'key': 'repeat',
            'title': 'Confirmed agreement', 'approval_file_id': source.pk}
    first = delivery.mutate_node(context.project.pk, context.admin, 'contracts', data)

    repeated = delivery.mutate_node(context.project.pk, context.admin, 'contracts', data)

    assert repeated['result']['id'] == first['result']['id']
    assert ProjectContract.objects.filter(approval_file=source).count() == 1


@pytest.mark.parametrize(('filename', 'raw', 'content_type'), [
    ('agreement.docx', docx_bytes(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    ('agreement.png', b'\x89PNG\r\n\x1a\noriginal image', 'image/png'),
])
def test_source_download_keeps_the_confirmed_format(context, filename, raw, content_type):
    """Original downloads preserve the confirmed bytes and exact MIME type."""
    source = confirmed_file(context, raw, filename)
    node = create_source(context, source)
    api = APIClient()
    api.force_authenticate(context.admin)

    response = api.get(f'/api/accounts/projects/{context.project.pk}/delivery/contracts/{node.pk}/source/')

    assert response.status_code == 200
    assert response.content == raw
    assert filename in response['Content-Disposition']
    assert response['Content-Type'] == content_type
    assert response['Cache-Control'] == 'private, no-store'


def test_private_contract_source_is_hidden_from_client(context):
    """Client authentication does not authorize a private source download."""
    node = create_source(context, confirmed_file(context))
    api = APIClient()
    api.force_authenticate(context.client)

    response = api.get(f'/api/accounts/projects/{context.project.pk}/delivery/contracts/{node.pk}/source/')

    assert response.status_code == 404


def test_docx_prompt_retains_exact_package_bytes(context):
    """Prompt capture retains the confirmed DOCX instead of a regenerated PDF."""
    raw = docx_bytes()
    source = confirmed_file(context, raw, 'agreement.docx')
    node = create_source(context, source)

    captured = prepare_prompt(context, contract_id=node.pk)

    prompt_source = node.prompt_contexts.get().sources.get(role='contract')
    with prompt_source.file.open('rb') as stream:
        assert stream.read() == raw
    assert prompt_source.origin == 'approval_file'
    assert prompt_source.source_id == str(source.pk)
    assert 'Original DOCX reference.' in captured['prompt']
    assert captured['complete'] is False


def test_unextractable_original_keeps_an_explicit_warning(context):
    """Unreadable original bytes cannot become a complete textual source."""
    source = confirmed_file(context, b'\x89PNG\r\n\x1a\noriginal image', 'agreement.png')
    node = create_source(context, source)

    captured = prepare_prompt(context, contract_id=node.pk)

    assert captured['sources'][0]['status'] == 'unreadable'
    assert captured['sources'][0]['fragments'] == []
    assert captured['complete'] is False


def test_external_signed_copy_is_the_contractual_download(context):
    """The verified signed copy becomes the canonical contractual download."""
    source = confirmed_file(context, docx_bytes(), 'agreement.docx')
    node = create_source(context, source)
    signed = pdf_bytes('The exact signed contract includes creating records.')
    delivery.attest_signature(context.project.pk, context.admin, 'contracts', node.pk, {
        'expected_version': version(context), 'request_id': 'sign-package', 'signer_name': 'Client',
        'signed_at': '2026-09-30T12:00:00Z', 'attestation': 'Client signature verified externally.',
    }, SimpleUploadedFile('signed.pdf', signed, content_type='application/pdf'))

    raw, filename, content_type = contract_source_file(context.project.pk, context.admin, 'contracts', node.pk)

    assert raw == signed
    assert filename.endswith('.pdf')
    assert content_type == 'application/pdf'


def test_package_source_cannot_be_deleted_while_a_contract_uses_it(context):
    """An explicit contractual reference protects its source from deletion."""
    source = confirmed_file(context)
    create_source(context, source)

    with pytest.raises(ProtectedError):
        source.delete()

    assert ProposalApprovalFile.objects.filter(pk=source.pk).exists()


def test_database_rejects_two_contractual_sources(context):
    """The database enforces source exclusivity when service checks are bypassed."""
    source = confirmed_file(context)

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectContract.objects.create(project=context.project, key='invalid', title='Invalid',
                                       document=context.document, approval_file=source)

    assert not ProjectContract.objects.filter(key='invalid').exists()
