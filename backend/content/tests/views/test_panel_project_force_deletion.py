"""Forced project deletion keeps its superuser confirmation boundary intact."""

import pytest
from accounts.models import Project, ProjectPhase
from django.test import Client
from rest_framework_simplejwt.tokens import AccessToken

from content.models import BusinessProposal, Document, DocumentFolder, DocumentType, IncomeRecord

pytestmark = pytest.mark.django_db


@pytest.fixture
def force_project(make_client_profile):
    profile = make_client_profile(company='Forced deletion client')
    return Project.objects.create(name='Forced deletion project', client=profile.user)


def force_preview_url(project):
    return f'/api/projects/{project.pk}/delete-preview/?force=true'


def force_delete_url(project):
    return f'/api/projects/{project.pk}/delete/'


def full_force_preview(client, project):
    initial = client.get(force_preview_url(project))
    delete_keys = [dependency['key'] for dependency in initial.data['dependencies']]
    return client.post(
        f'/api/projects/{project.pk}/delete-preview/',
        {'delete_keys': delete_keys},
        format='json',
    )


def test_superuser_confirmed_force_delete_removes_project(super_client, force_project):
    """A valid reviewed panel command reaches the purge and returns success."""
    preview = full_force_preview(super_client, force_project)

    response = super_client.delete(force_delete_url(force_project), {
        'force': True, 'confirmation': 'DELETE',
        'impact_token': preview.data['impact_token'],
        'delete_keys': preview.data['delete_keys'],
    }, format='json')

    assert response.status_code == 204
    assert not Project.objects.filter(pk=force_project.pk).exists()


def test_force_delete_blocks_foreign_income_without_client_profile(
    super_client, force_project, make_client_profile,
):
    """Legacy missing profiles never make another client's income disposable."""
    force_project.communication_root_thread.delete()
    force_project.client.profile.delete()
    other_client = make_client_profile(company='Retained income client')
    income = IncomeRecord.objects.create(
        project=force_project, client=other_client, concept='Foreign legacy income',
        period_date='2026-10-04', total_amount='100', gustavo_amount='50', carlos_amount='50',
    )
    preview = full_force_preview(super_client, force_project)

    response = super_client.delete(force_delete_url(force_project), {
        'force': True, 'confirmation': 'DELETE',
        'impact_token': preview.data['impact_token'],
        'delete_keys': preview.data['delete_keys'],
    }, format='json')

    assert response.status_code == 409
    assert Project.objects.filter(pk=force_project.pk).exists()
    income.refresh_from_db()
    assert income.client_id == other_client.pk
    assert income.project_id == force_project.pk


