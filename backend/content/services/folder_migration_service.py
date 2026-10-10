"""Pure migration plans, signed intent and atomic, exactly reversible writes."""

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

from accounts.models import (
    ContractAmendment,
    DeliveryDocumentLink,
    Project,
    ProjectContract,
    UserProfile,
)
from content.models import (
    Document,
    DocumentFolder,
    DocumentOwnershipOperation,
    DocumentState,
)
from content.models.document_folder import DocumentFolderMutationLock
from content.serializers.folder_migration import (
    FolderMigrationSerializer,
    MigrationApplySerializer,
    MigrationUndoSerializer,
)
from content.serializers.panel_projects import CreatePanelProjectSerializer
from content.services import project_service
from content.services.contract_mirror_service import (
    is_contract_mirror,
    mirror_documents,
    pinned_mirror_folder,
)
from content.services.diagnostic_privacy import register_mcp_domain_codes
from content.services.document_folder_service import document_portal_audience
from content.services.document_ownership_planner import (
    OwnershipPlanError,
    apply_ownership_plan,
    plan_ownership,
)
from content.services.entity_history import capture_instance, historical_write
from content.services.project_deletion_service import (
    _automatic_folder_ids,
    _dependency_inventory,
    delete_empty_project,
)
from content.services.project_document_folder_service import (
    PROJECT_FOLDER_TEMPLATE,
    adopt_project_root,
    clear_project_creation_extras,
    project_category_system_key,
    project_creation_undo_allowances,
    require_project_folder,
)
from content.services.project_state_service import (
    LEGACY_STATUS_BY_EFFECT,
    initialize_project_state,
)
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied

TOKEN_SALT = 'content.folder_migration'
TOKEN_MAX_AGE = 1800
NEW_PROJECT = 'new_project'
NEW_ROOT = 'new_root'
MODELS = {'content.document': Document, 'content.documentfolder': DocumentFolder}
FOLDER_FIELDS = (
    'name', 'parent_id', 'order', 'client_user_id', 'project_id', 'managed_project_id',
    'managed_client_id', 'system_key', 'is_archived', 'archived_at', 'archived_via_folder_id', 'retention_context_id',
)
DOCUMENT_FIELDS = (
    'folder_id', 'client_user_id', 'project_id', 'is_client_visible',
    'is_archived', 'archived_at', 'archived_via_folder_id', 'retention_context_id',
)
register_mcp_domain_codes(
    'plan_token_invalid', 'source_name_conflict', 'template_name_conflict', 'migration_blocked',
    'undo_blocked', 'changed_since', 'new_content_since', 'project_in_use', 'already_reverted',
    'request_id_conflict', 'undo_audience_changed',
)


class FolderMigrationError(OwnershipPlanError):
    def __init__(self, message, *, code='migration_blocked', **details):
        super().__init__(message, code=code, **details)


def _json(value):
    return json.loads(json.dumps(value, default=lambda obj: obj.isoformat(), ensure_ascii=False))


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def _state(row):
    fields = DOCUMENT_FIELDS if isinstance(row, Document) else FOLDER_FIELDS
    return _json({field: getattr(row, field) for field in fields})


def _item(row, before=None):
    state = _state(row)
    return {'model': row._meta.label_lower, 'id': row.pk, 'before': state if before is None else before, 'after': state}


def _normalized(data):
    serializer = FolderMigrationSerializer(data=data, context={'folder_migration': True})
    serializer.is_valid(raise_exception=True)
    return dict(serializer.data)


def _identity(actor, credential):
    from content.mcp.actor import mcp_actor
    from content.mcp.context import current_mcp_context
    context = current_mcp_context()
    actor = actor or (context.actor if context else None) or mcp_actor()
    credential = credential or (context.credential if context else None)
    return actor, credential


def _block(code, message, **details):
    return {'code': code, 'message': message, **details}


def _current(queryset, lock):
    return queryset.select_for_update() if lock else queryset


def _subtree(roots, *, lock=False):
    if lock:
        found = set(_current(DocumentFolder.objects.filter(pk__in=set(roots) - {None}).order_by('pk'), True).values_list('pk', flat=True))
        pending = found
        while pending:
            pending = set(_current(DocumentFolder.objects.filter(parent_id__in=pending).order_by('pk'), True).values_list('pk', flat=True)) - found
            found.update(pending)
        return found
    topology = dict(DocumentFolder.objects.values_list('pk', 'parent_id'))
    found, pending = set(), set(roots) - {None}
    while pending:
        found.update(pending)
        pending = {pk for pk, parent in topology.items() if parent in pending} - found
    return found & set(topology)


def _target(data, *, lock=False):
    if 'project_id' in data['target']:
        project = _current(Project.objects.filter(pk=data['target']['project_id']), lock).first()
        if project is None:
            raise NotFound('Proyecto no encontrado.')
        return project, project.name, {'client_user_id': project.client_id, 'project_id': project.pk}, None
    serializer = CreatePanelProjectSerializer(
        data=data['target']['create_project'], context={'folder_migration': True},
    )
    serializer.is_valid(raise_exception=True)
    state = serializer.validated_data.get('state') or DocumentState.objects.get(
        catalog='projects', system_key=Project.STATUS_DEVELOPMENT, is_active=True, merged_into__isnull=True,
    )
    return None, serializer.validated_data['name'], {
        'client_user_id': serializer.client_profile.user_id, 'project_id': NEW_PROJECT,
    }, state


