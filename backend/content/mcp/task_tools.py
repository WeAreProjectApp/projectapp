"""
Tool registry for the Tasks (Kanban) MCP connector.

Lets claude.ai manage the panel's Kanban board (/panel/tasks): list the board,
create/update/move/archive/duplicate tasks, and manage per-task comments and
alerts.

The tasks module has no service layer, so these handlers reuse the panel view's
helpers (`_next_position`, `_grouped_board_tasks`, `_serializer_context`,
`_STATUS_KEYS`, `_BOARD_KEYS`) and always validate through
`TaskCreateUpdateSerializer` to keep column `position` integrity intact.

Guardrails:
- `reorder_task` renumbers the whole target column transactionally (never sets
  an arbitrary position).
- Changing status without a position auto-appends to the new column.
- Comment authorship is attributed to the MCP actor (see content.mcp.actor).

Each entry: {'name', 'description', 'input_schema', 'handler'}.
"""
from django.db import transaction
from django.db.models import Q

from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError
from content.mcp.schema_policy import close_root_schemas
from content.models import Task, TaskAlert, TaskComment
from content.serializers.task import (
    TaskAlertCreateSerializer,
    TaskAlertSerializer,
    TaskCommentCreateSerializer,
    TaskCommentSerializer,
    TaskCreateUpdateSerializer,
    TaskListSerializer,
)
from content.views.task import (
    _BOARD_KEYS,
    _STATUS_KEYS,
    _grouped_board_tasks,
    _next_position,
    _serializer_context,
)


def _serializer_errors_to_message(errors):
    import json
    return 'Datos inválidos: ' + json.dumps(errors, ensure_ascii=False, default=str)


def _get_task_or_error(task_id):
    try:
        return Task.objects.get(pk=int(task_id))
    except (Task.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe una tarea con id={task_id}.')


def _task_payload(task):
    return TaskListSerializer(task, context=_serializer_context()).data


def _grouped_filtered(board_type, q):
    """Like _grouped_board_tasks but with an optional icontains text filter.

    The backend list view has no text search; the operator asked for search in
    every MCP, so `list_tasks` accepts `q` and filters title/description before
    grouping by status.
    """
    if not q:
        return _grouped_board_tasks(board_type)

    context = _serializer_context()
    base = (
        Task.objects.filter(board_type=board_type, is_archived=False)
        .filter(Q(title__icontains=q) | Q(description__icontains=q))
        .select_related('assignee')
        .order_by('position', '-created_at')
    )
    if board_type == Task.BoardType.MACRO:
        return {'items': TaskListSerializer(base, many=True, context=context).data}

    grouped = {key: [] for key in _STATUS_KEYS}
    for task in base:
        grouped.setdefault(task.status, []).append(task)
    return {
        key: TaskListSerializer(grouped[key], many=True, context=context).data
        for key in _STATUS_KEYS
    }


# ── Board / task handlers ────────────────────────────────────────────────────

def list_tasks(arguments):
    board = arguments.get('board', Task.BoardType.STANDARD)
    if board not in _BOARD_KEYS:
        raise ToolError(f'board inválido: usa uno de {_BOARD_KEYS}.')
    q = (arguments.get('q') or '').strip()
    return {'board': board, 'columns': _grouped_filtered(board, q)}


def list_archived_tasks(arguments):
    tasks = Task.objects.filter(is_archived=True).select_related('assignee').order_by('-updated_at')
    return {'results': TaskListSerializer(tasks, many=True, context=_serializer_context()).data}


def list_task_assignees(arguments):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    users = User.objects.filter(is_staff=True, is_active=True).order_by('first_name', 'username')
    return {'results': [
        {'id': u.id, 'name': (u.get_full_name().strip() or u.username)} for u in users
    ]}


def get_task(arguments):
    return _task_payload(_get_task_or_error(arguments.get('task_id')))


def create_task(arguments):
    serializer = TaskCreateUpdateSerializer(data=arguments)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    target_status = serializer.validated_data.get('status', Task.Status.TODO)
    target_board = serializer.validated_data.get('board_type', Task.BoardType.STANDARD)
    task = serializer.save(position=_next_position(target_status, board_type=target_board))
    return _task_payload(task)


def update_task(arguments):
    task = _get_task_or_error(arguments.get('task_id'))
    data = {k: v for k, v in arguments.items() if k != 'task_id'}
    if not data:
        raise ToolError('No se indicó ningún campo para actualizar.')

    serializer = TaskCreateUpdateSerializer(task, data=data, partial=True)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))

    previous_status = task.status
    new_status = serializer.validated_data.get('status', previous_status)
    status_changed = 'status' in serializer.validated_data and new_status != previous_status
    if status_changed and 'position' not in data:
        serializer.validated_data['position'] = _next_position(
            new_status, board_type=task.board_type, exclude_pk=task.pk,
        )
    task = serializer.save()
    return _task_payload(task)


