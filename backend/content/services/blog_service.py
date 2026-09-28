"""
Shared blog post logic used by the panel views (content.views.blog)
and the Blog Publisher MCP tools (content.mcp.tools).

Both entry points must go through the same pipeline so scheduled
publication (Huey), LinkedIn auto-post, and frontend rebuild never diverge.
"""
import copy as _copy
import logging

from django.utils import timezone as tz

from content.models import BlogPost
from content.services.frontend_build import schedule_rebuild_after_publish

logger = logging.getLogger(__name__)

BASE_URL = 'https://projectapp.co'
# Canonical public URL for posts (i18n strategy 'prefix': /blog/* only 301s here)
BLOG_PUBLIC_BASE = f'{BASE_URL}/es-co/blog'


def auto_publish_blog_to_linkedin(post):
    """
    Publish a blog post to LinkedIn if conditions are met:
    - Post is published (is_published=True)
    - Has a linkedin_summary (en preferred, es fallback)
    - Has not been published to LinkedIn yet (no linkedin_post_id)

    Runs silently — logs errors but never raises.
    """
    logger.info(
        '[LinkedIn] auto_publish_blog_to_linkedin called — slug=%s is_published=%s '
        'linkedin_post_id=%s linkedin_summary_es=%s linkedin_summary_en=%s',
        post.slug, post.is_published, bool(post.linkedin_post_id),
        bool(post.linkedin_summary_es), bool(post.linkedin_summary_en),
    )

    if not post.is_published:
        logger.info('[LinkedIn] skip: post "%s" is not published yet', post.slug)
        return
    if post.linkedin_post_id:
        logger.info('[LinkedIn] skip: post "%s" already has linkedin_post_id=%s', post.slug, post.linkedin_post_id)
        return

    # English first: LinkedIn content targets the US market.
    summary = post.linkedin_summary_en or post.linkedin_summary_es
    if not summary:
        logger.info('[LinkedIn] skip: post "%s" has no linkedin_summary (en or es) — fill it to enable auto-post', post.slug)
        return

    lang = 'en' if post.linkedin_summary_en else 'es'
    title = post.title_es if lang == 'es' else post.title_en

    # Get cover image URL
    cover_image_url = ''
    if post.cover_image_url:
        cover_image_url = post.cover_image_url
    elif post.cover_image:
        cover_image_url = f'{BASE_URL}{post.cover_image.url}'

    blog_url = f'{BLOG_PUBLIC_BASE}/{post.slug}'
    logger.info('[LinkedIn] attempting post to LinkedIn: slug=%s lang=%s url=%s', post.slug, lang, blog_url)

    try:
        from content.services.linkedin_service import publish_blog_to_linkedin

        try:
            result = publish_blog_to_linkedin(
                summary=summary,
                blog_url=blog_url,
                title=title,
                cover_image_url=cover_image_url,
                description=post.excerpt_es if lang == 'es' else post.excerpt_en,
            )
        except ValueError as exc:
            logger.error(
                '[LinkedIn] not connected / no credentials for blog "%s": %s',
                post.slug, exc,
            )
            return

        if result['success']:
            post.linkedin_post_id = result['post_id']
            post.linkedin_published_at = tz.now()
            post.save(update_fields=['linkedin_post_id', 'linkedin_published_at'])
            logger.info('[LinkedIn] auto-published blog "%s": post_id=%s', post.slug, result['post_id'])
        else:
            logger.warning('[LinkedIn] publish failed for "%s": %s', post.slug, result['message'])
    except Exception:
        logger.exception('[LinkedIn] unexpected error for blog "%s"', post.slug)


def enqueue_scheduled_publish_if_future(post):
    """
    If the post is a draft with a future published_at, enqueue a one-shot
    Huey task at that exact ETA so it publishes (site + LinkedIn) without
    waiting for the 1-minute periodic sweep.
    """
    if post.is_published or not post.published_at:
        return
    if post.published_at <= tz.now():
        return
    try:
        from content.tasks import publish_single_scheduled_blog
        publish_single_scheduled_blog.schedule(args=(post.id,), eta=post.published_at)
        logger.info(
            'Encolado publish_single_scheduled_blog para post %s a %s',
            post.id, post.published_at,
        )
    except Exception:
        logger.exception('Failed to enqueue scheduled publish for post %s', post.id)


