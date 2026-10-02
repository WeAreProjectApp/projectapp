"""Behavioral contract for internal approval without implicit provisioning."""
import json
from unittest.mock import patch
import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from freezegun import freeze_time
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
    detail_response = client.get(reverse('platform-deliverable-detail', kwargs={'project_id': row.project_id, 'deliverable_id': row.deliverable_id}))
    assert detail_response.status_code == 200
    assert [item['id'] for item in detail_response.json()['approval_files']] == list(ProposalApprovalFile.objects.filter(deliverable_id=row.deliverable_id).order_by('id').values_list('id', flat=True))
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


def test_inactive_canonical_client_confirmation_returns_current_workflow(reviewed_proposal, admin_user):
    from accounts.services.proposal_client_service import get_or_create_client_for_proposal, sync_snapshot
    profile = get_or_create_client_for_proposal(name='Canonical Customer', email='canonical@example.com')
    reviewed_proposal.client = profile
    reviewed_proposal.status = 'accepted'
    sync_snapshot(reviewed_proposal)
    reviewed_proposal.save()
    assert profile.user.is_active is False
    assert reviewed_proposal.platform_onboarding_completed_at is None
    users_before = get_user_model().objects.count()
    result = confirm(reviewed_proposal, profile, admin_user)
    reviewed_proposal.refresh_from_db()
    profile.user.refresh_from_db()
    assert reviewed_proposal.deliverable.project.client_id == profile.user_id
    assert (get_user_model().objects.count(), profile.user.is_active, profile.user.has_usable_password()) == (users_before, False, False)
    assert sorted(row['document_type'] for row in result['confirmed_files']) == ['commercial', 'contract', 'technical']
    assert result['proposal']['platform_onboarding_completed_at'] == reviewed_proposal.platform_onboarding_completed_at.isoformat()
    assert result['proposal']['available_transitions'] == reviewed_proposal.available_transitions == ['finished']


@pytest.mark.parametrize('ineligible', ['archived', 'staff'])
@freeze_time('2026-10-02T00:00:00Z')
def test_confirmation_rejects_ineligible_client_profiles(reviewed_proposal, approval_client, admin_user, ineligible):
    from django.utils import timezone
    from rest_framework.exceptions import ValidationError
    profile = {'archived': approval_client, 'staff': UserProfile.objects.get_or_create(user=admin_user, defaults={'role': 'admin'})[0]}[ineligible]
    archived_at = {'archived': timezone.now(), 'staff': None}[ineligible]
    profile.archived_at = archived_at
    profile.save(update_fields=['archived_at'])
    with pytest.raises(ValidationError):
        confirm(reviewed_proposal, profile, admin_user)
    assert not Project.objects.exists()
    assert not ProposalApprovalFile.objects.exists()


@pytest.mark.parametrize('field,value', [('hourly_rate', 35000), ('hours', 12), ('discount_percent', 15), ('name_es', 'Renamed package'), ('note_es', 'Revised scope note')])
def test_auto_commercial_catalog_change_invalidates_review(reviewed_proposal, admin_user, field, value):
    from content.models import HourPackage
    from content.services.proposal_approval_service import ApprovalConflict
    package = HourPackage.objects.create(nationality=reviewed_proposal.nationality, name_es='Selected package', name_en='Selected package', hours=10, hourly_rate=30000)
    ProposalSection.objects.create(proposal=reviewed_proposal, section_type='commercial_conditions', title='Conditions', content_json={'hourPackagesMode': 'auto'}, order=1)
    values = payload(reviewed_proposal, reviewed_proposal.client)
    values.pop('client_profile_id')
    values['new_client'] = {'name': 'Must not create', 'email': 'not-created@example.com'}
    users_before = get_user_model().objects.count()
    profiles_before = UserProfile.objects.count()
    setattr(package, field, value)
    package.save(update_fields=[field])
    with pytest.raises(ApprovalConflict) as caught:
        review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    assert caught.value.detail['code'] == 'stale_source'
    assert get_user_model().objects.count() == users_before
    assert UserProfile.objects.count() == profiles_before
    assert not Project.objects.exists()
    assert not ProposalApprovalFile.objects.exists()


