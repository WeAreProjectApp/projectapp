"""Observable safeguards for immutable project idea history."""

import pytest
from rest_framework.exceptions import PermissionDenied

from accounts.services import project_ideas as ideas
from accounts.services.project_collaboration_access import CollaborationConflict
from accounts.tests.project_collaboration_helpers import context, idea

pytestmark = pytest.mark.django_db


def test_edit_preserves_original_text():
    """Fails if editing overwrites the original revision."""
    c = context()
    original = idea(c, text='Sugerencia original')
    ideas.edit_idea(c.project.pk, c.client, original['id'], {'text': 'Sugerencia corregida', 'expected_version': 1})
    versions = ideas.revisions(c.project.pk, c.client, original['id'])['results']
    assert [version['text'] for version in versions] == ['Sugerencia corregida', 'Sugerencia original']


def test_edit_keeps_original_author_date():
    """Fails if an edit changes the original author or creation timestamp."""
    c = context()
    original = idea(c)
    changed = ideas.edit_idea(c.project.pk, c.client, original['id'], {'text': 'Corrección', 'expected_version': 1})
    assert (changed['author'], changed['created_at']) == (original['author'], original['created_at'])


def test_admin_cannot_rewrite_client_suggestion():
    """Fails if an administrator can rewrite a client suggestion."""
    c = context()
    original = idea(c)
    with pytest.raises(PermissionDenied):
        ideas.edit_idea(c.project.pk, c.admin, original['id'], {'text': 'Texto del equipo', 'expected_version': 1})


def test_admin_can_edit_team_suggestion():
    """Fails if the team cannot correct its own suggestion."""
    c = context()
    original = idea(c, actor=c.admin)
    changed = ideas.edit_idea(c.project.pk, c.admin, original['id'], {'text': 'Corrección del equipo', 'expected_version': 1})
    assert changed['text'] == 'Corrección del equipo'


def test_stale_edit_cannot_overwrite_current_text():
    """Fails if a stale revision overwrites the current suggestion text."""
    c = context()
    original = idea(c)
    ideas.edit_idea(c.project.pk, c.client, original['id'], {'text': 'Actual', 'expected_version': 1})
    with pytest.raises(CollaborationConflict):
        ideas.edit_idea(c.project.pk, c.client, original['id'], {'text': 'Obsoleto', 'expected_version': 1})
    assert ideas.get_idea(c.project.pk, c.client, original['id'])['text'] == 'Actual'


def test_archived_suggestion_cannot_be_edited():
    """Fails if a client can edit an archived suggestion."""
    c = context()
    original = idea(c)
    ideas.archive_idea(c.project.pk, c.admin, original['id'], {'expected_version': 1})
    with pytest.raises(PermissionDenied):
        ideas.edit_idea(c.project.pk, c.client, original['id'], {'text': 'Corrección', 'expected_version': 2})


def test_restore_allows_client_editing():
    """Fails if restoring a suggestion does not restore client editing."""
    c = context()
    original = idea(c)
    ideas.archive_idea(c.project.pk, c.admin, original['id'], {'expected_version': 1})
    restored = ideas.archive_idea(c.project.pk, c.admin, original['id'], {'expected_version': 2}, restore=True)
    assert ideas.get_idea(c.project.pk, c.client, restored['id'])['can_edit'] is True
