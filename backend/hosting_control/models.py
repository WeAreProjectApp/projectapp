"""Desired hosting presentation and independently acknowledged production targets."""
import hashlib

from django.conf import settings
from django.db import models


SUSPENSION_TITLE = 'Servicio suspendido'
SUSPENSION_TEXT = ('Comunícate con tu proveedor de hosting, mantenimiento y soporte '
                   'para gestionar la reactivación del servicio.')
BANNER_TITLE = 'Pago pendiente del servicio'
BANNER_TEXT = ('El servicio de hosting, mantenimiento y soporte tiene un pago pendiente. '
               'Por favor, comunícate con tu proveedor.')


class Control(models.Model):
    resource = models.OneToOneField('monitoring.Resource', on_delete=models.PROTECT, related_name='hosting_control')
    mode = models.CharField(max_length=12, default='normal', choices=[
        ('normal', 'Normal'), ('suspended', 'Pantalla de suspensión'), ('banner', 'Banner de aviso'),
    ])
    suspension_title = models.CharField(max_length=200, default=SUSPENSION_TITLE)
    suspension_text = models.TextField(max_length=2000, default=SUSPENSION_TEXT)
    banner_title = models.CharField(max_length=200, default=BANNER_TITLE)
    banner_text = models.TextField(max_length=2000, default=BANNER_TEXT)
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(mode__in=['normal', 'suspended', 'banner']), name='hosting_control_valid_mode')]


class Target(models.Model):
    control = models.ForeignKey(Control, on_delete=models.PROTECT, related_name='targets')
    key = models.SlugField(max_length=100, unique=True)
    origins = models.JSONField(default=list)
    lifecycle = models.CharField(max_length=12, default='active', choices=[('active', 'Activo'), ('suspended', 'Servicios suspendidos'), ('removed', 'Retirado')])
    adapter = models.CharField(max_length=40)
    acknowledged_version = models.PositiveIntegerField(null=True)
    acknowledged_digest = models.CharField(max_length=64, blank=True)
    acknowledged_payload = models.JSONField(default=dict)
    acknowledged_at = models.DateTimeField(null=True)
    last_seen_at = models.DateTimeField(null=True)
    last_error = models.CharField(max_length=300, blank=True)


class Event(models.Model):
    control = models.ForeignKey(Control, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    actor_name = models.CharField(max_length=150)
    source = models.CharField(max_length=100)
    before = models.JSONField()
    after = models.JSONField()
    version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']


class RuntimeCredential(models.Model):
    label = models.CharField(max_length=150)
    token_hash = models.CharField(max_length=64, unique=True)
    targets = models.ManyToManyField(Target)
    revoked_at = models.DateTimeField(null=True)

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode()).hexdigest()
