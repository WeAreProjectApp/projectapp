"""
Tool registry for the Blog Publisher MCP.

Each entry: {'name', 'description', 'input_schema', 'handler'}.
Handlers receive the raw `arguments` dict from tools/call, return a
JSON-serializable dict, and raise ToolError for business errors.
They reuse the exact same serializers and service pipeline as the panel.
"""
import json
from datetime import datetime, time

from django.utils import timezone as tz
from django.utils.dateparse import parse_date

from content.mcp.protocol import ToolError
from content.mcp.schema_policy import closed_object, close_root_schemas, open_object
from content.models import BlogPost
from content.serializers.blog import (
    BlogPostAdminDetailSerializer,
    BlogPostAdminListSerializer,
    BlogPostCreateUpdateSerializer,
    BlogPostFromJSONSerializer,
)
from content.services import blog_service


def _post_status(post):
    if post.is_published:
        return 'published'
    if post.published_at and post.published_at > tz.now():
        return 'scheduled'
    return 'draft'


def _post_summary(post):
    return {
        'id': post.id,
        'slug': post.slug,
        'title_es': post.title_es,
        'status': _post_status(post),
        'published_at': post.published_at.isoformat() if post.published_at else None,
        'public_url': f'{blog_service.BLOG_PUBLIC_BASE}/{post.slug}',
    }


def _serializer_errors_to_message(errors):
    return 'JSON inválido para el blog: ' + json.dumps(errors, ensure_ascii=False, default=str)


