"""Reapproval is a new confirmed package, never a bypass of the review."""
import pytest
from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError

from content.models import DocumentFolder, ProposalDocument
from content.services.proposal_approval_service import load_proposal, source_hash, review_proposal
from content.services.proposal_shared_documents import reconfirm, replace_binary_source
from content.tests.views.test_proposal_shared_documents import confirmed_proposal, approval_client, reviewed_proposal, revision_payload
from content.tests.views.test_proposal_approval import payload, pdf

pytestmark = pytest.mark.django_db


def test_reapproval_confirms_a_new_package_before_accepting(confirmed_proposal, admin_user):
    confirmed_proposal.status = 'negotiating'
    confirmed_proposal.save(update_fields=['status'])
    old_files = list(confirmed_proposal.approval_files.values_list('id', 'sha256'))

    package = reconfirm(confirmed_proposal.pk, revision_payload(confirmed_proposal, accept_proposal=True), actor=admin_user)

    confirmed_proposal.refresh_from_db()
    assert confirmed_proposal.status == 'accepted'
    assert package.number == 2
    assert package.source_hash == source_hash(confirmed_proposal)
    assert list(confirmed_proposal.approval_files.filter(package__number=1).values_list('id', 'sha256')) == old_files


def test_historical_binary_is_not_editable(confirmed_proposal, admin_user):
    binding = confirmed_proposal.document_bindings.get(source_key='custom-contract')
    binding.is_current = False
    binding.save(update_fields=['is_current'])

    with pytest.raises(ValidationError, match='fuente'):
        replace_binary_source(binding.pk, {'source_hash': source_hash(confirmed_proposal)}, pdf(), actor=admin_user)

    binding.refresh_from_db()
    assert not binding.draft_file


@pytest.fixture
def split_approved_proposal(reviewed_proposal, approval_client, admin_user):
    from content.services.contract_variants import FINAL_REQUIRED_PARAMS, SERVICE_PARAM_KEYS

    reviewed_proposal.status = 'accepted'
    reviewed_proposal.contract_modality = 'split'
    reviewed_proposal.service_contract_approved = True
    reviewed_proposal.contract_params = {key: 'Reviewed' for key in FINAL_REQUIRED_PARAMS + SERVICE_PARAM_KEYS}
    reviewed_proposal.contract_params['contractor_nit'] = '123456789'
    reviewed_proposal.save()
    product = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='contract_product', title='Product', is_generated=True)
    product.file.save('product.pdf', ContentFile(b'%PDF-1.4 product'))
    service = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='contract_service', title='Service', is_generated=True)
    service.file.save('service.pdf', ContentFile(b'%PDF-1.4 service'))
    annex = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='legal_annex', title='Annex')
    annex.file.save('annex.pdf', ContentFile(b'%PDF-1.4 annex'))
    initial = payload(reviewed_proposal, approval_client)
    initial.update(use_proposal_contracts=True, custom_documents=[])
    review_proposal(reviewed_proposal.pk, initial, actor=admin_user)
    return load_proposal(reviewed_proposal.pk), annex


def test_split_reapproval_retires_only_the_unapproved_service_identity(split_approved_proposal, admin_user):
    """Fails if removing service approval overwrites immutable bytes or leaves the service current."""
    proposal, annex = split_approved_proposal
    service_binding = proposal.document_bindings.get(source_key='contract_service')
    original_service = service_binding.current_file
    original_bytes = original_service.file.read()

    proposal.service_contract_approved = False
    proposal.save(update_fields=['service_contract_approved'])
    replacement = reconfirm(proposal.pk, revision_payload(proposal, use_proposal_contracts=True), actor=admin_user)

    service_binding.refresh_from_db()
    original_service.refresh_from_db()
    assert (service_binding.is_current, original_service.pk, original_service.file.read()) == (
        False, original_service.pk, original_bytes,
    )
    assert proposal.document_bindings.get(source_key='contract_product').current_file.package_id == replacement.pk
    assert proposal.document_bindings.get(source_key=f'original-{annex.pk}').current_file.package_id == replacement.pk