def test_manual_commercial_catalog_change_preserves_pact(reviewed_proposal, approval_client, admin_user):
    from content.models import HourPackage
    package = HourPackage.objects.create(nationality=reviewed_proposal.nationality, name_es='Catalog package', name_en='Catalog package', hours=10, hourly_rate=30000)
    section = ProposalSection.objects.create(proposal=reviewed_proposal, section_type='commercial_conditions', title='Conditions', content_json={'hourPackagesMode': 'manual', 'currency': 'COP', 'hourlyRate': 12000, 'packages': [{'name': 'Agreed package', 'hours': 4, 'hourlyRate': 12000}]}, order=1)
    values = payload(reviewed_proposal, approval_client)
    package.hourly_rate = 99999
    package.save(update_fields=['hourly_rate'])
    result = review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])
    section.refresh_from_db()
    assert result['confirmed'] is True
    assert section.content_json['hourlyRate'] == 12000
    assert section.content_json['packages'][0]['hourlyRate'] == 12000
    from io import BytesIO
    from pypdf import PdfReader
    commercial = ProposalApprovalFile.objects.get(proposal=reviewed_proposal, document_type='commercial')
    with commercial.file.open('rb') as stream:
        rendered = ' '.join(page.extract_text() for page in PdfReader(BytesIO(stream.read())).pages)
    assert 'Agreed package' in rendered
    assert '12.000' in rendered
    assert '99.999' not in rendered



def _review_uploads(client, proposal, values, files):
    return client.post(
        reverse('proposal-approval', kwargs={'proposal_id': proposal.pk}),
        {'payload': json.dumps(values), 'custom_files[]': files},
        format='multipart',
    )


def _private_blob_names():
    from pathlib import Path
    storage = ProposalApprovalFile._meta.get_field('file').storage
    root = Path(storage.location)
    return sorted(str(path.relative_to(root)) for path in root.rglob('*') if path.is_file())


@pytest.fixture
def private_blob_baseline():
    return _private_blob_names()


def _assert_unconfirmed(proposal, blobs_before):
    proposal.refresh_from_db()
    assert (proposal.status, proposal.deliverable_id, proposal.platform_approval_manifest, proposal.platform_onboarding_status, proposal.platform_onboarding_completed_at) == ('negotiating', None, {}, None, None)
    assert ProposalApprovalFile.objects.count() == 0
    assert _private_blob_names() == blobs_before


