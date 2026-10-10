"""Administrative ticket actions use the same validators and lifecycle as Platform."""
from copy import deepcopy

from accounts.services import issue_contract_reply as replies
from accounts.services import issue_reports as issues
from accounts.services.delivery_access import is_admin, project_for_actor
from accounts.services.delivery_authoring import CITATION_SCHEMA, reply_schema
from accounts.services.issue_evidence import attachment_for_actor
from accounts.views_issue_reports import context_options, ticket_response
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from rest_framework.exceptions import APIException

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.errors import normalize_error
from content.mcp.protocol import ToolError
from content.mcp.public_delivery_confirmation import (
    ISSUE_PUBLIC_TOOLS,
    configure_public_tool,
)
from content.mcp.upload_tools import consume_upload, store_artifact

ID = {'type': 'integer', 'minimum': 1}
VERSION = {'type': 'integer', 'minimum': 0}
TEXT = {'type': 'string'}
BOOL = {'type': 'boolean'}
KIND = {'type': 'string', 'enum': ['bug', 'change']}
RETRY = {'type': 'string', 'format': 'uuid', 'description': 'UUID estable para reintentar sin duplicar.'}
DOCUMENTS = {'type': 'array', 'items': ID, 'maxItems': 10, 'uniqueItems': True}
COMMON = {'expected_version': VERSION, 'request_id': RETRY}
SOURCE = {'source_requirement_id': ID, 'source_publication_id': ID, 'source_requirement_version': VERSION}
MESSAGES = {**COMMON, 'document_ids': DOCUMENTS, 'is_internal': BOOL}
CLASSIFICATIONS = reply_schema()['properties']['classifications']
CONTRACT_REPLY = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'context_id': RETRY, 'expected_version': VERSION, 'expected_ticket_version': VERSION,
        'human_reviewed': BOOL, 'classifications': CLASSIFICATIONS,
        'source_references': {'type': 'array', 'maxItems': 100, 'items': CITATION_SCHEMA},
    },
    'required': ['context_id', 'expected_version', 'expected_ticket_version', 'human_reviewed',
                 'classifications', 'source_references'],
}
ROOT_DESCRIPTIONS = {
    'project_id': 'Identificador entero positivo del proyecto autorizado.',
    'kind': 'Tipo de ticket: bug para un fallo o change para una solicitud de cambio.',
    'ticket_id': 'Identificador entero positivo del ticket dentro del proyecto y tipo indicados.',
    'status': 'Estado por el que filtrar; si se omite, incluye todos los estados.',
    'include_archived': 'Incluye tickets archivados; false por defecto.',
    'contract_id': 'Identificador entero positivo del contrato para consultar opciones del contexto.',
    'source_requirement_id': 'Identificador entero positivo de la guía publicada que origina el ticket.',
    'source_publication_id': 'Identificador entero positivo de la publicación histórica de la guía de origen.',
    'expected_version': 'Versión vigente del ticket, entero desde 0; se revalida al confirmar.',
    'attachment_id': 'Identificador entero positivo del adjunto privado del ticket.',
    'context_id': 'UUID del contexto de respuesta capturado para este ticket.',
    'source_key': 'Clave de una fuente incluida en el contexto de respuesta capturado.',
    'items': 'Lista de hasta 500 evaluaciones; cada objeto requiere id y expected_version. Puede estar vacía.',
}


def _actor():
    actor = mcp_actor()
    if not is_admin(actor):
        raise ToolError('Solo un administrador puede gestionar tickets.', code='FORBIDDEN')
    return actor


def _data(ticket, kind, actor, *, detail=True):
    return ticket_response(ticket, kind, issues.serializer_context(None, actor)['request'], detail=detail).data


def _list(arguments, actor):
    project_for_actor(arguments['project_id'], actor)
    from accounts.views import _bug_report_list_queryset, _change_request_list_queryset
    kind = arguments['kind']
    qs = issues.MODELS[kind].objects.filter(project_id=arguments['project_id'])
    if not arguments.get('include_archived'):
        qs = qs.filter(is_archived=False)
    if arguments.get('status'):
        qs = qs.filter(status=arguments['status'])
    build = _bug_report_list_queryset if kind == 'bug' else _change_request_list_queryset
    return {'tickets': [_data(ticket, kind, actor, detail=False) for ticket in build(qs, actor)]}


