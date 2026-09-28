"""Automatic document-folder lifecycle for platform projects.

`DocumentFolder.project` is the PA-64 association copied to descendants and
documents. `managed_project` has a narrower job: it marks the single root that
the system owns for a Project. Keeping those concepts separate lets operators
continue creating ordinary project-associated folders without turning them
into lifecycle-managed roots.
"""
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.services.project_catalog_service import (
    ACTIVE_PROJECT_EFFECTS,
    project_catalog_bucket,
)
from content.models import DocumentFolder


PROJECT_FOLDER_TEMPLATE = (
    ('Cuentas de cobro', 'collection_account'),
    ('Propuestas', 'commercial_proposal'),
    ('Entregables', None),
    ('QA', None),
)

class ProjectFolderReconciliationRequired(RuntimeError):
    """Raised when a historical project has not adopted a managed root yet."""


def project_category_system_key(project_id, document_kind):
    """Stable key shared by project roots and generated-document filing."""
    return f'generated:project:{project_id}:{document_kind}'


def require_project_folder(project):
    """Return the managed root without silently provisioning historical data."""
    root = DocumentFolder.objects.filter(
        managed_project=project,
        parent__isnull=True,
        is_archived=False,
    ).first()
    if root is None:
        raise ProjectFolderReconciliationRequired(
            f'El proyecto «{project.name}» no tiene una carpeta documental '
            'gestionada. Revisa y aplica la conciliación PA-108 antes de '
            'generar documentos.'
        )
    return root


def project_folder_readiness():
    """Summarize reviewed-root adoption for every canonical project."""
    from accounts.models import Project

    all_projects = Project.objects.all()
    projects = all_projects
    active_projects = projects.filter(
        Q(current_state__operational_effect__in=ACTIVE_PROJECT_EFFECTS)
        | Q(
            current_state__isnull=True,
            status__in=(Project.STATUS_DEVELOPMENT, Project.STATUS_ACTIVE),
        )
    )
    roots = DocumentFolder.objects.filter(
        managed_project__isnull=False,
        parent__isnull=True,
        is_archived=False,
    )
    project_count = all_projects.count()
    enabled_project_count = projects.count()
    active_project_count = active_projects.count()
    archived_project_count = enabled_project_count - active_project_count
    managed_root_count = roots.count()
    active_managed_root_count = roots.filter(
        Q(
            managed_project__current_state__operational_effect__in=(
                ACTIVE_PROJECT_EFFECTS
            ),
        )
        | Q(
            managed_project__current_state__isnull=True,
            managed_project__status__in=(
                Project.STATUS_DEVELOPMENT, Project.STATUS_ACTIVE,
            ),
        )
    ).count()
    missing_root_count = max(enabled_project_count - managed_root_count, 0)
    missing_active_root_count = max(
        active_project_count - active_managed_root_count,
        0,
    )

    if project_count == 0:
        readiness_status = 'no_projects'
    elif missing_root_count:
        readiness_status = 'reconciliation_required'
    else:
        readiness_status = 'ready'

    return {
        'status': readiness_status,
        'project_count': project_count,
        'enabled_project_count': enabled_project_count,
        'disabled_project_count': project_count - enabled_project_count,
        'active_project_count': active_project_count,
        'archived_project_count': archived_project_count,
        'managed_root_count': managed_root_count,
        'active_managed_root_count': active_managed_root_count,
        'missing_root_count': missing_root_count,
        'missing_active_root_count': missing_active_root_count,
    }


def _synchronize_root(root, project, *, created):
    update_fields = []
    expected = {
        'name': project.name,
        'parent_id': None,
        'project_id': project.pk,
        'client_user_id': project.client_id,
        'is_archived': False,
        'archived_at': None,
        'archived_via_folder_id': None,
    }
    for field, value in expected.items():
        if getattr(root, field) != value:
            setattr(root, field, value)
            update_fields.append(field.removesuffix('_id'))
    if update_fields:
        root.save(update_fields=[*update_fields, 'updated_at'])

    if created:
        for order, (name, document_kind) in enumerate(PROJECT_FOLDER_TEMPLATE):
            DocumentFolder.objects.create(
                creation_source='system', creation_operation='ensure_project_folder.template',
                name=name,
                parent=root,
                order=order,
                project=project,
                client_user=project.client,
                system_key=(
                    project_category_system_key(project.pk, document_kind)
                    if document_kind else None
                ),
            )

    # A Project client move keeps only folders that still point at that same
    # project coherent. A deliberately reassigned sub-branch is left alone.
    descendant_ids = root.get_descendant_ids()
    if descendant_ids:
        DocumentFolder.objects.filter(
            pk__in=descendant_ids,
            project_id=project.pk,
        ).exclude(client_user_id=project.client_id).update(
            client_user_id=project.client_id,
            updated_at=timezone.now(),
        )
    return root


@transaction.atomic
def synchronize_existing_project_folder(project):
    """Synchronize an adopted root, but never provision a historical one."""
    root = DocumentFolder.objects.select_for_update().filter(
        managed_project=project,
    ).first()
    if root is None:
        return None
    return _synchronize_root(root, project, created=False)


@transaction.atomic
def ensure_project_folder(project):
    """Return the project's single managed root, creating it when absent.

    The unique database relation is the concurrency guard. Template folders
    are created only with a genuinely new root, so adopting an existing tree
    during the reviewed migration never injects duplicate structure.
    """
    defaults = {
        'creation_source': 'system', 'creation_operation': 'ensure_project_folder',
        'name': project.name,
        'parent': None,
        'project': project,
        'client_user': project.client,
    }
    try:
        # The nested savepoint keeps the outer transaction usable when the
        # unique constraint reports a concurrent winner.
        with transaction.atomic():
            root, created = DocumentFolder.objects.get_or_create(
                managed_project=project,
                defaults=defaults,
            )
    except IntegrityError:
        # A concurrent creator won the OneToOne race. Its transaction owns the
        # template creation; this caller only needs the canonical root.
        root = DocumentFolder.objects.select_for_update().get(
            managed_project=project,
        )
        created = False

    return _synchronize_root(root, project, created=created)
