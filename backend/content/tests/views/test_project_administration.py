"""Session-admin project detail and commercial-phase adapters."""
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import (
    Deliverable, DeliveryPhase, DeliveryScope, Project, ProjectContract,
    ProjectPhase, UserProfile,
)
from content.models import BusinessProposal, Document


User = get_user_model()


def _project_context(label='primary'):
    client = User.objects.create_user(username=f'project-admin-client-{label}', password='test')
    profile = UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT)
    project = Project.objects.create(name=f'Administration project {label}', client=client)
    return profile, project


def _proposal(profile, project, *, status=BusinessProposal.Status.ACCEPTED, title='Linked proposal'):
    package = Deliverable.objects.create(project=project, title=f'{title} package', uploaded_by=profile.user)
    return BusinessProposal.objects.create(
        title=title, client=profile, client_name='Administration client',
        total_investment=1, status=status, deliverable=package,
    )


def _phase(profile, project, *, order, title):
    proposal = _proposal(profile, project, title=title)
    return ProjectPhase.objects.create(project=project, business_proposal=proposal, order=order)


def _bind_delivery_phase(project, phase):
    document = Document.objects.create(title='Delivery contract', project=project, client_user=project.client)
    contract = ProjectContract.objects.create(
        project=project, key='project-phase-contract', title='Delivery contract', document=document,
    )
    scope = DeliveryScope.objects.create(contract=contract, key='project-phase-scope', title='Delivery scope')
    DeliveryPhase.objects.create(
        scope=scope, commercial_phase=phase, key='project-phase-delivery', title='Delivery phase', order=1,
    )


def _bind_hosting_activated(project, phase):
    phase.hosting_activated_at = date(2026, 10, 1)
    phase.save(update_fields=['hosting_activated_at'])


def _bind_hosting_start(project, phase):
    phase.hosting_start_date = date(2026, 10, 1)
    phase.save(update_fields=['hosting_start_date'])


def _invalid_reorder_items(first, second, variant):
    if variant == 'duplicate-id':
        return [{'id': first.pk, 'order': 1}, {'id': first.pk, 'order': 2}]
    return [{'id': first.pk, 'order': 1}, {'id': second.pk, 'order': 3}]


def _immutable_order_payload(profile, project):
    return {'order': 2}


def _immutable_proposal_payload(profile, project):
    replacement = _proposal(profile, project, title='Replacement proposal')
    return {'business_proposal': replacement.pk}


@pytest.mark.django_db
def test_project_detail_keeps_the_commercial_fields(admin_client):
    """Fails if the project detail adapter drops dates, progress, or commercial JSON."""
    profile, project = _project_context()
    project.progress = 47
    project.start_date = date(2026, 1, 2)
    project.estimated_end_date = date(2026, 8, 3)
    project.payment_milestones = [{'label': 'Inicio'}]
    project.hosting_tiers = [{'frequency': 'quarterly'}]
    project.hosting_start_date = date(2026, 9, 4)
    project.save()

    response = admin_client.get(reverse('panel-project-detail', kwargs={'project_id': project.pk}))

    assert response.status_code == 200
    assert {key: response.data[key] for key in ('progress', 'start_date', 'estimated_end_date', 'payment_milestones', 'hosting_tiers', 'hosting_start_date')} == {
        'progress': 47, 'start_date': date(2026, 1, 2), 'estimated_end_date': date(2026, 8, 3),
        'payment_milestones': [{'label': 'Inicio'}], 'hosting_tiers': [{'frequency': 'quarterly'}],
        'hosting_start_date': date(2026, 9, 4),
    }


@pytest.mark.django_db
def test_commercial_phase_list_is_ordered_by_its_position(admin_client):
    """Fails if commercial phase reads ignore their configured positions."""
    profile, project = _project_context()
    second = _phase(profile, project, order=2, title='Second')
    first = _phase(profile, project, order=1, title='First')

    response = admin_client.get(reverse('project-commercial-phases', kwargs={'project_id': project.pk}))

    assert response.status_code == 200
    assert [(row['id'], row['order']) for row in response.data] == [(first.pk, 1), (second.pk, 2)]


