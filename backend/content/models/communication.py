from accounts.retention import RetainedProjectModel
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class CommunicationThread(RetainedProjectModel, models.Model):
    """A client conversation that can span several ordered messages."""

    class Status(models.TextChoices):
        OPEN = 'open', 'Abierto'
        CLOSED = 'closed', 'Cerrado'

    client = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.PROTECT,
        related_name='communication_threads',
        limit_choices_to={'role': 'client'},
    )
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='communication_threads', null=True, blank=True)
    folder = models.ForeignKey(
        'content.CommunicationFolder', null=True, blank=True,
        on_delete=models.PROTECT, related_name='threads',
    )
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='communication_threads_created',
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='communication_threads_updated',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Comunicación madre. Mismo reparto de conceptos que en el gestor documental:
    # `client`/`project` son la asociación de CUALQUIER hilo; estos dos marcan el
    # único hilo que representa a esa entidad en el módulo.
    #
    # `managed_client` apunta a UserProfile —y no a auth.User como su gemelo de
    # carpetas— por la misma razón que allá apunta a auth.User: coincidir con la
    # columna hermana (`client`), que es lo que hace posible la CheckConstraint
    # `client = F('managed_client')`.
    managed_project = models.OneToOneField('accounts.Project', on_delete=models.PROTECT, null=True, blank=True, related_name='communication_root_thread')
    managed_client = models.OneToOneField(
        'accounts.UserProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_communication_root_thread',
    )

    # Archivado: eje de VISIBILIDAD, ortogonal a `status`. Cerrar un hilo bloquea
    # su escritura y sigue mostrándolo; archivarlo lo saca de la vista sin decir
    # nada sobre la conversación.
    #
    # Sin `archived_via_*`: ese campo existe en carpetas sólo para poder revertir
    # una cascada, y acá los hilos son planos — no arrastran nada al archivarse.
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_activity_at', '-id']
        indexes = [
            models.Index(
                fields=['client', 'status', 'last_activity_at'],
                name='commthread_client_status_at',
            ),
            models.Index(
                fields=['project', 'status', 'last_activity_at'],
                name='commthread_project_status_at',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(managed_project__isnull=True)
                    | models.Q(project=models.F('managed_project'))
                ),
                name='managed_thread_matches_project',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(managed_client__isnull=True)
                    | models.Q(client=models.F('managed_client'))
                ),
                name='managed_thread_matches_client',
            ),
            # La madre es el punto de entrada de su entidad: si pudiera
            # archivarse, el proyecto o el cliente quedaría sin cabecera.
            models.CheckConstraint(
                condition=(
                    models.Q(managed_project__isnull=True)
                    & models.Q(managed_client__isnull=True)
                    | models.Q(is_archived=False)
                ),
                name='managed_thread_is_active',
            ),
            # Un hilo representa UNA entidad. Ser la madre del proyecto y la del
            # cliente a la vez haría ambigua la fila que el panel fija arriba.
            models.CheckConstraint(
                condition=(
                    models.Q(managed_client__isnull=True)
                    | models.Q(managed_project__isnull=True)
                ),
                name='managed_thread_is_project_or_client',
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def thread_kind(self):
        """Espejo literal de `DocumentFolder.folder_kind`."""
        if self.managed_project_id:
            return 'project'
        if self.managed_client_id:
            return 'client'
        return 'manual'

    def clean(self):
        errors = {}
        if self.client_id and self.client.role != self.client.ROLE_CLIENT:
            errors['client'] = 'El perfil seleccionado no es un cliente.'
        if (
            self.client_id
            and self.project_id
            and self.project.client_id != self.client.user_id
        ):
            errors['project'] = 'El proyecto no pertenece al cliente del hilo.'
        if errors:
            raise ValidationError(errors)


class CommunicationMessage(models.Model):
    """One immutable-after-delivery entry in a client conversation."""

    class Channel(models.TextChoices):
        EMAIL = 'email', 'Correo'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    class Direction(models.TextChoices):
        OUTGOING = 'outgoing', 'Saliente'
        INCOMING = 'incoming', 'Entrante'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        SENT = 'sent', 'Enviado'
        RECEIVED = 'received', 'Recibido'
        FAILED = 'failed', 'Fallido'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Registro manual'
        PLATFORM_EMAIL = 'platform_email', 'Correo enviado por la plataforma'
        LEGACY_EMAIL = 'legacy_email', 'Correo histórico importado'

    thread = models.ForeignKey(
        CommunicationThread,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    channel = models.CharField(max_length=12, choices=Channel.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    subject = models.CharField(max_length=500, blank=True, default='')
    content = models.TextField()
    occurred_at = models.DateTimeField(db_index=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='replies',
        null=True,
        blank=True,
    )
    email_log = models.OneToOneField(
        'content.EmailLog',
        on_delete=models.SET_NULL,
        related_name='communication_message',
        null=True,
        blank=True,
    )
    documents = models.ManyToManyField(
        'content.Document',
        through='content.CommunicationAttachment',
        related_name='communication_messages',
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='communication_messages_created',
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='communication_messages_updated',
        null=True,
        blank=True,
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True, default='')
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='communication_messages_voided',
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['occurred_at', 'id']
        indexes = [
            models.Index(
                fields=['thread', 'occurred_at'],
                name='commmessage_thread_at',
            ),
            models.Index(
                fields=['channel', 'direction', 'status'],
                name='commmessage_route_status',
            ),
        ]

    def __str__(self):
        return f'{self.get_direction_display()} · {self.get_channel_display()}'


class CommunicationAttachment(models.Model):
    """Reference an existing Document without copying its file or content."""

    message = models.ForeignKey(
        CommunicationMessage,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    document = models.ForeignKey(
        'content.Document',
        on_delete=models.PROTECT,
        related_name='communication_attachments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'document'],
                name='unique_communication_document',
            ),
        ]

    def __str__(self):
        return f'{self.message_id} → {self.document_id}'


class CommunicationMessageRevision(models.Model):
    """Append-only audit trail for successful draft edits."""

    message = models.ForeignKey(
        CommunicationMessage,
        on_delete=models.CASCADE,
        related_name='revisions',
    )
    changes = models.JSONField(default=list)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='communication_message_revisions',
        null=True,
        blank=True,
    )
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-edited_at', '-id']
        indexes = [
            models.Index(
                fields=['message', 'edited_at'],
                name='commrevision_message_at',
            ),
        ]

    def __str__(self):
        return f'Revisión de borrador #{self.message_id}'


class CommunicationMessageDateCorrection(models.Model):
    """Append-only audit trail for corrections to a message's business date."""

    message = models.ForeignKey(
        CommunicationMessage,
        on_delete=models.CASCADE,
        related_name='date_corrections',
    )
    previous_occurred_at = models.DateTimeField()
    corrected_occurred_at = models.DateTimeField()
    reason = models.TextField()
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='communication_date_corrections',
        null=True,
        blank=True,
    )
    corrected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-corrected_at', '-id']

    def __str__(self):
        return f'Corrección de fecha #{self.message_id}'
