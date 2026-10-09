"""Private, credential-owned proposal packages with confirmed delivery."""
import hashlib
import logging
from functools import wraps
from uuid import UUID

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import (
    check_known_fields,
    object_schema,
    writable_schema,
)
from content.mcp.protocol import ToolError
from content.mcp.upload_tools import store_artifact
from content.models import BusinessProposal, ProposalFormalization
from content.serializers.formalization import FormalizationPrepareSerializer
from content.services import proposal_formalization_service as service
from content.services.formalization_content import FormalizationError

logger = logging.getLogger(__name__)

ID = {'type': 'integer', 'minimum': 1}
PREPARATION_ID = {'type': 'string', 'format': 'uuid'}
PREPARE_SCHEMA = writable_schema(FormalizationPrepareSerializer)


def _credential():
    context = current_mcp_context()
    if context is None or context.credential is None or not context.credential.is_usable:
        raise ToolError('La operación requiere una credencial MCP activa.', code='FORBIDDEN')
    return context.credential


def _preparation(arguments):
    credential = _credential()
    try:
        preparation = (
            ProposalFormalization.objects.select_related('proposal__client')
            .prefetch_related('files').get(
                pk=UUID(str(arguments.get('preparation_id'))),
                proposal_id=int(arguments.get('proposal_id')),
                mcp_credential=credential,
            )
        )
    except (ProposalFormalization.DoesNotExist, ValueError, TypeError) as exc:
        raise ToolError('No existe esa preparación para esta credencial.', code='NOT_FOUND') from exc
    if preparation.expires_at <= timezone.now():
        raise ToolError('La preparación venció. Prepara nuevamente el correo.', code='EXPIRED_PREPARATION')
    return preparation


def _payload(preparation):
    return {
        'id': str(preparation.pk), 'proposal_id': preparation.proposal_id,
        'status': preparation.status, 'error': preparation.error,
        'sent_at': preparation.sent_at.isoformat() if preparation.sent_at else None,
        'payload': {key: value for key, value in preparation.payload.items() if key in PREPARE_SCHEMA['properties']},
        'expires_at': preparation.expires_at.isoformat(),
        'subject': preparation.payload['subject'],
        'recipient_emails': preparation.payload['recipient_emails'],
        'cc_emails': preparation.payload['cc_emails'],
        'html_preview': preparation.html_body, 'text_preview': preparation.text_body,
        'files': [{
            'file_id': item.pk, 'key': item.key, 'filename': item.filename,
            'description': item.description, 'mime_type': item.mime_type,
            'size': item.size, 'sha256': item.sha256,
        } for item in preparation.files.all()],
    }


def _domain_errors(handler):
    @wraps(handler)
    def wrapped(arguments):
        try:
            return handler(arguments)
        except FormalizationError as exc:
            raise ToolError(str(exc), code=exc.code.upper()) from exc
        except ValidationError as exc:
            raise ToolError('Datos de formalización inválidos.', details=exc.detail) from exc
    return wrapped


@_domain_errors
def prepare(arguments):
    credential = _credential()
    try:
        proposal = service.load_proposal(int(arguments.get('proposal_id')))
    except (BusinessProposal.DoesNotExist, ValueError, TypeError) as exc:
        raise ToolError('No existe esa propuesta.', code='NOT_FOUND') from exc
    payload = arguments.get('data', {})
    if 'data' in arguments:
        logger.info('[MCP] deprecated_envelope tool=%s keys=%s', 'prepare_proposal_formalization', sorted({'data'}))
    check_known_fields(payload, PREPARE_SCHEMA)
    flat = {key: value for key, value in arguments.items() if key not in {'proposal_id', 'data'}}
    check_known_fields(flat, PREPARE_SCHEMA)
    if set(payload) & set(flat):
        raise ToolError('No repitas campos en data y en los argumentos.')
    serializer = FormalizationPrepareSerializer(data={**payload, **flat})
    serializer.is_valid(raise_exception=True)
    preparation = service.prepare(
        proposal, mcp_actor(), serializer.validated_data, mcp_credential=credential,
    )
    return _payload(preparation)


def get_preparation(arguments):
    return _payload(_preparation(arguments))


