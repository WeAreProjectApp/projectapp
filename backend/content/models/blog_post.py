from content.models.editorial_text import EditorialTextModel
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class BlogPost(EditorialTextModel, models.Model):
    """
    Model for blog articles.

    Each post has a title, slug (auto-generated), cover image,
    excerpt for cards/listing, full HTML content, and a JSON list
    of sources consulted (each with name and url).

    Supports two content formats:
    - HTML (content_es / content_en) — legacy plain HTML.
    - Structured JSON (content_json_es / content_json_en) — rich
      sections with headings, lists, timelines, subsections, etc.
      When present, the frontend renders the JSON; otherwise it
      falls back to HTML via v-html.
    """

    AUTHOR_CHOICES = [
        ('projectapp-team', 'Project App Team'),
        ('gustavo-perez', 'Gustavo Pérez — CEO'),
        ('carlos-blanco', 'Carlos Blanco — CFO'),
    ]

    CATEGORY_CHOICES = [
        ('technology', 'Technology'),
        ('design', 'Design'),
        ('guides', 'Guides'),
        ('business', 'Business'),
        ('case-study', 'Case Study'),
        ('ai', 'AI'),
        ('development', 'Development'),
        ('marketing', 'Digital Marketing'),
        ('startup', 'Startups'),
        ('productivity', 'Productivity'),
        ('security', 'Cybersecurity'),
        ('cloud', 'Cloud & DevOps'),
        ('data', 'Data & Analytics'),
        ('no-code', 'No-Code / Low-Code'),
        ('trends', 'Trends'),
        ('e-commerce', 'E-Commerce'),
        ('ux-ui', 'UX / UI'),
    ]

    title_es = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    cover_image = models.ImageField(upload_to='blog/covers/', blank=True)
    cover_image_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text='External URL for cover image (used when no file is uploaded).',
    )
    cover_image_credit = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Attribution text for the cover image (e.g. "Photo by John Doe on Unsplash").',
    )
    cover_image_credit_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text='URL to the photographer profile or image source page.',
    )
    excerpt_es = models.TextField(
        help_text='Resumen corto en español (1-2 oraciones).'
    )
    excerpt_en = models.TextField(
        help_text='Short summary in English (1-2 sentences).'
    )
    content_es = models.TextField(
        blank=True, default='',
        help_text='Contenido completo del artículo en HTML (español).'
    )
    content_en = models.TextField(
        blank=True, default='',
        help_text='Full article content in HTML (English).'
    )
    content_json_es = models.JSONField(
        default=dict, blank=True,
        help_text='Structured JSON content in Spanish (intro, sections, conclusion, cta).'
    )
    content_json_en = models.JSONField(
        default=dict, blank=True,
        help_text='Structured JSON content in English (intro, sections, conclusion, cta).'
    )
    sources = models.JSONField(
        default=list, blank=True,
        help_text='List of {name, url} objects for consulted sources.'
    )

    category = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Category slug for filtering (e.g. technology, design, guides).'
    )
    read_time_minutes = models.PositiveIntegerField(
        default=0,
        help_text='Estimated reading time in minutes.'
    )
    is_featured = models.BooleanField(
        default=False,
        help_text='Pin this post as the featured/hero post on the blog listing.'
    )
    author = models.CharField(
        max_length=50, blank=True, default='projectapp-team',
        choices=AUTHOR_CHOICES,
        help_text='Author profile slug (projectapp-team, gustavo-perez, carlos-blanco).',
    )

    meta_title_es = models.CharField(
        max_length=255, blank=True, default='',
        help_text='SEO title override in Spanish.'
    )
    meta_title_en = models.CharField(
        max_length=255, blank=True, default='',
        help_text='SEO title override in English.'
    )
    meta_description_es = models.TextField(
        blank=True, default='',
        help_text='SEO meta description in Spanish.'
    )
    meta_description_en = models.TextField(
        blank=True, default='',
        help_text='SEO meta description in English.'
    )
    meta_keywords_es = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Comma-separated SEO keywords in Spanish.',
    )
    meta_keywords_en = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Comma-separated SEO keywords in English.',
    )

    linkedin_summary_es = models.TextField(
        blank=True, default='',
        help_text='Resumen para publicar en LinkedIn (español). Máximo ~1300 caracteres.',
    )
    linkedin_summary_en = models.TextField(
        blank=True, default='',
        help_text='Summary for LinkedIn post (English). Max ~1300 characters.',
    )
    linkedin_post_id = models.CharField(
        max_length=255, blank=True, default='',
        help_text='LinkedIn post URN after successful publication.',
    )
    linkedin_published_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Timestamp of last successful LinkedIn publication.',
    )

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = 'Blog Post'
        verbose_name_plural = 'Blog Posts'

    def __str__(self):
        return self.title_es

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title_es)
            slug = base_slug
            counter = 1
            while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
