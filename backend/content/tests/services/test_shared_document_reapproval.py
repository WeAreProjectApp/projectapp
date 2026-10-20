"""Reapproval is a new confirmed package, never a bypass of the review."""
import pytest
from rest_framework.exceptions import ValidationError

from content.models import DocumentFolder
from content.services.proposal_approval_service import source_hash, review_proposal
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