def _invalid_docx_without_document():
    from io import BytesIO
    from zipfile import ZipFile
    content = BytesIO()
    with ZipFile(content, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('word/styles.xml', '<styles/>')
    return content.getvalue()


def test_confirmation_rejects_nonexistent_project(admin_client, reviewed_proposal, approval_client, private_blob_baseline):
    """Fails if selecting an absent project silently creates a replacement."""
    values = payload(reviewed_proposal, approval_client)
    values.pop('new_project')
    values['project_id'] = 999999

    response = _review_uploads(admin_client, reviewed_proposal, values, [pdf()])

    assert response.status_code == 400
    assert response.json() == {'project_id': 'Ese proyecto no existe.'}
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    assert reviewed_proposal.client_id == approval_client.pk
    assert Project.objects.count() == 0


def test_confirmation_rejects_foreign_client_project(admin_client, reviewed_proposal, approval_client, private_blob_baseline):
    """Fails if review adopts a different client's project or overwrites its finances."""
    owner = get_user_model().objects.create_user(username='foreign-project-owner', email='foreign-project@example.com')
    UserProfile.objects.create(user=owner, role='client')
    project = Project.objects.create(client=owner, name='Foreign operation', progress=67, payment_milestones=[{'amount': 910}], hosting_tiers=[{'months': 6}])
    values = payload(reviewed_proposal, approval_client)
    values.pop('new_project')
    values['project_id'] = project.pk

    response = _review_uploads(admin_client, reviewed_proposal, values, [pdf()])

    assert response.status_code == 400
    assert response.json() == {'project_id': 'El proyecto debe pertenecer al cliente seleccionado.'}
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    project.refresh_from_db()
    assert (project.client_id, project.name, project.progress, project.payment_milestones, project.hosting_tiers) == (owner.pk, 'Foreign operation', 67, [{'amount': 910}], [{'months': 6}])
    assert reviewed_proposal.client_id == approval_client.pk
    assert Project.objects.count() == 1


def test_confirmation_rejects_legacy_project_substitution(admin_client, reviewed_proposal, approval_client, admin_user):
    """Fails if a first packet review replaces its already linked operational project."""
    from accounts.models import DeliverableFile
    original = Project.objects.create(client=approval_client.user, name='Linked operation', progress=81, payment_milestones=[{'amount': 620}], hosting_tiers=[{'months': 9}])
    root = Deliverable.objects.create(project=original, category='documents', title='Retained documents', uploaded_by=admin_user)
    attachment = DeliverableFile.objects.create(deliverable=root, title='Legacy retained copy', uploaded_by=admin_user)
    attachment.file.save('retained-copy.pdf', ContentFile(b'%PDF-1.4 retained copy'))
    reviewed_proposal.deliverable = root
    reviewed_proposal.save(update_fields=['deliverable'])
    replacement = Project.objects.create(client=approval_client.user, name='Forbidden replacement')
    values = payload(reviewed_proposal, approval_client)
    values.pop('new_project')
    values['project_id'] = replacement.pk

    response = _review_uploads(admin_client, reviewed_proposal, values, [pdf()])

    assert response.status_code == 409
    assert response.json()['code'] == 'immutable_link'
    reviewed_proposal.refresh_from_db()
    original.refresh_from_db()
    attachment.refresh_from_db()
    assert (reviewed_proposal.deliverable_id, reviewed_proposal.client_id, reviewed_proposal.platform_approval_manifest) == (root.pk, approval_client.pk, {})
    assert (original.client_id, original.name, original.progress, original.payment_milestones, original.hosting_tiers) == (approval_client.user_id, 'Linked operation', 81, [{'amount': 620}], [{'months': 9}])
    assert attachment.file.read() == b'%PDF-1.4 retained copy'
    assert (DeliverableFile.objects.filter(deliverable=root).count(), ProposalApprovalFile.objects.count(), Project.objects.count()) == (1, 0, 2)


@pytest.mark.parametrize('selection', ['foreign-annex', 'contract'], ids=['foreign-annex', 'contract'])
def test_optional_selection_rejects_invalid_original(admin_client, reviewed_proposal, approval_client, selection, private_blob_baseline):
    """Fails if the optional selector can copy another proposal's annex or bypass the contract switch."""
    from content.models import BusinessProposal
    other = BusinessProposal.objects.create(title='Other proposal', client=approval_client)
    proposals = {'foreign-annex': other, 'contract': reviewed_proposal}
    types = {'foreign-annex': 'legal_annex', 'contract': 'contract'}
    original = ProposalDocument.objects.create(proposal=proposals[selection], document_type=types[selection], title='Retained source')
    original.file.save('selected-original.pdf', ContentFile(b'%PDF-1.4 original evidence'))
    values = payload(reviewed_proposal, approval_client)
    values['selected_document_ids'] = [original.pk]

    response = _review_uploads(admin_client, reviewed_proposal, values, [pdf()])

    assert response.status_code == 400
    assert response.json() == {'selected_document_ids': 'Selecciona únicamente anexos de esta propuesta; los contratos usan el switch principal.'}
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    original.refresh_from_db()
    assert original.file.read() == b'%PDF-1.4 original evidence'
    assert original.proposal_id == proposals[selection].pk
    assert Project.objects.count() == 0


def test_missing_optional_blob_rejects_confirmation(admin_client, reviewed_proposal, approval_client, private_blob_baseline):
    """Fails if an already missing optional blob is treated as a valid reviewable attachment."""
    original = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='legal_annex', title='Missing legal annex')
    original.file.save('missing-legal-annex.pdf', ContentFile(b'%PDF-1.4 retained legal annex'))
    original_name = original.file.name
    assert original.file.read() == b'%PDF-1.4 retained legal annex'
    original.file.storage.delete(original_name)
    assert original.file.storage.exists(original_name) is False
    preview_response = admin_client.get(reverse('proposal-approval', kwargs={'proposal_id': reviewed_proposal.pk}))
    assert (preview_response.status_code, preview_response.json()['optional_documents']) == (200, [{'id': original.pk, 'title': 'Missing legal annex', 'document_type': 'legal_annex'}])
    values = payload(reviewed_proposal, approval_client)
    values['source_hash'] = preview_response.json()['source_hash']
    values['selected_document_ids'] = [original.pk]

    response = _review_uploads(admin_client, reviewed_proposal, values, [pdf()])

    assert (response.status_code, response.json()) == (400, {'files': 'No se pudo leer uno de los archivos.'})
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    original.refresh_from_db()
    assert (original.file.name, original.file.storage.exists(original_name), source_hash(reviewed_proposal)) == (original_name, False, preview_response.json()['source_hash'])
    assert ProposalDocument.objects.filter(pk=original.pk).count() == 1
    assert Project.objects.count() == 0


