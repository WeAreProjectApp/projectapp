"""Commercial phase adapters enforce the same ownership and history boundaries."""
from datetime import date

import pytest
from content.models import BusinessProposal, ProjectRetentionContext, ProposalSection
from content.services.proposal_approval_service import (
    load_proposal,
    review_proposal,
    source_hash,
)
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Deliverable, Project, ProjectPhase, UserProfile
from accounts.services.project_phases import PhaseError, add_phase
from accounts.tests.delivery_authoring_helpers import pdf_bytes
from accounts.tests.delivery_helpers import build_delivery_context, publish, version

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    """Provide an administrator and an owned execution graph in temporary storage."""
    result = build_delivery_context()
    result.admin.is_staff = True
    result.admin.save(update_fields=['is_staff'])
    return result


def _proposal(context, *, status='accepted', project=None):
    project = project or context.project
    package = Deliverable.objects.create(project=project, title='Reviewed package', uploaded_by=context.admin)
    return BusinessProposal.objects.create(
        title='Reviewed proposal', client=context.client.profile, client_name='Client',
        status=status, deliverable=package,
    )


def _api(context, surface):
    client = APIClient()
    if surface == 'panel':
        client.force_login(context.admin)
    else:
        client.force_authenticate(context.admin)
    return client


def _url(context, surface, phase=None):
    names = {'panel': 'project-commercial-phases', 'platform': 'platform-project-phases'}
    details = {'panel': 'project-commercial-phase-detail', 'platform': 'platform-project-phase-detail'}
    kwargs = {'project_id': context.project.pk}
    if phase:
        kwargs['phase_id'] = phase.pk
        return reverse(details[surface], kwargs=kwargs)
    return reverse(names[surface], kwargs=kwargs)


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_public_phase_creation_rejects_a_draft_proposal(context, surface):
    """Fails if either API treats an unaccepted proposal as a commercial phase."""
    proposal = _proposal(context, status='draft')

    response = _api(context, surface).post(_url(context, surface), {'proposal_id': proposal.pk}, format='json')

    assert response.status_code == 400
    assert not ProjectPhase.objects.filter(business_proposal=proposal).exists()


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_public_phase_creation_rejects_a_foreign_client(context, surface):
    """Fails if the proposal's client can disagree with the project owner."""
    proposal = _proposal(context)
    other = get_user_model().objects.create_user('different-phase-client', 'other@example.test')
    proposal.client = UserProfile.objects.create(user=other, role='client')
    proposal.save(update_fields=['client'])

    response = _api(context, surface).post(_url(context, surface), {'proposal_id': proposal.pk}, format='json')

    assert response.status_code == 400
    assert not ProjectPhase.objects.filter(business_proposal=proposal).exists()


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_public_phase_creation_requires_the_reviewed_project_link(context, surface):
    """Fails if a phase can attach a proposal whose package belongs elsewhere."""
    other = Project.objects.create(name='Other reviewed project', client=context.client)
    proposal = _proposal(context, project=other)

    response = _api(context, surface).post(_url(context, surface), {'proposal_id': proposal.pk}, format='json')

    assert response.status_code == 400
    assert not ProjectPhase.objects.filter(business_proposal=proposal).exists()


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_public_phase_creation_preserves_retained_source_context(context, surface):
    """Fails if retained source data becomes an active commercial phase."""
    proposal = _proposal(context)
    retained = ProjectRetentionContext.objects.create(
        client=context.client, original_project_id=901001, project_name='Deleted origin',
        created_by=context.admin,
    )
    package = Deliverable.objects.create(project=None, retention_context=retained,
                                         title='Retained package', uploaded_by=context.admin)
    proposal.deliverable = package
    proposal.save(update_fields=['deliverable'])

    response = _api(context, surface).post(_url(context, surface), {'proposal_id': proposal.pk}, format='json')

    assert response.status_code == 400
    assert 'Deleted origin' in str(response.data)
    assert not ProjectPhase.objects.filter(business_proposal=proposal).exists()


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_public_phase_creation_keeps_a_finished_historical_link(context, surface):
    """Fails if a valid legacy link needs a newly invented approval manifest."""
    proposal = _proposal(context, status='finished')

    response = _api(context, surface).post(_url(context, surface), {'proposal_id': proposal.pk}, format='json')

    assert response.status_code == 201
    assert ProjectPhase.objects.get(business_proposal=proposal).project_id == context.project.pk
    proposal.refresh_from_db()
    assert proposal.platform_approval_manifest == {}


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_public_phase_creation_rejects_a_proposal_already_phased_elsewhere(context, surface):
    """Fails if one reviewed proposal can join phases in two projects."""
    proposal = _proposal(context)
    other = Project.objects.create(name='Other phase project', client=context.client)
    foreign = ProjectPhase.objects.create(project=other, business_proposal=proposal, order=1)

    response = _api(context, surface).post(_url(context, surface), {'proposal_id': proposal.pk}, format='json')

    assert response.status_code == 400
    assert not context.project.phases.exists()
    assert ProjectPhase.objects.filter(pk=foreign.pk, project=other).exists()


