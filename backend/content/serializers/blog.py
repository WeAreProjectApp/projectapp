from content.serializers.editorial import EditorialModelSerializer
import json
import re

from rest_framework import serializers

from content.models import BlogPost

# Literal "\uXXXX" sequences (surrogate pairs first so emojis decode as one
# character). Some MCP clients double-escape non-ASCII text, so the string
# value itself arrives containing these sequences as plain characters.
_LITERAL_UNICODE_ESCAPE_RE = re.compile(
    r'\\u[dD][89abAB][0-9a-fA-F]{2}\\u[dD][c-fC-F][0-9a-fA-F]{2}'
    r'|\\u[0-9a-fA-F]{4}'
)


def _decode_escape_match(match):
    seq = match.group(0)
    decoded = json.loads(f'"{seq}"')
    if any('\ud800' <= ch <= '\udfff' for ch in decoded):
        # Unpaired surrogate — not representable; keep the literal text.
        return seq
    return decoded


def decode_literal_unicode_escapes(value):
    """Recursively decode literal \\uXXXX sequences in strings so text
    reaches the DB as real UTF-8 (defense against double-escaping clients)."""
    if isinstance(value, str):
        if '\\u' not in value:
            return value
        return _LITERAL_UNICODE_ESCAPE_RE.sub(_decode_escape_match, value)
    if isinstance(value, dict):
        return {k: decode_literal_unicode_escapes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode_literal_unicode_escapes(item) for item in value]
    return value


def _get_lang(serializer):
    """Return 'es' or 'en' from serializer context (default 'es')."""
    request = serializer.context.get('request')
    if request:
        lang = request.query_params.get('lang', 'es')
        return lang if lang in ('es', 'en') else 'es'
    return serializer.context.get('lang', 'es')


# ---------------------------------------------------------------------------
# Public serializers — expose virtual title/excerpt/content based on lang
# ---------------------------------------------------------------------------

def _get_cover_image_display(obj):
    """Return the best available cover image URL: uploaded file first, then external URL."""
    if obj.cover_image:
        return obj.cover_image.url
    return obj.cover_image_url or ''


class BlogPostListSerializer(EditorialModelSerializer):
    """
    Lightweight serializer for listing blog posts on public and admin views.
    Exposes language-resolved title and excerpt fields.
    """
    title = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    excerpt_plain = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = (
            'id', 'title', 'slug', 'cover_image',
            'excerpt', 'excerpt_plain', 'category', 'read_time_minutes', 'is_featured',
            'author',
            'is_published', 'published_at', 'created_at',
        )

    def get_title(self, obj):
        lang = _get_lang(self)
        return getattr(obj, f'title_{lang}')

    def get_excerpt(self, obj):
        lang = _get_lang(self)
        return getattr(obj, f'excerpt_{lang}')

    def get_excerpt_plain(self, obj):
        from content.services.editorial_format import plain_text
        key = 'excerpt_' + _get_lang(self)
        return plain_text(getattr(obj, key), format=obj.text_formats.get('/' + key, 'plain'))

    def get_cover_image(self, obj):
        return _get_cover_image_display(obj)


class BlogPostDetailSerializer(EditorialModelSerializer):
    """
    Full serializer for a single blog post, including content and sources.
    Exposes language-resolved title, excerpt, content and content_json fields.
    """
    title = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    excerpt_plain = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    content_json = serializers.SerializerMethodField()
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    meta_keywords = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = (
            'id', 'title', 'slug', 'cover_image',
            'cover_image_credit', 'cover_image_credit_url',
            'excerpt', 'excerpt_plain', 'content', 'content_json', 'sources',
            'category', 'read_time_minutes', 'is_featured',
            'author',
            'meta_title', 'meta_description', 'meta_keywords',
            'is_published', 'published_at',
            'created_at', 'updated_at',
        )

    def get_title(self, obj):
        lang = _get_lang(self)
        return getattr(obj, f'title_{lang}')

    def get_excerpt(self, obj):
        lang = _get_lang(self)
        return getattr(obj, f'excerpt_{lang}')

    def get_content(self, obj):
        lang = _get_lang(self)
        return getattr(obj, f'content_{lang}')

    def get_content_json(self, obj):
        lang = _get_lang(self)
        return getattr(obj, f'content_json_{lang}')

    def get_meta_title(self, obj):
        lang = _get_lang(self)
        return getattr(obj, f'meta_title_{lang}')

    def get_meta_description(self, obj):
        lang = _get_lang(self)
        return getattr(obj, f'meta_description_{lang}')

    def get_meta_keywords(self, obj):
        lang = _get_lang(self)
        return getattr(obj, f'meta_keywords_{lang}')

    def get_excerpt_plain(self, obj):
        from content.services.editorial_format import plain_text
        key = 'excerpt_' + _get_lang(self)
        return plain_text(getattr(obj, key), format=obj.text_formats.get('/' + key, 'plain'))

    def get_cover_image(self, obj):
        return _get_cover_image_display(obj)


