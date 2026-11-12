"""Contract tests for administrators following up monitoring cases."""

import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from monitoring.models import Case, CaseActivity, Resource, Source

CASES_URL = '/api/monitoring/cases/'


@pytest.fixture
def monitoring_case(db):
    server = Resource.objects.create(key='srv1681495', name='VPS de producción', kind='server')
    resource = Resource.objects.create(key='projectapp', name='ProjectApp', kind='project', server=server)
    source = Source.objects.create(resource=resource, key='integrity', name='Integridad')
    return Case.objects.create(
        source=source,
        fingerprint='integrity:backup',
        fingerprint_hash='a' * 64,
        title='Backup atrasado',
        severity='critical',
        first_seen_at=timezone.now(),
        last_seen_at=timezone.now(),
        detections=1,
        version=2,
    )


@pytest.fixture
def staff_user(db):
    user = get_user_model().objects.create_user(
        username='monitoring-staff', password='test-password', is_staff=True,
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
    )
    return user


@pytest.fixture
def regular_user(db):
    user = get_user_model().objects.create_user(
        username='monitoring-regular', password='test-password', is_staff=False,
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
    )
    return user


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_login(staff_user)
    return client


@pytest.mark.django_db
def test_cases_rejects_anonymous_user(monitoring_case):
    """Falla si el listado de seguimiento expone incidentes al público."""
    response = APIClient().get(CASES_URL)

    assert response.status_code == 403


@pytest.mark.django_db
def test_cases_rejects_authenticated_non_staff_user(regular_user, monitoring_case):
    """Falla si cualquier sesión autenticada puede consultar casos internos."""
    client = APIClient()
    client.force_login(regular_user)

    response = client.get(CASES_URL)

    assert response.status_code == 403


@pytest.mark.django_db
def test_staff_case_list_returns_paginated_case_envelope(staff_client, monitoring_case):
    """Falla si el panel deja de recibir el contrato paginado de casos."""
    response = staff_client.get(CASES_URL)

    assert response.status_code == 200
    assert response.json()['count'] == 1
    assert response.json()['page_size'] == 25
    assert response.json()['results'][0]['id'] == monitoring_case.pk


@pytest.mark.django_db
def test_case_state_requires_csrf_for_staff_session(staff_user, monitoring_case):
    """Falla si una sesión de panel puede mutar casos sin protección CSRF."""
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(staff_user)

    response = client.post(
        f'{CASES_URL}{monitoring_case.pk}/state/',
        {'state': 'reviewing', 'version': monitoring_case.version},
        format='json',
    )

    assert response.status_code == 403
    monitoring_case.refresh_from_db()
    assert monitoring_case.state == 'pending'


@pytest.mark.django_db
def test_state_change_writes_audit_version(staff_client, staff_user, monitoring_case):
    """Falla si un cambio de estado no deja versión y autor auditables."""
    response = staff_client.post(
        f'{CASES_URL}{monitoring_case.pk}/state/',
        {'state': 'reviewing', 'version': monitoring_case.version, 'note': 'Estoy revisando.'},
        format='json',
    )

    activity = CaseActivity.objects.get(case=monitoring_case, kind='state')
    assert response.status_code == 200
    assert response.json()['state'] == 'reviewing'
    assert response.json()['version'] == 3
    assert activity.actor_name == staff_user.get_username()
    assert activity.text == 'Estoy revisando.'


@pytest.mark.django_db
def test_stale_state_version_returns_conflict(staff_client, monitoring_case):
    """Falla si una pestaña desactualizada puede pisar el seguimiento actual."""
    response = staff_client.post(
        f'{CASES_URL}{monitoring_case.pk}/state/',
        {'state': 'reviewing', 'version': monitoring_case.version - 1},
        format='json',
    )

    assert response.status_code == 409
    monitoring_case.refresh_from_db()
    assert monitoring_case.state == 'pending'


@pytest.mark.django_db
def test_note_appears_in_case_history(staff_client, staff_user, monitoring_case):
    """Falla si una nota de seguimiento no conserva autor o desaparece del historial."""
    created = staff_client.post(
        f'{CASES_URL}{monitoring_case.pk}/notes/', {'text': 'Se verificó el respaldo.'}, format='json',
    )
    detail = staff_client.get(f'{CASES_URL}{monitoring_case.pk}/')

    assert created.status_code == 201
    assert created.json()['text'] == 'Se verificó el respaldo.'
    assert created.json()['actor_name'] == staff_user.get_username()
    assert detail.status_code == 200
    assert detail.json()['activities']['results'][0]['text'] == 'Se verificó el respaldo.'
