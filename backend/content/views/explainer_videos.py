from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import ExplainerVideoSettings
from content.serializers.explainer_videos import ExplainerVideoSettingsSerializer
from content.services.frontend_build import schedule_rebuild_after_publish

# Only these public surfaces are prerendered; proposals read settings at runtime.
VISIBILITY_FIELDS = ('show_additional_modules_video', 'show_financing_video')


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_explainer_video_settings(request):
    """Return the switches that show or hide each explainer video to clients."""
    serializer = ExplainerVideoSettingsSerializer(ExplainerVideoSettings.load())
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_explainer_video_settings(request):
    """Update the explainer-video switches.

    The canonical public pages are prerendered, so a real change schedules the
    frontend rebuild that bakes the new visibility into their HTML.
    """
    settings = ExplainerVideoSettings.load()
    before = {field: getattr(settings, field) for field in VISIBILITY_FIELDS}
    serializer = ExplainerVideoSettingsSerializer(
        settings, data=request.data, partial=True,
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    if any(getattr(settings, field) != value for field, value in before.items()):
        schedule_rebuild_after_publish()
    return Response(serializer.data, status=status.HTTP_200_OK)
