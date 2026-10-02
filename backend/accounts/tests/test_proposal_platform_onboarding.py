"""Compatibility guards for internal review and preservation of platform evidence."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from accounts.models import Deliverable, Project, ProjectIdea, UserProfile
from accounts.services.proposal_platform_onboarding import (
    _acting_user_for_sync,
    _find_client_user_by_email,
    _sync_proposal_documents_to_deliverable,
    ensure_deliverable_for_accepted_proposal,
    handle_proposal_accepted_for_platform,
    teardown_platform_for_proposal,
)
from accounts.services.technical_resources_sync import (
    sync_technical_resources_for_deliverable,
)
from content.models import BusinessProposal, IncomeRecord, ProposalSection

User = get_user_model()


@pytest.fixture
def admin_user(db):
    u = User.objects.create_user(
        username='admin-onb@test.com',
        email='admin-onb@test.com',
        password='pass',
        is_staff=True,
    )
    UserProfile.objects.create(user=u, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return u


@pytest.fixture
def client_user(db):
    u = User.objects.create_user(
        username='client-onb@test.com',
        email='client-onb@test.com',
        password='pass',
    )
    UserProfile.objects.create(user=u, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    return u


@pytest.fixture
def proposal_with_deliverable(db, client_user, admin_user):
    proj = Project.objects.create(name='P1', client=client_user)
    d = Deliverable.objects.create(
        project=proj,
        category=Deliverable.CATEGORY_DOCUMENTS,
        title='Entrega',
        uploaded_by=admin_user,
    )
    bp = BusinessProposal.objects.create(
        title='Prop',
        client_name='Test Client',
        client_email='client-onb@test.com',
        status=BusinessProposal.Status.ACCEPTED,
        deliverable=d,
    )
    ProposalSection.objects.create(
        proposal=bp,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
        title='Técnico',
        is_enabled=True,
        order=1,
        content_json={
            'epics': [
                {
                    'epicKey': 'e1',
                    'title': 'Epic One',
                    'requirements': [
                        {
                            'flowKey': 'f1',
                            'title': 'Req 1',
                            'description': '',
                            'configuration': '',
                            'usageFlow': 'flow',
                        },
                    ],
                },
            ],
        },
    )
    return bp


@pytest.mark.django_db
def test_handle_proposal_accepted_skips_when_already_completed(proposal_with_deliverable, admin_user):
    proposal_with_deliverable.platform_onboarding_completed_at = timezone.now()
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])

    out = handle_proposal_accepted_for_platform(
        proposal_with_deliverable, source='admin_panel', acting_user=admin_user,
    )
    assert out['skipped'] is True


@pytest.mark.django_db
def test_proposal_sync_creates_resources_without_delivery_reviews(proposal_with_deliverable, admin_user):
    from accounts.models import Requirement
    d = proposal_with_deliverable.deliverable

    result = sync_technical_resources_for_deliverable(d, admin_user)

    assert result['deliverables_created'] >= 1
    assert not Requirement.objects.exists()


@pytest.mark.django_db
def test_relaunch_keeps_a_project_with_contractual_delivery(proposal_with_deliverable):
    from accounts.tests._delivery_fixtures import make_delivery_stage
    from rest_framework.exceptions import ValidationError
    project = proposal_with_deliverable.deliverable.project
    stage = make_delivery_stage(project)

    with pytest.raises(ValidationError):
        teardown_platform_for_proposal(proposal_with_deliverable)

    proposal_with_deliverable.refresh_from_db()
    assert proposal_with_deliverable.deliverable_id is not None
    assert Project.objects.filter(pk=project.pk).exists()
    assert stage.phase.scope.contract.scopes.exists()


@pytest.mark.django_db
@patch(
    'content.services.proposal_email_service.ProposalEmailService.send_acceptance_confirmation',
    return_value=True,
)
def test_legacy_link_requires_review_before_sync(
    _mock_send, proposal_with_deliverable, admin_user,
):
    proposal_with_deliverable.platform_onboarding_completed_at = None
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])

    handle_proposal_accepted_for_platform(
        proposal_with_deliverable, source='admin_panel', acting_user=admin_user,
    )
    proposal_with_deliverable.refresh_from_db()
    assert proposal_with_deliverable.platform_onboarding_completed_at is None


@pytest.mark.django_db
def test_acceptance_preserves_original_document_locations_without_review(
    proposal_with_deliverable, admin_user,
):
    proposal_with_deliverable.platform_onboarding_completed_at = None
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])

    with (
        patch(
            'content.services.generated_document_filing_service.move_proposal_snapshots_to_project',
        ) as move_snapshots,
        patch(
            'accounts.services.proposal_platform_onboarding.sync_technical_resources_for_deliverable',
            return_value={'ok': True, 'detail': 'synced'},
        ),
        patch(
            'content.services.proposal_email_service.ProposalEmailService.send_acceptance_confirmation',
            return_value=True,
        ),
    ):
        handle_proposal_accepted_for_platform(
            proposal_with_deliverable,
            source='admin_panel',
            acting_user=admin_user,
        )

    move_snapshots.assert_not_called()
    assert not proposal_with_deliverable.platform_approval_manifest


# -- _acting_user_for_sync helpers -------------------------------------------


@pytest.mark.django_db
def test_acting_user_for_sync_returns_staff_user_when_acting_user_is_none(admin_user):
    """Falls back to staff user when acting_user is None."""
    result = _acting_user_for_sync(None)
    assert result is not None
    assert result.is_staff is True


@pytest.mark.django_db
def test_acting_user_for_sync_returns_provided_user_when_authenticated(admin_user):
    """Returns the acting_user directly when it is authenticated."""
    result = _acting_user_for_sync(admin_user)
    assert result == admin_user


# -- _find_client_user_by_email helpers --------------------------------------


@pytest.mark.django_db
def test_find_client_user_by_email_returns_none_for_empty_string():
    """Empty email string returns None without querying the DB."""
    result = _find_client_user_by_email('')
    assert result is None


@pytest.mark.django_db
def test_find_client_user_by_email_returns_none_for_whitespace():
    """Email consisting only of spaces returns None."""
    result = _find_client_user_by_email('   ')
    assert result is None


@pytest.mark.django_db
def test_find_client_user_by_email_returns_matching_user(client_user):
    """Returns the user when the email matches an existing account."""
    result = _find_client_user_by_email('client-onb@test.com')
    assert result is not None
    assert result.email == 'client-onb@test.com'


# -- ensure_deliverable_for_accepted_proposal --------------------------------


@pytest.mark.django_db
def test_ensure_deliverable_returns_existing_deliverable_when_set(proposal_with_deliverable):
    """Returns the deliverable directly when proposal.deliverable_id is already set."""
    result = ensure_deliverable_for_accepted_proposal(proposal_with_deliverable, None)
    assert result == proposal_with_deliverable.deliverable


@pytest.mark.django_db
def test_ensure_deliverable_returns_none_when_no_client_user_exists(admin_user):
    """Returns None when email is unknown (no matching user)."""
    proposal = BusinessProposal.objects.create(
        title='NoBP',
        client_name='Unknown',
        client_email='nobody@nowhere.invalid',
        status=BusinessProposal.Status.ACCEPTED,
    )
    result = ensure_deliverable_for_accepted_proposal(proposal, admin_user)
    assert result is None


@pytest.mark.django_db
def test_ensure_deliverable_returns_none_when_user_is_not_client(admin_user):
    """Returns None when matched user has a non-CLIENT role."""
    proposal = BusinessProposal.objects.create(
        title='AdminBP',
        client_name='Admin',
        client_email='admin-onb@test.com',
        status=BusinessProposal.Status.ACCEPTED,
    )
    result = ensure_deliverable_for_accepted_proposal(proposal, admin_user)
    assert result is None


@pytest.mark.django_db
@patch('accounts.views._extract_proposal_financial_data', return_value=([], []))
def test_acceptance_does_not_create_project_for_existing_client(
    _mock_extract, client_user, admin_user,
):
    """An existing client email never implicitly authorizes project creation."""
    proposal = BusinessProposal.objects.create(
        title='New Project BP',
        client_name='Test Client',
        client_email='client-onb@test.com',
        total_investment=Decimal('0'),
        hosting_percent=30,
        status=BusinessProposal.Status.ACCEPTED,
    )

    result = ensure_deliverable_for_accepted_proposal(proposal, admin_user)

    assert result is None
    assert not Project.objects.filter(client=client_user).exists()
    proposal.refresh_from_db()
    assert proposal.deliverable_id is None


# -- handle_proposal_accepted_for_platform edge cases -----------------------


@pytest.mark.django_db
@patch('content.services.proposal_email_service.ProposalEmailService.send_acceptance_confirmation', return_value=True)
@patch('accounts.services.proposal_platform_onboarding.sync_technical_resources_for_deliverable')
def test_unreviewed_acceptance_skips_resource_sync(_mock_sync, _mock_email, proposal_with_deliverable, admin_user):
    """An unreviewed proposal never invokes the resource synchronization path."""
    _mock_sync.return_value = {'ok': False, 'error': 'no_technical_section', 'detail': 'No section'}
    proposal_with_deliverable.platform_onboarding_completed_at = None
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])

    result = handle_proposal_accepted_for_platform(
        proposal_with_deliverable, source='admin_panel', acting_user=admin_user,
    )

    assert result == {'skipped': True, 'reason': 'review_required'}
    _mock_sync.assert_not_called()


# -- _ensure_project_stages -------------------------------------------------


@pytest.mark.django_db
@patch('content.services.proposal_email_service.ProposalEmailService.send_acceptance_confirmation', return_value=True)
@patch('accounts.services.proposal_platform_onboarding.sync_technical_resources_for_deliverable')
def test_unreviewed_acceptance_does_not_create_internal_stages(
    _mock_sync, _mock_email, proposal_with_deliverable, admin_user,
):
    """Unreviewed acceptance leaves internal stage tracking untouched."""
    from content.models import ProposalProjectStage

    _mock_sync.return_value = {'ok': True, 'detail': 'synced'}
    proposal_with_deliverable.platform_onboarding_completed_at = None
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])

    handle_proposal_accepted_for_platform(
        proposal_with_deliverable, source='admin_panel', acting_user=admin_user,
    )

    stages = ProposalProjectStage.objects.filter(proposal=proposal_with_deliverable)
    assert stages.count() == 0


@pytest.mark.django_db
@patch('content.services.proposal_email_service.ProposalEmailService.send_acceptance_confirmation', return_value=True)
@patch('accounts.services.proposal_platform_onboarding.sync_technical_resources_for_deliverable')
def test_repeated_unreviewed_acceptance_leaves_internal_stages_empty(
    _mock_sync, _mock_email, proposal_with_deliverable, admin_user,
):
    """Repeated unreviewed acceptance cannot initialize internal execution stages."""
    from content.models import ProposalProjectStage

    _mock_sync.return_value = {'ok': True, 'detail': 'synced'}
    proposal_with_deliverable.platform_onboarding_completed_at = None
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])

    handle_proposal_accepted_for_platform(
        proposal_with_deliverable, source='admin_panel', acting_user=admin_user,
    )
    # Pretend the proposal got re-processed by manually clearing the timestamp
    proposal_with_deliverable.platform_onboarding_completed_at = None
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])
    handle_proposal_accepted_for_platform(
        proposal_with_deliverable, source='admin_panel', acting_user=admin_user,
    )

    assert ProposalProjectStage.objects.filter(
        proposal=proposal_with_deliverable,
    ).count() == 0


# -- teardown_platform_for_proposal ------------------------------------------


@pytest.mark.django_db
def test_teardown_returns_early_when_no_deliverable_id():
    proposal = BusinessProposal.objects.create(
        title='TeardownNoDel',
        client_name='Client',
        status=BusinessProposal.Status.ACCEPTED,
    )
    teardown_platform_for_proposal(proposal)
    proposal.refresh_from_db()
    assert proposal.deliverable_id is None


@pytest.mark.django_db
def test_teardown_deletes_project_and_clears_deliverable_id(proposal_with_deliverable):
    project_pk = proposal_with_deliverable.deliverable.project_id
    teardown_platform_for_proposal(proposal_with_deliverable)
    proposal_with_deliverable.refresh_from_db()
    assert proposal_with_deliverable.deliverable_id is None
    assert not Project.objects.filter(pk=project_pk).exists()


@pytest.mark.django_db
def test_teardown_clears_platform_onboarding_completed_at(proposal_with_deliverable):
    proposal_with_deliverable.platform_onboarding_completed_at = timezone.now()
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])

    teardown_platform_for_proposal(proposal_with_deliverable)

    proposal_with_deliverable.refresh_from_db()
    assert proposal_with_deliverable.platform_onboarding_completed_at is None


@pytest.mark.django_db
def test_teardown_blocks_archived_project_idea_without_unlinking_proposal(
    proposal_with_deliverable, admin_user,
):
    """Fails if archived client ideas allow a relaunch to delete Platform evidence."""
    from rest_framework.exceptions import ValidationError
    from accounts.services.proposal_platform_onboarding import PlatformRelaunchConflict

    proposal = proposal_with_deliverable
    project = proposal.deliverable.project
    deliverable_id = proposal.deliverable_id
    completed_at = timezone.now()
    proposal.platform_onboarding_completed_at = completed_at
    proposal.save(update_fields=['platform_onboarding_completed_at'])
    idea = ProjectIdea.objects.create(
        project=project, author=admin_user, author_label='Equipo', origin='team',
        text='Conservar esta idea archivada.', archived_at=completed_at,
        archived_by=admin_user,
    )

    with pytest.raises(PlatformRelaunchConflict) as caught:
        teardown_platform_for_proposal(proposal)

    proposal.refresh_from_db()
    idea.refresh_from_db()
    assert isinstance(caught.value, ValidationError)
    assert caught.value.status_code == 409
    assert (
        Project.objects.filter(pk=project.pk).exists(), idea.project_id,
        idea.archived_at, proposal.deliverable_id,
        proposal.platform_onboarding_completed_at,
    ) == (True, project.pk, completed_at, deliverable_id, completed_at)


@pytest.mark.django_db
def test_teardown_blocks_project_income_without_nulling_its_foreign_key(
    proposal_with_deliverable,
):
    """Fails if relaunch deletes a project and turns linked accounting income into SET_NULL."""
    from accounts.services.proposal_platform_onboarding import PlatformRelaunchConflict

    proposal = proposal_with_deliverable
    project = proposal.deliverable.project
    deliverable_id = proposal.deliverable_id
    completed_at = timezone.now()
    proposal.platform_onboarding_completed_at = completed_at
    proposal.save(update_fields=['platform_onboarding_completed_at'])
    income = IncomeRecord.objects.create(
        project=project, client=project.client.profile, concept='Development',
        period_date='2026-10-02', total_amount=Decimal('100000'),
        gustavo_amount=Decimal('50000'), carlos_amount=Decimal('50000'),
    )

    with pytest.raises(PlatformRelaunchConflict):
        teardown_platform_for_proposal(proposal)

    proposal.refresh_from_db()
    income.refresh_from_db()
    assert (
        Project.objects.filter(pk=project.pk).exists(), income.project_id,
        proposal.deliverable_id, proposal.platform_onboarding_completed_at,
    ) == (True, project.pk, deliverable_id, completed_at)


# -- _sync_proposal_documents_to_deliverable ---------------------------------


@pytest.mark.django_db
@patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'')
@patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=b'')
def test_sync_documents_skips_deliverable_file_when_pdf_returns_empty_bytes(
    _mock_tech, _mock_gen, proposal_with_deliverable, admin_user,
):
    from accounts.models import DeliverableFile

    d = proposal_with_deliverable.deliverable
    before = DeliverableFile.objects.filter(deliverable=d).count()
    _sync_proposal_documents_to_deliverable(proposal_with_deliverable, d, admin_user)
    after = DeliverableFile.objects.filter(deliverable=d).count()
    assert after == before


@pytest.mark.django_db
@patch(
    'content.services.proposal_pdf_service.ProposalPdfService.generate',
    side_effect=Exception('pdf fail'),
)
@patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=None)
def test_sync_documents_does_not_raise_when_proposal_pdf_generation_fails(
    _mock_tech, _mock_gen, proposal_with_deliverable, admin_user,
):
    """Catches: a half-written deliverable. Asserting only that the call does not
    raise would also pass if it swallowed the failure AFTER attaching a file, so
    the count is what proves the failed PDF left nothing behind."""
    from accounts.models import DeliverableFile

    d = proposal_with_deliverable.deliverable
    before = DeliverableFile.objects.filter(deliverable=d).count()

    _sync_proposal_documents_to_deliverable(proposal_with_deliverable, d, admin_user)

    assert DeliverableFile.objects.filter(deliverable=d).count() == before


@pytest.mark.django_db
@patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=None)
@patch(
    'content.services.technical_document_pdf.generate_technical_document_pdf',
    side_effect=Exception('tech fail'),
)
def test_sync_documents_does_not_raise_when_technical_pdf_generation_fails(
    _mock_tech, _mock_gen, proposal_with_deliverable, admin_user,
):
    """Catches: a half-written deliverable. Asserting only that the call does not
    raise would also pass if it swallowed the failure AFTER attaching a file, so
    the count is what proves the failed PDF left nothing behind."""
    from accounts.models import DeliverableFile

    d = proposal_with_deliverable.deliverable
    before = DeliverableFile.objects.filter(deliverable=d).count()

    _sync_proposal_documents_to_deliverable(proposal_with_deliverable, d, admin_user)

    assert DeliverableFile.objects.filter(deliverable=d).count() == before


@pytest.mark.django_db
@patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=None)
@patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=None)
def test_sync_documents_copies_only_the_contracts_of_the_chosen_modality(
    _mock_tech, _mock_gen, proposal_with_deliverable, admin_user,
):
    """Fails if a split closing hands the client the stale single contract as well."""
    from content.models import ProposalDocument
    from django.core.files.base import ContentFile

    from accounts.models import DeliverableFile

    proposal_with_deliverable.contract_modality = 'split'
    proposal_with_deliverable.save(update_fields=['contract_modality'])
    for doc_type in ('contract', 'contract_product', 'contract_service'):
        doc = ProposalDocument.objects.create(
            proposal=proposal_with_deliverable, document_type=doc_type, title=doc_type, is_generated=True,
        )
        doc.file.save(f'{doc_type}.pdf', ContentFile(b'%PDF-1.4'), save=True)
    d = proposal_with_deliverable.deliverable

    _sync_proposal_documents_to_deliverable(proposal_with_deliverable, d, admin_user)

    copied = DeliverableFile.objects.filter(deliverable=d)
    assert sorted(copied.values_list('title', flat=True)) == ['contract_product', 'contract_service']
    assert set(copied.values_list('category', flat=True)) == {Deliverable.CATEGORY_CONTRACT}


@pytest.mark.django_db
@patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=None)
@patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=None)
def test_sync_documents_copies_the_single_contract_by_default(
    mock_tech, mock_gen, proposal_with_deliverable, admin_user,
):
    """Fails if the single contract every non-split proposal has stops reaching the deliverable."""
    from content.models import ProposalDocument
    from django.core.files.base import ContentFile

    from accounts.models import DeliverableFile

    doc = ProposalDocument.objects.create(
        proposal=proposal_with_deliverable, document_type='contract', title='contract', is_generated=True,
    )
    doc.file.save('contract.pdf', ContentFile(b'%PDF-1.4'), save=True)
    d = proposal_with_deliverable.deliverable

    _sync_proposal_documents_to_deliverable(proposal_with_deliverable, d, admin_user)

    copied = DeliverableFile.objects.filter(deliverable=d)
    assert copied.count() == 1
    assert copied.first().category == Deliverable.CATEGORY_CONTRACT


# -- ensure_deliverable edge cases -------------------------------------------


@pytest.mark.django_db
@override_settings(AUTO_PROVISION_CLIENT_FROM_PROPOSAL=True)
@patch('accounts.services.onboarding.create_client', side_effect=ValueError('Duplicate email'))
def test_ensure_deliverable_logs_and_continues_when_create_client_raises_value_error(
    _mock_create, admin_user,
):
    proposal = BusinessProposal.objects.create(
        title='AutoProv',
        client_name='Auto Client',
        client_email='nobody-autoprov@nowhere.invalid',
        status=BusinessProposal.Status.ACCEPTED,
    )
    result = ensure_deliverable_for_accepted_proposal(proposal, admin_user)
    assert result is None


@pytest.mark.django_db
def test_ensure_deliverable_returns_none_when_user_has_no_profile():
    u = User.objects.create_user(
        username='noprofile-onb@test.com',
        email='noprofile-onb@test.com',
        password='pass',
    )
    proposal = BusinessProposal.objects.create(
        title='NoProfile',
        client_name='No Profile',
        client_email='noprofile-onb@test.com',
        status=BusinessProposal.Status.ACCEPTED,
    )
    result = ensure_deliverable_for_accepted_proposal(proposal, None)
    assert result is None


# -- handle_proposal_accepted_for_platform with send_email=False -------------


@pytest.mark.django_db
@patch('accounts.services.proposal_platform_onboarding.sync_technical_resources_for_deliverable')
def test_unreviewed_acceptance_does_not_mark_completed(
    _mock_sync, proposal_with_deliverable, admin_user,
):
    _mock_sync.return_value = {'ok': True, 'detail': 'synced'}
    proposal_with_deliverable.platform_onboarding_completed_at = None
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])

    handle_proposal_accepted_for_platform(
        proposal_with_deliverable, source='admin_panel', acting_user=admin_user, send_email=False,
    )

    proposal_with_deliverable.refresh_from_db()
    assert proposal_with_deliverable.platform_onboarding_completed_at is None


@pytest.mark.django_db
@patch('accounts.services.proposal_platform_onboarding.sync_technical_resources_for_deliverable')
def test_unreviewed_acceptance_stays_pending_for_review(
    _mock_sync, proposal_with_deliverable, admin_user,
):
    _mock_sync.return_value = {'ok': True, 'detail': 'synced'}
    proposal_with_deliverable.platform_onboarding_completed_at = None
    proposal_with_deliverable.save(update_fields=['platform_onboarding_completed_at'])

    result = handle_proposal_accepted_for_platform(
        proposal_with_deliverable, source='admin_panel', acting_user=admin_user, send_email=False,
    )

    assert result == {'skipped': True, 'reason': 'review_required'}
