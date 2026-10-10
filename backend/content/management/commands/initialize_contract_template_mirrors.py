"""Idempotent, explicit initialization; never run from a session worktree."""
import json
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from content.models import ContractTemplateMirror, Document, DocumentFolder, DocumentType
from content.services.contract_mirror_service import mirror_placeholder_markdown
from content.services.contract_template_service import (
    MIRROR_TITLES, _synchronize, current_revision, default_template, list_mirrors,
)
from content.services.contract_template_validation import ContractTemplateError, VARIANTS


class Command(BaseCommand):
    help = 'Inicializa los tres espejos en la carpeta indicada por ID; sin --apply sólo informa.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--folder-id', type=int)
        parser.add_argument('--service-document-id', type=int)
        parser.add_argument('--actor-id', type=int)

    def handle(self, *args, **options):
        if not options['apply']:
            self.stdout.write(json.dumps(list_mirrors(), ensure_ascii=False))
            return
        if not options['folder_id']:
            raise CommandError('--folder-id es obligatorio al aplicar.')
        try:
            with transaction.atomic():
                template = default_template(lock=True)
                folder = DocumentFolder.objects.select_for_update().get(pk=options['folder_id'], is_archived=False)
                if template.mirror_folder_id is not None and template.mirror_folder_id != folder.pk:
                    raise CommandError(f'Los espejos ya están fijados a la carpeta {template.mirror_folder_id}; no se re-fijan.')
                if folder.client_user_id or folder.project_id:
                    raise CommandError('Contratos debe ser una carpeta interna sin cliente ni proyecto.')
                if template.mirror_folder_id is None:
                    template.mirror_folder = folder
                    template.save(update_fields=['mirror_folder'])
                actor = get_user_model().objects.get(pk=options['actor_id']) if options['actor_id'] else get_user_model().objects.filter(is_active=True, is_superuser=True).order_by('pk').first()
                if actor is None or not actor.is_active or not actor.is_staff:
                    raise CommandError('Se requiere un administrador activo como autor.')
                doc_type = DocumentType.objects.get(code='markdown')
                for key in VARIANTS:
                    revision = current_revision(template, key)
                    if revision is None:
                        raise CommandError('Falta la importación de versiones; aplica las migraciones del despliegue.')
                    mirror = template.mirrors.select_for_update().filter(variant=key).select_related('document', 'revision').first()
                    if mirror and mirror.revision_id == revision.pk and mirror.pdf_content and mirror.document.folder_id == folder.pk and mirror.document.title == MIRROR_TITLES[key]:
                        continue
                    if mirror:
                        document = mirror.document
                    else:
                        pk = template.mirror_document_id if key == 'combined' else options['service_document_id'] if key == 'service' else None
                        document = Document.objects.select_for_update().get(pk=pk) if pk else Document(document_type=doc_type)
                        if document.document_type_id != doc_type.pk or document.signed_at or document.requires_signature or document.generated_file or document.source_proposal_id or document.source_version or document.client_user_id or document.project_id or document.is_archived:
                            raise CommandError(f'El documento {document.pk} no es una copia interna convertible.')
                        original = document.content_markdown
                    document.title = MIRROR_TITLES[key]
                    document.folder = folder
                    document.is_client_visible = False
                    document.content_markdown = mirror_placeholder_markdown(key)
                    document.content_json = {}
                    document.save()
                    if mirror is None:
                        mirror = ContractTemplateMirror(template=template, variant=key, document=document,
                            revision=revision, synced_at=timezone.now(), imported_markdown=original)
                    _synchronize(template, revision, mirror, actor=actor, note='Inicialización del espejo contractual de solo lectura.', diff='')
                    if key == 'combined' and template.mirror_document_id != document.pk:
                        template.mirror_document = document
                        template.save(update_fields=['mirror_document'])
        except (ContractTemplateError, DocumentFolder.DoesNotExist, Document.DoesNotExist, DocumentType.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(list_mirrors(), ensure_ascii=False))
