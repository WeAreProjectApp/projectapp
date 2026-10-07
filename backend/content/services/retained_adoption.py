"""Audited exit from retention into a live project of the same client.

A forced project deletion keeps the unselected rows without a project and with
``retention_context``; ``RetainedProjectModel`` makes them read-only. Adoption
is the only sanctioned way out: a live target of the SAME client, an explicit
confirmation by the caller (the assign flow's preview and confirm), one
operation per retention context that records the ownership values before and
after, and an exact undo while nothing changed afterwards. The model guard
keeps refusing every other write.
"""
import hashlib
import json
import re
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import CASCADE, Q
from rest_framework.exceptions import ValidationError

from content.models import (
    CommunicationFolder, CommunicationThread, Document, DocumentFolder, HostingRecord,
    IncomeRecord, ProjectRetentionContext, ProjectRetentionOperation,
)
from content.services.entity_history import capture_instance, historical_write

OWNERSHIP_FIELDS = {
    'content.incomerecord': ('project_id', 'retention_context_id'),
    'content.hostingrecord': ('project_id', 'retention_context_id'),
    'content.document': ('project_id', 'folder_id', 'retention_context_id'),
    'content.communicationthread': ('project_id', 'folder_id', 'retention_context_id'),
    'accounts.projectphase': ('project_id', 'order', 'retention_context_id'),
    'accounts.deliverable': ('project_id', 'source_proposal_id', 'retention_context_id'),
}
MIN_TITLE_FOR_HINT = 8
HINTS_PER_ROW = 3


class RetentionConflict(ValidationError):
    status_code = 409


def ownership(row):
    """Ownership values an adoption changes, plus the edit stamp undo compares."""
    values = {name: getattr(row, name) for name in OWNERSHIP_FIELDS[row._meta.label_lower]}
    stamp = getattr(row, 'updated_at', None)
    values['updated_at'] = stamp.isoformat() if stamp else None
    return values


def _reload(row):
    return type(row)._base_manager.get(pk=row.pk)


# ── Duplicate hints (non-blocking) ───────────────────────────────────────────

def normalized(text):
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(char for char in text if not unicodedata.combining(char)).casefold()
    return re.sub(r'[^0-9a-z]+', ' ', text).strip()


def _similar(left, right):
    if len(left) < MIN_TITLE_FOR_HINT or len(right) < MIN_TITLE_FOR_HINT:
        return left == right and bool(left)
    return left == right or left.startswith(right) or right.startswith(left)


def duplicate_hints(row_key, title, candidates):
    """Up to three other rows whose normalized title looks like this one."""
    title = normalized(title)
    return [
        {'id': key[1], 'label': label}
        for key, (label, other) in candidates.items()
        if key != row_key and _similar(title, other)
    ][:HINTS_PER_ROW]


def hint_candidates(rows, label_of, extra=()):
    """{(kind, pk): (label, normalized label)} for rows and extra (kind, pk, label) triples."""
    candidates = {(row._meta.label_lower, row.pk): (label_of(row), normalized(label_of(row))) for row in rows}
    for kind, pk, label in extra:
        candidates.setdefault((kind, pk), (label, normalized(label)))
    return candidates


def retained_tag(record):
    """Where a row of the assign plan comes from, when it was retained."""
    if not record.retention_context_id:
        return None
    return {'context_id': record.retention_context_id,
            'project_name': record.retention_context.project_name}


def retained_threads(project):
    """The client's communication threads retained from a deleted project."""
    return (CommunicationThread._base_manager
            .filter(client__user=project.client, project__isnull=True, retention_context__isnull=False)
            .select_related('retention_context').order_by('pk'))


def _income_key(concept, period, kind):
    return normalized(concept), period.strftime('%Y-%m') if period else '', kind


