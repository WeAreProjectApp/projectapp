"""Query construction for admin document listings.

The legacy list and the paginated document-manager browser share every filter
and ordering rule through this module.  Keeping the queryset lazy is important:
the browser slices it before DRF serializes rows, so prefetches only run for the
visible page instead of the complete document inventory.
"""

from django.db.models import (
    Case, Count, DateTimeField, Exists, F, OuterRef, Prefetch, Q, When,
)
from django.db.models.functions import Coalesce

from content.models import (
    AccountingChangeLog,
    Document,
    DocumentFolder,
    DocumentStateEpisode,
    EmailLog,
    EmailLogTarget,
)


class DocumentQueryError(ValueError):
    """A malformed query parameter with its public API error message."""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field
        self.message = message


def _integer_list(params, field, message):
    raw = params.get(field)
    if raw in (None, ''):
        return []
    try:
        return [int(value) for value in raw.split(',') if value.strip()]
    except ValueError as exc:
        raise DocumentQueryError(field, message) from exc


def _association_filter(documents, params, field, lookup, message):
    raw = params.get(field)
    if raw == 'none':
        return documents.filter(**{f'{lookup}__isnull': True}), ('none', [])
    if raw in (None, '', 'all'):
        return documents, None

    ids = _integer_list(params, field, message)
    if ids:
        documents = documents.filter(**{f'{lookup}__in': ids})
    return documents, ('ids', ids)


def _entity_folders(project_selector, client_selector):
    folders = DocumentFolder.objects.all()
    managed_ids = set()

    if project_selector is not None:
        mode, ids = project_selector
        if mode == 'none':
            folders = folders.filter(project__isnull=True)
        else:
            folders = folders.filter(project_id__in=ids)
            managed_ids = set(
                folders.filter(managed_project_id__in=ids)
                .values_list('id', flat=True)
            )
        return folders, managed_ids

    if client_selector is not None:
        mode, ids = client_selector
        if mode == 'none':
            folders = folders.filter(client_user__isnull=True)
        else:
            folders = folders.filter(client_user__profile__id__in=ids)
            managed_ids = set(
                folders.filter(managed_client__profile__id__in=ids)
                .values_list('id', flat=True)
            )
        return folders, managed_ids

    return None, managed_ids


def _archived_visible_folder_ids(folders):
    """Mirror the client rollup rule for an archived entity root.

    Archived folders are visible themselves. Active folders are also visible
    when they contain an archived document anywhere below them, so operators
    can descend through the active chain to that content.
    """
    rows = list(folders.values('id', 'parent_id', 'is_archived'))
    parent_by_id = {row['id']: row['parent_id'] for row in rows}
    entity_ids = set(parent_by_id)
    visible = {row['id'] for row in rows if row['is_archived']}
    pending = list(
        Document.objects.filter(
            is_archived=True,
            folder_id__in=entity_ids,
        ).values_list('folder_id', flat=True).distinct()
    )

    while pending:
        folder_id = pending.pop()
        if folder_id in visible:
            parent_id = parent_by_id.get(folder_id)
            if parent_id in entity_ids and parent_id not in visible:
                pending.append(parent_id)
            continue
        visible.add(folder_id)
        parent_id = parent_by_id.get(folder_id)
        if parent_id in entity_ids:
            pending.append(parent_id)
    return visible


def _filter_root(documents, *, scope, project_selector, client_selector):
    entity_folders, managed_ids = _entity_folders(
        project_selector, client_selector,
    )

    if entity_folders is None:
        if scope == 'all':
            return documents.filter(folder__isnull=True)
        # A row rises to the global root when its container is outside the
        # visible scope. This is the server equivalent of isRootInScope().
        return documents.filter(
            Q(folder__isnull=True)
            | ~Q(folder__is_archived=(scope == 'archived'))
        )

    if scope == 'all':
        visible_ids = set(entity_folders.values_list('id', flat=True))
    elif scope == 'active':
        visible_ids = set(
            entity_folders.filter(is_archived=False).values_list('id', flat=True)
        )
    else:
        visible_ids = _archived_visible_folder_ids(entity_folders)

    return documents.filter(
        Q(folder__isnull=True)
        | Q(folder_id__in=managed_ids)
        | ~Q(folder_id__in=visible_ids)
    )


