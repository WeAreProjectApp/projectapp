"""What stops a client from being deleted: one answer for every caller.

Deleting a client deletes its ``User``; the ``UserProfile`` and every other
CASCADE child go with it, and whether Django lets that happen is decided by
the deletion Collector. This module asks the Collector's own question: it walks
the reverse relations the Collector walks (hidden ``related_name='+'`` ones
included), from ``User`` down every CASCADE chain, and every PROTECT or
RESTRICT relation met on the way is a blocker. ``Project.client`` is added on
top: it cascades, but a client's projects are business data a delete must
never take along.

The delete guard, the panel's orphan cut (list, status counts and the MCP
copies of both) and the data-integrity rule CL4 all read these blockers, so
what the panel offers to delete is exactly what the guard accepts. Before, four
places listed six relations by hand while a client has more than thirty
protected ones, and deleting a client that held any of the others failed with
an unhandled ``ProtectedError``.
"""
from collections import Counter, deque
from dataclasses import dataclass
from functools import cache, reduce
from operator import or_

from django.contrib.auth import get_user_model
from django.db.models import CASCADE, PROTECT, RESTRICT, BooleanField, Exists, ExpressionWrapper, OuterRef

# CASCADE levels followed below ``User``. The deepest chain that reaches a
# PROTECT today has two (User → Deliverable → ProposalApprovalFile); the bound
# only stops a self-referencing cascade from looping.
MAX_CASCADE_DEPTH = 4
BLOCKING_ON_DELETE = (PROTECT, RESTRICT)
# Cascading relations that still block: deleting the client must never delete
# these rows along with it.
BUSINESS_CASCADES = frozenset({'accounts.project.client'})


class ClientDeletionBlocked(ValueError):
    """Raised before any delete when protected rows still point at the client.

    The message keeps the panel's ``<code>:<count>`` shape; ``relations`` maps
    each blocking relation to its row count — labels and numbers, never row
    content.
    """

    code = 'client_has_protected_references'

    def __init__(self, relations):
        self.relations = dict(sorted(relations.items()))
        super().__init__(f'{self.code}:{sum(self.relations.values())}')


@dataclass(frozen=True)
class Blocker:
    """Rows of ``model`` that reach the client's user through ``lookup``."""

    name: str  # '<app_label>.<model>.<field>' of the relation's first hop
    model: type
    lookup: str  # ORM path from ``model`` to the user's pk

    def rows(self, user_id):
        # Base manager: an archived or retained row protects exactly the same.
        return self.model._base_manager.filter(**{self.lookup: user_id})

    def exists(self, outer):
        return Exists(self.model._base_manager.filter(**{self.lookup: OuterRef(outer)}))


def candidate_relations(model):
    """The reverse relations the deletion Collector walks, hidden ones included."""
    return [
        field for field in model._meta.get_fields(include_hidden=True)
        if field.auto_created and not field.concrete and (field.one_to_one or field.one_to_many)
    ]


@cache
def deletion_blockers():
    """Every relation that would stop deleting a client's user, as ``Blocker``s."""
    user_model = get_user_model()
    found = {}
    queue = deque([(user_model, 'pk', 0)])
    visited = {(user_model, 'pk')}
    while queue:
        model, path, depth = queue.popleft()
        for relation in candidate_relations(model):
            field = relation.field
            related = relation.related_model
            name = f'{related._meta.label_lower}.{field.name}'
            lookup = f'{field.name}__{path}'
            on_delete = field.remote_field.on_delete
            if on_delete in BLOCKING_ON_DELETE or (model is user_model and name in BUSINESS_CASCADES):
                found.setdefault((name, lookup), Blocker(name, related, lookup))
            elif on_delete is CASCADE and depth < MAX_CASCADE_DEPTH and (related, lookup) not in visited:
                visited.add((related, lookup))
                queue.append((related, lookup, depth + 1))
    return tuple(sorted(found.values(), key=lambda blocker: (blocker.name, blocker.lookup)))


def blocked_condition(outer):
    """True when any blocker has a row for the user in the outer ``outer`` column."""
    return reduce(or_, (blocker.exists(outer) for blocker in deletion_blockers()))


def deletion_blocked_annotation():
    """``deletion_blocked`` for a ``UserProfile`` queryset, in the same query."""
    return ExpressionWrapper(blocked_condition('user_id'), output_field=BooleanField())


def has_blockers(user_id):
    return get_user_model()._base_manager.filter(pk=user_id).filter(blocked_condition('pk')).exists()


def blocker_counts(user_id):
    """``{relation: rows}`` of every blocker the user has; empty when deletable."""
    if not has_blockers(user_id):
        return {}
    counts = Counter()
    for blocker in deletion_blockers():
        rows = blocker.rows(user_id).count()
        if rows:
            counts[blocker.name] += rows
    return dict(counts)


def protected_summary(error):
    """``{model label: rows}`` of a ``ProtectedError`` or ``RestrictedError``."""
    objects = getattr(error, 'protected_objects', None) or getattr(error, 'restricted_objects', None) or ()
    return dict(sorted(Counter(obj._meta.label_lower for obj in objects).items()))
