"""Refile a movable document without adopting the target folder's owner."""
from content.models import Document, DocumentFolder
from content.serializers.document import DocumentCreateUpdateSerializer
from content.services.data_integrity.catalog import register_fixer
from content.services.data_integrity.fixes.base import Fixer, change, blocker, retained_blockers
from content.services.data_integrity.scope import DOCUMENT, FOLDER
from content.services.data_integrity.types import RELINK
from content.services.data_integrity.snapshots import register_fields, snapshot_many

register_fields(FOLDER, 'client_user_id', 'project_id', 'parent_id', 'is_archived', 'system_key')
from content.services.document_write_service import movement_blockers


def _serializer(document, folder_id, actor):
    profile = getattr(document.client_user, 'profile', None) if document.client_user_id else None
    return DocumentCreateUpdateSerializer(document, data={
        'folder_id': folder_id, 'client': profile.pk if profile else None,
        'project': document.project_id,
    }, partial=True, context={'actor': actor})


class OrganizeDocumentFixer(Fixer):
    kind = RELINK
    fields = {DOCUMENT: ('folder_id', 'client_user_id', 'project_id', 'updated_by_id')}

    def guards_changed(self, step):
        key = (FOLDER, step['guards']['folder_id'])
        return snapshot_many([key])[key] != step['guards']['destination']

    def plan(self, finding, params, *, actor):
        document = Document._base_manager.select_related('client_user__profile', 'project', 'folder').get(
            pk=finding.evidence['document'])
        folder_id = params.get('folder_id')
        folder = DocumentFolder._base_manager.filter(pk=folder_id).first() if type(folder_id) is int and folder_id > 0 else None
        blockers = retained_blockers([document])
        blockers += [blocker(code, 'Este documento tiene un bloqueo de movimiento.') for code in movement_blockers(document)]
        if folder is None:
            blockers.append(blocker('input_required', 'Elige una carpeta de destino válida.'))
        elif folder.retention_context_id:
            blockers.append(blocker('retained_read_only', 'La carpeta conserva datos de un proyecto eliminado.'))
        elif (document.client_user_id and folder.client_user_id and document.client_user_id != folder.client_user_id) or (
            document.project_id and folder.project_id and document.project_id != folder.project_id
        ):
            blockers.append(blocker('folder_owner_mismatch', 'Elige una carpeta compatible con el cliente y proyecto del documento.'))
        if folder is not None:
            serializer = _serializer(document, folder.pk, actor)
            if not serializer.is_valid():
                blockers.append(blocker('writer_refused', 'El Gestor Documental no permite este movimiento.'))
            elif any(getattr(serializer.validated_data.get(field), 'pk', None) != getattr(document, field + '_id')
                     for field in ('client_user', 'project') if field in serializer.validated_data):
                blockers.append(blocker('association_change', 'El movimiento cambiaría la propiedad; revisa primero la asociación.'))
        return self.new_plan(params, closure=[(DOCUMENT, document.pk)],
            dependencies=[(FOLDER, folder.pk)] if folder else [],
            blockers=blockers, changes=[change(document, 'folder', document.folder.name if document.folder_id else 'Sin carpeta',
                folder.name if folder else 'Sin destino')], guards={'folder_id': folder.pk if folder else None,
                'destination': snapshot_many([(FOLDER, folder.pk)])[(FOLDER, folder.pk)] if folder else None},
            context={'document_id': document.pk, 'folder_id': folder.pk if folder else None})

    def apply(self, plan, *, actor):
        document = Document._base_manager.select_related('client_user__profile').get(pk=plan.context['document_id'])
        serializer = _serializer(document, plan.context['folder_id'], actor)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=actor)


register_fixer(('DC9', 'DC10', 'DC11'), OrganizeDocumentFixer())
