"""Apply only the exact approved resource inventory and preserve originals."""
import json

from django.core.management.base import BaseCommand, CommandError

from accounts.services.platform_media_migration import privatize


class Command(BaseCommand):
    help = 'Valida el manifest; con --apply copia y verifica los bytes antes de cambiar sus referencias.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)
        parser.add_argument('--manifest-sha256', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            result = privatize(options['manifest'], options['manifest_sha256'], apply=options['apply'])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, sort_keys=True))
