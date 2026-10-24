"""Provision the private AI key without writing to the application database."""
import os
from pathlib import Path

from cryptography.fernet import Fernet
from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Crea una llave IA privada solo si no existe; nunca muestra ni reemplaza su contenido.'

    def handle(self, *args, **options):
        if config('AI_CREDENTIALS_CIPHER_KEY', default=''):
            from accounts.services.platform_ai_cipher import cipher
            try:
                cipher()
            except Exception:
                raise CommandError('La llave de IA del entorno no es válida.') from None
            self.stdout.write('La llave de IA está configurada mediante el entorno.')
            return
        path = Path(config('AI_CREDENTIALS_CIPHER_KEY_FILE', default='') or Path(settings.PRIVATE_MEDIA_ROOT) / 'runtime-secrets' / 'platform-ai.key')
        if path.exists() or path.is_symlink():
            from accounts.services.platform_ai_cipher import cipher
            try:
                cipher()
            except Exception:
                raise CommandError('La llave existente no es válida. Restáurala; no se reemplazó ningún archivo.') from None
            self.stdout.write('La llave privada de IA ya existe y se conserva.')
            return
        from accounts.models_ai import PlatformAICredential
        if PlatformAICredential.objects.exclude(encrypted_value='').exists():
            raise CommandError('Hay credenciales cifradas y falta su llave. Restaura el archivo original desde el respaldo.')
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(Fernet.generate_key())
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            raise CommandError('No se pudo crear la llave privada de IA.') from None
        self.stdout.write('Llave privada de IA creada. Respalda el archivo antes de guardar credenciales.')
