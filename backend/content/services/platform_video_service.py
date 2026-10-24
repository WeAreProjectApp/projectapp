"""Client tutorial catalog; visibility shares the Help and AI feature gates."""
import logging

from rest_framework.exceptions import PermissionDenied

from content.models import VideoResource

logger = logging.getLogger(__name__)
PLATFORM_VIDEO_TOPICS = {
    'general': 'platform-overview',
    'chatbot': 'platform-chatbot',
    'voice-reporting': 'platform-voice-reporting',
}
PLATFORM_VIDEO_MODULES = tuple(PLATFORM_VIDEO_TOPICS.values())


def _help_enabled(actor):
    try:
        from accounts.services.platform_help import effective_video_enabled
    except ModuleNotFoundError as error:
        if error.name != 'accounts.services.platform_help':
            raise
        return False
    return effective_video_enabled(actor)


def _ai_capabilities(actor):
    from accounts.services.platform_ai import ai_capabilities
    return ai_capabilities(actor)


def client_videos(actor):

    profile = getattr(actor, 'profile', None)
    if not actor.is_active or not profile or not profile.is_client:
        raise PermissionDenied('Se requiere una cuenta de cliente activa.')
    enabled = _help_enabled(actor)
    if not enabled:
        return {'enabled': False, 'videos': []}

    capabilities = {}
    try:
        capabilities = _ai_capabilities(actor)
    except Exception:
        # Tutorials remain usable when AI configuration cannot be read. No
        # provider is called and no credential/message appears in this log.
        logger.warning('Platform video AI availability could not be read')

    from content.services.video_resource_service import video_descriptor
    resources = {
        resource.module: resource for resource in VideoResource.objects.filter(
            module__in=PLATFORM_VIDEO_MODULES, language='es', proposal__isnull=True,
        )
    }
    videos = []
    for topic, module in PLATFORM_VIDEO_TOPICS.items():
        capability = 'voice_reporting' if topic == 'voice-reporting' else topic
        if topic != 'general' and not capabilities.get(capability, {}).get('available'):
            continue
        resource = resources.get(module)
        mode = resource.mode if resource else 'default'
        descriptor = video_descriptor(resource)
        if mode == 'none' or (mode == 'uploaded' and descriptor is None):
            continue
        videos.append({
            'topic': topic, 'module': module, 'language': 'es',
            'resource': {'mode': mode, 'video': descriptor},
        })
    return {'enabled': True, 'videos': videos}
