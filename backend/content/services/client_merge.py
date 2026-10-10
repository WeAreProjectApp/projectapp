"""Preview-first, reversible client merges inside the integrity history operation.

No deletion, access revocation, historical snapshot rewrite or new containers.
The relation inventory fails closed when a model acquires an unreviewed FK.
"""
from collections import Counter

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException

from accounts.models import Project, UserProfile
from accounts.services.billing_reassignment import (
    validate_financial_reassignment, validate_project_billing_reassignment,
)
from accounts.services.client_archive_service import ClientArchiveError, archive_client, suspended_state
from accounts.services.delivery_client_transfer import assert_delivery_client_transfer_safe
from accounts.services.issue_client_transfer import assert_issue_client_transfer_safe
from accounts.services.proposal_client_service import (
    build_client_display_name, sync_diagnostic_snapshot, sync_snapshot,
)
from content.models import (
    AccountingChangeLog, BusinessProposal, ClientDocumentNumberSequence, CommunicationThread,
    Document, DocumentCollectionAccount, DocumentFolder, McpActionIntent, WebAppDiagnostic,
)
from content.services import accounting_service, document_folder_merge, project_service
from content.services.client_merge_policy import (
    BLOCK, COLLISION, NEVER, RELATION_POLICIES, RELINK, SPECIAL, discover_relations, policy_drift,
)
from content.services.document_folder_repair import fingerprint
from content.services.entity_history import capture_instance, current_history_operation_id
from content.services.entity_history_registry import roots_for
from content.services.data_integrity.snapshots import json_value

MAX_ITEMS = 1000
MAX_AGGREGATES = 300
SAMPLE_SIZE = 20
USER_FIELDS = ('first_name', 'last_name')
PROFILE_FIELDS = ('company_name', 'phone', 'address', 'cedula', 'nit',
                  'date_of_birth', 'gender', 'education_level')
DIGIT_FIELDS = frozenset(('phone', 'nit', 'cedula'))
ERRORS = (APIException, DjangoValidationError, ValueError)
NUMBER_SEQUENCE = 'content.ClientDocumentNumberSequence.client_profile'
IMMUTABLE_REFERENCES = (
    'AccountingChangeLog', 'EmailLogTarget', 'EntityHistory', 'EntityRevision', 'McpRequestLog.object_refs',
    'ProjectRetentionOperation.items', 'approval/formalization/contract snapshots', 'IssueContext.snapshot',
    'BillingContextEvent', 'FinancingAgreementEvent',
)


class ClientMergeError(ValueError):
    """Refusal after locks; the entire caller transaction must roll back."""


def _profile(value):
    return UserProfile._base_manager.select_related('user').get(pk=getattr(value, 'pk', value))


def is_placeholder(email):
    return (email or '').strip().casefold().endswith(UserProfile.PLACEHOLDER_EMAIL_DOMAIN)


def has_platform_access(profile):
    return bool(profile.user.is_active and (profile.user.has_usable_password() or profile.is_onboarded))


def _normalized(field, value):
    text = str(value or '').strip().casefold()
    if field in DIGIT_FIELDS:
        return ''.join(char for char in text if char.isdigit())
    if field == 'email' and is_placeholder(text):
        return ''
    return text


def _card(profile):
    return {'id': profile.pk, 'user_id': profile.user_id, 'display_name': build_client_display_name(profile),
            'email': profile.user.email, 'is_placeholder': is_placeholder(profile.user.email),
            'has_platform_access': has_platform_access(profile), 'billing_code': profile.billing_code}


def _block(code, message, **detail):
    return {'code': code, 'message': message, **detail}


def _permission_present(value):
    if isinstance(value, dict):
        return any(_permission_present(item) for item in value.values())
    if isinstance(value, list):
        return any(_permission_present(item) for item in value)
    return value is True


