"""Closed MCP tools for expected-income plans, confirmation and panel-parity writes."""
from calendar import monthrange
from copy import deepcopy
from datetime import date
import re

from rest_framework.exceptions import ErrorDetail, ValidationError

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError
from content.models import IncomeRecord, Ledger, RecurringPayment
from content.serializers.accounting import IncomeRecordSerializer
from content.services import accounting_expected_income_service as service
from content.services.accounting_income_detail_service import build_income_detail_payload
from content.services.accounting_income_duplicate_service import build_income_duplicate_draft, next_billing_date
from content.views.accounting import _ENTITIES, _apply_filters, base_queryset

MONEY_PATTERN = r'^\d{1,12}(\.\d{1,2})?$'
PERIOD_PATTERN = r'^\d{4}-(0[1-9]|1[0-2])$'
DATE_PATTERN = r'^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$'
PERIOD_OR_DATE_PATTERN = r'^\d{4}-(0[1-9]|1[0-2])(-[0-3]\d)?$'
SIDE_EFFECTS = ['Queda en el historial contable y se envía el correo de cambios a los socios.']
COMPACT_FIELDS = (
    'id', 'concept', 'client_name', 'project_name', 'origin', 'ledger', 'period',
    'period_date', 'period_start', 'period_end', 'period_cadence', 'total_amount',
    'gustavo_amount', 'carlos_amount', 'company_amount', 'vat_rate', 'paid_amount',
    'pending_amount', 'payment_status', 'collection_account_status',
    'collection_confidence', 'is_receivable_candidate',
)


def _money(description):
    return {'type': ['number', 'string'], 'minimum': 0, 'maximum': 999999999999.99,
            'pattern': MONEY_PATTERN, 'description': description}


def _relation(description):
    return {'type': ['integer', 'null'], 'minimum': 1, 'description': description}


INCOME_PROPERTIES = {
    'concept': {'type': 'string', 'minLength': 1, 'maxLength': 255,
                'description': 'Concepto del ingreso esperado que aparece en el historial y la cuenta de cobro.'},
    'total_amount': _money('Monto total incluido IVA del ingreso esperado; activa vista previa si cambia.'),
    'base_amount': _money('Base antes de IVA; requiere una tasa registrada y permite calcular el total.'),
    'vat_rate': {'type': ['number', 'string', 'null'], 'minimum': 0, 'maximum': 100,
                 'pattern': r'^\d{1,3}(\.\d{1,2})?$',
                 'description': 'Porcentaje de IVA entre 0 y 100; null significa sin registrar. Es obligatorio al crear.'},
    'vat_amount': _money('Monto de IVA para comprobar el cálculo; debe coincidir exactamente con la tasa y la base.'),
    'gustavo_amount': _money('Monto de Gustavo; junto con Carlos no puede superar el total.'),
    'carlos_amount': _money('Monto de Carlos; si el reparto era automático se recalcula con la regla del Panel.'),
    'company_amount': _money('Monto residual de empresa; envía al menos un socio para derivar el restante.'),
    'destination': {'type': 'string', 'enum': ['partners'],
                    'description': 'Destino Socios; un ingreso esperado no puede enviarse al bolsillo.'},
    'ledger': {'type': 'string', 'enum': list(Ledger.values), 'default': 'company',
               'description': 'Contabilidad; empresa permite reparto y una contabilidad personal pertenece al 100 % a su dueño.'},
    'period': {'type': 'string', 'pattern': PERIOD_PATTERN,
               'description': 'Mes esperado de cobro AAAA-MM, alias de period_date con día 1; ambos deben coincidir en mes.'},
    'period_date': {'type': 'string', 'pattern': PERIOD_OR_DATE_PATTERN,
                    'description': 'Fecha esperada de cobro AAAA-MM-DD o mes AAAA-MM; prevalece sobre el inicio del servicio.'},
    'period_start': {'type': ['string', 'null'], 'pattern': PERIOD_OR_DATE_PATTERN,
                     'description': 'Inicio de la ventana de hosting; AAAA-MM-DD o AAAA-MM con día 1, null para quitarla.'},
    'period_end': {'type': ['string', 'null'], 'pattern': DATE_PATTERN,
                   'description': 'Fin inclusivo de la ventana de hosting, en formato AAAA-MM-DD; null para quitarla.'},
    'period_cadence': {'type': 'string', 'enum': ['', *RecurringPayment.Frequency.values],
                       'description': 'Periodicidad de la ventana de hosting, por ejemplo semiannual para seis meses.'},
    'origin': {'type': 'string', 'enum': list(IncomeRecord.Origin.values),
               'description': 'Línea de negocio del ingreso esperado; hosting requiere ventana y periodicidad.'},
    'client': _relation('Identificador del perfil del cliente; null significa sin cliente. Cambiarlo puede limpiar el proyecto.'),
    'project': _relation('Identificador del proyecto del cliente; null significa sin proyecto.'),
    'collection_confidence': {'type': 'string', 'enum': ['', *IncomeRecord.CollectionConfidence.values],
                              'description': 'Probabilidad de cobro: high, medium o low; vacío deja la clasificación sin asignar.'},
    'notes': {'type': 'string', 'description': 'Notas del ingreso esperado, incluida la referencia documental y la regla de renovación.'},
}
ID_PROPERTY = {'type': 'integer', 'minimum': 1, 'description': 'Identificador positivo del ingreso esperado.'}
IF_MATCH_PROPERTY = {'type': 'string', 'pattern': r'^[0-9a-fA-F]{64}$',
                     'description': 'Huella etag obtenida al leer; rechaza cambios si el ingreso o sus pagos y cuentas variaron.'}
