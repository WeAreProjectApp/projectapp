"""Shared feature gates, configuration and write-only credentials."""
from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from accounts.models import UserProfile, Project
from accounts.models_ai import PlatformAISettings, PlatformAICredential, PlatformAIEvent, PlatformAIUsage
from accounts.serializers_ai import SettingsSerializer, ClientFlagsSerializer, validated
from accounts.services.platform_ai_cipher import encrypt, decrypt


class AIUnavailable(APIException):
    status_code = 503
    default_detail = 'La función de IA no está disponible. Puedes continuar escribiendo.'
    default_code = 'ai_unavailable'


class AIConflict(APIException):
    status_code = 409
    default_detail = 'La configuración cambió. Actualiza antes de guardar.'
    default_code = 'ai_conflict'


def require_admin(actor):
    if not actor or not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied('Solo un administrador del panel puede realizar esta operación.')


def check_version(actual, expected):
    if str(actual) != str(expected):
        raise AIConflict()


def event(actor, action, target, metadata=None):
    PlatformAIEvent.objects.create(actor=actor, action=action, target=target, metadata=metadata or {})


def configuration(*, lock=False):
    qs = PlatformAISettings.objects.select_for_update() if lock else PlatformAISettings.objects
    item = qs.filter(pk=1).first()
    return item or PlatformAISettings(pk=1)


def provider_for_model(model):
    if model not in ('claude-haiku-5-5', 'gpt-6-luna'):
        raise ValidationError('Modelo no admitido.')
    return 'anthropic' if model == 'claude-haiku-5-5' else 'openai'


def credential_status():
    rows = {row.provider: row for row in PlatformAICredential.objects.all()}
    return {provider: {'configured': bool(rows.get(provider) and rows[provider].encrypted_value),
                       'version': rows[provider].version if provider in rows else 0,
                       'last_test_status': rows[provider].last_test_status if provider in rows else '',
                       'tested_at': rows[provider].tested_at if provider in rows else None}
            for provider in ('anthropic', 'openai', 'jev')}


def credential(provider):
    if provider not in ('anthropic', 'openai', 'jev'):
        raise ValidationError('Proveedor no admitido.')
    value = PlatformAICredential.objects.filter(provider=provider).values_list('encrypted_value', flat=True).first()
    if not value:
        raise AIUnavailable()
    try:
        return decrypt(value)
    except Exception as exc:
        from django.core.exceptions import ImproperlyConfigured
        if isinstance(exc, ImproperlyConfigured):
            raise AIUnavailable() from None
        raise


def ai_capabilities(actor):
    from django.contrib.auth import get_user_model
    if not actor or not actor.is_authenticated or not actor.is_active or not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists():
        raise PermissionDenied('Se requiere una cuenta activa.')
    # Never reuse actor.profile's relation cache across a billed request.
    profile = UserProfile.objects.filter(user_id=actor.pk).first()
    config = configuration()
    keys = credential_status()
    client = bool(profile and profile.is_client)
    result = {}
    for name, flag, model in [('chatbot', 'chatbot_enabled', config.chatbot_model),
                              ('voice_reporting', 'voice_reporting_enabled', config.voice_report_model)]:
        enabled = bool(client and getattr(config, flag) and getattr(profile, flag))
        ready = keys[provider_for_model(model)]['configured']
        if name == 'chatbot':
            ready = ready and keys['jev']['configured']
        else:
            ready = ready and keys['openai']['configured']
        result[name] = {'enabled': enabled, 'available': bool(enabled and ready)}
    result['chatbot']['voice_available'] = bool(result['chatbot']['available'] and keys['openai']['configured'])
    from accounts.services.platform_ai_quota import snapshot
    result['quota'] = snapshot(actor, config)
    return result


def require_ai_feature(actor, feature, project=None, *, audio=False, require_project=True):
    if feature not in ('chatbot', 'voice_reporting'):
        raise ValidationError('Funcionalidad no admitida.')
    capabilities = ai_capabilities(actor)[feature]
    if not capabilities['enabled']:
        raise PermissionDenied('Esta funcionalidad está apagada.')
    if not capabilities['available'] or (audio and feature == 'chatbot' and not capabilities['voice_available']):
        raise AIUnavailable()
    if project is not None:
        from accounts.services.project_collaboration_access import project_for_actor
        return project_for_actor(project.pk if hasattr(project, 'pk') else project, actor)
    if (require_project or feature != 'chatbot') and not Project.objects.filter(client_id=actor.pk).exists():
        raise PermissionDenied('No hay proyectos disponibles.')
    return None


