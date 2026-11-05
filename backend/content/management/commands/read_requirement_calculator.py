"""Read-only access to the same versioned context exposed through MCP."""
import json
from django.core.management.base import BaseCommand, CommandError
from content.services.requirement_calculator import calculator_context


class Command(BaseCommand):
    help = 'Read the applicable requirement calculator; never creates or changes records.'

    def add_arguments(self, parser):
        parser.add_argument('--project-id', type=int)
        parser.add_argument('--project-version-id', type=int)

    def handle(self, *args, **options):
        for key in ('project_id', 'project_version_id'):
            if options[key] is not None and options[key] < 1:
                raise CommandError('Los identificadores deben ser positivos.')
        context = calculator_context(project_id=options['project_id'], project_version_id=options['project_version_id'])
        self.stdout.write(json.dumps(context, ensure_ascii=False, indent=2))
