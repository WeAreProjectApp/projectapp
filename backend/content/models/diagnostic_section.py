from content.models.editorial_text import EditorialTextModel
from django.db import models


class DiagnosticSection(EditorialTextModel, models.Model):
    """Individual section within a WebAppDiagnostic.

    Each section maps to a Vue component on the frontend via ``section_type``.
    Content is stored as JSON matching the props schema of each component.
    """

    class SectionType(models.TextChoices):
        PURPOSE = 'purpose', 'Propósito + Escala de Severidad'
        RADIOGRAPHY = 'radiography', 'Radiografía de la Aplicación'
        CATEGORIES = 'categories', 'Categorías Evaluadas'
        DELIVERY_STRUCTURE = 'delivery_structure', 'Estructura de la Entrega'
        EXECUTIVE_SUMMARY = 'executive_summary', 'Resumen Ejecutivo'
        COST = 'cost', 'Costo y Formas de Pago'
        TIMELINE = 'timeline', 'Cronograma'
        SCOPE = 'scope', 'Alcance y Consideraciones'

    class Visibility(models.TextChoices):
        INITIAL = 'initial', 'Sólo envío inicial'
        FINAL = 'final', 'Sólo envío final'
        BOTH = 'both', 'Ambos envíos'

    diagnostic = models.ForeignKey(
        'WebAppDiagnostic',
        on_delete=models.CASCADE,
        related_name='sections',
    )
    section_type = models.CharField(max_length=30, choices=SectionType.choices)
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)
    content_json = models.JSONField(default=dict, blank=True)
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.BOTH,
    )

    class Meta:
        ordering = ['order']
        unique_together = ['diagnostic', 'section_type']
        verbose_name = 'Diagnostic Section'
        verbose_name_plural = 'Diagnostic Sections'

    def __str__(self):
        return f'{self.diagnostic.title} — {self.get_section_type_display()}'
