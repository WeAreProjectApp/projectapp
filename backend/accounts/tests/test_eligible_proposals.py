"""Tests for GET /api/accounts/clients/:id/eligible-proposals/."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import Deliverable, Project, UserProfile
from accounts.services.project_phases import add_phase
from accounts.services.tokens import get_tokens_for_user

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(db):
    """Create a JWT client with the platform administrator role."""
    u = User.objects.create_user(username='a@e.co', email='a@e.co', password='x')
    UserProfile.objects.create(user=u, role='admin', is_onboarded=True, profile_completed=True)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(u)["access"]}')
    return c


@pytest.fixture
def client_user(db):
    """Create the client whose eligible proposals are requested."""
    u = User.objects.create_user(username='c@e.co', email='c@e.co', password='x')
    UserProfile.objects.create(user=u, role='client', is_onboarded=True, profile_completed=True)
    return u


def _make_proposal(email, title='P', status='accepted'):
    from content.models import BusinessProposal
    return BusinessProposal.objects.create(
        title=title, client_email=email, client_name='X', status=status,
    )


def test_eligible_proposals_only_returns_clients_signed_unattached(admin_client, client_user):
    """Return only accepted, unattached proposals belonging to the requested client."""
    _make_proposal('c@e.co', 'A', status='accepted')
    mine_signed_attached = _make_proposal('c@e.co', 'B', status='accepted')
    _make_proposal('c@e.co', 'C', status='draft')  # not signed
    _make_proposal('other@e.co', 'D', status='accepted')  # other client

    project = Project.objects.create(name='P', client=client_user)
    mine_signed_attached.client = client_user.profile
    mine_signed_attached.deliverable = Deliverable.objects.create(project=project, title='Reviewed package', uploaded_by=client_user)
    mine_signed_attached.save(update_fields=['client', 'deliverable'])
    add_phase(project, mine_signed_attached)

    resp = admin_client.get(f'/api/accounts/clients/{client_user.id}/eligible-proposals/')
    assert resp.status_code == 200
    titles = sorted(p['title'] for p in resp.json())
    assert titles == ['A']


def test_eligible_proposals_returns_empty_when_none(admin_client, client_user):
    """Return an empty list when the client has no eligible proposals."""
    resp = admin_client.get(f'/api/accounts/clients/{client_user.id}/eligible-proposals/')
    assert resp.status_code == 200
    assert resp.json() == []


def test_eligible_proposals_requires_admin(client_user):
    """Reject a client account requesting eligible proposals."""
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(client_user)["access"]}')
    resp = c.get(f'/api/accounts/clients/{client_user.id}/eligible-proposals/')
    assert resp.status_code in (403, 401)


def test_eligible_proposals_404_for_unknown_client(admin_client):
    """Return not found for an unknown client identifier."""
    resp = admin_client.get('/api/accounts/clients/9999999/eligible-proposals/')
    assert resp.status_code == 404


def test_eligible_proposals_includes_finished_status(admin_client, client_user):
    """Include the client proposal when its status is finished."""
    _make_proposal('c@e.co', 'Finished one', status='finished')
    resp = admin_client.get(f'/api/accounts/clients/{client_user.id}/eligible-proposals/')
    titles = [p['title'] for p in resp.json()]
    assert 'Finished one' in titles
