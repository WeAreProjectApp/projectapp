"""Behavioral contract for internal approval without implicit provisioning."""
import json
from unittest.mock import patch
import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from accounts.models import DataModelEntity, Deliverable, Project, UserProfile
from content.models import ProposalApprovalFile, ProposalDocument, ProposalSection
from content.services.proposal_approval_service import review_proposal, source_hash

pytestmark = pytest.mark.django_db


@pytest.fixture
def approval_client(db):
    user = get_user_model().objects.create_user(username='review-client', email='review@example.com')
    return UserProfile.objects.create(user=user, role='client')


@pytest.fixture
def reviewed_proposal(proposal, approval_client):
    proposal.client = approval_client
    proposal.status = 'negotiating'
    proposal.save()
    ProposalSection.objects.create(proposal=proposal, section_type='technical_document', title='Technical', content_json={'epics': [{'epicKey': 'base', 'title': 'Base', 'requirements': [{'title': 'Login'}]}]}, order=0)
    return proposal


def payload(proposal, profile):
    return {'action': 'confirm', 'source_hash': source_hash(proposal), 'request_id': 'request-one', 'client_profile_id': profile.pk, 'new_project': {'name': 'Chosen project'}, 'use_proposal_contracts': False, 'custom_documents': [{'title': 'Signed contract', 'document_type': 'contract'}]}


def pdf(name='signed.pdf', content=b'%PDF-1.4 contract'):
    return SimpleUploadedFile(name, content, content_type='application/pdf')


def confirm(proposal, profile, actor, **changes):
    values = payload(proposal, profile)
    values.update(changes)
    return review_proposal(proposal.pk, values, actor=actor, files=[pdf()])


def test_defer_accepts_without_creating_a_project(reviewed_proposal, admin_user):
    result = review_proposal(reviewed_proposal.pk, {'action': 'defer'}, actor=admin_user)
    reviewed_proposal.refresh_from_db()
    assert result['proposal']['project_review_required'] is True
    assert reviewed_proposal.status == 'accepted'
    assert not Project.objects.exists()
    assert not ProposalApprovalFile.objects.exists()


def test_custom_packet_preserves_original_contract(reviewed_proposal, approval_client, admin_user):
    doc = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='contract', title='Original', is_generated=True)
    doc.file.save('original.pdf', ContentFile(b'%PDF-1.4 original'))
    result = confirm(reviewed_proposal, approval_client, admin_user)
    doc.refresh_from_db()
    assert sorted(row['document_type'] for row in result['confirmed_files']) == ['commercial', 'contract', 'technical']
    assert doc.file.read() == b'%PDF-1.4 original'
    assert doc.proposal_id == reviewed_proposal.pk


def test_multiple_custom_documents_are_frozen(reviewed_proposal, approval_client, admin_user):
    values = payload(reviewed_proposal, approval_client)
    values['custom_documents'] += [{'title': 'Annex', 'document_type': 'legal_annex'}]
    result = review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf(), pdf('annex.pdf', b'%PDF-1.4 annex')])
    assert [row['title'] for row in result['confirmed_files'] if row['document_type'] in ('contract', 'legal_annex')] == ['Signed contract', 'Annex']
    assert ProposalApprovalFile.objects.count() == 4


def test_existing_project_keeps_operational_data(reviewed_proposal, approval_client, admin_user):
    project = Project.objects.create(client=approval_client.user, name='Operational', progress=73, description='Private operation', payment_milestones=[{'protected': True}], hosting_tiers=[{'old': True}])
    resource = Deliverable.objects.create(project=project, uploaded_by=admin_user, source_epic_key='base', title='Keep title', description='Keep description', is_archived=True)
    entity = DataModelEntity.objects.create(deliverable=resource, name='Manual', description='Keep', source_entity_name='Manual')
    reviewed_proposal.sections.filter(section_type='technical_document').update(content_json={'epics': [{'epicKey': 'base', 'title': 'Base', 'requirements': [{'title': 'Login'}]}], 'dataModel': {'entities': [{'name': 'New from proposal', 'description': 'Must not enter the archived resource'}]}})
    values = payload(reviewed_proposal, approval_client)
    values.pop('new_project')
    values['project_id'] = project.pk
    review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    project.refresh_from_db()
    resource.refresh_from_db()
    entity.refresh_from_db()
    assert (project.name, project.progress, project.description, project.payment_milestones, project.hosting_tiers) == ('Operational', 73, 'Private operation', [{'protected': True}], [{'old': True}])
    assert (resource.title, resource.description, resource.is_archived, entity.description) == ('Keep title', 'Keep description', True, 'Keep')
    assert not resource.data_model_entities.filter(source_entity_name='New from proposal').exists()


