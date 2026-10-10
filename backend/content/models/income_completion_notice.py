from django.db import models


class IncomeCompletionNotice(models.Model):
    """One durable internal notice per income, independent of its payments."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        PROCESSING = 'processing', 'Enviando'
        SENT = 'sent', 'Enviado'
        FAILED = 'failed', 'Fallido'
        SKIPPED = 'skipped', 'Omitido'

    income = models.OneToOneField(
        'IncomeRecord', on_delete=models.SET_NULL, null=True,
        related_name='completion_notice',
    )
    values = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'created_at'], name='income_notice_pending_idx')]
