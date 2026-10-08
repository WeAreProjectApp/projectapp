"""Write the private, immutable inventory used for resource byte conversion."""
import json

from django.core.management.base import BaseCommand, CommandError

from accounts.services.platform_media_migration import write_inventory


class Command(BaseCommand):
    help = 'Inventaría archivos de recursos vivos y conservados sin modificar la base ni sus archivos.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)

    def handle(self, *args, **options):
        try:
            result = write_inventory(options['manifest'])
        except (OSError, ValueError) as exc:
            raise CommandError('No se pudo guardar un inventario privado válido.') from exc
        self.stdout.write(json.dumps(result, sort_keys=True))
