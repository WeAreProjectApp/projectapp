"""Delete unused projects without cascading or detaching business data."""

from django.db import transaction
from django.db.models import Q

from accounts.models import Project
from content.models import (
    AccountingChangeLog, CommunicationMessage, CommunicationThread, Document, DocumentFolder,
    DocumentStateEpisode, DocumentStateEpisodeEvent,
)
from content.services.entity_history import capture_instance, historical_write
from content.services.project_document_folder_service import (
    PROJECT_FOLDER_TEMPLATE, project_category_system_key,
)
from content.services.project_service import log_project_event, project_snapshot


# Unknown future relations also block deletion; these names make the current
# inventory understandable to the operator without exposing database names.
DEPENDENCY_LABELS = {
    'accounts.projectadminaccess': ('accesses', 'Accesos administrativos'),
    'accounts.projectaccessnote': ('notes', 'Notas del proyecto'),
    'accounts.projectphase': ('phases', 'Fases y propuestas vinculadas'),
    'accounts.changerequest': ('change_requests', 'Solicitudes de cambio'),
    'accounts.bugreport': ('bugs', 'Reportes de errores'),
    'accounts.deliverable': ('deliverables', 'Entregables'),
    'accounts.projectdatamodelentity': ('data_models', 'Entidades del modelo de datos'),
    'accounts.notification': ('notifications', 'Notificaciones'),
    'accounts.hostingsubscription': ('subscriptions', 'Suscripciones de hosting'),
    'content.hostingrecord': ('hostings', 'Registros de hosting'),
    'content.incomerecord': ('incomes', 'Ingresos'),
    'content.document': ('documents', 'Documentos'),
    'content.financingagreement': ('agreements', 'Acuerdos de alianza'),
    'content.projectbrandasset': ('brand_assets', 'Recursos de marca'),
    'content.communicationfolder': ('communication_folders', 'Carpetas de comunicaciones'),
    'content.linktree': ('linktrees', 'Páginas de enlaces'),
    'secure_links.securelink': ('secure_links', 'Enlaces seguros'),
    'monitoring.resource': ('monitoring', 'Recursos de monitoreo'),
}


class ProjectDeleteBlocked(ValueError):
    def __init__(self, preview):
        super().__init__('El proyecto tiene información relacionada y no se puede eliminar.')
        self.preview = preview


def _current(queryset, lock):
    return queryset.select_for_update() if lock else queryset


def _count(queryset, lock):
    # A locking read sees current rows even inside a MySQL REPEATABLE READ
    # transaction whose earlier authentication/MCP reads created a snapshot.
    return len(list(_current(queryset, True).values_list('pk', flat=True))) if lock else queryset.count()


def _automatic_folder_ids(project, lock):
    """Only unchanged template folders are disposable, never custom folders."""
    root = _current(DocumentFolder.objects.all(), lock).filter(
        managed_project=project, project=project, parent__isnull=True,
        name=project.name, client_user_id=project.client_id,
        created_by__isnull=True, creation_source='system', is_archived=False,
    ).first()
    if root is None:
        return []
    ids = [root.pk]
    for order, (name, kind) in enumerate(PROJECT_FOLDER_TEMPLATE):
        child = _current(root.children.all(), lock).filter(
            name=name, order=order, project=project,
            client_user_id=project.client_id, created_by__isnull=True,
            creation_source='system', is_archived=False,
            system_key=(project_category_system_key(project.pk, kind) if kind else None),
        ).first()
        if child is not None:
            ids.append(child.pk)
    return ids


def _initial_episode_id(project, lock):
    episodes = list(_current(DocumentStateEpisode.objects.filter(project=project), lock))
    if len(episodes) != 1:
        return None
    episode = episodes[0]
    if (
        episode.state_id != project.current_state_id
        or episode.closed_at or episode.closed_by_id or episode.outcome
        or episode.close_note or episode.origin != DocumentStateEpisode.Origin.MANUAL
    ):
        return None
    events = list(_current(episode.events.all(), lock))
    if len(events) != 1:
        return None
    event = events[0]
    if (
        event.event_type != DocumentStateEpisodeEvent.EventType.OPENED
        or event.effective_at != episode.opened_at
        or event.details != {'origin': DocumentStateEpisode.Origin.MANUAL}
    ):
        return None
    return episode.pk


