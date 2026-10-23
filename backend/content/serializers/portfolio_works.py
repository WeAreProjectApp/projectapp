from content.serializers.editorial import EditorialModelSerializer
import copy as _copy

from rest_framework import serializers

from content.models import PortfolioWork


def _get_lang(serializer):
    """Return 'es' or 'en' from serializer context (default 'es')."""
    request = serializer.context.get('request')
    if request:
        lang = request.query_params.get('lang', 'es')
        return lang if lang in ('es', 'en') else 'es'
    return serializer.context.get('lang', 'es')


def _get_cover_image_display(obj):
    """Return the best available cover image URL: uploaded file first, then external URL."""
    if obj.cover_image:
        return obj.cover_image.url
    return obj.cover_image_url or ''


# ---------------------------------------------------------------------------
# Public serializers
# ---------------------------------------------------------------------------

class PortfolioWorkListSerializer(EditorialModelSerializer):
    """Lightweight serializer for listing portfolio works on public views."""
    title = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioWork
        fields = (
            'id', 'title', 'slug', 'cover_image', 'excerpt',
            'project_url', 'is_published', 'published_at', 'created_at',
        )

    def get_title(self, obj):
        return getattr(obj, f'title_{_get_lang(self)}')

    def get_excerpt(self, obj):
        return getattr(obj, f'excerpt_{_get_lang(self)}')

    def get_cover_image(self, obj):
        return _get_cover_image_display(obj)


class PortfolioWorkDetailSerializer(EditorialModelSerializer):
    """Full serializer for a single portfolio work (public)."""
    title = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    content_json = serializers.SerializerMethodField()
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()
    meta_keywords = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioWork
        fields = (
            'id', 'title', 'slug', 'cover_image',
            'excerpt', 'content_json', 'project_url',
            'meta_title', 'meta_description', 'meta_keywords',
            'is_published', 'published_at',
            'created_at', 'updated_at',
        )

    def get_title(self, obj):
        return getattr(obj, f'title_{_get_lang(self)}')

    def get_excerpt(self, obj):
        return getattr(obj, f'excerpt_{_get_lang(self)}')

    def get_content_json(self, obj):
        return getattr(obj, f'content_json_{_get_lang(self)}')

    def get_meta_title(self, obj):
        return getattr(obj, f'meta_title_{_get_lang(self)}')

    def get_meta_description(self, obj):
        return getattr(obj, f'meta_description_{_get_lang(self)}')

    def get_meta_keywords(self, obj):
        return getattr(obj, f'meta_keywords_{_get_lang(self)}')

    def get_cover_image(self, obj):
        return _get_cover_image_display(obj)


# ---------------------------------------------------------------------------
# Admin serializers
# ---------------------------------------------------------------------------

class PortfolioWorkAdminListSerializer(EditorialModelSerializer):
    """Admin list serializer — returns both language titles."""
    cover_image_display = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioWork
        fields = (
            'id', 'title_es', 'title_en', 'slug', 'cover_image',
            'cover_image_url', 'cover_image_display',
            'excerpt_es', 'excerpt_en', 'project_url',
            'is_published', 'published_at', 'order', 'created_at',
        )

    def get_cover_image_display(self, obj):
        return _get_cover_image_display(obj)


class PortfolioWorkAdminDetailSerializer(EditorialModelSerializer):
    """Admin detail serializer — returns all bilingual fields."""
    cover_image_display = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioWork
        fields = (
            'id', 'title_es', 'title_en', 'slug', 'cover_image',
            'cover_image_url', 'cover_image_display',
            'excerpt_es', 'excerpt_en',
            'content_json_es', 'content_json_en',
            'project_url',
            'category_title_es', 'category_title_en',
            'meta_title_es', 'meta_title_en',
            'meta_description_es', 'meta_description_en',
            'meta_keywords_es', 'meta_keywords_en',
            'is_published', 'published_at', 'order',
            'created_at', 'updated_at',
        )

    def get_cover_image_display(self, obj):
        return _get_cover_image_display(obj)


