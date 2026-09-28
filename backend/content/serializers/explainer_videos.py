from rest_framework import serializers

from content.models import ExplainerVideoSettings


class ExplainerVideoSettingsSerializer(serializers.ModelSerializer):
    resources = serializers.SerializerMethodField()

    def get_resources(self, obj):
        from content.services.video_resource_service import VIDEO_MODULES, video_descriptor
        from content.models import VideoResource
        slots = {resource.key: resource for resource in VideoResource.objects.filter(proposal__isnull=True)}
        return {
            f'{module}:{language}': {
                'mode': slots[f'{module}:{language}'].mode if f'{module}:{language}' in slots else 'default',
                'video': video_descriptor(slots.get(f'{module}:{language}')),
            }
            for module in VIDEO_MODULES for language in ('es', 'en')
        }

    class Meta:
        model = ExplainerVideoSettings
        fields = (
            'show_additional_modules_video',
            'show_financing_video',
            'show_proposal_video',
            'updated_at', 'resources',
        )
        read_only_fields = ('updated_at',)
