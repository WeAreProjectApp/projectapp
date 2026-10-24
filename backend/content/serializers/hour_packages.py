from typing import ClassVar

from rest_framework import serializers

from content.models import HourPackage, HourPackageSettings
from content.serializers.editorial import EditorialModelSerializer


class HourPackageAdminListSerializer(EditorialModelSerializer):
    """Admin list serializer — includes the currency derived from nationality."""
    currency = serializers.ReadOnlyField()
    reference_price = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    savings = serializers.SerializerMethodField()

    def _prices(self, obj):
        from content.models import HourPackageSettings
        from content.services.requirement_package_service import (
            price_context,
            priced_package,
        )
        if obj.pricing_model != 'requirements':
            return {'reference_price': '0', 'total_price': '0', 'savings': '0'}
        cache = self.context.setdefault('package_prices', {})
        if obj.pk not in cache:
            if 'package_settings' not in self.context:
                self.context['package_settings'] = HourPackageSettings.load()
            settings = self.context['package_settings']
            contexts = self.context.setdefault('price_contexts', {})
            if obj.nationality not in contexts:
                contexts[obj.nationality] = price_context(obj.nationality, settings)
            cache[obj.pk] = priced_package(obj, settings=settings, context=contexts[obj.nationality])
        return cache[obj.pk]

    def get_reference_price(self, obj):
        return self._prices(obj)['reference_price']

    def get_total_price(self, obj):
        return self._prices(obj)['total_price']

    def get_savings(self, obj):
        return self._prices(obj)['savings']

    class Meta:
        model = HourPackage
        fields = (
            'id', 'nationality', 'currency', 'name_es', 'name_en',
            'note_es', 'note_en', 'pricing_model', 'xs_count', 's_count', 'm_count',
            'validity_months', 'reference_price', 'total_price', 'savings', 'discount_percent',
            'is_active', 'order', 'updated_at',
        )


class HourPackageAdminDetailSerializer(HourPackageAdminListSerializer):
    class Meta(HourPackageAdminListSerializer.Meta):
        fields = HourPackageAdminListSerializer.Meta.fields + ('created_at',)


class HourPackageCreateUpdateSerializer(EditorialModelSerializer):
    """Serializer for creating and updating hour packages from the admin panel."""

    class Meta:
        model = HourPackage
        fields = (
            'nationality', 'name_es', 'name_en', 'note_es', 'note_en',
            'xs_count', 's_count', 'm_count', 'validity_months',
            'discount_percent', 'is_active', 'order',
        )
        extra_kwargs: ClassVar[dict] = {
            'note_es': {'required': False},
            'note_en': {'required': False},
            'discount_percent': {'required': False},
            'is_active': {'required': False},
            'order': {'required': False},
        }

    def validate(self, attrs):
        if self.instance and self.instance.pricing_model != 'requirements':
            raise serializers.ValidationError('Los paquetes históricos son de solo lectura.')
        counts = [attrs.get(f'{size}_count', getattr(self.instance, f'{size}_count', 0))
                  for size in ('xs', 's', 'm')]
        if not sum(counts):
            raise serializers.ValidationError('Incluye al menos un cupo XS, S o M.')
        from content.services.requirement_package_service import price_context
        price_context(attrs.get('nationality', getattr(self.instance, 'nationality', 'COL')))
        attrs['pricing_model'] = 'requirements'
        return attrs

    def validate_validity_months(self, value):
        if value < 1:
            raise serializers.ValidationError('La vigencia debe ser al menos un mes.')
        return value

    def validate_discount_percent(self, value):
        if not 0 <= value < 100:
            raise serializers.ValidationError('El descuento debe estar entre 0 y 99.')
        return value


class HourPackageSettingsSerializer(EditorialModelSerializer):
    """Singleton settings for the hour-packages panel."""

    exchange_rate = serializers.SerializerMethodField()

    def get_exchange_rate(self, obj):
        from content.models import AccountingSettings
        return str(AccountingSettings.load().usd_exchange_rate)

    class Meta:
        model = HourPackageSettings
        fields = (
            'default_view_mode', 'base_rate_col', 'base_rate_ext',
            'base_rate_usa', 'xs_price_cop', 's_price_cop', 'm_price_cop',
            'foreign_multiplier', 'usa_multiplier', 'alliance_xs_count',
            'alliance_s_count', 'alliance_m_count', 'exchange_rate', 'updated_at',
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

    def validate(self, attrs):
        for field in ('xs_price_cop', 's_price_cop', 'm_price_cop', 'foreign_multiplier', 'usa_multiplier'):
            if field in attrs and attrs[field] <= 0:
                raise serializers.ValidationError({field: 'El valor debe ser mayor a cero.'})
        counts = [attrs.get(f'alliance_{size}_count', getattr(self.instance, f'alliance_{size}_count', 0))
                  for size in ('xs', 's', 'm')]
        if not sum(counts):
            raise serializers.ValidationError('Alianza debe incluir al menos un cupo.')
        return attrs
