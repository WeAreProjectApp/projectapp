"""Subject rules for DocumentStateEpisode, and deleting a subject that has one.

Regression guard for the production 500 (MySQL error 3819) on
``DELETE /api/documents/<id>/delete/``: Django's ``CASCADE`` handler nullifies a
*nullable* FK before deleting the rows behind it, and the episode's CHECK
constraint used to forbid that transient state. See the
``non_deferring_constraints`` fixture for why the rest of the suite is blind to it.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from accounts.models import Project, UserProfile
from content.models import (
    Document,
    DocumentState,
    DocumentStateEpisode,
    DocumentStateEpisodeEvent,
    DocumentStateGroup,
    DocumentType,
)

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures('non_deferring_constraints'),
]

User = get_user_model()


@pytest.fixture
def markdown_type():
    return DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown', 'label': 'Markdown'},
    )[0]


@pytest.fixture
def document(markdown_type, admin_user):
    return Document.objects.create(
        title='Informe de avance',
        document_type=markdown_type,
        created_by=admin_user,
        updated_by=admin_user,
    )


@pytest.fixture
def client_user():
    user = User.objects.create_user(
        username='episode-client@example.com',
        email='episode-client@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
    return user


@pytest.fixture
def project(client_user):
    group = DocumentStateGroup.objects.create(
        catalog=DocumentStateGroup.Catalog.PROJECTS,
        name='Estados para probar el historial',
    )
    state = DocumentState.objects.create(
        catalog=DocumentStateGroup.Catalog.PROJECTS,
        group=group, name='En revisión',
    )
    project = Project.objects.create(
        name='Proyecto con estados', client=client_user, current_state=state,
    )
    DocumentStateEpisode.objects.create(project=project, state=state)
    return project


# ── The subject invariants themselves ──

def test_an_episode_may_lose_its_subject_transiently(document):
    """The literal statement Django emits before deleting the episode's row."""
    episode = document.state_episodes.get()

    DocumentStateEpisode.objects.filter(pk=episode.pk).update(document=None)

    episode.refresh_from_db()
    assert episode.document_id is None


def test_an_episode_cannot_point_at_a_document_and_a_project(document, project):
    episode = document.state_episodes.get()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DocumentStateEpisode.objects.filter(pk=episode.pk).update(project=project)


def test_saving_an_episode_without_a_subject_is_rejected(document):
    state = document.state_episodes.get().state

    with pytest.raises(ValidationError):
        DocumentStateEpisode.objects.create(state=state)


def test_saving_an_episode_with_two_subjects_is_rejected(document, project):
    state = document.state_episodes.get().state

    with pytest.raises(ValidationError):
        DocumentStateEpisode.objects.create(
            state=state, document=document, project=project,
        )


# ── Deleting a subject that owns episodes ──

def test_deleting_a_document_takes_its_episode_with_it(document):
    episode = document.state_episodes.get()
    assert episode.events.exists()

    document.delete()

    assert not Document.objects.filter(pk=document.pk).exists()
    assert not DocumentStateEpisodeEvent.objects.filter(episode_id=episode.pk).exists()
    assert DocumentStateEpisode.objects.count() == 0


def test_direct_project_delete_preserves_its_episode(project):
    episode = project.state_episodes.get()

    with pytest.raises(ProtectedError) as error:
        project.delete()

    assert episode in error.value.protected_objects
    episode.refresh_from_db()
    assert episode.project_id == project.pk


def test_bulk_document_delete_leaves_no_orphan_episode(document):
    assert document.state_episodes.exists()

    Document.objects.all().delete()

    assert DocumentStateEpisode.objects.count() == 0


def test_bulk_project_delete_preserves_its_episode(project):
    episode = project.state_episodes.get()

    with pytest.raises(ProtectedError) as error:
        Project.objects.all().delete()

    assert episode in error.value.protected_objects
    episode.refresh_from_db()
    assert episode.project_id == project.pk
