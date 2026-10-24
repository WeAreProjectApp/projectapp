"""Disposable Appi cache indexes remain exact, typed, and chatbot-versioned."""
import pytest
from django.contrib.auth import get_user_model

from accounts.models import Project, UserProfile
from accounts.services import appi_cache
from accounts.services import appi
from accounts.services.platform_ai import cache_version, invalidate_cache

from .appi_test_support import conversation, grant_cache_admin, ready_turn

pytest_plugins = ('accounts.tests.appi_test_support',)
pytestmark = pytest.mark.django_db


def test_cache_index_reuses_only_the_same_exact_or_typed_value(appi_context):
    """Fails if an Appi cache key drops the question type or serves a neighbouring value."""
    item = conversation(appi_context)
    turn = ready_turn(appi_context, item, exact_key='estado exacto', dependencies='typed-status')
    version = cache_version('chatbot', appi_context.config)

    appi_cache.remember(turn, appi_context.config, actor=appi_context.actor, project_id=appi_context.project.pk, version=version)

    assert appi_cache.lookup(appi_context.actor, appi_context.project.pk, 'exact', 'estado exacto', appi_context.config, version).pk == turn.pk
    assert appi_cache.lookup(appi_context.actor, appi_context.project.pk, 'typed', 'typed-status', appi_context.config, version).pk == turn.pk
    assert appi_cache.lookup(appi_context.actor, appi_context.project.pk, 'exact', 'estado parecido', appi_context.config, version) is None


def test_disabled_chatbot_cache_never_reads_a_hot_entry(appi_context):
    """Fails if disabling the chatbot cache still exposes an already indexed answer."""
    item = conversation(appi_context)
    turn = ready_turn(appi_context, item, exact_key='estado actual', dependencies='typed-current')
    version = cache_version('chatbot', appi_context.config)
    appi_cache.remember(turn, appi_context.config, actor=appi_context.actor, project_id=appi_context.project.pk, version=version)
    appi_context.config.chatbot_cache_enabled = False

    cached = appi_cache.lookup(appi_context.actor, appi_context.project.pk, 'exact', 'estado actual', appi_context.config, version)

    assert cached is None


def test_warmed_owner_cache_cannot_serve_another_clients_identical_question(appi_context):
    """Fails if a warmed private answer can cross the actor or project boundary on the same question."""
    owner_conversation = conversation(appi_context)
    owner_turn = ready_turn(
        appi_context,
        owner_conversation,
        exact_key='estado compartido',
        dependencies='owner-only-status',
        answer={'text': 'OWNER ONLY STATUS', 'project_ids': [appi_context.project.pk]},
    )
    version = cache_version('chatbot', appi_context.config)
    appi_cache.remember(owner_turn, appi_context.config, actor=appi_context.actor,
                        project_id=appi_context.project.pk, version=version)
    other = get_user_model().objects.create_user('cache-other', email='cache-other@appi.test')
    UserProfile.objects.update_or_create(
        user=other,
        defaults={'role': UserProfile.ROLE_CLIENT, 'chatbot_enabled': True},
    )
    other_project = Project.objects.create(client=other, name='Other cache project')
    other_conversation = appi.create_conversation(other, {'project_id': other_project.pk, 'language': 'es'})

    cached = appi._cached(other, other_conversation, 'estado compartido', appi_context.config, version)

    assert cached is None


def test_changed_chatbot_version_misses_the_previous_hot_key(appi_context):
    """Fails if invalidating chatbot cache leaves the former Redis index reusable."""
    item = conversation(appi_context)
    turn = ready_turn(appi_context, item, exact_key='estado versionado', dependencies='typed-versioned')
    before = cache_version('chatbot', appi_context.config)
    appi_cache.remember(turn, appi_context.config, actor=appi_context.actor, project_id=appi_context.project.pk, version=before)
    grant_cache_admin(appi_context)
    invalidate_cache(appi_context.actor, 'chatbot')
    after = cache_version('chatbot')

    assert after != before
    assert appi_cache.lookup(appi_context.actor, appi_context.project.pk, 'exact', 'estado versionado', appi_context.config, after) is None


def test_voice_only_invalidation_preserves_the_chatbot_hot_key(appi_context):
    """Fails if voice cache maintenance evicts a current chatbot answer unnecessarily."""
    item = conversation(appi_context)
    turn = ready_turn(appi_context, item, exact_key='estado aislado', dependencies='typed-isolated')
    before = cache_version('chatbot', appi_context.config)
    appi_cache.remember(turn, appi_context.config, actor=appi_context.actor, project_id=appi_context.project.pk, version=before)
    grant_cache_admin(appi_context)
    invalidate_cache(appi_context.actor, 'voice_report')
    after = cache_version('chatbot')

    cached = appi_cache.lookup(appi_context.actor, appi_context.project.pk, 'exact', 'estado aislado', appi_context.config, after)

    assert after == before
    assert cached.pk == turn.pk
