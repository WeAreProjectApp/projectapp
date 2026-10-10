"""Read-only ownership plans and their atomic, audited document-tree writer."""

import hashlib
import json
from collections import Counter, defaultdict
from types import SimpleNamespace

from accounts.models import (
    ContractAmendment,
    DeliveryDocumentLink,
    Project,
    ProjectContract,
    UserProfile,
)
from content.mcp.errors import normalize_error
from content.models import AccountingChangeLog, Document, DocumentFolder
from content.models.document_folder import DocumentFolderMutationLock
from content.serializers.strict_input import StrictInputMixin
from content.services import accounting_service
from content.services.contract_mirror_service import (
    is_contract_mirror,
    pinned_mirror_folder,
)
from content.services.diagnostic_privacy import register_mcp_domain_codes
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.services.document_write_service import movement_blockers
from content.services.entity_history import historical_write
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from rest_framework import serializers
from rest_framework.exceptions import APIException

CLIENT_POLICIES = ('inherit', 'keep', 'abort_on_conflict')
PORTAL_POLICIES = ('abort', 'allow', 'hide_new_exposure')
register_mcp_domain_codes(
    'ownership_conflict', 'ownership_conflict_keep', 'ownership_frozen',
    'portal_exposure', 'stale_move_plan', 'ownership_plan_blocked',
)


class OwnershipPlanError(APIException):
    status_code = 409
    default_code = 'ownership_plan_blocked'

    def __init__(self, message, *, code='ownership_plan_blocked', plan=None, **details):
        super().__init__(message, code=code)
        self.code = code
        self.plan = plan
        self.details = details
        # Preserve IDs and boolean values in structured domain details.
        self.detail = {'detail': message, 'code': code, **details}


class DocumentDecisionSerializer(StrictInputMixin, serializers.Serializer):
    document_id = serializers.IntegerField(min_value=1)
    action = serializers.ChoiceField(choices=('inherit', 'move'))
    destination_folder_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if attrs['action'] == 'move' and 'destination_folder_id' not in attrs:
            raise serializers.ValidationError({'destination_folder_id': 'Elige la carpeta destino.'})
        if attrs['action'] == 'inherit' and 'destination_folder_id' in attrs:
            raise serializers.ValidationError({'destination_folder_id': 'Sólo se usa con action=move.'})
        return attrs


class OwnershipPlanInputSerializer(StrictInputMixin, serializers.Serializer):
    document_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list, max_length=100)
    folder_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list, max_length=100)
    destination_folder_id = serializers.IntegerField(min_value=1, allow_null=True)
    client_policy = serializers.ChoiceField(choices=CLIENT_POLICIES)
    portal_policy = serializers.ChoiceField(choices=PORTAL_POLICIES, required=False, default='abort')
    document_decisions = DocumentDecisionSerializer(many=True, required=False, default=list, max_length=100)

    def validate(self, attrs):
        if not attrs['document_ids'] and not attrs['folder_ids']:
            raise serializers.ValidationError({'document_ids': 'Selecciona documentos o carpetas.'})
        for name in ('document_ids', 'folder_ids'):
            if len(attrs[name]) != len(set(attrs[name])):
                raise serializers.ValidationError({name: 'No repitas identificadores.'})
            attrs[name] = sorted(attrs[name])
        decisions = attrs['document_decisions']
        if len(decisions) != len({row['document_id'] for row in decisions}):
            raise serializers.ValidationError({'document_decisions': 'No repitas decisiones para un documento.'})
        attrs['document_decisions'] = sorted(decisions, key=lambda row: row['document_id'])
        return attrs


def portal_audience(document_state):
    """Return the authorized client user, without queries or mutable objects.

    Linked sources carry their resolved delivery audience. Their independent
    publication/signature rules are evaluated by the existing portal index,
    rather than inferred from the document's visibility checkbox.
    """
    if document_state.get('is_collection_account'):
        return None
    client = document_state.get('client_user_id')
    owner = document_state.get('project_client_user_id') if document_state.get('project_id') else client
    if owner is None or client not in (None, owner):
        return None
    if document_state.get('delivery_linked'):
        return owner if document_state.get('delivery_audience') == owner else None
    if document_state.get('is_archived') or not document_state.get('is_client_visible'):
        return None
    return owner


