"""The fixer contract and small helpers shared by every fixer.

A fixer turns one finding plus the operator's params into a ``FixPlan``
without writing, then applies it through the domain writers. The engine
snapshots ``plan.closure`` around ``apply`` to record exact before/after items,
and on undo calls ``revert`` (when defined) before restoring any field that
still differs.
"""
from content.services.data_integrity.snapshots import register_fields
from content.services.data_integrity.types import FixPlan, RecordRef, blocker


class Fixer:
    kind = ''
    # Exclusive fixers (merges) run alone in an operation, under their own cap.
    exclusive = False
    max_closure = None
    # {model_label: (attnames...)} this fixer may change, signal side effects included.
    fields = {}

    def __init__(self):
        for model_label, names in self.fields.items():
            register_fields(model_label, *names)

    def plan(self, finding, params, *, actor):
        raise NotImplementedError

    def apply(self, plan, *, actor):
        raise NotImplementedError

    # Optional: undo through the domain writers. The engine runs it inside a
    # savepoint, discards it if the writer rejects the old state, and then
    # restores every recorded field that still differs from ``before``.
    revert = None

    def new_plan(self, params, **kwargs):
        return FixPlan(fix_kind=self.kind, params=params, **kwargs)


def ref(instance, label=''):
    return RecordRef(instance._meta.label_lower, instance.pk, label or str(instance))


def retained_blockers(rows):
    """Retained rows are read-only (the model guard only covers ``save``)."""
    retained = [ref(row) for row in rows if getattr(row, 'retention_context_id', None)]
    if not retained:
        return []
    return [blocker('retained_read_only', 'Hay registros conservados de un proyecto eliminado: '
                    'sólo se trasladan con «Asignar registros sin proyecto».', retained)]


def required_choice(params, name, options, label):
    """(value, blockers): the chosen option or an input_required/invalid_input blocker."""
    value = params.get(name)
    allowed = {option['value'] for option in options}
    if value in (None, ''):
        return None, [blocker('input_required', f'Falta elegir {label}.')]
    if type(value) not in {type(option) for option in allowed} or value not in allowed:
        return None, [blocker('invalid_input', f'La opción elegida para {label} no es válida.')]
    return value, []


def change(row, field, before, after, label=''):
    return {'model': row._meta.label_lower, 'id': row.pk, 'label': label or str(row),
            'field': field, 'before': before, 'after': after}
