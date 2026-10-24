"""Disposable Redis indexes point to private, revalidated historical turns."""
import uuid

from django.core.cache import cache
from django.utils import timezone
from redis.exceptions import RedisError

from accounts.models_appi import AppiTurn
from accounts.services.appi_sources import digest


def _key(actor, project_id, kind, value, config):
    return 'appi:index:' + digest({'actor': actor.pk, 'project': project_id, 'kind': kind, 'value': value,
                                  'epoch': config.cache_epoch})


def lookup(actor, project_id, kind, value, config):
    if not config.chatbot_cache_enabled:
        return None
    try:
        turn_id = cache.get(_key(actor, project_id, kind, value, config))
    except (RedisError, OSError, ValueError, TypeError):
        return None
    if not turn_id:
        return None
    try:
        turn_id = uuid.UUID(str(turn_id))
    except (ValueError, TypeError, AttributeError):
        return None
    return AppiTurn.objects.filter(pk=turn_id, actor=actor, conversation__project_id=project_id,
        conversation__expires_at__gt=timezone.now(), status='ready', expires_at__gt=timezone.now()).first()


def remember(turn, config):
    if not config.chatbot_cache_enabled:
        return
    seconds = min(config.chatbot_cache_hours * 3600, int((turn.expires_at - timezone.now()).total_seconds()))
    if seconds <= 0:
        return
    values = {
        _key(turn.actor, turn.conversation.project_id, 'exact', turn.exact_key, config): str(turn.pk),
        _key(turn.actor, turn.conversation.project_id, 'typed', turn.dependencies, config): str(turn.pk),
    }
    try:
        cache.set_many(values, timeout=seconds)
    except (RedisError, OSError, ValueError, TypeError):
        pass  # Historical DB lookup remains available if disposable Redis is down.
