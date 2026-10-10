import copy as _copy
import logging
import math
from xml.sax.saxutils import escape as xml_escape

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone as tz
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from content.models import BlogPost, PortfolioWork
from content.services.frontend_build import schedule_rebuild_after_publish
from content.services.blog_service import (
    BASE_URL,
    # Re-exported: content.tasks imports auto_publish_blog_to_linkedin from
    # this module at call time (and tests patch it here).
    auto_publish_blog_to_linkedin,  # noqa: F401
    build_blog_json_template,
    create_post_from_json,
    get_calendar_posts,
    run_post_save_pipeline,
)
from content.serializers.blog import (
    BlogPostAdminDetailSerializer,
    BlogPostAdminListSerializer,
    BlogPostCreateUpdateSerializer,
    BlogPostDetailSerializer,
    BlogPostFromJSONSerializer,
    BlogPostListSerializer,
)

logger = logging.getLogger(__name__)

STATIC_SITEMAP_PAGES = [
    ('/en-us', '/es-co', 'weekly', '1.0'),
    ('/es-co', '/en-us', 'weekly', '1.0'),
    ('/en-us/landing-web-design', '/es-co/landing-web-design', 'weekly', '0.9'),
    ('/es-co/landing-web-design', '/en-us/landing-web-design', 'weekly', '0.9'),
    ('/en-us/about-us', '/es-co/about-us', 'monthly', '0.9'),
    ('/es-co/about-us', '/en-us/about-us', 'monthly', '0.9'),
    ('/en-us/portfolio-works', '/es-co/portfolio-works', 'weekly', '0.9'),
    ('/es-co/portfolio-works', '/en-us/portfolio-works', 'weekly', '0.9'),
    ('/en-us/contact', '/es-co/contact', 'monthly', '0.6'),
    ('/es-co/contact', '/en-us/contact', 'monthly', '0.6'),
    ('/en-us/additional-modules', '/es-co/additional-modules', 'weekly', '0.8'),
    ('/es-co/additional-modules', '/en-us/additional-modules', 'weekly', '0.8'),
    ('/en-us/partnership-program', '/es-co/partnership-program', 'monthly', '0.8'),
    ('/es-co/partnership-program', '/en-us/partnership-program', 'monthly', '0.8'),
    ('/en-us/building-with-us', '/es-co/building-with-us', 'monthly', '0.8'),
    ('/es-co/building-with-us', '/en-us/building-with-us', 'monthly', '0.8'),
]