def _get(arguments, actor):
    return _data(issues.get_ticket(arguments['project_id'], actor, arguments['kind'], arguments['ticket_id'],
                                  include_archived=True), arguments['kind'], actor)


def _payload(arguments):
    return deepcopy(arguments['payload'])


def _create(arguments, actor, kind):
    with transaction.atomic():
        payload = _payload(arguments)
        asset_id = payload.pop('screenshot_asset_id', None)
        if asset_id:
            upload = consume_upload(asset_id, allowed_content_types={'image/png', 'image/jpeg', 'image/webp'})
            if upload.received_size > 5 * 1024 * 1024:
                raise ToolError('La captura no puede superar 5 MB.')
            with upload.file.open('rb') as source:
                payload['screenshot'] = SimpleUploadedFile(upload.filename, source.read(), content_type=upload.content_type)
        return _data(issues.create_ticket(arguments['project_id'], actor, kind, payload), kind, actor)


def _evaluate(arguments, actor):
    kind = arguments['kind']
    return _data(issues.evaluate_ticket(arguments['project_id'], actor, kind, arguments['ticket_id'],
                                       _payload(arguments)), kind, actor)


def _comment(arguments, actor):
    from accounts.serializers import (
        BugCommentSerializer,
        ChangeRequestCommentSerializer,
    )
    comment = issues.comment_ticket(arguments['project_id'], actor, arguments['kind'], arguments['ticket_id'],
                                     _payload(arguments))
    serializer = BugCommentSerializer if arguments['kind'] == 'bug' else ChangeRequestCommentSerializer
    return serializer(comment).data


def _archive(arguments, actor):
    issues.archive_ticket(arguments['project_id'], actor, arguments['kind'], arguments['ticket_id'],
                          {key: arguments[key] for key in COMMON if key in arguments})
    return {'archived': True, 'ticket_id': arguments['ticket_id']}


def _convert(arguments, actor):
    return _data(issues.convert_request(arguments['project_id'], actor, arguments['ticket_id'], _payload(arguments)),
                 'change', actor)


def _download(arguments, actor):
    item = attachment_for_actor(arguments['attachment_id'], actor)
    message = item.response or item.bug_comment or item.change_comment
    ticket = (message.bug_report or message.change_request) if item.response_id else (
        message.bug_report if item.bug_comment_id else message.change_request
    )
    if ticket.project_id != arguments['project_id']:
        raise ToolError('Adjunto no encontrado en el proyecto.', code='NOT_FOUND')
    context = current_mcp_context()
    if not context or not context.credential:
        raise ToolError('La descarga requiere una credencial MCP.', code='FORBIDDEN')
    with item.file.open('rb') as source:
        body = source.read()
    return store_artifact(connector=context.connector, credential=context.credential,
                          filename=f'issue-evidence-{item.pk}.pdf', content_type='application/pdf',
                          content=body, request=context.request)


def _reply_source(arguments, actor):
    context = current_mcp_context()
    if not context or not context.credential:
        raise ToolError('La descarga requiere una credencial MCP.', code='FORBIDDEN')
    body, filename, content_type = replies.reply_source_file(
        arguments['project_id'], actor, arguments['kind'], arguments['ticket_id'],
        arguments['context_id'], arguments['source_key'],
    )
    return store_artifact(connector=context.connector, credential=context.credential,
                          filename=filename, content_type=content_type, content=body, request=context.request)


def _api_errors(operation):
    try:
        return operation()
    except APIException as exc:
        message, code, details = normalize_error(exc.detail, exc.status_code)
        raise ToolError(message, code=code, details=details) from exc


def _etag(arguments):
    def resolve():
        kind = arguments.get('kind', 'change')
        ticket = issues.get_ticket(arguments['project_id'], _actor(), kind, arguments['ticket_id'],
                                   include_archived=True)
        return {f'issue:{kind}:{ticket.pk}': str(ticket.version)}
    return _api_errors(resolve)