def unlinked_hints(project, *, incomes, documents, threads):
    """Possible duplicates of each retained row, in the plan or already in the target."""
    hints = {}
    pool = [(row.pk, row.concept, row.period_date, row.kind) for row in incomes]
    pool += list(IncomeRecord.objects.filter(project=project).values_list('pk', 'concept', 'period_date', 'kind'))
    for row in incomes:
        if row.retention_context_id:
            key = _income_key(row.concept, row.period_date, row.kind)
            hints[('content.incomerecord', row.pk)] = [
                {'id': pk, 'label': concept} for pk, concept, period, kind in pool
                if pk != row.pk and _income_key(concept, period, kind) == key
            ][:HINTS_PER_ROW]
    document_pool = hint_candidates(documents, lambda row: row.title, extra=[
        ('content.document', pk, title)
        for pk, title in Document.objects.filter(project=project, is_archived=False).values_list('pk', 'title')
    ])
    for row in documents:
        if row.retention_context_id:
            hints[('content.document', row.pk)] = duplicate_hints(('content.document', row.pk), row.title, document_pool)
    thread_pool = hint_candidates(threads, lambda row: row.title, extra=[
        ('content.communicationthread', pk, title)
        for pk, title in CommunicationThread.objects.filter(project=project).values_list('pk', 'title')
    ])
    for row in threads:
        hints[('content.communicationthread', row.pk)] = duplicate_hints(
            ('content.communicationthread', row.pk), row.title, thread_pool,
        )
    return hints


# ── Closure, inventory and operation bookkeeping ─────────────────────────────

def billing_closure(context, income_ids, hosting_ids, document_ids):
    """Retained rows that must leave retention together so billing pairs stay whole.

    An expected income moves with its liquid children (and a child with its
    parent), and every cuenta moves with the income or hosting it bills: a
    settlement requires both on the same project.
    """
    incomes, hostings, documents = set(income_ids), set(hosting_ids), set(document_ids)
    retained_incomes = IncomeRecord._base_manager.filter(retention_context=context)
    retained_documents = Document._base_manager.filter(retention_context=context)
    while True:
        size = len(incomes) + len(hostings) + len(documents)
        parents = IncomeRecord._base_manager.filter(pk__in=incomes).values('expected_income_id')
        incomes |= set(retained_incomes.filter(Q(expected_income_id__in=incomes) | Q(pk__in=parents))
                       .values_list('pk', flat=True))
        documents |= set(retained_documents.filter(Q(income_record_id__in=incomes) | Q(hosting_record_id__in=hostings))
                         .values_list('pk', flat=True))
        linked = list(Document._base_manager.filter(pk__in=documents).values_list('income_record_id', 'hosting_record_id'))
        incomes |= set(retained_incomes.filter(pk__in=[pk for pk, _ in linked if pk]).values_list('pk', flat=True))
        hostings |= set(HostingRecord._base_manager.filter(retention_context=context, pk__in=[pk for _, pk in linked if pk])
                        .values_list('pk', flat=True))
        if len(incomes) + len(hostings) + len(documents) == size:
            return incomes, hostings, documents


def cascade_followers(model, ids):
    """{model_label: ids} of rows that follow these rows (CASCADE), recursively."""
    found = defaultdict(set)
    frontier = [(model, set(ids))]
    while frontier:
        current, pks = frontier.pop()
        for relation in current._meta.related_objects:
            if relation.many_to_many or relation.on_delete is not CASCADE:
                continue
            related = relation.related_model
            children = set(related._base_manager.filter(**{f'{relation.field.name}__in': pks})
                           .values_list('pk', flat=True))
            new = children - found[related._meta.label_lower]
            if new:
                found[related._meta.label_lower] |= new
                frontier.append((related, new))
    return found


def remove_from_inventory(context, rows):
    """Take adopted rows (and what follows them) out of the consultation index."""
    by_model = defaultdict(set)
    for row in rows:
        by_model[type(row)].add(row.pk)
    leaving = defaultdict(set)
    for model, pks in by_model.items():
        leaving[model._meta.label_lower] |= pks
        for label, followers in cascade_followers(model, pks).items():
            leaving[label] |= followers
    index = {label: list(ids) for label, ids in context.retained_records.items()}
    removed = {}
    for label, pks in leaving.items():
        listed = index.get(label, [])
        leaving_ids = {str(value) for value in pks}
        gone = [pk for pk in listed if pk in leaving_ids]
        if gone:
            removed[label] = gone
            index[label] = [pk for pk in listed if pk not in gone]
    context.retained_records = {label: ids for label, ids in index.items() if ids}
    context.save(update_fields=['retained_records'])
    return removed


