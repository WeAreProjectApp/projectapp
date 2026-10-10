"""Administrative billing tools over the same validation as Panel and Platform."""
from copy import deepcopy

from accounts.serializers_billing_context import (
    BillingContextAssignmentSerializer,
    BillingContractLinkSerializer,
    HostingEvidenceSerializer,
    HostingReconciliationSerializer,
)
from accounts.services.billing_access import require_billing_admin
from accounts.services.billing_context import associate_account, context_data
from accounts.services.billing_contracts import link_billing_contract
from accounts.services.billing_read import (
    account_for_actor,
    project_billing_options,
    project_hosting_read,
)
from accounts.services.hosting_context import (
    hosting_inventory,
    reconcile_evidence,
    reconcile_hosting,
)
from rest_framework.exceptions import APIException

from content.mcp.actor import mcp_actor
from content.mcp.errors import normalize_error
from content.mcp.protocol import ToolError

ID = {'type': 'integer', 'minimum': 1}
NULL_ID = {'type': ['integer', 'null'], 'minimum': 1}
IDS = {'type': 'array', 'items': ID, 'uniqueItems': True}
COMMON = {'expected_version': {'type': 'integer', 'minimum': 0},
          'reason': {'type': 'string', 'minLength': 1, 'maxLength': 2000}}
ASSOCIATION = {**COMMON, 'billing_nature': {'type': 'string', 'enum': ['contract', 'hosting']},
               'contract_id': NULL_ID, 'amendment_id': NULL_ID, 'project_hosting_id': NULL_ID,
               'hosting_payment_id': NULL_ID}
IDENTITY = {**COMMON, 'subscription_id': NULL_ID, 'hosting_record_ids': IDS, 'operational_record_id': NULL_ID}
EVIDENCE = {**COMMON, 'label': {'type': 'string', 'minLength': 1, 'maxLength': 200},
            'group_id': NULL_ID, 'payment_ids': IDS, 'cycle_ids': IDS, 'document_ids': IDS}
PAYLOAD_DESCRIPTIONS = {
    BillingContractLinkSerializer: (
        'Fuente contractual existente: source_type y source_id, versión vigente del espacio '
        'y request_id estable de hasta 100 caracteres.'
    ),
    BillingContextAssignmentSerializer: (
        'Asociación explícita de la cuenta a contract o hosting, con versión vigente '
        'y motivo de 1 a 2000 caracteres; los vínculos opcionales admiten null.'
    ),
    HostingReconciliationSerializer: (
        'Identidad de la suscripción y registros de hosting que se asociarán, con versión vigente '
        'y motivo de 1 a 2000 caracteres; los identificadores opcionales admiten null.'
    ),
    HostingEvidenceSerializer: (
        'Grupo de evidencias existentes: versión, motivo de 1 a 2000 caracteres y etiqueta '
        'de 1 a 200; las listas de IDs son vacías por defecto y group_id admite null.'
    ),
}


def _validate(arguments, schema, serializer_class=None):
    unknown = set(arguments) - set(schema['properties'])
    missing = set(schema['required']) - set(arguments)
    if unknown or missing:
        raise ToolError('Argumentos desconocidos o incompletos.', details={'unknown': sorted(unknown), 'missing': sorted(missing)})
    for key in ('project_id', 'account_id'):
        if key in arguments and (isinstance(arguments[key], bool) or not isinstance(arguments[key], int) or arguments[key] < 1):
            raise ToolError(f'{key} debe ser un identificador positivo.')
    if serializer_class:
        payload = arguments.get('payload')
        if not isinstance(payload, dict):
            raise ToolError('payload debe ser un objeto JSON.')
        serializer = serializer_class(data=payload)
        unknown_payload = set(payload) - set(serializer.fields)
        if unknown_payload:
            raise ToolError('Campos de contexto desconocidos.', details={'fields': sorted(unknown_payload)})
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data
    return None


def _account(arguments, actor):
    doc = account_for_actor(arguments['account_id'], actor)
    if doc.project_id != arguments['project_id']:
        raise ToolError('La cuenta no pertenece al proyecto indicado.')
    return doc


def _read_account(arguments, actor, payload):
    return context_data(getattr(_account(arguments, actor), 'billing_context', None))


def _associate(arguments, actor, payload):
    _account(arguments, actor)
    return context_data(associate_account(arguments['account_id'], actor, payload))


def _tool(name, description, operation, *, serializer=None, fields=None, required=(), sensitive=False,
          payload_required=None, prepare_operation=None, version_getter=None, impact_builder=None):
    properties = {'project_id': {**ID, 'description': 'Identificador entero positivo del proyecto autorizado.'}}
    if required:
        properties['account_id'] = {**ID, 'description': 'Identificador entero positivo de la cuenta de cobro dentro del proyecto.'}
    if serializer:
        properties['payload'] = {'type': 'object', 'additionalProperties': False, 'properties': fields,
                                 'description': PAYLOAD_DESCRIPTIONS[serializer],
                                 'required': list(payload_required) if payload_required is not None else ['expected_version', 'reason'] + (['billing_nature'] if serializer == BillingContextAssignmentSerializer else ['label'] if serializer == HostingEvidenceSerializer else [])}
    schema = {'type': 'object', 'additionalProperties': False, 'properties': properties,
              'required': ['project_id', *required] + (['payload'] if serializer else [])}

    def execute(arguments):
        try:
            payload = _validate(arguments, schema, serializer)
            actor = mcp_actor()
            require_billing_admin(actor)
            return operation(arguments, actor, payload)
        except APIException as exc:
            message, code, details = normalize_error(exc.detail, exc.status_code)
            raise ToolError(message, code=code, details=details) from exc

    tool = {'name': name, 'description': description, 'risk': 'sensitive' if sensitive else 'read',
            'input_schema': schema, 'handler': execute}
    if sensitive:
        def prepare(arguments):
            try:
                payload = _validate(arguments, schema, serializer)
                actor = mcp_actor()
                require_billing_admin(actor)
                if prepare_operation:
                    prepare_operation(arguments, actor, payload)
                else:
                    hosting_inventory(arguments['project_id'], actor)
                if required:
                    _account(arguments, actor)
                return deepcopy(arguments)
            except APIException as exc:
                message, code, details = normalize_error(exc.detail, exc.status_code)
                raise ToolError(message, code=code, details=details) from exc

        def etag(arguments):
            actor = mcp_actor()
            if version_getter:
                return {f'project:{arguments["project_id"]}:delivery': str(version_getter(arguments, actor))}
            if required:
                version = _read_account(arguments, actor, None)['version']
                return {f'account:{arguments["account_id"]}:context': str(version)}
            inventory = hosting_inventory(arguments['project_id'], actor)
            return {f'project:{arguments["project_id"]}:hosting': str(inventory['version'])}

        tool.update(requires_confirmation=True, prepare_arguments=prepare, etag_resolver=etag,
                    impact_builder=impact_builder or (lambda arguments: {'summary': description, 'operation': name,
                                                       'project_id': arguments['project_id'], 'financial_effect': 'none'}))
    return tool