LIST_PROPERTIES = {
    'client_id': _relation('Filtra por perfil del cliente; null busca ingresos esperados sin cliente.'),
    'project_id': _relation('Filtra por proyecto; null busca ingresos esperados sin proyecto.'),
    'origin': {'type': 'array', 'minItems': 1, 'uniqueItems': True,
               'items': {'type': 'string', 'enum': [*IncomeRecord.Origin.values, 'none'],
                         'description': 'Línea de negocio; none representa sin clasificar.'},
               'description': 'Una o varias líneas de negocio; none incluye ingresos sin clasificar.'},
    'period_from': {'type': 'string', 'pattern': PERIOD_OR_DATE_PATTERN,
                    'description': 'Primer mes o fecha de cobro; AAAA-MM se convierte al primer día del mes.'},
    'period_to': {'type': 'string', 'pattern': PERIOD_OR_DATE_PATTERN,
                  'description': 'Último mes o fecha de cobro; AAAA-MM se convierte al último día del mes.'},
    'payment_status': {'type': 'array', 'minItems': 1, 'uniqueItems': True,
                       'items': {'type': 'string', 'enum': ['pending', 'partial', 'paid'],
                                 'description': 'Estado pendiente, parcialmente pagado o pagado.'},
                       'description': 'Uno o varios estados de pago calculados con pagos y deducciones.'},
    'q': {'type': 'string', 'minLength': 1, 'maxLength': 200,
           'description': 'Texto que se busca en el concepto o las notas del ingreso esperado.'},
    'page': {'type': 'integer', 'minimum': 1, 'default': 1,
             'description': 'Número de página, empezando por 1.'},
    'page_size': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25,
                  'description': 'Cantidad de ingresos esperados por página, entre 1 y 100.'},
}


def _schema(properties, required=()):
    return {'type': 'object', 'additionalProperties': False,
            'properties': deepcopy(properties), 'required': list(required)}


def _run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except service.ExpectedIncomeError as exc:
        raise ToolError(str(exc), code=exc.code, details=exc.details) from exc


def _strict(arguments, allowed, required=(), *, prefix=''):
    if not isinstance(arguments, dict):
        raise ValidationError({prefix or 'arguments': ErrorDetail('Debe ser un objeto JSON.', code='invalid')})
    errors = {f'{prefix}{key}': ErrorDetail('Campo desconocido para esta herramienta.', code='unknown_field')
              for key in sorted(set(arguments) - set(allowed))}
    errors.update({f'{prefix}{key}': ErrorDetail('Este campo es obligatorio.', code='required')
                   for key in required if key not in arguments})
    if errors:
        raise ValidationError(errors)


def _positive_id(value, field, *, nullable=False):
    if nullable and value is None:
        return None
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        raise ValidationError({field: ErrorDetail('Indica un identificador entero positivo.', code='invalid')})
    return value


