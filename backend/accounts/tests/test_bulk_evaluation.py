"""Regression coverage for bounded platform bulk evaluations."""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models.signals import post_init
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import BugReport, ChangeRequest, IssueEvent, Notification, Project, UserProfile


User = get_user_model()
HUGE_ID = 2 ** 100
# Includes the per-item transaction, locked project and persistent ticket history.
# Verified at 12 queries regardless of how many unrelated tickets the project has.
MAX_BULK_EVALUATION_QUERIES = 12

CHANGE_REQUEST_CASE = pytest.param(
    ChangeRequest,
    'approved',
    ChangeRequest.STATUS_PENDING,
    Notification.TYPE_CR_STATUS_CHANGED,
    'Solicitud actualizada',
    'No encontrada en el proyecto.',
    id='change-request',
)
BUG_REPORT_CASE = pytest.param(
    BugReport,
    'confirmed',
    BugReport.STATUS_REPORTED,
    Notification.TYPE_BUG_STATUS_CHANGED,
    'Bug actualizado',
    'No encontrado en el proyecto.',
    id='bug-report',
)
BULK_CASES = (CHANGE_REQUEST_CASE, BUG_REPORT_CASE)


def _user(email, role):
    user = User.objects.create_user(username=email, email=email, password='test-password')
    UserProfile.objects.create(
        user=user,
        role=role,
        is_onboarded=True,
        profile_completed=True,
    )
    return user


def _admin_client():
    admin = _user('bulk-admin@example.test', UserProfile.ROLE_ADMIN)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(admin).access_token}')
    return admin, client


def _project(name='Bulk project'):
    client_user = _user(f'{name.lower().replace(" ", "-")}@example.test', UserProfile.ROLE_CLIENT)
    return Project.objects.create(name=name, client=client_user, status=Project.STATUS_ACTIVE)


def _url(model, project):
    resource = 'change-requests' if model is ChangeRequest else 'bug-reports'
    return f'/api/accounts/projects/{project.id}/{resource}/bulk-evaluate/'


def _target(model, project, *, title='Bulk target', pk=None):
    values = {'project': project, 'title': title}
    if pk is not None:
        values['id'] = pk
    if model is ChangeRequest:
        return ChangeRequest.objects.create(created_by=project.client, **values)
    return BugReport.objects.create(reported_by=project.client, **values)


def _distractors(model, project, count=50):
    if model is ChangeRequest:
        ChangeRequest.objects.bulk_create([
            ChangeRequest(project=project, created_by=project.client, title=f'Distractor {number}')
            for number in range(count)
        ])
        return
    BugReport.objects.bulk_create([
        BugReport(project=project, reported_by=project.client, title=f'Distractor {number}')
        for number in range(count)
    ])