def _template_actions(source, root, project, blockers, *, lock=False):
    children = list(_current(source.children.order_by('pk'), lock))
    transferred = list(_current(root.children.order_by('pk'), lock)) if root else []
    actions, discarded = [], []
    for order, (name, kind) in enumerate(PROJECT_FOLDER_TEMPLATE):
        matches = [row for row in children if row.name.strip().lower() == name.lower()]
        if kind and matches:
            blockers.append(_block('template_name_conflict', f'La carpeta manual «{name}» ocupa una categoría automática.', folder_ids=[row.pk for row in matches]))
        if len(matches) > 1:
            blockers.append(_block('duplicate_folder_name', f'Hay varias carpetas «{name}».', folder_ids=[row.pk for row in matches]))
        existing = matches[0] if matches else next((row for row in transferred if row.name == name), None)
        if kind and project:
            key = project_category_system_key(project.pk, kind)
            misplaced = _current(DocumentFolder.objects.filter(system_key=key).exclude(pk__in=[row.pk for row in transferred]), lock)
            if misplaced.exists():
                blockers.append(_block('template_name_conflict', f'La categoría automática «{name}» existe fuera de la raíz descartable.', folder_ids=list(misplaced.values_list('pk', flat=True))))
        if matches and not kind:
            discarded.extend(row.pk for row in transferred if row.name.strip().lower() == name.lower())
        actions.append({
            'action': 'reuse' if existing else 'create', 'id': existing.pk if existing else None,
            'name': name, 'order': order,
            'system_key': project_category_system_key(project.pk if project else NEW_PROJECT, kind) if kind else None,
        })
    return actions, [row for row in transferred if row.pk not in discarded], discarded


def _source_actions(data, source, name, owner, remaining, blockers, *, lock=False):
    before, after = _state(source), _state(source)
    renames = []
    if 'source_rename_to' in data:
        new_name = data['source_rename_to']
        duplicates = _current(source.__class__.objects.annotate(normalized=Lower(Trim('name'))).filter(
            parent_id=source.parent_id, normalized=new_name.strip().lower(),
        ).exclude(pk=source.pk), lock)
        if duplicates.exists():
            blockers.append(_block('duplicate_folder_name', 'El nombre elegido para la fuente ya existe.', folder_ids=list(duplicates.values_list('pk', flat=True))))
        renames.append({'folder_id': source.pk, 'before': source.name, 'after': new_name})
        after['name'] = new_name
    archive = {'requested': data.get('archive_source_when_empty', False), 'will_archive': False, 'pending': []}
    if data['strategy'] == 'adopt_source':
        after.update(name=name, parent_id=None, client_user_id=owner['client_user_id'],
                     project_id=owner['project_id'], managed_project_id=owner['project_id'],
                     is_archived=False, archived_at=None, archived_via_folder_id=None)
    elif archive['requested']:
        archive['will_archive'] = not remaining
        archive['pending'] = remaining
        if not remaining:
            after.update(is_archived=True, archived_at='apply_time', archived_via_folder_id=None)
    return {'folder_id': source.pk, 'before': before, 'after': after}, renames, archive


