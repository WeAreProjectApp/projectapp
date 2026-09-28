from rest_framework import serializers

from content.serializers.strict_input import StrictInputMixin


class MoveDocumentsSerializer(StrictInputMixin, serializers.Serializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=100,
    )
    folder_id = serializers.IntegerField(min_value=1, allow_null=True)
    include_content = serializers.BooleanField(required=False, default=False)

    def validate_document_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("No repitas IDs de documentos.")
        return value