def restore_inventory(context, removed):
    index = {label: list(ids) for label, ids in context.retained_records.items()}
    for label, ids in removed.items():
        index[label] = sorted(set(index.get(label, [])) | set(ids), key=lambda value: (len(value), value))
    context.retained_records = index
    context.save(update_fields=['retained_records'])


def _project_root(target):
    """The target's managed root; without one, documents keep their folder."""
    from content.services.project_document_folder_service import require_project_folder
    try:
        return require_project_folder(target)
    except RuntimeError:
        return None


# ── Adoption through the assign flow ─────────────────────────────────────────

@dataclass
class PendingAdoption:
    """Released rows waiting for the assign services; ``finish`` audits them."""
    target: object
    actor: object
    origin: str
    reason: str
    income_ids: list = field(default_factory=list)
    hosting_ids: list = field(default_factory=list)
    document_ids: list = field(default_factory=list)
    threads: list = field(default_factory=list)
    groups: list = field(default_factory=list)  # [(context, [(row, before)])]

    def finish(self):
        operations = []
        for context, released in self.groups:
            items = []
            for row, before in released:
                current = _reload(row)
                items.append({'model': row._meta.label_lower, 'id': row.pk,
                              'before': before, 'after': ownership(current)})
            removed = remove_from_inventory(context, [row for row, _ in released])
            operation = ProjectRetentionOperation.objects.create(
                context=context, operation=ProjectRetentionOperation.Operation.ADOPT,
                origin=self.origin, target_project_id=self.target.pk,
                target_project_name=self.target.name, request_id=uuid.uuid4().hex,
                reason=self.reason, items=items, removed_records=removed, actor=self.actor,
            )
            operations.append({'operation_id': operation.pk, 'context_id': context.pk,
                               'project_name': context.project_name, 'records': len(items)})
        return operations


def _thread_updates(thread, target):
    folder = None
    if thread.folder_id:
        current = CommunicationFolder._base_manager.get(pk=thread.folder_id)
        if not current.retention_context_id and current.project_id in (None, target.pk):
            folder = current.pk
    return {'project_id': target.pk, 'folder_id': folder}


def _document_updates(document, root):
    if document.folder_id and DocumentFolder._base_manager.filter(
            pk=document.folder_id, retention_context__isnull=False).exists():
        return {'folder_id': root.pk}
    return {}


def _release(context, rows, *, target, root):
    released = []
    for row in rows:
        before = ownership(row)
        capture_instance(row)
        updates = {'retention_context_id': None}
        if isinstance(row, CommunicationThread):
            updates.update(_thread_updates(row, target))
        elif isinstance(row, Document) and root is not None:
            updates.update(_document_updates(row, root))
        changed = type(row)._base_manager.filter(pk=row.pk, retention_context=context).update(**updates)
        if changed != 1:
            raise RetentionConflict({'detail': 'Los datos conservados cambiaron mientras confirmabas. Revisa la lista de nuevo.',
                                     'code': 'stale_retention'})
        released.append((row, before))
    return released


def _client_user_id(row):
    if isinstance(row, Document):
        return row.client_user_id
    profile = row.client
    return profile.user_id if profile is not None else None