def _build_plan(data, *, lock=False):
    source = _current(DocumentFolder.objects.filter(pk=data['source_folder_id']), lock).first()
    if source is None:
        raise NotFound('Carpeta fuente no encontrada.')
    project, name, owner, state = _target(data, lock=lock)
    root = _current(DocumentFolder.objects.filter(managed_project=project), lock).first() if project else None
    blockers, warnings = [], []
    adopt = data['strategy'] == 'adopt_source'
    if source.is_archived or source.retention_context_id or source.system_key or source.managed_project_id or source.managed_client_id or adopt and source.parent_id:
        blockers.append(_block('migration_blocked', 'La fuente debe ser una carpeta manual activa y no conservada; para adoptar, debe ser raíz.', folder_id=source.pk))
    pinned, _pin_origin = pinned_mirror_folder()
    if adopt and pinned and source.pk == pinned.pk:
        blockers.append(_block('contract_mirror_folder_pinned', 'La carpeta fijada de contratos debe permanecer sin cliente ni proyecto.', folder_id=source.pk))
    if len(name) > 120:
        blockers.append(_block('migration_blocked', 'El nombre del proyecto supera los 120 caracteres de una carpeta.'))
    if root and root.pk in _subtree([source.pk], lock=lock):
        blockers.append(_block('migration_blocked', 'El destino está dentro de la fuente.'))
    disposable = None
    transferred = []
    discarded_templates = []
    if adopt and root:
        root_ids = _subtree([root.pk], lock=lock)
        if root_ids != set(_automatic_folder_ids(project, lock)) or _current(Document.objects.filter(folder_id__in=root_ids), lock).exists():
            blockers.append(_block('migration_blocked', 'La raíz del proyecto contiene información o carpetas personalizadas.', folder_id=root.pk))
        else:
            disposable = root
    if adopt:
        template_actions, transferred, discarded_templates = _template_actions(source, disposable, project, blockers, lock=lock)
        folders, documents, destination = [source.pk], [], None
        warnings.append(_block('managed_root_synchronization', 'Cada guardado posterior del proyecto impondrá el nombre del proyecto, padre nulo, cliente y estado activo de la raíz.'))
    else:
        template_actions = [] if root else [{'action': 'create', 'id': None, 'name': child_name, 'order': order,
            'system_key': project_category_system_key(project.pk if project else NEW_PROJECT, kind) if kind else None}
            for order, (child_name, kind) in enumerate(PROJECT_FOLDER_TEMPLATE)]
        child_ids = set(_current(source.children.order_by('pk'), lock).values_list('pk', flat=True))
        document_ids = set(_current(source.documents.order_by('pk'), lock).values_list('pk', flat=True))
        folders = data.get('include_folder_ids', sorted(child_ids))
        documents = data.get('include_document_ids', sorted(document_ids))
        if set(folders) - child_ids or set(documents) - document_ids:
            raise serializers.ValidationError('Los filtros sólo pueden incluir hijos y documentos directos de la fuente.')
        destination = root.pk if root else None
        if project and root is None:
            blockers.append(_block('migration_blocked', 'El proyecto existente no tiene raíz; usa adopt_source.'))
        destination_names = {row.name.strip().lower() for row in _current(root.children.order_by('pk'), lock)} if root else {child_name.lower() for child_name, _kind in PROJECT_FOLDER_TEMPLATE}
        selected_names = {}
        for child in _current(DocumentFolder.objects.filter(pk__in=folders).order_by('pk'), lock):
            normalized_name = child.name.strip().lower()
            if normalized_name in destination_names or normalized_name in selected_names:
                blockers.append(_block('duplicate_folder_name', f'El destino ya tiene una carpeta «{child.name}».', folder_id=child.pk))
            selected_names[normalized_name] = child.pk
        proposed_source_name = data.get('source_rename_to', source.name)
        if source.parent_id is None and proposed_source_name.strip().lower() == name.strip().lower():
            blockers.append(_block('source_name_conflict', 'Renombra la fuente con source_rename_to antes de crear o usar una raíz homónima.', folder_ids=[source.pk]))
    manual_roots = list(_current(DocumentFolder.objects.annotate(normalized=Lower(Trim('name'))).filter(
        parent__isnull=True, managed_project__isnull=True, managed_client__isnull=True,
        system_key__isnull=True, normalized=name.strip().lower(),
    ).exclude(pk=source.pk).order_by('pk'), lock).values_list('pk', flat=True))
    if manual_roots:
        blockers.append(_block('source_name_conflict', 'Otra raíz manual tiene el nombre del proyecto; renómbrala antes de migrar.', folder_ids=manual_roots))
    planner_input = {
        'folder_ids': folders, 'document_ids': documents, 'destination_folder_id': destination,
        'destination_owner': owner, 'client_policy': data['client_policy'],
        'portal_policy': data['portal_policy'], 'document_decisions': data['document_decisions'],
    }
    ownership = plan_ownership(**planner_input, lock=lock) if folders or documents else {
        'rows': [], 'blockers': [], 'warnings': [], 'plan_hash': _hash(planner_input), 'can_apply': True, 'totals': {},
    }
    rows = deepcopy(ownership['rows'])
    for row in rows:
        if adopt and row['resource_type'] == 'folder' and row['id'] == source.pk:
            row['after'].update(client_user_id=owner['client_user_id'], project_id=owner['project_id'],
                client_profile_id=UserProfile.objects.get(user_id=owner['client_user_id']).pk,
                project_client_user_id=owner['client_user_id'])
            if row['status'] == 'unchanged' and row['before'] != row['after']:
                row['status'] = 'changed'
        if not adopt and destination is None and row['after'].get('folder_or_parent_id') is None:
            row['after']['folder_or_parent_id'] = NEW_ROOT
    blockers.extend(ownership['blockers'])
    warnings.extend(ownership['warnings'])
    by_id = {(row['resource_type'], row['id']): row for row in rows}
    remaining = []
    for kind, children in (('folder', source.children.all()), ('document', source.documents.all())):
        for child in _current(children.order_by('pk'), lock):
            row = by_id.get((kind, child.pk))
            if row is None or row['after']['folder_or_parent_id'] == source.pk:
                remaining.append({'resource_type': kind, 'id': child.pk})
    source_action, renames, archive = _source_actions(data, source, name, owner, remaining, blockers, lock=lock)
    if archive['pending']:
        warnings.append(_block('archive_pending', 'La fuente conserva elementos, incluidos los archivados; seguirá activa.', records=remaining))
    scope_roots = [source.pk, root.pk if root else None, *[row.get('destination_folder_id') for row in data['document_decisions']]]
    baseline_folders = _subtree(scope_roots, lock=lock)
    baseline_documents = set(_current(Document.objects.filter(folder_id__in=baseline_folders).order_by('pk'), lock).values_list('pk', flat=True))
    baseline = {'folder_ids': sorted(baseline_folders), 'document_ids': sorted(baseline_documents)}
    structure = [_item(row) for row in _current(DocumentFolder.objects.filter(pk__in=baseline_folders).order_by('pk'), lock)]
    content = [_item(row) for row in _current(Document.objects.filter(pk__in=baseline_documents).order_by('pk'), lock)]
    folder_actions = [source_action] + [{'folder_id': row.pk, 'before': _state(row), 'after': {**_state(row), 'parent_id': source.pk}} for row in transferred]
    root_id = source.pk if adopt else destination or NEW_ROOT
    plan = {
        'input': data, 'strategy': data['strategy'], 'rows': rows, 'ownership_plan_hash': ownership['plan_hash'],
        'project_actions': {'action': 'create' if project is None else 'adopt' if adopt else 'use',
                            'project_id': owner['project_id'], 'client_user_id': owner['client_user_id'],
                            'name': name, 'state_id': state.pk if state else project.current_state_id},
        'template_folders': template_actions, 'folder_actions': folder_actions, 'renames': renames,
        'archive': archive, 'disposable_root_id': disposable.pk if disposable else None,
        'disposable_template_ids': discarded_templates,
        'final_tree': {'root_id': root_id, 'name': name, 'parent_id': None,
                       'items': [{'resource_type': row['resource_type'], 'id': row['id'],
                                  'parent_or_folder_id': row['after'].get('folder_or_parent_id')} for row in rows],
                       'remaining_in_source': remaining if not adopt else []},
        'baseline': baseline, 'can_apply': not blockers, 'blockers': blockers, 'warnings': warnings,
    }
    plan['after_hash'] = _hash([{'resource_type': row['resource_type'], 'id': row['id'], 'after': row['after']} for row in rows])
    plan['plan_hash'] = _hash({'plan': plan, 'structure': structure, 'content': content,
        'project': project_service.project_snapshot(project) if project else None})
    return plan


