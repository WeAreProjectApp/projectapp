import hashlib
import uuid
from pathlib import Path

from django.db import models
from django.db.models.fields.files import FieldFile
from django.utils.text import get_valid_filename

from content.storage import get_private_storage


PRIVATE_ATTACHMENT_PREFIX = 'private-email-history/'


class EmailAttachmentFieldFile(FieldFile):
    """Resolve retained private files without relocating historical media."""

    def __init__(self, instance, field, name):
        super().__init__(instance, field, name)
        if str(name or '').startswith(PRIVATE_ATTACHMENT_PREFIX):
            self.storage = get_private_storage()


def email_attachment_upload_to(instance, filename):
    """Keep immutable mail evidence outside user-controlled media paths."""
    safe_name = get_valid_filename(Path(filename or 'adjunto').name) or 'adjunto'
    prefix = (
        PRIVATE_ATTACHMENT_PREFIX
        if getattr(instance, '_private_attachments', False) else 'email-history/'
    )
    return (
        f'{prefix}{instance.snapshot.delivery_id}/'
        f'{uuid.uuid4().hex}-{safe_name}'
    )


class EmailDeliverySnapshot(models.Model):
    """Immutable evidence captured before one outbound SMTP attempt."""

    class Classification(models.TextChoices):
        CLIENT = 'client', 'Al cliente'
        INTERNAL = 'internal', 'Interno'
        SECURITY = 'security', 'Seguridad'

    delivery_id = models.UUIDField(unique=True, db_index=True)
    template_key = models.CharField(max_length=100)
    classification = models.CharField(
        max_length=10,
        choices=Classification.choices,
    )
    family = models.CharField(max_length=40, blank=True, default='')
    subject = models.CharField(max_length=500, blank=True, default='')
    from_email = models.CharField(max_length=320, blank=True, default='')
    to_recipients = models.JSONField(default=list, blank=True)
    cc_recipients = models.JSONField(default=list, blank=True)
    body = models.OneToOneField(
        'EmailBody',
        on_delete=models.PROTECT,
        related_name='delivery_snapshot',
    )
    message_size_bytes = models.PositiveBigIntegerField(default=0)
    attachment_size_bytes = models.PositiveBigIntegerField(default=0)
    attachment_count = models.PositiveIntegerField(default=0)
    resend_of = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='resends',
    )
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-captured_at', '-id']
        indexes = [
            models.Index(fields=['template_key', 'captured_at']),
            models.Index(fields=['family', 'captured_at']),
        ]

    def __str__(self):
        return f'{self.template_key} snapshot {self.delivery_id}'


class EmailAttachmentSnapshot(models.Model):
    """Exact bytes and recognition metadata for one sent attachment."""

    class FormatKind(models.TextChoices):
        PDF = 'pdf', 'PDF'
        WORD = 'word', 'Word'
        SPREADSHEET = 'spreadsheet', 'Excel / hoja de cálculo'
        IMAGE = 'image', 'Imagen'
        OTHER = 'other', 'Otro formato'

    snapshot = models.ForeignKey(
        EmailDeliverySnapshot,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to=email_attachment_upload_to, max_length=500)
    # Runtime-only routing keeps the concrete FileField and its migrations intact.
    file.attr_class = EmailAttachmentFieldFile
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(
        max_length=255,
        blank=True,
        default='application/octet-stream',
    )
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    position = models.PositiveIntegerField(default=0)
    format_kind = models.CharField(
        max_length=20,
        choices=FormatKind.choices,
        default=FormatKind.OTHER,
    )
    business_kind = models.CharField(max_length=64, blank=True, default='')
    business_kind_label = models.CharField(
        max_length=128,
        blank=True,
        default='',
    )
    source_document = models.ForeignKey(
        'Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_attachment_snapshots',
    )
    source_document_type_code = models.CharField(
        max_length=64,
        blank=True,
        default='',
    )
    source_document_type_name = models.CharField(
        max_length=128,
        blank=True,
        default='',
    )

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['snapshot', 'position'],
                name='uniq_email_attachment_position',
            ),
        ]
        indexes = [
            models.Index(fields=['format_kind']),
            models.Index(fields=['business_kind']),
        ]

    def __str__(self):
        return f'{self.filename} ({self.size_bytes} bytes)'


class EmailLinkSnapshot(models.Model):
    """A user-facing HTTP(S) link contained in the sent body."""

    class Group(models.TextChoices):
        CONTENT = 'content', 'Contenido'
        TEMPLATE = 'template', 'Plantilla o firma'

    snapshot = models.ForeignKey(
        EmailDeliverySnapshot,
        on_delete=models.CASCADE,
        related_name='links',
    )
    url = models.URLField(max_length=2048)
    url_sha256 = models.CharField(max_length=64, editable=False)
    label = models.CharField(max_length=500, blank=True, default='')
    group = models.CharField(
        max_length=10,
        choices=Group.choices,
        default=Group.CONTENT,
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['snapshot', 'url_sha256'],
                name='uniq_email_snapshot_link_hash',
            ),
        ]

    def save(self, *args, **kwargs):
        self.url_sha256 = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'url_sha256'}
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.url
