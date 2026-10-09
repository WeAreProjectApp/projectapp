"""Engine adapter for document-folder merges (DC4); the merge itself lives in content.services.document_folder_merge.

Also holds the two helpers both merge adapters share: the actor blocker and
the ordered restore their ``revert`` runs before the engine's exact restore.
"""
from content.services import document_folder_merge as folder_merge
from content.services.data_integrity.catalog import register_fixer
from content.services.data_integrity.fixes.base import Fixer, required_choice
from content.services.data_integrity.scope import DOCUMENT, FOLDER
from content.services.data_integrity.snapshots import json_value, model_for
from content.services.data_integrity.types import MERGE_FOLDERS, blocker
from content.services.entity_history import capture_instance
from rest_framework.exceptions import PermissionDenied

SAMPLE_SIZE = 20


def actor_blockers(actor):
    if folder_merge.is_active_superuser(actor):
        return []
    return [blocker('actor_not_superuser', 'Una fusión sólo la aplica un superusuario activo.')]


def recorded_rows(items):
    """``{(model, pk): {field: before}}`` for every recorded non-guard item."""
    rows = {}
    for item in items:
        if not item['guard']:
            rows.setdefault((item['model'], item['pk']), {})[item['field']] = item['before']
    return rows


def restore_rows(rows, keys):
    """Write ``before`` back one row at a time, in ``keys`` order, one UPDATE per row.

    Raw updates on purpose: an undo must not re-run the signals the merge
    already ran (snapshot re-syncs, project folder and thread synchronization).
    History-tracked rows are captured first, like the engine's exact restore.
    """
    for label, pk in keys:
        values = rows[(label, pk)]
        model = model_for(label)
        current = model._base_manager.filter(pk=pk).values(*values).first()
        if current is None:
            continue
        pending = {name: value for name, value in values.items() if json_value(current[name]) != value}
        if pending:
            capture_instance(model._base_manager.get(pk=pk))
            model._base_manager.filter(pk=pk).update(**pending)


def folder_changes(result):
    """The folder-merge preview as summarized ``changes``: one entry per kind of move, never per record."""
    survivor, duplicate = result['survivor'], result['duplicate']
    changes = [{'model': FOLDER, 'id': duplicate['id'], 'label': duplicate['name'], 'field': 'merged_into',
                'before': None, 'after': survivor['id'], 'totals': result['totals']}]
    documents = [row['id'] for row in result['documents_move']]
    if documents:
        changes.append({'model': DOCUMENT, 'id': None, 'label': 'Documentos activos que cambian de carpeta',
                        'field': 'folder', 'before': duplicate['id'], 'after': survivor['id'],
                        'count': len(documents), 'sample_ids': documents[:SAMPLE_SIZE]})
    if result['folders_move']:
        changes.append({'model': FOLDER, 'id': None, 'label': 'Subcarpetas que pasan a la carpeta conservada',
                        'field': 'parent', 'before': duplicate['id'], 'after': survivor['id'],
                        'count': len(result['folders_move']),
                        'items': [{'id': row['id'], 'new_order': row['new_order']}
                                  for row in result['folders_move'][:SAMPLE_SIZE]]})
    if result['folders_merge']:
        changes.append({'model': FOLDER, 'id': None, 'label': 'Subcarpetas que se fusionan con su homónima',
                        'field': 'merged_into', 'before': None, 'after': None,
                        'count': len(result['folders_merge']), 'items': result['folders_merge'][:SAMPLE_SIZE]})
    changes.append({'model': FOLDER, 'id': None, 'label': 'Carpetas que quedan vacías y se archivan',
                    'field': 'is_archived', 'before': False, 'after': True,
                    'count': len(result['folders_retire']), 'sample_ids': result['folders_retire'][:SAMPLE_SIZE]})
    return changes


def folder_warnings(result):
    warnings = []
    left = result['archived_left_in_place']
    if left['documents'] or left['folders']:
        warnings.append({'code': 'archived_left_in_place',
                         'message': 'Lo que ya estaba archivado se queda dentro de la carpeta duplicada, para '
                                    'conservar de dónde salió.',
                         'documents': len(left['documents']), 'folders': len(left['folders'])})
    warnings.append({'code': 'not_undoable_parts',
                     'message': 'Deshacer devuelve carpetas y documentos a su lugar, pero el historial, el recibo '
                                'de la fusión y las fechas de modificación se conservan.'})
    return warnings


class MergeFoldersFixer(Fixer):
    kind = MERGE_FOLDERS
    exclusive = True
    max_closure = folder_merge.MAX_ITEMS
    fields = {
        FOLDER: ('parent_id', 'order', 'is_archived', 'archived_at', 'archived_via_folder_id'),
        DOCUMENT: ('folder_id', 'updated_by_id'),
    }

    def plan(self, finding, params, *, actor):
        options = [{'value': pk} for pk in finding.evidence['folders']]
        survivor, found = required_choice(params, 'survivor', options, 'la carpeta que se conserva')
        duplicate, missing = required_choice(params, 'duplicate', options, 'la carpeta duplicada')
        blockers = found + missing + actor_blockers(actor)
        if survivor is None or duplicate is None:
            return self.new_plan(params, blockers=blockers)
        result = folder_merge.plan_folder_merge(survivor, duplicate)
        return self.new_plan(
            params,
            closure=[tuple(key) for key in result['closure']],
            changes=folder_changes(result),
            blockers=blockers + result['blockers'],
            guards={'survivor': survivor, 'duplicate': duplicate, 'plan_hash': result['fingerprint']},
            warnings=folder_warnings(result),
            context={'merge': result},
        )

    def apply(self, plan, *, actor):
        folder_merge.apply_folder_merge(plan.context['merge'], actor=actor)

    def revert(self, step, *, actor):
        """Reverse order: unarchive D, then the merged children, move folders back, then documents."""
        if actor_blockers(actor):
            # PermissionDenied is not swallowed by the engine's writer fallback.
            raise PermissionDenied('Deshacer una fusión requiere un superusuario activo.', code='actor_not_superuser')
        folder_merge.lock_folder_tree()
        rows = recorded_rows(step['items'])
        duplicate = step['guards'].get('duplicate')

        def rank(key):
            label, pk = key
            if label == FOLDER and 'is_archived' in rows[key]:
                return (0, pk != duplicate, pk)
            return (1 if label == FOLDER else 2, 0, pk)

        restore_rows(rows, sorted(rows, key=rank))

    def guards_changed(self, step):
        return folder_merge.folder_merge_undo_blockers(step['guards'].get('duplicate'))


register_fixer('DC4', MergeFoldersFixer())