def create_post_from_json(validated_data):
    """Create a BlogPost from BlogPostFromJSONSerializer.validated_data."""
    data = validated_data
    return BlogPost.objects.create(
        title_es=data['title_es'],
        title_en=data['title_en'],
        excerpt_es=data['excerpt_es'],
        excerpt_en=data['excerpt_en'],
        content_json_es=data['content_json_es'],
        content_json_en=data.get('content_json_en') or {},
        cover_image_url=data.get('cover_image_url', ''),
        sources=data.get('sources', []),
        category=data.get('category', ''),
        read_time_minutes=data.get('read_time_minutes', 0),
        is_featured=data.get('is_featured', False),
        is_published=data.get('is_published', False),
        published_at=data.get('published_at'),
        author=data.get('author', 'projectapp-team'),
        meta_title_es=data.get('meta_title_es', ''),
        meta_title_en=data.get('meta_title_en', ''),
        meta_description_es=data.get('meta_description_es', ''),
        meta_description_en=data.get('meta_description_en', ''),
        meta_keywords_es=data.get('meta_keywords_es', ''),
        meta_keywords_en=data.get('meta_keywords_en', ''),
        cover_image_credit=data.get('cover_image_credit', ''),
        cover_image_credit_url=data.get('cover_image_credit_url', ''),
        linkedin_summary_es=data.get('linkedin_summary_es', ''),
        linkedin_summary_en=data.get('linkedin_summary_en', ''),
    )


def run_post_save_pipeline(post, was_published=False):
    """
    Side effects shared by every create/update path.

    - LinkedIn auto-publish fires only on the transition to published
      (auto_publish_blog_to_linkedin also guards internally).
    - A draft with a future published_at gets a one-shot Huey task.
    - Any save touching a live post schedules a frontend rebuild.
    """
    if post.is_published and not was_published:
        auto_publish_blog_to_linkedin(post)
    enqueue_scheduled_publish_if_future(post)
    if post.is_published or was_published:
        schedule_rebuild_after_publish(reason='blog')


def build_blog_json_template():
    """Template payload for blog creation (panel download + MCP tool)."""
    from content.serializers.blog import AVAILABLE_CATEGORIES, BLOG_JSON_TEMPLATE
    return {
        'title_es': 'Título del artículo en español',
        'title_en': 'Article title in English',
        'excerpt_es': 'Resumen corto en español (1-2 oraciones).',
        'excerpt_en': 'Short summary in English (1-2 sentences).',
        'author': 'projectapp-team',
        'content_json_es': _copy.deepcopy(BLOG_JSON_TEMPLATE),
        'content_json_en': _copy.deepcopy(BLOG_JSON_TEMPLATE),
        'cover_image_url': '',
        'cover_image_credit': '',
        'cover_image_credit_url': '',
        'sources': [
            {'name': 'Source Name', 'url': 'https://example.com'},
        ],
        'category': 'technology',
        'read_time_minutes': 8,
        'is_featured': False,
        'is_published': False,
        'meta_title_es': '',
        'meta_title_en': '',
        'meta_description_es': '',
        'meta_description_en': '',
        'meta_keywords_es': '',
        'meta_keywords_en': '',
        'linkedin_summary_es': 'Resumen para LinkedIn en español (máx. ~1300 caracteres). Solo se usa si falta el resumen en inglés.',
        'linkedin_summary_en': 'LinkedIn summary in English (max ~1300 chars). Preferred: the auto-post publishes in English when this field is filled.',
        '_available_categories': AVAILABLE_CATEGORIES,
    }


def get_calendar_posts(start_dt, end_dt):
    """
    Posts with published_at in [start_dt, end_dt] plus drafts created in
    range, as calendar dicts (shape shared by the panel calendar and the
    MCP get_blog_calendar tool).
    """
    published_qs = BlogPost.objects.filter(
        published_at__gte=start_dt,
        published_at__lte=end_dt,
    )
    draft_qs = BlogPost.objects.filter(
        is_published=False,
        published_at__isnull=True,
        created_at__gte=start_dt,
        created_at__lte=end_dt,
    )
    all_ids = set(published_qs.values_list('id', flat=True)) | set(
        draft_qs.values_list('id', flat=True)
    )
    posts = BlogPost.objects.filter(id__in=all_ids)

    data = []
    for p in posts:
        is_scheduled = (
            not p.is_published
            and p.published_at is not None
            and p.published_at > tz.now()
        )
        cal_status = 'published' if p.is_published else ('scheduled' if is_scheduled else 'draft')
        data.append({
            'id': p.id,
            'title_es': p.title_es,
            'title_en': p.title_en,
            'slug': p.slug,
            'category': p.category,
            'is_published': p.is_published,
            'published_at': p.published_at.isoformat() if p.published_at else None,
            'created_at': p.created_at.isoformat(),
            'calendar_status': cal_status,
            'date': (
                p.published_at.strftime('%Y-%m-%d') if p.published_at
                else p.created_at.strftime('%Y-%m-%d')
            ),
        })
    return data