def _dependency_inventory(project, *, lock=False):
    """Return blockers plus the empty system structure safe to remove.

    Group reverse relations by model to avoid double-counting, e.g. a root
    folder references the same project through two separate foreign keys.
    """
    blockers = []
    disposable_folders = _automatic_folder_ids(project, lock)
    root = _current(DocumentFolder.objects.all(), lock).filter(managed_project=project).first()
    descendants = []
    frontier = [root.pk] if root else []
    while frontier:
        frontier = list(_current(DocumentFolder.objects.filter(
            parent_id__in=frontier,
        ).exclude(pk__in=descendants), lock).values_list('pk', flat=True))
        descendants.extend(frontier)
    folder_ids = list(_current(DocumentFolder.objects.all(), lock).filter(
        Q(project=project) | Q(managed_project=project) | Q(pk__in=descendants),
    ).values_list('pk', flat=True))
    # Include documents inside a folder even if someone changed their own
    # project association. They must not be detached when its root disappears.
    documents = Document.objects.filter(Q(project=project) | Q(folder_id__in=folder_ids))
    message_threads = CommunicationThread.objects.filter(
        Q(project=project) | Q(managed_project=project),
    )
    thread_ids = list(_current(message_threads, lock).values_list('pk', flat=True))
    message_ids = list(_current(CommunicationMessage.objects.filter(thread_id__in=thread_ids), lock).values_list('pk', flat=True))
    disposable_threads = list(_current(message_threads, lock).filter(
        managed_project=project, title=project.name,
        status=CommunicationThread.Status.OPEN, closed_at__isnull=True,
        is_archived=False, created_by__isnull=True, updated_by__isnull=True,
        folder__isnull=True, messages__isnull=True,
    ).values_list('pk', flat=True))

    def add(key, label, count):
        if count:
            blockers.append({'key': key, 'label': label, 'count': count})

    add('documents', 'Documentos', _count(documents, lock))
    add('document_folders', 'Carpetas documentales personalizadas',
        len(set(folder_ids) - set(disposable_folders)))
    add('communication_threads', 'Conversaciones con contenido o personalizadas',
        _count(message_threads.exclude(pk__in=disposable_threads), lock))
    add('messages', 'Mensajes', len(message_ids))
    episode_id = _initial_episode_id(project, lock)
    add('state_history', 'Historial de estados añadido',
        _count(DocumentStateEpisode.objects.filter(project=project).exclude(pk=episode_id), lock))

    special_models = {Document, DocumentFolder, CommunicationThread, DocumentStateEpisode}
    relations = {}
    for relation in Project._meta.related_objects:
        model = relation.related_model
        if model not in special_models:
            query = Q(**{relation.field.name: project.pk})
            relations[model] = relations.get(model, Q()) | query
    for model, query in relations.items():
        key, label = DEPENDENCY_LABELS.get(
            model._meta.label_lower,
            (model._meta.label_lower, str(model._meta.verbose_name_plural)),
        )
        add(key, label, _count(model._base_manager.filter(query), lock))

    operational_fields = (
        'production_url', 'staging_url', 'admin_url', 'repository_url',
        'admin_username', 'admin_password_encrypted', 'progress', 'start_date',
        'estimated_end_date', 'payment_milestones', 'hosting_tiers', 'hosting_start_date',
    )
    add('configuration', 'Configuración operativa del proyecto',
        int(any(getattr(project, field) for field in operational_fields)))
    return blockers, disposable_folders, disposable_threads


def deletion_preview(project):
    blockers, _, _ = _dependency_inventory(project)
    return {
        'project': {'id': project.pk, 'name': project.name},
        'can_delete': not blockers,
        'blockers': blockers,
    }


@historical_write
@transaction.atomic
def delete_empty_project(project_id, *, actor):
    # Foreign-key writers serialize against this parent lock. Use the same
    # inventory as preview, freshly read inside the deletion transaction.
    project = Project.objects.select_for_update().get(pk=project_id)
    blockers, folder_ids, thread_ids = _dependency_inventory(project, lock=True)
    if blockers:
        raise ProjectDeleteBlocked({
            'project': {'id': project.pk, 'name': project.name},
            'can_delete': False, 'blockers': blockers,
        })
    capture_instance(project)
    log_project_event(project, AccountingChangeLog.Action.DELETED,
                      project_snapshot(project), actor)
    # Delete template leaves before roots: DocumentFolder.parent is PROTECT.
    DocumentFolder.objects.filter(pk__in=folder_ids, parent__isnull=False).delete()
    DocumentFolder.objects.filter(pk__in=folder_ids).delete()
    CommunicationThread.objects.filter(pk__in=thread_ids).delete()
    project.delete()
