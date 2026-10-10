"""Merge a document folder into a same-named sibling, or a client root into another.

The duplicate D is emptied into the survivor S and then archived on its own;
nothing is deleted. The walk is deterministic (order, name, pk):

* D's active documents move to S, setting ``folder`` and ``updated_by`` exactly
  like the reviewed repair (``document_folder_repair.apply_repair``). Their
  client and project never change: a merge restores placement only.
* Each active child c of D merges recursively into S's only active child with
  the same normalized name and is archived afterwards, or, when S has no such
  child, is re-parented to the end of S's children.
* Archived content stays inside D. Its ``archived_via_folder`` provenance keeps
  pointing at the folder that archived it, so unarchiving still restores exactly
  what each archive dragged (``document_archive_service``).

``plan_folder_merge`` computes everything without writing and lists what would
block it; ``apply_folder_merge`` runs a plan inside the caller's transaction and
history operation and leaves the repair's receipt in ``AccountingChangeLog``.
``client_merge=(survivor_user_id, duplicate_user_id)`` is how the client merge
reuses this for client roots: the duplicate's user counts as the survivor's in
the scope checks, and D may be the duplicate's managed client root.
"""
from django.db import transaction

from content.management.commands.audit_archive_integrity import _audit
from content.models import AccountingChangeLog, Document, DocumentFolder
from content.models.document_folder import DocumentFolderMutationLock
from content.services.contract_mirror_service import folder_contains_mirror
from content.services.data_integrity.hashing import normalized
from content.services.document_archive_service import archive_folder
from content.services.document_folder_repair import fingerprint
from content.services.document_write_service import movement_blockers
from content.services.entity_history import current_history_operation_id

FOLDER = 'content.documentfolder'
DOCUMENT = 'content.document'
MAX_ITEMS = 500
MAX_DOCUMENTS = 200
RECEIPT_SOURCE = 'data_integrity:merge_folders'


class FolderMergeError(ValueError):
    """A merge refused while writing; the caller's transaction rolls back."""


def normalized_name(name):
    """The shared duplicate key used by DC4 and recursive child matching."""
    return normalized(name)


def is_active_superuser(actor):
    """Same criterion as ``document_folder_repair.apply_repair``."""
    return bool(getattr(actor, 'is_superuser', False) and getattr(actor, 'is_active', False))


def lock_folder_tree():
    """The manual-tree mutex taken by the folder serializer and the reviewed repair."""
    DocumentFolderMutationLock.objects.get_or_create(pk=1)
    DocumentFolderMutationLock.objects.select_for_update().get(pk=1)


def folder_record(folder):
    return {'model': FOLDER, 'id': folder.pk, 'label': folder.name}


def document_record(document):
    return {'model': DOCUMENT, 'id': document.pk, 'label': document.title}


def folder_card(folder):
    return {'id': folder.pk, 'name': folder.name, 'kind': folder.folder_kind, 'parent_id': folder.parent_id,
            'client_user_id': folder.client_user_id, 'project_id': folder.project_id}


def _subtree(folder):
    return {folder.pk} | folder.get_descendant_ids()


