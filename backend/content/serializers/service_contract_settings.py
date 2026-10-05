"""Numeric service terms, while retaining the existing contractual text boundary."""
from typing import ClassVar

from num2words import num2words
from rest_framework import serializers


class ServiceTermIntegerField(serializers.IntegerField):
    default_error_messages: ClassVar[dict] = {
        'invalid': 'Escribe un entero entre 1 y 999.',
        'min_value': 'Escribe un entero entre 1 y 999.',
        'max_value': 'Escribe un entero entre 1 y 999.',
    }

    def __init__(self, **kwargs):
        super().__init__(min_value=1, max_value=999, **kwargs)

    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail('invalid')
        return super().to_internal_value(data)


def format_service_term(value, *, duration=False):
    """Spanish masculine apocope: the template supplies días after notice values."""
    words = num2words(value, lang='es')
    if words.endswith('veintiuno'):
        words = words[:-9] + 'veintiún'
    elif words.endswith('uno'):
        words = words[:-3] + 'un'
    unit = (' mes' if value == 1 else ' meses') if duration else ''
    return f'{words} ({value}){unit}'


class ServiceTermField(serializers.CharField):
    """New integers become text; historical text remains byte-for-byte intact."""

    def __init__(self, *, duration=False, **kwargs):
        self.duration = duration
        super().__init__(trim_whitespace=False, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, str):
            return super().to_internal_value(data)
        value = ServiceTermIntegerField().run_validation(data)
        return format_service_term(value, duration=self.duration)


class StrictSettingsSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({
                    key: 'Este campo no se puede modificar aquí.' for key in unknown
                })
        return super().to_internal_value(data)


class ServiceContractSettingsSerializer(StrictSettingsSerializer):
    duration_options = serializers.ListField(
        child=ServiceTermIntegerField(), allow_empty=False, max_length=999,
    )
    notice_options = serializers.ListField(
        child=ServiceTermIntegerField(), allow_empty=False, max_length=999,
    )
    default_duration = ServiceTermIntegerField()
    default_renewal_notice = ServiceTermIntegerField()
    default_termination_notice = ServiceTermIntegerField()

    def validate(self, attrs):
        errors = {}
        for key in ('duration_options', 'notice_options'):
            if len(set(attrs[key])) != len(attrs[key]):
                errors[key] = 'Las opciones no pueden repetirse.'
            attrs[key] = sorted(attrs[key])
        for default, options in (
            ('default_duration', 'duration_options'),
            ('default_renewal_notice', 'notice_options'),
            ('default_termination_notice', 'notice_options'),
        ):
            if attrs[default] not in attrs[options]:
                errors[default] = 'Selecciona un valor incluido en las opciones.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class CompanyServiceSettingsSerializer(StrictSettingsSerializer):
    service_contract_settings = ServiceContractSettingsSerializer()


def fill_service_term_defaults(raw_params):
    """Explicit proposal values win; defaults only fill missing commercial terms."""
    from content.models.company_settings import CompanySettings, default_service_contract_settings
    company = CompanySettings.objects.filter(pk=1).values_list('service_contract_settings', flat=True).first()
    settings = company if company is not None else default_service_contract_settings()
    params = dict(raw_params or {})
    for key, default, duration in [
        ('service_initial_term', 'default_duration', True),
        ('service_renewal_notice_days', 'default_renewal_notice', False),
        ('service_termination_notice_days', 'default_termination_notice', False),
    ]:
        if params.get(key) in (None, ''):
            params[key] = format_service_term(settings[default], duration=duration)
    return params