class PortfolioWorkCreateUpdateSerializer(EditorialModelSerializer):
    """Serializer for creating and updating portfolio works from the admin panel."""

    class Meta:
        model = PortfolioWork
        fields = (
            'title_es', 'title_en', 'slug',
            'cover_image', 'cover_image_url',
            'excerpt_es', 'excerpt_en',
            'content_json_es', 'content_json_en',
            'project_url',
            'category_title_es', 'category_title_en',
            'meta_title_es', 'meta_title_en',
            'meta_description_es', 'meta_description_en',
            'meta_keywords_es', 'meta_keywords_en',
            'is_published', 'published_at', 'order',
        )
        extra_kwargs = {
            'slug': {'required': False},
            'published_at': {'required': False},
            'cover_image': {'required': False},
            'cover_image_url': {'required': False},
            'excerpt_es': {'required': False},
            'excerpt_en': {'required': False},
            'content_json_es': {'required': False},
            'content_json_en': {'required': False},
            'category_title_es': {'required': False},
            'category_title_en': {'required': False},
            'meta_title_es': {'required': False},
            'meta_title_en': {'required': False},
            'meta_description_es': {'required': False},
            'meta_description_en': {'required': False},
            'meta_keywords_es': {'required': False},
            'meta_keywords_en': {'required': False},
            'order': {'required': False},
        }

    def validate_content_json_es(self, value):
        return _validate_portfolio_json(value)

    def validate_content_json_en(self, value):
        return _validate_portfolio_json(value)


# ---------------------------------------------------------------------------
# JSON import serializer
# ---------------------------------------------------------------------------

class PortfolioWorkFromJSONSerializer(serializers.Serializer):
    """Serializer for creating a portfolio work from a complete JSON payload."""
    title_es = serializers.CharField(max_length=255)
    title_en = serializers.CharField(max_length=255)
    excerpt_es = serializers.CharField(required=False, default='', allow_blank=True)
    excerpt_en = serializers.CharField(required=False, default='', allow_blank=True)
    content_json_es = serializers.DictField(required=True)
    content_json_en = serializers.DictField(required=False, default=dict)
    project_url = serializers.URLField(max_length=500)
    cover_image_url = serializers.CharField(required=False, default='', allow_blank=True)
    is_published = serializers.BooleanField(required=False, default=False)
    order = serializers.IntegerField(required=False, default=0)
    meta_title_es = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    meta_title_en = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    meta_description_es = serializers.CharField(required=False, default='', allow_blank=True)
    meta_description_en = serializers.CharField(required=False, default='', allow_blank=True)
    meta_keywords_es = serializers.CharField(max_length=500, required=False, default='', allow_blank=True)
    meta_keywords_en = serializers.CharField(max_length=500, required=False, default='', allow_blank=True)

    def validate_content_json_es(self, value):
        return _validate_portfolio_json(value)

    def validate_content_json_en(self, value):
        if not value:
            return value
        return _validate_portfolio_json(value)


# ---------------------------------------------------------------------------
# Validation & template helpers
# ---------------------------------------------------------------------------

ALLOWED_PORTFOLIO_SECTIONS = {'problem', 'solution', 'results'}


def _validate_portfolio_json(value):
    """Validate the structured JSON content schema for portfolio works."""
    if not value:
        return value
    if not isinstance(value, dict):
        raise serializers.ValidationError('content_json must be a JSON object.')
    for key in ('problem', 'solution', 'results'):
        if key not in value:
            raise serializers.ValidationError(
                f'content_json must include a "{key}" key.'
            )
        section = value[key]
        if not isinstance(section, dict):
            raise serializers.ValidationError(
                f'"{key}" must be a JSON object with title and description.'
            )
    return value


PORTFOLIO_JSON_TEMPLATE = {
    'problem': {
        'title': 'The Challenge',
        'description': 'Describe the client problem or business challenge.',
        'highlights': [
            'Key pain point one',
            'Key pain point two',
            'Key pain point three',
        ],
    },
    'solution': {
        'title': 'Our Solution',
        'description': 'Describe the approach and technologies used.',
        'highlights': [
            'Solution highlight one',
            'Solution highlight two',
            'Solution highlight three',
        ],
    },
    'results': {
        'title': 'The Results',
        'description': 'Describe the measurable outcomes and impact.',
        'highlights': [
            'Result metric one',
            'Result metric two',
            'Result metric three',
        ],
        'testimonial_video_url': '',
    },
}