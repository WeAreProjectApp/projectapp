"""Ciclo de vida de la comunicación madre de un proyecto.

Espejo de `project_document_folder_service`, con una diferencia que impone el
dominio: un hilo **exige cliente** (`CommunicationThread.client` es NOT NULL),
y `Project.client` es `auth.User` mientras el hilo habla `UserProfile`. La
resolución de ese salto vive acá, y falla en silencio reportando en vez de
reventar: esto corre dentro del `post_save` de Project, y un proyecto no puede
quedar sin crearse porque su cliente no tenga perfil.
"""
from django.db import IntegrityError, transaction

from content.models import CommunicationThread


class ProjectCommunicationThreadUnavailable(RuntimeError):
    """Raised when a project cannot own a thread yet (no usable client profile)."""


def resolve_client_profile(project):
    """Perfil de cliente del proyecto, o None si no sirve como dueño de un hilo."""
    user = getattr(project, 'client', None)
    profile = getattr(user, 'profile', None) if user else None
    if profile is None:
        return None
    if profile.role != profile.ROLE_CLIENT:
        return None
    return profile


def require_project_thread(project):
    """Devuelve la madre sin provisionarla en silencio."""
    thread = CommunicationThread.objects.filter(
        managed_project=project,
        is_archived=False,
    ).first()
    if thread is None:
        raise ProjectCommunicationThreadUnavailable(
            f'El proyecto «{project.name}» no tiene comunicación madre.'
        )
    return thread


def project_thread_values(project, profile):
    """Read-only target shared by synchronization and integrity previews."""
    return {
        'title': project.name,
        'project_id': project.pk,
        'client_id': profile.pk,
        'is_archived': False,
        'archived_at': None,
    }


def _synchronize_root(thread, project, profile):
    """Mantiene la madre coherente con el proyecto que representa."""
    update_fields = []
    expected = project_thread_values(project, profile)
    for field, value in expected.items():
        if getattr(thread, field) != value:
            setattr(thread, field, value)
            update_fields.append(field.removesuffix('_id'))
    if update_fields:
        thread.save(update_fields=[*update_fields, 'updated_at'])
    return thread


@transaction.atomic
def synchronize_existing_project_thread(project):
    """Sincroniza una madre ya adoptada; nunca provisiona una que falte."""
    thread = CommunicationThread.objects.select_for_update().filter(
        managed_project=project,
    ).first()
    if thread is None:
        return None
    profile = resolve_client_profile(project)
    if profile is None:
        return thread
    return _synchronize_root(thread, project, profile)


@transaction.atomic
def ensure_project_thread(project):
    """Devuelve la única madre del proyecto, creándola si falta.

    La relación única es el guardia de concurrencia, igual que en carpetas.
    Devuelve None —sin crear nada— cuando el cliente del proyecto todavía no
    tiene un perfil utilizable: el caller decide si eso es un salto reportable
    o un error.
    """
    profile = resolve_client_profile(project)
    if profile is None:
        return None

    defaults = {
        'title': project.name,
        'project': project,
        'client': profile,
    }
    try:
        # El savepoint anidado deja usable la transacción exterior cuando la
        # relación única reporta un ganador concurrente.
        with transaction.atomic():
            thread, _created = CommunicationThread.objects.get_or_create(
                managed_project=project,
                defaults=defaults,
            )
    except IntegrityError:
        thread = CommunicationThread.objects.select_for_update().get(
            managed_project=project,
        )
    return _synchronize_root(thread, project, profile)
