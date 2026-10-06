from accounts.retention import RetainedProjectModel
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from content.models.history_tracked import HistoryTrackedModel

from content.utils import safe_slug


def normalize_document_state_name(value):
    """Return the accent/case-insensitive key used to prevent duplicates."""
    normalized = unicodedata.normalize('NFKD', str(value or '').strip())
    without_accents = ''.join(
        character for character in normalized
        if not unicodedata.combining(character)
    )
    return ' '.join(without_accents.casefold().split())


class DocumentStateGroup(models.Model):
    """A configurable state group shared by document and project catalogs."""

    class Catalog(models.TextChoices):
        DOCUMENTS = 'documents', 'Documentos'
        PROJECTS = 'projects', 'Proyectos'

    class SelectionMode(models.TextChoices):
        EXCLUSIVE = 'exclusive', 'Uno activo'
        ADDITIVE = 'additive', 'Varios activos'

    catalog = models.CharField(
        max_length=16,
        choices=Catalog.choices,
        default=Catalog.DOCUMENTS,
        db_index=True,
    )
    name = models.CharField(max_length=80)
    selection_mode = models.CharField(
        max_length=12,
        choices=SelectionMode.choices,
        default=SelectionMode.ADDITIVE,
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('order', 'name')
        constraints = [
            models.UniqueConstraint(
                fields=('catalog', 'name'),
                name='unique_state_group_name_per_catalog',
            ),
        ]

    def __str__(self):
        return self.name


class DocumentState(models.Model):
    """User-managed document state definition.

    ``system_key`` keeps integrations stable while users remain free to rename
    seeded states. States are retired/merged instead of deleted so episodes
    always retain their original meaning.
    """

    class Color(models.TextChoices):
        GRAY = 'gray', 'Gris'
        EMERALD = 'emerald', 'Verde'
        BLUE = 'blue', 'Azul'
        YELLOW = 'yellow', 'Amarillo'
        ORANGE = 'orange', 'Naranja'
        RED = 'red', 'Rojo'
        PURPLE = 'purple', 'Morado'

    class OperationalEffect(models.TextChoices):
        NONE = '', 'Sin efecto automático'
        DEVELOPMENT = 'development', 'En desarrollo'
        OPERATING = 'operating', 'Operativo'
        SUSPENDED = 'suspended', 'Cobros suspendidos'
        COMPLETED = 'completed', 'Cierre correcto'
        DECOMMISSIONED = 'decommissioned', 'Baja definitiva'

    OPERATIONAL_EFFECT_HELP = {
        OperationalEffect.NONE: (
            'Este estado no cambia por sí solo los cobros, los avisos ni el '
            'cierre del proyecto.'
        ),
        OperationalEffect.DEVELOPMENT: (
            'Permite los cobros y avisos que correspondan mientras el proyecto '
            'se construye; todavía no representa una entrega operativa.'
        ),
        OperationalEffect.OPERATING: (
            'Mantiene habilitados la operación, los cobros y los avisos del '
            'proyecto.'
        ),
        OperationalEffect.SUSPENDED: (
            'Detiene nuevos cobros y avisos, conserva la deuda ya causada y '
            'permite reactivar el proyecto.'
        ),
        OperationalEffect.COMPLETED: (
            'Exige un cierre financiero limpio, desactiva los hostings y '
            'detiene los cobros futuros.'
        ),
        OperationalEffect.DECOMMISSIONED: (
            'Es definitivo: cancela el servicio y los cobros futuros y exige '
            'decidir qué hacer con cada saldo pendiente.'
        ),
    }

    catalog = models.CharField(
        max_length=16,
        choices=DocumentStateGroup.Catalog.choices,
        default=DocumentStateGroup.Catalog.DOCUMENTS,
        db_index=True,
    )
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=300, blank=True, default='')
    normalized_name = models.CharField(max_length=80, editable=False)
    slug = models.SlugField(max_length=80, blank=True)
    color = models.CharField(
        max_length=16,
        choices=Color.choices,
        default=Color.GRAY,
    )
    group = models.ForeignKey(
        DocumentStateGroup,
        on_delete=models.PROTECT,
        related_name='states',
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    system_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text='Stable key for seeded integrations; names remain editable.',
    )
    operational_effect = models.CharField(
        max_length=20,
        choices=OperationalEffect.choices,
        blank=True,
        default=OperationalEffect.NONE,
        help_text='Project-side consequence policy; blank for document states.',
    )
    show_in_document_manager = models.BooleanField(
        default=False,
        help_text=(
            'Whether projects in this state appear in the default Documents '
            'project-folder list. Ignored for document states.'
        ),
    )
    merged_into = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merged_sources',
    )
    incompatibilities = models.ManyToManyField(
        'self',
        symmetrical=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('group__order', 'order', 'name')
        constraints = [
            models.UniqueConstraint(
                fields=('catalog', 'normalized_name'),
                name='unique_state_name_per_catalog',
            ),
            models.UniqueConstraint(
                fields=('catalog', 'slug'),
                name='unique_state_slug_per_catalog',
            ),
            models.UniqueConstraint(
                fields=('catalog', 'system_key'),
                name='unique_state_system_key_per_catalog',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def operational_effect_help(self):
        """Return the immutable business consequences behind an editable state."""
        if self.catalog != DocumentStateGroup.Catalog.PROJECTS:
            return ''
        return self.OPERATIONAL_EFFECT_HELP.get(
            self.operational_effect,
            self.OPERATIONAL_EFFECT_HELP[self.OperationalEffect.NONE],
        )

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.strip().split())
        self.description = ' '.join(self.description.strip().split())
        self.normalized_name = normalize_document_state_name(self.name)
        if self.group_id:
            self.catalog = self.group.catalog
        if not self.slug:
            base = safe_slug(self.name, 'estado')
            slug = base
            index = 2
            while DocumentState.objects.filter(
                catalog=self.catalog, slug=slug,
            ).exclude(pk=self.pk).exists():
                slug = f'{base}-{index}'
                index += 1
            self.slug = slug
        super().save(*args, **kwargs)


class DocumentStateEpisode(RetainedProjectModel, HistoryTrackedModel):
    """One state occurrence for exactly one document or project."""

    class Outcome(models.TextChoices):
        COMPLETED = 'completed', 'Cerrado'
        REMOVED = 'removed', 'Quitado'
        TRANSITIONED = 'transitioned', 'Transicionado'
        MERGED = 'merged', 'Fusionado'

    class Origin(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        NOTE = 'note', 'Nota'
        EMAIL = 'email', 'Correo'
        MIGRATION = 'migration', 'Migración'
        MCP = 'mcp', 'MCP'

    document = models.ForeignKey(
        'content.Document',
        on_delete=models.CASCADE,
        related_name='state_episodes',
        null=True,
        blank=True,
    )
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='state_episodes', null=True, blank=True)
    state = models.ForeignKey(
        DocumentState,
        on_delete=models.PROTECT,
        related_name='episodes',
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    outcome = models.CharField(
        max_length=16,
        choices=Outcome.choices,
        blank=True,
        default='',
    )
    close_note = models.CharField(max_length=500, blank=True, default='')
    origin = models.CharField(
        max_length=16,
        choices=Origin.choices,
        default=Origin.MANUAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('document', 'closed_at')),
            models.Index(fields=('project', 'closed_at')),
            models.Index(fields=('state', 'closed_at')),
        ]
        constraints = [
            # Un episodio representa a UN sujeto: documento o proyecto, nunca
            # los dos. La otra mitad ("al menos uno") no puede vivir acá: al
            # borrar el sujeto, Django anula la FK nullable antes de borrar la
            # fila (deletion.CASCADE) y MySQL no difiere los CHECK, así que ese
            # transitorio hacía imposible borrar el sujeto. La garantizan
            # clean() y save().
            models.CheckConstraint(
                condition=(
                    models.Q(document__isnull=True)
                    | models.Q(project__isnull=True)
                ),
                name='state_episode_subject_is_document_or_project',
            ),
        ]

    def clean(self):
        errors = {}
        if self.document_id is None and self.project_id is None and self.retention_context_id is None:
            errors['document'] = (
                'El episodio debe pertenecer a un documento o a un proyecto.'
            )
        if self.document_id and self.project_id:
            errors['project'] = (
                'El episodio no puede pertenecer a un documento y a un '
                'proyecto a la vez.'
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # El borrado de Django no pasa por acá — usa UpdateQuery/DeleteQuery —
        # así que esta guarda cubre el "al menos un sujeto" en todo write de la
        # aplicación sin bloquear el transitorio legítimo del collector.
        self.clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.document or self.project} — {self.state}'


class DocumentStateEpisodeEvent(models.Model):
    """Append-only audit event for an episode."""

    class EventType(models.TextChoices):
        OPENED = 'opened', 'Abierto'
        CLOSED = 'closed', 'Cerrado'
        REMOVED = 'removed', 'Quitado'
        TRANSITIONED = 'transitioned', 'Transicionado'
        MERGED = 'merged', 'Fusionado'
        OPENED_AT_CORRECTED = (
            'opened_at_corrected',
            'Fecha de apertura corregida',
        )

    episode = models.ForeignKey(
        DocumentStateEpisode,
        on_delete=models.CASCADE,
        related_name='events',
    )
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    effective_at = models.DateTimeField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('-recorded_at', '-id')
        indexes = [models.Index(fields=('episode', 'recorded_at'))]

    def __str__(self):
        return f'{self.episode_id} — {self.event_type}'