def test_missing_private_blob_download_preserves_receipt(reviewed_proposal, approval_client, admin_user, private_blob_baseline):
    """Fails if a missing confirmed blob returns success or destroys its retained receipt/link."""
    confirm(reviewed_proposal, approval_client, admin_user)
    row = ProposalApprovalFile.objects.get(source_key='custom-0')
    retained = (row.pk, row.sha256, row.size, row.file.name, row.project_id, row.deliverable_id)
    row.file.storage.delete(row.file.name)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(approval_client.user)}')

    response = client.get(reverse('platform-approval-file-download', kwargs={'project_id': row.project_id, 'file_id': row.pk}))

    assert response.status_code == 404
    assert response.json() == {'detail': 'El archivo no está disponible.'}
    row.refresh_from_db()
    reviewed_proposal.refresh_from_db()
    assert (row.pk, row.sha256, row.size, row.file.name, row.project_id, row.deliverable_id) == retained
    assert reviewed_proposal.deliverable_id == row.deliverable_id
    assert reviewed_proposal.platform_approval_manifest['project_id'] == row.project_id
    assert ProposalApprovalFile.objects.count() == 3
    assert len(_private_blob_names()) == len(private_blob_baseline) + 2


def test_archived_deliverable_hides_private_packet(reviewed_proposal, approval_client, admin_user, private_blob_baseline):
    """Fails if clients can download an archived root's retained private packet."""
    confirm(reviewed_proposal, approval_client, admin_user)
    row = ProposalApprovalFile.objects.get(source_key='custom-0')
    root = row.deliverable
    root.is_archived = True
    root.save(update_fields=['is_archived'])
    retained = (row.sha256, row.size, row.project_id, row.deliverable_id)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(approval_client.user)}')

    response = client.get(reverse('platform-approval-file-download', kwargs={'project_id': row.project_id, 'file_id': row.pk}))

    assert response.status_code == 404
    assert response.json() == {'detail': 'El archivo no está disponible.'}
    row.refresh_from_db()
    reviewed_proposal.refresh_from_db()
    assert (row.sha256, row.size, row.project_id, row.deliverable_id) == retained
    assert row.file.read() == b'%PDF-1.4 contract'
    assert reviewed_proposal.deliverable_id == root.pk
    assert ProposalApprovalFile.objects.count() == 3
    assert len(_private_blob_names()) == len(private_blob_baseline) + 3


