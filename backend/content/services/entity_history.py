"""Transactional aggregate history shared by HTTP, MCP and background writers."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from inspect import signature
import uuid

from django.db import DEFAULT_DB_ALIAS, transaction
from django.urls import Resolver404, resolve

from content.services.entity_history_registry import (
    entity_model, field_labels, roots_for, snapshot_entity,
)

_operation = ContextVar('entity_history_operation', default=None)
_disabled = ContextVar('entity_history_disabled', default=False)


def history_active():
    return _operation.get() is not None and not _disabled.get()


def current_history_operation_id():
    """The ``EntityRevision.operation_id`` the active write will use, if any."""
    op = _operation.get()
    return op.operation_id if op is not None and not _disabled.get() else None


@dataclass
class HistoryOperation:
    actor: object = None
    source: str = 'system'
    operation_id: object = field(default_factory=uuid.uuid4)
    before: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)


def changes_between(before, after, path=''):
    """Field/section differences; protected values are never passed to this function."""
    before, after = before or {}, after or {}
    changes = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        name = f'{path}.{key}' if path else key
        if old == new:
            continue
        if isinstance(old, dict) and isinstance(new, dict) and not (
            'id' in old or 'protected' in old
        ):
            changes.extend(changes_between(old, new, name))
        else:
            changes.append({'field': name, 'label': field_labels().get(key, key.replace('_', ' ')),
                            'old': old, 'new': new})
    return changes


def _identity(op):
    from content.mcp.context import current_mcp_context
    context = current_mcp_context()
    actor = op.actor() if callable(op.actor) else op.actor
    source = op.source
    if context:
        actor = context.actor
        source = f'mcp:{context.connector.slug}'
    authenticated = getattr(actor, 'is_authenticated', False)
    return {
        'actor_id_snapshot': actor.pk if authenticated else None,
        'actor_label': ((actor.get_full_name() or actor.username) if authenticated
                        else ('Integración MCP' if context else 'Sistema'))[:255],
        'source': source[:255],
    }


def capture(kind, pk, *, created=False):
    op = _operation.get()
    if op is None or _disabled.get():
        return
    key = (kind, pk)
    if key in op.before:
        if created:
            head, _, _, _, identity = op.before[key]
            op.before[key] = (head, None, {}, '', identity)
        return
    from content.models.entity_history import EntityHistory
    # Lock the live aggregate before reading its prior values. The durable row
    # additionally serializes tombstones and initialisation of existing rows.
    entity_model(kind).objects.select_for_update().filter(pk=pk).first()
    head, _ = EntityHistory.objects.get_or_create(entity_type=kind, object_id=pk)
    head = EntityHistory.objects.select_for_update().get(pk=head.pk)
    data, secrets, label = (None, {}, '') if created else snapshot_entity(kind, pk)
    op.before[key] = (head, data, secrets, label, _identity(op))


def capture_instance(instance, *, created=False):
    for kind, pk in sorted(roots_for(instance)):
        capture(kind, pk, created=created and pk == instance.pk
                and instance._meta.label == entity_model(kind)._meta.label)


def link_evidence(kind, pk, source_key):
    op = _operation.get()
    if op is not None:
        op.evidence.setdefault((kind, pk), []).append(source_key)


def _secret_changes(old, new):
    from accounts.services.credential_cipher import _get_cipher
    changed = []
    for path in sorted(set(old) | set(new)):
        left, right = old.get(path, ''), new.get(path, '')
        if left == right:
            continue
        # Compare plaintext only in memory: Fernet ciphertext is randomized.
        # Invalid ciphertext fails closed rather than becoming an empty value.
        cipher = _get_cipher()
        if (cipher.decrypt(left.encode()) if left else b'') != (
            cipher.decrypt(right.encode()) if right else b''
        ):
            changed.append({'field': path, 'label': 'Contenido protegido',
                            'old': {'protected': True, 'present': bool(left)},
                            'new': {'protected': True, 'present': bool(right)}})
    return changed


def append_revision(head, *, snapshot, secrets, action, changes, identity,
                    operation_id=None, evidence=None, source_key=None):
    from content.models.entity_history import EntityRevision
    head.revision += 1
    head.save(update_fields=['revision', 'object_label'])
    return EntityRevision.objects.create(
        history=head, number=head.revision, snapshot=snapshot, secrets=secrets,
        action=action, changes=changes, changed_fields=[{'field': c['field'], 'label': c['label']} for c in changes], operation_id=operation_id or uuid.uuid4(),
        evidence=evidence or [], source_key=source_key, **identity,
    )


def _flush(op):
    for (kind, pk), (head, before, old_secrets, old_label, identity) in op.before.items():
        after, secrets, label = snapshot_entity(kind, pk)
        changes = changes_between(before, after)
        protected_changes = _secret_changes(old_secrets, secrets)
        # Replace masked presence changes with the semantic secret comparison.
        protected_paths = {row['field'] for row in protected_changes}
        changes = [row for row in changes if row['field'] not in protected_paths]
        changes.extend(protected_changes)
        if not changes and before == after:
            continue
        head.refresh_from_db(fields=['revision'])
        head.object_label = label or old_label or head.object_label
        if not head.revision and before is not None:
            append_revision(head, snapshot=before, secrets=old_secrets, action='baseline',
                            changes=[], identity={'actor_label': 'Estado inicial', 'source': 'baseline'})
        action = 'created' if before is None else ('deleted' if after is None else 'updated')
        append_revision(head, snapshot=after if after is not None else before,
                        secrets=secrets if after is not None else old_secrets,
                        action=action, changes=changes, identity=identity,
                        operation_id=op.operation_id, evidence=op.evidence.get((kind, pk)))


@contextmanager
def history_operation(*, actor=None, source='system'):
    """Group a logical write into one revision per aggregate, atomically."""
    if _disabled.get() or _operation.get() is not None:
        yield
        return
    op = HistoryOperation(actor=actor, source=source)
    with transaction.atomic():
        token = _operation.set(op)
        try:
            yield
            if not transaction.get_rollback():
                _flush(op)
        finally:
            # on_commit callbacks may write other records. They must start a
            # new operation after this one has been flushed, not append to it.
            _operation.reset(token)


@contextmanager
def without_history():
    """Only for importing pre-existing evidence; never used by ordinary writers."""
    token = _disabled.set(True)
    try:
        yield
    finally:
        _disabled.reset(token)


def historical_write(function):
    parameters = signature(function)
    @wraps(function)
    def wrapped(*args, **kwargs):
        arguments = parameters.bind_partial(*args, **kwargs).arguments
        actor = next((arguments.get(key) for key in ('actor', 'user', 'acting_user') if arguments.get(key) is not None), None)
        data = arguments.get('validated_data', {})
        actor = actor or data.get('updated_by') or data.get('created_by')
        with history_operation(actor=actor, source='service'):
            return function(*args, **kwargs)
    return wrapped


class EntityHistoryMiddleware:
    write_path_prefixes = ('/api/', '/admin/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method in ('GET', 'HEAD', 'OPTIONS')
            or not request.path_info.startswith(self.write_path_prefixes)
        ):
            return self.get_response(request)
        try:
            view = resolve(request.path_info, getattr(request, 'urlconf', None)).func
        except Resolver404:
            view = None
        if DEFAULT_DB_ALIAS in getattr(view, '_non_atomic_requests', set()):
            return self.get_response(request)
        # DRF/JWT sets the underlying request.user during dispatch.
        with history_operation(actor=lambda: getattr(request, 'user', None), source='http'):
            return self.get_response(request)

    def process_exception(self, request, exception):
        if _operation.get() is not None:
            transaction.set_rollback(True)
