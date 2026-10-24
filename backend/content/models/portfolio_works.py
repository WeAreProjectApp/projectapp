from content.models.editorial_text import EditorialTextModel
import os

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class PortfolioWork(EditorialTextModel, models.Model):
    """
    PortfolioWork model representing completed projects or works in the ProjectApp.

    Each work has bilingual titles/excerpts, a slug (auto-generated), cover image,
    structured JSON content describing problem/solution/results, and SEO metadata.

    The content_json_es / content_json_en fields follow this structure:
    {
        "problem":  { "title": "...", "description": "...", "highlights": ["..."] },
        "solution": { "title": "...", "description": "...", "highlights": ["..."] },
        "results":  { "title": "...", "description": "...", "highlights": ["..."],
                       "testimonial_video_url": "" }
    }
    """

    title_en = models.CharField(max_length=255, verbose_name="Title (English)")
    title_es = models.CharField(max_length=255, verbose_name="Title (Spanish)")
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    cover_image = models.ImageField(upload_to='portfolio/cover/', blank=True)
    cover_image_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text='External URL for cover image (used when no file is uploaded).',
    )
    project_url = models.URLField(verbose_name="Project URL", max_length=500)
    category_title_en = models.CharField(
        max_length=255, verbose_name="Category Title (English)", blank=True, default='',
    )
    category_title_es = models.CharField(
        max_length=255, verbose_name="Category Title (Spanish)", blank=True, default='',
    )

    excerpt_es = models.TextField(
        blank=True, default='',
        help_text='Tagline corto en español para las cards del listado.',
    )
    excerpt_en = models.TextField(
        blank=True, default='',
        help_text='Short tagline in English for the listing cards.',
    )

    content_json_es = models.JSONField(
        default=dict, blank=True,
        help_text='Structured JSON content in Spanish (problem, solution, results).',
    )
    content_json_en = models.JSONField(
        default=dict, blank=True,
        help_text='Structured JSON content in English (problem, solution, results).',
    )

    # SEO
    meta_title_es = models.CharField(max_length=255, blank=True, default='')
    meta_title_en = models.CharField(max_length=255, blank=True, default='')
    meta_description_es = models.TextField(blank=True, default='')
    meta_description_en = models.TextField(blank=True, default='')
    meta_keywords_es = models.CharField(max_length=500, blank=True, default='')
    meta_keywords_en = models.CharField(max_length=500, blank=True, default='')

    # Publishing
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0, help_text='Manual sort order (lower first).')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-published_at', '-created_at']
        verbose_name = 'Portfolio Work'
        verbose_name_plural = 'Portfolio Works'

    def __str__(self):
        return self.title_en

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title_es) or slugify(self.title_en)
            slug = base_slug
            counter = 1
            while PortfolioWork.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Remove cover image before deleting the record
        if self.cover_image and os.path.isfile(self.cover_image.path):
            os.remove(self.cover_image.path)
        super().delete(*args, **kwargs)