def _prepare_contract(arguments, actor, payload):
    options = project_billing_options(arguments['project_id'], actor)
    if not any(row['source_type'] == payload['source_type'] and row['id'] == payload['source_id']
               for row in options['contract_sources']):
        raise ToolError('El contrato seleccionado no pertenece a este proyecto y cliente.', code='NOT_FOUND')
    if options['delivery_version'] != payload['expected_version']:
        raise ToolError('El proyecto cambió. Consulta nuevamente sus opciones.', code='STALE_VERSION')


def _contract_impact(arguments):
    options = project_billing_options(arguments['project_id'], mcp_actor())
    payload = arguments['payload']
    source = next((row for row in options['contract_sources']
                   if row['source_type'] == payload['source_type'] and row['id'] == payload['source_id']), None)
    if source is None or options['delivery_version'] != payload['expected_version']:
        raise ToolError('El contrato o el proyecto cambió. Consulta nuevamente sus opciones.', code='STALE_VERSION')
    return {'summary': 'Registrar el contrato existente para la facturación del proyecto.',
            'project_id': arguments['project_id'], 'project_name': options['project_name'],
            'source': source, 'financial_effect': 'none'}


PLATFORM_BILLING_TOOLS = [
    _tool('get_project_billing_options', 'Lista contratos/otrosí y el hosting único del proyecto sin conceder acceso documental.',
          lambda args, actor, data: project_billing_options(args['project_id'], actor)),
    _tool('link_project_billing_contract', 'Registra un contrato existente del proyecto para habilitar sus cuentas de cobro; no emite documentos ni modifica importes.',
          lambda args, actor, data: link_billing_contract(args['project_id'], actor, data),
          serializer=BillingContractLinkSerializer,
          fields={'source_type': {'type': 'string', 'enum': ['document', 'proposal_document']},
                  'source_id': ID, 'expected_version': {'type': 'integer', 'minimum': 0},
                  'request_id': {'type': 'string', 'minLength': 1, 'maxLength': 100}},
          payload_required=('source_type', 'source_id', 'expected_version', 'request_id'),
          sensitive=True, prepare_operation=_prepare_contract,
          impact_builder=_contract_impact,
          version_getter=lambda args, actor: project_billing_options(args['project_id'], actor)['delivery_version']),
    _tool('get_project_hosting', 'Consulta un hosting por proyecto y sus pagos, cuentas y evidencias sin sumar orígenes no conciliados.',
          lambda args, actor, data: project_hosting_read(args['project_id'], actor)),
    _tool('get_project_hosting_inventory', 'Inventaría orígenes históricos, contradicciones, cuentas pendientes y decisiones auditadas.',
          lambda args, actor, data: hosting_inventory(args['project_id'], actor)),
    _tool('get_collection_account_context', 'Consulta el contexto explícito de una cuenta o su asociación pendiente.',
          _read_account, required=('account_id',)),
    _tool('associate_collection_account_context', 'Asocia o corrige contrato/otrosí O hosting sin cambiar PDF, importe ni estado financiero.',
          _associate, required=('account_id',), serializer=BillingContextAssignmentSerializer,
          fields=ASSOCIATION, sensitive=True),
    _tool('preview_project_hosting_reconciliation', 'Valida la conciliación de orígenes sin guardar asociaciones ni modificar dinero.',
          lambda args, actor, data: reconcile_hosting(args['project_id'], actor, data, preview=True),
          serializer=HostingReconciliationSerializer, fields=IDENTITY),
    _tool('reconcile_project_hosting', 'Asocia explícitamente suscripción y registros al único hosting; conserva todos sus cobros y ciclos.',
          lambda args, actor, data: reconcile_hosting(args['project_id'], actor, data),
          serializer=HostingReconciliationSerializer, fields=IDENTITY, sensitive=True),
    _tool('preview_hosting_evidence', 'Valida equivalencia de evidencias financieras existentes sin registrar pagos.',
          lambda args, actor, data: reconcile_evidence(args['project_id'], actor, data, preview=True),
          serializer=HostingEvidenceSerializer, fields=EVIDENCE),
    _tool('reconcile_hosting_evidence', 'Agrupa o corrige evidencias existentes por decisión explícita; audita la membresía anterior y conserva la historia financiera.',
          lambda args, actor, data: reconcile_evidence(args['project_id'], actor, data),
          serializer=HostingEvidenceSerializer, fields=EVIDENCE, sensitive=True),
]
