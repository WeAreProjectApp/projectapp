from content.serializers.editorial import EditorialModelSerializer
from rest_framework import serializers

from content.models import HourPackage, HourPackageSettings


class HourPackageAdminListSerializer(EditorialModelSerializer):
    """Admin list serializer — includes the currency derived from nationality."""
    currency = serializers.ReadOnlyField()

    class Meta:
        model = HourPackage
        fields = (
            'id', 'nationality', 'currency', 'name_es', 'name_en',
            'note_es', 'note_en', 'hours', 'hourly_rate', 'discount_percent',
            'is_active', 'order', 'updated_at',
        )


class HourPackageAdminDetailSerializer(EditorialModelSerializer):
    """Admin detail serializer — all fields for the edit form."""
    currency = serializers.ReadOnlyField()

    class Meta:
        model = HourPackage
        fields = (
            'id', 'nationality', 'currency', 'name_es', 'name_en',
            'note_es', 'note_en', 'hours', 'hourly_rate', 'discount_percent',
            'is_active', 'order', 'created_at', 'updated_at',
        )


class HourPackageCreateUpdateSerializer(EditorialModelSerializer):
    """Serializer for creating and updating hour packages from the admin panel."""

    class Meta:
        model = HourPackage
        fields = (
            'nationality', 'name_es', 'name_en', 'note_es', 'note_en',
            'hours', 'hourly_rate', 'discount_percent', 'is_active', 'order',
        )
        extra_kwargs = {
            'note_es': {'required': False},
            'note_en': {'required': False},
            'discount_percent': {'required': False},
            'is_active': {'required': False},
            'order': {'required': False},
        }

    def validate_hours(self, value):
        if value < 1:
            raise serializers.ValidationError('Las horas deben ser al menos 1.')
        return value

    def validate_hourly_rate(self, value):
        if value <= 0:
            raise serializers.ValidationError('La tarifa por hora debe ser mayor a 0.')
        return value

    def validate_discount_percent(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError('El descuento debe estar entre 0 y 100.')
        return value


class HourPackageSettingsSerializer(EditorialModelSerializer):
    """Singleton settings for the hour-packages panel."""

    class Meta:
        model = HourPackageSettings
        fields = (
            'default_view_mode', 'base_rate_col', 'base_rate_ext',
            'base_rate_usa', 'updated_at',
        )

    def _validate_base_rate(self, value):
        if value <= 0:
            raise serializers.ValidationError('La tarifa base debe ser mayor a 0.')
        return value

    def validate_base_rate_col(self, value):
        return self._validate_base_rate(value)

    def validate_base_rate_ext(self, value):
        return self._validate_base_rate(value)

    def validate_base_rate_usa(self, value):
        return self._validate_base_rate(value)