class _Planner:
    """One walk of D into S. Every check appends a blocker; nothing is written."""

    def __init__(self, survivor, duplicate, client_merge):
        self.survivor = survivor
        self.duplicate = duplicate
        self.client_merge = tuple(client_merge) if client_merge else None
        self.ops = []
        self.merges = []
        self.left_documents = []
        self.left_folders = []
        self.closure = {(FOLDER, survivor.pk), (FOLDER, duplicate.pk)}
        self.visited = set()
        self._blockers = {}

    # ── Helpers ──────────────────────────────────────────────────────────────

    def block(self, code, message, records=()):
        entry = self._blockers.setdefault(code, {'code': code, 'message': message, 'records': []})
        for record in records:
            if record not in entry['records']:
                entry['records'].append(record)

    def blockers(self):
        return [{key: value for key, value in entry.items() if key != 'records' or value}
                for entry in self._blockers.values()]

    def mapped(self, user_id):
        """Inside a client merge the duplicate's user already counts as the survivor's."""
        if self.client_merge and user_id == self.client_merge[1]:
            return self.client_merge[0]
        return user_id

    def same_association(self, target, source):
        """D's (client, project) equals S's, or D has none (the repair case)."""
        if (source.client_user_id, source.project_id) == (None, None):
            return True
        return (self.mapped(source.client_user_id), source.project_id) == (
            self.mapped(target.client_user_id), target.project_id,
        )

    def fits(self, target, client_user_id, project_id, project_client_id):
        """A row that ends up under ``target`` must not belong to another client or project."""
        if target.project_id and project_id not in (None, target.project_id):
            return False
        if target.client_user_id:
            target_user_id = self.mapped(target.client_user_id)
            if self.mapped(client_user_id) not in (None, target_user_id):
                return False
            if project_id and self.mapped(project_client_id) != target_user_id:
                return False
        return True

    # ── Checks ───────────────────────────────────────────────────────────────

    def check_pair(self):
        """Top-level preconditions. Returns whether the walk is meaningful."""
        survivor, duplicate = self.survivor, self.duplicate
        both = [folder_record(survivor), folder_record(duplicate)]
        if survivor.pk == duplicate.pk:
            self.block('same_folder', 'La carpeta que se conserva y la duplicada deben ser distintas.', both)
            return False
        archived = [folder_record(folder) for folder in (survivor, duplicate) if folder.is_archived]
        if archived:
            self.block('folder_archived', 'Las dos carpetas deben estar activas.', archived)
        managed = [folder_record(folder) for folder in (survivor, duplicate) if folder.system_key]
        if managed:
            self.block('system_managed', 'Las carpetas administradas por el sistema no se fusionan.', managed)
        projects = [folder_record(folder) for folder in (survivor, duplicate) if folder.managed_project_id]
        if projects:
            self.block('wrong_kind', 'La raíz de un proyecto no se fusiona: se concilia con '
                       'reconcile_project_folders.', projects)
        if self.client_merge:
            if (survivor.managed_client_id != self.client_merge[0]
                    or duplicate.managed_client_id not in (None, self.client_merge[1])):
                self.block('wrong_kind', 'En una fusión de clientes sólo se fusionan las raíces de los dos clientes.',
                           both)
        elif duplicate.managed_client_id:
            self.block('wrong_kind', 'La carpeta raíz de un cliente sólo se fusiona al fusionar los clientes.',
                       [folder_record(duplicate)])
        siblings = survivor.parent_id == duplicate.parent_id
        if not self.client_merge:
            if not siblings:
                self.block('not_siblings', 'Las dos carpetas deben estar dentro de la misma carpeta.', both)
            if normalized_name(survivor.name) != normalized_name(duplicate.name):
                self.block('name_mismatch', 'Las carpetas deben llamarse igual (sin contar tildes, mayúsculas, '
                           'signos ni espacios repetidos).', both)
        if not self.same_association(survivor, duplicate):
            self.block('scope_mismatch', 'La carpeta duplicada pertenece a otro cliente o proyecto que la que '
                       'se conserva.', both)
        return bool(self.client_merge) or siblings

    def check_subtrees(self):
        """Retained rows, contract mirrors and archive-invariant anomalies in either subtree."""
        survivor, duplicate = self.survivor, self.duplicate
        ids = _subtree(survivor) | _subtree(duplicate)
        retained = [folder_record(row) for row in DocumentFolder._base_manager
                    .filter(pk__in=ids, retention_context__isnull=False).order_by('pk')]
        retained += [document_record(row) for row in Document._base_manager
                     .filter(folder_id__in=ids, retention_context__isnull=False).order_by('pk')]
        if retained:
            self.block('retained_rows', 'Hay carpetas o documentos conservados de un proyecto eliminado: son de '
                       'sólo lectura y la fusión no puede tocarlos.', retained)
        for root in (survivor, duplicate):
            if folder_contains_mirror(root):
                self.block('contract_mirror', 'Una carpeta contiene la plantilla contractual de sólo lectura; '
                           'no se puede fusionar.', [folder_record(root)])
        immovable = [document_record(row) for row in Document._base_manager.filter(folder_id__in=ids)
                     .select_related('document_type').order_by('pk')
                     if set(movement_blockers(row)) - {'archived'}]
        if immovable:
            self.block('document_not_movable', 'Hay documentos que no admiten movimientos.', immovable)
        audit = _audit()
        anomalies = [{'model': DOCUMENT, 'id': pk, 'label': title}
                     for pk, title, folder_id in audit['lost_documents'] if folder_id in ids]
        anomalies += [{'model': FOLDER, 'id': pk, 'label': name}
                      for pk, name in audit['buried_folders'] if pk in ids]
        anomalies += [{'model': FOLDER, 'id': pk, 'label': ''}
                      for cycle in audit['cycles'] if ids & set(cycle) for pk in cycle]
        anomalies += [{'model': FOLDER, 'id': pk, 'label': name}
                      for pk, name in audit['active_folders_with_provenance'] if pk in ids]
        provenance = {pk for pk, _ in audit['active_docs_with_provenance']}
        if provenance:
            anomalies += [document_record(row) for row in Document._base_manager
                          .filter(pk__in=provenance, folder_id__in=ids).order_by('pk')]
        if anomalies:
            self.block('tree_anomaly', 'El árbol tiene inconsistencias de archivado (ciclos, elementos activos '
                       'dentro de carpetas archivadas o procedencia anómala). Corrígelas con '
                       'audit_archive_integrity antes de fusionar.', anomalies)

    def check_carried(self, folder, target):
        """A re-parented child carries its whole subtree under ``target``."""
        ids = _subtree(folder)
        mismatched = [folder_record(row) for row in DocumentFolder._base_manager.filter(pk__in=ids)
                      .select_related('project').order_by('pk')
                      if not self.fits(target, row.client_user_id, row.project_id,
                                       row.project.client_id if row.project_id else None)]
        mismatched += [document_record(row) for row in Document._base_manager.filter(folder_id__in=ids)
                       .select_related('project').order_by('pk')
                       if not self.fits(target, row.client_user_id, row.project_id,
                                        row.project.client_id if row.project_id else None)]
        if mismatched:
            self.block('scope_mismatch', 'Hay carpetas o documentos de otro cliente o proyecto que quedarían dentro '
                       'de la carpeta que se conserva.', mismatched)

    def mergeable(self, target, source):
        if (source.system_key or target.system_key or source.managed_project_id or source.managed_client_id
                or target.managed_project_id or target.managed_client_id):
            return False
        return self.same_association(target, source)

    # ── Walk ─────────────────────────────────────────────────────────────────

    def plan_document(self, document, source, target):
        if document.is_archived:
            self.left_documents.append(document.pk)
            return
        if movement_blockers(document):
            self.block('document_not_movable', 'Hay documentos que no admiten movimientos (plantilla contractual, '
                       'PDF generado o cuenta de cobro emitida).', [document_record(document)])
        if not self.fits(target, document.client_user_id, document.project_id,
                         document.project.client_id if document.project_id else None):
            self.block('scope_mismatch', 'Hay documentos de otro cliente o proyecto que quedarían dentro de la '
                       'carpeta que se conserva.', [document_record(document)])
        self.ops.append({'op': 'document', 'id': document.pk, 'from': source.pk, 'to': target.pk})
        self.closure.add((DOCUMENT, document.pk))

    def walk(self, target, source):
        if len(self.closure) > MAX_ITEMS:
            self.block('merge_too_large', 'La fusión supera el máximo de registros; divide el trabajo.')
            return
        if source.pk in self.visited:
            self.block('tree_anomaly', 'El árbol tiene un ciclo; corrígelo con audit_archive_integrity antes de '
                       'fusionar.', [folder_record(source)])
            return
        self.visited.add(source.pk)
        documents = (Document._base_manager.filter(folder_id=source.pk)
                     .select_related('project', 'document_type').order_by('pk'))
        for document in documents:
            self.plan_document(document, source, target)
        targets = list(DocumentFolder._base_manager.filter(parent_id=target.pk).order_by('order', 'name', 'pk'))
        children = list(DocumentFolder._base_manager.filter(parent_id=source.pk).order_by('order', 'name', 'pk'))
        next_order = max((child.order for child in targets), default=-1) + 1
        active = []
        for child in children:
            if child.is_archived:
                self.left_folders.append(child.pk)
            else:
                active.append(child)
        for index, child in enumerate(active):
            key = normalized_name(child.name)
            if child.system_key:
                self.block('system_managed', 'Hay subcarpetas administradas por el sistema que no se pueden mover.',
                           [folder_record(child)])
                continue
            matches = [row for row in targets if not row.is_archived and normalized_name(row.name) == key]
            if len(matches) > 1:
                self.block('ambiguous_survivor_child', 'La carpeta que se conserva tiene varias subcarpetas activas '
                           'con el mismo nombre que una de la duplicada; fusiónalas primero.',
                           [folder_record(child)] + [folder_record(row) for row in matches])
                continue
            if matches:
                twin = matches[0]
                if not self.mergeable(twin, child):
                    self.block('unmergeable_child_collision', 'Una subcarpeta coincide en nombre con otra de la '
                               'carpeta que se conserva, pero no se pueden fusionar (sistema, otro cliente u otro '
                               'proyecto).', [folder_record(child), folder_record(twin)])
                    continue
                self.merges.append({'source': child.pk, 'target': twin.pk})
                self.closure |= {(FOLDER, child.pk), (FOLDER, twin.pk)}
                self.walk(twin, child)
                self.ops.append({'op': 'retire', 'id': child.pk})
                continue
            self.check_carried(child, target)
            self.ops.append({'op': 'folder', 'id': child.pk, 'from': source.pk, 'to': target.pk,
                             'old_order': child.order, 'new_order': next_order + index})
            self.closure.add((FOLDER, child.pk))
            # A later same-named source child now collides with this planned move.
            targets.append(child)

    # ── Result ───────────────────────────────────────────────────────────────

    def payload(self):
        documents = [op for op in self.ops if op['op'] == 'document']
        folders = [op for op in self.ops if op['op'] == 'folder']
        retired = [op['id'] for op in self.ops if op['op'] == 'retire']
        closure = sorted(self.closure)
        if len(closure) > MAX_ITEMS or len(documents) > MAX_DOCUMENTS:
            self.block('merge_too_large', f'La fusión toca {len(closure)} registros y mueve {len(documents)} '
                       f'documentos; el máximo es {MAX_ITEMS} registros y {MAX_DOCUMENTS} documentos.')
        left = {'documents': sorted(self.left_documents), 'folders': sorted(self.left_folders)}
        return {
            'survivor': folder_card(self.survivor),
            'duplicate': folder_card(self.duplicate),
            'documents_move': [{'id': op['id'], 'from': op['from'], 'to': op['to']} for op in documents],
            'folders_move': [{key: op[key] for key in ('id', 'from', 'to', 'old_order', 'new_order')}
                             for op in folders],
            'folders_merge': list(self.merges),
            'folders_retire': retired,
            'archived_left_in_place': left,
            'blockers': self.blockers(),
            'totals': {
                'documents_move': len(documents), 'folders_move': len(folders),
                'folders_merge': len(self.merges), 'folders_retire': len(retired),
                'archived_left_in_place': len(left['documents']) + len(left['folders']),
                'items': len(closure),
            },
            'ops': list(self.ops),
            'closure': [[label, pk] for label, pk in closure],
            'fingerprint': fingerprint({'survivor': self.survivor.pk, 'duplicate': self.duplicate.pk,
                                        'ops': self.ops}),
        }


