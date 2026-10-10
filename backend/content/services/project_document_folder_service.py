"""Automatic document-folder lifecycle for platform projects.

`DocumentFolder.project` is the PA-64 association copied to descendants and
documents. `managed_project` has a narrower job: it marks the single root that
the system owns for a Project. Keeping those concepts separate lets operators
continue creating ordinary project-associated folders without turning them
into lifecycle-managed roots.
"""
import hashlib
import json
import logging
from uuid import uuid4

from accounts.services.project_catalog_service import (
    ACTIVE_PROJECT_EFFECTS,
)
from content.models import DocumentFolder
from content.models.document_folder import lock_document_folder_mutations
from content.services.diagnostic_privacy import register_mcp_domain_codes
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)
register_mcp_domain_codes('project_root_name_conflict')

ROOT_NAME_HINT = (
    'Usa create_project con root_folder_id tras revisar preview_folder_migration, '
    'o renombra la carpeta existente.'
)
_PROJECT_CONFIGURATION_FIELDS = (
    'production_url', 'staging_url', 'admin_url', 'repository_url',
    'admin_username', 'admin_password_encrypted', 'progress', 'start_date',
    'estimated_end_date', 'payment_milestones', 'hosting_tiers', 'hosting_start_date',
)


PROJECT_FOLDER_TEMPLATE = (
    ('Cuentas de cobro', 'collection_account'),
    ('Propuestas', 'commercial_proposal'),
    ('Entregables', None),
    ('QA', None),
)

class ProjectFolderReconciliationRequired(RuntimeError):
    """Raised when a historical project has not adopted a managed root yet."""


class ProjectRootNameConflict(APIException):
    """A manual root needs an explicit migration before using its name."""

    status_code = 400
    default_code = 'project_root_name_conflict'

    def __init__(self, folders, reasons):
        message = 'Ya existe una carpeta manual con el nombre del proyecto.'
        self.code = self.default_code
        self.details = {
            'folder_ids': [folder.pk for folder in folders],
            'paths': [folder.name for folder in folders],
            'reasons': reasons,
            'hint': ROOT_NAME_HINT,
        }
        super().__init__(message, code=self.code)
        self.detail = {'detail': message, 'code': self.code, **self.details}


def _manual_name_matches(name, *, exclude_folder_id=None):
    roots = DocumentFolder.objects.annotate(normalized_name=Lower(Trim('name'))).filter(
        parent__isnull=True, managed_project__isnull=True,
        managed_client__isnull=True, system_key__isnull=True,
        normalized_name=name.strip().lower(),
    ).order_by('pk')
    if exclude_folder_id is not None:
        roots = roots.exclude(pk=exclude_folder_id)
    return list(roots)


def _automatic_adoption_plan(name, folder):
    """Check eligibility independent of the future project's client.

    A name alone cannot authorize keeping an existing owner or exposing a
    document to an unknown client. The actual create request then previews the
    complete migration with its validated client and lifecycle state.
    """
    from content.services.document_ownership_planner import plan_ownership
    from content.services.folder_migration_service import _template_actions

    plan = plan_ownership(
        folder_ids=[folder.pk], destination_folder_id=None,
        client_policy='abort_on_conflict', portal_policy='abort',
    )
    blockers = plan['blockers']
    if folder.is_archived or folder.retention_context_id or len(name) > 120:
        blockers.append({'code': 'migration_blocked', 'folder_id': folder.pk})
    for row in plan['rows']:
        before = row['before']
        if row['status'] in ('pinned', 'frozen'):
            blockers.append({'code': row['status'], 'resource_type': row['resource_type'], 'resource_id': row['id']})
        elif before.get('client_user_id') is not None or before.get('project_id') is not None:
            blockers.append({'code': 'ownership_conflict', 'resource_type': row['resource_type'], 'resource_id': row['id']})
        elif row['resource_type'] == 'document' and before.get('is_client_visible'):
            blockers.append({'code': 'portal_exposure', 'resource_type': 'document', 'resource_id': row['id']})
    templates, _transferred, _discarded = _template_actions(folder, None, None, blockers)
    plan.update(
        strategy='adopt_source', source_folder_id=folder.pk,
        client_policy='abort_on_conflict', portal_policy='abort',
        template_folders=templates, can_apply=not blockers,
    )
    return plan


def project_root_name_decision(name, *, exclude_folder_id=None):
    """Create a root or adopt one strictly safe manual homonym."""
    matches = _manual_name_matches(name, exclude_folder_id=exclude_folder_id)
    if not matches:
        return {'decision': 'create'}
    if len(matches) != 1:
        raise ProjectRootNameConflict(matches, [{'code': 'multiple_manual_roots'}])
    plan = _automatic_adoption_plan(name, matches[0])
    if not plan['can_apply']:
        raise ProjectRootNameConflict(matches, plan['blockers'])
    return {'decision': 'adopt', 'folder_id': matches[0].pk, 'plan': plan}


def validate_project_root_rename(name, *, exclude_folder_id=None):
    """Renames never adopt a manual root implicitly."""
    matches = _manual_name_matches(name, exclude_folder_id=exclude_folder_id)
    if matches:
        raise ProjectRootNameConflict(matches, [{'code': 'rename_collision'}])
    return name


def lock_project_root_names():
    """Serialize root creation with the reviewed tree mutation engine."""
    lock_document_folder_mutations()


