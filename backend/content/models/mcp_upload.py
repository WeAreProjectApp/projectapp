import uuid

from django.db import models

from content.video_upload_storage import McpUploadStorage


def mcp_upload_path(instance, filename):
    prefix = 'mcp-video-uploads' if instance.content_type == 'video/mp4' else 'mcp-uploads'
    return f'{prefix}/{instance.connector.slug}/{instance.id}/{filename}'


class McpUpload(models.Model):
    """Temporary, integrity-checked binary upload owned by one credential."""

    STATUS_PENDING = 'pending'
    STATUS_COMPLETE = 'complete'
    STATUS_CONSUMED = 'consumed'
    STATUS_ABORTED = 'aborted'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_CONSUMED, 'Consumed'),
        (STATUS_ABORTED, 'Aborted'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(
        'content.McpConnector',
        on_delete=models.CASCADE,
        related_name='uploads',
    )
    credential = models.ForeignKey(
        'content.McpCredential',
        on_delete=models.CASCADE,
        related_name='uploads',
    )
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    expected_size = models.PositiveBigIntegerField()
    expected_sha256 = models.CharField(max_length=64)
    received_size = models.PositiveBigIntegerField(default=0)
    next_chunk_index = models.PositiveIntegerField(default=0)
    file = models.FileField(upload_to=mcp_upload_path, storage=McpUploadStorage(), blank=True)
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.connector.slug}:{self.filename}:{self.status}'