# ---------------------------------------------------------------------------
# Admin serializers — expose all _es/_en fields
# ---------------------------------------------------------------------------

class BlogPostAdminListSerializer(EditorialModelSerializer):
    """
    Admin list serializer — returns both language titles.
    """
    cover_image_display = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = (
            'id', 'title_es', 'title_en', 'slug', 'cover_image',
            'cover_image_url', 'cover_image_display',
            'excerpt_es', 'excerpt_en',
            'category', 'read_time_minutes', 'is_featured',
            'is_published', 'published_at', 'created_at',
        )

    def get_cover_image_display(self, obj):
        return _get_cover_image_display(obj)


class BlogPostAdminDetailSerializer(EditorialModelSerializer):
    """
    Admin detail serializer — returns all bilingual fields.
    """
    cover_image_display = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = (
            'id', 'title_es', 'title_en', 'slug', 'cover_image',
            'cover_image_url', 'cover_image_display',
            'cover_image_credit', 'cover_image_credit_url',
            'excerpt_es', 'excerpt_en',
            'content_es', 'content_en',
            'content_json_es', 'content_json_en',
            'sources', 'category', 'read_time_minutes', 'is_featured',
            'author',
            'meta_title_es', 'meta_title_en',
            'meta_description_es', 'meta_description_en',
            'meta_keywords_es', 'meta_keywords_en',
            'linkedin_summary_es', 'linkedin_summary_en',
            'linkedin_post_id', 'linkedin_published_at',
            'is_published', 'published_at',
            'created_at', 'updated_at',
        )

    def get_cover_image_display(self, obj):
        return _get_cover_image_display(obj)


class BlogPostCreateUpdateSerializer(EditorialModelSerializer):
    """
    Serializer for creating and updating blog posts from the admin panel.
    """

    class Meta:
        model = BlogPost
        fields = (
            'title_es', 'title_en', 'slug', 'cover_image',
            'cover_image_url',
            'cover_image_credit', 'cover_image_credit_url',
            'excerpt_es', 'excerpt_en',
            'content_es', 'content_en',
            'content_json_es', 'content_json_en',
            'sources', 'category', 'read_time_minutes', 'is_featured',
            'author',
            'meta_title_es', 'meta_title_en',
            'meta_description_es', 'meta_description_en',
            'meta_keywords_es', 'meta_keywords_en',
            'linkedin_summary_es', 'linkedin_summary_en',
            'is_published', 'published_at',
        )
        extra_kwargs = {
            'slug': {'required': False},
            'published_at': {'required': False},
            'content_es': {'required': False},
            'content_en': {'required': False},
            'content_json_es': {'required': False},
            'content_json_en': {'required': False},
            'category': {'required': False},
            'read_time_minutes': {'required': False},
            'is_featured': {'required': False},
            'meta_title_es': {'required': False},
            'meta_title_en': {'required': False},
            'meta_description_es': {'required': False},
            'meta_description_en': {'required': False},
            'meta_keywords_es': {'required': False},
            'meta_keywords_en': {'required': False},
            'linkedin_summary_es': {'required': False},
            'linkedin_summary_en': {'required': False},
            'cover_image_credit': {'required': False},
            'cover_image_credit_url': {'required': False},
            'author': {'required': False},
        }

    def validate_sources(self, value):
        """Ensure sources is a list of objects with name and url."""
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'sources must be a JSON array.'
            )
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError(
                    'Each source must be a JSON object.'
                )
            if 'name' not in item or 'url' not in item:
                raise serializers.ValidationError(
                    'Each source must have "name" and "url" keys.'
                )
        return value

    def validate_content_json_es(self, value):
        return _validate_content_json(value)

    def validate_content_json_en(self, value):
        return _validate_content_json(value)

    def validate(self, attrs):
        return decode_literal_unicode_escapes(attrs)


# ---------------------------------------------------------------------------
# JSON content validation helper
# ---------------------------------------------------------------------------

ALLOWED_SECTION_KEYS = {
    'heading', 'content', 'list', 'subsections', 'timeline', 'examples',
    'image', 'quote', 'callout', 'video', 'key_takeaways', 'faq', 'text_formats',
}


def _validate_content_json(value):
    """Validate the structured JSON content schema."""
    if not value:
        return value
    if not isinstance(value, dict):
        raise serializers.ValidationError('content_json must be a JSON object.')
    if 'intro' not in value or 'sections' not in value:
        raise serializers.ValidationError(
            'content_json must include "intro" and "sections" keys.'
        )
    if not isinstance(value['sections'], list):
        raise serializers.ValidationError('"sections" must be a list.')
    for i, section in enumerate(value['sections']):
        if not isinstance(section, dict):
            raise serializers.ValidationError(
                f'sections[{i}] must be a JSON object.'
            )
        if 'heading' not in section:
            raise serializers.ValidationError(
                f'sections[{i}] must have a "heading" key.'
            )
    return value


# ---------------------------------------------------------------------------
# JSON blog template
# ---------------------------------------------------------------------------

