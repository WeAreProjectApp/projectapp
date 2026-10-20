"""Inventory first; explicitly attach exact historical packages after review."""
import hashlib
import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from content.models import BusinessProposal, Document, DocumentFolder
from content.services.proposal_approval_service import load_proposal, source_hash
from content.services.proposal_shared_documents import create_package


class Command(BaseCommand):
    help = 'Inventario sin escrituras; --apply requiere propuesta, actor y huella revisada.'

    def add_arguments(self, parser):
        parser.add_argument('--proposal', type=int)
        parser.add_argument('--actor', type=int)
        parser.add_argument('--expected-hash')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if options['apply'] and options['proposal'] and options['expected_hash']:
            existing = BusinessProposal.objects.filter(pk=options['proposal']).first()
            if existing and existing.approval_packages.filter(request_id=f"historical-{existing.pk}", payload_hash=options['expected_hash']).exists():
                self.stdout.write('Ya incorporada; no se crearon documentos.')
                return
        query = BusinessProposal.objects.filter(status__in=['accepted', 'finished']).order_by('pk')
        if options['proposal']:
            query = query.filter(pk=options['proposal'])
        inventory = []
        for proposal in query:
            row = load_proposal(proposal.pk)
            files = list(row.approval_files.order_by('pk').values('id', 'source_key', 'sha256', 'size'))
            root = DocumentFolder.objects.filter(managed_project_id=(row.deliverable.project_id if row.deliverable_id else None)).values('id', 'name', 'project_id', 'client_user_id', 'is_archived').first() if row.deliverable_id and row.deliverable.project_id else None
            existing_documents = list(Document.objects.filter(source_proposal=row).values('id', 'title', 'source_version', 'folder_id'))
            inventory.append({'root_folder': root, 'existing_documents': existing_documents, 'proposal_id': row.pk, 'project': row.linked_project, 'source_hash': source_hash(row),
                'files': files, 'confirmed': bool(row.platform_approval_manifest), 'incorporated': row.approval_packages.exists()})
        digest = hashlib.sha256(json.dumps(inventory, sort_keys=True, default=str).encode()).hexdigest()
        if not options['apply']:
            self.stdout.write(json.dumps({'inventory': inventory, 'expected_hash': digest}, ensure_ascii=False, default=str))
            return
        if not options['proposal'] or not options['actor'] or options['expected_hash'] != digest:
            raise CommandError('Revisa una propuesta y proporciona --actor y --expected-hash vigentes.')
        actor = get_user_model().objects.filter(pk=options['actor'], is_staff=True, is_active=True).first()
        if actor is None or len(inventory) != 1:
            raise CommandError('Se requiere un administrador activo y una propuesta existente.')
        with transaction.atomic():
            proposal = BusinessProposal.objects.select_for_update().get(pk=options['proposal'])
            if proposal.approval_packages.exists():
                self.stdout.write('Ya incorporada; no se crearon documentos.')
                return
            rows = list(proposal.approval_files.select_for_update().all())
            manifest = proposal.platform_approval_manifest
            if not manifest or not proposal.deliverable_id or not proposal.deliverable.project_id or not rows:
                raise CommandError('Completa primero la revisión: faltan proyecto, contrato o archivos confirmados.')
            if source_hash(load_proposal(proposal.pk)) != inventory[0]['source_hash']:
                raise CommandError('La propuesta cambió durante la revisión.')
            expected = {item['id']: (item['sha256'], item['size']) for item in manifest.get('files', [])}
            for row in rows:
                with row.file.open('rb') as stream:
                    hasher, size = hashlib.sha256(), 0
                    for chunk in iter(lambda: stream.read(65536), b''):
                        hasher.update(chunk)
                        size += len(chunk)
                if expected.get(row.pk) != (hasher.hexdigest(), size):
                    raise CommandError('Un archivo no coincide con el cierre confirmado; no se incorporó nada.')
            package, _ = create_package(proposal, actor=actor, request_id=f'historical-{proposal.pk}',
                payload_hash=digest, source_hash=inventory[0]['source_hash'], written_rows=rows, manifest=manifest)
        self.stdout.write(f'Paquete {package.number} incorporado conservando los archivos originales.')
