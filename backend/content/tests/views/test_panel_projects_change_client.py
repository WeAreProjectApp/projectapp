"""The change-client endpoints: the ONLY path that moves a project between
clients — previewed, mode-explicit, stale-proof, and audited.

The generic update keeps refusing the client (``client_immutable``), so an
ownership change can never happen as a side effect of an edit.
"""
from decimal import Decimal

import pytest
from accounts.models import Project

from content.models import HostingRecord, IncomeRecord

pytestmark = pytest.mark.django_db


def preview_url(project_id, client_profile_id=None):
    base = f'/api/projects/{project_id}/change-client/preview/'
    if client_profile_id is None:
        return base
    return f'{base}?client_profile_id={client_profile_id}'


def apply_url(project_id):
    return f'/api/projects/{project_id}/change-client/'


def make_project(profile, name='Vastago', *, status=Project.STATUS_ACTIVE):
    return Project.objects.create(name=name, client=profile.user, status=status)


def thread_ids(project):
    """Threads the preview would list for ``project``.

    Every project is auto-provisioned a mother thread, so an apply payload that
    omits it looks to the staleness check like a row that appeared after the
    preview — which is exactly what it protects against. A real client echoes
    the preview; these tests echo it the same way.
    """
    return list(
        project.communication_threads.values_list('pk', flat=True),
    )


def make_hosting(profile, project):
    return HostingRecord.objects.create(
        client=profile, project=project,
        client_name='Ana - Vastago', monthly_value=Decimal('120000.00'),
    )


def make_income(profile, project, **overrides):
    fields = {
        'concept': 'Vastago - Fase 1',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-07-01',
        'total_amount': Decimal('1000000.00'),
        'gustavo_amount': Decimal('500000.00'),
        'carlos_amount': Decimal('500000.00'),
        'client': profile,
        'project': project,
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


class TestPreviewEndpoint:
    def test_answers_the_labelled_impact(
        self, admin_client, make_client_profile,
    ):
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        hosting = make_hosting(old, project)
        income = make_income(old, project)

        response = admin_client.get(preview_url(project.pk, new.pk))

        assert response.status_code == 200, response.data
        assert response.data['project']['id'] == project.pk
        assert response.data['new_client']['profile_id'] == new.pk
        assert [row['id'] for row in response.data['hostings_move']] == [
            hosting.pk,
        ]
        assert response.data['hosting_ids'] == [hosting.pk]
        assert response.data['income_ids'] == [income.pk]
        assert response.data['totals']['move'] == 2

    def test_the_destination_must_exist_and_differ(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile()
        project = make_project(owner)

        missing = admin_client.get(preview_url(project.pk, 99999))
        same = admin_client.get(preview_url(project.pk, owner.pk))

        assert missing.status_code == 400
        assert missing.data['code'] == 'client_not_found'
        assert same.status_code == 400
        assert same.data['code'] == 'same_client'

    def test_a_terminal_project_answers_400(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile()
        target = make_client_profile()
        project = make_project(owner, status=Project.STATUS_DECOMMISSIONED)

        response = admin_client.get(preview_url(project.pk, target.pk))

        assert response.status_code == 400
        assert response.data['code'] == 'project_terminal'


class TestApplyEndpoint:
    def test_mode_is_required_and_explicit(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile()
        target = make_client_profile()
        project = make_project(owner)

        response = admin_client.post(apply_url(project.pk), {
            'client_profile_id': target.pk,
            'mode': 'everything',
        }, format='json')

        assert response.status_code == 400
        assert response.data['code'] == 'invalid_mode'

    def test_a_vanished_plan_row_answers_409_and_writes_nothing(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile()
        target = make_client_profile()
        project = make_project(owner)
        income = make_income(owner, project)

        response = admin_client.post(apply_url(project.pk), {
            'client_profile_id': target.pk,
            'mode': 'move',
            'income_ids': [income.pk, 99999],
        }, format='json')

        assert response.status_code == 409
        assert response.data['code'] == 'records_not_found'
        assert response.data['missing_ids'] == [99999]
        project.refresh_from_db()
        assert project.client_id == owner.user_id

    def test_a_row_linked_after_the_preview_answers_409(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile()
        target = make_client_profile()
        project = make_project(owner)
        seen = make_income(owner, project)
        unseen = make_income(owner, project, concept='Nuevo')

        response = admin_client.post(apply_url(project.pk), {
            'client_profile_id': target.pk,
            'mode': 'move',
            'income_ids': [seen.pk],
            'communication_thread_ids': thread_ids(project),
        }, format='json')

        assert response.status_code == 409
        assert response.data['code'] == 'records_changed'
        assert response.data['changed_ids'] == [unseen.pk]
        seen.refresh_from_db()
        assert seen.client_id == owner.pk

    def test_move_applies_and_answers_the_annotated_row_with_counts(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile()
        target = make_client_profile()
        project = make_project(owner)
        income = make_income(owner, project)

        response = admin_client.post(apply_url(project.pk), {
            'client_profile_id': target.pk,
            'mode': 'move',
            'hosting_ids': [],
            'income_ids': [income.pk],
            'communication_thread_ids': thread_ids(project),
        }, format='json')

        assert response.status_code == 200, response.data
        assert response.data['moved'] == {
            'hostings': 0, 'incomes': 1, 'draft_accounts': 0,
            'project_folders': 5,
        }
        row = response.data['project']
        assert row['client']['profile_id'] == target.pk
        # The annotated counts answer for the permitted income move.
        assert row['hostings_count'] == 0
        assert row['incomes_count'] == 1

    def test_hosting_history_rejects_move_before_endpoint_writes(
        self, admin_client, make_client_profile,
    ):
        """Falla si el endpoint mueve un hosting legado antes de bloquear el proyecto."""
        owner = make_client_profile()
        target = make_client_profile()
        project = make_project(owner)
        hosting = make_hosting(owner, project)

        response = admin_client.post(apply_url(project.pk), {
            'client_profile_id': target.pk,
            'mode': 'move',
            'hosting_ids': [hosting.pk],
            'income_ids': [],
            'communication_thread_ids': thread_ids(project),
        }, format='json')

        assert response.status_code == 400
        assert 'historia financiera' in response.data['detail']
        project.refresh_from_db()
        hosting.refresh_from_db()
        assert project.client_id == owner.user_id
        assert hosting.client_id == owner.pk
        assert hosting.project_id == project.pk

    def test_detach_leaves_the_records_with_their_client(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile()
        target = make_client_profile()
        project = make_project(owner)
        income = make_income(owner, project)

        response = admin_client.post(apply_url(project.pk), {
            'client_profile_id': target.pk,
            'mode': 'detach',
            'income_ids': [income.pk],
            'communication_thread_ids': thread_ids(project),
        }, format='json')

        assert response.status_code == 200, response.data
        assert response.data['detached']['incomes'] == 1
        assert response.data['project']['incomes_count'] == 0
        income.refresh_from_db()
        assert income.client_id == owner.pk
        assert income.project_id is None

    def test_the_generic_update_still_refuses_the_client(
        self, admin_client, make_client_profile,
    ):
        """Regression pin: the dedicated endpoint is the only path."""
        owner = make_client_profile()
        other = make_client_profile()
        project = make_project(owner)

        response = admin_client.patch(
            f'/api/projects/{project.pk}/update/',
            {'client_profile_id': other.pk}, format='json',
        )

        assert response.status_code == 400
        assert response.data['code'] == 'client_immutable'