def test_superuser_force_delete_without_csrf_is_rejected(superuser, force_project):
    """The new destructive body does not bypass session CSRF protection."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(superuser)

    response = client.delete(force_delete_url(force_project), {
        'force': True, 'confirmation': 'DELETE', 'impact_token': 'x' * 64, 'delete_keys': [],
    }, content_type='application/json')

    assert response.status_code == 403
    assert Project.objects.filter(pk=force_project.pk).exists()


@pytest.mark.parametrize(('method', 'url_factory'), [
    ('get', force_preview_url), ('delete', force_delete_url),
])
def test_superuser_jwt_cannot_use_forced_panel_deletion(api_client, superuser, force_project, method, url_factory):
    """A platform JWT never grants access to session-only forced deletion."""
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(superuser)}')

    response = getattr(api_client, method)(url_factory(force_project), {
        'force': True, 'confirmation': 'DELETE', 'impact_token': 'x' * 64, 'delete_keys': [],
    }, format='json')

    assert response.status_code == 403
    assert Project.objects.filter(pk=force_project.pk).exists()


def test_superuser_preview_returns_selected_project_with_impact_token(super_client, force_project):
    """Fails if a force preview stops binding the confirmation to its selected project."""
    proposal = BusinessProposal.objects.create(
        title='Default selection phase proposal', client_name='Forced deletion client',
    )
    ProjectPhase.objects.create(project=force_project, business_proposal=proposal, order=1)
    response = super_client.get(force_preview_url(force_project))

    assert response.status_code == 200
    assert response.data['project'] == {
        'id': force_project.pk,
        'name': 'Forced deletion project',
    }
    assert response.data['force'] is True
    assert len(response.data['impact_token']) == 64
    assert response.data['delete_keys'] == []
    assert response.data['dependencies'][0]['key'] == 'phases'
    assert response.data['dependencies'][0]['selected'] is False


def test_force_preview_applies_only_explicitly_selected_category(super_client, force_project):
    """Fails if a selected phase preview marks an unrelated deletion category for removal."""
    proposal = BusinessProposal.objects.create(
        title='Preview phase proposal', client_name='Forced deletion client',
    )
    ProjectPhase.objects.create(project=force_project, business_proposal=proposal, order=1)

    response = super_client.post(
        f'/api/projects/{force_project.pk}/delete-preview/',
        {'delete_keys': ['phases']},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['delete_keys'] == ['phases']
    selected_keys = [
        dependency['key'] for dependency in response.data['dependencies']
        if dependency['selected']
    ]
    phase = response.data['dependencies'][0]
    assert selected_keys == ['phases']
    assert phase['label'] == 'Fases comerciales'
    assert phase['description'] == 'Fases creadas desde propuestas. Las propuestas comerciales se conservan.'
    assert phase['count'] == 1
    assert phase['requires'] == []


def test_force_delete_requires_explicit_selection(super_client, force_project):
    """Fails if a legacy forced-delete payload can skip the explicit selection contract."""
    preview = super_client.get(force_preview_url(force_project))

    response = super_client.delete(
        force_delete_url(force_project),
        {
            'force': True,
            'confirmation': 'DELETE',
            'impact_token': preview.data['impact_token'],
        },
        format='json',
    )

    assert response.status_code == 400
    assert response.data == {
        'delete_keys': ['Elige explícitamente qué datos se eliminan; una lista vacía conserva todos.'],
    }
    assert Project.objects.filter(pk=force_project.pk).exists()


@pytest.mark.parametrize('payload', [
    {'force': True, 'delete_keys': []},
    {'force': True, 'confirmation': 'DELETE', 'delete_keys': []},
    {'force': True, 'confirmation': 'delete', 'impact_token': 'x' * 64, 'delete_keys': []},
    {'force': True, 'confirmation': ' DELETE', 'impact_token': 'x' * 64, 'delete_keys': []},
    {'force': True, 'confirmation': 'DELETE ', 'impact_token': 'x' * 64, 'delete_keys': []},
])
def test_force_delete_rejects_nonexact_confirmation(super_client, force_project, payload):
    """Fails if missing, lowercase, or padded DELETE can purge a project."""
    response = super_client.delete(force_delete_url(force_project), payload, format='json')

    assert response.status_code == 400
    assert Project.objects.filter(pk=force_project.pk).exists()
    assert DocumentFolder.objects.filter(project_id=force_project.pk).exists()


def test_force_delete_rejects_stale_preview_token(super_client, force_project):
    """Fails if a dependency added after preview can be deleted without reconfirmation."""
    preview = super_client.get(force_preview_url(force_project))
    document_type, _ = DocumentType.objects.get_or_create(
        code='force-delete-stale', defaults={'name': 'Force delete stale'},
    )
    document = Document.objects.create(
        project=force_project,
        document_type=document_type,
        title='Added after preview',
    )

    response = super_client.delete(
        force_delete_url(force_project),
        {
            'force': True,
            'confirmation': 'DELETE',
            'impact_token': preview.data['impact_token'],
            'delete_keys': [],
        },
        format='json',
    )

    assert response.status_code == 409
    assert response.data['code'] == 'stale_project_delete_preview'
    assert Project.objects.filter(pk=force_project.pk).exists()
    assert Document.objects.filter(pk=document.pk, project=force_project).exists()


def test_staff_cannot_preview_forced_project_deletion(admin_client, force_project):
    """Fails if an ordinary panel staff user can request a forced-delete preview."""
    response = admin_client.get(force_preview_url(force_project))

    assert response.status_code == 403
    assert Project.objects.filter(pk=force_project.pk).exists()


def test_staff_cannot_submit_forced_project_deletion(admin_client, force_project):
    """Fails if an ordinary panel staff user can submit a forced project deletion."""
    response = admin_client.delete(
        force_delete_url(force_project),
        {'force': True, 'confirmation': 'DELETE', 'impact_token': 'x' * 64, 'delete_keys': []},
        format='json',
    )

    assert response.status_code == 403
    assert Project.objects.filter(pk=force_project.pk).exists()
