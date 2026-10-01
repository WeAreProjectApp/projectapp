"""Observable project and ownership isolation for project ideas."""

import pytest
from rest_framework.exceptions import NotFound

from accounts.services import project_idea_collections as collections
from accounts.services import project_ideas as ideas
from accounts.tests.project_collaboration_helpers import context, idea
from accounts.tests.test_project_idea_collections import selection

pytestmark = pytest.mark.django_db


def test_other_project_cannot_read_idea_revision():
    """Fails if another project can read a suggestion revision."""
    c = context()
    original = idea(c)
    with pytest.raises(NotFound):
        ideas.revisions(c.other_project.pk, c.other, original['id'])


def test_client_transfer_hides_previous_client_ideas():
    """Fails if a new owner can read the previous client's suggestions."""
    c = context()
    idea(c, text='Private previous owner suggestion')
    c.project.client = c.other
    c.project.save()
    assert ideas.list_ideas(c.project.pk, c.other)['results'] == []


def test_admin_keeps_previous_owner_suggestion():
    """Fails if ownership transfer hides prior ideas from the administrator."""
    c = context()
    original = idea(c, text='Preserved suggestion')
    c.project.client = c.other
    c.project.save()
    assert ideas.get_idea(c.project.pk, c.admin, original['id'])['text'] == 'Preserved suggestion'


def test_previous_client_ideas_cannot_be_collected_for_new_owner():
    """Fails if a prior client's idea enters a new owner's collection."""
    c = context()
    original = idea(c)
    c.project.client = c.other
    c.project.save()
    with pytest.raises(NotFound):
        collections.create_collection(c.project.pk, c.admin, selection(original))
