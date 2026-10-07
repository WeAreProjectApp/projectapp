"""Tests for the ProjectPhase model, service, and REST endpoints."""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import Deliverable, Project, ProjectPhase, UserProfile
from accounts.services.project_phases import (
    PhaseError,
    add_phase,
    remove_phase,
    reorder_phases,
)
from accounts.services.tokens import get_tokens_for_user

User = get_user_model()
pytestmark = pytest.mark.django_db
MAX_PROJECT_PHASE_LIST_QUERIES = 6


@pytest.fixture
def client_user(db):
    """Create the tenant account used by project-phase ownership checks."""
    user = User.objects.create_user(
        username='client@example.com', email='client@example.com', password='x',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
    return user


@pytest.fixture
def project(client_user):
    """Create a project owned by the client tenant fixture."""
    return Project.objects.create(name='Test project', client=client_user)


def _reviewed_proposal(project, title):
    """Arrange an accepted proposal whose reviewed package belongs to the project."""
    from content.models import BusinessProposal
    package = Deliverable.objects.create(project=project, title=f'{title} package', uploaded_by=project.client)
    return BusinessProposal.objects.create(title=title, client_name='Test Client', client=project.client.profile,
                                           status='accepted', deliverable=package)


@pytest.fixture
def business_proposal(project):
    """Create a proposal that can be attached to a project phase."""
    return _reviewed_proposal(project, 'Proposal A')


# =========================================================================
# Model tests
# =========================================================================


def test_phase_links_project_and_proposal_with_order(project, business_proposal):
    """Fails if a phase loses its persisted project, proposal, or sequence."""
    p = ProjectPhase.objects.create(
        project=project, business_proposal=business_proposal, order=1,
    )
    assert p.project == project
    assert p.business_proposal == business_proposal
    assert p.order == 1


def test_unique_constraint_blocks_same_proposal_twice_on_one_project(project, business_proposal):
    """Fails if one proposal can occupy duplicate phases in one project."""
    ProjectPhase.objects.create(project=project, business_proposal=business_proposal, order=1)
    with pytest.raises(IntegrityError):
        ProjectPhase.objects.create(project=project, business_proposal=business_proposal, order=2)


def test_ordering_by_order_field(project, business_proposal):
    """Fails if phase retrieval ignores the saved phase sequence."""
    from content.models import BusinessProposal
    p2 = BusinessProposal.objects.create(title='P2', client_name='X')
    ProjectPhase.objects.create(project=project, business_proposal=p2, order=2)
    ProjectPhase.objects.create(project=project, business_proposal=business_proposal, order=1)
    titles = [ph.business_proposal.title for ph in project.phases.all()]
    assert titles == ['Proposal A', 'P2']


def test_linked_business_proposal_returns_first_phase_proposal(project, business_proposal):
    """Fails if a project cannot resolve its first linked proposal."""
    ProjectPhase.objects.create(project=project, business_proposal=business_proposal, order=1)
    assert project.linked_business_proposal() == business_proposal


def test_linked_business_proposal_returns_none_when_no_phases(project):
    """Fails if an unphased project reports a nonexistent linked proposal."""
    assert project.linked_business_proposal() is None


# =========================================================================
# Service tests
# =========================================================================


def _add_distinct_phases(project, user, count):
    """Create phases whose populated deliverables expose descriptor query drift."""
    from content.models import BusinessProposal

    phases = []
    starting_order = project.phases.count()
    for number in range(1, count + 1):
        proposal = BusinessProposal.objects.create(
            title=f'Performance proposal {number}',
            client_name='Performance client',
            total_investment=Decimal('12000.00'),
        )
        if count == 1 or number < count:
            deliverable = Deliverable.objects.create(
                project=project,
                title=f'Performance deliverable {number}',
                category=Deliverable.CATEGORY_OTHER,
                uploaded_by=user,
            )
            proposal.deliverable = deliverable
            proposal.save(update_fields=['deliverable'])
        # Read budgets include historical unreviewed/unlinked rows. They are not
        # newly writable through the stricter commercial phase service.
        phases.append(ProjectPhase.objects.create(project=project, business_proposal=proposal, order=starting_order + number))
    return phases


def _list_phase_queries(client, url):
    client.get(url)
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url)
    assert response.status_code == 200
    return len(queries), response.json()


