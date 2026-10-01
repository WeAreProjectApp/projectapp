"""Observable payload and query bounds for project collaboration lists."""

from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import ValidationError

from accounts.models_project_ideas import ProjectIdeaCollection
from accounts.services import project_idea_collections as collections
from accounts.services import project_ideas as ideas
from accounts.tests.project_collaboration_helpers import context, idea

pytestmark = pytest.mark.django_db


def test_idea_list_queries_remain_bounded_at_a_full_page():
    """Fails if one full idea page regresses beyond six database queries."""
    c = context()
    for number in range(25):
        idea(c, text=f'Sugerencia {number}')
    with CaptureQueriesContext(connection) as queries:
        result = ideas.list_ideas(c.project.pk, c.client)
    assert len(result['results']) == 20
    assert len(queries) <= 6


def test_oversized_collection_leaves_no_frozen_copy():
    """Fails if an oversized snapshot writes any immutable collection row."""
    c = context()
    selected = [idea(c, text='x' * 10_000) for _ in range(20)]
    with pytest.raises(ValidationError):
        collections.create_collection(c.project.pk, c.admin, {
            'title': 'Una recopilación demasiado extensa', 'request_id': str(uuid4()),
            'items': [{'idea_id': item['id'], 'expected_version': item['version']} for item in selected]})
    assert ProjectIdeaCollection.objects.count() == 0


def test_multibyte_text_is_bounded_before_creation():
    """Fails if over-limit UTF-8 text creates a project idea."""
    c = context()
    with pytest.raises(ValidationError):
        idea(c, text='🙂' * 3_000)
    assert ideas.list_ideas(c.project.pk, c.client)['count'] == 0


def test_collection_list_queries_do_not_grow_per_snapshot():
    """Fails if collection summaries load snapshot items per result."""
    c = context()
    source = idea(c)
    for number in range(20):
        collections.create_collection(c.project.pk, c.admin, {
            'title': f'Alternativa {number}', 'request_id': str(uuid4()),
            'items': [{'idea_id': source['id'], 'expected_version': source['version']}]})
    with CaptureQueriesContext(connection) as queries:
        result = collections.list_collections(c.project.pk, c.admin)
    assert len(result['results']) == 20
    assert len(queries) <= 6
    assert 'items' not in result['results'][0]
    assert result['results'][0]['item_count'] == 1