def _get_post_or_error(post_id):
    try:
        return BlogPost.objects.get(pk=int(post_id))
    except (BlogPost.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe un blog post con id={post_id}.')


# ── Handlers ────────────────────────────────────────────────────────────────

def get_blog_template(arguments):
    template = blog_service.build_blog_json_template()
    categories = template.pop('_available_categories')
    return {
        'template': template,
        'available_categories': categories,
        'scheduling_notes': (
            'Para programar: is_published=false + published_at futuro (ISO 8601 '
            'con timezone, ej. 2026-07-10T09:00:00-05:00). El sistema publica '
            'automáticamente a esa hora, postea en LinkedIn si hay '
            'linkedin_summary, y reconstruye el sitio. Para publicar ya: '
            'is_published=true. Para borrador: is_published=false sin published_at.'
        ),
    }


def create_blog_post(arguments):
    serializer = BlogPostFromJSONSerializer(data=arguments)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    post = blog_service.create_post_from_json(serializer.validated_data)
    blog_service.run_post_save_pipeline(post)
    return _post_summary(post)


def update_blog_post(arguments):
    args = dict(arguments)
    post = _get_post_or_error(args.pop('post_id', None))
    was_published = post.is_published
    serializer = BlogPostCreateUpdateSerializer(post, data=args, partial=True)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    serializer.save()
    blog_service.run_post_save_pipeline(post, was_published=was_published)
    return _post_summary(post)


def delete_blog_post(arguments):
    post = _get_post_or_error(arguments.get('post_id'))
    if post.is_published:
        raise ToolError(
            'Este post está publicado. Despublícalo primero con update_blog_post '
            '(is_published=false) o elimínalo desde el panel.'
        )
    post_id = post.id
    post.delete()
    return {'deleted': True, 'id': post_id}


def list_blog_posts(arguments):
    try:
        page = max(1, int(arguments.get('page', 1) or 1))
        page_size = max(1, min(int(arguments.get('page_size', 15) or 15), 50))
    except (TypeError, ValueError):
        raise ToolError('page y page_size deben ser enteros.')
    qs = BlogPost.objects.all()
    total = qs.count()
    start = (page - 1) * page_size
    page_posts = list(qs[start:start + page_size])
    rows = BlogPostAdminListSerializer(page_posts, many=True).data
    posts_by_id = {p.id: p for p in page_posts}
    results = []
    for row in rows:
        post = posts_by_id[row['id']]
        results.append({**dict(row), 'status': _post_status(post)})
    return {'count': total, 'page': page, 'page_size': page_size, 'results': results}


def get_blog_post(arguments):
    """Return the complete editable representation, not only the list card."""
    post = _get_post_or_error(arguments.get('post_id'))
    return {
        **BlogPostAdminDetailSerializer(post).data,
        'status': _post_status(post),
        'public_url': f'{blog_service.BLOG_PUBLIC_BASE}/{post.slug}',
    }


def get_blog_calendar(arguments):
    try:
        # parse_date returns None for malformed strings but raises ValueError
        # for well-formed impossible dates (e.g. 2026-02-30).
        start_date = parse_date(str(arguments.get('start', '')))
        end_date = parse_date(str(arguments.get('end', '')))
    except ValueError:
        start_date = end_date = None
    if not start_date or not end_date:
        raise ToolError('Formato de fecha inválido: usa YYYY-MM-DD en start y end.')
    start_dt = tz.make_aware(datetime.combine(start_date, time.min))
    end_dt = tz.make_aware(datetime.combine(end_date, time.max))
    return {'posts': blog_service.get_calendar_posts(start_dt, end_dt)}


# ── Registry ────────────────────────────────────────────────────────────────

_POST_ID_PROP = {'post_id': {'type': 'integer', 'description': 'ID del blog post.'}}

_BLOG_CREATE_PROPS = {
    'title_es': {'type': 'string'},
    'title_en': {'type': 'string'},
    'excerpt_es': {'type': 'string'},
    'excerpt_en': {'type': 'string'},
    'content_json_es': open_object(
        'Contenido estructurado del artículo en español; usa get_blog_template.',
        'El serializer valida secciones de distintos tipos, cuyo contenido y claves dependen del artículo.',
    ),
    'content_json_en': open_object(
        'Contenido estructurado del artículo en inglés; usa get_blog_template.',
        'El serializer valida secciones de distintos tipos, cuyo contenido y claves dependen del artículo.',
    ),
    'category': {'type': 'string'},
    'cover_image_url': {'type': 'string'},
    'sources': {
        'type': 'array',
        'items': closed_object(
            {'name': {'type': 'string'}, 'url': {'type': 'string'}},
            ['name', 'url'],
        ),
    },
    'read_time_minutes': {'type': 'integer'},
    'is_featured': {'type': 'boolean'},
    'is_published': {'type': 'boolean'},
    'published_at': {'type': ['string', 'null'], 'description': 'ISO 8601 con timezone; null quita la programación.'},
    'author': {'type': 'string'},
    'meta_title_es': {'type': 'string'},
    'meta_title_en': {'type': 'string'},
    'meta_description_es': {'type': 'string'},
    'meta_description_en': {'type': 'string'},
    'meta_keywords_es': {'type': 'string'},
    'meta_keywords_en': {'type': 'string'},
    'cover_image_credit': {'type': 'string'},
    'cover_image_credit_url': {'type': 'string'},
    'linkedin_summary_es': {'type': 'string'},
    'linkedin_summary_en': {'type': 'string'},
}
_BLOG_UPDATE_PROPS = {
    **_POST_ID_PROP,
    **_BLOG_CREATE_PROPS,
    'slug': {'type': 'string', 'description': 'Identificador del artículo en la URL pública.'},
}

BLOG_TOOLS = close_root_schemas([
    {
        'name': 'get_blog_template',
        'description': (
            'Devuelve el template JSON bilingüe (ES/EN) para crear un blog post, '
            'las categorías disponibles y las reglas de programación. Llama esto '
            'antes de create_blog_post para conocer la estructura exacta.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': get_blog_template,
    },
    {
        'name': 'create_blog_post',
        'description': (
            'Crea un blog post con el JSON completo (misma estructura que '
            'get_blog_template). Borrador: is_published=false. Publicar ya: '
            'is_published=true. Programar: is_published=false + published_at futuro.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _BLOG_CREATE_PROPS,
            'required': ['title_es', 'title_en', 'excerpt_es', 'excerpt_en', 'content_json_es'],
        },
        'handler': create_blog_post,
    },
    {
        'name': 'update_blog_post',
        'description': (
            'Actualiza parcialmente un blog post: envía post_id y sólo los '
            'campos a cambiar (mismos campos que create_blog_post, más slug). '
            'Para despublicar: is_published=false.'
        ),
        'input_schema': closed_object(_BLOG_UPDATE_PROPS, ['post_id']),
        # The write serializer also accepts legacy HTML without advertising it
        # as part of the structured JSON creation workflow.
        'accepted_arguments_schema': closed_object({
            **_BLOG_UPDATE_PROPS,
            'content_es': {'type': 'string', 'description': 'Contenido HTML heredado en español.'},
            'content_en': {'type': 'string', 'description': 'Contenido HTML heredado en inglés.'},
        }, ['post_id']),
        'handler': update_blog_post,
    },
    {
        'name': 'delete_blog_post',
        'description': (
            'Elimina un post NO publicado. Los posts publicados no se pueden '
            'borrar por MCP (guardrail SEO): despublícalos primero o usa el panel.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _POST_ID_PROP,
            'required': ['post_id'],
        },
        'handler': delete_blog_post,
    },
    {
        'name': 'list_blog_posts',
        'description': 'Lista todos los posts (publicados, programados y borradores) con paginación.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'page': {'type': 'integer', 'default': 1},
                'page_size': {'type': 'integer', 'default': 15, 'maximum': 50},
            },
        },
        'handler': list_blog_posts,
    },
    {
        'name': 'get_blog_post',
        'description': (
            'Abre un blog post completo por ID, incluidos contenido bilingüe, '
            'JSON estructurado, fuentes, SEO, portada, copy de LinkedIn y '
            'programación. Úsala después de list_blog_posts y antes de editar.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _POST_ID_PROP,
            'required': ['post_id'],
        },
        'handler': get_blog_post,
    },
    {
        'name': 'get_blog_calendar',
        'description': (
            'Posts con published_at en un rango de fechas más borradores creados '
            'en el rango. Úsalo para revisar qué hay agendado antes de programar.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'start': {'type': 'string', 'description': 'YYYY-MM-DD'},
                'end': {'type': 'string', 'description': 'YYYY-MM-DD'},
            },
            'required': ['start', 'end'],
        },
        'handler': get_blog_calendar,
    },
])
