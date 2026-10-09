"""Strict payloads for the data-integrity panel API and its MCP adapters."""
from rest_framework import serializers

from accounts.serializers_delivery import StrictSerializer
from content.services.data_integrity.engine import MAX_FIXES
from content.services.data_integrity.scope import QUERYABLE_KINDS, SCOPE_KINDS
from content.services.data_integrity.types import DOMAINS, EXISTING_TOOL, FIX_KINDS, REPORT_ONLY, SEVERITIES

HASH = r'^[0-9a-f]{64}$'


class CommaSeparatedField(serializers.Field):
    """A list given as a JSON array or as ``a,b`` in a query string."""

    def __init__(self, *, choices=None, **kwargs):
        self.choices = choices
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        values = data if isinstance(data, list) else str(data).split(',')
        cleaned = sorted({str(value).strip() for value in values if str(value).strip()})
        unknown = sorted(set(cleaned) - set(self.choices)) if self.choices else []
        if unknown:
            raise serializers.ValidationError(f'Valores no válidos: {", ".join(unknown)}.')
        return cleaned

    def to_representation(self, value):
        return value


class ScopeSerializer(StrictSerializer):
    kind = serializers.ChoiceField(choices=SCOPE_KINDS)
    id = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate(self, attrs):
        if attrs['kind'] == 'all':
            return {'kind': 'all', 'id': None}
        if not attrs.get('id'):
            raise serializers.ValidationError({'id': 'Indica el registro que delimita la revisión.'})
        return attrs


class FindingsQuerySerializer(StrictSerializer):
    scope_kind = serializers.ChoiceField(choices=SCOPE_KINDS, default='all')
    scope_id = serializers.IntegerField(min_value=1, required=False)
    scope_query = serializers.CharField(max_length=200, required=False, trim_whitespace=True)
    domains = CommaSeparatedField(choices=DOMAINS, required=False)
    rule_ids = CommaSeparatedField(required=False)
    severity = CommaSeparatedField(choices=SEVERITIES, required=False)
    page = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        kind = attrs['scope_kind']
        if attrs.get('scope_query') and attrs.get('scope_id'):
            raise serializers.ValidationError({'scope_query': 'Usa scope_id o scope_query, no los dos.'})
        if attrs.get('scope_query') and kind not in QUERYABLE_KINDS:
            raise serializers.ValidationError({'scope_query': 'Sólo se busca por texto un cliente o un proyecto.'})
        if kind != 'all' and not (attrs.get('scope_id') or attrs.get('scope_query')):
            raise serializers.ValidationError({'scope_id': 'Indica el registro que delimita la revisión.'})
        return attrs


class FixSelectionSerializer(StrictSerializer):
    fingerprint = serializers.RegexField(HASH)
    rule_id = serializers.RegexField(r'^[A-Z]{2}\d{1,2}$')
    fix_kind = serializers.ChoiceField(choices=FIX_KINDS + (REPORT_ONLY, EXISTING_TOOL), required=False)
    params = serializers.DictField(required=False, default=dict)


class FixPreviewSerializer(StrictSerializer):
    scope = ScopeSerializer()
    fixes = FixSelectionSerializer(many=True)

    def validate_fixes(self, value):
        if not 1 <= len(value) <= MAX_FIXES:
            raise serializers.ValidationError(f'Elige entre 1 y {MAX_FIXES} correcciones por lote.')
        fingerprints = [selection['fingerprint'] for selection in value]
        if len(set(fingerprints)) != len(fingerprints):
            raise serializers.ValidationError('No repitas un hallazgo en el mismo lote.')
        return [dict(selection) for selection in value]


class _ConfirmedSerializer(StrictSerializer):
    reason = serializers.CharField(max_length=2000, trim_whitespace=True)
    request_id = serializers.CharField(max_length=100, trim_whitespace=True)
    expected_impact_hash = serializers.RegexField(HASH)


class FixApplySerializer(FixPreviewSerializer, _ConfirmedSerializer):
    pass


class UndoSerializer(_ConfirmedSerializer):
    pass


class OperationsQuerySerializer(StrictSerializer):
    page = serializers.IntegerField(min_value=1, default=1)
    rule_id = serializers.RegexField(r'^[A-Z]{2}\d{1,2}$', required=False)
