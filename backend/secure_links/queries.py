"""Authoritative folder scope, filters and counts shared by REST and MCP."""
from django.db.models import Count, Q
from django.utils import timezone
from accounts.models import Project, UserProfile
from accounts.services.project_catalog_service import project_catalog_bucket
from accounts.services.proposal_client_service import build_client_display_name
from content.services.folder_tree import descendant_ids
from .models import SecureLink, SecureLinkFolder
from .folder_services import folder_for


def filter_links(data):
    query = SecureLink.objects.select_related('client__user', 'project', 'created_by', 'folder')
    scope = data.get('archive_scope', 'active')
    if scope != 'all':
        query = query.filter(is_archived=scope == 'archived')
    folder = data.get('folder', 'all')
    if folder == 'none':
        query = query.filter(folder__isnull=True)
    elif folder != 'all':
        root = folder_for(int(folder))
        ids = {root.pk} | descendant_ids(SecureLinkFolder.objects.values_list('pk', 'parent_id'), root.pk)
        query = query.filter(folder_id__in=ids)
    for field in ('origin', 'client', 'project', 'owner'):
        if data.get(field):
            query = query.filter(**{f'{field}__isnull': True}) if data[field] == 'none' else query.filter(**{field: data[field]})
    if data.get('search'):
        term = data['search']
        query = query.filter(
            Q(title__icontains=term) | Q(creator_name__icontains=term) | Q(creator_email__icontains=term)
            | Q(client__user__first_name__icontains=term) | Q(client__user__last_name__icontains=term)
            | Q(client__company_name__icontains=term) | Q(project__name__icontains=term)
        )
    return query


def counts_for(query):
    now = timezone.now()
    conditions = query.lifecycle_conditions(now)
    received = Q(audience=SecureLink.Audience.TEAM)
    totals = query.aggregate(
        all=Count('pk'), received=Count('pk', filter=received),
        unopened_received=Count('pk', filter=received & Q(consumed_at__isnull=True, revoked_at__isnull=True)),
        **{f'legacy_{key}': Count('pk', filter=value) for key, value in query.status_conditions(now).items()},
        **{f'lifecycle_{key}': Count('pk', filter=value) for key, value in conditions.items()},
    )
    return {
        'counts': {'all': totals['all'], **{key: totals[f'legacy_{key}'] for key in SecureLink.STATUSES}},
        'lifecycle_counts': {'all': totals['all'], 'received': totals['received'], **{key: totals[f'lifecycle_{key}'] for key in conditions}},
        'unopened_received': totals['unopened_received'],
    }


def selected_links(data, query=None):
    query = filter_links(data) if query is None else query
    if data.get('received'):
        query = query.filter(audience=SecureLink.Audience.TEAM)
    if data.get('status'):
        query = query.with_status(data['status'])
    if data.get('lifecycle_status'):
        query = query.with_lifecycle_status(data['lifecycle_status'])
    return query


def _empty_inventory():
    return {'active': {'folders': 0, 'documents': 0}, 'archived': {'folders': 0, 'documents': 0}}


def navigation_payload():
    from collections import defaultdict
    projects = list(Project.objects.select_related('client__profile__user', 'current_state', 'secure_link_root_folder'))
    project_counts, client_counts = defaultdict(_empty_inventory), defaultdict(_empty_inventory)
    totals, unassigned_project, unassigned_client = _empty_inventory(), _empty_inventory(), _empty_inventory()
    unfiled = _empty_inventory()
    client_folders = defaultdict(lambda: {'active': set(), 'archived': set()})
    folders = list(SecureLinkFolder.objects.values('id', 'parent_id', 'managed_project_id', 'is_archived'))
    parents = {row['id']: row['parent_id'] for row in folders}
    project_by_folder = {row['id']: row['managed_project_id'] for row in folders if row['managed_project_id']}
    for row in folders:
        pk, seen, trail = row['id'], set(), []
        while pk is not None and pk not in project_by_folder and pk not in seen:
            seen.add(pk)
            trail.append(pk)
            pk = parents.get(pk)
        root_project = project_by_folder.get(pk)
        for folder_id in trail:
            project_by_folder[folder_id] = root_project
        scope = 'archived' if row['is_archived'] else 'active'
        totals[scope]['folders'] += 1
        project_counts[project_by_folder.get(row['id'])][scope]['folders'] += 1
    rows = SecureLink.objects.values('folder_id', 'client_id', 'project_id', 'is_archived').annotate(total=Count('pk'))
    for row in rows:
        scope = 'archived' if row['is_archived'] else 'active'
        count = row['total']
        totals[scope]['documents'] += count
        project_counts[project_by_folder.get(row['folder_id'])][scope]['documents'] += count
        client_counts[row['client_id']][scope]['documents'] += count
        if row['folder_id'] is None:
            unfiled[scope]['documents'] += count
        else:
            client_folders[row['client_id']][scope].add(row['folder_id'])
        if not row['project_id']:
            unassigned_project[scope]['documents'] += count
        if not row['client_id']:
            unassigned_client[scope]['documents'] += count
    for client_id, scopes in client_folders.items():
        for scope, folder_ids in scopes.items():
            client_counts[client_id][scope]['folders'] = len(folder_ids)
    return {
        'totals': totals, 'unfiled': unfiled,
        'unassigned': {'project': unassigned_project, 'client': unassigned_client},
        'projects': [{
            'id': p.pk, 'name': p.name, 'client': getattr(getattr(p.client, 'profile', None), 'pk', None),
            'client_name': build_client_display_name(p.client.profile) if hasattr(p.client, 'profile') else p.client.email,
            'managed_root_id': getattr(getattr(p, 'secure_link_root_folder', None), 'pk', None),
            'catalog_bucket': project_catalog_bucket(p), 'counts': project_counts[p.pk],
        } for p in projects],
        'clients': [{'id': c.pk, 'name': build_client_display_name(c), 'counts': client_counts[c.pk],
                     'catalog_bucket': 'archived' if c.is_archived_client else 'active'}
                    for c in UserProfile.objects.clients().select_related('user')],
    }


def folder_index():
    from .folder_serializers import FolderSerializer
    rows = SecureLinkFolder.objects.annotate(
        link_count=Count('links', filter=Q(links__is_archived=False)),
        archived_link_count=Count('links', filter=Q(links__is_archived=True)),
    )
    return {'folders': [{**FolderSerializer(row).data, 'link_count': row.link_count,
                         'archived_link_count': row.archived_link_count} for row in rows],
            'navigation': navigation_payload()}
