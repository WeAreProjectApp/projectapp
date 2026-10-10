"""
Tool registry for the LinkedIn Personal Content MCP connector.

Lets claude.ai manage the freeform LinkedIn posts of the panel module
(/panel/linkedin) for the owner's PERSONAL profile: check the OAuth
connection health, list/read posts, create drafts, schedule, edit,
delete and publish now. A future `linkedin-company` connector will cover
the organization page (different author URN and scope).

Guardrails baked in:
- Published posts are immutable (edit/delete-guarded exactly like the panel).
- No image handling: posts created via MCP are text-only; images stay
  panel-only (the MCP transport does not carry binaries).
- OAuth connection/reconnection is panel-only; tokens are never exposed.

Each entry: {'name', 'description', 'input_schema', 'handler'}. Handlers
receive the raw `arguments` dict, return a JSON-serializable dict, and raise
ToolError for business errors. They reuse the exact same serializer and
service pipeline as the panel (atomic double-publish guard, Huey ETA
scheduling), so behavior never diverges.
"""
from datetime import timedelta

from django.utils import timezone

from content.mcp.protocol import ToolError
from content.mcp.schema_policy import close_root_schemas
from content.models import LinkedInPost
from content.serializers.linkedin_post import LinkedInPostSerializer
from content.services.linkedin_post_service import (
    apply_schedule_transition,
    publish_linkedin_post_now,
)
from content.services.linkedin_service import get_connection_status

STATUS_CHOICES = {choice[0] for choice in LinkedInPost.STATUS_CHOICES}

_EXPIRY_WARN_DAYS = 7


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_post_or_error(post_id):
    try:
        return LinkedInPost.objects.get(pk=int(post_id))
    except (LinkedInPost.DoesNotExist, TypeError, ValueError):
        raise ToolError(
            f'No existe un post de LinkedIn con id={post_id}. '
            'Usa list_posts para ver los disponibles.'
        )


def _public_url(post):
    if post.status == LinkedInPost.STATUS_PUBLISHED and post.linkedin_post_id:
        return f'https://www.linkedin.com/feed/update/{post.linkedin_post_id}/'
    return None


def _post_summary(post):
    return {
        'id': post.id,
        'commentary_preview': (
            post.commentary if len(post.commentary) <= 120
            else post.commentary[:120] + '…'
        ),
        'status': post.status,
        'has_image': bool(post.image),
        'scheduled_at': post.scheduled_at.isoformat() if post.scheduled_at else None,
        'published_at': post.published_at.isoformat() if post.published_at else None,
        'public_url': _public_url(post),
    }


def _post_detail(post):
    return {
        **_post_summary(post),
        'commentary': post.commentary,
        'error_message': post.error_message,
        'created_at': post.created_at.isoformat(),
        'updated_at': post.updated_at.isoformat(),
    }


def _serializer_errors_to_message(errors):
    parts = []
    for field, messages in errors.items():
        joined = ' '.join(str(m) for m in messages)
        parts.append(f'{field}: {joined}')
    return 'Datos inválidos — ' + ' | '.join(parts)


def _validate_and_save(serializer):
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    post = serializer.save()
    apply_schedule_transition(post)
    return post


# ── Handlers ─────────────────────────────────────────────────────────────────

def connection_status(arguments):
    status_data = get_connection_status()
    result = dict(status_data)
    if not status_data.get('connected'):
        result['warning'] = (
            'LinkedIn no está conectado. La conexión OAuth se hace desde '
            '/panel/linkedin (botón "Conectar LinkedIn"); no es posible '
            'conectar desde el MCP. Publicar o programar posts fallará '
            'hasta reconectar.'
        )
        return result

    expires_at = status_data.get('expires_at')
    if expires_at:
        from django.utils.dateparse import parse_datetime
        expiry = parse_datetime(expires_at)
        if expiry and expiry <= timezone.now() + timedelta(days=_EXPIRY_WARN_DAYS):
            result['warning'] = (
                f'El token de LinkedIn expira el {expiry.date().isoformat()} '
                '(≤7 días). Reconecta desde /panel/linkedin antes de esa fecha; '
                'los posts programados después fallarán.'
            )
    return result


def list_posts(arguments):
    qs = LinkedInPost.objects.all()
    status_filter = arguments.get('status')
    if status_filter:
        if status_filter not in STATUS_CHOICES:
            raise ToolError(
                f'Status inválido: {status_filter}. '
                f'Opciones: {", ".join(sorted(STATUS_CHOICES))}.'
            )
        qs = qs.filter(status=status_filter)
    posts = list(qs[:50])
    return {
        'count': len(posts),
        'posts': [_post_summary(p) for p in posts],
    }


def get_post(arguments):
    post = _get_post_or_error(arguments.get('post_id'))
    return _post_detail(post)


def create_post(arguments):
    data = {'commentary': arguments.get('commentary', '')}
    if arguments.get('scheduled_at'):
        data['scheduled_at'] = arguments['scheduled_at']
    post = _validate_and_save(LinkedInPostSerializer(data=data))
    return _post_detail(post)