BLOG_JSON_TEMPLATE = {
    'intro': 'Introductory paragraph for the blog post.',
    'sections': [
        {
            'heading': 'Section Title',
            'content': 'Paragraph text for this section.',
            'list': ['Item one', 'Item two', 'Item three'],
        },
        {
            'heading': 'Another Section',
            'content': 'More content here.',
            'subsections': [
                {'title': 'Subsection A', 'description': 'Description of subsection A.'},
                {'title': 'Subsection B', 'description': 'Description of subsection B.'},
            ],
        },
        {
            'heading': 'Section with Image',
            'content': 'Content that accompanies the image.',
            'image': {
                'url': 'https://images.unsplash.com/photo-example',
                'alt': 'Descriptive alt text for the image.',
                'credit': 'Photo by John Doe on Unsplash',
                'credit_url': 'https://unsplash.com/@johndoe',
            },
        },
        {
            'heading': 'Section with Quote',
            'content': 'Context around the quote.',
            'quote': {
                'text': 'The best way to predict the future is to invent it.',
                'author': 'Alan Kay',
            },
        },
        {
            'heading': 'Process / Timeline',
            'content': 'How the process works:',
            'timeline': [
                {'step': 'Step 1', 'description': 'First step description.'},
                {'step': 'Step 2', 'description': 'Second step description.'},
            ],
        },
        {
            'heading': 'Examples',
            'content': 'Real-world use cases:',
            'examples': ['Example one', 'Example two'],
        },
        {
            'heading': 'Important Note',
            'content': 'Additional context around the callout.',
            'callout': {
                'type': 'tip',
                'title': 'Pro Tip',
                'text': 'Callout body text. Type can be: tip, warning, info, or note.',
            },
        },
        {
            'heading': 'Watch the Demo',
            'content': 'See it in action:',
            'video': {
                'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'title': 'Demo video title for accessibility.',
            },
        },
        {
            'heading': 'Key Takeaways',
            'key_takeaways': [
                'First key insight or learning from the article.',
                'Second key insight summarised in one sentence.',
                'Third takeaway the reader should remember.',
            ],
        },
        {
            'heading': 'Frequently Asked Questions',
            'faq': [
                {
                    'question': 'What is the main benefit?',
                    'answer': 'The main benefit is improved efficiency and lower costs.',
                },
                {
                    'question': 'How long does implementation take?',
                    'answer': 'Typical implementation takes 2-4 weeks depending on complexity.',
                },
            ],
        },
    ],
    'conclusion': 'Concluding paragraph summarising the article.',
    'cta': 'Call to action text inviting the reader to take the next step.',
}

AVAILABLE_CATEGORIES = [
    {'slug': slug, 'label': label}
    for slug, label in BlogPost.CATEGORY_CHOICES
]


class BlogPostFromJSONSerializer(serializers.Serializer):
    """
    Serializer for creating a blog post from a complete JSON payload.
    Mirrors the ProposalFromJSONSerializer pattern.
    """
    title_es = serializers.CharField(max_length=255)
    title_en = serializers.CharField(max_length=255)
    excerpt_es = serializers.CharField()
    excerpt_en = serializers.CharField()
    text_formats = serializers.JSONField(required=False, default=dict)
    content_json_es = serializers.DictField(required=True)
    content_json_en = serializers.DictField(required=False, default=dict)
    cover_image_url = serializers.CharField(required=False, default='', allow_blank=True)
    sources = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
    )
    category = serializers.CharField(max_length=50, required=False, default='')
    read_time_minutes = serializers.IntegerField(required=False, default=0)
    is_featured = serializers.BooleanField(required=False, default=False)
    is_published = serializers.BooleanField(required=False, default=False)
    published_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    author = serializers.CharField(max_length=50, required=False, default='projectapp-team', allow_blank=True)
    meta_title_es = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    meta_title_en = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    meta_description_es = serializers.CharField(required=False, default='', allow_blank=True)
    meta_description_en = serializers.CharField(required=False, default='', allow_blank=True)
    meta_keywords_es = serializers.CharField(max_length=500, required=False, default='', allow_blank=True)
    meta_keywords_en = serializers.CharField(max_length=500, required=False, default='', allow_blank=True)
    cover_image_credit = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    cover_image_credit_url = serializers.CharField(required=False, default='', allow_blank=True)
    linkedin_summary_es = serializers.CharField(required=False, default='', allow_blank=True)
    linkedin_summary_en = serializers.CharField(required=False, default='', allow_blank=True)

    def validate_content_json_es(self, value):
        return _validate_content_json(value)

    def validate_content_json_en(self, value):
        if not value:
            return value
        return _validate_content_json(value)

    def validate_sources(self, value):
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError('Each source must be a JSON object.')
            if 'name' not in item or 'url' not in item:
                raise serializers.ValidationError(
                    'Each source must have "name" and "url" keys.'
                )
        return value

    def validate(self, attrs):
        from content.services.editorial_format import validate_editorial_values
        validate_editorial_values('blogpost', attrs)
        return decode_literal_unicode_escapes(attrs)