@_domain_errors
def download_file(arguments):
    preparation = _preparation(arguments)
    try:
        file_id = int(arguments.get('file_id'))
    except (ValueError, TypeError) as exc:
        raise ToolError('file_id debe identificar un adjunto.', code='VALIDATION_ERROR') from exc
    item = next((item for item in preparation.files.all() if item.pk == file_id), None)
    if item is None:
        raise ToolError('El archivo no pertenece a esta preparación.', code='NOT_FOUND')
    try:
        with item.file.open('rb') as source:
            content = source.read(service.MAX_ATTACHMENT_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise ToolError('El adjunto ya no está disponible.', code='ATTACHMENT_CHANGED') from exc
    if hashlib.sha256(content).hexdigest() != item.sha256:
        raise ToolError('El adjunto cambió. Prepara nuevamente el correo.', code='ATTACHMENT_CHANGED')
    context = current_mcp_context()
    return store_artifact(
        connector=context.connector, credential=context.credential,
        filename=item.filename, content_type=item.mime_type,
        content=content, request=context.request,
    )


@_domain_errors
def send(arguments):
    preparation = _preparation(arguments)
    service.send_preparation(preparation)
    # Failed/unknown delivery is an outcome. The confirmation was durably
    # consumed before entering this handler, outside its transaction.
    return _payload(preparation)


@_domain_errors
def send_impact(arguments):
    preparation = _preparation(arguments)
    service.check_current(preparation)
    if preparation.status != ProposalFormalization.Status.PREPARED:
        raise ToolError('Esta preparación ya fue consumida.', code='PREPARATION_CONSUMED')
    return {'summary': 'Enviar exactamente el paquete preparado.', **_payload(preparation)}


def _tool(name, description, handler, *, prepare_tool=False, file_tool=False, sensitive=False):
    properties = {'proposal_id': ID}
    required = ['proposal_id']
    if prepare_tool:
        properties.update(PREPARE_SCHEMA['properties'])
        required.extend(PREPARE_SCHEMA.get('required', []))
    else:
        properties['preparation_id'] = PREPARATION_ID
        required.append('preparation_id')
    if file_tool:
        properties['file_id'] = ID
        required.append('file_id')
    schema = object_schema(properties, required)

    def checked(arguments):
        check_known_fields(arguments, tool.get('accepted_arguments_schema') or tool['input_schema'])
        return arguments

    tool = {
        'name': name, 'description': description,
        'risk': 'sensitive' if sensitive else 'write' if prepare_tool else 'read',
        'requires_confirmation': sensitive,
        'input_schema': schema, 'handler': lambda arguments: handler(checked(arguments)),
    }
    if prepare_tool:
        tool['accepted_arguments_schema'] = object_schema(
            {**properties, 'data': PREPARE_SCHEMA}, ('proposal_id',),
        )
    if sensitive:
        tool['durable_execution'] = True
        tool['prepare_arguments'] = checked
        tool['impact_builder'] = send_impact
    return tool


PROPOSAL_FORMALIZATION_TOOLS = [
    _op('get_proposal_formalization_options', 'Consulta los documentos disponibles y el correo predeterminado para formalizar la propuesta.', 'formalization-options', path=('proposal_id',)),
    _op('render_proposal_formalization_pdf', 'Genera el PDF contractual, comercial o técnico disponible para formalizar la propuesta.', 'formalization-pdf', path=('proposal_id', 'kind')),
    _op('read_proposal_formalization_markdown', 'Consulta el Markdown de los anexos comercial o técnico de la propuesta.', 'formalization-markdown', path=('proposal_id', 'kind')),
    _tool('prepare_proposal_formalization', 'Prepara un paquete privado para esta credencial durante 24 horas; devuelve correo y archivos para revisar sin enviar.', prepare, prepare_tool=True),
    _tool('get_proposal_formalization', 'Consulta el correo y los adjuntos exactos de una preparación propia aún vigente.', get_preparation),
    _tool('download_proposal_formalization_file', 'Descarga un adjunto exacto del paquete preparado como archivo temporal de esta credencial.', download_file, file_tool=True),
    _tool('send_proposal_formalization', 'Previsualiza el envío del paquete revisado; confirm_action envía una sola vez y rechaza cambios posteriores.', send, sensitive=True),
]

for _tool_definition in PROPOSAL_FORMALIZATION_TOOLS:
    if _tool_definition['name'] == 'render_proposal_formalization_pdf':
        _tool_definition['input_schema']['properties']['kind']['enum'] = list(service.DOCUMENTS)
    elif _tool_definition['name'] == 'read_proposal_formalization_markdown':
        _tool_definition['input_schema']['properties']['kind']['enum'] = ['commercial', 'technical']
