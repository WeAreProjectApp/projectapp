"""Scan, preview, apply and undo: the only entry points views and tools call.

Apply and undo follow the retained-adoption contract
(``content.services.retained_adoption``): a hash-bound preview, an idempotent
``request_id``, locks, a recomputed preview under the locks, and nothing but
raised exceptions once a write happened (a handled 4xx would let the history
middleware commit).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from content.models import DataIntegrityOperation
from content.services.data_integrity import catalog
from content.services.data_integrity.hashing import digest
from content.services.data_integrity.snapshots import diff_items, model_for, snapshot_many
from content.services.data_integrity.types import (
    DOMAIN_LABELS, EXISTING_TOOL, MERGE_CLIENTS, REPORT_ONLY, IntegrityConflict, blocker,
)
from content.services.entity_history import capture_instance, current_history_operation_id, historical_write

MAX_FIXES = 20
MAX_CLOSURE = 500
PAGE_SIZE = 50
OPERATIONS_PAGE_SIZE = 20
# Rows are locked model by model in this order, each model by pk.
LOCK_ORDER = (
    'accounts.project', 'accounts.userprofile', 'auth.user', 'content.businessproposal',
    'content.incomerecord', 'content.hostingrecord', 'content.document', 'content.documentfolder',
    'content.communicationfolder', 'content.communicationthread', 'accounts.projectphase',
    'content.proposalsection',
)


def current_source(default):
    from content.mcp.context import current_mcp_context
    context = current_mcp_context()
    return f'mcp:{context.connector.slug}' if context else default


# ── Scan ─────────────────────────────────────────────────────────────────────

def select_rules(scope, *, domains=None, rule_ids=None, severity=None):
    selected = []
    for item in catalog.rules():
        if domains and item.domain not in domains:
            continue
        if rule_ids and item.id not in rule_ids:
            continue
        if severity and item.severity not in severity:
            continue
        if item.full_sweep_only and not scope.is_all:
            continue
        selected.append(item)
    return selected


def stamp(item, finding):
    """Fill the fingerprint and default fix kinds of a freshly detected finding."""
    finding.fingerprint = digest({
        'r': item.id, 'v': item.version,
        's': sorted([subject.model, subject.pk] for subject in finding.subjects),
        'e': finding.evidence,
    })
    if not finding.fix_kinds:
        finding.fix_kinds = item.fix_kinds
    return finding


def detect(item, scope):
    return [stamp(item, finding) for finding in item.detect(scope)]


def scan(scope, **filters):
    """[(rule, finding)] in catalog order."""
    return [(item, finding) for item in select_rules(scope, **filters) for finding in detect(item, scope)]


def finding_payload(item, finding):
    fixable = [kind for kind in finding.fix_kinds
               if kind not in (REPORT_ONLY, EXISTING_TOOL) and catalog.get_fixer(item.id, kind)]
    return {
        'fingerprint': finding.fingerprint, 'rule_id': item.id, 'rule_version': item.version,
        'domain': item.domain, 'severity': item.severity, 'title': item.title,
        'message': finding.message or item.description,
        'subjects': [subject.payload() for subject in finding.subjects],
        'evidence': finding.evidence, 'fix_kinds': list(finding.fix_kinds),
        'fixable_kinds': fixable, 'inputs': finding.inputs, 'suggestion': finding.suggestion,
        'tool': finding.tool,
    }


def findings_payload(scope, *, page=1, **filters):
    found = [finding_payload(item, finding) for item, finding in scan(scope, **filters)]
    by_domain, by_rule = {}, {}
    for row in found:
        by_domain[row['domain']] = by_domain.get(row['domain'], 0) + 1
        by_rule[row['rule_id']] = by_rule.get(row['rule_id'], 0) + 1
    pages = max(1, -(-len(found) // PAGE_SIZE))
    return {
        'catalog_version': catalog.CATALOG_VERSION, 'scope': scope.payload(),
        'count': len(found), 'page': page, 'pages': pages,
        'summary': {
            'by_domain': [{'domain': key, 'label': DOMAIN_LABELS[key], 'count': value}
                          for key, value in by_domain.items()],
            'by_rule': by_rule,
            'fixable': sum(1 for row in found if row['fixable_kinds']),
            'needs_input': sum(1 for row in found if row['fixable_kinds'] and row['inputs']),
            'existing_tool': sum(1 for row in found if EXISTING_TOOL in row['fix_kinds']),
            'report_only': sum(1 for row in found if row['fix_kinds'] == [REPORT_ONLY]),
        },
        'results': found[(page - 1) * PAGE_SIZE:page * PAGE_SIZE],
    }


# ── Preview ──────────────────────────────────────────────────────────────────

def _current_findings(scope, fixes):
    current = {}
    for rule_id in sorted({selection['rule_id'] for selection in fixes}):
        item = catalog.get_rule(rule_id)
        if item is not None:
            for finding in detect(item, scope):
                current[finding.fingerprint] = (item, finding)
    return current


def _plan_step(selection, entry, *, actor):
    params = selection.get('params') or {}
    step = {'fingerprint': selection['fingerprint'], 'rule_id': selection['rule_id'], 'rule_version': None,
            'fix_kind': selection.get('fix_kind'), 'params': params, 'subjects': [], 'changes': [],
            'closure': [], 'guards': {}, 'warnings': [], 'blockers': []}
    if entry is None or entry[0].id != selection['rule_id']:
        step['blockers'].append(blocker('finding_resolved', 'Este hallazgo ya no aparece: '
                                        'alguien lo corrigió o cambió. Vuelve a revisar.'))
        return step, None
    item, finding = entry
    fixable = [kind for kind in finding.fix_kinds if kind not in (REPORT_ONLY, EXISTING_TOOL)]
    kind = selection.get('fix_kind') or (fixable[0] if fixable else finding.fix_kinds[0])
    step.update(fix_kind=kind, rule_version=item.version,
                subjects=[subject.payload() for subject in finding.subjects])
    if kind == REPORT_ONLY:
        step['blockers'].append(blocker('report_only', 'Este hallazgo sólo se informa: se resuelve a mano.'))
        return step, None
    if kind == EXISTING_TOOL:
        step['blockers'].append({**blocker('existing_tool', 'Se corrige con otra herramienta, '
                                           'con su propia vista previa.'), 'tool': finding.tool})
        return step, None
    fixer = catalog.get_fixer(item.id, kind) if kind in finding.fix_kinds else None
    if fixer is None:
        step['blockers'].append(blocker('fix_kind_unavailable', 'Esa corrección no está disponible '
                                        'para este hallazgo.'))
        return step, None
    plan = fixer.plan(finding, params, actor=actor)
    step.update(changes=plan.changes, closure=sorted({(label, pk) for label, pk in plan.closure}),
                guards=plan.guards, warnings=plan.warnings, blockers=list(plan.blockers))
    return step, (item, finding, fixer, plan)


def _batch_blockers(steps, plans):
    found = []
    exclusive = [entry[2] for entry in plans if entry and entry[2].exclusive]
    if exclusive and len(steps) > 1:
        found.append(blocker('exclusive_fix', 'Una fusión se aplica sola, sin otras correcciones en el lote.'))
    owners, overlaps = {}, set()
    for step in steps:
        for key in step['closure']:
            if owners.setdefault(key, step['fingerprint']) != step['fingerprint']:
                overlaps.add(key)
    if overlaps:
        found.append(blocker('overlapping_fixes', 'Dos correcciones del lote tocan los mismos registros; '
                             'aplícalas en lotes separados.',
                             [{'model': label, 'id': pk} for label, pk in sorted(overlaps)]))
    cap = (exclusive[0].max_closure or MAX_CLOSURE) if exclusive else MAX_CLOSURE
    if len(owners) > cap:
        found.append(blocker('batch_too_large', f'El lote toca {len(owners)} registros; el máximo es {cap}. '
                             'Elige menos correcciones.'))
    return found, sorted(owners)


def _build(scope, fixes, *, actor):
    current = _current_findings(scope, fixes)
    steps, plans = [], []
    for selection in fixes:
        step, entry = _plan_step(selection, current.get(selection['fingerprint']), actor=actor)
        steps.append(step)
        plans.append(entry)
    batch, keys = _batch_blockers(steps, plans)
    before = snapshot_many(keys)
    basis = {
        'catalog_version': catalog.CATALOG_VERSION, 'scope': scope.payload(), 'blockers': batch,
        'steps': [{**step, 'closure': [[label, pk, before[(label, pk)]] for label, pk in step['closure']]}
                  for step in steps],
    }
    impact = {
        'catalog_version': catalog.CATALOG_VERSION, 'scope': scope.payload(), 'blockers': batch,
        'steps': [{**step, 'closure': len(step['closure'])} for step in steps],
        'records': len(keys), 'impact_hash': digest(basis),
    }
    impact['blocked'] = bool(batch or any(step['blockers'] for step in steps))
    return impact, plans, keys


def preview_fixes(scope, fixes, *, actor):
    impact, _, _ = _build(scope, fixes, actor=actor)
    return impact


# ── Apply ────────────────────────────────────────────────────────────────────

def lock_rows(keys):
    """Lock a closure in the shared model order, then primary-key order."""
    by_model = {}
    for label, pk in keys:
        by_model.setdefault(label, []).append(pk)
    rank = {label: index for index, label in enumerate(LOCK_ORDER)}
    for label in sorted(by_model, key=lambda name: (rank.get(name, len(rank)), name)):
        model = model_for(label)
        pks = [model._meta.pk.to_python(pk) for pk in by_model[label]]
        list(model._base_manager.select_for_update()
             .filter(pk__in=pks).order_by('pk').values_list('pk', flat=True))


def _lock_folder_tree(keys, *, steps):
    # Client merge adapters take the mutex even when no folder rows are recorded.
    if (any(label == 'content.documentfolder' for label, _ in keys)
            or any(step['fix_kind'] == MERGE_CLIENTS for step in steps)):
        from content.services.document_folder_merge import lock_folder_tree
        lock_folder_tree()


def _payload_hash(scope, fixes, reason):
    return digest({'scope': scope.payload(), 'fixes': fixes, 'reason': reason})


def _replay(request_id, payload_hash=None, reverts_id=None):
    existing = DataIntegrityOperation.objects.filter(request_id=request_id).first()
    if existing is None:
        return None
    same = (existing.payload_hash == payload_hash if payload_hash is not None
            else existing.reverts_id == reverts_id)
    if not same:
        raise IntegrityConflict('Este request_id ya se usó para otra operación.', code='request_conflict')
    return {**operation_summary(existing), 'idempotent': True}


def _still_detected(item, finding, scope):
    return any(other.fingerprint == finding.fingerprint for other in detect(item, scope))


@historical_write
@transaction.atomic
def apply_fixes(scope, fixes, *, actor, reason, request_id, expected_impact_hash, source='service'):
    payload_hash = _payload_hash(scope, fixes, reason)
    replay = _replay(request_id, payload_hash=payload_hash)
    if replay:
        return replay
    impact, _, keys = _build(scope, fixes, actor=actor)
    _lock_folder_tree(keys, steps=impact['steps'])
    lock_rows(keys)
    impact, plans, keys = _build(scope, fixes, actor=actor)
    if impact['impact_hash'] != expected_impact_hash:
        raise IntegrityConflict('Los datos cambiaron desde la vista previa. Revísala de nuevo.', code='stale_impact')
    if impact['blocked']:
        raise IntegrityConflict('El lote tiene bloqueos.', code='apply_blocked',
                                blockers=impact['blockers'] + [
                                    {**entry, 'fingerprint': step['fingerprint']}
                                    for step in impact['steps'] for entry in step['blockers']])
    recorded = []
    for step, (item, finding, fixer, plan) in zip(impact['steps'], plans):
        closure = sorted({(label, pk) for label, pk in plan.closure})
        before = snapshot_many(closure)
        fixer.apply(plan, actor=actor)
        after = snapshot_many(closure)
        if _still_detected(item, finding, scope):
            raise IntegrityConflict(f'La corrección de {item.id} no resolvió el hallazgo; no se aplicó nada.',
                                    code='fix_ineffective', fingerprint=finding.fingerprint)
        recorded.append({
            'fingerprint': finding.fingerprint, 'rule_id': item.id, 'rule_version': item.version,
            'fix_kind': plan.fix_kind, 'params': plan.params, 'subjects': step['subjects'],
            'guards': plan.guards, 'items': diff_items(before, after),
        })
    try:
        with transaction.atomic():
            operation = DataIntegrityOperation.objects.create(
                kind=DataIntegrityOperation.Kind.APPLY, source=current_source(source),
                catalog_version=catalog.CATALOG_VERSION, scope=scope.payload(), request_id=request_id,
                payload_hash=payload_hash, impact_hash=impact['impact_hash'], reason=reason,
                steps=recorded, history_operation_id=current_history_operation_id(), actor=actor,
            )
    except IntegrityError:
        replay = _replay(request_id, payload_hash=payload_hash)
        if replay:
            return replay
        raise
    return operation_summary(operation)


# ── Undo ─────────────────────────────────────────────────────────────────────

def _item_keys(operation):
    return sorted({(item['model'], item['pk']) for step in operation.steps for item in step['items']})


def _guard_blockers(operation):
    found = []
    for step in operation.steps:
        fixer = catalog.get_fixer(step['rule_id'], step['fix_kind'])
        check = getattr(fixer, 'guards_changed', None)
        if check is None:
            continue
        changed = check(step)
        if isinstance(changed, (list, tuple)):
            found.extend({**entry, 'rule_id': step['rule_id']} for entry in changed)
        elif changed:
            found.append({**blocker('guard_changed', f'Cambió algo de lo que dependía la corrección {step["rule_id"]}; '
                                   'deshacerla dejaría datos incoherentes.'), 'rule_id': step['rule_id']})
    return found


def preview_undo(operation_id):
    operation = get_object_or_404(DataIntegrityOperation, pk=operation_id)
    blockers = []
    if operation.kind != DataIntegrityOperation.Kind.APPLY:
        blockers.append(blocker('not_undoable', 'Un deshacer no se deshace; aplica la corrección de nuevo.'))
    if DataIntegrityOperation.objects.filter(reverts=operation).exists():
        blockers.append(blocker('already_reverted', 'Esta corrección ya se deshizo.'))
    current = snapshot_many(_item_keys(operation))
    changed = []
    for step in operation.steps:
        for item in step['items']:
            row = current[(item['model'], item['pk'])]
            if row is None or row.get(item['field']) != item['after']:
                changed.append({'model': item['model'], 'id': item['pk'], 'field': item['field']})
    if changed:
        blockers.append({**blocker('changed_since', 'Algunos registros cambiaron después de la corrección; '
                                   'deshacerla pisaría esos cambios.'), 'records': changed})
    blockers += _guard_blockers(operation)
    impact = {
        'operation_id': operation.pk, 'created_at': operation.created_at.isoformat(),
        'reason': operation.reason, 'scope': operation.scope,
        'steps': [{'rule_id': step['rule_id'], 'fix_kind': step['fix_kind'], 'subjects': step['subjects'],
                   'items': len([item for item in step['items'] if not item['guard']])}
                  for step in operation.steps],
        'blockers': blockers,
    }
    impact['impact_hash'] = digest(impact)
    impact['blocked'] = bool(blockers)
    return impact


def _restore_exact(step):
    """Write back every recorded non-guard field that still differs from ``before``."""
    keys = sorted({(item['model'], item['pk']) for item in step['items']})
    current = snapshot_many(keys)
    pending = {}
    for item in reversed(step['items']):
        row = current[(item['model'], item['pk'])]
        if not item['guard'] and row is not None and row.get(item['field']) != item['before']:
            pending.setdefault((item['model'], item['pk']), {})[item['field']] = item['before']
    for (label, pk), values in pending.items():
        model = model_for(label)
        pk = model._meta.pk.to_python(pk)
        capture_instance(model._base_manager.get(pk=pk))
        model._base_manager.filter(pk=pk).update(**values)


@historical_write
@transaction.atomic
def undo_operation(operation_id, *, actor, reason, request_id, expected_impact_hash, source='service'):
    replay = _replay(request_id, reverts_id=operation_id)
    if replay:
        return replay
    operation = get_object_or_404(DataIntegrityOperation, pk=operation_id)
    keys = _item_keys(operation)
    _lock_folder_tree(keys, steps=operation.steps)
    operation = get_object_or_404(DataIntegrityOperation.objects.select_for_update(), pk=operation_id)
    lock_rows(keys)
    impact = preview_undo(operation_id)
    if impact['impact_hash'] != expected_impact_hash:
        raise IntegrityConflict('La corrección cambió. Revisa de nuevo la vista previa.', code='stale_impact')
    if impact['blocked']:
        raise IntegrityConflict('No se puede deshacer esta corrección.', code='undo_blocked',
                                blockers=impact['blockers'])
    recorded = []
    for step in reversed(operation.steps):
        keys = sorted({(item['model'], item['pk']) for item in step['items']})
        before = snapshot_many(keys)
        fixer = catalog.get_fixer(step['rule_id'], step['fix_kind'])
        if fixer is not None and fixer.revert is not None:
            try:
                with transaction.atomic():
                    fixer.revert(step, actor=actor)
            except (ValidationError, DjangoValidationError, IntegrityError, ValueError):
                pass  # The savepoint is gone; the exact restore below takes over.
        _restore_exact(step)
        after = snapshot_many(keys)
        mismatched = [item for item in step['items'] if not item['guard']
                      and (after[(item['model'], item['pk'])] or {}).get(item['field']) != item['before']]
        if mismatched:
            raise IntegrityConflict('No se pudo restaurar exactamente el estado anterior; no se cambió nada.',
                                    code='undo_not_exact')
        recorded.append({**{key: step[key] for key in ('fingerprint', 'rule_id', 'rule_version', 'fix_kind',
                                                        'params', 'subjects', 'guards')},
                         'items': diff_items(before, after)})
    undo = DataIntegrityOperation.objects.create(
        kind=DataIntegrityOperation.Kind.UNDO, source=current_source(source),
        catalog_version=catalog.CATALOG_VERSION, scope=operation.scope, request_id=request_id,
        payload_hash=digest({'reverts': operation.pk, 'reason': reason}), impact_hash=impact['impact_hash'],
        reason=reason, steps=recorded, history_operation_id=current_history_operation_id(),
        reverts=operation, actor=actor,
    )
    return operation_summary(undo)


# ── Log ──────────────────────────────────────────────────────────────────────

def operation_summary(operation):
    reverted = DataIntegrityOperation.objects.filter(reverts=operation).values_list('pk', flat=True).first()
    return {
        'operation_id': operation.pk, 'kind': operation.kind, 'source': operation.source,
        'created_at': operation.created_at.isoformat(), 'actor': operation.actor.get_username(),
        'reason': operation.reason, 'scope': operation.scope, 'catalog_version': operation.catalog_version,
        'reverts': operation.reverts_id, 'reverted_by': reverted, 'idempotent': False,
        'steps': [{'rule_id': step['rule_id'], 'fix_kind': step['fix_kind'], 'subjects': step['subjects'],
                   'items': len([item for item in step['items'] if not item['guard']])}
                  for step in operation.steps],
    }


def operations_payload(*, page=1, rule_id=None):
    rows = DataIntegrityOperation.objects.select_related('actor')
    if rule_id:
        rows = [row for row in rows if any(step['rule_id'] == rule_id for step in row.steps)]
        total = len(rows)
    else:
        total = rows.count()
    start = (page - 1) * OPERATIONS_PAGE_SIZE
    return {'count': total, 'page': page, 'pages': max(1, -(-total // OPERATIONS_PAGE_SIZE)),
            'results': [operation_summary(row) for row in rows[start:start + OPERATIONS_PAGE_SIZE]]}
