"""MCP tools for administering client communications.

The handlers deliberately reuse the panel serializers and service layer so a
conversation cannot bypass thread, message, reply, document, archive, or audit
guardrails. Message actions only update the registry; none delivers email or
WhatsApp itself.
"""
import json

from django.core.paginator import Paginator

from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError
from content.models import CommunicationMessage
from content.serializers.communication import (
    CommunicationDateCorrectionWriteSerializer,
    CommunicationDraftUpdateSerializer,
    CommunicationMarkSentSerializer,
    CommunicationMessageCreateSerializer,
    CommunicationMessageSerializer,
    CommunicationThreadDetailSerializer,
    CommunicationThreadListSerializer,
    CommunicationThreadWriteSerializer,
    CommunicationVoidSerializer,
)
from content.services import communication_query_service, communication_service


def _serializer_error(errors):
    return 'Datos inválidos: ' + json.dumps(errors, ensure_ascii=False, default=str)


def _positive_int(value, *, field, default=None, maximum=None):
    if value in (None, ''):
        return default
    if isinstance(value, bool):
        raise ToolError(f'{field} debe ser un número entero.')
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ToolError(f'{field} debe ser un número entero.') from exc
    if parsed < 1:
        raise ToolError(f'{field} debe ser mayor que cero.')
    return min(parsed, maximum) if maximum is not None else parsed


def _reject_unknown_fields(arguments, allowed_fields):
    if not isinstance(arguments, dict):
        raise ToolError('Los argumentos deben ser un objeto JSON.')
    unknown_fields = sorted(set(arguments) - set(allowed_fields))
    if unknown_fields:
        raise ToolError(f'Campos no permitidos: {", ".join(unknown_fields)}.')


def _thread_or_error(thread_id):
    if thread_id in (None, ''):
        raise ToolError('thread_id es obligatorio.')
    thread_id = _positive_int(thread_id, field='thread_id')
    thread = (
        communication_query_service.thread_queryset()
        .filter(pk=thread_id)
        .first()
    )
    if thread is None:
        raise ToolError(f'No existe un hilo con id={thread_id}.')
    return thread


def _message_or_error(message_id):
    if message_id in (None, ''):
        raise ToolError('message_id es obligatorio.')
    message_id = _positive_int(message_id, field='message_id')
    message = (
        CommunicationMessage.objects.select_related('thread')
        .filter(pk=message_id)
        .first()
    )
    if message is None:
        raise ToolError(f'No existe un mensaje con id={message_id}.')
    return message


def _thread_detail(thread_id):
    return CommunicationThreadDetailSerializer(
        communication_query_service.thread_queryset().get(pk=thread_id),
    ).data


def _message_detail(message_id):
    return CommunicationMessageSerializer(
        communication_query_service.message_queryset().get(pk=message_id),
    ).data


def list_threads(arguments):
    """Return the same filtered, paginated thread list exposed by the panel."""
    _reject_unknown_fields(arguments, {
        'client_id', 'project_id', 'status', 'channel', 'direction',
        'message_status', 'reply_status', 'date_from', 'date_to', 'q',
        'order', 'scope', 'page', 'page_size', 'folder',
    })
    query_params = {
        key: value for key, value in arguments.items()
        if key not in {'client_id', 'project_id', 'page', 'page_size'}
    }
    if arguments.get('client_id') not in (None, ''):
        query_params['client'] = arguments['client_id']
    if arguments.get('project_id') not in (None, ''):
        query_params['project'] = arguments['project_id']
    try:
        filters = communication_query_service.parse_filters(query_params)
    except communication_query_service.CommunicationFilterError as exc:
        raise ToolError(_serializer_error(exc.errors)) from exc

    queryset = communication_query_service.apply_filters(
        communication_query_service.thread_queryset(), filters,
    )

    page_number = _positive_int(arguments.get('page'), field='page', default=1)
    page_size = _positive_int(
        arguments.get('page_size'), field='page_size', default=20, maximum=100,
    )
    paginator = Paginator(
        communication_query_service.order_threads(queryset, filters.order), page_size,
    )
    page = paginator.get_page(page_number)
    return {
        'results': CommunicationThreadListSerializer(page.object_list, many=True).data,
        'count': paginator.count,
        'page': page.number,
        'num_pages': paginator.num_pages,
    }