def test_add_phase_appends_at_end_when_order_omitted(project, business_proposal):
    """Fails if implicit phase insertion does not append after existing work."""
    phase = add_phase(project, business_proposal)
    assert phase.order == 1
    p2 = _reviewed_proposal(project, 'P2')
    phase2 = add_phase(project, p2)
    assert phase2.order == 2


def test_add_phase_rejects_duplicate(project, business_proposal):
    """Fails if the phase service permits a repeated proposal."""
    add_phase(project, business_proposal)
    with pytest.raises(PhaseError) as exc:
        add_phase(project, business_proposal)
    assert exc.value.code == 'duplicate_proposal'


def test_remove_phase_renumbers_remaining(project, business_proposal):
    """Fails if deletion leaves gaps in the remaining phase sequence."""
    p2 = _reviewed_proposal(project, 'P2')
    p3 = _reviewed_proposal(project, 'P3')
    add_phase(project, business_proposal)
    ph2 = add_phase(project, p2)
    add_phase(project, p3)
    remove_phase(project, ph2.id)
    remaining = list(project.phases.values_list('order', 'business_proposal__title').order_by('order'))
    assert remaining == [(1, 'Proposal A'), (2, 'P3')]


def test_reorder_phases_writes_new_order_atomically(project, business_proposal):
    """Fails if a valid reorder does not persist the requested sequence."""
    p2 = _reviewed_proposal(project, 'P2')
    p3 = _reviewed_proposal(project, 'P3')
    ph1 = add_phase(project, business_proposal)
    ph2 = add_phase(project, p2)
    ph3 = add_phase(project, p3)
    reorder_phases(project, [
        {'id': ph3.id, 'order': 1},
        {'id': ph1.id, 'order': 2},
        {'id': ph2.id, 'order': 3},
    ])
    titles_in_order = [ph.business_proposal.title for ph in project.phases.all()]
    assert titles_in_order == ['P3', 'Proposal A', 'P2']


def test_reorder_phases_rejects_phase_from_another_project(project, business_proposal, client_user):
    """Fails if reorder input can inject a phase from another project."""
    other = Project.objects.create(name='Other', client=client_user)
    p_other = _reviewed_proposal(other, 'PO')
    phase_other = add_phase(other, p_other)
    ph1 = add_phase(project, business_proposal)
    with pytest.raises(PhaseError) as exc:
        reorder_phases(project, [
            {'id': phase_other.id, 'order': 1},
            {'id': ph1.id, 'order': 2},
        ])
    assert exc.value.code == 'invalid_phase_id'


# =========================================================================
# HTTP-level endpoint tests
# =========================================================================


@pytest.fixture
def admin_user(db):
    """Create an administrator authorized to manage every project's phases."""
    u = User.objects.create_user(
        username='admin@example.com', email='admin@example.com', password='x',
    )
    UserProfile.objects.create(user=u, role='admin', is_onboarded=True, profile_completed=True)
    return u


@pytest.fixture
def authed_client(admin_user):
    """Provide a JWT client carrying the administrator's platform identity."""
    tokens = get_tokens_for_user(admin_user)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    return c


def test_list_phases_endpoint_returns_ordered_phases(authed_client, project, business_proposal):
    """Fails if the phase endpoint stops respecting the persisted phase order."""

    later_proposal = _reviewed_proposal(project, 'Later proposal')
    add_phase(project, later_proposal, order=2)
    add_phase(project, business_proposal, order=1)

    resp = authed_client.get(f'/api/accounts/projects/{project.id}/phases/')

    assert resp.status_code == 200
    data = resp.json()
    assert [row['proposal']['title'] for row in data] == ['Proposal A', 'Later proposal']