@historical_write
@transaction.atomic
def adopt_for_assignment(target, *, actor, income_ids=(), hosting_ids=(), document_ids=(),
                         thread_ids=(), reason='', origin='assign_unlinked'):
    """Release the retained rows of an assign plan; the caller then assigns them.

    Returns a :class:`PendingAdoption` whose id lists include the billing
    closure, so the existing assign services move cuentas and children together
    with full accounting audit. Threads are assigned here (no assign service).
    """
    pending = PendingAdoption(target=target, actor=actor, origin=origin,
                              reason=reason or 'Asignación de registros sin proyecto',
                              income_ids=list(income_ids), hosting_ids=list(hosting_ids),
                              document_ids=list(document_ids))
    selected = {
        IncomeRecord: IncomeRecord._base_manager.filter(pk__in=income_ids, retention_context__isnull=False),
        HostingRecord: HostingRecord._base_manager.filter(pk__in=hosting_ids, retention_context__isnull=False),
        Document: Document._base_manager.filter(pk__in=document_ids, retention_context__isnull=False),
        CommunicationThread: CommunicationThread._base_manager.filter(pk__in=thread_ids, retention_context__isnull=False),
    }
    by_context = defaultdict(lambda: defaultdict(set))
    for model, rows in selected.items():
        for pk, context_id in rows.values_list('pk', 'retention_context_id'):
            by_context[context_id][model].add(pk)
    unknown_threads = set(thread_ids) - by_context_ids(by_context, CommunicationThread)
    if unknown_threads:
        raise RetentionConflict({'detail': 'Sólo se asignan aquí los hilos conservados de este cliente.',
                                 'code': 'records_changed', 'changed_ids': sorted(unknown_threads)})
    if not by_context:
        return pending
    root = None
    contexts = ProjectRetentionContext.objects.select_for_update().filter(pk__in=by_context).order_by('pk')
    for context in contexts:
        if context.client_id != target.client_id:
            raise RetentionConflict({'detail': f'Los datos conservados de «{context.project_name}» pertenecen a otro cliente.',
                                     'code': 'different_client'})
        ids = by_context[context.pk]
        incomes, hostings, documents = billing_closure(context, ids[IncomeRecord], ids[HostingRecord], ids[Document])
        if documents and root is None:
            root = _project_root(target)
        rows = (list(IncomeRecord._base_manager.filter(pk__in=incomes, retention_context=context).select_related('client'))
                + list(HostingRecord._base_manager.filter(pk__in=hostings, retention_context=context).select_related('client'))
                + list(Document._base_manager.filter(pk__in=documents, retention_context=context))
                + list(CommunicationThread._base_manager.filter(pk__in=ids[CommunicationThread], retention_context=context)
                       .select_related('client')))
        foreign = sorted(row.pk for row in rows if _client_user_id(row) not in (None, target.client_id))
        if foreign:
            raise RetentionConflict({'detail': 'Hay registros conservados de otro cliente en esta selección.',
                                     'code': 'different_client', 'changed_ids': foreign})
        released = _release(context, rows, target=target, root=root)
        pending.groups.append((context, released))
        # Liquid children whose expected parent also moves are rewritten by the
        # assign service's own cascade; listing them again would audit them twice.
        moving = set(pending.income_ids) | incomes
        parents = dict(IncomeRecord._base_manager.filter(pk__in=incomes).values_list('pk', 'expected_income_id'))
        cascaded = {pk for pk, parent in parents.items() if parent in moving}
        pending.income_ids = sorted(moving - cascaded)
        pending.hosting_ids = sorted(set(pending.hosting_ids) | hostings)
        pending.document_ids = sorted(set(pending.document_ids) | documents)
        pending.threads += [row for row, _ in released if isinstance(row, CommunicationThread)]
    return pending


def by_context_ids(by_context, model):
    return {pk for ids in by_context.values() for pk in ids[model]}


# ── Undo ─────────────────────────────────────────────────────────────────────

_MODELS = {
    'content.incomerecord': IncomeRecord, 'content.hostingrecord': HostingRecord,
    'content.document': Document, 'content.communicationthread': CommunicationThread,
}


def _current_items(operation):
    rows = []
    for item in operation.items:
        model = _MODELS.get(item['model'])
        row = model._base_manager.filter(pk=item['id']).first() if model else None
        rows.append((item, row))
    return rows