def _bind_delivery(context, phase):
    context.phase.commercial_phase = phase
    context.phase.save(update_fields=['commercial_phase'])
    publish(context)


def _bind_hosting_start(context, phase):
    phase.hosting_start_date = date(2026, 10, 1)
    phase.save(update_fields=['hosting_start_date'])


def _bind_hosting_activated(context, phase):
    phase.hosting_activated_at = date(2026, 10, 1)
    phase.save(update_fields=['hosting_activated_at'])


@pytest.mark.parametrize('surface', ['panel', 'platform'])
@pytest.mark.parametrize('bind', [_bind_delivery, _bind_hosting_start, _bind_hosting_activated])
def test_public_phase_deletion_preserves_bound_history(context, surface, bind):
    """Fails if either API deletes a phase supporting delivery or hosting."""
    phase = add_phase(context.project, _proposal(context))
    bind(context, phase)
    expected_version = version(context)

    response = _api(context, surface).delete(_url(context, surface, phase))

    assert response.status_code == 400
    assert ProjectPhase.objects.filter(pk=phase.pk).exists()
    assert version(context) == expected_version


def _approval_claim(context, proposal):
    proposal.platform_approval_manifest = {
        'request_id': 'confirmed-review', 'project_id': context.project.pk,
        'client_profile_id': context.client.profile.pk,
    }
    proposal.save(update_fields=['platform_approval_manifest'])


def test_internal_approval_phase_requires_its_exact_claim(context):
    """Fails if confirmation without acceptance loses its reviewed commercial phase."""
    proposal = _proposal(context, status='negotiating')
    ProposalSection.objects.create(proposal=proposal, section_type='technical_document',
                                    title='Technical scope', content_json={'epics': []}, order=0)

    review_proposal(proposal.pk, {
        'action': 'confirm', 'source_hash': source_hash(load_proposal(proposal.pk)), 'request_id': 'confirmed-review',
        'client_profile_id': context.client.profile.pk, 'project_id': context.project.pk,
        'use_proposal_contracts': False, 'accept_proposal': False,
        'custom_documents': [{'title': 'Contract', 'document_type': 'contract'}],
    }, actor=context.admin, files=[SimpleUploadedFile('contract.pdf', pdf_bytes(), content_type='application/pdf')])

    assert ProjectPhase.objects.get(business_proposal=proposal).project_id == context.project.pk
    proposal.refresh_from_db()
    assert proposal.status == 'negotiating'
    assert proposal.platform_approval_manifest['request_id'] == 'confirmed-review'


def test_internal_approval_phase_rejects_an_unrelated_request(context):
    """Fails if an arbitrary request identifier acts as an acceptance bypass."""
    proposal = _proposal(context, status='negotiating')
    _approval_claim(context, proposal)

    with pytest.raises(PhaseError):
        add_phase(context.project, proposal, approval_request_id='unrelated-request')

    assert not ProjectPhase.objects.filter(business_proposal=proposal).exists()


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_public_phase_request_cannot_claim_the_internal_transition(context, surface):
    """Fails if HTTP input can opt into the private approval-only transition."""
    proposal = _proposal(context, status='negotiating')
    _approval_claim(context, proposal)

    response = _api(context, surface).post(_url(context, surface), {
        'proposal_id': proposal.pk, 'approval_request_id': 'confirmed-review',
    }, format='json')

    assert response.status_code == 400
    assert not ProjectPhase.objects.filter(business_proposal=proposal).exists()


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_public_phase_request_rejects_an_invalid_proposal_identifier(context, surface):
    """Fails if a malformed proposal identifier crashes a commercial phase API."""
    response = _api(context, surface).post(_url(context, surface), {'proposal_id': 'not-an-id'}, format='json')

    assert response.status_code == 400
    assert not context.project.phases.exists()