@pytest.mark.django_db
def test_commercial_phase_list_excludes_other_project_phases(admin_client):
    """Fails if commercial phase reads expose a phase belonging to another project."""
    profile, project = _project_context()
    local = _phase(profile, project, order=1, title='Local')
    other_profile, other = _project_context('other')
    _phase(other_profile, other, order=1, title='Other')

    response = admin_client.get(reverse('project-commercial-phases', kwargs={'project_id': project.pk}))

    assert response.status_code == 200
    assert [(row['id'], row['order']) for row in response.data] == [(local.pk, 1)]


@pytest.mark.django_db
def test_commercial_phase_post_creates_a_requested_phase_for_a_linked_accepted_proposal(admin_client):
    """Fails if a linked accepted proposal cannot be added at the requested commercial phase position."""
    profile, project = _project_context()
    proposal = _proposal(profile, project)

    response = admin_client.post(
        reverse('project-commercial-phases', kwargs={'project_id': project.pk}),
        {'proposal_id': proposal.pk, 'order': 3}, format='json',
    )

    assert response.status_code == 201
    assert ProjectPhase.objects.get(project=project, business_proposal=proposal).order == 3


@pytest.mark.django_db
def test_commercial_phase_post_rejects_a_linked_draft(admin_client):
    """Fails if a draft proposal can be exposed as a commercial project phase."""
    profile, project = _project_context()
    proposal = _proposal(profile, project, status=BusinessProposal.Status.DRAFT)

    response = admin_client.post(
        reverse('project-commercial-phases', kwargs={'project_id': project.pk}),
        {'proposal_id': proposal.pk}, format='json',
    )

    assert response.status_code == 400
    assert 'proposal_id' in response.data
    assert ProjectPhase.objects.filter(project=project).count() == 0


@pytest.mark.django_db
def test_first_phase_hosting_date_updates_the_project_date(admin_client):
    """Fails if setting the first phase hosting date leaves the project billing date stale."""
    profile, project = _project_context()
    phase = _phase(profile, project, order=1, title='First')

    response = admin_client.patch(
        reverse('project-commercial-phase-detail', kwargs={'project_id': project.pk, 'phase_id': phase.pk}),
        {'hosting_start_date': '2026-10-07'}, format='json',
    )

    phase.refresh_from_db()
    project.refresh_from_db()
    assert response.status_code == 200
    assert (phase.hosting_start_date, project.hosting_start_date) == (date(2026, 10, 7), date(2026, 10, 7))


@pytest.mark.django_db
def test_second_phase_hosting_date_does_not_change_the_first_project_date(admin_client):
    """Fails if a later phase overwrites the project's initial hosting date."""
    profile, project = _project_context()
    first = _phase(profile, project, order=1, title='First')
    first.hosting_start_date = date(2026, 9, 1)
    first.save(update_fields=['hosting_start_date'])
    phase = _phase(profile, project, order=2, title='Second')
    project.hosting_start_date = date(2026, 9, 1)
    project.save(update_fields=['hosting_start_date'])

    response = admin_client.patch(
        reverse('project-commercial-phase-detail', kwargs={'project_id': project.pk, 'phase_id': phase.pk}),
        {'hosting_start_date': '2026-10-07'}, format='json',
    )

    phase.refresh_from_db()
    project.refresh_from_db()
    assert response.status_code == 200
    assert (phase.hosting_start_date, project.hosting_start_date) == (date(2026, 10, 7), date(2026, 9, 1))