def build_document_list_queryset(
    params,
    *,
    scope,
    order='recent',
    search_max_length=200,
    resolve_root=False,
):
    """Build the optimized, ordered queryset shared by document list readers."""
    delivered_targets = EmailLogTarget.objects.filter(
        entity_type=AccountingChangeLog.EntityType.COLLECTION_ACCOUNT,
        object_id=OuterRef('pk'),
    ).exclude(email_log__status=EmailLog.Status.FAILED)
    failed_targets = EmailLogTarget.objects.filter(
        entity_type=AccountingChangeLog.EntityType.COLLECTION_ACCOUNT,
        object_id=OuterRef('pk'),
        email_log__status=EmailLog.Status.FAILED,
    )
    documents = Document.objects.all()
    if scope != 'all':
        documents = documents.filter(is_archived=(scope == 'archived'))

    documents, client_selector = _association_filter(
        documents,
        params,
        'client',
        'client_user__profile__id',
        'El identificador de cliente no es válido.',
    )
    documents, project_selector = _association_filter(
        documents,
        params,
        'project',
        'project_id',
        'El identificador de proyecto no es válido.',
    )

    folder = params.get('folder')
    if folder == 'none':
        documents = documents.filter(folder__isnull=True)
    elif folder == 'root' and resolve_root:
        documents = _filter_root(
            documents,
            scope=scope,
            project_selector=project_selector,
            client_selector=client_selector,
        )
    elif folder not in (None, '', 'all'):
        try:
            documents = documents.filter(folder_id=int(folder))
        except (TypeError, ValueError) as exc:
            raise DocumentQueryError(
                'folder', 'El identificador de carpeta no es válido.',
            ) from exc

    tag_ids = _integer_list(
        params, 'tags', 'La lista de etiquetas no es válida.',
    )
    if tag_ids:
        documents = documents.filter(tags__id__in=tag_ids).distinct()

    state_ids = _integer_list(
        params, 'states', 'La lista de estados no es válida.',
    )
    if state_ids:
        documents = documents.filter(
            state_episodes__state_id__in=state_ids,
            state_episodes__closed_at__isnull=True,
        ).distinct()

    without_state_ids = _integer_list(
        params,
        'without_states',
        'La lista de estados ausentes no es válida.',
    )
    if without_state_ids:
        active_document_ids = DocumentStateEpisode.objects.filter(
            state_id__in=without_state_ids,
            closed_at__isnull=True,
        ).values('document_id')
        documents = documents.exclude(pk__in=active_document_ids)

    preset = str(params.get('preset') or '').strip()
    if preset == 'needs_fix':
        documents = documents.filter(
            state_episodes__state__system_key='needs_fix',
            state_episodes__closed_at__isnull=True,
        ).distinct()
    elif preset == 'sent_not_closed':
        sent_ids = DocumentStateEpisode.objects.filter(
            state__system_key='sent', closed_at__isnull=True,
        ).values('document_id')
        closed_ids = DocumentStateEpisode.objects.filter(
            state__system_key='closed', closed_at__isnull=True,
        ).values('document_id')
        documents = documents.filter(pk__in=sent_ids).exclude(pk__in=closed_ids)
    elif preset == 'closed':
        documents = documents.filter(
            state_episodes__state__system_key='closed',
            state_episodes__closed_at__isnull=True,
        ).distinct()
    elif preset == 'unclassified':
        classified_ids = DocumentStateEpisode.objects.filter(
            state__group__selection_mode='exclusive',
            closed_at__isnull=True,
        ).values('document_id')
        documents = (
            documents.exclude(pk__in=classified_ids)
            .exclude(document_type__code='collection_account')
        )
    elif preset:
        raise DocumentQueryError(
            'preset', 'La consulta predefinida no es válida.',
        )

    search = str(params.get('search') or '').strip()[:search_max_length]
    if search:
        from content.services.record_id_search import id_search_predicate
        exact_id, predicate = id_search_predicate(search)
        if not exact_id:
            predicate |= Q(title__icontains=search) | Q(client_name__icontains=search)
        documents = documents.filter(predicate)

    documents = documents.annotate(
        _has_delivered_collection_email=Exists(delivered_targets),
        _has_failed_collection_email=Exists(failed_targets),
        thread_document_count=Count(
            'thread_item__thread__items', distinct=True,
        ),
        _display_sort_date=Case(
            When(
                is_archived=True,
                then=Coalesce(F('archived_at'), F('created_at')),
            ),
            default=F('created_at'),
            output_field=DateTimeField(),
        ),
    ).prefetch_related(
        'tags',
        Prefetch(
            'state_episodes',
            queryset=(
                DocumentStateEpisode.objects.filter(closed_at__isnull=True)
                .select_related('state__group')
            ),
            to_attr='prefetched_active_state_episodes',
        ),
    ).select_related(
        'document_type', 'folder', 'project', 'client_user__profile',
        'thread_item__thread', 'contract_template',
    )

    prefix = '' if order == 'oldest' else '-'
    return documents.order_by(
        f'{prefix}_display_sort_date',
        f'{prefix}created_at',
        f'{prefix}pk',
    )
