"""One domain boundary for the client, panel and projects MCP."""
from copy import deepcopy
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from accounts.models_platform_help import (
    ClientPlatformHelpSettings, PlatformGuidedTour, PlatformGuidedTourRevision,
    PlatformHelpEvent, PlatformHelpSettings, PlatformTourProgress,
)
from accounts.serializers_platform_help import (
    HelpFlagsSerializer, TourContentSerializer, TourProgressSerializer,
    TourVersionSerializer, TourWriteSerializer, validated,
)
from accounts.services.platform_help_targets import TARGETS, target_available
from accounts.services.project_collaboration_access import check_version, paginate, project_for_actor


def require_admin(actor):
    if not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied('Solo los administradores pueden gestionar Ayuda.')


def require_client(actor):
    profile = getattr(actor, 'profile', None)
    if not actor.is_authenticated or not actor.is_active or not profile or not profile.is_client or not profile.is_onboarded:
        raise PermissionDenied('Se requiere una cuenta activa de cliente.')
    return profile


def _flags(instance):
    return {'tour_enabled': instance.tour_enabled if instance else True,
            'video_enabled': instance.video_enabled if instance else True,
            'version': instance.version if instance else 0}


def effective_flags(user):
    require_client(user)
    global_flags = _flags(PlatformHelpSettings.objects.filter(pk=1).first())
    client_flags = _flags(ClientPlatformHelpSettings.objects.filter(user=user).first())
    return {key: global_flags[key] and client_flags[key] for key in ('tour_enabled', 'video_enabled')}


def effective_video_enabled(user):
    return effective_flags(user)['video_enabled']


def effective_tour_enabled(user):
    return effective_flags(user)['tour_enabled']


def _capabilities(user):
    # Help also works before the independently delivered AI feature is installed.
    try:
        from accounts.services.platform_ai import ai_capabilities
    except ModuleNotFoundError as error:
        if error.name != 'accounts.services.platform_ai':
            raise
        return {}
    return ai_capabilities(user)


def _event(actor, action, subject, changes):
    PlatformHelpEvent.objects.create(actor=actor, action=action, subject=str(subject), changes=changes)


def settings_payload(actor):
    require_admin(actor)
    return _flags(PlatformHelpSettings.objects.filter(pk=1).first())


def _client(user_id):
    return get_user_model().objects.select_related('profile').filter(pk=user_id, profile__role='client').first()


def client_payload(actor, user_id):
    require_admin(actor)
    user = _client(user_id)
    if not user:
        raise NotFound('Cliente no encontrado.')
    return {'user_id': user.pk, 'name': user.get_full_name() or user.email,
            **_flags(ClientPlatformHelpSettings.objects.filter(user=user).first())}


def list_clients(actor, page=1, search=''):
    require_admin(actor)
    users = get_user_model().objects.filter(profile__role='client').select_related('platform_help_settings').order_by('pk')
    if search:
        users = users.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))
    return paginate(users, page, lambda user: {'user_id': user.pk, 'name': user.get_full_name() or user.email,
                                            **_flags(getattr(user, 'platform_help_settings', None))})


@transaction.atomic
def update_flags(actor, data, user_id=None):
    require_admin(actor)
    values = validated(HelpFlagsSerializer, data)
    if user_id is None:
        instance, _ = PlatformHelpSettings.objects.get_or_create(pk=1)
    else:
        user = _client(user_id)
        if not user:
            raise NotFound('Cliente no encontrado.')
        instance, _ = ClientPlatformHelpSettings.objects.get_or_create(user=user)
    instance = type(instance).objects.select_for_update().get(pk=instance.pk)
    check_version(instance, values.pop('expected_version'))
    for key, value in values.items():
        setattr(instance, key, value)
    instance.version += 1
    instance.save()
    _event(actor, 'update_flags', f'client:{user_id}' if user_id else 'global', values)
    return _flags(instance)


def _tour(tour_id, lock=False):
    qs = PlatformGuidedTour.objects.select_for_update() if lock else PlatformGuidedTour.objects
    tour = qs.filter(pk=tour_id).first()
    if not tour:
        raise NotFound('Recorrido no encontrado.')
    return tour


def tour_payload(tour):
    return {'id': tour.pk, 'slug': tour.slug, 'context': tour.context, 'kind': tour.kind,
            'priority': tour.priority, 'is_active': tour.is_active, 'content': tour.draft,
            'published_revision': tour.published_revision, 'version': tour.version}


def admin_catalog(actor):
    require_admin(actor)
    return {'results': [tour_payload(tour) for tour in PlatformGuidedTour.objects.order_by('priority', 'pk')],
            'targets': TARGETS}


def get_tour(actor, tour_id):
    require_admin(actor)
    return tour_payload(_tour(tour_id))


def _validate_content(content, context):
    values = validated(TourContentSerializer, content)
    if any(TARGETS[step['target']]['context'] != context for step in values['steps']):
        raise ValidationError({'content': 'Los destinos deben pertenecer al contexto del recorrido.'})
    return values