def serve_sitemap_xml(request):
    """Serve a dynamic sitemap.xml combining static pages, blog posts and portfolio works."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
        '',
    ]

    # Static bilingual pages
    for path, alt, changefreq, priority in STATIC_SITEMAP_PAGES:
        hl_self = 'en-us' if path.startswith('/en-us') else 'es-co'
        hl_alt = 'es-co' if hl_self == 'en-us' else 'en-us'
        lines.append('  <url>')
        lines.append(f'    <loc>{BASE_URL}{xml_escape(path)}</loc>')
        lines.append(f'    <xhtml:link rel="alternate" hreflang="{hl_self}" href="{BASE_URL}{xml_escape(path)}" />')
        lines.append(f'    <xhtml:link rel="alternate" hreflang="{hl_alt}" href="{BASE_URL}{xml_escape(alt)}" />')
        lines.append(f'    <changefreq>{changefreq}</changefreq>')
        lines.append(f'    <priority>{priority}</priority>')
        lines.append('  </url>')

    # Blog index (bilingual — i18n strategy is 'prefix', unprefixed /blog is not a route)
    lines.append('')
    lines.append('  <!-- Blog -->')
    for idx_path, idx_alt in (('/es-co/blog', '/en-us/blog'), ('/en-us/blog', '/es-co/blog')):
        hl_self = 'es-co' if idx_path.startswith('/es-co') else 'en-us'
        hl_alt = 'en-us' if hl_self == 'es-co' else 'es-co'
        lines.append('  <url>')
        lines.append(f'    <loc>{BASE_URL}{idx_path}</loc>')
        lines.append(f'    <xhtml:link rel="alternate" hreflang="{hl_self}" href="{BASE_URL}{idx_path}" />')
        lines.append(f'    <xhtml:link rel="alternate" hreflang="{hl_alt}" href="{BASE_URL}{idx_alt}" />')
        lines.append('    <changefreq>daily</changefreq>')
        lines.append('    <priority>0.8</priority>')
        lines.append('  </url>')

    # Blog posts (dynamic, bilingual)
    posts = BlogPost.objects.filter(is_published=True).values('slug', 'updated_at')
    if posts.exists():
        lines.append('')
        lines.append('  <!-- Blog Posts -->')
        for post in posts:
            lastmod = post['updated_at'].strftime('%Y-%m-%d') if post['updated_at'] else ''
            es_url = f'{BASE_URL}/es-co/blog/{xml_escape(post["slug"])}'
            en_url = f'{BASE_URL}/en-us/blog/{xml_escape(post["slug"])}'
            for loc_url in (es_url, en_url):
                lines.append('  <url>')
                lines.append(f'    <loc>{loc_url}</loc>')
                lines.append(f'    <xhtml:link rel="alternate" hreflang="es-co" href="{es_url}" />')
                lines.append(f'    <xhtml:link rel="alternate" hreflang="en-us" href="{en_url}" />')
                if lastmod:
                    lines.append(f'    <lastmod>{lastmod}</lastmod>')
                lines.append('    <changefreq>weekly</changefreq>')
                lines.append('    <priority>0.7</priority>')
                lines.append('  </url>')

    # Portfolio works (dynamic, bilingual)
    works = PortfolioWork.objects.filter(is_published=True).values('slug', 'updated_at')
    if works.exists():
        lines.append('')
        lines.append('  <!-- Portfolio Works -->')
        for work in works:
            lastmod = work['updated_at'].strftime('%Y-%m-%d') if work['updated_at'] else ''
            en_url = f'{BASE_URL}/en-us/portfolio-works/{xml_escape(work["slug"])}'
            es_url = f'{BASE_URL}/es-co/portfolio-works/{xml_escape(work["slug"])}'
            lines.append('  <url>')
            lines.append(f'    <loc>{en_url}</loc>')
            lines.append(f'    <xhtml:link rel="alternate" hreflang="en-us" href="{en_url}" />')
            lines.append(f'    <xhtml:link rel="alternate" hreflang="es-co" href="{es_url}" />')
            if lastmod:
                lines.append(f'    <lastmod>{lastmod}</lastmod>')
            lines.append('    <changefreq>weekly</changefreq>')
            lines.append('    <priority>0.8</priority>')
            lines.append('  </url>')
            lines.append('  <url>')
            lines.append(f'    <loc>{es_url}</loc>')
            lines.append(f'    <xhtml:link rel="alternate" hreflang="en-us" href="{en_url}" />')
            lines.append(f'    <xhtml:link rel="alternate" hreflang="es-co" href="{es_url}" />')
            if lastmod:
                lines.append(f'    <lastmod>{lastmod}</lastmod>')
            lines.append('    <changefreq>weekly</changefreq>')
            lines.append('    <priority>0.8</priority>')
            lines.append('  </url>')

    lines.append('')
    lines.append('</urlset>')
    lines.append('')

    xml = '\n'.join(lines)
    response = HttpResponse(xml, content_type='application/xml; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=300, s-maxage=300'
    return response


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public endpoints (no auth required)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def list_blog_posts(request):
    """
    List published blog posts with pagination.
    Accepts ?lang=es|en, ?page=1, ?page_size=6 query params.
    Returns {results, count, page, page_size, total_pages}.
    """
    qs = BlogPost.objects.filter(is_published=True)

    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = min(50, max(1, int(request.query_params.get('page_size', 6))))
    except (ValueError, TypeError):
        page_size = 6

    total = qs.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)

    start = (page - 1) * page_size
    end = start + page_size
    page_qs = qs[start:end]

    serializer = BlogPostListSerializer(
        page_qs, many=True, context={'request': request}
    )
    return Response({
        'results': serializer.data,
        'count': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def retrieve_blog_post(request, slug):
    """
    Retrieve a single published blog post by slug.
    Accepts ?lang=es|en query param (default 'es').
    Returns 404 if not found or not published.
    """
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    serializer = BlogPostDetailSerializer(
        post, context={'request': request}
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Admin endpoints (staff only)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_admin_blog_posts(request):
    """
    List all blog posts (including drafts) for admin management.
    Supports pagination via ?page=N&page_size=N query params.
    Returns all bilingual fields.
    """
    qs = BlogPost.objects.all()

    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 15))
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    total = qs.count()
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    end = start + page_size

    serializer = BlogPostAdminListSerializer(qs[start:end], many=True)
    return Response({
        'results': serializer.data,
        'count': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_blog_post(request):
    """
    Create a new blog post.
    """
    serializer = BlogPostCreateUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    post = serializer.save()
    logger.info(
        '[Blog] post created: id=%s slug=%s is_published=%s published_at=%s',
        post.id, post.slug, post.is_published, post.published_at,
    )
    run_post_save_pipeline(post)
    detail = BlogPostAdminDetailSerializer(post)
    return Response(detail.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def retrieve_admin_blog_post(request, post_id):
    """
    Retrieve full blog post detail for admin editing.
    Returns all bilingual fields.
    """
    post = get_object_or_404(BlogPost, pk=post_id)
    serializer = BlogPostAdminDetailSerializer(post)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_blog_post(request, post_id):
    """
    Update a blog post's fields.
    """
    post = get_object_or_404(BlogPost, pk=post_id)
    was_published = post.is_published
    serializer = BlogPostCreateUpdateSerializer(
        post, data=request.data, partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    logger.info(
        '[Blog] post updated: id=%s slug=%s was_published=%s is_published=%s published_at=%s',
        post.id, post.slug, was_published, post.is_published, post.published_at,
    )
    run_post_save_pipeline(post, was_published=was_published)
    detail = BlogPostAdminDetailSerializer(post)
    return Response(detail.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_blog_post(request, post_id):
    """
    Delete a blog post.
    """
    post = get_object_or_404(BlogPost, pk=post_id)
    was_published = post.is_published
    post.delete()
    if was_published:
        schedule_rebuild_after_publish(reason='blog')
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_blog_post_from_json(request):
    """
    Create a blog post from a complete JSON payload.

    Mirrors the proposal create-from-json pattern: accepts metadata
    and structured content_json in a single request.
    """
    serializer = BlogPostFromJSONSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    post = create_post_from_json(serializer.validated_data)
    run_post_save_pipeline(post)
    detail = BlogPostAdminDetailSerializer(post)
    return Response(detail.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_blog_json_template(request):
    """
    Return a downloadable JSON template for blog post creation.
    Includes all section types with placeholder content.
    """
    return Response(build_blog_json_template(), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def blog_sitemap_data(request):
    """
    Return a lightweight list of published blog posts for dynamic sitemap generation.
    Each entry contains slug and updated_at.
    """
    qs = BlogPost.objects.filter(is_published=True).values('slug', 'updated_at')
    return Response(list(qs), status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def duplicate_blog_post(request, post_id):
    """
    Duplicate a blog post: creates a deep copy reset to draft status.
    """
    post = get_object_or_404(BlogPost, pk=post_id)

    new_post = BlogPost.objects.create(
        title_es=f'{post.title_es} (copia)',
        title_en=f'{post.title_en} (copy)',
        slug='',
        excerpt_es=post.excerpt_es,
        excerpt_en=post.excerpt_en,
        content_es=post.content_es,
        content_en=post.content_en,
        content_json_es=_copy.deepcopy(post.content_json_es),
        content_json_en=_copy.deepcopy(post.content_json_en),
        cover_image_url=post.cover_image_url,
        sources=_copy.deepcopy(post.sources),
        category=post.category,
        read_time_minutes=post.read_time_minutes,
        is_featured=False,
        meta_title_es=post.meta_title_es,
        meta_title_en=post.meta_title_en,
        meta_description_es=post.meta_description_es,
        meta_description_en=post.meta_description_en,
        is_published=False,
        published_at=None,
    )

    detail = BlogPostAdminDetailSerializer(new_post)
    return Response(detail.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([MultiPartParser])
def upload_blog_cover_image(request, post_id):
    """
    Upload a cover image file for a blog post.
    Expects multipart/form-data with a 'cover_image' file field.
    """
    post = get_object_or_404(BlogPost, pk=post_id)
    cover = request.FILES.get('cover_image')
    if not cover:
        return Response(
            {'cover_image': 'No se adjuntó ninguna imagen.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    post.cover_image = cover
    post.save(update_fields=['cover_image', 'updated_at'])

    detail = BlogPostAdminDetailSerializer(post)
    return Response(detail.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def blog_calendar(request):
    """
    Return blog posts within a date range for calendar display.

    Query params:
      - start: YYYY-MM-DD (required)
      - end: YYYY-MM-DD (required)

    Returns posts that have published_at within [start, end],
    plus drafts created within that range.
    """
    start_str = request.query_params.get('start')
    end_str = request.query_params.get('end')

    if not start_str or not end_str:
        return Response(
            {'detail': 'start and end query params are required (YYYY-MM-DD).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    start_date = parse_date(start_str)
    end_date = parse_date(end_str)
    if not start_date or not end_date:
        return Response(
            {'detail': 'Invalid date format. Use YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from datetime import datetime, time
    start_dt = tz.make_aware(datetime.combine(start_date, time.min))
    end_dt = tz.make_aware(datetime.combine(end_date, time.max))

    data = get_calendar_posts(start_dt, end_dt)
    return Response(data, status=status.HTTP_200_OK)