def _public_fields(arguments, action):
    extras = {'income_id', 'if_match'} if action == 'update' else {'income_id', 'overrides'} if action == 'duplicate' else set()
    allowed = extras if action == 'duplicate' else set(INCOME_PROPERTIES) | extras
    required = ('income_id',) if action in ('update', 'duplicate') else ('concept', 'origin', 'vat_rate')
    _strict(arguments, allowed, required)
    if action in ('update', 'duplicate'):
        _positive_id(arguments['income_id'], 'income_id')
    if action == 'duplicate':
        fields = arguments.get('overrides', {})
        _strict(fields, INCOME_PROPERTIES, prefix='overrides.')
    else:
        fields = {key: value for key, value in arguments.items() if key in INCOME_PROPERTIES}
    for key in ('client', 'project'):
        if key in fields:
            _positive_id(fields[key], f'overrides.{key}' if action == 'duplicate' else key, nullable=True)
    if 'if_match' in arguments:
        if not isinstance(arguments['if_match'], str) or not re.fullmatch(r'[0-9a-fA-F]{64}', arguments['if_match']):
            raise ValidationError({'if_match': ErrorDetail('Indica una huella hexadecimal de 64 caracteres.', code='invalid')})
    return fields


def _prepare(arguments, action):
    fields = _public_fields(arguments, action)
    if action == 'create':
        plan = _run(service.build_change_plan, fields)
        return {'fields': plan['fields']}
    income = _run(service.load_expected_income, arguments['income_id'])
    if action == 'duplicate':
        etag = _run(service.income_etag, income)
        fields = _run(service.build_duplicate_fields, income, fields)
        plan = _run(service.build_change_plan, fields)
        return {'income_id': income.pk, 'fields': plan['fields'], '_source_etag': etag}
    plan = _run(service.build_change_plan, fields, income=income, if_match=arguments.get('if_match'))
    return {'income_id': income.pk, 'fields': plan['fields'], '_expected_etag': plan['etag']}


def _needs_confirmation(arguments):
    fields = _public_fields(arguments, 'update')
    income = _run(service.load_expected_income, arguments['income_id'])
    return _run(service.build_change_plan, fields, income=income,
                if_match=arguments.get('if_match'))['needs_confirmation']


def _etags(arguments):
    income = _run(service.load_expected_income, arguments['income_id'])
    expected = arguments.get('_expected_etag', arguments.get('_source_etag'))
    return {'income': _run(service.check_etag, income, expected)}


def _compact_row(income):
    data = IncomeRecordSerializer(income).data
    result = {key: data[key] for key in COMPACT_FIELDS}
    result.update(client_id=data['client'], project_id=data['project'],
                  locks=[row['code'] for row in service.income_editability(income)['blockers']])
    return result


def _impact(arguments, action):
    source = _run(service.load_expected_income, arguments['income_id']) if action != 'create' else None
    if action == 'update':
        plan = _run(service.build_change_plan, arguments['fields'], income=source,
                    if_match=arguments['_expected_etag'])
    else:
        if source is not None:
            _run(service.check_etag, source, arguments['_source_etag'])
        plan = _run(service.build_change_plan, arguments['fields'])
    verb = {'update': 'Actualizar', 'create': 'Crear', 'duplicate': 'Duplicar'}[action]
    main = f"total {plan['after']['total_amount']} y cobro {plan['after']['period_date']}"
    if action == 'update':
        changed = {row['field']: row for row in plan['changes']}
        primary = next((changed[key] for key in service.CONFIRMATION_FIELDS if key in changed), None)
        if primary:
            main = f"{primary['label']}: {primary['before']} → {primary['after']}"
    impact = {
        'summary': f"{verb} el ingreso esperado «{plan['after']['concept']}»: {main}.",
        'action': action, 'income_id': source.pk if action == 'update' else None,
        'etag': plan['etag'] if action == 'update' else arguments.get('_source_etag'),
        **{key: plan[key] for key in ('changes', 'before', 'after', 'split', 'vat', 'notices',
                                     'warnings', 'requires_confirmation_because')},
        'side_effects': list(SIDE_EFFECTS),
    }
    if action == 'duplicate':
        draft = build_income_duplicate_draft(source)
        start = plan['after']['period_start']
        offset_date = next_billing_date(source, date.fromisoformat(start)).isoformat() if start else None
        impact['source'] = {**_compact_row(source), 'etag': arguments['_source_etag']}
        impact['period_rule'] = {
            'rule': 'kept_payment_offset' if offset_date == plan['after']['period_date'] else 'explicit_billing_date',
            'period_anchor': draft['period_anchor'],
            'message': 'La ventana cubre el servicio; la fecha esperada de cobro conserva su desplazamiento salvo cambio explícito.',
        }
    return service.json_safe(impact)


