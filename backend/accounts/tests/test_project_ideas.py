"""Observable safeguards for project idea creation and archival."""

from uuid import uuid4

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import DeliveryWorkspace, ProjectContract
from accounts.models_project_ideas import ProjectIdea
from accounts.services import project_ideas as ideas
from accounts.services.project_collaboration_access import CollaborationConflict
from accounts.tests.project_collaboration_helpers import context, idea

pytestmark = pytest.mark.django_db


def test_client_creation_keeps_authenticated_author():
    """Fails if a client idea stores a supplied author instead of the caller."""
    c = context()
    result = idea(c)
    stored = ProjectIdea.objects.get(pk=result['id'])
    assert (stored.author_id, stored.author_label, stored.origin) == (c.client.pk, 'Cliente', 'client')


def test_admin_creation_is_team_origin():
    """Fails if an administrator suggestion loses its team origin marker."""
    c = context()
    result = idea(c, actor=c.admin)
    assert result['origin'] == 'team'


@pytest.mark.parametrize('text', ['', '   ', 'a' * 10001])
def test_invalid_text_creates_nothing(text):
    """Fails if invalid idea text persists a partial suggestion."""
    c = context()
    with pytest.raises(ValidationError):
        idea(c, text=text)
    assert ProjectIdea.objects.count() == 0


def test_supplied_author_is_rejected():
    """Fails if request data can impersonate a different idea author."""
    c = context()
    with pytest.raises(ValidationError):
        ideas.create_idea(c.project.pk, c.client, {'text': 'Una idea', 'request_id': str(uuid4()), 'author': c.admin.pk})
    assert ProjectIdea.objects.count() == 0


def test_creation_retry_reuses_original():
    """Fails if an idempotent retry creates a second suggestion."""
    c = context()
    data = {'text': 'Una idea', 'request_id': str(uuid4())}
    original = ideas.create_idea(c.project.pk, c.client, data)
    retry = ideas.create_idea(c.project.pk, c.client, data)
    assert retry['id'] == original['id']


def test_changed_creation_retry_is_conflict():
    """Fails if one idempotency key can create two different suggestions."""
    c = context()
    data = {'text': 'Una idea', 'request_id': str(uuid4())}
    ideas.create_idea(c.project.pk, c.client, data)
    with pytest.raises(CollaborationConflict):
        ideas.create_idea(c.project.pk, c.client, {**data, 'text': 'Otra idea'})


def test_archive_preserves_client_read():
    """Fails if archiving hides a client's existing suggestion."""
    c = context()
    original = idea(c)
    ideas.archive_idea(c.project.pk, c.admin, original['id'], {'expected_version': 1})
    assert ideas.get_idea(c.project.pk, c.client, original['id'])['archived'] is True


def test_client_cannot_archive():
    """Fails if a client can archive a suggestion reserved for the team."""
    c = context()
    original = idea(c)
    with pytest.raises(PermissionDenied):
        ideas.archive_idea(c.project.pk, c.client, original['id'], {'expected_version': 1})


def test_suggestion_does_not_create_contractual_work():
    """Fails if a suggestion implicitly creates a contract or workspace."""
    c = context()
    idea(c)
    assert (ProjectContract.objects.count(), DeliveryWorkspace.objects.count()) == (0, 0)