def auto_adopt_project_root(data, folder_id, *, actor):
    """Create through the migration engine so automatic adoption is undoable."""
    from accounts.models import Project
    from content.mcp.context import current_mcp_context
    from content.services.folder_migration_service import (
        apply_folder_migration,
        preview_folder_migration,
    )

    context = current_mcp_context()
    credential = context.credential if context else None
    preview = preview_folder_migration({
        'source_folder_id': folder_id, 'strategy': 'adopt_source',
        'target': {'create_project': data},
        'client_policy': 'abort_on_conflict', 'portal_policy': 'abort',
    }, actor=actor, credential=credential)
    if not preview['can_apply']:
        raise ProjectRootNameConflict(
            [DocumentFolder.objects.get(pk=folder_id)], preview['blockers'],
        )
    report = apply_folder_migration(
        preview['plan_token'], 'Adopción automática de la raíz del proyecto',
        f'auto-project-root:{uuid4()}', actor=actor, credential=credential, origin='auto',
    )
    project = Project.objects.get(pk=report['project_id'])
    project._document_root = {
        'folder_id': report['root_folder_id'], 'adopted': True,
        'migration_id': report['migration_id'],
    }
    return project


def project_document_root_result(project):
    """Expose the same root receipt in Panel, platform and MCP creates."""
    return getattr(project, '_document_root', None) or {
        'folder_id': require_project_folder(project).pk,
        'adopted': False, 'migration_id': None,
    }


def _creation_configuration_hash(project):
    configuration = {field: getattr(project, field) for field in _PROJECT_CONFIGURATION_FIELDS}
    encoded = json.dumps(configuration, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _notification_state(notification):
    return json.loads(json.dumps(notification, sort_keys=True, default=str))


def record_project_creation_extras(project, migration_id, notification):
    """Include platform startup facts in the automatic adoption's undo boundary."""
    from accounts.models import Notification
    from content.models import DocumentOwnershipOperation

    operation = DocumentOwnershipOperation.objects.select_for_update().get(
        pk=migration_id, created_project_id=project.pk, origin='auto',
    )
    operation.report['project_creation'] = {
        'configuration_hash': _creation_configuration_hash(project),
        'notification': _notification_state(Notification.objects.filter(pk=notification.pk).values().get()),
    }
    operation.save(update_fields=['report'])


def project_creation_undo_allowances(operation, project, *, lock):
    """Only unchanged startup facts may be removed with the created project."""
    from accounts.models import Notification

    baseline = operation.report.get('project_creation')
    if not baseline:
        return {}
    query = Notification.objects.filter(pk=baseline['notification']['id'], project=project)
    if lock:
        query = query.select_for_update()
    return {
        'configuration': int(_creation_configuration_hash(project) == baseline['configuration_hash']),
        'notifications': int(_notification_state(query.values().first()) == baseline['notification']),
    }


def clear_project_creation_extras(operation):
    """Remove startup facts after the migration's locked undo checks pass."""
    from accounts.models import Notification, Project
    from content.services.entity_history import capture_instance

    baseline = operation.report.get('project_creation')
    if not baseline:
        return
    project = Project.objects.get(pk=operation.created_project_id)
    capture_instance(project)
    Notification.objects.filter(pk=baseline['notification']['id'], project=project).delete()
    Project.objects.filter(pk=project.pk).update(**{
        field: Project._meta.get_field(field).get_default() for field in _PROJECT_CONFIGURATION_FIELDS
    })


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
    with transaction.atomic():
        return _update_root(root, project, created=created)


def _update_root(root, project, *, created):
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
    if root.name != project.name:
        matches = _manual_name_matches(project.name, exclude_folder_id=root.pk)
        if matches:
            expected.pop('name')
            logger.warning(
                'Keeping document root %s name for project %s: manual root conflict %s',
                root.pk, project.pk, [folder.pk for folder in matches],
            )
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
def adopt_project_root(project, folder):
    """Adopt a reviewed manual root without provisioning a competing tree.

    The migration engine owns policy validation and any disposable-root
    replacement. All constrained root markers change in one save.
    """
    folder.name = project.name
    folder.parent_id = None
    folder.managed_project = project
    folder.project = project
    folder.client_user_id = project.client_id
    folder.is_archived = False
    folder.archived_at = None
    folder.archived_via_folder_id = None
    folder.save(update_fields=[
        'name', 'parent', 'managed_project', 'project', 'client_user',
        'is_archived', 'archived_at', 'archived_via_folder', 'updated_at',
    ])
    for order, (name, kind) in enumerate(PROJECT_FOLDER_TEMPLATE):
        key = project_category_system_key(project.pk, kind) if kind else None
        query = DocumentFolder.objects.filter(system_key=key) if key else folder.children.annotate(
            normalized_name=Lower(Trim('name')),
        ).filter(normalized_name=name.lower())
        if not query.exists():
            DocumentFolder.objects.create(
                name=name, parent=folder, order=order, project=project,
                client_user_id=project.client_id, system_key=key,
                creation_source='system', creation_operation='adopt_project_root.template',
            )
    return folder


@transaction.atomic
def ensure_project_folder(project):
    """Return the project's single managed root, creating it when absent.

    The unique database relation is the concurrency guard. Template folders
    are created only with a genuinely new root, so adopting an existing tree
    during the reviewed migration never injects duplicate structure.
    """
    root = DocumentFolder.objects.select_for_update().filter(managed_project=project).first()
    if root is not None:
        return _synchronize_root(root, project, created=False)
    lock_project_root_names()
    matches = _manual_name_matches(project.name)
    if matches:
        raise ProjectRootNameConflict(matches, [{'code': 'root_adoption_required'}])
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