def test_split_reapproval_reuses_the_retired_service_document_identity(
    split_approved_proposal, admin_user,
):
    """Fails if reapproving generated service terms creates a second gestor document."""
    proposal, _annex = split_approved_proposal
    service_binding = proposal.document_bindings.get(source_key='contract_service')
    service_document_id = service_binding.document_id
    proposal.service_contract_approved = False
    proposal.save(update_fields=['service_contract_approved'])
    reconfirm(proposal.pk, revision_payload(proposal, use_proposal_contracts=True), actor=admin_user)
    proposal.service_contract_approved = True
    proposal.save(update_fields=['service_contract_approved'])

    restored = reconfirm(
        proposal.pk,
        revision_payload(proposal, request_id='third-confirmation', use_proposal_contracts=True),
        actor=admin_user,
    )

    service_binding.refresh_from_db()
    assert (service_binding.document_id, service_binding.is_current, service_binding.current_file.package_id) == (
        service_document_id, True, restored.pk,
    )


@pytest.fixture
def custom_split_approved_proposal(reviewed_proposal, approval_client, admin_user):
    reviewed_proposal.contract_modality = 'split'
    reviewed_proposal.service_contract_approved = True
    reviewed_proposal.save(update_fields=['contract_modality', 'service_contract_approved'])
    initial = payload(reviewed_proposal, approval_client)
    initial.update(
        use_proposal_contracts=False,
        custom_documents=[
            {'title': 'Product contract', 'document_type': 'contract_product'},
            {'title': 'Service contract', 'document_type': 'contract_service'},
        ],
    )
    review_proposal(
        reviewed_proposal.pk, initial, actor=admin_user,
        files=[pdf('product.pdf'), pdf('service.pdf')],
    )
    return load_proposal(reviewed_proposal.pk)


def test_custom_service_requires_a_new_file_after_product_only_reapproval(
    custom_split_approved_proposal, admin_user,
):
    """Fails if restoring custom service approval reuses a retired contract without a new file."""
    proposal = custom_split_approved_proposal
    service_binding = proposal.document_bindings.get(source_key='custom-contract_service')
    original = service_binding.current_file
    original_bytes, service_document_id = original.file.read(), service_binding.document_id

    proposal.service_contract_approved = False
    proposal.save(update_fields=['service_contract_approved'])
    reconfirm(
        proposal.pk, revision_payload(proposal, use_proposal_contracts=False), actor=admin_user,
    )
    proposal.service_contract_approved = True
    proposal.save(update_fields=['service_contract_approved'])

    restored = reconfirm(
        proposal.pk,
        revision_payload(
            proposal, request_id='custom-service-restored', use_proposal_contracts=False,
            custom_documents=[
                {'title': 'Product contract', 'document_type': 'contract_product'},
                {'title': 'Renewed service contract', 'document_type': 'contract_service'},
            ],
        ),
        actor=admin_user,
        files=[pdf('product.pdf'), pdf('renewed-service.pdf', b'%PDF-1.4 renewed service')],
    )

    service_binding.refresh_from_db()
    original.refresh_from_db()
    assert (original.file.read(), service_binding.document_id) == (original_bytes, service_document_id)
    assert (service_binding.is_current, service_binding.current_file.package_id) == (True, restored.pk)
    assert service_binding.current_file.file.read() == b'%PDF-1.4 renewed service'


@pytest.fixture
def existing_contract_folder(reviewed_proposal, approval_client):
    from accounts.models import Project
    project = Project.objects.create(name='Already organized', client=approval_client.user)
    root = DocumentFolder.objects.get(managed_project=project)
    folder = DocumentFolder.objects.create(name='Contratos', parent=root, project=project, client_user=approval_client.user)
    return project, folder


def test_existing_project_contract_folder_is_reused(reviewed_proposal, approval_client, admin_user, existing_contract_folder):
    project, folder = existing_contract_folder
    data = payload(reviewed_proposal, approval_client)
    data.pop('new_project')
    data['project_id'] = project.pk

    review_proposal(reviewed_proposal.pk, data, actor=admin_user, files=[pdf()])

    folder.refresh_from_db()
    assert folder.system_key == f'approval:project:{project.pk}:contracts'
    assert folder.parent.children.filter(name='Contratos').count() == 1