def get_thread(arguments):
    """Open one complete thread, including messages and document references."""
    _reject_unknown_fields(arguments, {'thread_id'})
    thread = _thread_or_error(arguments.get('thread_id'))
    return _thread_detail(thread.pk)


def create_thread(arguments):
    _reject_unknown_fields(arguments, {'client_id', 'project_id', 'title', 'folder_id'})
    data = {
        'client': arguments.get('client_id'),
        'title': arguments.get('title'),
    }
    if 'project_id' in arguments:
        data['project'] = arguments.get('project_id')
    if 'folder_id' in arguments:
        data['folder'] = arguments['folder_id']
    serializer = CommunicationThreadWriteSerializer(data=data)
    if not serializer.is_valid():
        raise ToolError(_serializer_error(serializer.errors))
    try:
        thread = communication_service.create_thread(
            actor=mcp_actor(), **serializer.validated_data,
        )
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _thread_detail(thread.pk)


def update_thread(arguments):
    _reject_unknown_fields(arguments, {'thread_id', 'title', 'project_id', 'folder_id'})
    if 'thread_id' not in arguments:
        raise ToolError('thread_id es obligatorio.')
    supplied_fields = {'title', 'project_id', 'folder_id'}.intersection(arguments)
    if not supplied_fields:
        raise ToolError('Envía al menos un campo para actualizar.')

    thread = _thread_or_error(arguments.get('thread_id'))
    data = {}
    if 'title' in arguments:
        data['title'] = arguments['title']
    if 'project_id' in arguments:
        data['project'] = arguments['project_id']
    if 'folder_id' in arguments:
        data['folder'] = arguments['folder_id']
    serializer = CommunicationThreadWriteSerializer(
        thread,
        data=data,
        partial=True,
    )
    if not serializer.is_valid():
        raise ToolError(_serializer_error(serializer.errors))
    try:
        thread = communication_service.update_thread(
            thread,
            actor=mcp_actor(),
            **serializer.validated_data,
        )
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _thread_detail(thread.pk)


def close_thread(arguments):
    _reject_unknown_fields(arguments, {'thread_id'})
    thread = _thread_or_error(arguments.get('thread_id'))
    try:
        thread = communication_service.close_thread(thread, actor=mcp_actor())
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _thread_detail(thread.pk)


def reopen_thread(arguments):
    _reject_unknown_fields(arguments, {'thread_id'})
    thread = _thread_or_error(arguments.get('thread_id'))
    try:
        thread = communication_service.reopen_thread(thread, actor=mcp_actor())
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _thread_detail(thread.pk)


def archive_thread(arguments):
    _reject_unknown_fields(arguments, {'thread_id'})
    thread = _thread_or_error(arguments.get('thread_id'))
    try:
        thread = communication_service.archive_thread(thread, actor=mcp_actor())
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _thread_detail(thread.pk)


def unarchive_thread(arguments):
    _reject_unknown_fields(arguments, {'thread_id'})
    thread = _thread_or_error(arguments.get('thread_id'))
    try:
        thread = communication_service.unarchive_thread(thread, actor=mcp_actor())
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _thread_detail(thread.pk)


