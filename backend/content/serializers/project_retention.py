"""Strict payloads for undoing an adoption and discarding empty retained containers."""
from rest_framework import serializers

from accounts.serializers_delivery import StrictSerializer

CONTAINER_KINDS = ('communication_threads', 'communication_folders', 'document_folders')


class _ConfirmedRetentionSerializer(StrictSerializer):
    reason = serializers.CharField(max_length=2000, trim_whitespace=True)
    request_id = serializers.CharField(max_length=100, trim_whitespace=True)
    expected_impact_hash = serializers.RegexField(r'^[0-9a-f]{64}$')


class RetainedUndoSerializer(_ConfirmedRetentionSerializer):
    pass


class RetainedCleanupSerializer(_ConfirmedRetentionSerializer):
    selection = serializers.DictField(
        child=serializers.ListField(child=serializers.IntegerField(min_value=1)),
        required=False, allow_null=True, default=None,
    )

    def validate_selection(self, value):
        if value is None:
            return None
        unknown = sorted(set(value) - set(CONTAINER_KINDS))
        if unknown:
            raise serializers.ValidationError(f'Tipos no válidos: {", ".join(unknown)}.')
        return {key: sorted(set(ids)) for key, ids in value.items()}


def selection_from_query(params):
    """{kind: [ids]} from comma-separated query params, or None for every container."""
    selection = {}
    for kind in CONTAINER_KINDS:
        raw = params.get(kind)
        if raw in (None, ''):
            continue
        try:
            selection[kind] = sorted({int(value) for value in str(raw).split(',') if value.strip()})
        except ValueError as exc:
            raise serializers.ValidationError({kind: 'Usa identificadores numéricos separados por comas.'}) from exc
    return selection or None