def test_duplicate_confirmation_reuses_packet(reviewed_proposal, approval_client, admin_user):
    values = payload(reviewed_proposal, approval_client)
    first = review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    second = review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    assert second['idempotent'] is True
    assert first['confirmed_files'] == second['confirmed_files']
    assert Project.objects.count() == 1


@pytest.mark.parametrize('field,value', [('total_investment', 999), ('status', 'rejected')])
def test_stale_sources_leave_no_new_project(reviewed_proposal, approval_client, admin_user, field, value):
    from content.services.proposal_approval_service import ApprovalConflict
    values = payload(reviewed_proposal, approval_client)
    setattr(reviewed_proposal, field, value)
    reviewed_proposal.save(update_fields=[field])
    with pytest.raises(ApprovalConflict):
        review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    assert not Project.objects.exists()
    assert not ProposalApprovalFile.objects.exists()


@pytest.mark.parametrize('content', [b'', b'not-a-pdf'])
def test_invalid_upload_leaves_no_new_client(reviewed_proposal, admin_user, content):
    from rest_framework.exceptions import ValidationError
    values = payload(reviewed_proposal, reviewed_proposal.client)
    values.pop('client_profile_id')
    values['new_client'] = {'name': 'Inline', 'email': 'inline@example.com'}
    with pytest.raises(ValidationError):
        review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf(content=content)])
    assert not UserProfile.objects.filter(user__email='inline@example.com').exists()
    assert not Project.objects.exists()


def test_custom_mode_requires_at_least_one_file(reviewed_proposal, approval_client, admin_user):
    from rest_framework.exceptions import ValidationError
    with pytest.raises(ValidationError):
        review_proposal(reviewed_proposal.pk, payload(reviewed_proposal, approval_client), actor=admin_user)
    assert not Project.objects.exists()


def test_retry_uses_frozen_resources(reviewed_proposal, approval_client, admin_user):
    result = confirm(reviewed_proposal, approval_client, admin_user)
    reviewed_proposal.sections.filter(section_type='technical_document').update(content_json={'epics': [{'epicKey': 'new', 'title': 'Should not sync'}]})
    reviewed_proposal.total_investment = 777
    reviewed_proposal.save(update_fields=['total_investment'])
    approval_client.user.first_name = 'Changed client'
    approval_client.user.save(update_fields=['first_name'])
    retry = review_proposal(reviewed_proposal.pk, {'action': 'retry'}, actor=admin_user)
    assert retry['linked_project'] == result['linked_project']
    assert retry['client'] == result['client']
    assert retry['commercial_summary'] == result['commercial_summary']
    assert retry['confirmed_files'] == result['confirmed_files']
    assert not Deliverable.objects.filter(source_epic_key='new').exists()
    assert ProposalApprovalFile.objects.count() == 3


def test_retry_rejects_remapping(reviewed_proposal, approval_client, admin_user):
    from content.services.proposal_approval_service import ApprovalConflict
    confirm(reviewed_proposal, approval_client, admin_user)
    with pytest.raises(ApprovalConflict):
        review_proposal(reviewed_proposal.pk, {'action': 'retry', 'new_project': {'name': 'Replacement'}}, actor=admin_user)
    assert Project.objects.count() == 1


def test_inline_client_and_project_are_created_on_confirmation(reviewed_proposal, admin_user):
    values = payload(reviewed_proposal, reviewed_proposal.client)
    values.pop('client_profile_id')
    values['new_client'] = {'name': 'Inline', 'email': 'inline@example.com'}
    result = review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    profile = UserProfile.objects.get(user__email='inline@example.com')
    assert Project.objects.get(pk=result['linked_project']['id']).client_id == profile.user_id
    reviewed_proposal.refresh_from_db()
    assert reviewed_proposal.client_id == profile.pk


def test_legacy_link_keeps_deliverable_for_first_packet(reviewed_proposal, approval_client, admin_user):
    project = Project.objects.create(client=approval_client.user, name='Legacy')
    root = Deliverable.objects.create(project=project, title='Legacy', uploaded_by=admin_user)
    reviewed_proposal.deliverable = root
    reviewed_proposal.save(update_fields=['deliverable'])
    values = payload(reviewed_proposal, approval_client)
    values.pop('new_project')
    values['project_id'] = project.pk
    review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    reviewed_proposal.refresh_from_db()
    assert reviewed_proposal.deliverable_id == root.pk
    assert Project.objects.count() == 1