def create_message(arguments):
    _reject_unknown_fields(arguments, {
        'thread_id', 'channel', 'direction', 'subject', 'content',
        'occurred_at', 'reply_to_id', 'document_ids',
    })
    thread = _thread_or_error(arguments.get('thread_id'))
    data = {
        field: arguments[field]
        for field in (
            'channel', 'direction', 'subject', 'content', 'occurred_at',
            'document_ids',
        )
        if field in arguments
    }
    if 'reply_to_id' in arguments:
        data['reply_to'] = arguments.get('reply_to_id')
    serializer = CommunicationMessageCreateSerializer(data=data)
    if not serializer.is_valid():
        raise ToolError(_serializer_error(serializer.errors))
    validated_data = dict(serializer.validated_data)
    document_ids = validated_data.pop('document_ids', [])
    try:
        message = communication_service.create_message(
            thread=thread,
            actor=mcp_actor(),
            document_ids=document_ids,
            **validated_data,
        )
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _message_detail(message.pk)


_UPDATE_MESSAGE_FIELDS = frozenset({
    'subject', 'content', 'document_ids', 'reply_to_id', 'occurred_at',
})


def update_message(arguments):
    _reject_unknown_fields(
        arguments,
        _UPDATE_MESSAGE_FIELDS | {'message_id'},
    )
    if 'message_id' not in arguments:
        raise ToolError('message_id es obligatorio.')
    supplied_fields = _UPDATE_MESSAGE_FIELDS.intersection(arguments)
    if not supplied_fields:
        raise ToolError('Envía al menos un campo para actualizar.')

    message = _message_or_error(arguments.get('message_id'))
    data = {
        field: arguments[field]
        for field in ('subject', 'content', 'occurred_at', 'document_ids')
        if field in arguments
    }
    if 'reply_to_id' in arguments:
        data['reply_to'] = arguments.get('reply_to_id')
    serializer = CommunicationDraftUpdateSerializer(
        message,
        data=data,
        partial=True,
    )
    if not serializer.is_valid():
        raise ToolError(_serializer_error(serializer.errors))
    validated_data = dict(serializer.validated_data)
    document_ids = validated_data.pop('document_ids', None)
    try:
        message = communication_service.update_draft(
            message,
            actor=mcp_actor(),
            document_ids=document_ids,
            **validated_data,
        )
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _message_detail(message.pk)


def delete_draft(arguments):
    _reject_unknown_fields(arguments, {'message_id'})
    message = _message_or_error(arguments.get('message_id'))
    message_id = message.pk
    thread_id = message.thread_id
    try:
        communication_service.delete_draft(message, actor=mcp_actor())
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return {
        'deleted': True,
        'id': message_id,
        'thread_id': thread_id,
    }


def mark_message_sent(arguments):
    _reject_unknown_fields(arguments, {'message_id', 'occurred_at'})
    message = _message_or_error(arguments.get('message_id'))
    data = {
        'occurred_at': arguments['occurred_at'],
    } if 'occurred_at' in arguments else {}
    serializer = CommunicationMarkSentSerializer(data=data)
    if not serializer.is_valid():
        raise ToolError(_serializer_error(serializer.errors))
    try:
        communication_service.mark_sent(
            message,
            actor=mcp_actor(),
            **serializer.validated_data,
        )
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _message_detail(message.pk)


def void_message(arguments):
    _reject_unknown_fields(arguments, {'message_id', 'reason'})
    message = _message_or_error(arguments.get('message_id'))
    serializer = CommunicationVoidSerializer(data={
        'reason': arguments.get('reason'),
    })
    if not serializer.is_valid():
        raise ToolError(_serializer_error(serializer.errors))
    try:
        message = communication_service.void_message(
            message,
            actor=mcp_actor(),
            **serializer.validated_data,
        )
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _message_detail(message.pk)


def correct_message_date(arguments):
    _reject_unknown_fields(arguments, {'message_id', 'occurred_at', 'reason'})
    message = _message_or_error(arguments.get('message_id'))
    serializer = CommunicationDateCorrectionWriteSerializer(data={
        'occurred_at': arguments.get('occurred_at'),
        'reason': arguments.get('reason'),
    })
    if not serializer.is_valid():
        raise ToolError(_serializer_error(serializer.errors))
    try:
        message = communication_service.correct_message_date(
            message,
            actor=mcp_actor(),
            **serializer.validated_data,
        )
    except communication_service.CommunicationError as exc:
        raise ToolError(str(exc.args[0] if exc.args else exc)) from exc
    return _message_detail(message.pk)