def _outcome(income, **status):
    income = _run(service.load_expected_income, income.pk)
    return service.json_safe({**status, 'income': IncomeRecordSerializer(income).data,
                              'etag': service.income_etag(income), 'editability': service.income_editability(income)})


def _apply(arguments, action):
    context = current_mcp_context()
    confirmed = bool(context and context.confirmation_bypass)
    if not confirmed:
        fields = _public_fields(arguments, action)
        if action != 'update':
            raise ToolError('Este ingreso esperado requiere vista previa y confirm_action.', code='CONFIRMATION_REQUIRED')
        income = _run(service.load_expected_income, arguments['income_id'])
        plan = _run(service.build_change_plan, fields, income=income, if_match=arguments.get('if_match'))
        if plan['needs_confirmation']:
            raise ToolError('El cambio ahora requiere una nueva vista previa y confirm_action.', code='CONFIRMATION_REQUIRED')
        expected = plan['etag']
    else:
        key = '_source_etag' if action == 'duplicate' else '_expected_etag'
        required = ('fields',) if action == 'create' else ('income_id', 'fields', key)
        _strict(arguments, required, required)
        fields = arguments['fields']
        _strict(fields, INCOME_PROPERTIES)
        expected = arguments.get(key)
        income = _run(service.load_expected_income, arguments['income_id']) if action == 'update' else None
        plan = _run(service.build_change_plan, fields, income=income, if_match=expected if income else None)
    if action == 'update':
        if not plan['changes']:
            return _outcome(income, updated=False, notices=plan['notices'], warnings=plan['warnings'])
        income = _run(service.apply_update, income.pk, fields, expected_etag=expected, actor=mcp_actor())
        return _outcome(income, updated=True, notices=plan['notices'], warnings=plan['warnings'])
    if action == 'duplicate':
        income = _run(service.apply_duplicate, arguments['income_id'], fields,
                      expected_etag=expected, actor=mcp_actor())
    else:
        income = _run(service.apply_create, fields, actor=mcp_actor())
    return _outcome(income, created=True, notices=plan['notices'], warnings=plan['warnings'])


def _period_bound(value, field, *, end=False):
    try:
        if not isinstance(value, str):
            raise ValueError
        result = date.fromisoformat(f'{value}-01' if len(value) == 7 else value)
        return result.replace(day=monthrange(result.year, result.month)[1]) if end and len(value) == 7 else result
    except ValueError as exc:
        raise ValidationError({field: ErrorDetail('Indica un mes AAAA-MM o una fecha AAAA-MM-DD válida.', code='invalid')}) from exc


