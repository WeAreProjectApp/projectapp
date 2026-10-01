"""Immutable evidence and durable delivery attempts for closure emails.

The preparation is the legal/audit record created before an administrator can
send an approved delivery-stage closure notice.  Attempts are deliberately
separate: SMTP is an external side effect and its transient state must not
rewrite the prepared client-facing evidence.
"""
import uuid

from django.conf import settings
from django.db import models

from content.storage import get_private_storage


class ImmutableDeliveryEvidenceQuerySet(models.QuerySet):
    """Prevent bulk mutation of captured closure-email evidence."""

    def update(self, **kwargs):
        raise ValueError('La evidencia de cierre por correo no se puede modificar.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError('La evidencia de cierre por correo no se puede modificar.')


class ImmutableDeliveryEvidence(models.Model):
    """Insert-only base for a prepared closure email and its exact files."""

    objects = ImmutableDeliveryEvidenceQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('La evidencia de cierre por correo no se puede modificar.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('La evidencia de cierre por correo no se puede eliminar.')


class DeliveryEvidenceEmail(ImmutableDeliveryEvidence):
    """The rendered, reviewed closure notice captured before any SMTP call."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'accounts.Project', on_delete=models.PROTECT,
        related_name='delivery_closure_emails',
    )
    stage = models.ForeignKey(
        'accounts.DeliveryStage', on_delete=models.PROTECT,
        related_name='closure_emails',
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='prepared_delivery_closure_emails',
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='delivery_closure_emails',
    )
    mcp_credential = models.ForeignKey(
        'content.McpCredential', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='prepared_delivery_closure_emails',
    )
    to_recipients = models.JSONField(default=list)
    from_email = models.CharField(max_length=320)
    subject = models.CharField(max_length=500)
    html_body = models.TextField()
    text_body = models.TextField()
    # Deliberately safe metadata only: identity/version trail and public
    # attachment manifest, never prompt sources or private conversation data.
    snapshot_payload = models.JSONField(default=dict)
    closure_history = models.JSONField(default=dict)
    captured_version = models.PositiveIntegerField()
    request_id = models.CharField(max_length=100)
    manifest_sha256 = models.CharField(max_length=64)
    resend_of = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='resend_preparations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'request_id'],
                name='delivery_closure_email_request_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['stage', 'created_at']),
            models.Index(fields=['client', 'created_at']),
        ]


class DeliveryEvidenceEmailFile(ImmutableDeliveryEvidence):
    """Exact private bytes included with one immutable closure-email draft."""

    email = models.ForeignKey(
        'accounts.DeliveryEvidenceEmail', on_delete=models.PROTECT,
        related_name='attachments',
    )
    delivery_snapshot = models.ForeignKey(
        'accounts.DeliveryDocumentSnapshot', on_delete=models.PROTECT,
        null=True, blank=True, related_name='closure_email_files',
    )
    file = models.FileField(
        storage=get_private_storage,
        upload_to='delivery/closure-emails/%Y/%m/', max_length=500,
    )
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=255, default='application/octet-stream')
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['email', 'position'],
                name='delivery_closure_email_file_position_unique',
            ),
        ]


class DeliveryEvidenceEmailAttempt(models.Model):
    """Mutable external-send receipt for one prepared closure email."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        SENDING = 'sending', 'Enviando'
        SENT = 'sent', 'Enviado'
        FAILED = 'failed', 'Fallido'
        UNKNOWN = 'unknown', 'Desconocido'

    email = models.ForeignKey(
        'accounts.DeliveryEvidenceEmail', on_delete=models.PROTECT,
        related_name='attempts',
    )
    request_id = models.CharField(max_length=100)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='delivery_closure_email_attempts',
    )
    mcp_credential = models.ForeignKey(
        'content.McpCredential', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivery_closure_email_attempts',
    )
    gateway_snapshot = models.ForeignKey(
        'content.EmailDeliverySnapshot', on_delete=models.PROTECT,
        null=True, blank=True, related_name='delivery_closure_email_attempts',
    )
    email_log = models.ForeignKey(
        'content.EmailLog', on_delete=models.PROTECT,
        null=True, blank=True, related_name='delivery_closure_email_attempts',
    )
    resend_of = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='retries',
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING,
    )
    error_message = models.TextField(blank=True, default='')
    claimed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['email', 'request_id'],
                name='delivery_closure_email_attempt_request_unique',
            ),
        ]
        indexes = [models.Index(fields=['email', 'status'])]
