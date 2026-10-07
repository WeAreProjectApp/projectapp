"""Shared strict payload for Panel and MCP routing corrections."""
from rest_framework import serializers


class ProposalProjectReassignmentSerializer(serializers.Serializer):
    target_project_id = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=2000, trim_whitespace=True)
    expected_impact_hash = serializers.RegexField(r'^[0-9a-f]{64}$')
    request_id = serializers.CharField(max_length=100, trim_whitespace=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({'non_field_errors': ['Se esperaba un objeto JSON.']})
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: 'Campo no permitido.' for key in sorted(unknown)})
        return super().to_internal_value(data)
