"""Observable fake-data safeguards for project collaboration fixtures."""

from datetime import date

import pytest
from content.fake_data import SeedContext
from django.core.management.base import CommandError
from django.test import override_settings

from accounts.management.commands._project_collaboration_seed import (
    clear_fake_project_collaboration,
    seed_project_collaboration,
)
from accounts.models_project_client_access import ProjectClientAccessPolicy
from accounts.models_project_ideas import (
    ProjectIdea,
    ProjectIdeaCollection,
    ProjectIdeaRevision,
)
from accounts.services import project_client_access as access
from accounts.services import project_ideas as ideas
from accounts.tests.project_collaboration_helpers import context, enable, sources

pytestmark = pytest.mark.django_db


def seed_context():
    """Return deterministic seed metadata for collaboration test data."""
    return SeedContext(seed=42, anchor_date=date(2026, 10, 1), namespace='p4-tests')


@override_settings(FAKE_DATA_ALLOWED=False)
def test_seed_refuses_disabled_fake_data():
    """Fails if collaboration seed data bypasses the fake-data gate."""
    c = context()
    with pytest.raises(CommandError):
        seed_project_collaboration(c.project, seed_context(), c.admin)
    assert ProjectIdea.objects.count() == 0


@override_settings(FAKE_DATA_ALLOWED=True)
def test_seed_leaves_every_access_field_hidden():
    """Fails if seed data grants any client access field by default."""
    c = context()
    sources(c)
    seed_project_collaboration(c.project, seed_context(), c.admin)
    assert ProjectClientAccessPolicy.objects.get(project=c.project).permissions == {}
    assert access.get_policy(c.project.pk, c.admin)['permissions'] == access.empty_matrix()


@override_settings(FAKE_DATA_ALLOWED=True)
def test_seed_retry_preserves_the_collected_snapshot():
    """Fails if a seed retry overwrites a frozen collection snapshot."""
    c = context()
    seed_project_collaboration(c.project, seed_context(), c.admin)
    suggestion = ProjectIdea.objects.get(project=c.project, origin='client')
    ideas.edit_idea(c.project.pk, c.client, suggestion.pk, {'text': 'Corrección posterior', 'expected_version': 1})
    seed_project_collaboration(c.project, seed_context(), c.admin)
    assert list(ProjectIdeaCollection.objects.get(project=c.project).items.values_list('text', flat=True)) == [
        'Evaluar un tablero adicional en un contrato futuro.']


@override_settings(FAKE_DATA_ALLOWED=True)
def test_seed_preserves_administrator_visibility():
    """Fails if seeding replaces an administrator's access policy."""
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    before = ProjectClientAccessPolicy.objects.get(project=c.project).permissions
    seed_project_collaboration(c.project, seed_context(), c.admin)
    assert ProjectClientAccessPolicy.objects.get(project=c.project).permissions == before


@override_settings(FAKE_DATA_ALLOWED=True)
def test_seed_creates_an_archived_revision_example():
    """Fails if seed data omits its archived idea history example."""
    c = context()
    seed_project_collaboration(c.project, seed_context(), c.admin)
    team = ProjectIdea.objects.get(project=c.project, origin='team')
    assert list(ProjectIdeaRevision.objects.filter(idea=team).order_by('number').values_list('text', flat=True)) == [
        'Revisar alternativas antes de definir un nuevo contrato.',
        'Comparar alternativas con el cliente antes de definir un contrato futuro.']
    assert team.archived_at is not None


@override_settings(FAKE_DATA_ALLOWED=True)
def test_seed_does_not_create_a_contract():
    """Fails if collaboration fake data creates a contract automatically."""
    from accounts.models import ProjectContract
    c = context()
    seed_project_collaboration(c.project, seed_context(), c.admin)
    assert not ProjectContract.objects.filter(project=c.project).exists()


@override_settings(FAKE_DATA_ALLOWED=True)
def test_collection_reset_preserves_other_projects():
    """Fails if clearing one project's seed data removes another's data."""
    c = context()
    seed_project_collaboration(c.project, seed_context(), c.admin)
    seed_project_collaboration(c.other_project, seed_context(), c.admin)
    clear_fake_project_collaboration([c.project])
    assert list(ProjectIdeaCollection.objects.values_list('project_id', flat=True)) == [c.other_project.pk]
