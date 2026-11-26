"""Shared receipt identity for the accounting panel and its settlement adapters."""
from rest_framework import serializers


class ReceiptEvidenceSerializer(serializers.Serializer):
    income_id = serializers.IntegerField(min_value=1)
    hosting_record_id = serializers.IntegerField(min_value=1)
    cycle_id = serializers.IntegerField(min_value=1, required=False)
    liquid_id = serializers.IntegerField(min_value=1, required=False)


class HostingReceiptSerializer(serializers.Serializer):
    issuer = serializers.CharField(max_length=96, required=False)
    reference = serializers.CharField(max_length=128, required=False)
    entries = ReceiptEvidenceSerializer(many=True, allow_empty=False)

    def validate(self, data):
        if bool(data.get('issuer')) != bool(data.get('reference')):
            raise serializers.ValidationError('Indica tanto la fuente como el folio estable del pago.')
        if data.get('issuer', '').startswith('@'):
            raise serializers.ValidationError('Elige la fuente que emitió el folio del pago.')
        ids = [entry['income_id'] for entry in data['entries']]
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError('Indica una sola imputación de hosting por ingreso.')
        if not data.get('issuer') and not any(e.get('liquid_id') or e.get('cycle_id') for e in data['entries']):
            raise serializers.ValidationError('Selecciona un asiento existente o indica la referencia del pago acreditado.')
        return data