def update_post(arguments):
    post = _get_post_or_error(arguments.get('post_id'))
    if post.status == LinkedInPost.STATUS_PUBLISHED:
        raise ToolError(
            'Un post ya publicado en LinkedIn no se puede editar. '
            'Crea uno nuevo con create_post si necesitas otra versión.'
        )
    data = {}
    if 'commentary' in arguments:
        data['commentary'] = arguments['commentary']
    if 'scheduled_at' in arguments:
        data['scheduled_at'] = arguments['scheduled_at'] or None
    if not data:
        raise ToolError('Nada que actualizar: envía commentary y/o scheduled_at.')
    post = _validate_and_save(LinkedInPostSerializer(post, data=data, partial=True))
    return _post_detail(post)


def delete_post(arguments):
    post = _get_post_or_error(arguments.get('post_id'))
    post_id = post.id
    post.delete()
    return {
        'deleted': True,
        'id': post_id,
        'note': 'Solo se eliminó el registro local; nada cambió en LinkedIn.',
    }


def publish_post(arguments):
    post = _get_post_or_error(arguments.get('post_id'))

    result = publish_linkedin_post_now(post)

    if result.get('already'):
        raise ToolError(result['message'])
    if result.get('not_connected'):
        raise ToolError(
            f'{result["message"]} Reconecta LinkedIn desde /panel/linkedin.'
        )
    if not result['success']:
        raise ToolError(
            f'LinkedIn rechazó la publicación: {result["message"]} '
            'El post quedó en status=failed; corrige y reintenta con publish_post.'
        )

    post.refresh_from_db()
    return _post_detail(post)


# ── Registry ─────────────────────────────────────────────────────────────────

LINKEDIN_TOOLS = close_root_schemas([
    {
        'name': 'get_connection_status',
        'description': (
            'Consulta el estado de la conexión OAuth con LinkedIn (perfil '
            'personal): perfil conectado y fecha de expiración del token. '
            'Incluye warning si está desconectado o expira en ≤7 días. '
            'Úsala antes de publicar o programar.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': connection_status,
    },
    {
        'name': 'list_posts',
        'description': (
            'Lista los posts de LinkedIn del módulo (máx 50, más recientes '
            'primero) con preview del texto, status y fechas. Filtra con '
            'status: draft, scheduled, published o failed. Usa get_post para '
            'el texto completo.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'status': {
                    'type': 'string',
                    'enum': sorted(STATUS_CHOICES),
                    'description': 'Filtrar por status (omitir para todos).',
                },
            },
        },
        'handler': list_posts,
    },
    {
        'name': 'get_post',
        'description': (
            'Devuelve el detalle completo de un post: texto íntegro, status, '
            'programación, URL pública si está publicado y error_message si '
            'falló.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'post_id': {'type': 'integer', 'description': 'ID del post (de list_posts).'},
            },
            'required': ['post_id'],
        },
        'handler': get_post,
    },
    {
        'name': 'create_post',
        'description': (
            'Crea un post de LinkedIn (solo texto, máx 3000 caracteres; las '
            'imágenes se agregan desde /panel/linkedin). Sin scheduled_at '
            'queda como borrador. Con scheduled_at (ISO 8601 futuro con '
            'timezone, ej. 2026-07-10T09:00:00-05:00) queda programado y el '
            'sistema lo publica automáticamente a esa hora.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'commentary': {
                    'type': 'string',
                    'description': 'Texto del post (máx 3000 caracteres).',
                },
                'scheduled_at': {
                    'type': 'string',
                    'description': 'Fecha/hora futura ISO 8601 para programar (omitir para borrador).',
                },
            },
            'required': ['commentary'],
        },
        'handler': create_post,
    },
    {
        'name': 'update_post',
        'description': (
            'Edita el texto y/o la programación de un post en borrador, '
            'programado o fallido. scheduled_at vacío o null cancela la '
            'programación (vuelve a borrador). Los posts publicados son '
            'inmutables.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'post_id': {'type': 'integer', 'description': 'ID del post a editar.'},
                'commentary': {'type': 'string', 'description': 'Nuevo texto (máx 3000).'},
                'scheduled_at': {
                    'type': 'string',
                    'description': 'Nueva fecha ISO 8601 futura, o "" para cancelar la programación.',
                },
            },
            'required': ['post_id'],
        },
        'handler': update_post,
    },
    {
        'name': 'delete_post',
        'description': (
            'Elimina el registro local de un post. No borra nada en LinkedIn '
            '(un post ya publicado sigue visible en el perfil).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'post_id': {'type': 'integer', 'description': 'ID del post a eliminar.'},
            },
            'required': ['post_id'],
        },
        'handler': delete_post,
    },
    {
        'name': 'publish_post',
        'description': (
            'Publica un post inmediatamente en el perfil personal de '
            'LinkedIn. Protegido contra doble publicación. Si LinkedIn '
            'rechaza la publicación el post queda en failed con el detalle '
            'del error y se puede reintentar.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'post_id': {'type': 'integer', 'description': 'ID del post a publicar.'},
            },
            'required': ['post_id'],
        },
        'handler': publish_post,
    },
])