def _descendants(roots, topology):
    children = defaultdict(list)
    for pk, parent_id in topology.items():
        children[parent_id].append(pk)
    found, pending = set(), list(roots)
    while pending:
        pk = pending.pop()
        if pk in found or pk not in topology:
            continue
        found.add(pk)
        pending.extend(children[pk])
    return found


def _ancestors(ids, topology):
    result, pending = set(), list(ids)
    while pending:
        pk = pending.pop()
        if pk is None or pk in result or pk not in topology:
            continue
        result.add(pk)
        pending.append(topology[pk])
    return result


def _documents(query):
    return Document.objects.filter(query).select_related(
        'document_type', 'project', 'contract_template', 'contract_mirror',
    ).annotate(
        ownership_delivery_linked=Exists(DeliveryDocumentLink.objects.filter(document_id=OuterRef('pk'))),
        ownership_contract_linked=Exists(ProjectContract.objects.filter(document_id=OuterRef('pk'))),
        ownership_amendment_linked=Exists(ContractAmendment.objects.filter(document_id=OuterRef('pk'))),
    ).order_by('pk')


def _read_scope(data, *, lock):
    if lock:
        # The migration seeds the mutex. A preview never creates it.
        DocumentFolderMutationLock.objects.select_for_update().filter(pk=1).first()
    topology = dict(DocumentFolder.objects.values_list('pk', 'parent_id'))
    scope_ids = _descendants(data['folder_ids'], topology)
    query = Q(pk__in=data['document_ids']) | Q(folder_id__in=scope_ids)
    document_values = list(Document.objects.filter(query).values('pk', 'project_id', 'folder_id'))
    destinations = {data['destination_folder_id']} | {
        row['destination_folder_id'] for row in data['document_decisions'] if row['action'] == 'move'
    }
    pinned, _source = pinned_mirror_folder()
    involved_ids = _ancestors(
        scope_ids | (destinations - {None}) | {row['folder_id'] for row in document_values}
        | ({pinned.pk} if pinned else set()), topology,
    )
    # Siblings participate in name validation and therefore in staleness.
    if data['folder_ids']:
        involved_ids.update(pk for pk, parent in topology.items() if parent in destinations)
    folder_fields = ('pk', 'project_id', 'managed_project_id', 'parent_id')
    folder_values = list(DocumentFolder.objects.filter(pk__in=involved_ids).values(*folder_fields))
    project_ids = {row['project_id'] for row in document_values + folder_values} | {row['managed_project_id'] for row in folder_values}
    project_ids.discard(None)
    document_ids = {row['pk'] for row in document_values}
    if lock:
        # Do not join nullable relations in locking reads: lock only these
        # tables, in the same order on every write path.
        list(Project.objects.select_for_update().filter(pk__in=project_ids).order_by('pk'))
        list(DocumentFolder.objects.select_for_update().filter(pk__in=involved_ids).order_by('pk'))
        list(Document.objects.select_for_update().filter(pk__in=document_ids).order_by('pk'))
        # Placement or project changes during discovery can introduce rows
        # outside the ordered lock set. Retry with a fresh scope instead of
        # planning against an unlocked relation or skipping a new descendant.
        current_folders = list(DocumentFolder.objects.filter(pk__in=involved_ids).values(*folder_fields))
        current_documents = list(Document.objects.filter(query).values('pk', 'project_id', 'folder_id'))
        def indexed(values):
            return {row['pk']: row for row in values}
        if (indexed(current_folders) != indexed(folder_values)
                or indexed(current_documents) != indexed(document_values)
                or any(row['parent_id'] != topology.get(row['pk']) for row in current_folders)):
            raise OwnershipPlanError('El alcance cambió durante el movimiento. Vuelve a consultar preview_move.', code='stale_move_plan')
    projects = {obj.pk: obj for obj in Project.objects.filter(pk__in=project_ids)}
    folders = {obj.pk: obj for obj in DocumentFolder.objects.filter(pk__in=involved_ids).order_by('pk')}
    documents = {obj.pk: obj for obj in _documents(Q(pk__in=document_ids))}
    decisions = {row['document_id']: row for row in data['document_decisions']}
    if set(decisions) - (set(documents) | set(data['document_ids'])):
        raise serializers.ValidationError({'document_decisions': 'Las decisiones deben pertenecer a documentos del alcance.'})
    users = {obj.client_user_id for obj in list(folders.values()) + list(documents.values())} | {obj.client_id for obj in projects.values()}
    profiles = dict(UserProfile.objects.filter(user_id__in=users).values_list('user_id', 'pk'))
    pinned_ids = _descendants([pinned.pk], topology) if pinned else set()
    return scope_ids, folders, documents, projects, profiles, pinned_ids