def test_second_private_write_failure_rolls_back_confirmation(reviewed_proposal, approval_client, admin_user, private_blob_baseline):
    """Fails if storage failure after one real write leaks a blob or partially provisions the review."""
    storage = ProposalApprovalFile._meta.get_field('file').storage
    real_save = storage.save
    writes = {}

    def save_first(name, content, max_length=None):
        stored = real_save(name, content, max_length=max_length)
        writes['name'] = stored
        with storage.open(stored, 'rb') as stream:
            writes['bytes'] = stream.read()
        return stored

    def fail_second(name, content, max_length=None):
        raise OSError('private write unavailable')

    actions = iter((save_first, fail_second))

    def save_boundary(name, content, max_length=None):
        return next(actions)(name, content, max_length=max_length)

    values = payload(reviewed_proposal, approval_client)
    values.pop('client_profile_id')
    values['new_client'] = {'name': 'Rollback customer', 'email': 'rollback-customer@example.com'}
    users_before = get_user_model().objects.count()
    profiles_before = UserProfile.objects.count()
    original = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='legal_annex', title='Source retained')
    original.file.save('rollback-source.pdf', ContentFile(b'%PDF-1.4 source retained'))
    values['source_hash'] = source_hash(reviewed_proposal)

    with patch.object(storage, 'save', side_effect=save_boundary):
        with pytest.raises(OSError, match='private write unavailable'):
            review_proposal(reviewed_proposal.pk, values, actor=admin_user, files=[pdf()])

    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    assert writes['bytes'] == b'%PDF-1.4 contract'
    assert storage.exists(writes['name']) is False
    assert (get_user_model().objects.count(), UserProfile.objects.count(), reviewed_proposal.client_id) == (users_before, profiles_before, approval_client.pk)
    assert (Project.objects.count(), Deliverable.objects.count()) == (0, 0)
    original.refresh_from_db()
    assert original.file.read() == b'%PDF-1.4 source retained'


