"""Versioned calculator definitions, project agreements and measured deliveries."""
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CalculatorRevision(models.Model):
    definition = models.JSONField()
    digest = models.CharField(max_length=64)
    note = models.CharField(max_length=2000)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ['-pk']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Las revisiones de la calculadora son inmutables.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Las revisiones de la calculadora se conservan.')


class RequirementCalculator(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    current_revision = models.ForeignKey(CalculatorRevision, on_delete=models.PROTECT, related_name='+')
    document = models.OneToOneField('content.Document', on_delete=models.PROTECT, related_name='calculator_definition')

    class Meta:
        constraints: ClassVar[list] = [models.CheckConstraint(condition=models.Q(id=1), name='requirement_calculator_singleton')]


class ProjectCalculatorVersion(models.Model):
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='calculator_versions')
    base_revision = models.ForeignKey(CalculatorRevision, on_delete=models.PROTECT)
    document = models.OneToOneField('content.Document', on_delete=models.PROTECT, related_name='project_calculator_version')
    definition = models.JSONField()
    status = models.CharField(max_length=8, choices=[('draft', 'Borrador'), ('approved', 'Aprobada')], default='draft')
    digest = models.CharField(max_length=64)
    note = models.CharField(max_length=2000)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    approved_at = models.DateTimeField(null=True, blank=True)
    pdf_content = models.BinaryField(default=bytes, editable=False)
    pdf_digest = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering: ClassVar[list[str]] = ['-pk']

    def save(self, *args, **kwargs):
        if not self._state.adding and type(self).objects.filter(pk=self.pk, status='approved').exists():
            raise ValidationError('La calculadora aprobada está congelada. Crea otro borrador.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Las versiones particulares de la calculadora se conservan.')


class CalculatorEstimate(models.Model):
    revision = models.ForeignKey(CalculatorRevision, on_delete=models.PROTECT)
    project_version = models.ForeignKey(ProjectCalculatorVersion, null=True, blank=True, on_delete=models.PROTECT)
    project = models.ForeignKey('accounts.Project', null=True, blank=True, on_delete=models.PROTECT, related_name='calculator_estimates')
    request_id = models.UUIDField(unique=True)
    requirement = models.TextField()
    size = models.CharField(max_length=7)
    signal_ids = models.JSONField(default=list)
    explanation = models.TextField()
    expected_size = models.CharField(max_length=7, blank=True)
    snapshot = models.JSONField()
    definition_digest = models.CharField(max_length=64, db_index=True, default='')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ['-pk']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Las estimaciones se conservan con la definición utilizada.')
        return super().save(*args, **kwargs)


class CalculatorActual(models.Model):
    estimate = models.ForeignKey(CalculatorEstimate, on_delete=models.PROTECT, related_name='actuals')
    supersedes = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='correction')
    actual_hours = models.DecimalField(max_digits=12, decimal_places=2)
    hourly_cost_cop = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    evidence = models.TextField()
    cause = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ['-pk']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Corrige un cierre mediante otro evento, sin sobrescribirlo.')
        return super().save(*args, **kwargs)


class ProjectCalculatorChange(models.Model):
    version = models.ForeignKey(ProjectCalculatorVersion, on_delete=models.PROTECT, related_name='changes')
    definition = models.JSONField()
    digest = models.CharField(max_length=64)
    status = models.CharField(max_length=8)
    note = models.CharField(max_length=2000)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ['-pk']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Los ajustes de la calculadora se conservan como eventos.')
        return super().save(*args, **kwargs)