def _folder(value):
    return DocumentFolder._base_manager.get(pk=getattr(value, 'pk', value))


def plan_folder_merge(survivor, duplicate, *, client_merge=None):
    """What merging ``duplicate`` into ``survivor`` would do, with its blockers. Writes nothing.

    Returns ``survivor``/``duplicate`` cards, ``documents_move``, ``folders_move``
    ``[{id, from, to, old_order, new_order}]``, ``folders_merge``
    ``[{source, target}]``, ``folders_retire``, ``archived_left_in_place``,
    ``blockers``, ``totals``, the ordered ``ops`` the apply runs, the
    ``closure`` of rows it writes and the plan ``fingerprint``.
    """
    planner = _Planner(_folder(survivor), _folder(duplicate), client_merge)
    if planner.check_pair():
        planner.check_subtrees()
        planner.walk(planner.survivor, planner.duplicate)
        planner.ops.append({'op': 'retire', 'id': planner.duplicate.pk})
    result = planner.payload()
    result['client_merge'] = list(client_merge) if client_merge else None
    ids = _subtree(planner.survivor) | _subtree(planner.duplicate)
    result['expected'] = {
        'folders': [fingerprint(row) for row in DocumentFolder._base_manager.filter(pk__in=ids)
                    .order_by('pk').values()],
        'documents': [fingerprint(row) for row in Document._base_manager.filter(folder_id__in=ids)
                      .order_by('pk').values()],
    }
    result['fingerprint'] = fingerprint({key: value for key, value in result.items() if key != 'fingerprint'})
    return result


