"""Cycle-safe traversal shared by filing domains; one materialized parent index."""
from collections import defaultdict


def descendant_ids(rows, root_id):
    children = defaultdict(list)
    for pk, parent_id in rows:
        children[parent_id].append(pk)
    seen = {root_id}
    pending = list(children[root_id])
    while pending:
        pk = pending.pop()
        if pk not in seen:
            seen.add(pk)
            pending.extend(children[pk])
    return seen - {root_id}
