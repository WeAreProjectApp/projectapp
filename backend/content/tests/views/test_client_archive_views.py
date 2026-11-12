"""HTTP surface of client archiving.

Three things are worth a view test rather than a service test: that the
ordinary identity PATCH can no longer archive anyone, that the preview/apply
pair speaks the codes the modal branches on, and that archived clients stop
surfacing in the autocomplete that feeds every "assign a client" flow.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from accounts.models import Project, UserProfile

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def admin_client(client):
    user = User.objects.create_superuser(
        username='arch-admin@example.com',
        email='arch-admin@example.com',
        password='pass12345',
    )
    UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': UserProfile.ROLE_ADMIN},
    )
    client.login(username='arch-admin@example.com', password='pass12345')
    return client


@pytest.fixture
def profile():
    user = User.objects.create_user(
        username='arch-view@example.com',
        email='arch-view@example.com',
        password='pass12345',
        first_name='Vista',
        last_name='Archivo',
    )
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)


class TestPatchRefusesToArchive:
    def test_the_identity_patch_rejects_is_archived(
        self, admin_client, profile,
    ):
        # Archiving suspends projects and cancels their future billing. If the
        # ordinary save button could carry it, that would happen with no
        # preview and no audit row.
        response = admin_client.patch(
            reverse('update-proposal-client', args=[profile.pk]),
            {'is_archived': True},
            content_type='application/json',
        )

        assert response.status_code == 400
        assert response.data['error'] == 'client_archive_transition_required'
        profile.refresh_from_db()
        assert profile.archived_at is None

    def test_an_ordinary_identity_edit_still_works(
        self, admin_client, profile,
    ):
        response = admin_client.patch(
            reverse('update-proposal-client', args=[profile.pk]),
            {'company': 'Nueva Empresa'},
            content_type='application/json',
        )

        assert response.status_code == 200
        profile.refresh_from_db()
        assert profile.company_name == 'Nueva Empresa'


class TestArchiveEndpoints:
    def test_preview_reports_the_projects_and_writes_nothing(
        self, admin_client, profile,
    ):
        project = Project.objects.create(
            name='Proyecto vivo',
            client=profile.user,
            status=Project.STATUS_ACTIVE,
        )

        response = admin_client.get(
            reverse('preview-client-archive', args=[profile.pk]),
        )

        assert response.status_code == 200
        assert [p['project_id'] for p in response.data['projects']] == [
            project.pk,
        ]
        assert response.data['projects'][0]['impact_token']
        profile.refresh_from_db()
        assert profile.archived_at is None

    def test_archive_suspends_and_returns_the_client(
        self, admin_client, profile,
    ):
        project = Project.objects.create(
            name='Proyecto vivo',
            client=profile.user,
            status=Project.STATUS_ACTIVE,
        )
        preview = admin_client.get(
            reverse('preview-client-archive', args=[profile.pk]),
        ).data
        payload = {
            'transitions': [
                {
                    'project_id': p['project_id'],
                    'impact_token': p['impact_token'],
                }
                for p in preview['projects']
            ],
        }

        response = admin_client.post(
            reverse('archive-proposal-client', args=[profile.pk]),
            payload,
            content_type='application/json',
        )

        assert response.status_code == 200
        assert response.data['client']['is_archived'] is True
        assert response.data['suspended_projects'] == [project.pk]
        project.refresh_from_db()
        assert project.current_state.system_key == 'suspended'

    def test_a_stale_confirmation_answers_409(self, admin_client, profile):
        Project.objects.create(
            name='Proyecto vivo',
            client=profile.user,
            status=Project.STATUS_ACTIVE,
        )

        response = admin_client.post(
            reverse('archive-proposal-client', args=[profile.pk]),
            {'transitions': []},
            content_type='application/json',
        )

        assert response.status_code == 409
        assert response.data['error'] == 'projects_changed'
        profile.refresh_from_db()
        assert profile.archived_at is None

    def test_archiving_twice_answers_409(self, admin_client, profile):
        admin_client.post(
            reverse('archive-proposal-client', args=[profile.pk]),
            {'transitions': []},
            content_type='application/json',
        )

        response = admin_client.post(
            reverse('archive-proposal-client', args=[profile.pk]),
            {'transitions': []},
            content_type='application/json',
        )

        assert response.status_code == 409
        assert response.data['error'] == 'client_already_archived'

    def test_unarchive_names_the_projects_it_left_suspended(
        self, admin_client, profile,
    ):
        project = Project.objects.create(
            name='Proyecto vivo',
            client=profile.user,
            status=Project.STATUS_ACTIVE,
        )
        preview = admin_client.get(
            reverse('preview-client-archive', args=[profile.pk]),
        ).data
        admin_client.post(
            reverse('archive-proposal-client', args=[profile.pk]),
            {
                'transitions': [
                    {
                        'project_id': p['project_id'],
                        'impact_token': p['impact_token'],
                    }
                    for p in preview['projects']
                ],
            },
            content_type='application/json',
        )

        response = admin_client.post(
            reverse('unarchive-proposal-client', args=[profile.pk]),
            content_type='application/json',
        )

        assert response.status_code == 200
        assert response.data['client']['is_archived'] is False
        # The UI has to be able to say "these stayed suspended", because
        # reactivating them does not bring their cancelled incomes back.
        assert response.data['still_suspended'] == [project.pk]

    def test_transitions_must_be_a_list(self, admin_client, profile):
        response = admin_client.post(
            reverse('archive-proposal-client', args=[profile.pk]),
            {'transitions': 'todos'},
            content_type='application/json',
        )

        assert response.status_code == 400
        assert response.data['error'] == 'invalid_transitions'


class TestAutocompleteExcludesArchived:
    def test_an_archived_client_is_out_of_the_picker(
        self, admin_client, profile,
    ):
        profile.archived_at = timezone.now()
        profile.save(update_fields=['archived_at'])

        response = admin_client.get(
            reverse('search-proposal-clients'), {'q': 'Vista'},
        )

        assert response.status_code == 200
        assert [row['id'] for row in response.data] == []

    def test_include_archived_brings_it_back_for_reassignment(
        self, admin_client, profile,
    ):
        profile.archived_at = timezone.now()
        profile.save(update_fields=['archived_at'])

        response = admin_client.get(
            reverse('search-proposal-clients'),
            {'q': 'Vista', 'include_archived': 'true'},
        )

        assert response.status_code == 200
        assert [row['id'] for row in response.data] == [profile.pk]
