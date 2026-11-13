"""Single precedence and write boundary for Panel, MCP and client availability."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, F, Subquery
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from accounts.feature_catalog import CATALOG, FEATURES
from accounts.models_feature_flags import (
    ClientPlatformFeatureSettings, PlatformFeatureEvent, PlatformFeatureSettings,
)
from accounts.services.project_collaboration_access import paginate


class FeatureConflict(APIException):
    status_code = 409
    default_detail = 'La configuración cambió. Actualiza antes de guardar.'
    default_code = 'feature_conflict'


class FeatureDisabled(PermissionDenied):
    def __init__(self, key):
        super().__init__({'code': 'feature_disabled', 'feature': key,
                          'detail': 'Esta funcionalidad no está disponible para tu cuenta.'})


def require_admin(actor):
    if not actor or not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied('Solo un administrador del Panel puede gestionar funcionalidades.')


def client(user_id):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise ValidationError('Identificador de cliente inválido.') from None
    if user_id < 1:
        raise ValidationError('Identificador de cliente inválido.')
    user = get_user_model().objects.filter(pk=user_id, profile__role='client').first()
    if user is None:
        raise NotFound('Cliente no encontrado.')
    return user


def lock_global():
    PlatformFeatureSettings.objects.get_or_create(pk=1)
    return PlatformFeatureSettings.objects.select_for_update().get(pk=1)


def configuration(user_id=None):
    if user_id is None:
        return PlatformFeatureSettings.objects.filter(pk=1).first() or PlatformFeatureSettings(pk=1)
    return (ClientPlatformFeatureSettings.objects.filter(user_id=user_id).first()
            or ClientPlatformFeatureSettings(user_id=user_id))


def values_for(user_id=None):
    if user_id is None:
        return merge_values(configuration().values, {})
    user = get_user_model().objects.select_related('platform_feature_settings').annotate(
        _global_feature_values=Subquery(PlatformFeatureSettings.objects.filter(pk=1).values('values')[:1]),
    ).get(pk=user_id)
    return values_from_user(user)


def merge_values(defaults, overrides):
    return {key: overrides.get(key, defaults.get(key, item['default_enabled']))
            for key, item in FEATURES.items()}


def profile_queryset():
    from accounts.models import UserProfile
    return UserProfile.objects.select_related('user', 'user__platform_feature_settings').annotate(
        _global_feature_values=Subquery(PlatformFeatureSettings.objects.filter(pk=1).values('values')[:1]),
    )


def values_from_user(user, defaults=None):
    scope = getattr(user, 'platform_feature_settings', None)
    global_values = getattr(user, '_global_feature_values', {}) if defaults is None else defaults
    return merge_values(global_values or {}, scope.values if scope else {})


def values_from_profile(profile):
    return values_from_user(profile.user, profile._global_feature_values or {})


def request_values(request):
    from accounts.authentication import SessionJWTAuthentication
    if isinstance(request.successful_authenticator, SessionJWTAuthentication):
        return request.user._platform_feature_values
    return values_for(request.user.pk)


def enabled(actor, key, *, request=None):
    if key not in FEATURES:
        raise ValidationError('Clave de funcionalidad desconocida.')
    if not actor or not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied('Se requiere una cuenta activa.')
    profile = (getattr(actor, 'profile', None) if request is not None
               else profile_queryset().filter(user_id=actor.pk).first())
    role = profile.role if profile else None
    if role == 'admin':
        return True
    if role != 'client':
        raise PermissionDenied('Se requiere una cuenta de Plataforma.')
    return (request_values(request) if request is not None else values_from_profile(profile))[key]


def require_feature(actor, key, *, request=None):
    if not enabled(actor, key, request=request):
        raise FeatureDisabled(key)


def payload(actor, user_id=None):
    require_admin(actor)
    user = client(user_id) if user_id is not None else None
    defaults = configuration()
    scope = defaults if user_id is None else configuration(user_id)
    result = []
    for key, item in FEATURES.items():
        global_value = defaults.values.get(key, item['default_enabled'])
        override = scope.values.get(key) if user else None
        result.append({**item, 'global_value': global_value, 'override': override,
                       'effective': global_value if override is None else override,
                       'source': 'client' if override is not None else 'global'})
    return {'catalog_version': CATALOG['version'], 'version': scope.version,
            'global_version': defaults.version, 'user_id': user.pk if user else None,
            'name': (user.get_full_name() or user.email) if user else None, 'features': result}


def validate_changes(data, *, client_scope):
    if not isinstance(data, dict):
        raise ValidationError('Se requiere un objeto de configuración.')
    if set(data) - {'expected_version', 'values'}:
        raise ValidationError('Campos de configuración desconocidos.')
    version, values = data.get('expected_version'), data.get('values')
    if type(version) is not int or version < 0:
        raise ValidationError({'expected_version': 'Indica la versión vigente.'})
    if not isinstance(values, dict) or not values or set(values) - FEATURES.keys():
        raise ValidationError({'values': 'Indica al menos una clave conocida.'})
    if any(type(value) is not bool and not (client_scope and value is None) for value in values.values()):
        raise ValidationError({'values': 'Usa true/false; null permite heredar solo por cliente.'})
    return version, values


def sync_legacy(values, user_id):
    """Keep deprecated projections/version tokens current; evaluation never reads them."""
    from accounts.models import UserProfile
    from accounts.models_ai import PlatformAISettings
    from accounts.models_platform_help import ClientPlatformHelpSettings, PlatformHelpSettings
    ai = {'platform.ai_chatbot': 'chatbot_enabled', 'platform.ai_voice_reports': 'voice_reporting_enabled'}
    help_flags = {'platform.help_tours': 'tour_enabled', 'platform.help_videos': 'video_enabled'}
    effective = values_for(user_id)
    ai_values = {field: effective[key] for key, field in ai.items() if key in values}
    help_values = {field: effective[key] for key, field in help_flags.items() if key in values}
    if user_id is None:
        if any(key.startswith('platform.ai_') for key in values):
            PlatformAISettings.objects.get_or_create(pk=1)
            PlatformAISettings.objects.filter(pk=1).update(**ai_values, version=F('version') + 1)
        if help_values:
            PlatformHelpSettings.objects.get_or_create(pk=1)
            PlatformHelpSettings.objects.filter(pk=1).update(**help_values, version=F('version') + 1)
    else:
        UserProfile.objects.filter(user_id=user_id).update(**ai_values, updated_at=timezone.now())
        if help_values:
            ClientPlatformHelpSettings.objects.get_or_create(user_id=user_id)
            ClientPlatformHelpSettings.objects.filter(user_id=user_id).update(**help_values, version=F('version') + 1)


@transaction.atomic
def update(actor, data, user_id=None):
    require_admin(actor)
    version, values = validate_changes(data, client_scope=user_id is not None)
    # The singleton lock also serializes first creation of a client's scope.
    global_config = lock_global()
    scope = global_config
    if user_id is not None:
        user = client(user_id)
        scope, _ = ClientPlatformFeatureSettings.objects.get_or_create(user=user)
        scope = ClientPlatformFeatureSettings.objects.select_for_update().get(pk=scope.pk)
    if scope.version != version:
        raise FeatureConflict()
    changes = {key: {'before': scope.values.get(key), 'after': value} for key, value in values.items()}
    scope.values = dict(scope.values)
    for key, value in values.items():
        if value is None:
            scope.values.pop(key, None)
        else:
            scope.values[key] = value
    scope.version += 1
    scope.save()
    sync_legacy(values, user_id)
    PlatformFeatureEvent.objects.create(actor=actor, client_id=user_id,
                                       scope='client' if user_id is not None else 'global',
                                       changes=changes, version=scope.version)
    return payload(actor, user_id)


def list_clients(actor, page=1, search=''):
    require_admin(actor)
    if len(search) > 200:
        raise ValidationError('La búsqueda admite hasta 200 caracteres.')
    qs = get_user_model().objects.filter(profile__role='client').filter(
        Q(email__icontains=search) | Q(first_name__icontains=search)
        | Q(last_name__icontains=search) | Q(profile__company_name__icontains=search)).order_by('pk')
    return paginate(qs, page, lambda user: {'user_id': user.pk, 'name': user.get_full_name() or user.email})


def events(actor, page=1, user_id=None):
    require_admin(actor)
    qs = PlatformFeatureEvent.objects.all()
    if user_id is not None:
        client(user_id)
        qs = qs.filter(client_id=user_id)
    return paginate(qs, page, lambda event: {'id': event.pk, 'actor_id': event.actor_id,
        'client_id': event.client_id, 'scope': event.scope, 'changes': event.changes,
        'version': event.version, 'created_at': event.created_at})