def _tool(name, description, handler, properties, required=(), *, risk='read'):
    described = {key: {**field, 'description': ROOT_DESCRIPTIONS.get(key, field.get('description'))}
                 for key, field in {'project_id': ID, **properties}.items()}
    schema = {'type': 'object', 'additionalProperties': False,
              'properties': described, 'required': ['project_id', *required]}

    def execute(arguments):
        def call():
            _validate(arguments, schema)
            return handler(arguments, _actor())
        return _api_errors(call)

    result = {'name': name, 'description': description, 'risk': risk,
              'input_schema': schema, 'handler': execute}
    if risk == 'sensitive':
        def prepare(arguments):
            def validate():
                _validate(arguments, schema)
                project_for_actor(arguments['project_id'], _actor())
                return deepcopy(arguments)
            return _api_errors(validate)
        result.update(requires_confirmation=True, prepare_arguments=prepare,
                      etag_resolver=_etag, impact_builder=lambda arguments: {
                          'summary': description, 'project_id': arguments['project_id'],
                          'ticket_id': arguments['ticket_id'],
                      })
    return result


def _validate(value, schema, path='arguments'):
    """Validate the transport envelope; domain serializers still own business rules."""
    kinds = schema.get('type', [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    actual = ('null' if value is None else 'boolean' if isinstance(value, bool) else
              'integer' if isinstance(value, int) else 'number' if isinstance(value, float) else
              'string' if isinstance(value, str) else 'array' if isinstance(value, list) else
              'object' if isinstance(value, dict) else '')
    if kinds and actual not in kinds and not (actual == 'integer' and 'number' in kinds):
        raise ToolError(f'{path}: tipo inválido.')
    if 'enum' in schema and value not in schema['enum']:
        raise ToolError(f'{path}: opción inválida.')
    if actual in ('integer', 'number') and value < schema.get('minimum', value):
        raise ToolError(f'{path}: valor inválido.')
    if actual == 'object':
        fields = schema.get('properties', {})
        if set(schema.get('required', [])) - set(value):
            raise ToolError(f'{path}: faltan campos obligatorios.')
        if not schema.get('additionalProperties', True) and set(value) - set(fields):
            raise ToolError(f'{path}: campos desconocidos.')
        for key, item in value.items():
            if key in fields:
                _validate(item, fields[key], f'{path}.{key}')
    if actual == 'array':
        if len(value) > schema.get('maxItems', len(value)):
            raise ToolError(f'{path}: demasiados elementos.')
        for item in value:
            _validate(item, schema.get('items', {}), path)


def _payload_schema(properties, required=(), *, description='Datos del ticket para esta operación; sólo admite los campos declarados.'):
    return {'type': 'object', 'additionalProperties': False, 'properties': properties,
            'required': list(required), 'description': description}


ISSUE_TOOLS = [
    _tool('list_issue_reports', 'Lista bugs o solicitudes del proyecto, con contexto histórico y estados.',
          _list, {'kind': KIND, 'status': TEXT, 'include_archived': BOOL}, ('kind',)),
    _tool('get_issue_report', 'Lee detalle, respuestas, documentos e historia del ticket; no modifica guías.',
          _get, {'kind': KIND, 'ticket_id': ID}, ('kind', 'ticket_id')),
    _tool('get_issue_context_options', 'Obtiene guías publicadas, contratos y documentos del contexto para un ticket.',
          lambda args, actor: context_options(args['project_id'], actor, **{key: value for key, value in args.items() if key != 'project_id'}),
          {'kind': KIND, 'ticket_id': ID, 'contract_id': ID,
           'source_requirement_id': ID, 'source_publication_id': ID}),
    _tool('create_bug_report', 'Reporta un bug general sin guía obligatoria, o captura una publicación concreta.',
          lambda args, actor: _create(args, actor, 'bug'), {'payload': _payload_schema({
              **SOURCE, 'request_id': RETRY,
              'screenshot_asset_id': {**RETRY, 'description': 'UUID de una captura propia completada, PNG, JPEG o WebP, de hasta 5 MB.'},
              'title': TEXT, 'description': TEXT,
              'severity': {'type': 'string', 'enum': ['critical', 'high', 'medium', 'low']},
              'steps_to_reproduce': {'type': 'array', 'items': TEXT}, 'expected_behavior': TEXT,
              'actual_behavior': TEXT, 'environment': {'type': 'string', 'enum': ['production', 'staging', 'dev']},
              'device_browser': TEXT, 'is_recurring': BOOL,
          }, ('title',), description='Datos del bug: título obligatorio y origen opcional; severity es medium y environment es production por defecto.')}, ('payload',), risk='write'),
    _tool('create_change_request', 'Crea una solicitud de ampliación desde una guía publicada, sin aprobarla.',
          lambda args, actor: _create(args, actor, 'change'), {'payload': _payload_schema({
              **SOURCE, 'request_id': RETRY,
              'screenshot_asset_id': {**RETRY, 'description': 'UUID de una captura propia completada, PNG, JPEG o WebP, de hasta 5 MB.'},
              'title': TEXT, 'description': TEXT, 'module_or_screen': TEXT,
              'suggested_priority': {'type': 'string', 'enum': ['critical', 'high', 'medium', 'low']}, 'is_urgent': BOOL,
          }, ('title', 'source_requirement_id'), description='Datos de la solicitud: título y guía publicada obligatorios; suggested_priority es medium e is_urgent es false por defecto.')}, ('payload',), risk='write'),
    _tool('evaluate_issue_report', 'Cambia estado o responde con documentos. Resuelto por equipo no es conformidad del cliente. contract_reply exige contexto, citas verificadas y revisión humana explícita; sin él el alcance sigue indeterminado.',
          _evaluate, {'kind': KIND, 'ticket_id': ID, 'payload': _payload_schema({
              **MESSAGES, 'status': TEXT, 'admin_response': TEXT, 'contract_id': {'type': ['integer', 'null'], 'minimum': 1},
              'contract_reply': CONTRACT_REPLY,
              'linked_bug_id': {'type': ['integer', 'null'], 'minimum': 1},
              'estimated_cost': {'type': ['number', 'string', 'null']}, 'estimated_time': TEXT,
          }, ('expected_version',), description='Evaluación del ticket con versión vigente y estado o respuesta; document_ids admite hasta 10 IDs únicos e is_internal es false por defecto.')}, ('kind', 'ticket_id', 'payload'), risk='write'),
    _tool('comment_issue_report', 'Comenta o reabre un bug resuelto con «sigue fallando», preservando historia.',
          _comment, {'kind': KIND, 'ticket_id': ID, 'payload': _payload_schema({
              **MESSAGES, 'content': TEXT, 'reopen': BOOL,
          }, ('content', 'expected_version'), description='Comentario y versión vigente del ticket; is_internal y reopen son false por defecto, con hasta 10 documentos únicos.')}, ('kind', 'ticket_id', 'payload'), risk='write'),
    _tool('bulk_evaluate_issue_reports', 'Evalúa hasta 500 tickets, con resultado y error independiente por ticket.',
          lambda args, actor: issues.bulk_evaluate(args['project_id'], actor, args['kind'], args['items']),
          {'kind': KIND, 'items': {'type': 'array', 'maxItems': 500, 'items': _payload_schema({
              **MESSAGES, 'id': ID, 'status': TEXT, 'admin_response': TEXT, 'contract_id': {'type': ['integer', 'null'], 'minimum': 1},
              'contract_reply': CONTRACT_REPLY,
              'linked_bug_id': {'type': ['integer', 'null'], 'minimum': 1},
              'estimated_cost': {'type': ['number', 'string', 'null']}, 'estimated_time': TEXT,
          }, ('id', 'expected_version'))}}, ('kind', 'items'), risk='write'),
    _tool('archive_issue_report', 'Archiva el ticket sin eliminar su historia ni alterar aprobaciones.',
          _archive, {'kind': KIND, 'ticket_id': ID, **COMMON}, ('kind', 'ticket_id', 'expected_version'), risk='sensitive'),
    _tool('convert_change_request', 'Convierte una solicitud aprobada en una guía nueva y pendiente, dentro del contrato aplicable y una etapa editable.',
          _convert, {'ticket_id': ID, 'payload': _payload_schema({
              'stage_id': ID, 'expected_version': VERSION, 'issue_version': VERSION, 'request_id': RETRY,
          }, ('stage_id', 'expected_version', 'issue_version'), description='Etapa de destino y versiones vigentes del espacio y de la solicitud; request_id es un UUID opcional de reintento.')}, ('ticket_id', 'payload'), risk='sensitive'),
    _tool('download_issue_attachment', 'Descarga los bytes históricos privados de un documento del ticket.',
          _download, {'attachment_id': ID}, ('attachment_id',)),
    _tool('get_issue_reply_options', 'Obtiene fuentes seleccionables y versiones para preparar una respuesta contractual del ticket; no elige contrato.',
          lambda args, actor: replies.reply_options(args['project_id'], actor, args['kind'], args['ticket_id']),
          {'kind': KIND, 'ticket_id': ID}, ('kind', 'ticket_id')),
    _tool('prepare_issue_reply', 'Captura origen y conversación públicos reales del ticket con fuentes del motor compartido. Contrato nulo conserva alcance indeterminado. No llama IA ni publica.',
          lambda args, actor: replies.prepare_reply(args['project_id'], actor, args['kind'], args['ticket_id'], _payload(args)),
          {'kind': KIND, 'ticket_id': ID, 'payload': _payload_schema({
              'expected_version': VERSION, 'expected_ticket_version': VERSION, 'request_id': RETRY,
              'contract_id': {'type': ['integer', 'null'], 'minimum': 1},
              'amendment_ids': {'type': 'array', 'items': ID, 'maxItems': 30},
              'sources': {'type': 'array', 'maxItems': 30, 'items': _payload_schema({
                  'document_id': ID, 'proposal_document_id': ID,
                  'role': {'type': 'string', 'enum': ['contractual_annex', 'reference']},
                  'applicability_note': TEXT,
              }, ('role', 'applicability_note'))},
              'missing_sources': {'type': 'array', 'items': TEXT, 'maxItems': 30},
              'uncertainties': {'type': 'array', 'items': TEXT, 'maxItems': 30}, 'instructions': TEXT,
          }, ('expected_version', 'expected_ticket_version', 'request_id'),
              description='Selección de contrato y fuentes para responder al ticket, con versiones vigentes y UUID de reintento; hasta 30 elementos por lista.')},
          ('kind', 'ticket_id', 'payload'), risk='write'),
    _tool('get_issue_reply_context', 'Lee el contexto privado de autoría del ticket para revisión y auditoría administrativas.',
          lambda args, actor: replies.get_reply_context(args['project_id'], actor, args['kind'], args['ticket_id'], args['context_id']),
          {'kind': KIND, 'ticket_id': ID, 'context_id': RETRY}, ('kind', 'ticket_id', 'context_id')),
    _tool('preview_issue_reply', 'Verifica JSON v2, citas, dueño, destino y versiones sin cambiar ticket, guías o respuestas.',
          lambda args, actor: replies.preview_reply(args['project_id'], actor, args['kind'], args['ticket_id'], _payload(args)),
          {'kind': KIND, 'ticket_id': ID, 'payload': _payload_schema({
              'expected_version': VERSION, 'expected_ticket_version': VERSION, 'payload': reply_schema(),
          }, ('expected_version', 'expected_ticket_version', 'payload'),
              description='Versiones vigentes del espacio y del ticket, junto al JSON v2 de respuesta con contexto y citas verificables.')}, ('kind', 'ticket_id', 'payload')),
    _tool('download_issue_reply_source', 'Descarga una fuente privada capturada del ticket como artefacto exclusivo de la credencial MCP.',
          _reply_source, {'kind': KIND, 'ticket_id': ID, 'context_id': RETRY, 'source_key': TEXT},
          ('kind', 'ticket_id', 'context_id', 'source_key')),
]

for _public_tool in ISSUE_TOOLS:
    if _public_tool['name'] in ISSUE_PUBLIC_TOOLS:
        configure_public_tool(_public_tool, _actor)
