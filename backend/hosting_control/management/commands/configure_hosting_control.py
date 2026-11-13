"""Explicit provisioning only: no automatic activation, secret output or service operations."""
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from monitoring.models import Resource
from hosting_control.models import Control, RuntimeCredential, Target


class TargetInput(serializers.Serializer):
    key = serializers.SlugField(max_length=100)
    name = serializers.CharField(max_length=160)
    server = serializers.SlugField(max_length=100)
    server_key = serializers.SlugField(max_length=100, required=False)
    lifecycle = serializers.ChoiceField(choices=['active', 'suspended', 'removed'])
    adapter = serializers.CharField(max_length=40)
    origins = serializers.ListField(child=serializers.URLField(), allow_empty=False)

    def validate_origins(self, values):
        for value in values:
            url = urlsplit(value)
            if url.scheme != 'https' or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment:
                raise serializers.ValidationError('Usa orígenes HTTPS sin rutas ni credenciales.')
        return list(dict.fromkeys(value.rstrip('/') for value in values))


class Command(BaseCommand):
    help = 'Importar el inventario de producción o emitir/revocar credenciales sin imprimir secretos.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', type=Path)
        parser.add_argument('--issue', help='Etiqueta del receptor.')
        parser.add_argument('--targets', nargs='+')
        parser.add_argument('--token-file', type=Path)
        parser.add_argument('--revoke', type=int)

    @transaction.atomic
    def handle(self, *args, **options):
        if options['revoke'] is not None:
            if not RuntimeCredential.objects.filter(pk=options['revoke']).update(revoked_at=timezone.now()):
                raise CommandError('Credencial desconocida.')
            self.stdout.write('Credencial revocada.')
            return
        if options['manifest']:
            try:
                data = json.loads(options['manifest'].read_text())
                serializer = TargetInput(data=data['targets'], many=True)
                serializer.is_valid(raise_exception=True)
                rows = serializer.validated_data
                if len({row['key'] for row in rows}) != len(rows):
                    raise ValueError()
            except (OSError, ValueError, KeyError, TypeError, serializers.ValidationError):
                raise CommandError('Manifiesto de producción inválido.') from None
            for row in rows:
                server, _ = Resource.objects.get_or_create(key=row.get('server_key', row['server']), defaults={'name': row['server'], 'kind': 'server'})
                resource, _ = Resource.objects.get_or_create(key=row['key'], defaults={
                    'name': row['name'], 'kind': 'project', 'environment': 'production', 'server': server,
                })
                if resource.kind != 'project' or resource.environment != 'production' or resource.server_id != server.pk or server.kind != 'server':
                    raise CommandError('Identidad existente incompatible; revisar la coordenada del proyecto.')
                control, _ = Control.objects.get_or_create(resource=resource)
                target, created = Target.objects.get_or_create(key=row['key'], defaults={
                    'control': control, 'origins': row['origins'], 'adapter': row['adapter'], 'lifecycle': row['lifecycle'],
                })
                if not created:
                    # Moving an enrolled production requires a new enrollment; never
                    # carry an acknowledgment or a machine credential to a new origin.
                    if target.control_id != control.pk or target.origins != row['origins'] or target.adapter != row['adapter']:
                        raise CommandError('El destino cambió; requiere revisar y renovar su integración.')
                    target.lifecycle = row['lifecycle']
                    target.save(update_fields=['lifecycle'])
            self.stdout.write(f'Inventario registrado: {len(rows)} destinos. Modos conservados.')
        if options['issue']:
            path = options['token_file']
            keys = set(options['targets'] or [])
            targets = list(Target.objects.filter(key__in=keys))
            if not path or not keys or len(targets) != len(keys):
                raise CommandError('--targets y --token-file nuevo son obligatorios.')
            token = secrets.token_urlsafe(48)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except OSError:
                raise CommandError('No se pudo crear el archivo protegido; no se sobrescribe.') from None
            with os.fdopen(fd, 'w') as output:
                output.write(token)
            credential = RuntimeCredential.objects.create(label=options['issue'], token_hash=RuntimeCredential.hash_token(token))
            credential.targets.set(targets)
            self.stdout.write(f'Credencial {credential.pk} creada en archivo protegido; no se imprime.')
        elif not options['manifest']:
            raise CommandError('Indica --manifest, --issue o --revoke.')
