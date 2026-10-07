"""Durable activity notices; client conformity remains a separate record."""
import uuid

from django.conf import settings
from django.db import models

from accounts.retention import RetainedProjectModel


class DeliveryNotificationEvent(RetainedProjectModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        SENDING = 'sending', 'Enviando'
        SENT = 'sent', 'Enviado'
        FAILED = 'failed', 'Fallido'
        UNKNOWN = 'unknown', 'Resultado desconocido'
        CANCELLED = 'cancelled', 'Cancelado'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, null=True,
                                blank=True, related_name='delivery_notification_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name='delivery_notification_events')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               related_name='client_delivery_notification_events')
    operation_key = models.CharField(max_length=100)
    event_type = models.CharField(max_length=40)
    audience = models.CharField(max_length=10, choices=[('client', 'Cliente'), ('team', 'Equipo')])
    recipients = models.JSONField(default=list)
    from_email = models.CharField(max_length=320)
    subject = models.CharField(max_length=500)
    text_body = models.TextField()
    html_body = models.TextField()
    public_context = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    version = models.PositiveIntegerField(default=1)
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        constraints = (models.UniqueConstraint(fields=['project', 'operation_key'],
                                               name='delivery_notice_operation_unique'),)
        indexes = (models.Index(fields=['project', 'created_at']),
                   models.Index(fields=['status', 'created_at']))


class DeliveryNotificationAttempt(models.Model):
    event = models.ForeignKey(DeliveryNotificationEvent, on_delete=models.CASCADE, related_name='attempts')
    request_id = models.CharField(max_length=100)
    preview_sha256 = models.CharField(max_length=64, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name='delivery_notification_attempts')
    credential = models.ForeignKey('content.McpCredential', on_delete=models.PROTECT,
                                   null=True, blank=True, related_name='delivery_notice_attempts')
    status = models.CharField(max_length=12, choices=DeliveryNotificationEvent.Status.choices,
                              default=DeliveryNotificationEvent.Status.PENDING)
    gateway_snapshot = models.ForeignKey('content.EmailDeliverySnapshot', on_delete=models.PROTECT,
                                         null=True, blank=True, related_name='delivery_notice_attempts')
    error_code = models.CharField(max_length=80, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
        constraints = (models.UniqueConstraint(fields=['event', 'request_id'],
                                               name='delivery_notice_attempt_unique'),)