def grant_blockers(user_id, project_ids):
    from accounts.models_project_client_access import ProjectClientAccessPolicy
    policies = ProjectClientAccessPolicy._base_manager.filter(
        Q(recipient_id=user_id) | Q(project_id__in=project_ids),
    ).order_by('pk')
    ids = [row.pk for row in policies if row.recipient_id is not None or _permission_present(row.permissions)]
    return ([_block('client_access_grants', 'Hay permisos de acceso a proyectos. Su revocación no se puede '
                    'deshacer; revísalos antes de fusionar.', sample_ids=ids[:SAMPLE_SIZE], count=len(ids))]
            if ids else [])


def transfer_blockers(projects, target_user, *, actor=None):
    found = []
    for project in projects:
        try:
            validate_project_billing_reassignment(project, target_user)
            assert_delivery_client_transfer_safe(project, target_user, actor=actor)
            assert_issue_client_transfer_safe(project, target_user)
        except ERRORS as error:
            found.append(_block('project_transfer_frozen', 'Un proyecto conserva entregas, tickets o historia '
                                'financiera que impide trasladarlo.', project_id=project.pk, reason=str(error)))
    return found


def association_blockers(target_profile_id, link_ids):
    """Never combine or delete colliding secure-link idempotency receipts."""
    from secure_links.models import SecureLink
    collisions = []
    for link in SecureLink._base_manager.filter(pk__in=link_ids, creation_request_id__isnull=False):
        if SecureLink._base_manager.filter(owner_id=target_profile_id,
                                           creation_request_id=link.creation_request_id).exclude(pk=link.pk).exists():
            collisions.append(link.pk)
    return ([_block('association_collision', 'Hay enlaces seguros con la misma clave de creación. '
                    'No se pueden reunir sin perder uno de sus recibos.', count=len(collisions),
                    sample_ids=collisions[:SAMPLE_SIZE])] if collisions else [])


def _identity(survivor, duplicate, resolutions):
    fills, conflicts, user_values, profile_values, blockers = [], [], {}, {}, []
    allowed = set(USER_FIELDS + PROFILE_FIELDS + ('email',))
    if (not isinstance(resolutions, dict) or set(resolutions) - allowed
            or any(value not in ('survivor', 'duplicate') for value in resolutions.values())):
        blockers.append(_block('invalid_input', 'Las decisiones deben elegir «survivor» o «duplicate» '
                               'para cada dato en conflicto.'))
        resolutions = {}
    for field in USER_FIELDS + PROFILE_FIELDS + ('email',):
        user_field = field in USER_FIELDS or field == 'email'
        left, right = (survivor.user, duplicate.user) if user_field else (survivor, duplicate)
        if not hasattr(left, field):
            continue
        old, incoming = getattr(left, field), getattr(right, field)
        left_key, right_key = _normalized(field, old), _normalized(field, incoming)
        value = old
        if not left_key and right_key:
            value = incoming
            fills.append({'field': field, 'before': json_value(old), 'after': json_value(incoming)})
        elif left_key and right_key and left_key != right_key:
            resolution = resolutions.get(field)
            conflicts.append({'field': field, 'survivor': json_value(old), 'duplicate': json_value(incoming),
                              'resolution': resolution})
            if resolution is None:
                blockers.append(_block('identity_conflict', 'Elige qué valor conservar para este dato.', field=field))
            elif resolution == 'duplicate':
                value = incoming
        if value != old:
            (user_values if user_field else profile_values)[field] = value
    email = user_values.get('email', survivor.user.email)
    username = survivor.user.username
    if 'email' in user_values and _normalized('email', email):
        email = email.strip().lower()
        # update_client_profile uses this same truncation for auth.User's limit.
        username = email[:get_user_model()._meta.get_field('username').max_length]
        user_values.update(email=email, username=username)
    retired = {'email': f'merged_{duplicate.pk}@temp.example.com', 'username': f'merged_{duplicate.pk}',
               'is_active': False}
    users = get_user_model()._base_manager.exclude(pk__in=[survivor.user_id, duplicate.user_id])
    for label, candidate_email, candidate_username in (
            ('survivor', email, username), ('duplicate', retired['email'], retired['username'])):
        query = Q(username__iexact=candidate_username) | Q(email__iexact=candidate_username)
        if candidate_email:
            query |= Q(email__iexact=candidate_email) | Q(username__iexact=candidate_email)
        if users.filter(query).exists():
            blockers.append(_block('identity_collision', 'Otro usuario ya tiene el correo o el nombre de acceso '
                                   'que usaría la fusión.', identity=label))
    if (retired['username'].casefold() == username.casefold()
            or retired['email'].casefold() == email.casefold()):
        blockers.append(_block('identity_collision', 'La identidad retirada coincide con la que se conserva.'))
    sequences = {row.client_profile_id: row.pk for row in ClientDocumentNumberSequence._base_manager.filter(
        client_profile_id__in=[survivor.pk, duplicate.pk],
    )}
    transfer = not survivor.billing_code and bool(duplicate.billing_code)
    if ((survivor.pk in sequences and not survivor.billing_code)
            or (duplicate.pk in sequences and not duplicate.billing_code)
            or (transfer and survivor.pk in sequences)):
        blockers.append(_block('billing_sequence_conflict', 'El código de facturación y su secuencia no se '
                               'pueden trasladar sin mezclar numeraciones.'))
    billing = {'action': 'transfer' if transfer else 'keep_reserved',
               'survivor_code': duplicate.billing_code if transfer else survivor.billing_code,
               'duplicate_code': None if transfer else duplicate.billing_code,
               'sequence_id': sequences.get(duplicate.pk) if transfer else None}
    return ({'fills': fills, 'conflicts': conflicts, 'email': email, 'username': username,
             'retired': retired, 'billing': billing}, user_values, profile_values, blockers)


