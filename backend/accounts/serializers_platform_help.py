"""Validated authoring vocabulary; no executable selectors, HTML or URLs."""
from rest_framework import serializers
from accounts.services.platform_help_targets import TARGETS


class HelpFlagsSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=0)
    tour_enabled = serializers.BooleanField(required=False)
    video_enabled = serializers.BooleanField(required=False)


class TourStepSerializer(serializers.Serializer):
    target = serializers.ChoiceField(choices=list(TARGETS))
    title_es = serializers.CharField(max_length=160)
    title_en = serializers.CharField(max_length=160)
    description_es = serializers.CharField(max_length=1600)
    description_en = serializers.CharField(max_length=1600)


class TourContentSerializer(serializers.Serializer):
    title_es = serializers.CharField(max_length=160)
    title_en = serializers.CharField(max_length=160)
    steps = TourStepSerializer(many=True, min_length=1, max_length=30)

    def validate_steps(self, steps):
        keys = [step['target'] for step in steps]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError('Cada destino solo puede aparecer una vez.')
        return steps


class TourWriteSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=80, required=False)
    context = serializers.ChoiceField(choices=['general', 'project', 'voice'], required=False)
    kind = serializers.ChoiceField(choices=['onboarding', 'novelty'], required=False)
    priority = serializers.IntegerField(min_value=0, max_value=32767, required=False)
    is_active = serializers.BooleanField(required=False)
    content = TourContentSerializer(required=False)
    expected_version = serializers.IntegerField(min_value=0, required=False)


class TourVersionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=0)


class TourProgressSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['in_progress', 'paused', 'completed', 'skipped'])
    revision = serializers.IntegerField(min_value=1)
    last_step = serializers.ChoiceField(choices=list(TARGETS), required=False, allow_blank=True)
    project_id = serializers.IntegerField(min_value=1, required=False)
    manual = serializers.BooleanField(default=False)


def validated(serializer_class, data):
    # DRF normally ignores undeclared keys; reject them for panel/MCP parity.
    serializer = serializer_class(data=data)
    unknown = set(data) - set(serializer.fields)
    if unknown:
        raise serializers.ValidationError({key: 'Campo no permitido.' for key in unknown})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data
