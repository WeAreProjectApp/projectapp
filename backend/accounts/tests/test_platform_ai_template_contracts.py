"""Panel contracts for previewing and versioning Platform AI templates."""
import pytest
from django.middleware.csrf import get_token
from django.test import RequestFactory
from rest_framework.test import APIClient

from accounts.models_ai import (
    PlatformAIEvent,
    PlatformAITemplate,
    PlatformAITemplateRevision,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def panel_admin(admin_user):
    """Create an administrator allowed to change Platform AI settings."""
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    return admin_user


@pytest.fixture
def panel_client(panel_admin):
    """Build a panel session with a valid CSRF token."""
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(panel_admin)
    request = RequestFactory().get('/')
    csrf_token = get_token(request)
    client.cookies['csrftoken'] = request.META['CSRF_COOKIE']
    return client, {'HTTP_X_CSRFTOKEN': csrf_token}


def template_for(family, scenario, content, version=1):
    """Create an explicitly versioned template with its matching revision."""
    template, _ = PlatformAITemplate.objects.get_or_create(
        family=family, scenario=scenario, language='es', defaults={'content': content, 'version': version},
    )
    template.content = content
    template.version = version
    template.save(update_fields=['content', 'version', 'updated_at'])
    template.revisions.all().delete()
    PlatformAITemplateRevision.objects.create(template=template, version=version, content=content)
    return template


def chat_template(content='{scope_label}\n\n{facts_text}', version=1):
    """Create a project-status template with the required chat placeholders."""
    return template_for('chatbot', 'project_status', content, version)


def test_template_preview_renders_the_allowed_chat_slots(panel_client):
    """Fails if template preview calls a provider instead of rendering the local sample."""
    client, headers = panel_client
    template = chat_template()

    response = client.post(
        f'/api/platform/ai/admin/templates/{template.pk}/preview/',
        {'expected_version': 1, 'content': 'Estado de {scope_label}: {facts_text}'},
        format='json',
        **headers,
    )

    assert response.status_code == 200, response.data
    assert response['Cache-Control'] == 'no-store'
    assert response.json() == {
        'preview': 'Estado de scope label: facts text', 'provider_called': False,
    }
    assert template.revisions.count() == 1


def test_template_patch_creates_a_reviewable_revision(panel_client, panel_admin):
    """Fails if saving revised instructions overwrites the only reviewed template version."""
    client, headers = panel_client
    template = chat_template()

    response = client.patch(
        f'/api/platform/ai/admin/templates/{template.pk}/',
        {'expected_version': 1, 'content': 'Proyecto {scope_label}\n{facts_text}'},
        format='json',
        **headers,
    )

    template.refresh_from_db()
    revision = template.revisions.get(version=2)
    assert response.status_code == 200, response.data
    assert template.version == 2
    assert template.content == 'Proyecto {scope_label}\n{facts_text}'
    assert revision.content == template.content
    assert revision.actor == panel_admin
    assert PlatformAIEvent.objects.get(action='template.update').metadata == {'version': 2}


def test_template_restore_preserves_the_revised_history(panel_client):
    """Fails if restoring a template destroys the instruction version selected by the operator."""
    client, headers = panel_client
    template = chat_template('Primero {scope_label}\n{facts_text}', version=2)
    PlatformAITemplateRevision.objects.create(
        template=template, version=1, content='{scope_label}\n\n{facts_text}',
    )

    response = client.post(
        f'/api/platform/ai/admin/templates/{template.pk}/restore/',
        {'expected_version': 2, 'version': 1}, format='json', **headers,
    )

    template.refresh_from_db()
    assert response.status_code == 200, response.data
    assert template.version == 3
    assert template.content == '{scope_label}\n\n{facts_text}'
    assert list(template.revisions.order_by('version').values_list('version', 'content')) == [
        (1, '{scope_label}\n\n{facts_text}'),
        (2, 'Primero {scope_label}\n{facts_text}'),
        (3, '{scope_label}\n\n{facts_text}'),
    ]
    assert PlatformAIEvent.objects.get(action='template.restore').metadata == {'version': 3}


def test_template_patch_rejects_a_stale_version_without_creating_a_revision(panel_client):
    """Fails if an outdated template editor can append an instruction revision."""
    client, headers = panel_client
    template = chat_template(version=2)

    response = client.patch(
        f'/api/platform/ai/admin/templates/{template.pk}/',
        {'expected_version': 1, 'content': 'Actualizado {scope_label}\n{facts_text}'},
        format='json',
        **headers,
    )

    template.refresh_from_db()
    assert response.status_code == 409
    assert template.version == 2
    assert template.revisions.count() == 1
    assert PlatformAIEvent.objects.filter(action='template.update').count() == 0


def test_template_preview_rejects_missing_required_slots(panel_client):
    """Fails if preview accepts a chatbot template that discards structured project facts."""
    client, headers = panel_client
    template = chat_template()

    response = client.post(
        f'/api/platform/ai/admin/templates/{template.pk}/preview/',
        {'expected_version': 1, 'content': 'Estado de {scope_label}'}, format='json', **headers,
    )

    assert response.status_code == 400
    assert template.revisions.count() == 1
    assert PlatformAIEvent.objects.filter(action='template.update').count() == 0


def test_report_template_patch_saves_plain_voice_instructions(panel_client):
    """Fails if a voice report template is forced to contain chatbot-only placeholders."""
    client, headers = panel_client
    template = template_for('report', 'bug', 'Instrucción inicial.')

    response = client.patch(
        f'/api/platform/ai/admin/templates/{template.pk}/',
        {'expected_version': 1, 'content': 'Describe el fallo sin inventar una causa.'},
        format='json',
        **headers,
    )

    template.refresh_from_db()
    assert response.status_code == 200, response.data
    assert template.content == 'Describe el fallo sin inventar una causa.'
    assert template.version == 2
    assert template.revisions.get(version=2).content == template.content


def test_template_versions_return_the_most_recent_revision_first(panel_client):
    """Fails if panel reviewers see an older template revision before the active revision."""
    client, _ = panel_client
    template = chat_template('Nueva {scope_label}\n{facts_text}', version=2)
    PlatformAITemplateRevision.objects.create(
        template=template, version=1, content='{scope_label}\n\n{facts_text}',
    )

    response = client.get(f'/api/platform/ai/admin/templates/{template.pk}/versions/')

    assert response.status_code == 200
    assert [item['version'] for item in response.json()] == [2, 1]
    assert response.json()[0]['content'] == 'Nueva {scope_label}\n{facts_text}'


def test_template_restore_rejects_a_missing_revision(panel_client):
    """Fails if restoring an unknown version changes the template selected by the operator."""
    client, headers = panel_client
    template = chat_template()

    response = client.post(
        f'/api/platform/ai/admin/templates/{template.pk}/restore/',
        {'expected_version': 1, 'version': 9}, format='json', **headers,
    )

    template.refresh_from_db()
    assert response.status_code == 404
    assert template.version == 1
    assert template.revisions.count() == 1
    assert PlatformAIEvent.objects.filter(action='template.restore').count() == 0