# ── Apply ────────────────────────────────────────────────────────────────────

def _move_document(op, actor):
    document = Document.objects.get(pk=op['id'])
    if document.folder_id != op['from'] or document.is_archived:
        raise FolderMergeError('Un documento cambió desde la vista previa; no se fusionó nada.')
    # Placement only, as in the reviewed repair: client and project stay.
    document.folder_id = op['to']
    document.updated_by = actor
    document.save(update_fields=['folder', 'updated_by', 'updated_at'])


def _move_folder(op):
    folder = DocumentFolder.objects.get(pk=op['id'])
    if folder.parent_id != op['from'] or folder.is_archived:
        raise FolderMergeError('Una subcarpeta cambió desde la vista previa; no se fusionó nada.')
    folder.parent_id = op['to']
    folder.order = op['new_order']
    folder.save(update_fields=['parent', 'order', 'updated_at'])


def _retire(pk):
    folder = DocumentFolder.objects.get(pk=pk)
    descendants = folder.get_descendant_ids()
    if (Document.objects.filter(folder_id__in={pk} | descendants, is_archived=False).exists()
            or DocumentFolder.objects.filter(pk__in=descendants, is_archived=False).exists()):
        raise FolderMergeError('La carpeta duplicada dejó de estar vacía; se revierte la fusión.')
    archive_folder(folder)


