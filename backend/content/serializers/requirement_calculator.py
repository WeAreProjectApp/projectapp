"""Closed, bounded schemas shared by Panel and MCP calculator writes."""
from decimal import Decimal
from itertools import pairwise

from rest_framework import serializers

SIZES = ('XS', 'S', 'M', 'L', 'XL')
OUTCOMES = (*SIZES, 'PROJECT')


class ClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('Se esperaba un objeto.')
        unknown = set(data) - self.fields.keys()
        if unknown:
            raise serializers.ValidationError({key: 'Campo desconocido.' for key in unknown})
        return super().to_internal_value(data)


def number(*, nullable=False, maximum='100000000000'):
    return serializers.DecimalField(max_digits=16, decimal_places=3, min_value=Decimal(0),
                                    max_value=Decimal(maximum), allow_null=nullable)


class SizeSerializer(ClosedSerializer):
    id = serializers.ChoiceField(choices=SIZES)
    label = serializers.CharField(max_length=200)
    definition = serializers.CharField(max_length=4000)
    examples = serializers.ListField(child=serializers.CharField(max_length=2000), min_length=1, max_length=20)
    points = number(maximum='10000')
    hours_min = number(maximum='100000')
    hours_max = number(maximum='100000')
    standard_value_cop = number(nullable=True)

    def validate(self, attrs):
        if attrs['points'] <= 0 or attrs['hours_max'] <= attrs['hours_min']:
            raise serializers.ValidationError('Los puntos deben ser positivos y la banda interna creciente.')
        if attrs['standard_value_cop'] is not None and attrs['standard_value_cop'] <= 0:
            raise serializers.ValidationError('El valor estándar debe ser positivo o quedar pendiente.')
        return attrs


class SignalSerializer(ClosedSerializer):
    id = serializers.SlugField(max_length=100)
    size = serializers.ChoiceField(choices=OUTCOMES)
    label = serializers.CharField(max_length=500)
    description = serializers.CharField(max_length=6000)
    surcharge_percent = number(maximum='1000')


class ModifierSerializer(ClosedSerializer):
    id = serializers.SlugField(max_length=100)
    label = serializers.CharField(max_length=1500)
    kind = serializers.ChoiceField(choices=('percentage', 'factor', 'fixed_hours', 'separate'))
    minimum = number(nullable=True, maximum='10000')
    maximum = number(nullable=True, maximum='10000')
    applies_to = serializers.ListField(child=serializers.ChoiceField(choices=SIZES), min_length=1, max_length=5)
    exclusive_group = serializers.SlugField(max_length=100, allow_blank=True)

    def validate(self, attrs):
        low, high = attrs['minimum'], attrs['maximum']
        if attrs['kind'] != 'separate' and (low is None or high is None):
            raise serializers.ValidationError('El modificador numérico necesita ambos límites.')
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError('El límite inferior no puede superar el superior.')
        return attrs


class FamilySerializer(ClosedSerializer):
    label = serializers.CharField(max_length=300)
    small = serializers.CharField(max_length=2000)
    medium = serializers.CharField(max_length=2000)
    large = serializers.CharField(max_length=2000)
    extra_large = serializers.CharField(max_length=2000)


class CalibrationSerializer(ClosedSerializer):
    minimum_samples = serializers.IntegerField(min_value=3, max_value=1000)
    deviation_percent = number(maximum='1000')
    hourly_cost_cop = number(nullable=True)

    def validate_hourly_cost_cop(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError('El costo debe ser positivo o quedar pendiente.')
        return value


class DefinitionSerializer(ClosedSerializer):
    schema_version = serializers.IntegerField(min_value=1, max_value=1)
    title = serializers.CharField(max_length=200)
    methodology = serializers.CharField(max_length=20000)
    project_rules = serializers.ListField(child=serializers.CharField(max_length=2000), min_length=1, max_length=30)
    sizes = SizeSerializer(many=True, min_length=5, max_length=5)
    signals = SignalSerializer(many=True, min_length=1, max_length=500)
    modifiers = ModifierSerializer(many=True, max_length=100)
    families = FamilySerializer(many=True, max_length=100)
    calibration = CalibrationSerializer()

    def validate(self, attrs):
        if [row['id'] for row in attrs['sizes']] != list(SIZES):
            raise serializers.ValidationError('Las tallas deben ser XS, S, M, L y XL, en ese orden.')
        points = [row['points'] for row in attrs['sizes']]
        if any(a >= b for a, b in pairwise(points)):
            raise serializers.ValidationError('Los puntos deben crecer con la talla.')
        for collection in ('signals', 'modifiers'):
            ids = [row['id'] for row in attrs[collection]]
            if len(set(ids)) != len(ids):
                raise serializers.ValidationError({collection: 'Los identificadores deben ser únicos.'})
        return attrs


class DefinitionWriteSerializer(ClosedSerializer):
    definition = DefinitionSerializer()
    note = serializers.CharField(max_length=2000)
    if_match = serializers.CharField(max_length=150)
    document_id = serializers.IntegerField(min_value=1, required=False)


class ProjectDraftSerializer(ClosedSerializer):
    base_revision_id = serializers.IntegerField(min_value=1)
    note = serializers.CharField(max_length=2000)
    if_match = serializers.CharField(max_length=150)


class ApproveSerializer(ClosedSerializer):
    if_match = serializers.CharField(max_length=150)
    note = serializers.CharField(max_length=2000)


class EstimateSerializer(ClosedSerializer):
    request_id = serializers.UUIDField()
    revision_id = serializers.IntegerField(min_value=1)
    project_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    project_version_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    definition_digest = serializers.CharField(min_length=64, max_length=64)
    requirement = serializers.CharField(max_length=30000)
    size = serializers.ChoiceField(choices=OUTCOMES)
    signal_ids = serializers.ListField(child=serializers.SlugField(max_length=100), max_length=100)
    explanation = serializers.CharField(max_length=15000)
    expected_size = serializers.ChoiceField(choices=OUTCOMES, required=False, allow_blank=True)


class ActualSerializer(ClosedSerializer):
    estimate_id = serializers.IntegerField(min_value=1)
    actual_hours = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('.01'))
    hourly_cost_cop = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('.01'), required=False, allow_null=True)
    evidence = serializers.CharField(max_length=8000)
    cause = serializers.CharField(max_length=8000)
    supersedes_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
