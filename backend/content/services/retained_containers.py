"""Discard the empty containers a forced project deletion left retained.

Folders and threads only organise content. Once their documents, threads and
messages have been adopted elsewhere, nothing can use them again: their roots
and system keys belong to a project that no longer exists. Only EMPTY
containers of one retention context are deleted, leaf first, in one audited
operation. Any row still pointing to a container blocks it, including
relations this module does not know about.
"""
import hashlib
import json

from django.db import transaction

from content.models import (
    CommunicationFolder, CommunicationThread, DocumentFolder, ProjectRetentionContext,
    ProjectRetentionOperation,
)
from content.models.document_folder import DocumentFolderMutationLock
from content.services.retained_adoption import RetentionConflict, remove_from_inventory

# Threads first (they sit in communication folders), then folders leaf first.
KINDS = (
    ('communication_threads', CommunicationThread, 'title', 'folder_id'),
    ('communication_folders', CommunicationFolder, 'name', 'parent_id'),
    ('document_folders', DocumentFolder, 'name', 'parent_id'),
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _holders(row, discarding):
    """{relation: count} of rows still pointing to this container."""
    holders = {}
    for relation in row._meta.related_objects:
        if relation.many_to_many:
            continue
        related = relation.related_model
        rows = related._base_manager.filter(**{relation.field.name: row.pk})
        ignored = discarding.get(related._meta.label_lower)
        if ignored:
            rows = rows.exclude(pk__in=ignored)
        count = rows.count()
        if count:
            holders[related._meta.label_lower] = count
    return holders


def _depth(row, parents):
    depth, current, seen = 0, parents.get(row.pk), set()
    while current and current not in seen:
        seen.add(current)
        depth += 1
        current = parents.get(current)
    return depth


def _candidates(context, selection):
    """Every retained container of the context, or the selected ids per kind."""
    chosen = {}
    for key, model, _, _ in KINDS:
        rows = model._base_manager.filter(retention_context=context).order_by('pk')
        if selection is not None:
            rows = rows.filter(pk__in=selection.get(key, []))
        chosen[key] = list(rows)
    return chosen


def preview_discard(context_id, selection=None):
    context = ProjectRetentionContext.objects.get(pk=context_id)
    chosen = _candidates(context, selection)
    discarding = {model._meta.label_lower: {row.pk for row in chosen[key]} for key, model, _, _ in KINDS}
    containers, blockers = [], []
    for key, model, label_field, parent_field in KINDS:
        parents = {row.pk: getattr(row, parent_field) for row in chosen[key]} if parent_field == 'parent_id' else {}
        for row in sorted(chosen[key], key=lambda item: (-_depth(item, parents), item.pk)):
            holders = _holders(row, discarding)
            containers.append({'kind': key, 'id': row.pk, 'label': getattr(row, label_field), 'holders': holders})
            if holders:
                blockers.append({'code': 'not_empty', 'kind': key, 'id': row.pk,
                                 'message': f'«{getattr(row, label_field)}» todavía contiene o referencia datos.'})
    if not containers:
        blockers.append({'code': 'nothing_to_discard', 'message': 'No hay contenedores conservados para eliminar.'})
    if selection is not None:
        found = {(item['kind'], item['id']) for item in containers}
        missing = sorted((key, pk) for key, ids in selection.items() for pk in ids if (key, pk) not in found)
        if missing:
            blockers.append({'code': 'not_in_context', 'message': 'Algunos contenedores no pertenecen a estos datos conservados.',
                             'records': [{'kind': key, 'id': pk} for key, pk in missing]})
    impact = {'context_id': context.pk, 'project_name': context.project_name,
              'containers': containers, 'blockers': blockers}
    impact['impact_hash'] = _digest(impact)
    return impact


@transaction.atomic
def discard_empty_containers(context_id, *, actor, reason, request_id, expected_impact_hash, selection=None):
    payload_hash = _digest({'context_id': context_id, 'selection': selection, 'reason': reason})
    existing = ProjectRetentionOperation.objects.filter(request_id=request_id).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise RetentionConflict({'detail': 'Este request_id pertenece a otra operación.', 'code': 'request_conflict'})
        return {'operation_id': existing.pk, 'deleted': len(existing.items), 'idempotent': True}
    context = ProjectRetentionContext.objects.select_for_update().get(pk=context_id)
    DocumentFolderMutationLock.objects.get_or_create(pk=1)
    DocumentFolderMutationLock.objects.select_for_update().get(pk=1)
    impact = preview_discard(context_id, selection)
    if impact['impact_hash'] != expected_impact_hash:
        raise RetentionConflict({'detail': 'Los contenedores cambiaron. Revisa de nuevo la vista previa.', 'code': 'stale_impact'})
    if impact['blockers']:
        raise RetentionConflict({'detail': 'Sólo se eliminan contenedores vacíos.', 'code': 'discard_blocked',
                                 'blockers': impact['blockers']})
    models = {key: model for key, model, _, _ in KINDS}
    rows, items = [], []
    for container in impact['containers']:
        row = models[container['kind']]._base_manager.get(pk=container['id'])
        rows.append(row)
        items.append({'model': row._meta.label_lower, 'id': row.pk, 'label': container['label']})
    removed = remove_from_inventory(context, rows)
    for row in rows:  # already ordered: threads, then folders leaf first
        type(row)._base_manager.filter(pk=row.pk, retention_context=context).delete()
    operation = ProjectRetentionOperation.objects.create(
        context=context, operation=ProjectRetentionOperation.Operation.DISCARD, origin='discard',
        request_id=request_id, payload_hash=payload_hash, reason=reason, items=items,
        removed_records=removed, actor=actor,
    )
    return {'operation_id': operation.pk, 'deleted': len(items), 'idempotent': False}
