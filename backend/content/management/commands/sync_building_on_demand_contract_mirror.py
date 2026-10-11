"""Inspect or explicitly synchronize the private cell contract mirror."""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from content.services.building_on_demand_content import BuildingOnDemandError
from content.services.building_on_demand_contract_service import mirror_status, sync_mirror


class Command(BaseCommand):
    help = 'Sincroniza el espejo de Building on Demand en Contratos; sin --apply sólo informa.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--folder-id', type=int)
        parser.add_argument('--actor-id', type=int)

    def handle(self, *args, **options):
        try:
            if not options['apply']:
                self.stdout.write(json.dumps(mirror_status(), ensure_ascii=False))
                return
            users = get_user_model().objects
            if options['actor_id'] is not None:
                actor = users.filter(pk=options['actor_id']).first()
            else:
                actor = users.filter(is_active=True, is_superuser=True).order_by('pk').first()
            if actor is None or not actor.is_active or not actor.is_staff:
                raise CommandError('Se requiere un administrador activo como autor.')
            result = sync_mirror(actor=actor, folder_id=options['folder_id'])
        except BuildingOnDemandError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False))
