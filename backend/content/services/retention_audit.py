"""Read-only audit of the data retained by forced project deletions.

Counts come from the rows that still carry ``retention_context``, not only from
the index captured at deletion time, so whatever later left or drifted shows up.
Kinds without a direct project link were listed at deletion but never marked:
they follow their parent and have no live count of their own.
"""
from collections import defaultdict

from django.apps import apps
from django.db.models import Q

from accounts.models import Deliverable, Project, ProjectPhase
from accounts.retention import RetainedProjectModel
from accounts.services.proposal_client_service import build_client_display_name
from content.models import ProjectRetentionContext
from content.services.project_deletion_catalog import CATEGORIES

PAGE_SIZE = 20
IDS_PER_CATEGORY = 100


def retained_models():
    return sorted(
        (model for model in apps.get_models() if issubclass(model, RetainedProjectModel)),
        key=lambda model: model._meta.label_lower,
    )


def _project_fields(model):
    return [field.name for field in model._meta.concrete_fields
            if field.is_relation and field.remote_field.model is Project]


def _live_ids(context_ids):
    """{context_id: {model_label: [ids]}} for rows that still carry the marker."""
    live = defaultdict(lambda: defaultdict(list))
    for model in retained_models():
        rows = (model._base_manager.filter(retention_context_id__in=context_ids)
                .order_by('pk').values_list('retention_context_id', 'pk'))
        for context_id, pk in rows:
            live[context_id][model._meta.label_lower].append(str(pk))
    return live


def _proposals(context_ids):
    """Proposals whose own deliverable or commercial phase stayed retained."""
    found = defaultdict(dict)

    def entry(context_id, proposal_id, title, status):
        return found[context_id].setdefault(proposal_id, {
            'id': proposal_id, 'title': title, 'status': status,
            'deliverable_id': None, 'phase_ids': [],
        })

    deliverables = (Deliverable._base_manager
                    .filter(retention_context_id__in=context_ids, business_proposal__isnull=False)
                    .values_list('retention_context_id', 'pk', 'business_proposal__id',
                                 'business_proposal__title', 'business_proposal__status'))
    for context_id, pk, proposal_id, title, status in deliverables:
        entry(context_id, proposal_id, title, status)['deliverable_id'] = pk
    phases = (ProjectPhase._base_manager
              .filter(retention_context_id__in=context_ids)
              .order_by('pk')
              .values_list('retention_context_id', 'pk', 'business_proposal_id',
                           'business_proposal__title', 'business_proposal__status'))
    for context_id, pk, proposal_id, title, status in phases:
        entry(context_id, proposal_id, title, status)['phase_ids'].append(pk)
    return {context_id: sorted(rows.values(), key=lambda row: row['id'])
            for context_id, rows in found.items()}


def _category(label, context, live_ids):
    try:
        model = apps.get_model(label)
    except LookupError:  # an index entry for a model that no longer exists
        model = None
    meta = CATEGORIES.get(label, {'key': label, 'label': label, 'label_en': label})
    tracked = model is not None and issubclass(model, RetainedProjectModel)
    listed = set(context.retained_records.get(label, []))
    return {
        'key': meta['key'], 'label': meta['label'], 'label_en': meta['label_en'], 'model': label,
        'at_deletion': context.category_counts.get(label, len(listed)),
        'tracked': tracked,
        'remaining': len(live_ids) if tracked else None,
        'ids': live_ids[:IDS_PER_CATEGORY],
        # Marked rows the deletion index never listed: drift worth explaining.
        'unlisted': len(set(live_ids) - listed),
    }


def integrity_findings():
    """Retained rows that also point to a project again (bypassed write paths)."""
    findings = []
    for model in retained_models():
        names = _project_fields(model)
        if not names:
            continue
        linked = Q()
        for name in names:
            linked |= Q(**{f'{name}__isnull': False})
        count = model._base_manager.filter(retention_context__isnull=False).filter(linked).count()
        if count:
            label = model._meta.label_lower
            findings.append({'model': label, 'key': CATEGORIES.get(label, {}).get('key', label),
                             'issue': 'retained_with_project', 'count': count})
    return findings


def audit_payload(*, page=1, client_profile_id=None, integrity=False):
    contexts = (ProjectRetentionContext.objects
                .select_related('client__profile', 'created_by')
                .order_by('-created_at', '-id'))
    if client_profile_id is not None:
        contexts = contexts.filter(client__profile__pk=client_profile_id)
    total = contexts.count()
    rows = list(contexts[(page - 1) * PAGE_SIZE:page * PAGE_SIZE])
    ids = [context.pk for context in rows]
    live = _live_ids(ids) if ids else {}
    proposals = _proposals(ids) if ids else {}
    results = []
    for context in rows:
        context_live = live.get(context.pk, {})
        labels = sorted(set(context.category_counts) | set(context.retained_records) | set(context_live))
        categories = [_category(label, context, context_live.get(label, [])) for label in labels]
        profile = getattr(context.client, 'profile', None)
        results.append({
            'id': context.pk,
            'original_project_id': context.original_project_id,
            'project_name': context.project_name,
            'created_at': context.created_at,
            'created_by': {'id': context.created_by_id,
                           'name': context.created_by.get_full_name() or context.created_by.email},
            'client': {'profile_id': getattr(profile, 'pk', None), 'user_id': context.client_id,
                       'name': build_client_display_name(profile) if profile else context.client.email},
            'pending_total': sum(row['remaining'] or 0 for row in categories),
            'categories': categories,
            'proposals': proposals.get(context.pk, []),
        })
    payload = {'count': total, 'page': page, 'page_size': PAGE_SIZE, 'results': results}
    if integrity:
        payload['integrity'] = integrity_findings()
    return payload