def admin_settings(actor):
    require_admin(actor)
    return {**SettingsSerializer(configuration()).data, 'credentials': credential_status()}


@transaction.atomic
def update_settings(actor, data):
    require_admin(actor)
    values = validated(SettingsSerializer, data)
    item, _ = PlatformAISettings.objects.get_or_create(pk=1)
    item = PlatformAISettings.objects.select_for_update().get(pk=1)
    check_version(item.version, values.pop('expected_version'))
    for field, value in values.items():
        setattr(item, field, value)
    item.version += 1
    item.save()
    event(actor, 'settings.update', 'global', {'fields': sorted(values), 'version': item.version})
    return admin_settings(actor)


def client_data(profile):
    return {'user_id': profile.user_id, 'name': profile.user.get_full_name() or profile.user.email,
            'chatbot_enabled': profile.chatbot_enabled, 'voice_reporting_enabled': profile.voice_reporting_enabled,
            'ai_request_limit': profile.ai_request_limit, 'ai_window_minutes': profile.ai_window_minutes,
            'version': profile.updated_at.isoformat()}


@transaction.atomic
def client_flags(actor, user_id, data=None):
    require_admin(actor)
    profile = UserProfile.objects.clients().select_related('user').filter(user_id=user_id)
    profile = (profile.select_for_update() if data is not None else profile).first()
    if not profile:
        raise NotFound('Cliente no encontrado.')
    if data is not None:
        values = validated(ClientFlagsSerializer, data)
        check_version(profile.updated_at.isoformat(), values.pop('expected_version'))
        for field, value in values.items():
            setattr(profile, field, value)
        if (profile.ai_request_limit is None) != (profile.ai_window_minutes is None):
            raise ValidationError('Define cupo y ventana juntos, o deja ambos vacíos para heredar.')
        profile.save(update_fields=[*values, 'updated_at'])
        event(actor, 'client.update', str(user_id), {'fields': sorted(values)})
    return client_data(profile)


@transaction.atomic
def set_credential(actor, provider, *, expected_version, api_key=None, encrypted_value=None, remove=False):
    require_admin(actor)
    if provider not in ('anthropic', 'openai', 'jev'):
        raise ValidationError('Proveedor no admitido.')
    # Lock the singleton also serializes creation before a credential row exists.
    config, _ = PlatformAISettings.objects.get_or_create(pk=1)
    PlatformAISettings.objects.select_for_update().get(pk=config.pk)
    item = PlatformAICredential.objects.select_for_update().filter(provider=provider).first()
    check_version(item.version if item else 0, expected_version)
    value = '' if remove else encrypted_value or encrypt(api_key)
    if value:
        decrypt(value)  # A prepared MCP secret must belong to this server's key.
    if item is None:
        item = PlatformAICredential(provider=provider, version=0)
    item.encrypted_value = value
    item.version += 1
    item.last_test_status = ''
    item.tested_at = None
    item.save()
    event(actor, 'credential.delete' if remove else 'credential.set', provider, {'version': item.version})
    return credential_status()[provider]


@transaction.atomic
def invalidate_cache(actor, function):
    require_admin(actor)
    if function not in ('chatbot', 'voice_report', 'all'):
        raise ValidationError('Función no admitida.')
    config, _ = PlatformAISettings.objects.get_or_create(pk=1)
    config = PlatformAISettings.objects.select_for_update().get(pk=config.pk)
    config.cache_epoch += 1
    config.version += 1
    config.save(update_fields=['cache_epoch', 'version', 'updated_at'])
    event(actor, 'cache.invalidate', function)
    return {'invalidated': True, 'cache_epoch': config.cache_epoch}


def usage_summary(actor):
    require_admin(actor)
    now = timezone.now()
    rows = PlatformAIUsage.objects.filter(created_at__gte=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    return {'month': now.strftime('%Y-%m'), 'groups': list(rows.values('purpose', 'provider', 'model', 'status').annotate(
        requests=Count('id'), audio_seconds=Sum('audio_seconds'), input_tokens=Sum('input_tokens'),
        output_tokens=Sum('output_tokens'), cache_read_tokens=Sum('cache_read_tokens'),
        cache_write_tokens=Sum('cache_write_tokens'), estimated_cost=Sum('estimated_cost')))}
