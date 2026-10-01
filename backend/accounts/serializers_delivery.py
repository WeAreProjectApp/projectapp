"""Strict write contracts for Platform delivery authoring and review."""
from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({'non_field_errors': ['Se esperaba un objeto JSON.']})
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: 'Campo no permitido.' for key in sorted(unknown)})
        return super().to_internal_value(data)


class GuideSerializer(StrictSerializer):
    role = serializers.CharField(required=False, allow_blank=True, max_length=300)
    environment = serializers.CharField(required=False, allow_blank=True, max_length=500)
    preparation = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    data = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    steps = serializers.ListField(child=serializers.CharField(max_length=3000), required=False, max_length=100)
    expected_result = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    failure_signals = serializers.CharField(required=False, allow_blank=True, max_length=20000)


class VersionedSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=0)
    request_id = serializers.CharField(max_length=100, required=False)


class NodeSerializer(VersionedSerializer):
    key = serializers.SlugField(max_length=100)
    title = serializers.CharField(max_length=300)


class ContractSerializer(NodeSerializer):
    document_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    proposal_document_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    client_visible = serializers.BooleanField(required=False)


class AmendmentSerializer(ContractSerializer):
    contract_id = serializers.IntegerField(min_value=1)


class ScopeSerializer(NodeSerializer):
    contract_id = serializers.IntegerField(min_value=1)
    amendment_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    is_current = serializers.BooleanField(required=False)


class PhaseSerializer(NodeSerializer):
    scope_id = serializers.IntegerField(min_value=1)
    commercial_phase_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    order = serializers.IntegerField(min_value=0, required=False)


class StageSerializer(NodeSerializer):
    phase_id = serializers.IntegerField(min_value=1)
    description = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    order = serializers.IntegerField(min_value=0, required=False)


class RequirementSerializer(NodeSerializer):
    stage_id = serializers.IntegerField(min_value=1)
    description = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    guide = GuideSerializer(required=False)
    order = serializers.IntegerField(min_value=0, required=False)


class PublishSerializer(VersionedSerializer):
    request_id = serializers.CharField(max_length=100)


class DecisionSerializer(StrictSerializer):
    requirement_id = serializers.IntegerField(min_value=1)
    version = serializers.IntegerField(min_value=1)
    decision = serializers.ChoiceField(choices=['approved', 'objected', 'rejected'])
    message = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    environment = serializers.CharField(required=False, allow_blank=True, max_length=200)


class ReviewSerializer(PublishSerializer):
    decisions = DecisionSerializer(many=True, allow_empty=False)
    message = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    document_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=20)
    evidence_message = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    evidence_document_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=20)
    client_statement = serializers.BooleanField(required=False)
    source_message_id = serializers.IntegerField(min_value=1, required=False)
    original_reviewer = serializers.CharField(max_length=300, required=False)
    occurred_at = serializers.DateTimeField(required=False)
    evidence_channel = serializers.ChoiceField(choices=['email', 'whatsapp', 'document'], required=False)
    external_reference = serializers.CharField(max_length=1000, required=False)


LEVELS = ['project', 'contract', 'amendment', 'scope', 'phase', 'stage', 'requirement']


class LinkSerializer(VersionedSerializer):
    level = serializers.ChoiceField(choices=LEVELS)
    target_id = serializers.IntegerField(min_value=1)
    document_id = serializers.IntegerField(min_value=1)


class MessageSerializer(PublishSerializer):
    level = serializers.ChoiceField(choices=LEVELS)
    target_id = serializers.IntegerField(min_value=1)
    requirement_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=100)
    message = serializers.CharField(max_length=20000)
    document_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=20)
    is_internal = serializers.BooleanField(required=False)


class SignatureSerializer(PublishSerializer):
    signer_name = serializers.CharField(max_length=255)
    signed_at = serializers.DateTimeField()
    attestation = serializers.CharField(max_length=20000)


NODE_SERIALIZERS = {
    'contracts': ContractSerializer, 'amendments': AmendmentSerializer,
    'scopes': ScopeSerializer, 'phases': PhaseSerializer,
    'stages': StageSerializer, 'requirements': RequirementSerializer,
}