@transaction.atomic
def apply_folder_merge(plan, *, actor, source=RECEIPT_SOURCE):
    """Run a plan from ``plan_folder_merge`` and leave the receipt. Raises on any refusal.

    Runs inside the caller's history operation: the data-integrity engine (or a
    client merge running inside it) owns the revision source.
    """
    if not is_active_superuser(actor):
        raise FolderMergeError('La fusión de carpetas requiere un administrador activo.')
    if plan['blockers']:
        raise FolderMergeError('La fusión de carpetas tiene bloqueos; revisa la vista previa.')
    if current_history_operation_id() is None:
        raise FolderMergeError('La fusión requiere la operación de historial del motor.')
    lock_folder_tree()
    document_ids = sorted(op['id'] for op in plan['ops'] if op['op'] == 'document')
    folder_ids = sorted({pk for label, pk in plan['closure'] if label == FOLDER})
    list(Document.objects.select_for_update().filter(pk__in=document_ids).order_by('pk').values_list('pk', flat=True))
    list(DocumentFolder.objects.select_for_update().filter(pk__in=folder_ids).order_by('pk')
         .values_list('pk', flat=True))
    survivor = DocumentFolder.objects.get(pk=plan['survivor']['id'])
    duplicate = DocumentFolder.objects.get(pk=plan['duplicate']['id'])
    current = plan_folder_merge(survivor, duplicate, client_merge=plan.get('client_merge'))
    if current['blockers'] or current['fingerprint'] != plan['fingerprint']:
        raise FolderMergeError('El estado cambió desde la vista previa; no se fusionó nada.')
    for op in plan['ops']:
        if op['op'] == 'document':
            _move_document(op, actor)
        elif op['op'] == 'folder':
            _move_folder(op)
        else:
            _retire(op['id'])
    moved_folders = [op['id'] for op in plan['ops'] if op['op'] == 'folder']
    merged_folders = [entry['source'] for entry in plan['folders_merge']]
    operation_id = current_history_operation_id()
    AccountingChangeLog.objects.create(
        entity_type='document_folder',
        object_id=duplicate.pk,
        object_repr=duplicate.name,
        action='updated',
        actor=actor,
        actor_username=actor.get_username(),
        changes=[
            {'field': 'merge_plan', 'old': '', 'new': plan['fingerprint']},
            {'field': 'merged_into', 'old': '', 'new': survivor.pk},
            {'field': 'folder', 'old': duplicate.pk, 'new': survivor.pk},
            {'field': 'document_ids', 'old': document_ids, 'new': document_ids},
            {'field': 'folder_ids', 'old': moved_folders, 'new': moved_folders},
            {'field': 'merged_folder_ids', 'old': merged_folders, 'new': merged_folders},
            {'field': 'is_archived', 'old': False, 'new': True},
            {'field': 'operation', 'old': None,
             'new': {'source': source, 'history_operation_id': str(operation_id) if operation_id else None}},
        ],
    )
    return {'survivor': survivor.pk, 'duplicate': duplicate.pk, 'documents': document_ids,
            'folders_moved': moved_folders, 'folders_merged': merged_folders}


# ── Undo guards ──────────────────────────────────────────────────────────────

def folder_merge_undo_blockers(duplicate_id):
    """Facts that make restoring D unsafe beyond the engine's changed-since check."""
    folder = DocumentFolder._base_manager.filter(pk=duplicate_id).select_related('parent').first()
    if folder is None:
        return [{'code': 'folder_missing', 'message': 'La carpeta duplicada ya no existe.'}]
    if folder.parent_id and folder.parent.is_archived:
        return [{'code': 'parent_archived', 'message': 'La carpeta que contenía a la duplicada se archivó después; '
                 'restaurarla la dejaría oculta dentro de una carpeta archivada.',
                 'records': [folder_record(folder.parent)]}]
    return []