def test_list_phases_serializes_nested_proposal_fields(authed_client, project, client_user):
    """Fails if nested proposals lose deliverable IDs or pricing details."""
    from content.models import BusinessProposal

    deliverable = Deliverable.objects.create(
        project=project,
        title='Phase deliverable',
        category=Deliverable.CATEGORY_OTHER,
        uploaded_by=client_user,
    )
    linked_proposal = BusinessProposal.objects.create(
        title='Linked phase',
        client_name='Test Client',
        total_investment=Decimal('12000.00'),
        status=BusinessProposal.Status.ACCEPTED,
        deliverable=deliverable,
    )
    detached_proposal = BusinessProposal.objects.create(
        title='Detached phase',
        client_name='Test Client',
        total_investment=Decimal('9000.00'),
        status=BusinessProposal.Status.FINISHED,
    )
    # Existing historical phases remain readable, including a missing package.
    ProjectPhase.objects.create(project=project, business_proposal=linked_proposal, order=1)
    ProjectPhase.objects.create(project=project, business_proposal=detached_proposal, order=2)

    response = authed_client.get(f'/api/accounts/projects/{project.id}/phases/')

    assert response.status_code == 200
    rows = response.json()
    assert rows[0]['proposal'] == {
        'id': linked_proposal.pk,
        'title': 'Linked phase',
        'total_amount': 12000.0,
        'status': BusinessProposal.Status.ACCEPTED,
        'deliverable_id': deliverable.pk,
    }
    assert rows[1]['proposal']['deliverable_id'] is None
    assert rows[0]['hosting_tiers'][0]['frequency'] == 'quarterly'
    assert rows[0]['hosting_tiers'][0]['billing_amount'] == 1620


def test_anonymous_user_cannot_list_project_phases(project):
    """Fails if the phase endpoint stops requiring platform authentication."""
    response = APIClient().get(f'/api/accounts/projects/{project.id}/phases/')

    assert response.status_code == 401