def _container_plan(survivor, duplicate):
    containers, folder_plan, blockers = {}, None, []
    for name, model, left_id, right_id in (
            ('communications', CommunicationThread, survivor.pk, duplicate.pk),
            ('documents', DocumentFolder, survivor.user_id, duplicate.user_id)):
        left = model._base_manager.filter(managed_client_id=left_id).first()
        right = model._base_manager.filter(managed_client_id=right_id).first()
        action = 'none' if right is None else ('transfer' if left is None else
                                              ('demote' if name == 'communications' else 'merge'))
        containers[name] = {'action': action, 'survivor_root': left.pk if left else None,
                            'duplicate_root': right.pk if right else None}
        if name == 'documents' and action == 'merge':
            folder_plan = document_folder_merge.plan_folder_merge(
                left, right, client_merge=(survivor.user_id, duplicate.user_id),
            )
            containers[name]['merge'] = {'totals': folder_plan['totals'], 'blockers': folder_plan['blockers']}
            if folder_plan['blockers']:
                blockers.append(_block('document_root_merge_blocked', 'Las raíces documentales no se pueden '
                                       'fusionar todavía.', blockers=folder_plan['blockers']))
    return containers, folder_plan, blockers


def _add_rows(rows, queryset):
    for row in queryset:
        rows[(row._meta.label_lower, row.pk)] = row


@transaction.atomic
def plan_client_merge(survivor, duplicate, *, resolutions=None, actor=None):
    """Compute the public summary and private writer manifest without writes."""
    return _plan_client_merge(survivor, duplicate, resolutions=resolutions, actor=actor,
                              relation_inventory=discover_relations())