_THREAD_ID = {
    'thread_id': {
        'type': 'integer',
        'minimum': 1,
        'description': 'ID del hilo de comunicaciones que se quiere administrar.',
    },
}

_MESSAGE_ID = {
    'message_id': {
        'type': 'integer',
        'minimum': 1,
        'description': 'ID del mensaje dentro del registro de comunicaciones.',
    },
}


COMMUNICATION_TOOLS = [
    {
        'name': 'list_threads',
        'description': (
            'Lista hilos de comunicaciones, ordenados por actividad reciente. '
            'Úsala para localizar conversaciones por cliente, proyecto, texto, '
            'canal, dirección, estado del hilo, respuesta o estado/fecha de sus mensajes.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'client_id': {'type': 'integer', 'description': 'Filtra por el ID del perfil de cliente.'},
                'project_id': {'type': 'integer', 'description': 'Filtra por el ID del proyecto.'},
                'status': {'type': 'string', 'enum': ['open', 'closed'], 'description': 'Estado actual del hilo.'},
                'channel': {'type': 'string', 'enum': ['email', 'whatsapp'], 'description': 'Canal de al menos un mensaje.'},
                'direction': {'type': 'string', 'enum': ['outgoing', 'incoming'], 'description': 'Dirección de al menos un mensaje.'},
                'message_status': {'type': 'string', 'enum': ['draft', 'sent', 'received', 'failed'], 'description': 'Estado de al menos un mensaje.'},
                'reply_status': {'type': 'string', 'enum': ['answered', 'unanswered'], 'description': 'Respondido o sin respuesta; aplica a mensajes salientes enviados y no anulados.'},
                'date_from': {'type': 'string', 'description': 'Fecha o fecha-hora ISO mínima de los mensajes.'},
                'date_to': {'type': 'string', 'description': 'Fecha o fecha-hora ISO máxima de los mensajes.'},
                'q': {'type': 'string', 'description': 'Texto en título, cliente, proyecto, asunto o contenido.'},
                'order': {
                    'type': 'string',
                    'enum': ['recent', 'oldest', 'title'],
                    'description': 'Ordena por actividad reciente, actividad antigua o título.',
                },
                'scope': {
                    'type': 'string',
                    'enum': ['active', 'archived', 'all'],
                    'description': 'Consulta hilos activos, archivados o ambos; active por defecto.',
                },
                'page': {'type': 'integer', 'minimum': 1, 'description': 'Página, desde 1.'},
                'page_size': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'description': 'Resultados por página; máximo 100.'},
            },
            'additionalProperties': False,
        },
        'handler': list_threads,
    },
    {
        'name': 'get_thread',
        'description': (
            'Abre un hilo completo con sus mensajes cronológicos, estados, '
            'respuestas, documentos referenciados y correcciones de fecha. '
            'No modifica la conversación.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _THREAD_ID,
            'required': ['thread_id'],
            'additionalProperties': False,
        },
        'handler': get_thread,
    },
    {
        'name': 'create_thread',
        'description': (
            'Crea un hilo vacío para un cliente existente. client_id es '
            'obligatorio; project_id es opcional pero, si se envía, el proyecto '
            'debe pertenecer a ese cliente. El hilo nace abierto.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'client_id': {'type': 'integer', 'description': 'ID obligatorio del perfil de cliente.'},
                'project_id': {'type': ['integer', 'null'], 'description': 'ID opcional de un proyecto del mismo cliente.'},
                'title': {'type': 'string', 'description': 'Título descriptivo del hilo.'},
            },
            'required': ['client_id', 'title'],
            'additionalProperties': False,
        },
        'handler': create_thread,
    },
    {
        'name': 'update_thread',
        'description': (
            'Edita un hilo abierto localizado previamente. Permite corregir el '
            'título o asociar/desasociar un proyecto del mismo cliente; el cliente '
            'histórico, la identidad y los mensajes del hilo se conservan. '
            'Envía thread_id y al menos uno de title, project_id o folder_id.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_THREAD_ID,
                'title': {
                    'type': 'string',
                    'description': 'Nuevo título no vacío del hilo.',
                },
                'project_id': {
                    'type': ['integer', 'null'],
                    'description': 'Proyecto del mismo cliente; null deja el hilo sin proyecto.',
                },
            },
            'required': ['thread_id'],
            'additionalProperties': False,
        },
        'handler': update_thread,
    },
    {
        'name': 'close_thread',
        'description': (
            'Cierra un hilo abierto sin archivarlo. Mientras esté cerrado no '
            'acepta mensajes nuevos ni permite confirmar borradores como enviados.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _THREAD_ID,
            'required': ['thread_id'],
            'additionalProperties': False,
        },
        'handler': close_thread,
    },
    {
        'name': 'reopen_thread',
        'description': (
            'Reabre un hilo cerrado para permitir nuevas anotaciones y confirmar '
            'envíos pendientes; no cambia su condición de archivo.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _THREAD_ID,
            'required': ['thread_id'],
            'additionalProperties': False,
        },
        'handler': reopen_thread,
    },
    {
        'name': 'archive_thread',
        'description': (
            'Archiva un hilo manual para retirarlo de la consulta activa sin '
            'borrarlo ni cerrarlo. Las comunicaciones madre no se pueden archivar.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _THREAD_ID,
            'required': ['thread_id'],
            'additionalProperties': False,
        },
        'handler': archive_thread,
    },
    {
        'name': 'unarchive_thread',
        'description': (
            'Restaura un hilo archivado a la consulta activa conservando su '
            'estado abierto o cerrado y todo su historial.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _THREAD_ID,
            'required': ['thread_id'],
            'additionalProperties': False,
        },
        'handler': unarchive_thread,
    },
    {
        'name': 'create_message',
        'description': (
            'Agrega un mensaje a un hilo abierto. Los entrantes se registran '
            'como recibidos y los salientes como borradores; esta herramienta '
            'no envía correo ni WhatsApp. Puede responder otro mensaje del mismo '
            'hilo y referenciar documentos existentes del cliente.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_THREAD_ID,
                'channel': {'type': 'string', 'enum': ['email', 'whatsapp'], 'description': 'Canal en el que ocurrió u ocurrirá el mensaje.'},
                'direction': {'type': 'string', 'enum': ['outgoing', 'incoming'], 'description': 'outgoing para ProjectApp→cliente; incoming para cliente→ProjectApp.'},
                'subject': {'type': 'string', 'description': 'Asunto obligatorio en email y vacío en WhatsApp.'},
                'content': {'type': 'string', 'description': 'Texto completo del mensaje.'},
                'occurred_at': {'type': 'string', 'description': 'Fecha-hora ISO; usa la fecha actual si se omite.'},
                'reply_to_id': {'type': ['integer', 'null'], 'description': 'Mensaje previo del mismo hilo y dirección opuesta.'},
                'document_ids': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'Documentos existentes del mismo cliente para referenciar.'},
            },
            'required': ['thread_id', 'channel', 'direction', 'content'],
            'additionalProperties': False,
        },
        'handler': create_message,
    },
    {
        'name': 'update_message',
        'description': (
            'Edita en el mismo registro un borrador saliente activo localizado '
            'previamente con get_thread. Permite corregir asunto, contenido, fecha, '
            'respuesta y documentos del cliente; conserva ID, hilo, canal y dirección. '
            'No crea otro mensaje ni envía correo o WhatsApp. Envía message_id '
            'y al menos uno de subject, content, document_ids, reply_to_id u occurred_at.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'message_id': {
                    'type': 'integer',
                    'minimum': 1,
                    'description': 'ID obligatorio del borrador saliente activo.',
                },
                'subject': {
                    'type': 'string',
                    'description': 'Asunto obligatorio y no vacío para correo; vacío para WhatsApp.',
                },
                'content': {
                    'type': 'string',
                    'description': 'Texto completo corregido del mensaje.',
                },
                'document_ids': {
                    'type': 'array',
                    'items': {'type': 'integer', 'minimum': 1},
                    'description': 'Reemplaza por completo los documentos relacionados; [] elimina todos.',
                },
                'reply_to_id': {
                    'type': ['integer', 'null'],
                    'description': 'Mensaje de dirección opuesta del mismo hilo; null elimina la referencia.',
                },
                'occurred_at': {
                    'type': 'string',
                    'description': 'Fecha-hora ISO corregida del borrador.',
                },
            },
            'required': ['message_id'],
            'additionalProperties': False,
        },
        'handler': update_message,
    },
    {
        'name': 'delete_draft',
        'description': (
            'Elimina definitivamente un borrador activo. Rechaza mensajes '
            'enviados, recibidos, fallidos o anulados para preservar la evidencia.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _MESSAGE_ID,
            'required': ['message_id'],
            'additionalProperties': False,
        },
        'handler': delete_draft,
    },
    {
        'name': 'mark_message_sent',
        'description': (
            'Marca como enviado un borrador saliente activo y, opcionalmente, '
            'corrige la fecha-hora del envío. Sólo registra que el envío ocurrió '
            'fuera del sistema; no entrega el mensaje por ningún canal.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_MESSAGE_ID,
                'occurred_at': {'type': 'string', 'description': 'Fecha-hora ISO real del envío; conserva la actual si se omite.'},
            },
            'required': ['message_id'],
            'additionalProperties': False,
        },
        'handler': mark_message_sent,
    },
    {
        'name': 'void_message',
        'description': (
            'Anula un mensaje enviado, recibido o fallido sin eliminarlo. Exige '
            'un motivo y conserva el contenido como evidencia histórica.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_MESSAGE_ID,
                'reason': {
                    'type': 'string',
                    'minLength': 1,
                    'description': 'Motivo obligatorio de la anulación.',
                },
            },
            'required': ['message_id', 'reason'],
            'additionalProperties': False,
        },
        'handler': void_message,
    },
    {
        'name': 'correct_message_date',
        'description': (
            'Corrige la fecha-hora de un mensaje enviado, recibido o fallido y '
            'agrega una corrección append-only con actor, motivo y valores anterior/nuevo.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_MESSAGE_ID,
                'occurred_at': {
                    'type': 'string',
                    'description': 'Nueva fecha-hora ISO, distinta de la actual.',
                },
                'reason': {
                    'type': 'string',
                    'minLength': 1,
                    'description': 'Motivo obligatorio de la corrección.',
                },
            },
            'required': ['message_id', 'occurred_at', 'reason'],
            'additionalProperties': False,
        },
        'handler': correct_message_date,
    },
]


# Filing is organizational and also works on closed threads.
for _tool in COMMUNICATION_TOOLS:
    if _tool['name'] in {'create_thread', 'update_thread'}:
        _tool['input_schema']['properties']['folder_id'] = {
            'type': ['integer', 'null'], 'minimum': 1,
            'description': 'Carpeta compatible; null deja el hilo sin carpeta.',
        }
    if _tool['name'] == 'list_threads':
        _tool['input_schema']['properties']['folder'] = {
            'type': ['integer', 'string'],
            'description': 'ID de carpeta o none; q busca en todas las carpetas del contexto.',
        }

from content.mcp.communication_folder_tools import COMMUNICATION_FOLDER_TOOLS
COMMUNICATION_TOOLS.extend(COMMUNICATION_FOLDER_TOOLS)