def _notification(project, model, target):
    notification_type = (
        Notification.TYPE_CR_STATUS_CHANGED
        if model is ChangeRequest else Notification.TYPE_BUG_STATUS_CHANGED
    )
    return Notification.objects.get(
        user=project.client,
        type=notification_type,
        related_object_id=target.id,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
def test_bulk_evaluation_materializes_requested_rows_with_constant_query_count(
        model, new_status, old_status, notification_type, notification_prefix, missing_detail,
):
    """Fails if the one-item bulk payload materializes same-project distractors."""
    _, api_client = _admin_client()
    light_project = _project('Light bulk project')
    crowded_project = _project('Crowded bulk project')
    light_target = _target(model, light_project, title='Light target')
    crowded_target = _target(model, crowded_project, title='Crowded target')
    _distractors(model, crowded_project)
    initialized_ids = []

    def remember_initialized(sender, instance, **kwargs):
        initialized_ids.append(instance.pk)

    post_init.connect(remember_initialized, sender=model, weak=False)
    try:
        light_payload = [{'id': light_target.id, 'status': new_status}]
        with CaptureQueriesContext(connection) as light_queries:
            light_response = api_client.post(_url(model, light_project), light_payload, format='json')
        light_initialized_ids = list(initialized_ids)
        initialized_ids.clear()

        crowded_payload = [{'id': crowded_target.id, 'status': new_status}]
        with CaptureQueriesContext(connection) as crowded_queries:
            crowded_response = api_client.post(_url(model, crowded_project), crowded_payload, format='json')
        crowded_initialized_ids = list(initialized_ids)
    finally:
        post_init.disconnect(remember_initialized, sender=model)

    assert light_response.json() == {
        'updated': 1, 'updated_ids': [light_target.id], 'errors': [],
    }
    assert crowded_response.json() == {
        'updated': 1, 'updated_ids': [crowded_target.id], 'errors': [],
    }
    assert light_initialized_ids == [light_target.id]
    assert crowded_initialized_ids == [crowded_target.id]
    assert len(light_queries) == len(crowded_queries) <= MAX_BULK_EVALUATION_QUERIES
    assert not model.objects.filter(project=crowded_project, status=new_status).exclude(
        id=crowded_target.id,
    ).exists()
    assert IssueEvent.objects.filter(project=crowded_project, action='evaluate', status=new_status).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
def test_bulk_evaluation_status_change_creates_client_notification(
        model, new_status, old_status, notification_type, notification_prefix, missing_detail,
):
    """Fails if a bulk status update stops creating its client notification."""
    _, api_client = _admin_client()
    project = _project()
    target = _target(model, project)
    payload = [{'id': target.id, 'status': new_status}]

    response = api_client.post(_url(model, project), payload, format='json')

    assert response.status_code == 200
    target.refresh_from_db()
    assert target.status == new_status
    notification = _notification(project, model, target)
    assert notification.type == notification_type
    assert notification.title == f'{notification_prefix}: {target.title}'
    assert notification.project_id == project.id
    assert notification.related_object_id == target.id
    assert notification.deliverable_id is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
def test_bulk_evaluation_returns_empty_result_for_empty_array(model, new_status, old_status,
                                                              notification_type, notification_prefix,
                                                              missing_detail):
    """Fails if an empty bulk payload stops returning the established zero result."""
    _, api_client = _admin_client()
    project = _project()

    response = api_client.post(_url(model, project), [], format='json')

    assert response.status_code == 200
    assert response.json() == {'updated': 0, 'updated_ids': [], 'errors': []}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
def test_bulk_evaluation_processes_exactly_500_items(model, new_status, old_status,
                                                      notification_type, notification_prefix,
                                                      missing_detail):
    """Fails if the inclusive 500-item bulk boundary stops processing each entry."""
    _, api_client = _admin_client()
    project = _project()
    target = _target(model, project)
    payload = [{'id': target.id, 'status': new_status}] * 500

    response = api_client.post(_url(model, project), payload, format='json')

    assert response.status_code == 200
    assert response.json()['updated'] == 500
    assert response.json()['updated_ids'] == [target.id] * 500
    assert response.json()['errors'] == []
    target.refresh_from_db()
    assert target.status == new_status
    assert Notification.objects.filter(
        user=project.client,
        type=notification_type,
        related_object_id=target.id,
    ).count() == 500


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
def test_bulk_evaluation_rejects_more_than_500_items(model, new_status, old_status,
                                                      notification_type, notification_prefix,
                                                      missing_detail):
    """Fails if an oversized bulk payload is accepted past the Spanish 500-item limit."""
    _, api_client = _admin_client()
    project = _project()
    payload = [{}] * 501

    response = api_client.post(_url(model, project), payload, format='json')

    assert response.status_code == 400
    assert response.json() == {'detail': 'Máximo 500 evaluaciones por carga.'}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
def test_bulk_evaluation_forbids_non_admin(model, new_status, old_status,
                                           notification_type, notification_prefix, missing_detail):
    """Fails if a project client can bulk-evaluate records without the admin role."""
    project = _project()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(project.client).access_token}')

    response = client.post(_url(model, project), [], format='json')

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
def test_bulk_evaluation_preserves_integer_key_aliases(
        model, new_status, old_status, notification_type, notification_prefix, missing_detail,
):
    """Fails if bool and integral-float IDs stop matching an integer dictionary key."""
    _, api_client = _admin_client()
    project = _project()
    target = _target(model, project, pk=1)
    payload = [
        {'id': target.id, 'status': new_status},
        {'id': True, 'status': new_status},
        {'id': float(target.id), 'status': new_status},
    ]

    response = api_client.post(_url(model, project), payload, format='json')

    assert response.status_code == 200
    assert response.json() == {'updated': 3, 'updated_ids': [target.id] * 3, 'errors': []}
    target.refresh_from_db()
    assert target.status == new_status


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
def test_bulk_evaluation_returns_ordered_per_item_misses(
        model, new_status, old_status, notification_type, notification_prefix, missing_detail,
):
    """Fails if bulk misses lose their original input order or mutate a foreign project row."""
    _, api_client = _admin_client()
    project = _project()
    local_target = _target(model, project, pk=1)
    foreign_project = _project('Foreign bulk project')
    foreign_target = _target(model, foreign_project)
    payload = [
        {'id': str(local_target.id), 'status': new_status},
        {'id': float(local_target.id) + 0.5, 'status': new_status},
        {'id': HUGE_ID, 'status': new_status},
        {'id': foreign_target.id, 'status': new_status},
        {'status': new_status},
        'not-an-object',
    ]

    response = api_client.post(_url(model, project), payload, format='json')

    assert response.status_code == 200
    data = response.json()
    assert data['updated'] == 0
    assert data['updated_ids'] == []
    assert data['errors'] == [
        {'index': 0, 'id': str(local_target.id), 'detail': missing_detail},
        {'index': 1, 'id': float(local_target.id) + 0.5, 'detail': missing_detail},
        {'index': 2, 'id': HUGE_ID, 'detail': missing_detail},
        {'index': 3, 'id': foreign_target.id, 'detail': missing_detail},
        {'index': 4, 'detail': 'Falta el campo id.'},
        {'index': 5, 'detail': 'Item no es un objeto.'},
    ]
    local_target.refresh_from_db()
    assert local_target.status == old_status
    foreign_target.refresh_from_db()
    assert foreign_target.status == old_status


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
def test_bulk_evaluation_repeats_duplicate_valid_ids(model, new_status, old_status,
                                                     notification_type, notification_prefix,
                                                     missing_detail):
    """Fails if duplicate IDs no longer retain their two ordered update notifications."""
    _, api_client = _admin_client()
    project = _project()
    target = _target(model, project)
    payload = [{'id': target.id, 'status': new_status}] * 2

    response = api_client.post(_url(model, project), payload, format='json')

    assert response.status_code == 200
    assert response.json() == {'updated': 2, 'updated_ids': [target.id, target.id], 'errors': []}
    target.refresh_from_db()
    assert target.status == new_status
    assert Notification.objects.filter(
        user=project.client,
        type=notification_type,
        related_object_id=target.id,
    ).count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('model', 'new_status', 'old_status', 'notification_type', 'notification_prefix', 'missing_detail'),
    BULK_CASES,
)
@pytest.mark.parametrize('unhashable_id', ([], {}), ids=('list', 'dictionary'))
def test_bulk_evaluation_returns_unhashable_id_error_after_a_valid_item(model, new_status, old_status,
                                                                    notification_type, notification_prefix,
                                                                    missing_detail, unhashable_id):
    """Fails if malformed IDs crash the batch instead of reporting an independent item error."""
    _, api_client = _admin_client()
    project = _project()
    target = _target(model, project)
    payload = [
        {'id': target.id, 'status': new_status},
        {'id': unhashable_id, 'status': new_status},
    ]

    response = api_client.post(_url(model, project), payload, format='json')

    assert response.status_code == 200
    assert response.json() == {
        'updated': 1, 'updated_ids': [target.pk],
        'errors': [{'index': 1, 'id': unhashable_id, 'detail': missing_detail}],
    }
    target.refresh_from_db()
    assert target.status == new_status
    assert Notification.objects.filter(
        user=project.client,
        type=notification_type,
        related_object_id=target.id,
    ).count() == 1