def _plan_client_merge(survivor, duplicate, *, resolutions, actor, relation_inventory):
    survivor, duplicate = _profile(survivor), _profile(duplicate)
    blockers = []
    if survivor.pk == duplicate.pk:
        blockers.append(_block('same_client', 'El cliente que se conserva y el duplicado deben ser distintos.'))
    if (survivor.role != UserProfile.ROLE_CLIENT or duplicate.role != UserProfile.ROLE_CLIENT
            or survivor.user.is_staff or survivor.user.is_superuser
            or duplicate.user.is_staff or duplicate.user.is_superuser):
        blockers.append(_block('staff_or_admin', 'No se fusionan cuentas administrativas.'))
    if survivor.archived_at is not None:
        blockers.append(_block('survivor_archived', 'El cliente que se conserva está archivado.'))
    if has_platform_access(duplicate):
        blockers.append(_block('duplicate_has_platform_access', 'El duplicado tiene acceso a la plataforma. '
                               'Considera conservar ese cliente e invertir la fusión.'))
    if actor is not None and not document_folder_merge.is_active_superuser(actor):
        blockers.append(_block('actor_not_superuser', 'Una fusión sólo la aplica un superusuario activo.'))
    drift = policy_drift(relation_inventory)
    if drift['missing'] or drift['stale']:
        blockers.append(_block('relation_policy_missing', 'Hay relaciones sin una política de fusión revisada.', **drift))
    identity, user_values, profile_values, identity_blocks = _identity(
        survivor, duplicate, {} if resolutions is None else resolutions,
    )
    blockers += identity_blocks
    projects = list(Project._base_manager.filter(client_id=duplicate.user_id).order_by('pk'))
    project_ids = [row.pk for row in projects]
    # The merge has the repair's active-superuser boundary. Reuse the transfer
    # guards for their history checks, without adding Platform-role authority.
    blockers += transfer_blockers(projects, survivor.user)
    blockers += grant_blockers(duplicate.user_id, project_ids)
    containers, folder_plan, container_blocks = _container_plan(survivor, duplicate)
    blockers += container_blocks
    rows = {(row._meta.label_lower, row.pk): row for row in (survivor, duplicate, survivor.user, duplicate.user)}
    relations, manifests, never = [], {}, {}
    for key, relation in sorted(relation_inventory.items()):
        policy = RELATION_POLICIES.get(key)
        linked = list(relation.rows_for(duplicate).order_by('pk'))
        ids = [row.pk for row in linked]
        relations.append({'relation': key, 'policy': policy, 'count': len(ids), 'sample_ids': ids[:SAMPLE_SIZE]})
        if policy == NEVER or key == 'accounts.UserProfile.user':
            never[key] = len(ids)
        elif policy == BLOCK and ids:
            code = ('retained_context' if key == 'content.ProjectRetentionContext.client' else
                    'client_access_grants' if key == 'accounts.ProjectClientAccessPolicy.recipient' else
                    'duplicate_has_privileges')
            blockers.append(_block(code, 'El duplicado tiene datos o responsabilidades que impiden fusionarlo.',
                                   relation=key, count=len(ids), sample_ids=ids[:SAMPLE_SIZE]))
        elif policy in (RELINK, COLLISION, SPECIAL):
            if key == NUMBER_SEQUENCE and identity['billing']['action'] != 'transfer':
                never[key] = len(ids)
                continue  # D keeps its reserved code and counter; no FK is rewritten.
            manifests[key] = ids
            _add_rows(rows, linked)
            if any(getattr(row, 'retention_context_id', None) for row in linked):
                blockers.append(_block('retained_context', 'Hay registros conservados de un proyecto eliminado; '
                                       'son de sólo lectura.', relation=key))
            if key in ('content.IncomeRecord.client', 'content.HostingRecord.client'):
                for record in linked:
                    try:
                        validate_financial_reassignment(record, {'client': survivor})
                    except ERRORS as error:
                        blockers.append(_block('financial_reassignment_invalid', 'Un registro financiero no '
                                               'admite el cambio de cliente.', relation=key,
                                               record_id=record.pk, reason=str(error)))
    for field in ('groups', 'user_permissions'):
        ids = list(getattr(duplicate.user, field).order_by('pk').values_list('pk', flat=True))
        relations.append({'relation': f'auth.User.{field}', 'policy': BLOCK, 'count': len(ids),
                          'sample_ids': ids[:SAMPLE_SIZE]})
        if ids:
            blockers.append(_block('duplicate_has_privileges', 'El duplicado tiene grupos o permisos de Django.',
                                   relation=f'auth.User.{field}'))
    blockers += association_blockers(survivor.pk, manifests.get('secure_links.SecureLink.owner', []))
    pending = [str(row.pk) for row in McpActionIntent.objects.filter(
        status=McpActionIntent.STATUS_PENDING, expires_at__gt=timezone.now())
               .order_by('pk').only('pk', 'arguments')
               if str(row.arguments.get('client_id', '')) == str(duplicate.pk)]
    if pending:
        blockers.append(_block('pending_mcp_actions', 'Hay acciones pendientes de confirmación para el '
                               'duplicado. Resuélvelas primero.', count=len(pending), sample_ids=pending[:SAMPLE_SIZE]))
    # Identity-save signals refresh S's existing proposal/diagnostic snapshots too.
    for model in (BusinessProposal, WebAppDiagnostic):
        _add_rows(rows, model._base_manager.filter(client_id__in=[survivor.pk, duplicate.pk]).order_by('pk'))
    _add_rows(rows, DocumentCollectionAccount._base_manager.filter(
        document_id__in=manifests.get('content.Document.client_user', []),
        document__document_type__code='collection_account', document__commercial_status='draft',
    ))
    # Project.save synchronizes its adopted roots and project-associated descendants.
    roots = list(DocumentFolder._base_manager.filter(managed_project_id__in=project_ids))
    folder_ids = {row.pk for row in roots}
    for root in roots:
        folder_ids |= root.get_descendant_ids()
    _add_rows(rows, DocumentFolder._base_manager.filter(pk__in=folder_ids))
    _add_rows(rows, CommunicationThread._base_manager.filter(managed_project_id__in=project_ids))
    if folder_plan:
        for label, pk in folder_plan['closure']:
            row = apps.get_model(label)._base_manager.get(pk=pk)
            rows[(label, pk)] = row
    if any(getattr(row, 'retention_context_id', None) for row in rows.values()):
        blockers.append(_block('retained_context', 'El traslado afectaría registros conservados de sólo lectura.'))
    if duplicate.archived_at is None:
        try:
            suspended_state()  # archive_client resolves this even with zero projects.
        except ClientArchiveError:
            blockers.append(_block('client_archive_unavailable', 'Falta el estado Suspendido que requiere el '
                                   'servicio de archivo de clientes.'))
    aggregates = {key for row in rows.values() for key in roots_for(row)}
    totals = {'items': len(rows), 'tracked_aggregates': len(aggregates),
              'relinked_relations': sum(len(ids) for ids in manifests.values()), 'projects': len(projects)}
    if len(rows) > MAX_ITEMS or len(aggregates) > MAX_AGGREGATES:
        blockers.append(_block('merge_too_large', 'La fusión supera el máximo de 1.000 registros o '
                               '300 entidades con historial.', totals=totals))
    payload = {'survivor': _card(survivor), 'duplicate': _card(duplicate), 'identity': identity,
               'relations': relations, 'never_rewritten': never, 'containers': containers,
               'snapshot_counts': dict(sorted(Counter(label for label, _ in rows).items())),
               'warnings': [
                   _block('new_rows_stay_with_survivor', 'Lo creado para el cliente que se conserva después de '
                          'la fusión seguirá con él al deshacer.'),
                   _block('history_is_preserved', 'Los recibos y el historial de la fusión se conservan al deshacer.'),
                   _block('immutable_references', 'La evidencia, las referencias de historial y las copias '
                          'legales conservan al cliente original.', references=list(IMMUTABLE_REFERENCES)),
               ], 'swap_suggestion': ({'survivor': duplicate.pk, 'duplicate': survivor.pk}
                                     if has_platform_access(duplicate) and not has_platform_access(survivor) else None),
               'blockers': blockers, 'totals': totals}
    closure = sorted(rows)
    # Whole-row hashes bind service callers as well as engine previews, without
    # leaking passwords, ciphertext or document bodies into the public summary.
    by_model = {}
    for label, pk in closure:
        by_model.setdefault(label, []).append(pk)
    expected = {}
    for label, pks in by_model.items():
        for row in apps.get_model(label)._base_manager.filter(pk__in=pks).values():
            expected[f'{label}:{row[apps.get_model(label)._meta.pk.attname]}'] = fingerprint(row)
    guards = {'survivor': survivor.pk, 'duplicate': duplicate.pk, 'survivor_user': survivor.user_id,
              'duplicate_user': duplicate.user_id, 'projects': project_ids, 'containers': containers,
              'identities': {str(row.pk): {'email': row.email, 'username': row.username}
                             for row in (survivor.user, duplicate.user)},
              'billing_codes': {str(row.pk): row.billing_code for row in (survivor, duplicate)},
              'billing': identity['billing'], 'duplicate_password': fingerprint(duplicate.user.password),
              'duplicate_onboarded': duplicate.is_onboarded,
              'state_hash': fingerprint(expected)}
    result = {'preview': payload, 'closure': closure, 'relations': manifests, 'user_values': user_values,
              'profile_values': profile_values, 'guards': guards, 'expected': expected}
    result['fingerprint'] = fingerprint(result)
    return result