@pytest.mark.django_db
@pytest.mark.parametrize(
    'payload_builder', (_immutable_order_payload, _immutable_proposal_payload), ids=('order', 'proposal'),
)
def test_commercial_phase_patch_rejects_an_immutable_field(admin_client, payload_builder):
    """Fails if a phase patch can change an immutable commercial phase field."""
    profile, project = _project_context()
    phase = _phase(profile, project, order=1, title='Immutable')
    original_proposal_id = phase.business_proposal_id

    response = admin_client.patch(
        reverse('project-commercial-phase-detail', kwargs={'project_id': project.pk, 'phase_id': phase.pk}),
        payload_builder(profile, project), format='json',
    )

    phase.refresh_from_db()
    assert response.status_code == 400
    assert (phase.order, phase.hosting_start_date, phase.business_proposal_id) == (1, None, original_proposal_id)


@pytest.mark.django_db
@pytest.mark.parametrize(
    'bind_phase',
    (_bind_delivery_phase, _bind_hosting_activated, _bind_hosting_start),
    ids=('delivery', 'hosting-activated', 'hosting-start'),
)
def test_commercial_phase_delete_keeps_a_bound_phase(admin_client, bind_phase):
    """Fails if deleting a delivery or hosting-bound phase discards retained project context."""
    profile, project = _project_context()
    phase = _phase(profile, project, order=1, title='Bound phase')
    bind_phase(project, phase)

    response = admin_client.delete(reverse('project-commercial-phase-detail', kwargs={'project_id': project.pk, 'phase_id': phase.pk}))

    assert response.status_code == 400
    assert ProjectPhase.objects.filter(pk=phase.pk).exists()


@pytest.mark.django_db
def test_commercial_phase_delete_removes_the_requested_phase_and_renumbers_the_rest(admin_client):
    """Fails if deleting a clean phase leaves a gap in the remaining commercial phase order."""
    profile, project = _project_context()
    first = _phase(profile, project, order=1, title='First')
    second = _phase(profile, project, order=2, title='Second')

    response = admin_client.delete(reverse('project-commercial-phase-detail', kwargs={'project_id': project.pk, 'phase_id': first.pk}))

    assert response.status_code == 204
    assert list(ProjectPhase.objects.filter(project=project).order_by('order').values_list('pk', 'order')) == [(second.pk, 1)]


@pytest.mark.django_db
def test_commercial_phase_reorder_persists_the_requested_order(admin_client):
    """Fails if a valid commercial phase reorder returns an order different from the stored sequence."""
    profile, project = _project_context()
    first = _phase(profile, project, order=1, title='First')
    second = _phase(profile, project, order=2, title='Second')

    response = admin_client.patch(
        reverse('project-commercial-phases-reorder', kwargs={'project_id': project.pk}),
        {'items': [{'id': first.pk, 'order': 2}, {'id': second.pk, 'order': 1}]}, format='json',
    )

    assert response.status_code == 200
    assert [(row['id'], row['order']) for row in response.data] == [(second.pk, 1), (first.pk, 2)]
    assert list(ProjectPhase.objects.filter(project=project).order_by('order').values_list('pk', 'order')) == [(second.pk, 1), (first.pk, 2)]


@pytest.mark.django_db
@pytest.mark.parametrize('variant', ('duplicate-id', 'nonconsecutive-order'))
def test_commercial_phase_reorder_rejects_an_invalid_sequence(admin_client, variant):
    """Fails if invalid phase identifiers or positions can rewrite the stored order."""
    profile, project = _project_context()
    first = _phase(profile, project, order=1, title='First')
    second = _phase(profile, project, order=2, title='Second')
    payload = {'items': _invalid_reorder_items(first, second, variant)}

    response = admin_client.patch(
        reverse('project-commercial-phases-reorder', kwargs={'project_id': project.pk}), payload, format='json',
    )

    assert response.status_code == 400
    assert list(ProjectPhase.objects.filter(project=project).order_by('order').values_list('pk', 'order')) == [(first.pk, 1), (second.pk, 2)]
