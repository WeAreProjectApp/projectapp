"""Bounded, closed inputs for Panel, Platform and MCP package operations."""
from django.utils import timezone
from rest_framework import serializers

from content.serializers.requirement_calculator import ClosedSerializer, OUTCOMES


class PackageWriteSerializer(ClosedSerializer):
    request_id = serializers.UUIDField()


class ExampleWriteSerializer(PackageWriteSerializer):
    language = serializers.ChoiceField(choices=['es', 'en'], required=False)
    expected_revision = serializers.IntegerField(min_value=0)
    examples = serializers.DictField(child=serializers.ListField(child=serializers.CharField(max_length=2000), min_length=1, max_length=10))
    note = serializers.CharField(max_length=2000)

    def validate_examples(self, value):
        if not set(value) <= set(OUTCOMES):
            raise serializers.ValidationError('Usa XS, S, M, L, XL o PROJECT.')
        return value


class OrderCreateSerializer(PackageWriteSerializer):
    package_id = serializers.IntegerField(min_value=1)
    method = serializers.ChoiceField(choices=['online', 'external'])
    language = serializers.ChoiceField(choices=['es', 'en'], default='es')
    conditions_accepted = serializers.BooleanField()
    quote_digest = serializers.CharField(min_length=64, max_length=64)

    def validate_conditions_accepted(self, value):
        if not value:
            raise serializers.ValidationError('Acepta las condiciones antes de crear la compra.')
        return value


class ExternalPaymentSerializer(PackageWriteSerializer):
    paid_at = serializers.DateTimeField()
    payment_reference = serializers.CharField(max_length=200)

    def validate_paid_at(self, value):
        if value > timezone.now():
            raise serializers.ValidationError('La fecha del pago no puede estar en el futuro.')
        return value


class TransactionVerifySerializer(PackageWriteSerializer):
    transaction_id = serializers.RegexField(r'^[a-zA-Z0-9_-]{1,100}$')


class RequestCreateSerializer(PackageWriteSerializer):
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(max_length=15000)


class RequestVersionSerializer(PackageWriteSerializer):
    expected_version = serializers.IntegerField(min_value=0)


class ProposalWriteSerializer(RequestVersionSerializer):
    size = serializers.ChoiceField(choices=OUTCOMES)
    explanation = serializers.CharField(max_length=8000)
    scope = serializers.CharField(max_length=15000)
    assumptions = serializers.CharField(max_length=8000, allow_blank=True, default='')
    delivery_from = serializers.DateField()
    delivery_until = serializers.DateField()
    schedule_conditions = serializers.CharField(max_length=4000, allow_blank=True, default='')
    signal_ids = serializers.ListField(child=serializers.SlugField(max_length=100), max_length=100)
    warranty = serializers.BooleanField(default=False)
    language = serializers.ChoiceField(choices=['es', 'en'], default='es')

    def validate(self, attrs):
        if attrs['delivery_until'] < attrs['delivery_from']:
            raise serializers.ValidationError({'delivery_until': 'El final no puede ser anterior al inicio.'})
        if attrs['delivery_from'] < timezone.localdate():
            raise serializers.ValidationError({'delivery_from': 'La fecha orientativa debe ser hoy o posterior.'})
        return attrs


class DecisionWriteSerializer(RequestVersionSerializer):
    proposal_id = serializers.IntegerField(min_value=1)
    decision = serializers.ChoiceField(choices=['accept', 'object'])
    message = serializers.CharField(max_length=8000, required=False, default='', allow_blank=True)
    order_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs['decision'] == 'object' and not attrs['message'].strip():
            raise serializers.ValidationError({'message': 'Explica tu objeción para que el equipo pueda revisarla.'})
        return attrs


class ReversalSerializer(PackageWriteSerializer):
    reason = serializers.CharField(max_length=2000)


class PackageSettingsSerializer(RequestVersionSerializer):
    nationality = serializers.ChoiceField(choices=['COL', 'EXT', 'USA'])
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