def preview_undo(operation_id):
    operation = ProjectRetentionOperation.objects.select_related('context').get(pk=operation_id)
    blockers = []
    if operation.operation != ProjectRetentionOperation.Operation.ADOPT:
        blockers.append({'code': 'not_undoable', 'message': 'Sólo se deshace un traslado; los descartes y reasignaciones no.'})
    if hasattr(operation, 'reverted_by'):
        blockers.append({'code': 'already_reverted', 'message': 'Este traslado ya se deshizo.'})
    changed = []
    for item, row in _current_items(operation):
        if row is None or ownership(row) != item['after']:
            changed.append({'model': item['model'], 'id': item['id']})
    if changed:
        blockers.append({'code': 'changed_since', 'message': 'Algunos registros cambiaron después del traslado; '
                         'deshacerlo pisaría esos cambios.', 'records': changed})
    impact = {
        'operation_id': operation.pk, 'context_id': operation.context_id,
        'project_name': operation.context.project_name, 'target_project_id': operation.target_project_id,
        'target_project_name': operation.target_project_name, 'created_at': operation.created_at.isoformat(),
        'records': [{'model': item['model'], 'id': item['id']} for item in operation.items],
        'blockers': blockers,
    }
    impact['impact_hash'] = hashlib.sha256(json.dumps(impact, sort_keys=True, default=str).encode()).hexdigest()
    return impact


@historical_write
@transaction.atomic
def undo_adoption(operation_id, *, actor, reason, request_id, expected_impact_hash):
    existing = ProjectRetentionOperation.objects.filter(request_id=request_id).first()
    if existing:
        if existing.reverts_id != operation_id:
            raise RetentionConflict({'detail': 'Este request_id pertenece a otra operación.', 'code': 'request_conflict'})
        return {'operation_id': existing.pk, 'reverts': operation_id, 'idempotent': True}
    operation = ProjectRetentionOperation.objects.select_for_update().select_related('context').get(pk=operation_id)
    context = ProjectRetentionContext.objects.select_for_update().get(pk=operation.context_id)
    impact = preview_undo(operation_id)
    if impact['impact_hash'] != expected_impact_hash:
        raise RetentionConflict({'detail': 'El traslado cambió. Revisa de nuevo la vista previa.', 'code': 'stale_impact'})
    if impact['blockers']:
        raise RetentionConflict({'detail': 'No se puede deshacer este traslado.', 'code': 'undo_blocked',
                                 'blockers': impact['blockers']})
    from content.services import accounting_service
    from content.services.accounting_service import EntityType
    rows = _current_items(operation)
    ids = defaultdict(list)
    for item, row in rows:
        ids[item['model']].append(row.pk)
    # Clear the project through the accounting writers so the ledger audits the
    # reversal like any other edit; the raw restore below then re-marks retention.
    if ids['content.incomerecord']:
        accounting_service.bulk_assign_project(EntityType.INCOME, ids['content.incomerecord'], None, actor)
    if ids['content.hostingrecord']:
        accounting_service.bulk_assign_project(EntityType.HOSTING, ids['content.hostingrecord'], None, actor)
    if ids['content.document']:
        accounting_service.assign_project_to_documents(ids['content.document'], None, actor)
    items = []
    for item, row in rows:
        current = _reload(row)
        capture_instance(current)
        restore = {name: value for name, value in item['before'].items() if name != 'updated_at'}
        type(current)._base_manager.filter(pk=current.pk).update(**restore)
        items.append({'model': item['model'], 'id': item['id'], 'before': ownership(current),
                      'after': ownership(_reload(current))})
    restore_inventory(context, operation.removed_records)
    undo = ProjectRetentionOperation.objects.create(
        context=context, operation=ProjectRetentionOperation.Operation.UNDO, origin='undo',
        target_project_id=operation.target_project_id, target_project_name=operation.target_project_name,
        request_id=request_id, reason=reason, items=items, reverts=operation, actor=actor,
    )
    return {'operation_id': undo.pk, 'reverts': operation.pk, 'idempotent': False, 'records': len(items)}