def reorder_task(arguments):
    task = _get_task_or_error(arguments.get('task_id'))
    new_status = arguments.get('status', task.status)
    if new_status not in _STATUS_KEYS:
        raise ToolError(f'status inválido: usa uno de {_STATUS_KEYS}.')
    try:
        new_index = int(arguments.get('position', 0) or 0)
    except (TypeError, ValueError):
        raise ToolError('position debe ser un entero.')
    if new_index < 0:
        new_index = 0

    with transaction.atomic():
        task.status = new_status
        task.save(update_fields=['status'])
        column = list(
            Task.objects.filter(status=new_status, board_type=task.board_type)
            .exclude(pk=task.pk)
            .order_by('position', 'created_at')
        )
        if new_index > len(column):
            new_index = len(column)
        column.insert(new_index, task)
        for index, item in enumerate(column):
            if item.position != index:
                item.position = index
                item.save(update_fields=['position'])

    return {'board': task.board_type, 'columns': _grouped_board_tasks(task.board_type)}


def delete_task(arguments):
    task = _get_task_or_error(arguments.get('task_id'))
    task_id = task.id
    task.delete()
    return {'deleted': True, 'id': task_id}


def duplicate_task(arguments):
    original = _get_task_or_error(arguments.get('task_id'))
    new_task = Task.objects.create(
        title=f'{original.title} (copia)',
        description=original.description,
        status=original.status,
        priority=original.priority,
        board_type=original.board_type,
        assignee=original.assignee,
        due_date=original.due_date,
        position=_next_position(original.status, board_type=original.board_type),
    )
    return _task_payload(new_task)


def archive_task(arguments):
    task = _get_task_or_error(arguments.get('task_id'))
    task.is_archived = True
    task.archive_reason = (arguments.get('archive_reason') or '').strip()
    task.save(update_fields=['is_archived', 'archive_reason'])
    return _task_payload(task)


def unarchive_task(arguments):
    task = _get_task_or_error(arguments.get('task_id'))
    task.is_archived = False
    task.archive_reason = ''
    task.save(update_fields=['is_archived', 'archive_reason'])
    return _task_payload(task)


# ── Comments ─────────────────────────────────────────────────────────────────

def list_task_comments(arguments):
    task = _get_task_or_error(arguments.get('task_id'))
    comments = task.comments.select_related('author').all()
    return {'results': TaskCommentSerializer(comments, many=True).data}


def create_task_comment(arguments):
    task = _get_task_or_error(arguments.get('task_id'))
    serializer = TaskCommentCreateSerializer(data={'text': arguments.get('text')})
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    comment = serializer.save(task=task, author=mcp_actor())
    return TaskCommentSerializer(comment).data


