"""Field snapshots: the before/after values an operation records and undo restores.

Each fixer registers the fields it may change on every model in its closure,
including fields signal side effects write. ``updated_at`` and
``retention_context_id`` are always captured when the model has them: they are
guards (a later edit or retention makes an undo stale) and are never restored.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.apps import apps

GUARD_FIELDS = ('updated_at', 'retention_context_id')
FIELDS = {}


def register_fields(model_label, *names):
    FIELDS[model_label] = tuple(sorted(set(FIELDS.get(model_label, ())) | set(names)))


def model_for(model_label):
    return apps.get_model(model_label)


def fields_for(model_label):
    model = model_for(model_label)
    attnames = {field.attname for field in model._meta.concrete_fields}
    names = set(FIELDS.get(model_label, ())) | {name for name in GUARD_FIELDS if name in attnames}
    unknown = names - attnames
    if unknown:
        raise LookupError(f'{model_label} has no fields {sorted(unknown)}')
    return tuple(sorted(names))


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    return value


def snapshot_many(keys):
    """{(model_label, pk): {field: value} | None} for every key; None means deleted."""
    by_model = {}
    for model_label, pk in keys:
        by_model.setdefault(model_label, set()).add(pk)
    result = {}
    for model_label, pks in by_model.items():
        model = model_for(model_label)
        names = fields_for(model_label)
        identities = {pk: model._meta.pk.to_python(pk) for pk in pks}
        rows = model._base_manager.filter(pk__in=identities.values()).values('pk', *names)
        found = {json_value(row.pop('pk')): {name: json_value(value) for name, value in row.items()} for row in rows}
        for pk in pks:
            result[(model_label, pk)] = found.get(json_value(identities[pk]))
    return result


def diff_items(before, after):
    """Record changed non-guard fields plus all guards of each changed row.

    Unchanged guards still protect undo after a queryset update. Rows whose
    only changes are guards are omitted.
    """
    items = []
    for key in sorted(before, key=lambda item: (item[0], item[1])):
        old, new = before[key] or {}, after.get(key) or {}
        names = set(old) | set(new)
        if not any(old.get(name) != new.get(name) for name in names - set(GUARD_FIELDS)):
            continue
        for name in sorted(names):
            if name in GUARD_FIELDS or old.get(name) != new.get(name):
                items.append({'model': key[0], 'pk': json_value(key[1]), 'field': name,
                              'before': old.get(name), 'after': new.get(name),
                              'guard': name in GUARD_FIELDS})
    return items
