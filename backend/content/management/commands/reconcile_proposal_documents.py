"""Inventory first; recover exact approved document identities after review."""
import hashlib
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import APIException

from content.models import BusinessProposal
from content.services.proposal_approval_service import load_proposal
from content.services.proposal_document_reconciliation import preview, reconcile


class Command(BaseCommand):
    help = 'Inventario sin escrituras; --apply requiere propuesta, actor y huella revisada.'

    def add_arguments(self, parser):
        parser.add_argument('--proposal', type=int)
        parser.add_argument('--actor', type=int)
        parser.add_argument('--expected-hash')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        query = BusinessProposal.objects.filter(status__in=['accepted', 'finished']).order_by('pk')
        if options['proposal']:
            query = query.filter(pk=options['proposal'])
        inventory = [preview(load_proposal(pk)) for pk in query.values_list('pk', flat=True)]
        digest = (inventory[0]['expected_hash'] if options['proposal'] and len(inventory) == 1
                  else hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest())
        if not options['apply']:
            self.stdout.write(json.dumps({'inventory': inventory, 'expected_hash': digest}, ensure_ascii=False))
            return
        actor = get_user_model().objects.filter(pk=options['actor'], is_staff=True, is_active=True).first()
        if actor is None or not options['proposal'] or len(inventory) != 1 or not options['expected_hash']:
            raise CommandError('Revisa una propuesta y proporciona --actor y --expected-hash vigentes.')
        if inventory[0]['already_complete']:
            self.stdout.write('Ya incorporada; no se crearon documentos.')
            return
        try:
            result = reconcile(options['proposal'], actor=actor, expected_hash=options['expected_hash'])
        except APIException as exc:
            raise CommandError(f'No se incorporó nada; revisa la huella y los bloqueos: {exc.detail}') from exc
        self.stdout.write(f'Paquete {result["package_number"]} incorporado conservando los archivos originales.')