def test_panel_approval_requires_csrf(reviewed_proposal, admin_user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(admin_user)
    response = client.post(reverse('proposal-approval', kwargs={'proposal_id': reviewed_proposal.pk}), {'action': 'defer'}, format='json')
    assert response.status_code == 403
    reviewed_proposal.refresh_from_db()
    assert reviewed_proposal.status == 'negotiating'


def test_panel_approval_rejects_bearer_only(reviewed_proposal, admin_user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin_user)}')
    response = client.get(reverse('proposal-approval', kwargs={'proposal_id': reviewed_proposal.pk}))
    assert response.status_code == 403


def test_private_file_rejects_other_client(reviewed_proposal, approval_client, admin_user):
    result = confirm(reviewed_proposal, approval_client, admin_user)
    user = get_user_model().objects.create_user(username='other', email='other@example.com')
    UserProfile.objects.create(user=user, role='client')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    row = ProposalApprovalFile.objects.first()
    response = client.get(reverse('platform-approval-file-download', kwargs={'project_id': result['linked_project']['id'], 'file_id': row.pk}))
    assert response.status_code == 403


def test_private_file_download_returns_confirmed_bytes(reviewed_proposal, approval_client, admin_user):
    confirm(reviewed_proposal, approval_client, admin_user)
    row = ProposalApprovalFile.objects.get(source_key='custom-0')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(approval_client.user)}')
    response = client.get(reverse('platform-approval-file-download', kwargs={'project_id': row.project_id, 'file_id': row.pk}))
    assert response.status_code == 200
    assert b''.join(response.streaming_content) == b'%PDF-1.4 contract'
    assert response['Cache-Control'] == 'private, no-store'


def test_panel_multipart_confirm_uses_packet_metadata(admin_client, reviewed_proposal, approval_client):
    response = admin_client.post(reverse('proposal-approval', kwargs={'proposal_id': reviewed_proposal.pk}), {'payload': json.dumps(payload(reviewed_proposal, approval_client)), 'custom_files[]': pdf()}, format='multipart')
    assert response.status_code == 200
    assert response.json()['confirmed'] is True


@pytest.mark.parametrize('modality,expected', [('single', ['contract']), ('split', ['contract_product', 'contract_service'])])
def test_proposal_contract_mode_copies_only_active_contracts(reviewed_proposal, approval_client, admin_user, modality, expected):
    from content.services.contract_variants import FINAL_REQUIRED_PARAMS, SERVICE_PARAM_KEYS
    reviewed_proposal.status = 'accepted'
    reviewed_proposal.contract_modality = modality
    reviewed_proposal.contract_params = {key: 'Reviewed' for key in FINAL_REQUIRED_PARAMS + SERVICE_PARAM_KEYS}
    reviewed_proposal.contract_params['contractor_nit'] = '123456789'
    reviewed_proposal.save()
    single = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='contract', title='Combined', is_generated=True)
    single.file.save('single.pdf', ContentFile(b'%PDF-1.4 combined'))
    product = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='contract_product', title='Product', is_generated=True)
    product.file.save('product.pdf', ContentFile(b'%PDF-1.4 product'))
    service = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='contract_service', title='Service', is_generated=True)
    service.file.save('service.pdf', ContentFile(b'%PDF-1.4 service'))
    values = payload(reviewed_proposal, approval_client)
    values['use_proposal_contracts'] = True
    values['custom_documents'] = []
    result = review_proposal(reviewed_proposal.pk, values, actor=admin_user)
    assert sorted(row['document_type'] for row in result['confirmed_files'] if row['document_type'] in ProposalDocument.CONTRACT_DOC_TYPES) == expected
    assert ProposalDocument.objects.filter(proposal=reviewed_proposal).count() == 3


def test_original_optional_documents_require_explicit_selection(reviewed_proposal, approval_client, admin_user):
    doc = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='other', title='Private negotiation')
    doc.file.save('negotiation.pdf', ContentFile(b'%PDF-1.4 negotiation'))
    result = confirm(reviewed_proposal, approval_client, admin_user)
    assert 'Private negotiation' not in [row['title'] for row in result['confirmed_files']]
    assert doc.file.storage.exists(doc.file.name)


def test_private_file_corruption_is_not_served(reviewed_proposal, approval_client, admin_user):
    confirm(reviewed_proposal, approval_client, admin_user)
    row = ProposalApprovalFile.objects.get(source_key='custom-0')
    with row.file.storage.open(row.file.name, 'wb') as stream:
        stream.write(b'%PDF-1.4 changed')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(approval_client.user)}')
    response = client.get(reverse('platform-approval-file-download', kwargs={'project_id': row.project_id, 'file_id': row.pk}))
    assert response.status_code == 404


def test_public_detail_hides_project_identity(reviewed_proposal, approval_client, admin_user):
    from content.serializers.proposal import ProposalDetailSerializer
    confirm(reviewed_proposal, approval_client, admin_user)
    reviewed_proposal.refresh_from_db()
    public = ProposalDetailSerializer(reviewed_proposal).data
    assert 'linked_project' not in public
    assert 'platform_approval_manifest' not in public
    assert 'client' not in public