@pytest.mark.django_db
def test_bug_bulk_evaluation_persists_a_same_project_link():
    """Fails if a valid bulk linked_bug_id no longer persists with the duplicate status."""
    _, api_client = _admin_client()
    project = _project()
    linked_bug = _target(BugReport, project, title='Original bug')
    target = _target(BugReport, project, title='Duplicate bug')
    payload = [{'id': target.id, 'status': BugReport.STATUS_DUPLICATE, 'linked_bug_id': linked_bug.id}]

    response = api_client.post(_url(BugReport, project), payload, format='json')

    assert response.status_code == 200
    assert response.json() == {'updated': 1, 'updated_ids': [target.id], 'errors': []}
    target.refresh_from_db()
    assert target.status == BugReport.STATUS_DUPLICATE
    assert target.linked_bug_id == linked_bug.id


def _foreign_bug(project):
    other_project = _project('Other bug project')
    return _target(BugReport, other_project, title='Foreign bug')


def _archived_bug(project):
    archived_bug = _target(BugReport, project, title='Archived bug')
    archived_bug.is_archived = True
    archived_bug.save(update_fields=['is_archived'])
    return archived_bug


def _assert_invalid_link_response(response, target, expected_error):
    assert response.status_code == 200
    assert response.json() == {
        'updated': 0,
        'updated_ids': [],
        'errors': [{
            'index': 0,
            'id': target.id,
            'detail': {'linked_bug_id': [expected_error]},
        }],
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('linked_bug_factory', 'expected_error'),
    (
        pytest.param(_foreign_bug, 'El bug vinculado debe pertenecer al mismo proyecto.', id='foreign'),
        pytest.param(_archived_bug, 'El bug vinculado está archivado.', id='archived'),
    ),
)
def test_bug_bulk_evaluation_rejects_invalid_link_without_status_change(linked_bug_factory,
                                                                        expected_error):
    """Fails if invalid bulk bug links are accepted and change the target status."""
    _, api_client = _admin_client()
    project = _project()
    target = _target(BugReport, project)
    linked_bug = linked_bug_factory(project)
    payload = [{
        'id': target.id,
        'status': BugReport.STATUS_DUPLICATE,
        'linked_bug_id': linked_bug.id,
    }]
    response = api_client.post(_url(BugReport, project), payload, format='json')
    _assert_invalid_link_response(response, target, expected_error)

    target.refresh_from_db()
    assert target.status == BugReport.STATUS_REPORTED
    assert target.linked_bug_id is None
