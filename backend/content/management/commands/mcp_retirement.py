"""Preview-first retirement; never remove audit rows or transfer credentials."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from content.mcp.connectors import CONNECTORS
from content.mcp.consumer_migration import equivalent_replacement
from content.mcp.migration import retirement_status
from content.models import McpConnector, McpCredential


class Command(BaseCommand):
    help = 'Consulta o aplica un retiro MCP después de verificar consumidores y observación.'

    def add_arguments(self, parser):
        parser.add_argument('--slug', required=True, choices=sorted(CONNECTORS))
        action = parser.add_mutually_exclusive_group()
        action.add_argument('--verify-consumers', action='store_true')
        action.add_argument('--migrated-credential', type=int)
        action.add_argument('--retire', action='store_true')
        parser.add_argument('--replacement-credential', type=int, action='append', default=[])
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        connector = McpConnector.objects.select_for_update().filter(slug=options['slug']).first()
        if connector is None:
            raise CommandError('El conector no está registrado en esta base.')
        spec = CONNECTORS[connector.slug]
        if options['migrated_credential']:
            credential = connector.credentials.select_for_update().filter(pk=options['migrated_credential']).first()
            replacements = list(McpCredential.objects.select_related('connector').filter(
                pk__in=options['replacement_credential'], catalog='canonical', connector__is_active=True,
            ))
            if credential is None or not replacements or len(replacements) != len(set(options['replacement_credential'])):
                raise CommandError('Indica la credencial antigua y sus credenciales canónicas de reemplazo.')
            from content.mcp.module_catalog import CANONICAL_FOR, FINANCIAL_PROJECT_TOOLS, INFRASTRUCTURE_TOOLS
            from content.mcp.connectors import LEGACY_TOOLS_BY_SLUG
            required_owners = {
                'accounting' if tool['name'] in FINANCIAL_PROJECT_TOOLS else CANONICAL_FOR[connector.slug]
                for tool in LEGACY_TOOLS_BY_SLUG[connector.slug]
                if tool['name'] not in INFRASTRUCTURE_TOOLS and credential.allows(tool['name'])
            }
            if {item.connector.slug for item in replacements} != required_owners:
                raise CommandError('Faltan destinos canónicos para alguna función del consumidor.')
            if any(not item.is_usable or item.pk == credential.pk or not equivalent_replacement(credential, item)
                   for item in replacements):
                raise CommandError('Los reemplazos deben conservar exactamente permisos, actor y vencimiento del consumidor.')
            if options['apply']:
                credential.migrated_at = timezone.now()
                credential.save(update_fields=['migrated_at', 'updated_at'])
        elif options['verify_consumers'] and options['apply']:
            connector.consumers_verified_at = timezone.now()
            connector.save(update_fields=['consumers_verified_at', 'updated_at'])
        report = retirement_status(connector)
        if options['retire'] and options['apply']:
            if not report['eligible']:
                raise CommandError('Retiro bloqueado: ' + ', '.join(report['blockers']))
            field = 'retired_at' if spec.compatibility else 'aliases_retired_at'
            setattr(connector, field, timezone.now())
            connector.save(update_fields=[field, 'updated_at'])
            report['retired'] = True
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