def test_confirmed_packet_blocks_project_deletion(reviewed_proposal, approval_client, admin_user):
    from content.services.project_deletion_service import deletion_preview
    result = confirm(reviewed_proposal, approval_client, admin_user)
    preview = deletion_preview(Project.objects.get(pk=result['linked_project']['id']))
    assert preview['can_delete'] is False
    assert any(row['count'] == 3 for row in preview['blockers'])


def test_changed_request_does_not_replace_confirmed_package(reviewed_proposal, approval_client, admin_user):
    from content.services.proposal_approval_service import ApprovalConflict
    values = payload(reviewed_proposal, approval_client)
    first = review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    with pytest.raises(ApprovalConflict):
        review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf(content=b'%PDF-1.4 replacement')])
    assert ProposalApprovalFile.objects.get(source_key='custom-0').sha256 == first['confirmed_files'][0]['sha256']


def test_missing_technical_detail_rolls_back_inline_creation(reviewed_proposal, admin_user):
    from rest_framework.exceptions import ValidationError
    reviewed_proposal.sections.all().delete()
    values = payload(reviewed_proposal, reviewed_proposal.client)
    values.pop('client_profile_id')
    values['new_client'] = {'name': 'Inline', 'email': 'rolledback@example.com'}
    with pytest.raises(ValidationError):
        review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    assert not UserProfile.objects.filter(user__email='rolledback@example.com').exists()
    assert not Project.objects.exists()


def test_legacy_launch_retry_keeps_confirmed_project(admin_client, reviewed_proposal, approval_client, admin_user):
    first = confirm(reviewed_proposal, approval_client, admin_user)
    project = Project.objects.get(pk=first['linked_project']['id'])
    project.description = 'Operational information'
    project.save(update_fields=['description'])
    response = admin_client.post(reverse('launch-to-platform', kwargs={'proposal_id': reviewed_proposal.pk}), {'action': 'retry'}, format='json')
    project.refresh_from_db()
    assert response.status_code == 200
    assert response.json()['linked_project'] == first['linked_project']
    assert response.json()['confirmed_files'] == first['confirmed_files']
    assert project.description == 'Operational information'


def test_commercial_pdf_uses_confirmed_client_identity(reviewed_proposal, admin_user):
    from io import BytesIO
    from pypdf import PdfReader
    values = payload(reviewed_proposal, reviewed_proposal.client)
    values.pop('client_profile_id')
    values['new_client'] = {'name': 'Inline Closure Customer', 'email': 'inline-closure@example.com'}
    greeting = ProposalSection.objects.create(proposal=reviewed_proposal, section_type='greeting', title='Greeting', content_json={'clientName': 'Wrong Previous Client'}, order=1)
    values['source_hash'] = source_hash(reviewed_proposal)
    review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    commercial = ProposalApprovalFile.objects.get(source_key='commercial')
    reader = PdfReader(BytesIO(commercial.file.read()))
    # The first PDF page is the shared branding cover; the next carries the client.
    assert 'Inline Closure Customer' in reader.pages[1].extract_text()
    assert 'Wrong Previous Client' not in reader.pages[1].extract_text()
    greeting.refresh_from_db()
    assert greeting.content_json == {'clientName': 'Wrong Previous Client'}


def test_inline_client_rejects_existing_admin_email(reviewed_proposal, admin_user):
    from rest_framework.exceptions import ValidationError
    values = payload(reviewed_proposal, reviewed_proposal.client)
    values.pop('client_profile_id')
    values['new_client'] = {'name': 'Wrong adoption', 'email': admin_user.email}
    with pytest.raises(ValidationError):
        review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    admin_user.refresh_from_db()
    assert admin_user.is_staff is True
    assert not UserProfile.objects.filter(user=admin_user, role='client').exists()
    assert not Project.objects.exists()


def test_confirmed_empty_selection_invalidates_review_source(reviewed_proposal, approval_client, admin_user):
    from content.models import ProposalChangeLog
    from content.services.proposal_approval_service import ApprovalConflict
    values = payload(reviewed_proposal, approval_client)
    ProposalChangeLog.objects.create(proposal=reviewed_proposal, change_type='calc_confirmed', actor_type='client', description='Client explicitly confirmed an empty selection.')
    with pytest.raises(ApprovalConflict) as caught:
        review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    assert caught.value.detail['code'] == 'stale_source'
    reviewed_proposal.refresh_from_db()
    assert reviewed_proposal.selected_modules == []
    assert reviewed_proposal.deliverable_id is None
    assert not Project.objects.exists()
