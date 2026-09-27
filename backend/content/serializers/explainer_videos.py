from rest_framework import serializers

from content.models import ExplainerVideoSettings


class ExplainerVideoSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExplainerVideoSettings
        fields = (
            'show_additional_modules_video',
            'show_financing_video',
            'show_proposal_video',
            'updated_at',
        )
        read_only_fields = ('updated_at',)
