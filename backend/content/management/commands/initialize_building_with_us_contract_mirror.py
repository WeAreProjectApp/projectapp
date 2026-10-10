"""Explicit, idempotent initialization; never run from a session worktree."""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from content.services.building_with_us_content import BuildingWithUsError
from content.services.building_with_us_contract_service import initialize_mirror, mirror_status


class Command(BaseCommand):
    help = 'Inicializa el espejo de Building with Us en Contratos; sin --apply sólo informa.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--folder-id', type=int)
        parser.add_argument('--actor-id', type=int)

    def handle(self, *args, **options):
        try:
            if not options['apply']:
                self.stdout.write(json.dumps(mirror_status(), ensure_ascii=False))
                return
            if not options['folder_id']:
                raise CommandError('--folder-id es obligatorio al aplicar.')
            users = get_user_model().objects
            actor = users.filter(pk=options['actor_id']).first() if options['actor_id'] else users.filter(is_active=True, is_superuser=True).order_by('pk').first()
            if actor is None or not actor.is_active or not actor.is_staff:
                raise CommandError('Se requiere un administrador activo como autor.')
            result = initialize_mirror(options['folder_id'], actor=actor)
        except BuildingWithUsError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False))