def delete_task_comment(arguments):
    task_id = arguments.get('task_id')
    comment_id = arguments.get('comment_id')
    try:
        comment = TaskComment.objects.get(pk=int(comment_id), task_id=int(task_id))
    except (TaskComment.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe un comentario id={comment_id} en la tarea id={task_id}.')
    comment.delete()
    return {'deleted': True, 'id': comment_id}


# ── Alerts ───────────────────────────────────────────────────────────────────

def list_task_alerts(arguments):
    task = _get_task_or_error(arguments.get('task_id'))
    return {'results': TaskAlertSerializer(task.alerts.all(), many=True).data}


def create_task_alert(arguments):
    task = _get_task_or_error(arguments.get('task_id'))
    data = {'notify_at': arguments.get('notify_at'), 'note': arguments.get('note', '')}
    serializer = TaskAlertCreateSerializer(data=data)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    alert = serializer.save(task=task)
    return TaskAlertSerializer(alert).data


def delete_task_alert(arguments):
    task_id = arguments.get('task_id')
    alert_id = arguments.get('alert_id')
    try:
        alert = TaskAlert.objects.get(pk=int(alert_id), task_id=int(task_id))
    except (TaskAlert.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe una alerta id={alert_id} en la tarea id={task_id}.')
    alert.delete()
    return {'deleted': True, 'id': alert_id}


# ── Registry ─────────────────────────────────────────────────────────────────

_TASK_ID_PROP = {'task_id': {'type': 'integer', 'description': 'ID de la tarea.'}}
_STATUS_ENUM = list(_STATUS_KEYS)
_PRIORITY_ENUM = [p.value for p in Task.Priority]
_BOARD_ENUM = list(_BOARD_KEYS)

_TASK_WRITE_PROPS = {
    'title': {'type': 'string', 'description': 'Título (obligatorio al crear).'},
    'description': {'type': 'string'},
    'status': {'type': 'string', 'enum': _STATUS_ENUM},
    'priority': {'type': 'string', 'enum': _PRIORITY_ENUM},
    'board_type': {'type': 'string', 'enum': _BOARD_ENUM},
    'assignee_id': {'type': ['integer', 'null'], 'description': 'ID de usuario staff (de list_task_assignees).'},
    'due_date': {'type': ['string', 'null'], 'description': 'Fecha límite YYYY-MM-DD.'},
    'position': {
        'type': 'integer',
        'description': 'Posición en la columna; al crear se añade siempre al final. Para renumerar usa reorder_task.',
    },
}

TASK_TOOLS = close_root_schemas([
    {
        'name': 'list_tasks',
        'description': (
            'Devuelve el tablero de un board agrupado por estado '
            '(todo/in_progress/blocked/done). Params: board '
            '(standard/weekly/monthly/macro, default standard) y q opcional '
            'para filtrar por título/descripción.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'board': {'type': 'string', 'enum': _BOARD_ENUM, 'default': 'standard'},
                'q': {'type': 'string', 'description': 'Filtro de texto opcional.'},
            },
        },
        'handler': list_tasks,
    },
    {
        'name': 'list_archived_tasks',
        'description': 'Lista todas las tareas archivadas de todos los boards.',
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': list_archived_tasks,
    },
    {
        'name': 'list_task_assignees',
        'description': 'Lista los usuarios staff activos asignables a una tarea (id + nombre).',
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': list_task_assignees,
    },
    {
        'name': 'get_task',
        'description': (
            'Abre una tarea por ID con descripción, tablero, estado, prioridad, '
            'responsable, vencimiento, posición y estado de archivo.'
        ),
        'input_schema': {'type': 'object', 'properties': _TASK_ID_PROP, 'required': ['task_id']},
        'handler': get_task,
    },
    {
        'name': 'create_task',
        'description': (
            'Crea una tarea (se añade al final de su columna de estado). Sólo '
            'title es obligatorio; el resto usa defaults.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _TASK_WRITE_PROPS,
            'required': ['title'],
        },
        'handler': create_task,
    },
    {
        'name': 'update_task',
        'description': (
            'Actualiza una tarea (parcial). Al cambiar status sin position, la '
            'tarea se reubica al final de la nueva columna. Envía task_id + '
            'campos a cambiar.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_TASK_ID_PROP, **_TASK_WRITE_PROPS},
            'required': ['task_id'],
        },
        'handler': update_task,
    },
    {
        'name': 'reorder_task',
        'description': (
            'Mueve una tarea a un estado y una posición (índice 0-based) y '
            'renumera la columna. Devuelve el tablero actualizado.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_TASK_ID_PROP,
                'status': {'type': 'string', 'enum': _STATUS_ENUM},
                'position': {'type': 'integer', 'minimum': 0},
            },
            'required': ['task_id'],
        },
        'handler': reorder_task,
    },
    {
        'name': 'delete_task',
        'description': (
            'Elimina permanentemente una tarea por ID. Usa archive_task cuando '
            'el historial deba conservarse en el tablero.'
        ),
        'input_schema': {'type': 'object', 'properties': _TASK_ID_PROP, 'required': ['task_id']},
        'handler': delete_task,
    },
    {
        'name': 'duplicate_task',
        'description': 'Duplica una tarea (sólo campos básicos, con " (copia)" en el título).',
        'input_schema': {'type': 'object', 'properties': _TASK_ID_PROP, 'required': ['task_id']},
        'handler': duplicate_task,
    },
    {
        'name': 'archive_task',
        'description': 'Archiva una tarea (opcional archive_reason).',
        'input_schema': {
            'type': 'object',
            'properties': {**_TASK_ID_PROP, 'archive_reason': {'type': 'string'}},
            'required': ['task_id'],
        },
        'handler': archive_task,
    },
    {
        'name': 'unarchive_task',
        'description': 'Restaura una tarea archivada a su tablero.',
        'input_schema': {'type': 'object', 'properties': _TASK_ID_PROP, 'required': ['task_id']},
        'handler': unarchive_task,
    },
    {
        'name': 'list_task_comments',
        'description': (
            'Lista en orden todos los comentarios de una tarea, con autor y '
            'fecha de creación. No modifica el hilo de comentarios.'
        ),
        'input_schema': {'type': 'object', 'properties': _TASK_ID_PROP, 'required': ['task_id']},
        'handler': list_task_comments,
    },
    {
        'name': 'create_task_comment',
        'description': 'Añade un comentario a una tarea. El autor es el usuario de servicio MCP.',
        'input_schema': {
            'type': 'object',
            'properties': {**_TASK_ID_PROP, 'text': {'type': 'string'}},
            'required': ['task_id', 'text'],
        },
        'handler': create_task_comment,
    },
    {
        'name': 'delete_task_comment',
        'description': (
            'Elimina permanentemente un comentario identificado dentro de una '
            'tarea; falla si el comentario pertenece a otra tarea.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_TASK_ID_PROP, 'comment_id': {'type': 'integer'}},
            'required': ['task_id', 'comment_id'],
        },
        'handler': delete_task_comment,
    },
    {
        'name': 'list_task_alerts',
        'description': (
            'Lista las alertas manuales de una tarea, incluidas fecha de aviso, '
            'nota, estado de envío y fecha de creación.'
        ),
        'input_schema': {'type': 'object', 'properties': _TASK_ID_PROP, 'required': ['task_id']},
        'handler': list_task_alerts,
    },
    {
        'name': 'create_task_alert',
        'description': 'Crea una alerta manual para una tarea (notify_at obligatorio, note opcional).',
        'input_schema': {
            'type': 'object',
            'properties': {
                **_TASK_ID_PROP,
                'notify_at': {'type': 'string', 'description': 'Fecha YYYY-MM-DD.'},
                'note': {'type': 'string'},
            },
            'required': ['task_id', 'notify_at'],
        },
        'handler': create_task_alert,
    },
    {
        'name': 'delete_task_alert',
        'description': (
            'Elimina permanentemente una alerta identificada dentro de una '
            'tarea; falla si la alerta pertenece a otra tarea.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_TASK_ID_PROP, 'alert_id': {'type': 'integer'}},
            'required': ['task_id', 'alert_id'],
        },
        'handler': delete_task_alert,
    },
])
