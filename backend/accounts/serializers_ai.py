"""Closed input contracts shared by Panel, Platform and MCP."""
from rest_framework import serializers

from accounts.models_ai import PlatformAISettings, TEXT_MODELS, PROVIDERS


class ClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError('Hay campos no admitidos en la solicitud.')
        return super().to_internal_value(data)


class SettingsSerializer(serializers.ModelSerializer):
    expected_version = serializers.IntegerField(min_value=1, write_only=True, required=True)
    chatbot_model = serializers.ChoiceField(choices=TEXT_MODELS, required=False)
    voice_report_model = serializers.ChoiceField(choices=TEXT_MODELS, required=False)
    monthly_audio_limit = serializers.IntegerField(min_value=1, max_value=100000, required=False)
    daily_user_audio_limit = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    ai_request_limit = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    ai_window_minutes = serializers.IntegerField(min_value=1, max_value=10080, required=False)
    max_output_tokens = serializers.IntegerField(min_value=256, max_value=2000, required=False)
    report_cache_hours = serializers.IntegerField(min_value=1, max_value=24, required=False)
    chatbot_cache_hours = serializers.IntegerField(min_value=1, max_value=24, required=False)

    class Meta:
        model = PlatformAISettings
        fields = ['chatbot_enabled', 'voice_reporting_enabled', 'chatbot_model', 'voice_report_model',
                  'monthly_audio_limit', 'daily_user_audio_limit', 'ai_request_limit', 'ai_window_minutes', 'max_output_tokens',
                  'report_cache_enabled', 'chatbot_cache_enabled', 'report_cache_hours', 'chatbot_cache_hours',
                  'version', 'updated_at', 'expected_version']
        read_only_fields = ['version', 'updated_at']

    def to_internal_value(self, data):
        if set(data) - set(self.fields):
            raise serializers.ValidationError('Hay campos no admitidos en la solicitud.')
        return super().to_internal_value(data)


class ClientFlagsSerializer(ClosedSerializer):
    chatbot_enabled = serializers.BooleanField(required=False)
    voice_reporting_enabled = serializers.BooleanField(required=False)
    ai_request_limit = serializers.IntegerField(min_value=1, max_value=1000, required=False, allow_null=True)
    ai_window_minutes = serializers.IntegerField(min_value=1, max_value=10080, required=False, allow_null=True)
    expected_version = serializers.CharField(max_length=50)


class CredentialSerializer(ClosedSerializer):
    api_key = serializers.CharField(min_length=10, max_length=4096, write_only=True, trim_whitespace=True)
    expected_version = serializers.IntegerField(min_value=0)


class TemplateSerializer(ClosedSerializer):
    content = serializers.CharField(max_length=12000)
    expected_version = serializers.IntegerField(min_value=1)


class TemplateRestoreSerializer(ClosedSerializer):
    version = serializers.IntegerField(min_value=1)
    expected_version = serializers.IntegerField(min_value=1)


class TranscriptionSerializer(ClosedSerializer):
    audio = serializers.FileField(max_length=200)
    purpose = serializers.ChoiceField(choices=['chatbot', 'voice_report'])
    project_id = serializers.IntegerField(min_value=1, required=False)
    request_id = serializers.UUIDField()


class ReportDraftSerializer(ClosedSerializer):
    request_id = serializers.UUIDField()
    transcription_id = serializers.UUIDField()
    transcript = serializers.CharField(max_length=6000)
    scenario = serializers.ChoiceField(choices=['bug', 'change', 'stage_observation'])
    language = serializers.ChoiceField(choices=['es', 'en'], default='es')
    source_requirement_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    stage_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


def validated(serializer, data):
    item = serializer(data=data)
    item.is_valid(raise_exception=True)
    return item.validated_data
