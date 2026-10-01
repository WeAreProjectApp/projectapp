"""Strict write contracts; identity always comes from the authenticated actor."""
from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({'non_field_errors': ['La solicitud debe ser un objeto.']})
        if set(data) - set(self.fields):
            raise serializers.ValidationError({'non_field_errors': ['La solicitud contiene campos no permitidos.']})
        return super().to_internal_value(data)


class VersionField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            raise serializers.ValidationError('La versión debe ser un entero.')
        return super().to_internal_value(data)


class IdeaTextSerializer(StrictSerializer):
    text = serializers.CharField(max_length=10_000, trim_whitespace=False)

    def validate_text(self, value):
        if not value.strip():
            raise serializers.ValidationError('Escribe una idea antes de guardar.')
        if len(value.encode('utf-8')) > 10_000:
            raise serializers.ValidationError('La idea es demasiado extensa. Divide el texto en varias sugerencias.')
        return value


class IdeaCreateSerializer(IdeaTextSerializer):
    request_id = serializers.UUIDField()


class IdeaEditSerializer(IdeaTextSerializer):
    expected_version = VersionField(min_value=1)


class IdeaArchiveSerializer(StrictSerializer):
    expected_version = VersionField(min_value=1)


class CollectionSelectionSerializer(StrictSerializer):
    idea_id = serializers.IntegerField(min_value=1)
    expected_version = VersionField(min_value=1)


class IdeaCollectionSerializer(StrictSerializer):
    title = serializers.CharField(max_length=255)
    items = CollectionSelectionSerializer(many=True, min_length=1, max_length=100)
    request_id = serializers.UUIDField()

    def validate_items(self, value):
        if len({item['idea_id'] for item in value}) != len(value):
            raise serializers.ValidationError('Selecciona cada idea una sola vez.')
        return value


def validated(serializer_class, data):
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data
