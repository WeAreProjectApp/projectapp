"""Small, closed inputs; client identity is always resolved from authentication."""
from rest_framework import serializers


class ConversationSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)
    language = serializers.ChoiceField(choices=('es', 'en'), default='es')


class QuestionSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    question = serializers.CharField(max_length=2000, trim_whitespace=True)
    transcription_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_question(self, value):
        if any(ord(char) < 32 and char not in '\n\t' for char in value):
            raise serializers.ValidationError('Usa una pregunta de texto sin caracteres de control.')
        return value