def _list(arguments):
    _strict(arguments, LIST_PROPERTIES)
    page, size = arguments.get('page', 1), arguments.get('page_size', 25)
    _positive_id(page, 'page')
    _positive_id(size, 'page_size')
    if size > 100:
        raise ValidationError({'page_size': ErrorDetail('El máximo es 100.', code='max_value')})
    params = {}
    for key in ('client_id', 'project_id'):
        if key in arguments:
            value = _positive_id(arguments[key], key, nullable=True)
            params[key.removesuffix('_id')] = 'none' if value is None else str(value)
    for key in ('origin', 'payment_status'):
        if key in arguments:
            values = arguments[key]
            choices = LIST_PROPERTIES[key]['items']['enum']
            if (not isinstance(values, list) or not values
                    or any(not isinstance(value, str) or value not in choices for value in values)):
                raise ValidationError({key: ErrorDetail('Indica una lista no vacía de opciones válidas.', code='invalid')})
            if len(set(values)) != len(values):
                raise ValidationError({key: ErrorDetail('No repitas opciones.', code='invalid')})
            params[key] = ','.join(values)
    for key, target in (('period_from', 'date_from'), ('period_to', 'date_to')):
        if key in arguments:
            params[target] = _period_bound(arguments[key], key, end=key == 'period_to').isoformat()
    if 'date_from' in params and 'date_to' in params and params['date_from'] > params['date_to']:
        raise ValidationError({'period_to': ErrorDetail('El fin debe ser igual o posterior al inicio.', code='invalid')})
    if 'q' in arguments:
        value = arguments['q']
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200:
            raise ValidationError({'q': ErrorDetail('El texto debe tener entre 1 y 200 caracteres.', code='invalid')})
        params['q'] = value.strip()
    config = {**_ENTITIES['income'], 'search_fields': ('concept', 'notes')}
    try:
        queryset = _apply_filters(base_queryset(config).filter(kind='expected'), params, config)
    except ValueError as exc:
        raise ToolError(str(exc), code='VALIDATION_ERROR') from exc
    count = queryset.count()
    rows = service.with_income_relations(queryset.order_by('-period_date', '-id'))[(page - 1) * size:page * size]
    return {'results': [_compact_row(row) for row in rows], 'count': count, 'page': page,
            'page_size': size, 'num_pages': (count + size - 1) // size, 'has_next': page * size < count}


def _get(arguments):
    _strict(arguments, {'income_id'}, ('income_id',))
    income = _run(service.load_expected_income, _positive_id(arguments['income_id'], 'income_id'))
    payload = build_income_detail_payload(income)
    return service.json_safe({
        'income': payload['income'], 'payments': payload['liquid'], 'deductions': payload['expenses'],
        'collection_account': payload['collection_account'], 'etag': service.income_etag(income),
        'editability': service.income_editability(income),
    })


READ_NOTICE = (
    'Consulta el ingreso esperado sin modificarlo. Para cambiar dinero, IVA, reparto, contabilidad, '
    'cliente o proyecto usa vista previa y confirm_action: se aplica la regla de reparto del Panel '
    'y se respetan bloqueos por pagos, datos conservados y cuentas emitidas.'
)
WRITE_NOTICE = (
    'Sin reparto explícito usa la regla del Panel al crear o recalcula un reparto automático al cambiar '
    'el total; conserva un reparto personalizado y avisa. Los pagos y las cuentas emitidas bloquean '
    'finanzas, cliente y proyecto; los datos conservados bloquean toda edición.'
)
EXPECTED_INCOME_TOOLS = [
    {'name': 'list_expected_incomes', 'risk': 'read',
     'description': f'Lista cada ingreso esperado por cliente, proyecto, origen, fechas o texto, con importes y bloqueos. {READ_NOTICE}',
     'input_schema': _schema(LIST_PROPERTIES), 'handler': _list},
    {'name': 'get_expected_income', 'risk': 'read',
     'description': f'Lee el ingreso esperado, pagos, deducciones, cuenta de cobro y etag para comprobar su versión. {READ_NOTICE}',
     'input_schema': _schema({'income_id': ID_PROPERTY}, ('income_id',)), 'handler': _get},
    {'name': 'update_expected_income', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': ('Actualiza un ingreso esperado: cambios descriptivos se aplican directamente; dinero, IVA, reparto, '
                     f'contabilidad, cliente o proyecto requieren vista previa y confirm_action. {WRITE_NOTICE}'),
     'input_schema': _schema({'income_id': ID_PROPERTY, 'if_match': IF_MATCH_PROPERTY, **INCOME_PROPERTIES}, ('income_id',)),
     'confirmation_predicate': _needs_confirmation, 'prepare_arguments': lambda args: _prepare(args, 'update'),
     'impact_builder': lambda args: _impact(args, 'update'), 'etag_resolver': _etags,
     'handler': lambda args: _apply(args, 'update')},
    {'name': 'create_expected_income', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': ('Crea un ingreso esperado con total o base y tasa de IVA explícita (null permitido). '
                     f'Siempre pide vista previa y confirm_action antes de escribir. {WRITE_NOTICE}'),
     'input_schema': _schema(INCOME_PROPERTIES, ('concept', 'origin', 'vat_rate')),
     'prepare_arguments': lambda args: _prepare(args, 'create'), 'impact_builder': lambda args: _impact(args, 'create'),
     'handler': lambda args: _apply(args, 'create')},
    {'name': 'duplicate_expected_income', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': ('Duplica un ingreso esperado para el siguiente ciclo conservando el desfase de cobro y aceptando overrides. '
                     f'Siempre pide vista previa y confirm_action; nunca copia pagos ni cuentas. {WRITE_NOTICE}'),
     'input_schema': _schema({'income_id': ID_PROPERTY,
                             'overrides': {**_schema(INCOME_PROPERTIES),
                                           'description': 'Campos que sustituyen el borrador del siguiente ingreso esperado.'}}, ('income_id',)),
     'prepare_arguments': lambda args: _prepare(args, 'duplicate'), 'impact_builder': lambda args: _impact(args, 'duplicate'),
     'etag_resolver': _etags, 'handler': lambda args: _apply(args, 'duplicate')},
]