def _linked(document):
    return document.ownership_delivery_linked or document.ownership_contract_linked or document.ownership_amendment_linked


def _delivery_audiences(documents):
    from accounts.document_views import _visible_docs_qs

    linked = [doc for doc in documents.values() if _linked(doc)]
    owners = {doc.project.client_id if doc.project_id else doc.client_user_id for doc in linked} - {None}
    result = {}
    for user in get_user_model().objects.filter(pk__in=owners):
        visible = _visible_docs_qs(SimpleNamespace(user=user)).filter(pk__in=[doc.pk for doc in linked])
        result.update({pk: user.pk for pk in visible.values_list('pk', flat=True)})
    return result


def _state(item, *, folders, projects, profiles, delivery_audience=None):
    document = isinstance(item, Document)
    project = projects.get(item.project_id)
    state = {
        'folder_or_parent_id': item.folder_id if document else item.parent_id,
        'client_profile_id': profiles.get(item.client_user_id),
        'client_user_id': item.client_user_id,
        'project_id': item.project_id,
        'project_client_user_id': project.client_id if project else None,
        'is_client_visible': item.is_client_visible if document else None,
        'is_archived': item.is_archived,
        'portal_audience': None,
    }
    if document:
        state.update(
            is_collection_account=getattr(item.document_type, 'code', None) == COLLECTION_ACCOUNT,
            delivery_linked=bool(_linked(item)), delivery_audience=delivery_audience,
        )
        state['portal_audience'] = portal_audience(state)
    return state


def _owner(state, destination, policy, projects):
    """Keep project/client pairs coherent without ever removing an owner."""
    current = (state['client_user_id'], state['project_id'])
    if destination is None:
        return current, None
    project_id = destination.project_id
    project_client = projects[project_id].client_id if project_id in projects else None
    target = (destination.client_user_id or project_client, project_id)
    if target == (None, None):
        return current, None
    client = current[0] or (state['project_client_user_id'] if current[1] else None)
    conflict = client is not None and (
        client != target[0] or current[1] is not None and current[1] != target[1]
    )
    if conflict and policy != 'inherit':
        return current, 'ownership_conflict_keep' if policy == 'keep' else 'ownership_conflict'
    if policy == 'keep':
        return current, None
    return target, None


def _blocker(code, message, row):
    return {'code': code, 'message': message, 'resource_type': row['resource_type'], 'resource_id': row['id']}


def _validation_blockers(serializer, row, *, default_code='validation_error'):
    if serializer.is_valid():
        return []
    message, code, _details = normalize_error(serializer.errors)
    return [_blocker(default_code if code == 'VALIDATION_ERROR' else code.lower(), message, row)]


