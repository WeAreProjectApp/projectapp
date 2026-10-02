"""Observable safeguards for immutable future-contract idea collections."""

from uuid import uuid4

import pytest
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models_project_ideas import ProjectIdeaCollection
from accounts.services import project_idea_collections as collections
from accounts.services import project_ideas as ideas
from accounts.services.project_collaboration_access import CollaborationConflict
from accounts.tests.project_collaboration_helpers import context, idea

pytestmark = pytest.mark.django_db


def selection(*items):
    """Build a valid ordered collection request from idea projections."""
    return {'title': 'Ideas para un contrato futuro', 'request_id': str(uuid4()),
            'items': [{'idea_id': item['id'], 'expected_version': item['version']} for item in items]}


def test_collection_preserves_selected_order():
    """Fails if collection snapshots reorder the selected suggestions."""
    c = context()
    first, second = idea(c, text='Primera'), idea(c, text='Segunda')
    result = collections.create_collection(c.project.pk, c.admin, selection(second, first))
    assert [item['text'] for item in result['items']] == ['Segunda', 'Primera']


def test_edit_does_not_change_collected_text():
    """Fails if a later edit mutates an already collected snapshot."""
    c = context()
    original = idea(c, text='Original')
    result = collections.create_collection(c.project.pk, c.admin, selection(original))
    ideas.edit_idea(c.project.pk, c.client, original['id'], {'text': 'Corregida', 'expected_version': 1})
    assert collections.get_collection(c.project.pk, c.admin, result['id'])['items'][0]['text'] == 'Original'


def test_stale_selection_writes_no_collection():
    """Fails if a stale selected revision creates a partial collection."""
    c = context()
    original = idea(c)
    ideas.edit_idea(c.project.pk, c.client, original['id'], {'text': 'Corregida', 'expected_version': 1})
    with pytest.raises(CollaborationConflict):
        collections.create_collection(c.project.pk, c.admin, selection(original))
    assert ProjectIdeaCollection.objects.count() == 0


def test_cross_project_selection_is_atomic():
    """Fails if a foreign idea creates any collection in this project."""
    c = context()
    original = idea(c)
    foreign = ideas.create_idea(c.other_project.pk, c.other, {'text': 'Otro proyecto', 'request_id': str(uuid4())})
    with pytest.raises(NotFound):
        collections.create_collection(c.project.pk, c.admin, selection(original, foreign))
    assert ProjectIdeaCollection.objects.count() == 0


def test_duplicate_selection_is_rejected():
    """Fails if a collection accepts the same suggestion twice."""
    c = context()
    original = idea(c)
    with pytest.raises(ValidationError):
        collections.create_collection(c.project.pk, c.admin, selection(original, original))


def test_client_cannot_read_collections():
    """Fails if a client can read internal future-contract collections."""
    c = context()
    with pytest.raises(PermissionDenied):
        collections.list_collections(c.project.pk, c.client)


def test_collection_retry_returns_existing_copy():
    """Fails if a retried collection request creates a second snapshot."""
    c = context()
    data = selection(idea(c))
    original = collections.create_collection(c.project.pk, c.admin, data)
    retry = collections.create_collection(c.project.pk, c.admin, data)
    assert retry['id'] == original['id']