@pytest.mark.parametrize('content', [b'PK\x03\x04corrupt', _invalid_docx_without_document()], ids=['corrupt-zip', 'missing-document'])
def test_invalid_docx_rejects_confirmation(admin_client, reviewed_proposal, approval_client, content, private_blob_baseline):
    """Fails if PK-prefixed garbage or a ZIP lacking the Word document can become a confirmed contract."""
    upload = SimpleUploadedFile('invalid.docx', content, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    values = payload(reviewed_proposal, approval_client)

    response = _review_uploads(admin_client, reviewed_proposal, values, [upload])

    assert response.status_code == 400
    assert response.json() == {'custom_files': 'El documento Office no es válido.'}
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    assert Project.objects.count() == 0


def test_oversized_packet_rejects_confirmation(admin_client, reviewed_proposal, approval_client, private_blob_baseline):
    """Fails if individually allowed uploads can exceed the aggregate 36 MB packet limit."""
    content = b'%PDF-1.4\n' + b'x' * (13 * 1024 * 1024 - len(b'%PDF-1.4\n'))
    uploads = [pdf('contract.pdf', content), pdf('annex.pdf', content), pdf('amendment.pdf', content)]
    values = payload(reviewed_proposal, approval_client)
    values.pop('client_profile_id')
    values['new_client'] = {'name': 'Oversized rollback', 'email': 'oversized-rollback@example.com'}
    values['custom_documents'] = [{'title': 'Contract', 'document_type': 'contract'}, {'title': 'Annex', 'document_type': 'legal_annex'}, {'title': 'Amendment', 'document_type': 'amendment'}]
    users_before = get_user_model().objects.count()
    profiles_before = UserProfile.objects.count()
    assert tuple(upload.size for upload in uploads) == (13 * 1024 * 1024,) * 3

    response = _review_uploads(admin_client, reviewed_proposal, values, uploads)

    assert response.status_code == 400
    assert response.json() == {'files': 'El paquete supera el máximo de 36 MB.'}
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    assert get_user_model().objects.count() == users_before
    assert UserProfile.objects.count() == profiles_before
    assert reviewed_proposal.client_id == approval_client.pk
    assert Project.objects.count() == 0


def test_retry_before_confirmation_requires_review(admin_client, reviewed_proposal, approval_client, private_blob_baseline):
    """Fails if retry can provision an unreviewed proposal or mark it completed."""
    response = admin_client.post(reverse('proposal-approval', kwargs={'proposal_id': reviewed_proposal.pk}), {'action': 'retry'}, format='json')

    assert response.status_code == 409
    assert response.json()['code'] == 'review_required'
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    assert reviewed_proposal.client_id == approval_client.pk
    assert reviewed_proposal.platform_onboarding_status is None
    assert Project.objects.count() == 0


@pytest.mark.parametrize('selection', ['client', 'project'], ids=['client', 'project'])
def test_confirmation_rejects_ambiguous_selection(admin_client, reviewed_proposal, approval_client, selection, private_blob_baseline):
    """Fails if simultaneous existing/new selection is accepted instead of a field error."""
    project = Project.objects.create(client=approval_client.user, name='Keep existing project')
    values = payload(reviewed_proposal, approval_client)
    additions = {'client': {'new_client': {'name': 'Do not create', 'email': 'ambiguous@example.com'}}, 'project': {'project_id': project.pk}}
    fields = {'client': 'client_profile_id', 'project': 'project_id'}
    messages = {'client': 'Selecciona un cliente o crea uno nuevo.', 'project': 'Selecciona un proyecto o crea uno nuevo.'}
    values.update(additions[selection])
    users_before = get_user_model().objects.count()

    response = _review_uploads(admin_client, reviewed_proposal, values, [pdf()])

    assert response.status_code == 400
    assert response.json() == {fields[selection]: [messages[selection]]}
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    assert get_user_model().objects.count() == users_before
    project.refresh_from_db()
    assert (project.client_id, project.name) == (approval_client.user_id, 'Keep existing project')
    assert Project.objects.count() == 1


def test_defer_rejects_uploaded_document(admin_client, reviewed_proposal, approval_client, private_blob_baseline):
    """Fails if uploading during deferral accepts the proposal before rejecting its file."""
    response = _review_uploads(admin_client, reviewed_proposal, {'action': 'defer'}, [pdf()])

    assert response.status_code == 400
    assert response.json() == {'custom_files': 'Posponer no guarda adjuntos.'}
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    assert reviewed_proposal.client_id == approval_client.pk
    assert Project.objects.count() == 0


def test_original_contract_switch_rejects_custom_upload(admin_client, reviewed_proposal, approval_client, private_blob_baseline):
    """Fails if the original-contract switch allows an additional custom contract packet."""
    original = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='contract', title='Retained original contract', is_generated=True)
    original.file.save('retained-original-contract.pdf', ContentFile(b'%PDF-1.4 original contract'))
    original_name = original.file.name
    values = payload(reviewed_proposal, approval_client)
    values['use_proposal_contracts'] = True

    response = _review_uploads(admin_client, reviewed_proposal, values, [pdf()])

    assert response.status_code == 400
    assert response.json() == {'custom_files': 'Desactiva los contratos de la propuesta para adjuntar documentos personalizados.'}
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    assert Project.objects.count() == 0

    original.refresh_from_db()
    assert (original.file.name, original.proposal_id) == (original_name, reviewed_proposal.pk)
    assert original.file.read() == b'%PDF-1.4 original contract'
    assert reviewed_proposal.client_id == approval_client.pk


def test_disallowed_extension_rejects_confirmation(admin_client, reviewed_proposal, approval_client, private_blob_baseline):
    """Fails if a forbidden filename extension enters the durable approval packet."""
    original = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='contract', title='Retained original contract', is_generated=True)
    original.file.save('retained-original-contract.pdf', ContentFile(b'%PDF-1.4 original contract'))
    original_name = original.file.name
    values = payload(reviewed_proposal, approval_client)

    response = _review_uploads(admin_client, reviewed_proposal, values, [pdf('contract.exe')])

    assert response.status_code == 400
    assert response.json() == {'custom_files': 'Formato no permitido. Usa PDF, Word, Excel o imágenes.'}
    _assert_unconfirmed(reviewed_proposal, private_blob_baseline)
    assert Project.objects.count() == 0

    original.refresh_from_db()
    assert (original.file.name, original.proposal_id) == (original_name, reviewed_proposal.pk)
    assert original.file.read() == b'%PDF-1.4 original contract'
    assert reviewed_proposal.client_id == approval_client.pk