def _plan_row(item, destination_id, *, direct, policy, portal_policy, folders, projects, profiles, pinned_ids, delivery_audience):
    from content.serializers.document import DocumentCreateUpdateSerializer
    from content.serializers.document_folder import DocumentFolderSerializer

    document = isinstance(item, Document)
    before = _state(item, folders=folders, projects=projects, profiles=profiles, delivery_audience=delivery_audience)
    after = dict(before)
    row = {'resource_type': 'document' if document else 'folder', 'id': item.pk,
           'status': 'unchanged', 'before': before, 'after': after, 'conflict': None, 'blockers': []}
    destination = folders.get(destination_id)
    pinned = is_contract_mirror(item) if document else item.pk in pinned_ids
    pinned = pinned or (document and item.folder_id in pinned_ids)
    frozen = bool(item.retention_context_id) or document and (
        item.is_generated_snapshot or item.deliverable_id or _linked(item)
        or before['is_collection_account'] and item.commercial_status != Document.CommercialStatus.DRAFT
    )
    proposed, conflict = _owner(before, destination, policy, projects)
    ownership_changed = proposed != (before['client_user_id'], before['project_id'])
    if pinned:
        row['status'] = 'pinned'
    elif frozen:
        row['status'] = 'frozen'
        if ownership_changed:
            row['blockers'].append(_blocker('ownership_frozen', 'La propiedad de este registro está congelada.', row))
        elif conflict:
            row['conflict'] = conflict
            row['blockers'].append(_blocker(conflict, 'El registro pertenece a otro cliente o proyecto.', row))
    else:
        row['conflict'] = conflict
        if conflict:
            row['blockers'].append(_blocker(conflict, 'El registro pertenece a otro cliente o proyecto.', row))
        after['client_user_id'], after['project_id'] = proposed
        after['client_profile_id'] = profiles.get(proposed[0])
        project = projects.get(proposed[1])
        after['project_client_user_id'] = project.client_id if project else None
    if direct:
        after['folder_or_parent_id'] = destination_id
        if destination_id is not None and destination is None:
            row['blockers'].append(_blocker('folder_not_found', 'La carpeta destino no existe.', row))
        elif document:
            for code in movement_blockers(item):
                row['blockers'].append(_blocker(code, 'El documento no admite este movimiento.', row))
            if destination_id is None:
                row['blockers'].append(_blocker('folder_required', 'Elige una carpeta destino para el documento.', row))
            if not row['blockers']:
                # Explicit ownership suppresses the legacy inheritance here;
                # it is only validation, never a serializer save.
                payload = {'folder_id': destination_id, 'client': after['client_profile_id'], 'project': after['project_id']}
                default_code = 'folder_archived' if destination and destination.is_archived else 'folder_not_movable' if destination and destination.is_system_managed else 'validation_error'
                row['blockers'].extend(_validation_blockers(DocumentCreateUpdateSerializer(item, data=payload, partial=True), row, default_code=default_code))
        elif item.parent_id != destination_id:
            default_code = 'folder_archived' if destination and destination.is_archived else 'folder_not_movable' if destination and destination.is_system_managed else 'validation_error'
            row['blockers'].extend(_validation_blockers(DocumentFolderSerializer(item, data={'parent': destination_id}, partial=True), row, default_code=default_code))
        if item.retention_context_id and after['folder_or_parent_id'] != before['folder_or_parent_id']:
            row['blockers'].append(_blocker('ownership_frozen', 'Los registros conservados sólo permiten consulta.', row))
            after['folder_or_parent_id'] = before['folder_or_parent_id']
    if not document and ownership_changed and not pinned and not frozen and not conflict:
        payload = {'client': after['client_profile_id'], 'project': after['project_id']}
        row['blockers'].extend(_validation_blockers(DocumentFolderSerializer(item, data=payload, partial=True), row))
    if document:
        if (after['client_user_id'], after['project_id']) != (before['client_user_id'], before['project_id']):
            from accounts.services.billing_reassignment import (
                validate_document_reassignment,
            )
            try:
                validate_document_reassignment(item, changes={
                    'client_user_id': after['client_user_id'], 'project_id': after['project_id'],
                })
            except serializers.ValidationError as exc:
                message, code, _details = normalize_error(exc.detail)
                row['blockers'].append(_blocker(code.lower(), message, row))
        after['portal_audience'] = portal_audience(after)
        exposure = after['portal_audience'] is not None and after['portal_audience'] != before['portal_audience']
        restored_before = portal_audience({**before, 'is_archived': False})
        restored_after = portal_audience({**after, 'is_archived': False})
        latent = before['is_archived'] and restored_after is not None and restored_after != restored_before
        row['latent_exposure'] = bool(latent)
        if exposure and portal_policy == 'abort':
            row['blockers'].append(_blocker('portal_exposure', 'El movimiento daría acceso a un nuevo cliente en el portal.', row))
        if (exposure or latent) and portal_policy == 'hide_new_exposure':
            after['is_client_visible'] = False
            after['portal_audience'] = portal_audience(after)
    if row['blockers']:
        row['status'] = 'blocked'
    elif row['status'] == 'unchanged' and before != after:
        row['status'] = 'changed'
    return row