def _update(model, pk, **values):
    """A single constraint-safe UPDATE, with aggregate history captured first."""
    row = model._base_manager.get(pk=pk)
    capture_instance(row)
    if any(field.attname == 'updated_at' for field in model._meta.concrete_fields):
        values['updated_at'] = timezone.now()
    model._base_manager.filter(pk=pk).update(**values)


def _relink(plan, relation, target_id):
    for pk in plan['relations'].get(relation.key, []):
        _update(relation.model, pk, **{relation.field.attname: target_id})


@transaction.atomic
def apply_client_merge(plan, *, actor):
    """P1-P11 in the caller's history operation; any refusal rolls everything back."""
    if not document_folder_merge.is_active_superuser(actor):
        raise ClientMergeError('Una fusión sólo la aplica un superusuario activo.')
    if plan['preview']['blockers']:
        raise ClientMergeError('La fusión tiene bloqueos; revisa la vista previa.')
    if current_history_operation_id() is None:
        raise ClientMergeError('La fusión requiere la operación de historial del motor.')
    document_folder_merge.lock_folder_tree()
    # Engine callers already hold the closure locks; reuse the same row order.
    from content.services.data_integrity.engine import lock_rows
    lock_rows(plan['closure'])
    survivor, duplicate = _profile(plan['guards']['survivor']), _profile(plan['guards']['duplicate'])
    resolutions = {row['field']: row['resolution'] for row in plan['preview']['identity']['conflicts']}
    relation_inventory = discover_relations()
    current = _plan_client_merge(survivor, duplicate, resolutions=resolutions, actor=actor,
                                 relation_inventory=relation_inventory)
    if current['preview']['blockers'] or current['fingerprint'] != plan['fingerprint']:
        raise ClientMergeError('Los datos cambiaron desde la vista previa; no se fusionó nada.')
    for model in (BusinessProposal, WebAppDiagnostic):
        for row in model._base_manager.filter(client_id__in=[survivor.pk, duplicate.pk]):
            capture_instance(row)
    # P1: raw identity retirement avoids a premature D snapshot cascade.
    _update(get_user_model(), duplicate.user_id, **plan['preview']['identity']['retired'])
    # P2: release the unique billing code before adopting it and its counter.
    billing = plan['preview']['identity']['billing']
    if billing['action'] == 'transfer':
        _update(UserProfile, duplicate.pk, billing_code=None)
        plan_profile_values = {**plan['profile_values'], 'billing_code': billing['survivor_code']}
    else:
        plan_profile_values = plan['profile_values']
    if plan['user_values']:
        for name, value in plan['user_values'].items():
            setattr(survivor.user, name, value)
        survivor.user.save(update_fields=list(plan['user_values']))
    if plan_profile_values:
        for name, value in plan_profile_values.items():
            setattr(survivor, name, value)
        survivor.save(update_fields=[*plan_profile_values, 'updated_at'])
    if billing['sequence_id']:
        _update(ClientDocumentNumberSequence, billing['sequence_id'], client_profile_id=survivor.pk)
    # P3: the managed-client CHECK and O2O must hold after each UPDATE.
    roots = plan['preview']['containers']
    comm = roots['communications']
    if comm['duplicate_root']:
        _update(CommunicationThread, comm['duplicate_root'], client_id=survivor.pk,
                managed_client_id=survivor.pk if comm['action'] == 'transfer' else None)
    for key in ('content.CommunicationFolder.client', 'content.CommunicationThread.client'):
        for pk in plan['relations'].get(key, []):
            if key == 'content.CommunicationThread.client' and pk == comm['duplicate_root']:
                continue
            relation = relation_inventory[key]
            _update(relation.model, pk, **{relation.field.attname: survivor.pk})
    # P4: roots first, then every other associated folder (including system trees).
    folders = roots['documents']
    if folders['duplicate_root']:
        _update(DocumentFolder, folders['duplicate_root'], client_user_id=survivor.user_id,
                managed_client_id=survivor.user_id if folders['action'] == 'transfer' else None)
    for pk in plan['relations'].get('content.DocumentFolder.client_user', []):
        if pk != folders['duplicate_root']:
            _update(DocumentFolder, pk, client_user_id=survivor.user_id)
    if folders['action'] == 'merge':
        merge = document_folder_merge.plan_folder_merge(
            folders['survivor_root'], folders['duplicate_root'],
            client_merge=(survivor.user_id, duplicate.user_id),
        )
        document_folder_merge.apply_folder_merge(merge, actor=actor)
    # P5: project signals now observe folders/threads under S already.
    for pk in plan['guards']['projects']:
        project = Project._base_manager.get(pk=pk)
        project.client = survivor.user
        project.save(update_fields=['client', 'updated_at'])
    # P6: emitted accounts keep emission facts; drafts reuse the domain writer.
    for pk in plan['relations'].get('content.Document.client_user', []):
        document = Document._base_manager.select_related('document_type').get(pk=pk)
        if (document.document_type and document.document_type.code == 'collection_account'
                and document.commercial_status == 'draft'):
            project_service._move_draft(document, survivor, actor)
        else:
            _update(Document, pk, client_user_id=survivor.user_id)
    # P7: validated financial reassignment, including hosting contact snapshots.
    for key in ('content.IncomeRecord.client', 'content.HostingRecord.client'):
        relation = relation_inventory[key]
        for pk in plan['relations'].get(key, []):
            record = relation.model._base_manager.get(pk=pk)
            validate_financial_reassignment(record, {'client': survivor})
            old_values = accounting_service.snapshot_values(record, 'income' if 'IncomeRecord' in key else 'hosting')
            record.client = survivor
            fields = ['client', 'updated_at']
            if 'HostingRecord' in key:
                fields += accounting_service._refresh_hosting_snapshot(record)
            record.save(update_fields=fields)
            accounting_service.log_entity_diff('income' if 'IncomeRecord' in key else 'hosting', record, old_values, actor)
    # P8: refresh canonical contact snapshots, never legal/approval snapshots.
    for model, key, sync in ((BusinessProposal, 'content.BusinessProposal.client', sync_snapshot),
                             (WebAppDiagnostic, 'content.WebAppDiagnostic.client', sync_diagnostic_snapshot)):
        for pk in plan['relations'].get(key, []):
            _update(model, pk, client_id=survivor.pk)
            sync(model._base_manager.select_related('client__user').get(pk=pk))
    # P9: remaining associations; special/collision relations were handled above.
    done = {'content.CommunicationFolder.client', 'content.CommunicationThread.client',
            'content.DocumentFolder.client_user', 'accounts.Project.client', 'content.IncomeRecord.client',
            'content.HostingRecord.client', 'content.BusinessProposal.client', 'content.WebAppDiagnostic.client',
            'content.DocumentFolder.managed_client', 'content.CommunicationThread.managed_client', NUMBER_SEQUENCE}
    for key, relation in relation_inventory.items():
        if RELATION_POLICIES.get(key) in (RELINK, COLLISION) and key not in done:
            _relink(plan, relation, survivor.user_id if relation.target is get_user_model() else survivor.pk)
    # P10: retire D only after confirming zero remaining projects (no cascades).
    if Project._base_manager.filter(client_id=duplicate.user_id).exists():
        raise ClientMergeError('El duplicado todavía tiene proyectos; se revierte la fusión.')
    duplicate.refresh_from_db()
    if duplicate.archived_at is None:
        archive_client(duplicate, transitions=[], actor=actor)
    for profile, field, target in ((duplicate, 'merged_into', survivor.pk), (survivor, 'merged_from', duplicate.pk)):
        AccountingChangeLog.objects.create(
            entity_type=AccountingChangeLog.EntityType.CLIENT, object_id=profile.pk,
            object_repr=build_client_display_name(profile), action=AccountingChangeLog.Action.UPDATED,
            actor=actor, actor_username=actor.get_username(),
            changes=[{'field': field, 'old': None, 'new': target},
                     {'field': 'operation', 'old': None, 'new': str(current_history_operation_id())}],
        )
    # P11: query the inventory again so an omitted or newly linked row rolls back.
    for key, relation in relation_inventory.items():
        policy = RELATION_POLICIES.get(key)
        should_move = policy in (RELINK, COLLISION) or key == 'content.Document.client_user'
        if key == NUMBER_SEQUENCE and billing['action'] != 'transfer':
            should_move = False
        if should_move and relation.rows_for(duplicate).exists():
            raise ClientMergeError(f'Quedó una asociación pendiente ({key}); se revierte la fusión.')
    return {'survivor': survivor.pk, 'duplicate': duplicate.pk, 'totals': plan['preview']['totals']}


