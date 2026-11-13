"""Project-owned package purchases and explicit, auditable client consent."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PackageRecord(models.Model):
    """Financial and consent records survive project lifecycle operations."""

    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='+')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class PackageExampleRevision(models.Model):
    project = models.ForeignKey('accounts.Project', null=True, blank=True, on_delete=models.PROTECT, related_name='package_example_revisions')
    language = models.CharField(max_length=2, choices=[('es', 'Español'), ('en', 'English')])
    examples = models.JSONField(default=dict)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    note = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Publica otra revisión de ejemplos; no sobrescribas el historial.')
        return super().save(*args, **kwargs)


class PackageProjectSettings(models.Model):
    project = models.OneToOneField('accounts.Project', on_delete=models.PROTECT, related_name='package_settings')
    nationality = models.CharField(max_length=3, choices=[('COL', 'Colombia'), ('EXT', 'Extranjeros'), ('USA', 'Estados Unidos')], default='COL')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    version = models.PositiveIntegerField(default=0)


class PackageOrder(PackageRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey('content.HourPackage', on_delete=models.PROTECT, related_name='+')
    snapshot = models.JSONField()
    currency = models.CharField(max_length=3)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=8, choices=[('online', 'En línea'), ('external', 'Externo')])
    status = models.CharField(max_length=12, default='pending', choices=[('pending', 'Pendiente'), ('processing', 'En proceso'), ('paid', 'Pagada'), ('failed', 'Fallida'), ('cancelled', 'Anulada')])
    payment_reference = models.CharField(max_length=200, blank=True)
    payment_link_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    checkout_url = models.URLField(max_length=500, blank=True)
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')

    class Meta:
        ordering = ['-created_at', '-pk']


class PackageRequest(PackageRecord):
    ticket = models.OneToOneField('accounts.ChangeRequest', on_delete=models.PROTECT, related_name='package_request')
    status = models.CharField(max_length=16, default='pending', choices=[('pending', 'Pendiente de evaluación'), ('evaluating', 'En evaluación'), ('offered', 'Pendiente de aceptación'), ('objected', 'Con objeciones'), ('accepted', 'Aceptada'), ('cancelled', 'Anulada')])
    version = models.PositiveIntegerField(default=0)
    current_proposal = models.ForeignKey('accounts.PackageSizingProposal', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class PackageSizingProposal(models.Model):
    request = models.ForeignKey(PackageRequest, on_delete=models.PROTECT, related_name='proposals')
    estimate = models.ForeignKey('content.CalculatorEstimate', on_delete=models.PROTECT, related_name='+')
    public_snapshot = models.JSONField()
    warranty = models.BooleanField(default=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']


class PackageDecision(models.Model):
    proposal = models.OneToOneField(PackageSizingProposal, on_delete=models.PROTECT, related_name='decision')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    decision = models.CharField(max_length=8, choices=[('accept', 'Aceptar'), ('object', 'Objetar')])
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PackageMovement(models.Model):
    order = models.ForeignKey(PackageOrder, on_delete=models.PROTECT, related_name='movements')
    size = models.CharField(max_length=2, choices=[('XS', 'XS'), ('S', 'S'), ('M', 'M')])
    quantity = models.IntegerField()
    kind = models.CharField(max_length=8, choices=[('credit', 'Compra'), ('debit', 'Consumo'), ('reversal', 'Reversión')])
    decision = models.OneToOneField(PackageDecision, null=True, blank=True, on_delete=models.PROTECT, related_name='movement')
    reverses = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='reversal')
    reason = models.CharField(max_length=2000, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']
        constraints = [models.CheckConstraint(condition=(models.Q(kind='debit', quantity=-1) | models.Q(kind__in=['credit', 'reversal'], quantity__gt=0)), name='package_movement_direction')]


class PackageOperation(models.Model):
    project = models.ForeignKey('accounts.Project', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    request_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    receipt = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'request_id'], name='package_operation_retry')]