def _fingerprint(folders, documents, projects, pinned_ids):
    return {
        'folders': [{name: getattr(obj, name) for name in (
            'pk', 'name', 'parent_id', 'client_user_id', 'project_id', 'managed_project_id',
            'managed_client_id', 'system_key', 'is_archived', 'retention_context_id',
        )} for obj in folders.values()],
        'documents': [{name: getattr(obj, name) for name in (
            'pk', 'folder_id', 'client_user_id', 'project_id', 'is_client_visible',
            'is_archived', 'retention_context_id', 'document_type_id', 'commercial_status', 'deliverable_id',
        )} | {'generated_file': str(obj.generated_file), 'contract_mirror': is_contract_mirror(obj), 'delivery_linked': bool(_linked(obj))}
            for obj in documents.values()],
        'projects': [{'id': obj.pk, 'client_user_id': obj.client_id} for obj in sorted(projects.values(), key=lambda obj: obj.pk)],
        'pinned_folder_ids': sorted(pinned_ids),
    }


def plan_ownership(*, document_ids=(), folder_ids=(), destination_folder_id, client_policy, portal_policy='abort', document_decisions=(), lock=False):
    """Plan an entire subtree and explicit document exceptions without writes."""
    serializer = OwnershipPlanInputSerializer(data={
        'document_ids': list(document_ids), 'folder_ids': list(folder_ids),
        'destination_folder_id': destination_folder_id, 'client_policy': client_policy,
        'portal_policy': portal_policy, 'document_decisions': list(document_decisions),
    })
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    scope_ids, folders, documents, projects, profiles, pinned_ids = _read_scope(data, lock=lock)
    decisions = {row['document_id']: row for row in data['document_decisions']}
    audiences = _delivery_audiences(documents)
    # Selecting both a parent and its child moves the parent once; the child
    # remains attached to it while taking part in the same ownership policy.
    selected = set(data['folder_ids'])
    topology = {key: obj.parent_id for key, obj in folders.items()}
    roots = {pk for pk in selected & scope_ids if not (_ancestors([folders[pk].parent_id], topology) & selected)}
    rows = []
    for kind, ids, objects in (('folder', scope_ids | selected, folders), ('document', set(documents) | set(data['document_ids']), documents)):
        for pk in sorted(ids):
            item = objects.get(pk)
            if item is None:
                row = {'resource_type': kind, 'id': pk, 'status': 'blocked', 'before': {}, 'after': {}, 'conflict': None, 'blockers': []}
                row['blockers'] = [_blocker('not_found', 'El registro no existe.', row)]
            else:
                decision = decisions.get(pk, {}) if kind == 'document' else {}
                destination_id = decision.get('destination_folder_id', data['destination_folder_id'])
                row = _plan_row(
                    item, destination_id, direct=pk in roots if kind == 'folder' else pk in data['document_ids'] or decision.get('action') == 'move',
                    policy='inherit' if decision.get('action') == 'inherit' else data['client_policy'],
                    portal_policy=data['portal_policy'], folders=folders, projects=projects, profiles=profiles,
                    pinned_ids=pinned_ids, delivery_audience=audiences.get(pk),
                )
            rows.append(row)
    # The serializer's name validator also compares siblings that this plan
    # would bring together, which do not share a parent in the database yet.
    from content.serializers.document_folder import validate_folder_name
    for row in rows:
        if (row['resource_type'] != 'folder' or row['id'] not in roots
                or row['before']['folder_or_parent_id'] == row['after']['folder_or_parent_id']):
            continue
        try:
            validate_folder_name(folders[row['id']].name, folders.get(destination_folder_id), folders[row['id']], planned_siblings=[folders[pk] for pk in sorted(roots)])
        except serializers.ValidationError as exc:
            message, code, _details = normalize_error(exc.detail)
            blocker = _blocker(code.lower(), message, row)
            if blocker not in row['blockers']:
                row['blockers'].append(blocker)
                row['status'] = 'blocked'
    blockers = [blocker for row in rows for blocker in row['blockers']]
    warnings = [_blocker('latent_exposure', 'El documento ganaría audiencia si se restaurara.', row) for row in rows if row.get('latent_exposure')]
    fingerprint = _fingerprint(folders, documents, projects, pinned_ids)
    canonical = json.dumps({'input': data, 'rows': rows, 'fingerprint': fingerprint}, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    destination = folders.get(destination_folder_id)
    return {
        'destination_owner': {'client_profile_id': profiles.get(destination.client_user_id or getattr(projects.get(destination.project_id), 'client_id', None)) if destination else None,
                              'project_id': destination.project_id if destination else None},
        'rows': rows, 'totals': {**dict(Counter(row['status'] for row in rows)), 'folders': sum(row['resource_type'] == 'folder' for row in rows), 'documents': sum(row['resource_type'] == 'document' for row in rows)},
        'can_apply': not blockers, 'blockers': blockers, 'warnings': warnings,
        'plan_hash': hashlib.sha256(canonical.encode()).hexdigest(),
    }


def _audit(item, row, actor, old_values):
    entity_type = AccountingChangeLog.EntityType.DOCUMENT if isinstance(item, Document) else AccountingChangeLog.EntityType.DOCUMENT_FOLDER
    accounting_service.log_entity_diff(entity_type, item, old_values, actor)
    # The accounting catalog predates folder reparenting and portal policies.
    # Record these fields too, without mutating that shared catalog.
    extra = ('is_client_visible',) if isinstance(item, Document) else ('folder_or_parent_id',)
    changes = [{'field': 'parent' if key == 'folder_or_parent_id' else key,
                'label': 'Carpeta superior' if key == 'folder_or_parent_id' else 'Visible en el portal',
                'old': row['before'][key], 'new': row['after'][key]}
               for key in extra if row['before'][key] != row['after'][key]]
    if changes:
        accounting_service.log_accounting_change(entity_type=entity_type, object_id=item.pk,
            object_repr=accounting_service.object_repr(entity_type, item), action=AccountingChangeLog.Action.UPDATED,
            changes=changes, actor=actor)


@historical_write
@transaction.atomic
def apply_ownership_plan(plan_input, *, actor, expected_plan_hash=None):
    """Re-plan under ordered row locks, then write every changed row or none."""
    from accounts.services.billing_reassignment import validate_document_reassignment

    plan = plan_ownership(**plan_input, lock=True)
    if expected_plan_hash is not None and expected_plan_hash != plan['plan_hash']:
        raise OwnershipPlanError('La vista previa cambió. Vuelve a consultar preview_move.', code='stale_move_plan', plan=plan, plan_hash=plan['plan_hash'])
    if not plan['can_apply']:
        raise OwnershipPlanError('No se aplicó ningún movimiento: el plan contiene bloqueos.', plan=plan, blockers=plan['blockers'])
    for row in plan['rows']:
        if row['before'] == row['after']:
            continue
        model = Document if row['resource_type'] == 'document' else DocumentFolder
        item = model.objects.get(pk=row['id'])
        entity_type = AccountingChangeLog.EntityType.DOCUMENT if model is Document else AccountingChangeLog.EntityType.DOCUMENT_FOLDER
        old_values = accounting_service.snapshot_values(item, entity_type)
        after = row['after']
        changes = {'client_user_id': after['client_user_id'], 'project_id': after['project_id'],
                   'folder_id' if model is Document else 'parent_id': after['folder_or_parent_id']}
        if model is Document:
            validate_document_reassignment(item, changes=changes, lock=True)
            changes.update(is_client_visible=after['is_client_visible'], updated_by=actor)
        for field, value in changes.items():
            setattr(item, field, value)
        item.save(update_fields=[*changes, 'updated_at'])
        _audit(item, row, actor, old_values)
    return plan
