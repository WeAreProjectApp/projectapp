from rest_framework import serializers

from content.serializers.strict_input import StrictInputMixin
from content.services.document_ownership_planner import (
    CLIENT_POLICIES,
    PORTAL_POLICIES,
    DocumentDecisionSerializer,
)


class MoveDocumentsSerializer(StrictInputMixin, serializers.Serializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=100,
    )
    folder_id = serializers.IntegerField(min_value=1, allow_null=True)
    include_content = serializers.BooleanField(required=False, default=False)
    client_policy = serializers.ChoiceField(choices=CLIENT_POLICIES, required=False)
    portal_policy = serializers.ChoiceField(choices=PORTAL_POLICIES, required=False)
    expected_plan_hash = serializers.RegexField(r'^[a-f0-9]{64}$', required=False)
    document_decisions = DocumentDecisionSerializer(many=True, required=False, max_length=100)

    def validate_document_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("No repitas IDs de documentos.")
        return value

    def validate(self, attrs):
        if 'client_policy' not in attrs and {'portal_policy', 'expected_plan_hash', 'document_decisions'}.intersection(attrs):
            raise serializers.ValidationError({'client_policy': 'Elige la política para usar la vista previa del movimiento.'})
        return attrs
