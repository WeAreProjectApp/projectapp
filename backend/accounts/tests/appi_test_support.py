"""Shared persisted fixtures for Appi boundary tests."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Project, UserProfile
from accounts.models_ai import PlatformAICredential, PlatformAISettings, PlatformAITemplate
from accounts.models_appi import AppiConversation, AppiTurn
from accounts.services import appi_answers, appi_sources
from accounts.services.platform_ai_cipher import encrypt
from accounts.services.platform_ai_templates import defaults


def install_chat_templates():
    """Install the fixed template catalogue used by real Appi rendering."""
    for row in defaults():
        PlatformAITemplate.objects.get_or_create(
            family=row['family'], scenario=row['scenario'], language=row['language'],
            defaults={'content': row['content']},
        )


@pytest.fixture
def appi_context(settings, monkeypatch):
    """Return an enabled client, owned project, API client, and real templates."""
    settings.PLATFORM_AI_CIPHER_KEY = Fernet.generate_key()
    actor = get_user_model().objects.create_user('appi-owner', email='owner@appi.test')
    UserProfile.objects.update_or_create(
        user=actor, defaults={'role': UserProfile.ROLE_CLIENT, 'chatbot_enabled': True},
    )
    config, _ = PlatformAISettings.objects.update_or_create(
        pk=1, defaults={'chatbot_enabled': True, 'chatbot_cache_enabled': True},
    )
    PlatformAICredential.objects.create(provider='jev', encrypted_value=encrypt('jev-test-key'))
    PlatformAICredential.objects.create(provider='anthropic', encrypted_value=encrypt('anthropic-test-key'))
    PlatformAICredential.objects.create(provider='openai', encrypted_value=encrypt('openai-test-key'))
    install_chat_templates()
    project = Project.objects.create(client=actor, name='Appi project', progress=25)
    monkeypatch.setattr('accounts.tasks_appi.process_appi_turn', lambda turn_id: None)
    api = APIClient()
    api.force_authenticate(actor)
    return SimpleNamespace(actor=actor, project=project, config=config, api=api)


def conversation(context, *, project=None):
    """Create an unexpired persisted conversation for an owned project."""
    return AppiConversation.objects.create(
        actor=context.actor,
        project=context.project if project is None else project,
        language='es',
        expires_at=timezone.now() + timedelta(days=1),
    )


def ready_turn(context, item, *, query=None, dependencies='', answer=None, exact_key='exact-key'):
    """Persist one ready Appi response with a concrete request id."""
    query = query or {'scenario': 'project_status', 'topic': 'general', 'explain': False}
    answer = answer or {'text': 'Appi project: 25 %.', 'project_ids': [context.project.pk]}
    return AppiTurn.objects.create(
        conversation=item,
        actor=context.actor,
        request_id=uuid4(),
        request_fingerprint=appi_sources.digest({'request': str(uuid4())}),
        question='Estado del proyecto',
        language='es',
        status='ready',
        query=query,
        answer=answer,
        dependencies=dependencies,
        context_key=appi_sources.digest({}),
        exact_key=exact_key,
        expires_at=item.expires_at,
    )


def project_status_data(context):
    """Build the source projection through the production whitelist."""
    query = {'scenario': 'project_status', 'topic': 'general', 'explain': True}
    return query, appi_sources.snapshot(context.actor, context.project.pk, query, 'es')


def answer_dependencies(context, query, data):
    """Return the persisted dependency fingerprint for a current projection."""
    return appi_answers.dependencies(query, data, 'es', config=context.config)


def ready_history(context, item, count):
    """Create current, equivalent rows for a history query-budget comparison."""
    query, data = project_status_data(context)
    dependencies = answer_dependencies(context, query, data)
    answer = {'text': 'Appi project: 25 %.', 'project_ids': data['project_ids']}
    return [ready_turn(context, item, query=query, dependencies=dependencies, answer=answer,
                       exact_key=f'history-{index}') for index in range(count)]


def select_count(captured):
    """Count SELECT statements without making a timing-based performance assertion."""
    return sum(query['sql'].lstrip().upper().startswith('SELECT') for query in captured.captured_queries)


def grant_cache_admin(context):
    """Give the fixture owner the administrative authority required to invalidate a cache."""
    context.actor.is_staff = True
    context.actor.save(update_fields=['is_staff'])
