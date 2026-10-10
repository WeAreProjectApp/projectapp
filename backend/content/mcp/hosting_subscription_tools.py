"""Confirmed hosting lifecycle decisions on the shared financial service."""

from accounts.models import HostingSubscription
from accounts.services.billing_access import require_billing_admin
from accounts.services.hosting_subscription_lifecycle import apply_change, plan_change
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError
from content.services.diagnostic_privacy import register_mcp_domain_codes

register_mcp_domain_codes(
    'subscription_change_blocked', 'stale_subscription_preview',
    'subscription_lifecycle_required',
)

FIELDS = {
    'subscription_id': {'type': 'integer', 'minimum': 1,
                        'description': 'Identificador entero positivo de la suscripción de hosting.'},
    'action': {
        'type': 'string', 'enum': ['pause', 'cancel', 'resume'],
        'description': (
            'pause: pausa manual y anula cobros futuros; cancel: cancela definitivamente '
            'y anula cobros futuros; resume: reanuda una pausa manual restaurando cobros '
            'aún futuros o abriendo un ciclo nuevo sin cobrar el tiempo pausado.'
        ),
    },
    'effective_date': {
        'type': 'string', 'format': 'date',
        'description': 'Fecha efectiva (AAAA-MM-DD), hasta hoy UTC; por defecto hoy.',
    },
}


class PreviewSerializer(serializers.Serializer):
    subscription_id = serializers.IntegerField(min_value=1, error_messages={
        'invalid': 'Usa un identificador entero positivo.',
        'min_value': 'Usa un identificador entero positivo.', 'null': 'Indica la suscripción.',
    })
    action = serializers.ChoiceField(choices=('pause', 'cancel', 'resume'), error_messages={
        'invalid_choice': 'Elige pausar, cancelar o reanudar.', 'null': 'Indica la acción.',
    })
    effective_date = serializers.DateField(default=lambda: timezone.now().date(), error_messages={
        'invalid': 'Usa una fecha válida (AAAA-MM-DD).', 'null': 'Usa una fecha válida (AAAA-MM-DD).',
        'datetime': 'Usa una fecha sin hora (AAAA-MM-DD).',
    })

    def validate_subscription_id(self, value):
        if isinstance(self.initial_data['subscription_id'], bool) or not isinstance(self.initial_data['subscription_id'], int):
            raise serializers.ValidationError('Usa un identificador entero positivo.')
        return value


class StringField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class ChangeSerializer(PreviewSerializer):
    reason = StringField(min_length=3, max_length=500, error_messages={
        'invalid': 'Escribe el motivo como texto.', 'blank': 'Escribe un motivo.',
        'null': 'Escribe un motivo.', 'required': 'El motivo es obligatorio.',
        'min_length': 'Escribe un motivo de al menos 3 caracteres.',
        'max_length': 'Escribe un motivo de hasta 500 caracteres.',
    })
    expected_impact_hash = StringField(error_messages={
        'invalid': 'Usa el impact_hash de la vista previa como texto.',
        'blank': 'Indica el impact_hash de la vista previa.',
        'null': 'Indica el impact_hash de la vista previa.',
        'required': 'El impact_hash de la vista previa es obligatorio.',
    })


def _prepare(arguments, *, change=False):
    serializer = (ChangeSerializer if change else PreviewSerializer)(data=arguments)
    unknown = set(arguments) - set(serializer.fields)
    if unknown:
        raise ToolError(
            'Hay campos desconocidos.', code='unknown_field',
            details={'fields': sorted(unknown)},
        )
    serializer.is_valid(raise_exception=True)
    require_billing_admin(mcp_actor())
    # Intent arguments must be JSON-serializable, including the frozen default
    # date so confirmation cannot silently change its meaning after midnight.
    args = dict(serializer.validated_data)
    args['effective_date'] = args['effective_date'].isoformat()
    return args


def _preview(arguments):
    subscription = HostingSubscription.objects.filter(pk=arguments['subscription_id']).first()
    if subscription is None:
        raise NotFound('Suscripción de hosting no encontrada.')
    return plan_change(subscription, arguments['action'], arguments.get('effective_date'))


def _read(arguments):
    return _preview(_prepare(arguments))


def _impact(arguments):
    preview = _preview(arguments)
    if preview['impact_hash'] != arguments['expected_impact_hash']:
        raise ToolError('El impacto cambió. Vuelve a revisar la vista previa.', code='STALE_VERSION')
    if not preview['can_apply']:
        raise ToolError(
            'La suscripción tiene bloqueos.', code='SUBSCRIPTION_CHANGE_BLOCKED',
            details={'blockers': preview['blockers'], 'can_apply': False},
        )
    return {**preview, 'reason': arguments['reason']}


def _change(arguments):
    args = _prepare(arguments, change=True)
    return apply_change(
        args['subscription_id'], args['action'], args['effective_date'],
        args['reason'], args['expected_impact_hash'], mcp_actor(),
    )


HOSTING_SUBSCRIPTION_TOOLS = [
    {
        'name': 'preview_hosting_subscription_change',
        'description': (
            'Previsualiza pausar, cancelar o reanudar una suscripción de hosting: anula '
            'cobros abiertos posteriores a la fecha efectiva y conserva pagos recibidos, '
            'historial de pagos, ciclos contables y cuentas de cobro sin modificarlos.'
        ),
        'risk': 'read', 'strict_arguments': True,
        'input_schema': {
            'type': 'object', 'additionalProperties': False, 'properties': FIELDS,
            'required': ['subscription_id', 'action'],
        },
        'output_schema': {'type': 'object'},
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
        'handler': _read,
    },
    {
        'name': 'change_hosting_subscription',
        'description': (
            'Aplica con confirmación una pausa, cancelación o reanudación de hosting: '
            'anula y archiva cobros abiertos futuros, conserva pagos recibidos e historia '
            'contable y audita el motivo. Requiere el impact_hash de la vista previa vigente.'
        ),
        'risk': 'sensitive', 'requires_confirmation': True, 'strict_arguments': True,
        'input_schema': {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                **FIELDS, 'reason': {'type': 'string', 'minLength': 3, 'maxLength': 500,
                                    'description': 'Motivo de la pausa, cancelación o reanudación, de 3 a 500 caracteres.'},
                'expected_impact_hash': {'type': 'string', 'minLength': 1,
                                         'description': 'impact_hash no vacío de preview_hosting_subscription_change; se revalida al confirmar.'},
            },
            'required': ['subscription_id', 'action', 'reason', 'expected_impact_hash'],
        },
        'output_schema': {'type': 'object'},
        'annotations': {'readOnlyHint': False, 'destructiveHint': True,
                        'idempotentHint': False, 'openWorldHint': False},
        'prepare_arguments': lambda arguments: _prepare(arguments, change=True),
        'impact_builder': _impact,
        'etag_resolver': lambda arguments: {'hosting_subscription': _preview(arguments)['impact_hash']},
        'handler': _change,
    },
]