def test_client_lists_own_project_phases(client_user, project, business_proposal):
    """Fails if a client can no longer read phases belonging to their project."""
    tokens = get_tokens_for_user(client_user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    add_phase(project, business_proposal)

    response = client.get(f'/api/accounts/projects/{project.id}/phases/')

    assert response.status_code == 200
    assert response.json()[0]['proposal']['id'] == business_proposal.pk


def test_profileless_user_lists_own_project_phases(db, business_proposal):
    """Fails if an owner without a profile loses access to their project phases."""
    owner = User.objects.create_user(
        username='profileless-owner@example.com',
        email='profileless-owner@example.com',
        password='x',
    )
    project = Project.objects.create(name='Profileless owner project', client=owner)
    add_phase(project, business_proposal)
    tokens = get_tokens_for_user(owner)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

    response = client.get(f'/api/accounts/projects/{project.id}/phases/')

    assert not UserProfile.objects.filter(user=owner).exists()
    assert response.status_code == 200
    assert response.json()[0]['proposal']['id'] == business_proposal.pk


def test_client_cannot_list_foreign_project_phases(client_user, project, business_proposal):
    """Fails if tenant filtering exposes phases from another client's project."""
    foreign_user = User.objects.create_user(
        username='foreign-client@example.com', email='foreign-client@example.com', password='x',
    )
    UserProfile.objects.create(user=foreign_user, role=UserProfile.ROLE_CLIENT)
    tokens = get_tokens_for_user(foreign_user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    add_phase(project, business_proposal)

    response = client.get(f'/api/accounts/projects/{project.id}/phases/')

    assert response.status_code == 404
    assert response.json()['detail'] == 'project_not_found'


def test_profileless_user_cannot_list_foreign_project_phases(db, project, business_proposal):
    """Fails if a missing profile bypasses tenant filtering for project phases."""
    foreign_user = User.objects.create_user(
        username='profileless-foreign@example.com',
        email='profileless-foreign@example.com',
        password='x',
    )
    add_phase(project, business_proposal)
    tokens = get_tokens_for_user(foreign_user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

    response = client.get(f'/api/accounts/projects/{project.id}/phases/')

    assert not UserProfile.objects.filter(user=foreign_user).exists()
    assert response.status_code == 404
    assert response.json() == {'detail': 'project_not_found'}


def test_project_phase_list_query_budget_is_constant(authed_client, project, client_user):
    """Fails if reading deliverables restores a query for each populated phase."""
    url = f'/api/accounts/projects/{project.id}/phases/'
    _add_distinct_phases(project, client_user, 1)

    one_query_count, one_row = _list_phase_queries(authed_client, url)
    _add_distinct_phases(project, client_user, 49)
    fifty_query_count, fifty_rows = _list_phase_queries(authed_client, url)

    assert len(one_row) == 1
    assert len(fifty_rows) == 50
    assert one_query_count == fifty_query_count
    assert fifty_query_count <= MAX_PROJECT_PHASE_LIST_QUERIES


def test_add_phase_endpoint(authed_client, project, business_proposal):
    """Fails if an administrator cannot add the first project phase."""
    resp = authed_client.post(
        f'/api/accounts/projects/{project.id}/phases/',
        {'proposal_id': business_proposal.id},
        format='json',
    )
    assert resp.status_code == 201
    assert resp.json()['order'] == 1


def test_add_phase_endpoint_rejects_duplicate(authed_client, project, business_proposal):
    """Fails if the HTTP API accepts a duplicate proposal phase."""
    add_phase(project, business_proposal)
    resp = authed_client.post(
        f'/api/accounts/projects/{project.id}/phases/',
        {'proposal_id': business_proposal.id},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.json()['detail'] == 'duplicate_proposal'


def test_remove_phase_endpoint(authed_client, project, business_proposal):
    """Fails if an administrator's delete request leaves the phase intact."""
    phase = add_phase(project, business_proposal)
    resp = authed_client.delete(f'/api/accounts/projects/{project.id}/phases/{phase.id}/')
    assert resp.status_code == 204
    assert project.phases.count() == 0


def test_reorder_phases_endpoint(authed_client, project, business_proposal):
    """Fails if the reorder endpoint does not store the submitted order."""
    p2 = _reviewed_proposal(project, 'P2')
    ph1 = add_phase(project, business_proposal)
    ph2 = add_phase(project, p2)
    resp = authed_client.patch(
        f'/api/accounts/projects/{project.id}/phases/reorder/',
        [{'id': ph2.id, 'order': 1}, {'id': ph1.id, 'order': 2}],
        format='json',
    )
    assert resp.status_code == 200
    titles = [ph.business_proposal.title for ph in project.phases.all()]
    assert titles == ['P2', 'Proposal A']


def test_patch_phase_sets_hosting_start_date(authed_client, project, business_proposal):
    """Fails if a hosting start date cannot be saved through the endpoint."""
    phase = add_phase(project, business_proposal)
    resp = authed_client.patch(
        f'/api/accounts/projects/{project.id}/phases/{phase.id}/',
        {'hosting_start_date': '2026-06-01'},
        format='json',
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['hosting_start_date'] == '2026-06-01'
    phase.refresh_from_db()
    assert str(phase.hosting_start_date) == '2026-06-01'


def test_patch_phase_clears_hosting_start_date(authed_client, project, business_proposal):
    """Fails if a null hosting start date does not clear the stored value."""
    phase = add_phase(project, business_proposal)
    phase.hosting_start_date = '2026-06-01'
    phase.save()
    resp = authed_client.patch(
        f'/api/accounts/projects/{project.id}/phases/{phase.id}/',
        {'hosting_start_date': None},
        format='json',
    )
    assert resp.status_code == 200
    phase.refresh_from_db()
    assert phase.hosting_start_date is None


def test_patch_phase_returns_hosting_tiers(authed_client, project, business_proposal):
    """Fails if phase updates omit the configured hosting-tier response data."""
    phase = add_phase(project, business_proposal)
    resp = authed_client.patch(
        f'/api/accounts/projects/{project.id}/phases/{phase.id}/',
        {'hosting_start_date': '2026-07-01'},
        format='json',
    )
    assert resp.status_code == 200
    tiers = resp.json().get('hosting_tiers', [])
    assert len(tiers) == 3
    frequencies = [t['frequency'] for t in tiers]
    assert frequencies == ['quarterly', 'semiannual', 'nine_month']


def test_patch_phase_rejects_non_admin(project, business_proposal, client_user):
    """Fails if a client JWT can alter hosting data on a project phase."""
    from accounts.services.tokens import get_tokens_for_user
    phase = add_phase(project, business_proposal)
    tokens = get_tokens_for_user(client_user)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    resp = c.patch(
        f'/api/accounts/projects/{project.id}/phases/{phase.id}/',
        {'hosting_start_date': '2026-06-01'},
        format='json',
    )
    assert resp.status_code == 403


def test_list_phases_includes_hosting_tiers_and_start_date(authed_client, project, business_proposal):
    """Fails if phase listing drops hosting dates or tier configuration."""
    phase = add_phase(project, business_proposal)
    phase.hosting_start_date = '2026-05-01'
    phase.save()
    resp = authed_client.get(f'/api/accounts/projects/{project.id}/phases/')
    assert resp.status_code == 200
    data = resp.json()[0]
    assert data['hosting_start_date'] == '2026-05-01'
    assert 'hosting_tiers' in data
    assert len(data['hosting_tiers']) == 3