@transaction.atomic
def write_tour(actor, data, tour_id=None):
    require_admin(actor)
    values = validated(TourWriteSerializer, data)
    content = values.pop('content', None)
    version = values.pop('expected_version', None)
    if tour_id is None:
        if not values.get('slug') or not values.get('context') or content is None:
            raise ValidationError('Se requieren identificador, contexto y contenido bilingüe.')
        if PlatformGuidedTour.objects.filter(slug=values['slug']).exists():
            raise ValidationError({'slug': 'Este identificador ya existe.'})
        tour = PlatformGuidedTour(**values)
    else:
        tour = _tour(tour_id, lock=True)
        if version is None:
            raise ValidationError({'expected_version': 'Se requiere la versión vigente.'})
        check_version(tour, version)
        if any(key in values and values[key] != getattr(tour, key) for key in ('slug', 'context', 'kind')):
            raise ValidationError('La identidad y el contexto no cambian; crea otra novedad.')
        for key, value in values.items():
            setattr(tour, key, value)
    if content is not None:
        tour.draft = _validate_content(content, tour.context)
    tour.version += 1
    tour.save()
    _event(actor, 'write_tour', tour.slug, {'version': tour.version})
    return tour_payload(tour)


@transaction.atomic
def publish_tour(actor, tour_id, data):
    require_admin(actor)
    values = validated(TourVersionSerializer, data)
    tour = _tour(tour_id, lock=True)
    check_version(tour, values['expected_version'])
    content = _validate_content(tour.draft, tour.context)
    tour.published_revision += 1
    tour.version += 1
    PlatformGuidedTourRevision.objects.create(tour=tour, number=tour.published_revision, content=content, created_by=actor)
    tour.save()
    _event(actor, 'publish_tour', tour.slug, {'revision': tour.published_revision})
    return tour_payload(tour)


def revisions(actor, tour_id):
    require_admin(actor)
    return {'results': list(_tour(tour_id).revisions.order_by('-number').values('number', 'content', 'created_at'))}


def preview_tour(actor, tour_id):
    require_admin(actor)
    tour = _tour(tour_id)
    return {**tour_payload(tour), 'content': _validate_content(tour.draft, tour.context), 'preview': True}


def client_catalog(user, project_id=None):
    flags = effective_flags(user)
    if project_id is not None:
        project_for_actor(project_id, user)
    if not flags['tour_enabled']:
        return {**flags, 'tours': []}
    capabilities = _capabilities(user)
    tours = list(PlatformGuidedTour.objects.filter(is_active=True, published_revision__gt=0).order_by('priority', 'pk'))
    progress = {item.tour_id: item for item in PlatformTourProgress.objects.filter(user=user, tour__in=tours)}
    published = {(item.tour_id, item.number): item.content for item in PlatformGuidedTourRevision.objects.filter(
        tour__in=tours, number=F('tour__published_revision'))}
    result = []
    for tour in tours:
        if tour.context != 'general' and project_id is None:
            continue
        content = deepcopy(published.get((tour.pk, tour.published_revision), {}))
        content['steps'] = [step for step in content.get('steps', []) if target_available(step['target'], tour.context, capabilities)]
        if not content['steps']:
            continue
        state = progress.get(tour.pk)
        result.append({'id': tour.pk, 'slug': tour.slug, 'context': tour.context, 'kind': tour.kind,
                       'revision': tour.published_revision, 'content': content,
                       'status': state.status if state else '', 'last_step': state.last_step if state else ''})
    return {**flags, 'tours': result}


@transaction.atomic
def record_progress(user, tour_id, data):
    require_client(user)
    values = validated(TourProgressSerializer, data)
    if not effective_tour_enabled(user):
        raise PermissionDenied('Los recorridos están desactivados.')
    # Lock parent to serialize first progress creation and terminal acknowledgements.
    tour = _tour(tour_id, lock=True)
    if not tour.is_active:
        raise NotFound('Recorrido no disponible.')
    if tour.context != 'general':
        if 'project_id' not in values:
            raise ValidationError({'project_id': 'Se requiere un proyecto.'})
        project_for_actor(values['project_id'], user)
    revision = tour.revisions.filter(number=values['revision']).first()
    if not revision:
        raise ValidationError({'revision': 'Revisión no disponible.'})
    step = values.get('last_step', '')
    if step and step not in {item['target'] for item in revision.content['steps']}:
        raise ValidationError({'last_step': 'Este paso no pertenece al recorrido.'})
    progress = PlatformTourProgress.objects.filter(user=user, tour=tour).first()
    # Replaying is allowed, but never clears a terminal acknowledgement.
    if progress and progress.status in ('completed', 'skipped'):
        return {'status': progress.status}
    if progress is None:
        progress = PlatformTourProgress(user=user, tour=tour)
    progress.status = values['status']
    progress.revision = values['revision']
    progress.last_step = step
    progress.save()
    return {'status': progress.status}


def progress_report(actor, page=1, user_id=None):
    require_admin(actor)
    qs = PlatformTourProgress.objects.select_related('user', 'tour').order_by('-updated_at', '-pk')
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    return paginate(qs, page, lambda row: {'user_id': row.user_id, 'user': row.user.email, 'tour': row.tour.slug,
                                         'status': row.status, 'revision': row.revision, 'last_step': row.last_step,
                                         'updated_at': row.updated_at})