@transaction.atomic
def client_merge_undo_blockers(step):
    """Guard facts outside recorded row differences, checked toward D on undo."""
    guards = step['guards']
    try:
        survivor, duplicate = _profile(guards['survivor']), _profile(guards['duplicate'])
    except UserProfile.DoesNotExist:
        return [_block('identity_missing', 'Uno de los perfiles de la fusión ya no existe.')]
    users = get_user_model()._base_manager.exclude(pk__in=[survivor.user_id, duplicate.user_id])
    blockers = []
    for identity in guards['identities'].values():
        query = Q(username__iexact=identity['username'])
        if _normalized('email', identity['email']):
            query |= Q(email__iexact=identity['email']) | Q(username__iexact=identity['email'])
        if users.filter(query).exists():
            blockers.append(_block('identity_taken', 'Otro usuario tomó una identidad necesaria para deshacer.'))
    for code in guards['billing_codes'].values():
        if code and UserProfile._base_manager.exclude(pk__in=[survivor.pk, duplicate.pk]).filter(
                billing_code__iexact=code).exists():
            blockers.append(_block('identity_taken', 'Otro cliente tomó un código de facturación que se restauraría.'))
    if (duplicate.user.is_active or fingerprint(duplicate.user.password) != guards['duplicate_password']
            or duplicate.is_onboarded != guards['duplicate_onboarded']):
        blockers.append(_block('duplicate_access_changed', 'El acceso del duplicado cambió después de la '
                               'fusión: activación, contraseña o incorporación a la plataforma.'))
    projects = list(Project._base_manager.filter(pk__in=guards['projects']).order_by('pk'))
    blockers += transfer_blockers(projects, duplicate.user)
    blockers += grant_blockers(duplicate.user_id, guards['projects'])
    link_ids = [item['pk'] for item in step['items']
                if item['model'] == 'secure_links.securelink' and item['field'] == 'owner_id']
    blockers += association_blockers(duplicate.pk, link_ids)
    from content.models import McpCredential, Task
    if (McpCredential._base_manager.filter(actor_id=duplicate.user_id).exists()
            or Task._base_manager.filter(assignee_id=duplicate.user_id).exists()
            or duplicate.user.groups.exists() or duplicate.user.user_permissions.exists()):
        blockers.append(_block('duplicate_access_changed', 'El duplicado recibió permisos o responsabilidades.'))
    for name, model, user_id in (('documents', DocumentFolder, duplicate.user_id),
                                  ('communications', CommunicationThread, duplicate.pk)):
        root = guards['containers'][name]['duplicate_root']
        if root and model._base_manager.filter(managed_client_id=user_id).exclude(pk=root).exists():
            blockers.append(_block('container_taken', 'El duplicado tiene una nueva raíz; no se puede restaurar la anterior.'))
        if name == 'documents' and root:
            blockers += document_folder_merge.folder_merge_undo_blockers(root)
    sequence = guards['billing']['sequence_id']
    if sequence and ClientDocumentNumberSequence._base_manager.filter(client_profile_id=duplicate.pk).exclude(pk=sequence).exists():
        blockers.append(_block('billing_sequence_conflict', 'El duplicado tiene una nueva secuencia de numeración.'))
    return blockers
