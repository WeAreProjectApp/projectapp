"""One income family, retaining the expected-income service's stronger guards."""
from copy import deepcopy

from django.db import transaction
from rest_framework.exceptions import ErrorDetail, ValidationError

from content.mcp import accounting_tools as generic
from content.mcp import expected_income_tools as expected
from content.mcp.protocol import ToolError
from content.mcp.context import current_mcp_context
from content.models import IncomeRecord
from content.serializers.accounting import IncomeRecordSerializer
from content.services import accounting_expected_income_service as service


def _income(arguments):
    income_id = expected._positive_id(arguments.get('income_id'), 'income_id')
    income = generic._get_instance_or_error('income', income_id)
    _check_kind(income.kind)
    return income


def _check_kind(kind):
    context = current_mcp_context()
    kinds = getattr(context.credential, 'income_kinds', []) if context else []
    if kinds and kind not in kinds:
        raise ToolError('La credencial no permite este tipo de ingreso.', code='FORBIDDEN')


def _list(arguments):
    properties = {**generic._list_schema('income')['properties'], **expected.LIST_PROPERTIES}
    expected._strict(arguments, properties)
    page = expected._positive_id(arguments.get('page', 1), 'page')
    size = expected._positive_id(arguments.get('page_size', 25), 'page_size')
    if size > 100:
        raise ToolError('page_size no puede superar 100.')
    params = {key: value for key, value in arguments.items() if key not in expected.LIST_PROPERTIES}
    for key in ('client_id', 'project_id'):
        if key in arguments:
            value = expected._positive_id(arguments[key], key, nullable=True)
            params[key[:-3]] = 'none' if value is None else str(value)
    for key in ('origin', 'payment_status'):
        if key in arguments:
            values = arguments[key]
            choices = expected.LIST_PROPERTIES[key]['items']['enum']
            if not isinstance(values, list) or not values or any(not isinstance(value, str) or value not in choices for value in values):
                raise ToolError(f'{key} debe ser una lista no vacía de opciones válidas.')
            params[key] = ','.join(values)
    for key, target in (('period_from', 'date_from'), ('period_to', 'date_to')):
        if key in arguments:
            params[target] = expected._period_bound(arguments[key], key, end=key == 'period_to').isoformat()
    if 'q' in arguments:
        params['q'] = arguments['q']
    if params.get('date_from', '') > params.get('date_to', '9999-12-31'):
        raise ToolError('El fin debe ser igual o posterior al inicio.')
    config = generic._ENTITIES['income']
    try:
        queryset = generic._apply_filters(generic.base_queryset(config), generic._str_params(params), config)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    context = current_mcp_context()
    kinds = getattr(context.credential, 'income_kinds', []) if context else []
    if kinds:
        queryset = queryset.filter(kind__in=kinds)
    count = queryset.count()
    rows = service.with_income_relations(queryset.order_by('-period_date', '-pk'))[(page - 1) * size:page * size]
    data = []
    for income in rows:
        item = dict(IncomeRecordSerializer(income).data)
        item['editability'] = service.json_safe(service.income_editability(income))
        data.append(item)
    return {'results': data, 'count': count, 'page': page, 'page_size': size,
            'num_pages': (count + size - 1) // size, 'has_next': page * size < count}


def _get(arguments):
    income = _income(arguments)
    if income.kind == 'expected':
        return expected._get(arguments)
    payload = generic.get_income_detail({'record_id': income.pk})
    return {**payload, 'payments': payload.get('liquid', []), 'deductions': payload.get('expenses', []),
            'etag': service.income_etag(income), 'editability': service.json_safe(service.income_editability(income))}


def _prepare(arguments, action):
    arguments = dict(arguments)
    instance = _income(arguments) if action != 'create' else None
    if action == 'update' and not (set(arguments) - {'income_id', 'if_match'}):
        raise ToolError('Incluye al menos un campo para actualizar el ingreso.')
    kind = arguments.pop('kind', instance.kind if instance else 'expected')
    _check_kind(kind)
    if action == 'duplicate':
        _check_kind('expected')
        # Panel duplication always opens the next expected charge, even from a liquid.
        income = _income(arguments)
        fields = expected._run(service.build_duplicate_fields, income, arguments.get('overrides', {}))
        plan = expected._run(service.build_change_plan, fields)
        return {'branch': 'expected', 'action': 'create', 'prepared': {'fields': plan['fields']},
                'source_id': income.pk, 'source_etag': service.income_etag(income)}
    if kind == 'expected' and (instance is None or instance.kind == 'expected'):
        arguments = generic._resolve_project_reference(
            'income', arguments, instance=_income(arguments) if action == 'update' else None,
        )
        return {'branch': 'expected', 'action': action,
                'prepared': expected._prepare(arguments, action)}
    if kind not in IncomeRecord.Kind.values:
        raise ToolError('kind debe ser expected, liquid o lost.')
    fields = {key: value for key, value in arguments.items() if key not in {'income_id', 'if_match'}}
    fields = generic._resolve_project_reference('income', fields, instance=instance)
    fields['kind'] = kind
    if instance is not None and instance.kind == 'expected':
        editability = service.income_editability(instance)
        if editability['blockers']:
            raise ToolError('El ingreso esperado tiene datos bloqueados para cambiar de tipo.',
                            code='INCOME_LOCKED', details={'blockers': editability['blockers']})
        expected._run(service.build_change_plan,
                      {key: value for key, value in fields.items() if key in service.INCOME_FIELDS},
                      income=instance, if_match=arguments.get('if_match'))
    serializer = generic._ENTITIES['income']['write'](instance, data=fields, partial=instance is not None)
    unknown = set(fields) - set(serializer.fields)
    if unknown:
        raise ValidationError({key: ErrorDetail('Campo exclusivo de ingresos esperados.', code='unknown_field') for key in sorted(unknown)})
    serializer.is_valid(raise_exception=True)
    if instance is not None:
        expected._run(service.check_etag, instance, arguments.get('if_match'))
    return {'branch': 'generic', 'action': action, 'prepared': fields,
            'income_id': instance.pk if instance else None,
            'before': service.json_safe(IncomeRecordSerializer(instance).data) if instance else None,
            'etag': service.income_etag(instance) if instance else None}


def _etags(arguments):
    if 'source_id' in arguments:
        income = generic._get_instance_or_error('income', arguments['source_id'])
        return {'source': service.income_etag(income)}
    if arguments['branch'] == 'expected':
        return expected._etags(arguments['prepared']) if arguments['action'] == 'update' else {}
    if arguments.get('income_id'):
        return {'income': service.income_etag(generic._get_instance_or_error('income', arguments['income_id']))}
    return {}


def _impact(arguments):
    if arguments['branch'] == 'expected':
        impact = expected._impact(arguments['prepared'], arguments['action'])
    else:
        impact = {'summary': 'Guardar el ingreso con las validaciones del Panel.',
                  'action': arguments['action'], 'income_id': arguments.get('income_id'),
                  'before': arguments.get('before'),
                  'after': arguments['prepared'], 'side_effects': list(expected.SIDE_EFFECTS)}
    if 'source_id' in arguments:
        impact['source_id'] = arguments['source_id']
        impact['source_etag'] = arguments['source_etag']
    return impact


@transaction.atomic
def _apply(arguments):
    locked_id = arguments.get('source_id') or arguments.get('income_id')
    if locked_id:
        service.lock_billing_rows(income_ids=[locked_id], include_income_children=True,
                                 include_origin_documents=True)
    if 'source_id' in arguments:
        expected._run(service.check_etag,
                      generic._get_instance_or_error('income', arguments['source_id']), arguments['source_etag'])
    if arguments['branch'] == 'expected':
        return expected._apply(arguments['prepared'], arguments['action'])
    fields = arguments['prepared']
    if arguments['action'] == 'update':
        income = generic._get_instance_or_error('income', arguments['income_id'])
        expected._run(service.check_etag, income, arguments['etag'])
        result = generic._make_update('income')({'record_id': income.pk, **fields})
    else:
        result = generic._make_create('income')(fields)
    return {'income': result, 'etag': service.income_etag(IncomeRecord.objects.get(pk=result['id']))}


def build_income_tools():
    tools = {tool['name']: tool for tool in generic.ACCOUNTING_TOOLS}
    listed = deepcopy(tools['list_income'])
    listed.update(name='list_incomes', operation_id='income:list', handler=_list,
                  strict_arguments=True,
                  input_schema=expected._schema({**generic._list_schema('income')['properties'], **expected.LIST_PROPERTIES}))
    detail = deepcopy(tools['get_income_detail'])
    detail.update(name='get_income', operation_id='income:get', handler=_get,
                  input_schema=expected._schema({'income_id': expected.ID_PROPERTY}, ('income_id',)))
    properties = {**deepcopy(generic._ENTITY_FIELDS['income']['props']), **deepcopy(expected.INCOME_PROPERTIES)}
    properties['destination'] = deepcopy(generic._ENTITY_FIELDS['income']['props']['destination'])
    kind = {'type': 'string', 'enum': list(IncomeRecord.Kind.values),
            'description': 'expected: por cobrar; liquid: recibido; lost: perdido. Se requiere al crear.'}
    properties['kind'] = kind
    writes = []
    for action in ('create', 'update', 'duplicate'):
        if action == 'create':
            schema = expected._schema(properties, ('concept', 'kind', 'origin'))
            schema['if'] = {'properties': {'kind': {'const': 'expected'}}}
            schema['then'] = {'required': ['vat_rate']}
        elif action == 'update':
            schema = expected._schema({**properties,
                                       'income_id': expected.ID_PROPERTY, 'if_match': expected.IF_MATCH_PROPERTY}, ('income_id',))
        else:
            schema = expected._schema({'income_id': expected.ID_PROPERTY,
                                      'overrides': expected._schema(expected.INCOME_PROPERTIES)}, ('income_id',))
        writes.append({
            'name': f'{action}_income', 'operation_id': f'income:{action}',
            'description': (
                f'{action.capitalize()} un ingreso con las reglas del Panel. La duplicación abre el siguiente esperado; '
                'no copia pagos ni cuentas. Los esperados conservan validación de IVA, reparto, bloqueos y etag. '
                'Devuelve vista previa y requiere confirm_action antes de escribir.'
            ),
            'risk': 'sensitive', 'requires_confirmation': True, 'strict_arguments': True,
            'input_schema': schema, 'prepare_arguments': lambda args, action=action: _prepare(args, action),
            'impact_builder': _impact, 'etag_resolver': _etags, 'handler': _apply,
        })
    return [listed, detail, *writes]