def preview_folder_migration(input, *, actor=None, credential=None):
    """Plan without provisioning folders, projects, mutexes or audit records."""
    actor, credential = _identity(actor, credential)
    plan = _build_plan(_normalized(input))
    plan['plan_token'] = _sign_plan(plan['input'], plan['plan_hash'], actor, credential)
    return plan


def _sign_plan(input, plan_hash, actor, credential):
    return signing.dumps({
        'v': 1, 'input': input, 'plan_hash': plan_hash,
        'credential_id': credential.pk if credential else None, 'actor_id': actor.pk,
    }, salt=TOKEN_SALT, compress=True)


def decode_plan_token(plan_token, *, actor=None, credential=None):
    actor, credential = _identity(actor, credential)
    try:
        payload = signing.loads(plan_token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        if not isinstance(payload, dict) or payload.get('v') != 1 or not {'input', 'plan_hash', 'actor_id', 'credential_id'} <= payload.keys():
            raise signing.BadSignature('Invalid migration payload')
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise FolderMigrationError('La vista previa venció o su token no es válido; vuelve a previsualizar.', code='plan_token_invalid') from exc
    if payload['actor_id'] != actor.pk or payload['credential_id'] != (credential.pk if credential else None):
        raise PermissionDenied('La vista previa pertenece a otra credencial o actor.')
    return payload


def plan_from_token(plan_token, *, actor=None, credential=None):
    payload = decode_plan_token(plan_token, actor=actor, credential=credential)
    return payload, _build_plan(_normalized(payload['input']))


def _require_plan(plan, expected_hash):
    if plan['plan_hash'] != expected_hash:
        raise FolderMigrationError('La vista previa cambió; vuelve a revisar el plan.', code='stale_version', plan_hash=plan['plan_hash'])
    if plan['blockers']:
        raise FolderMigrationError('La migración tiene bloqueos; no se modificó ningún registro.', blockers=plan['blockers'])


def _lock_scope(plan, *, restore_project_ids=()):
    # The mutex precedes projects, then folders, then documents, all in pk order.
    DocumentFolderMutationLock.objects.select_for_update().get(pk=1)
    folder_ids = set(plan['baseline']['folder_ids'])
    folder_ids.update(DocumentFolder.objects.filter(parent__isnull=True).values_list('pk', flat=True))
    folder_query = DocumentFolder.objects.filter(pk__in=folder_ids).order_by('pk')
    document_query = Document.objects.filter(pk__in=plan['baseline']['document_ids']).order_by('pk')
    previous_folders = {row.pk: _state(row) for row in folder_query}
    document_guard_fields = (*DOCUMENT_FIELDS, 'document_type_id', 'commercial_status', 'generated_file', 'deliverable_id')

    def document_guard(row):
        return {key: str(getattr(row, key)) if key == 'generated_file' else getattr(row, key) for key in document_guard_fields}

    previous_documents = {row.pk: document_guard(row) for row in document_query}
    projects = {value for row in plan['rows'] for state in ('before', 'after')
                for value in [row[state].get('project_id')] if type(value) is int}
    projects.update(restore_project_ids)
    if type(plan['project_actions']['project_id']) is int:
        projects.add(plan['project_actions']['project_id'])
    projects.update(DocumentFolder.objects.filter(pk__in=folder_ids, project__isnull=False).values_list('project_id', flat=True))
    projects.update(document_query.filter(project__isnull=False).values_list('project_id', flat=True))
    list(Project.objects.select_for_update().filter(pk__in=projects).order_by('pk'))
    current_folders = {row.pk: _state(row) for row in folder_query.select_for_update()}
    current_documents = {row.pk: document_guard(row) for row in document_query.select_for_update()}
    current_folder_ids = _subtree(plan['baseline']['folder_ids'], lock=True)
    current_document_ids = set(Document.objects.select_for_update().filter(folder_id__in=current_folder_ids).order_by('pk').values_list('pk', flat=True))
    if (previous_folders != current_folders or previous_documents != current_documents
            or current_folder_ids != set(plan['baseline']['folder_ids'])
            or current_document_ids != set(plan['baseline']['document_ids'])):
        raise FolderMigrationError('El alcance cambió durante la adquisición de candados; vuelve a previsualizar.', code='stale_version')
    planned_links = {row['id']: row['before']['delivery_linked'] for row in plan['rows'] if row['resource_type'] == 'document' and row['before']}
    linked_ids = set()
    for model in (DeliveryDocumentLink, ProjectContract, ContractAmendment):
        linked_ids.update(model.objects.select_for_update().filter(document_id__in=planned_links).order_by('pk').values_list('document_id', flat=True))
    if any(bool(pk in linked_ids) != expected for pk, expected in planned_links.items()):
        raise FolderMigrationError('Un documento adquirió o perdió un vínculo de entrega; vuelve a previsualizar.', code='stale_version')


def _replay(request_id, plan_hash, actor, credential, *, lock=False):
    operation = _current(DocumentOwnershipOperation.objects.filter(request_id=request_id), lock).first()
    if operation is None:
        return None
    if operation.actor_id != actor.pk or operation.credential_id != (credential.pk if credential else None):
        raise PermissionDenied('Este request_id pertenece a otra credencial o actor.')
    if operation.plan_hash != plan_hash:
        raise FolderMigrationError('Este request_id ya pertenece a otro plan.', code='request_id_conflict')
    return operation.report


def _create_project(data, *, actor, source=None):
    serializer = CreatePanelProjectSerializer(
        data=data, context={'request': SimpleNamespace(user=actor), 'folder_migration': True},
    )
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data
    state = validated.get('state') or DocumentState.objects.get(
        catalog='projects', system_key=Project.STATUS_DEVELOPMENT, is_active=True, merged_into__isnull=True,
    )
    project = Project(name=validated['name'], description=validated.get('description', ''),
                      client=serializer.client_profile.user, current_state=state,
                      status=LEGACY_STATUS_BY_EFFECT[state.operational_effect])
    if source is not None:
        project._pending_root_adoption = source
    project.save()
    initialize_project_state(project, state, actor=actor)
    project_service.log_project_event(project, project_service.Action.CREATED, {}, actor)
    return project


def _delete_disposable_root(root_id, source, discarded_templates=()):
    if root_id is None:
        return []
    root = DocumentFolder.objects.get(pk=root_id)
    snapshots = [_folder_snapshot(root)]
    capture_instance(root)
    for child in root.children.order_by('pk'):
        capture_instance(child)
        if child.pk in discarded_templates:
            snapshots.append(_folder_snapshot(child))
            child.delete()
            continue
        child.parent = source
        child.save(update_fields=['parent', 'updated_at'])
    root.delete()
    return snapshots


def _folder_snapshot(folder):
    return _json({field.attname: getattr(folder, field.attname) for field in folder._meta.concrete_fields if field.name != 'updated_at'})


def _resolved_state(state, project, root):
    result = dict(state)
    for key in ('project_id', 'managed_project_id'):
        if result.get(key) == NEW_PROJECT:
            result[key] = project.pk
    for key in ('folder_or_parent_id', 'parent_id', 'folder_id'):
        if result.get(key) == NEW_ROOT:
            result[key] = root.pk
    return result


def _check_postconditions(plan, project, root, applied):
    if DocumentFolder.objects.filter(managed_project=project).count() != 1 or require_project_folder(project).pk != root.pk:
        raise FolderMigrationError('No quedó exactamente una raíz gestionada.')
    manual = DocumentFolder.objects.annotate(normalized=Lower(Trim('name'))).filter(
        parent__isnull=True, managed_project__isnull=True, managed_client__isnull=True,
        system_key__isnull=True, normalized=project.name.strip().lower(),
    )
    if manual.exists():
        raise FolderMigrationError('Quedó una raíz manual homónima del proyecto.')
    pinned, _origin = pinned_mirror_folder()
    if pinned and (pinned.is_archived or pinned.client_user_id is not None or pinned.project_id is not None
                   or mirror_documents(Document.objects.all()).exclude(folder=pinned).exists()
                   or mirror_documents(Document.objects.all()).filter(Q(client_user__isnull=False) | Q(project__isnull=False)).exists()):
        raise FolderMigrationError('La carpeta fijada no conserva todos los espejos activos.')
    actual = {(row['resource_type'], row['id']): row['after'] for row in applied['rows']}
    canonical_after = []
    for row in plan['rows']:
        state = dict(actual.get((row['resource_type'], row['id']), {}))
        if plan['project_actions']['project_id'] == NEW_PROJECT and state.get('project_id') == project.pk:
            state['project_id'] = NEW_PROJECT
        if plan['final_tree']['root_id'] == NEW_ROOT and state.get('folder_or_parent_id') == root.pk:
            state['folder_or_parent_id'] = NEW_ROOT
        canonical_after.append({'resource_type': row['resource_type'], 'id': row['id'], 'after': state})
    if _hash(canonical_after) != plan['after_hash']:
        raise FolderMigrationError('La huella del estado posterior no coincide con el destino hipotético confirmado.')
    for row in plan['rows']:
        expected = _resolved_state(row['after'], project, root)
        if actual.get((row['resource_type'], row['id'])) != expected:
            raise FolderMigrationError('El resultado de propiedad no coincide con el plan.', resource_id=row['id'])
        obj = MODELS['content.document' if row['resource_type'] == 'document' else 'content.documentfolder'].objects.get(pk=row['id'])
        placement = obj.folder_id if isinstance(obj, Document) else obj.parent_id
        if (obj.client_user_id, obj.project_id, placement) != (expected['client_user_id'], expected['project_id'], expected['folder_or_parent_id']):
            raise FolderMigrationError('El estado guardado no coincide con el plan.', resource_id=row['id'])
        if isinstance(obj, Document) and obj.is_client_visible != expected['is_client_visible']:
            raise FolderMigrationError('La visibilidad guardada no coincide con el plan.', resource_id=row['id'])
    for action in plan['folder_actions']:
        actual_state = _state(DocumentFolder.objects.get(pk=action['folder_id']))
        expected = _resolved_state(action['after'], project, root)
        if expected['archived_at'] == 'apply_time':
            if actual_state['archived_at'] is None:
                raise FolderMigrationError('La fuente no quedó archivada.')
            expected['archived_at'] = actual_state['archived_at']
        # Ownership of the migrated subtree is checked against planner rows.
        for key in ('name', 'parent_id', 'managed_project_id', 'is_archived', 'archived_at', 'archived_via_folder_id'):
            if actual_state[key] != expected[key]:
                raise FolderMigrationError('La estructura guardada no coincide con el plan.', folder_id=action['folder_id'])


@historical_write
@transaction.atomic
def apply_folder_migration(plan_token, reason, request_id, *, actor, credential=None, origin=None):
    args = MigrationApplySerializer(data={'plan_token': plan_token, 'reason': reason, 'request_id': request_id})
    args.is_valid(raise_exception=True)
    reason, request_id = args.validated_data['reason'], args.validated_data['request_id']
    payload = decode_plan_token(plan_token, actor=actor, credential=credential)
    replay = _replay(request_id, payload['plan_hash'], actor, credential)
    if replay is not None:
        return replay
    initial = _build_plan(_normalized(payload['input']))
    _lock_scope(initial)
    replay = _replay(request_id, payload['plan_hash'], actor, credential, lock=True)
    if replay is not None:
        return replay
    plan = _build_plan(_normalized(payload['input']), lock=True)
    _require_plan(plan, payload['plan_hash'])
    data = plan['input']
    tracked = {('content.documentfolder', pk): _state(row) for pk in plan['baseline']['folder_ids']
               if (row := DocumentFolder.objects.filter(pk=pk).first()) is not None}
    tracked.update({('content.document', pk): {**_state(row), 'portal_audience': document_portal_audience(row, lock=True)}
                    for pk in plan['baseline']['document_ids']
                    if (row := Document.objects.filter(pk=pk).first()) is not None})
    source = DocumentFolder.objects.get(pk=data['source_folder_id'])
    for rename in plan['renames']:
        capture_instance(source)
        source.name = rename['after']
        source.save(update_fields=['name', 'updated_at'])
    existing_folder_ids = set(DocumentFolder.objects.values_list('pk', flat=True))
    deleted = _delete_disposable_root(plan['disposable_root_id'], source, plan['disposable_template_ids'])
    adopt = data['strategy'] == 'adopt_source'
    created_project_id = None
    if 'create_project' in data['target']:
        project = _create_project(data['target']['create_project'], actor=actor, source=source if adopt else None)
        created_project_id = project.pk
    else:
        project = Project.objects.get(pk=data['target']['project_id'])
        if adopt:
            capture_instance(source)
            adopt_project_root(project, source)
    root = require_project_folder(project)
    ownership_input = {
        'folder_ids': [source.pk] if adopt else data.get('include_folder_ids', list(source.children.values_list('pk', flat=True))),
        'document_ids': [] if adopt else data.get('include_document_ids', list(source.documents.values_list('pk', flat=True))),
        'destination_folder_id': None if adopt else root.pk,
        'destination_owner': {'client_user_id': project.client_id, 'project_id': project.pk},
        'client_policy': data['client_policy'], 'portal_policy': data['portal_policy'], 'document_decisions': data['document_decisions'],
    }
    if ownership_input['folder_ids'] or ownership_input['document_ids']:
        current = plan_ownership(**ownership_input, lock=True)
        applied = apply_ownership_plan(ownership_input, actor=actor, expected_plan_hash=current['plan_hash'])
    else:
        applied = {'rows': []}
    archived, pending = [], []
    source.refresh_from_db()
    if plan['archive']['requested']:
        if source.children.exists() or source.documents.exists():
            pending = plan['archive']['pending']
        else:
            capture_instance(source)
            source.is_archived, source.archived_at, source.archived_via_folder_id = True, timezone.now(), None
            source.save(update_fields=['is_archived', 'archived_at', 'archived_via_folder', 'updated_at'])
            archived = [source.pk]
    _check_postconditions(plan, project, root, applied)
    created = sorted(set(DocumentFolder.objects.values_list('pk', flat=True)) - existing_folder_ids)
    items = [_item(row, before) for (model, pk), before in sorted(tracked.items())
             if (row := MODELS[model].objects.filter(pk=pk).first()) is not None]
    operation = DocumentOwnershipOperation.objects.create(
        kind=DocumentOwnershipOperation.Kind.ADOPTION if adopt else DocumentOwnershipOperation.Kind.MIGRATION,
        origin=origin or ('mcp' if credential else 'panel'), request_id=request_id,
        plan_hash=plan['plan_hash'], input=data, reason=reason, actor=actor, credential=credential,
        items=items, created_folder_ids=created, deleted_folder_snapshots=deleted, created_project_id=created_project_id,
    )
    report = {
        'migration_id': operation.pk, 'operation_id': operation.pk, 'strategy': data['strategy'],
        'project_id': project.pk, 'root_folder_id': root.pk, 'source_folder_id': source.pk,
        'plan_hash': plan['plan_hash'],
        'moved': [item for item in items if any(item['before'][key] != value for key, value in item['after'].items())],
        'archived_folder_ids': archived, 'pending': pending, 'pending_reason': 'La fuente conserva elementos.' if pending else None,
        'created_folder_ids': created, 'created_project_id': created_project_id,
        'deleted_folder_ids': [row['id'] for row in deleted], 'warnings': plan['warnings'],
        'baseline': {'folder_ids': sorted(set(plan['baseline']['folder_ids']) | set(created)),
                     'document_ids': plan['baseline']['document_ids']},
        'created_folder_states': {str(row.pk): _state(row) for row in DocumentFolder.objects.filter(pk__in=created)},
    }
    operation.report = report
    operation.save(update_fields=['report'])
    return report


def get_folder_migration(operation_id):
    operation = DocumentOwnershipOperation.objects.filter(pk=operation_id).first()
    if operation is None:
        raise NotFound('Migración no encontrada.')
    return operation.report


def _undo_project_blockers(operation, project, *, lock):
    blockers, automatic, _threads = _dependency_inventory(project, lock=lock)
    known = {model: {item['id'] for item in operation.items if item['model'] == model}
             for model in MODELS}
    tree = _subtree(_current(DocumentFolder.objects.filter(managed_project=project), lock).values_list('pk', flat=True), lock=lock)
    removable_docs = len(list(_current(Document.objects.filter(Q(project=project) | Q(folder_id__in=tree), pk__in=known['content.document']), lock).values_list('pk', flat=True)))
    removable_folders = len(list(_current(DocumentFolder.objects.filter(Q(project=project) | Q(managed_project=project) | Q(pk__in=tree)).exclude(pk__in=automatic).filter(
        pk__in=known['content.documentfolder'] | set(operation.created_folder_ids),
    ), lock).values_list('pk', flat=True)))
    subtraction = {'documents': removable_docs, 'document_folders': removable_folders}
    subtraction.update(project_creation_undo_allowances(operation, project, lock=lock))
    return [{**row, 'count': row['count'] - subtraction.get(row['key'], 0)} for row in blockers
            if row['count'] > subtraction.get(row['key'], 0)]


def preview_undo_migration(operation_id, *, lock=False):
    operation = DocumentOwnershipOperation.objects.filter(pk=operation_id).first()
    if operation is None:
        raise NotFound('Migración no encontrada.')
    blockers = []
    if operation.kind == DocumentOwnershipOperation.Kind.UNDO or DocumentOwnershipOperation.objects.filter(reverts=operation).exists():
        blockers.append(_block('already_reverted', 'Esta operación no admite otro deshacer.'))
    current, changed = [], []
    for item in operation.items:
        row = _current(MODELS[item['model']].objects.filter(pk=item['id']), lock).first()
        value = _state(row) if row else None
        current.append({'model': item['model'], 'id': item['id'], 'state': value})
        if value != item['after']:
            changed.append({'model': item['model'], 'id': item['id']})
        elif row is not None and isinstance(row, Document) and _undo_would_change_frozen_document(item, row, lock=lock):
            changed.append({'model': item['model'], 'id': item['id'], 'reason': 'ownership_frozen'})
        if isinstance(row, Document):
            audience_blocker = _undo_audience_blocker(item, row, lock=lock)
            if audience_blocker:
                blockers.append(audience_blocker)
    for pk in operation.created_folder_ids:
        row = _current(DocumentFolder.objects.filter(pk=pk), lock).first()
        value = _state(row) if row else None
        current.append({'model': 'content.documentfolder', 'id': pk, 'state': value})
        if value != operation.report['created_folder_states'].get(str(pk)):
            changed.append({'model': 'content.documentfolder', 'id': pk})
    if changed:
        blockers.append(_block('changed_since', 'Algunos registros cambiaron; deshacer sobrescribiría esos cambios.', records=changed))
    touches = {(item['model'], item['id']) for item in operation.items} | {('content.documentfolder', pk) for pk in operation.created_folder_ids}
    later_ids = []
    for later in DocumentOwnershipOperation.objects.filter(pk__gt=operation.pk, reverted_by__isnull=True).exclude(kind='undo').order_by('pk'):
        if touches & {(item['model'], item['id']) for item in later.items}:
            later_ids.append(later.pk)
    if later_ids:
        blockers.append(_block('changed_since', 'Deshaz primero las operaciones posteriores que tocaron estos registros.', reason='lifo', operation_ids=later_ids))
    baseline = operation.report['baseline']
    folder_ids = _subtree(baseline['folder_ids'], lock=lock)
    document_ids = set(_current(Document.objects.filter(folder_id__in=folder_ids).order_by('pk'), lock).values_list('pk', flat=True))
    new_folders = sorted(folder_ids - set(baseline['folder_ids']))
    new_documents = sorted(document_ids - set(baseline['document_ids']))
    if new_folders or new_documents:
        blockers.append(_block('new_content_since', 'Hay contenido nuevo dentro de las carpetas afectadas.', folder_ids=new_folders, document_ids=new_documents))
    for snapshot in operation.deleted_folder_snapshots:
        if DocumentFolder.objects.filter(pk=snapshot['id']).exists() or DocumentFolder.objects.filter(slug=snapshot['slug']).exists():
            blockers.append(_block('changed_since', 'La identidad de una carpeta eliminada volvió a usarse.', folder_id=snapshot['id']))
    if operation.created_project_id:
        project = _current(Project.objects.filter(pk=operation.created_project_id), lock).first()
        dependencies = _undo_project_blockers(operation, project, lock=lock) if project else [_block('changed_since', 'El proyecto creado ya no existe.')]
        if dependencies:
            blockers.append(_block('project_in_use', 'El proyecto creado adquirió información que impide eliminarlo.', dependencies=dependencies))
    impact = {
        'migration_id': operation.pk, 'can_apply': not blockers, 'can_undo': not blockers,
        'records': current, 'restore': operation.items, 'delete_folder_ids': operation.created_folder_ids,
        'restore_deleted_folders': operation.deleted_folder_snapshots,
        'delete_project_id': operation.created_project_id, 'blockers': blockers,
        'contents': {'folder_ids': sorted(folder_ids), 'document_ids': sorted(document_ids)},
    }
    impact['impact_hash'] = _hash(impact)
    return impact


def _undo_audience_blocker(item, document, *, lock=False):
    restored_audience = document_portal_audience(document, item['before'], lock=lock)
    original_audience = item['before'].get('portal_audience')
    if restored_audience is not None and restored_audience != original_audience:
        return _block(
            'undo_audience_changed', f'Deshacer daría acceso a un nuevo cliente al documento «{document.title}».',
            resource_type='document', resource_id=document.pk, document_id=document.pk,
            before_audience=original_audience, after_audience=restored_audience,
        )
    return None


def _undo_would_change_frozen_document(item, document, *, lock):
    pair = ('client_user_id', 'project_id')
    ownership_changed = any(item['before'][key] != item['after'][key] for key in pair)
    placement_changed = item['before']['folder_id'] != item['after']['folder_id']
    generated = document.is_generated_snapshot or is_contract_mirror(document)
    if placement_changed and generated:
        return True
    if not ownership_changed:
        return False
    issued_account = (document.document_type is not None and document.document_type.code == 'collection_account'
                      and document.commercial_status != Document.CommercialStatus.DRAFT)
    linked = any(_current(model.objects.filter(document_id=document.pk), lock).exists()
                 for model in (DeliveryDocumentLink, ProjectContract, ContractAmendment))
    return bool(generated or document.deliverable_id or document.retention_context_id or issued_account or linked)


def _restore_values(model, pk, state):
    row = model.objects.get(pk=pk)
    capture_instance(row)
    fields = DOCUMENT_FIELDS if model is Document else FOLDER_FIELDS
    model.objects.filter(pk=pk).update(**{key: value for key, value in state.items() if key in fields})


def _delete_created_folders(ids):
    pending = set(ids)
    while pending:
        leaves = [pk for pk in sorted(pending) if not DocumentFolder.objects.filter(parent_id=pk).exists()]
        if not leaves or Document.objects.filter(folder_id__in=leaves).exists():
            raise FolderMigrationError('Las carpetas creadas ya no están vacías.', code='undo_blocked')
        DocumentFolder.objects.filter(pk__in=leaves).delete()
        pending.difference_update(leaves)


@historical_write
@transaction.atomic
def undo_migration(operation_id, expected_impact_hash, reason, request_id, *, actor, credential=None):
    serializer = MigrationUndoSerializer(data={
        'migration_id': operation_id, 'expected_impact_hash': expected_impact_hash,
        'reason': reason, 'request_id': request_id,
    })
    serializer.is_valid(raise_exception=True)
    request_id, reason = serializer.validated_data['request_id'], serializer.validated_data['reason']
    replay = _replay(request_id, expected_impact_hash, actor, credential)
    if replay is not None:
        if replay.get('reverts') != operation_id:
            raise FolderMigrationError('Este request_id pertenece a otro deshacer.', code='request_id_conflict')
        return replay
    operation = DocumentOwnershipOperation.objects.filter(pk=operation_id).first()
    if operation is None:
        raise NotFound('Migración no encontrada.')
    impact = preview_undo_migration(operation_id)
    _lock_scope({'baseline': {'folder_ids': impact['contents']['folder_ids'], 'document_ids': impact['contents']['document_ids']},
                 'rows': [], 'project_actions': {'project_id': operation.report['project_id']}},
                restore_project_ids={item['before']['project_id'] for item in operation.items
                                     if item['before']['project_id'] is not None})
    operation = DocumentOwnershipOperation.objects.select_for_update().get(pk=operation_id)
    replay = _replay(request_id, expected_impact_hash, actor, credential, lock=True)
    if replay is not None:
        return replay
    impact = preview_undo_migration(operation_id, lock=True)
    if impact['impact_hash'] != expected_impact_hash:
        raise FolderMigrationError('El impacto cambió; vuelve a revisar deshacer.', code='stale_version')
    if impact['blockers']:
        raise FolderMigrationError('No se puede deshacer la migración.', code='undo_blocked', blockers=impact['blockers'])
    undo_items = []
    # Release the OneToOne marker before recreating any disposable former root.
    for item in operation.items:
        if item['model'] == 'content.documentfolder' and item['after']['managed_project_id'] != item['before']['managed_project_id']:
            _restore_values(DocumentFolder, item['id'], item['before'])
    for snapshot in operation.deleted_folder_snapshots:
        row = DocumentFolder(**snapshot)
        row.save(force_insert=True)
        DocumentFolder.objects.filter(pk=row.pk).update(created_at=snapshot['created_at'])
    for item in operation.items:
        model = MODELS[item['model']]
        if model is Document:
            blocker = _undo_audience_blocker(item, model.objects.get(pk=item['id']), lock=True)
            if blocker:
                raise FolderMigrationError('No se puede deshacer la migración.', code='undo_blocked', blockers=[blocker])
        _restore_values(model, item['id'], item['before'])
        undo_items.append({'model': item['model'], 'id': item['id'], 'before': item['after'], 'after': _state(model.objects.get(pk=item['id']))})
    _delete_created_folders(operation.created_folder_ids)
    if operation.created_project_id:
        clear_project_creation_extras(operation)
        delete_empty_project(operation.created_project_id, actor=actor)
    undo = DocumentOwnershipOperation.objects.create(
        kind='undo', origin='mcp' if credential else 'panel', request_id=request_id,
        plan_hash=expected_impact_hash, input={'migration_id': operation_id}, reason=reason,
        items=undo_items, reverts=operation, actor=actor, credential=credential,
    )
    report = {'operation_id': undo.pk, 'reverts': operation.pk, 'restored': len(undo_items),
              'deleted_folder_ids': operation.created_folder_ids, 'deleted_project_id': operation.created_project_id,
              'restored_folder_ids': [row['id'] for row in operation.deleted_folder_snapshots]}
    undo.report = report
    undo.save(update_fields=['report'])
    return report
