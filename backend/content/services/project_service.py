"""Cross-module operations on a project's client relationship.

``accounts.Project`` owns the client (a User) while hostings, incomes and
documents point at the project AND at the client (a UserProfile)
independently. This service is the only writer allowed to move a project
between clients: the impact is computed first (preview), the apply runs in
one transaction with one audit row per touched record, and issued documents
are never rewritten — an emitted cuenta is a fact, not a pointer.

Modes (the operator chooses every time; there is no default):
- ``move``: the linked records follow the project to the new client. Incomes
  with an active (non-cancelled) cuenta de cobro never change client — they
  detach from the project instead and stay with the old one; the path for a
  wrongly-billed cuenta is anular y reemitir, not rewriting history.
- ``detach``: the records keep their client and lose the project.
"""
from content.services.entity_history import historical_write
import logging

from content.models import (
    AccountingChangeLog,
    CommunicationThread,
    Document,
    DocumentFolder,
    HostingRecord,
    IncomeRecord,
)
from content.serializers.accounting import month_label
from content.services import accounting_service
from content.services.collection_account_create_service import (
    customer_snapshot_defaults,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

EntityType = AccountingChangeLog.EntityType
Action = AccountingChangeLog.Action

MODE_MOVE = 'move'
MODE_DETACH = 'detach'
MODES = (MODE_MOVE, MODE_DETACH)


def _profile_payload(profile):
    from accounts.services.proposal_client_service import (
        build_client_display_name,
    )

    if profile is None:
        return None
    return {'profile_id': profile.pk, 'name': build_client_display_name(profile)}


def _income_label(income):
    return {
        'id': income.pk,
        'label': income.concept,
        'kind_label': income.get_kind_display(),
        'period_label': month_label(income.period_date),
    }


def _collection_documents_qs(project):
    return Document.objects.filter(
        project=project, document_type__code=COLLECTION_ACCOUNT,
    )


def linked_sets(project, *, lock=False):
    """Everything pointing at the project, grouped by how the cascade treats it.

    ``blocked_income_pks``: incomes with a non-cancelled cuenta — their client
    is frozen by the emitted (or in-flight) document. ``draft_following`` are
    drafts with no income behind them (hosting-origin/standalone): they ride
    with the project. Income-backed drafts always belong to a blocked income
    (an active draft blocks it by definition), so they detach with it.
    """
    from accounts.models import (
        CollectionAccountContext,
        HostingSubscription,
        Payment,
        ProjectHosting,
    )
    from content.models import CommunicationFolder

    def rows(qs):
        qs = qs.order_by('pk')
        return qs.select_for_update() if lock else qs

    subscriptions = list(rows(HostingSubscription.objects.filter(project=project)))
    project_hostings = list(rows(ProjectHosting.objects.filter(project=project)))
    payments = list(rows(Payment.objects.filter(subscription_id__in=[row.pk for row in subscriptions])))
    hostings = list(rows(HostingRecord.objects.filter(project=project).select_related('client__user')))
    incomes = list(rows(IncomeRecord.objects.filter(project=project).select_related('client__user')))
    income_accounts = list(rows(Document.objects.filter(income_record_id__in=[row.pk for row in incomes])))
    blocked_income_pks = {
        row.income_record_id for row in income_accounts
        if row.commercial_status != Document.CommercialStatus.CANCELLED
    }
    cuentas = list(rows(_collection_documents_qs(project).select_related('collection_account')))
    drafts = [row for row in cuentas if row.commercial_status == Document.CommercialStatus.DRAFT]
    contexts = list(rows(CollectionAccountContext.objects.filter(document_id__in=[row.pk for row in cuentas])))
    communication_threads = list(rows(CommunicationThread.objects.filter(project=project).select_related('client__user')))
    communication_folders = list(rows(CommunicationFolder.objects.filter(project=project)))
    managed_root = rows(DocumentFolder.objects.filter(managed_project=project)).first()
    if managed_root is None:
        managed_folders = []
    else:
        managed_ids = {managed_root.pk}
        frontier = [managed_root.pk]
        while frontier:
            frontier = list(rows(DocumentFolder.objects.filter(parent_id__in=frontier)).values_list('pk', flat=True))
            managed_ids.update(frontier)
        managed_folders = list(rows(DocumentFolder.objects.filter(pk__in=managed_ids, project=project)))
    other_documents = list(rows(Document.objects.filter(project=project).exclude(document_type__code=COLLECTION_ACCOUNT)))
    return {
        'hostings': hostings,
        'incomes': incomes,
        'blocked_income_pks': blocked_income_pks,
        'draft_following': [d for d in drafts if d.income_record_id is None],
        'draft_detaching': [d for d in drafts if d.income_record_id is not None],
        'issued_accounts': [row for row in cuentas if row.commercial_status in (
            Document.CommercialStatus.ISSUED, Document.CommercialStatus.PAID,
        )],
        'collection_accounts': cuentas,
        'income_accounts': income_accounts,
        'collection_account_contexts': contexts,
        'subscriptions': subscriptions,
        'project_hostings': project_hostings,
        'payments': payments,
        'liquid_children': list(rows(IncomeRecord.objects.filter(expected_income_id__in=[
            row.pk for row in incomes if row.kind == IncomeRecord.Kind.EXPECTED
        ]))),
        # A conversation is historical evidence for its original client. It
        # never follows a project to a different owner; it loses only the
        # project scope and remains reachable from that original client.
        'communication_threads': communication_threads,
        'communication_folders': communication_folders,
        'managed_folders': managed_folders,
        # Contracts and other non-cuenta documents document the project and
        # travel with it implicitly; they are reported, never rewritten.
        'other_documents': other_documents,
        'other_documents_count': len(other_documents),
    }


def plan_client_change(sets, mode):
    """Pure cascade decisions used both to describe and to execute a mode."""
    linked_income_ids = {row.pk for row in sets['incomes']}
    independent_incomes = [
        row for row in sets['incomes'] if row.expected_income_id not in linked_income_ids
    ]
    moving = mode == MODE_MOVE
    records = {
        'hostings_move': [row.pk for row in sets['hostings'] if moving and row.client_id is not None],
        'hostings_detach': [row.pk for row in sets['hostings'] if not moving],
        'incomes_move': [row.pk for row in independent_incomes
                         if moving and row.client_id is not None and row.pk not in sets['blocked_income_pks']],
        'incomes_detach': [row.pk for row in independent_incomes
                           if not moving or (row.client_id is not None and row.pk in sets['blocked_income_pks'])],
        'draft_accounts_move': [row.pk for row in sets['draft_following'] if moving],
        'draft_accounts_detach': [row.pk for row in sets['draft_detaching']] + [
            row.pk for row in sets['draft_following'] if not moving
        ],
        'project_folders_move': [row.pk for row in sets['managed_folders']],
        'communication_threads_detach': [row.pk for row in sets['communication_threads']],
        'communication_folders_detach': [row.pk for row in sets['communication_folders']],
    }
    records['liquid_children_move'] = [row.pk for row in sets['liquid_children']
                                       if row.expected_income_id in records['incomes_move']]
    records['liquid_children_detach'] = [row.pk for row in sets['liquid_children']
                                         if row.expected_income_id in records['incomes_detach']]
    return {
        'moved': {
            'hostings': len(records['hostings_move']), 'incomes': len(records['incomes_move']),
            'draft_accounts': len(records['draft_accounts_move']),
            'project_folders': len(records['project_folders_move']),
        },
        'detached': {
            'hostings': len(records['hostings_detach']), 'incomes': len(records['incomes_detach']),
            'draft_accounts': len(records['draft_accounts_detach']),
        },
        'detached_communications': len(records['communication_threads_detach']),
        'skipped': {
            'issued_accounts': len(sets['issued_accounts']),
            'clientless': sum(row.client_id is None for row in sets['hostings'] + independent_incomes) if moving else 0,
            'other_documents': sets['other_documents_count'],
        },
        'records': records,
    }


def _client_change_impact(project, new_profile, sets, evaluation, *, lock=False):
    """Hash all identities, including hidden financial history and capped tails."""
    import hashlib
    import json

    from accounts.services.project_client_transfer import transfer_history_ids

    payments = sets['payments']
    financial_history = {
        'subscriptions': [{
            'id': subscription.pk,
            'payments': [{'id': payment.pk, 'status': payment.status, 'due_date': payment.due_date.isoformat()}
                         for payment in payments if payment.subscription_id == subscription.pk],
        } for subscription in sets['subscriptions']],
        'project_hosting_ids': [row.pk for row in sets['project_hostings']],
        'hosting_record_ids': [row.pk for row in sets['hostings']],
        'issued_accounts': [{'id': row.pk, 'status': row.commercial_status} for row in sets['collection_accounts']
                            if row.commercial_status != Document.CommercialStatus.DRAFT],
        'collection_account_contexts': [{
            'id': row.pk, 'document_id': row.document_id, 'nature': row.nature,
            'contract_id': row.contract_id, 'amendment_id': row.amendment_id, 'project_hosting_id': row.hosting_id,
        } for row in sets['collection_account_contexts']],
    }
    planned = {mode: plan_client_change(sets, mode) for mode in MODES}
    identities = {name: sorted(row.pk for row in rows) for name, rows in sets.items() if isinstance(rows, list)}
    history_ids = transfer_history_ids(project, lock=lock)
    canonical = {
        'target_profile_id': new_profile.pk, 'target_owner_id': new_profile.user_id,
        'current_owner_id': project.client_id,
        'linked_sets': identities, 'history_ids': history_ids,
        'blocked_income_ids': sorted(sets['blocked_income_pks']),
        'blockers': [{'code': row['code'], 'resource_type': row['resource_type'], 'resource_id': row['resource_id']}
                     for row in evaluation['blockers']],
        'financial_history': financial_history, 'planned': planned,
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str).encode('utf-8')
    return {
        **evaluation, 'can_apply': not any(evaluation['blocker_counts'].values()),
        'planned': planned, 'financial_history': financial_history,
        'impact_hash': hashlib.sha256(encoded).hexdigest(),
    }


def change_client_preview(project, new_profile, *, lock=False):
    """The full impact of moving ``project`` to ``new_profile``, labelled.

    The hash describes both modes, so the operator can choose either after
    reviewing it. Legacy Panel clients can still echo the linked id lists.
    """
    from accounts.models import Project
    from accounts.services.project_client_transfer import client_transfer_blockers

    if lock:
        project = Project.objects.select_for_update().get(pk=project.pk)
    evaluation = client_transfer_blockers(project, new_profile.user, lock=lock)
    sets = linked_sets(project, lock=lock)
    blocked = sets['blocked_income_pks']
    current_profile = getattr(project.client, 'profile', None)

    def cuenta_row(document):
        return {
            'id': document.pk,
            'title': document.title,
            'public_number': document.public_number or '',
            'status_label': document.get_commercial_status_display(),
        }

    hostings_move = [
        {'id': record.pk, 'label': record.display_label}
        for record in sets['hostings'] if record.client_id is not None
    ]
    incomes_move = [
        _income_label(record) for record in sets['incomes']
        if record.client_id is not None and record.pk not in blocked
    ]
    incomes_blocked = [
        {
            **_income_label(record),
            'reason': 'Tiene una cuenta de cobro activa: se desvincula del '
                      'proyecto y conserva su cliente.',
        }
        for record in sets['incomes'] if record.pk in blocked
    ]
    clientless = (
        [
            {'id': record.pk, 'entity': 'hosting', 'label': record.display_label}
            for record in sets['hostings'] if record.client_id is None
        ]
        + [
            {'id': record.pk, 'entity': 'income', 'label': record.concept}
            for record in sets['incomes'] if record.client_id is None
        ]
    )
    return {
        **_client_change_impact(project, new_profile, sets, evaluation, lock=lock),
        'project': {'id': project.pk, 'name': project.name},
        'current_client': _profile_payload(current_profile),
        'new_client': _profile_payload(new_profile),
        'hostings_move': hostings_move,
        'incomes_move': incomes_move,
        'incomes_blocked': incomes_blocked,
        'clientless': clientless,
        'draft_accounts': [
            cuenta_row(d)
            for d in sets['draft_following'] + sets['draft_detaching']
        ],
        'issued_accounts': [cuenta_row(d) for d in sets['issued_accounts']],
        'communication_threads_detaching': [
            {'id': thread.pk, 'title': thread.title}
            for thread in sets['communication_threads']
        ],
        'project_folders_following': [
            {'id': folder.pk, 'name': folder.name}
            for folder in sets['managed_folders']
        ],
        'other_documents_count': sets['other_documents_count'],
        'hosting_ids': [record.pk for record in sets['hostings']],
        'income_ids': [record.pk for record in sets['incomes']],
        'communication_thread_ids': [
            thread.pk for thread in sets['communication_threads']
        ],
        'totals': {
            'move': len(hostings_move) + len(incomes_move),
            'blocked': len(incomes_blocked),
            'clientless': len(clientless),
            'drafts': len(sets['draft_following']) + len(sets['draft_detaching']),
            'issued': len(sets['issued_accounts']),
            'communications': len(sets['communication_threads']),
            'project_folders': len(sets['managed_folders']),
        },
    }


def _log_diff(entity_type, instance, old_values, user):
    return accounting_service.log_entity_diff(
        entity_type, instance, old_values, user,
    )


def _detach_record(entity_type, record, user):
    old_values = accounting_service.snapshot_values(record, entity_type)
    record.project = None
    record.save(update_fields=['project', 'updated_at'])
    _log_diff(entity_type, record, old_values, user)


def _detach_draft(document, user):
    old_values = accounting_service.snapshot_values(
        document, EntityType.COLLECTION_ACCOUNT,
    )
    document.project = None
    document.save(update_fields=['project', 'updated_at'])
    _log_diff(EntityType.COLLECTION_ACCOUNT, document, old_values, user)


def _move_draft(document, new_profile, user):
    """A project-only draft follows the project: new client, fresh snapshot.

    Only the provisional customer_* snapshot is rewritten — a draft has not
    been emitted, so there is no history to preserve; ``customer_project_name``
    stays, the project itself did not change.
    """
    old_values = accounting_service.snapshot_values(
        document, EntityType.COLLECTION_ACCOUNT,
    )
    document.client_user = new_profile.user
    document.save(update_fields=['client_user', 'updated_at'])
    account = getattr(document, 'collection_account', None)
    if account is not None:
        defaults = customer_snapshot_defaults(new_profile)
        account.customer_name = defaults['name'] or ''
        account.customer_email = defaults['email'] or ''
        account.customer_identification = defaults['identification'] or ''
        account.customer_identification_type = (
            defaults['identification_type'] or ''
        )
        account.customer_contact_name = defaults['contact_name'] or ''
        account.customer_address = defaults['address'] or ''
        account.save(update_fields=[
            'customer_name', 'customer_email', 'customer_identification',
            'customer_identification_type', 'customer_contact_name',
            'customer_address',
        ])
    _log_diff(EntityType.COLLECTION_ACCOUNT, document, old_values, user)


@historical_write
@transaction.atomic
def change_client_apply(project, new_profile, mode, user):
    """Move the project to ``new_profile`` and cascade per ``mode``.

    One transaction: a half-moved project would split every per-client
    figure across two owners. Audit rows ride inside it (a rolled-back move
    must not leave a log claiming it happened) and none of them notify by
    email — the bulk convention.
    """
    from accounts.models import Project
    from accounts.services.billing_reassignment import (
        validate_project_billing_reassignment,
    )
    from accounts.services.delivery_client_transfer import (
        assert_delivery_client_transfer_safe,
    )
    from accounts.services.issue_client_transfer import (
        assert_issue_client_transfer_safe,
    )

    original_project = project
    project = Project.objects.select_for_update().get(pk=project.pk)
    # P0 integrates finance -> delivery -> issues -> access revoke -> save.
    validate_project_billing_reassignment(project, new_profile.user)
    project = assert_delivery_client_transfer_safe(original_project, new_profile.user, actor=user)
    assert_issue_client_transfer_safe(project, new_profile.user)
    sets = linked_sets(project, lock=True)
    plan = plan_client_change(sets, mode)
    records = plan['records']

    old_project_values = accounting_service.snapshot_values(
        project, EntityType.PROJECT,
    )
    if project.client_id != new_profile.user_id:
        from accounts.services.project_client_access import revoke_grants
        revoke_grants(project, actor=user)
    moved = plan['moved']
    detached = plan['detached']
    skipped = plan['skipped']

    # Always preserve the original client on historical conversations. Both
    # cascade modes only detach their project pointer.
    #
    # The old managed thread becomes ordinary historical correspondence; a
    # fresh thread is provisioned for the new owner after the cascade.
    detached_communications = plan['detached_communications']
    if detached_communications:
        CommunicationThread.objects.filter(
            pk__in=records['communication_threads_detach'],
        ).update(
            project=None,
            managed_project=None,
            folder=None,
            updated_by=user,
            updated_at=timezone.now(),
        )

    # Old correspondence folders remain with their historical client.
    from content.models import CommunicationFolder
    CommunicationFolder.objects.filter(pk__in=records['communication_folders_detach']).update(project=None)

    # Detach historical threads before post-save synchronization can replace
    # their client with the new project owner.
    project.client = new_profile.user
    project.save(update_fields=['client', 'updated_at'])
    _log_diff(EntityType.PROJECT, project, old_project_values, user)

    for record in sets['hostings']:
        if record.pk in records['hostings_detach']:
            _detach_record(EntityType.HOSTING, record, user)
        elif record.pk in records['hostings_move']:
            old_values = accounting_service.snapshot_values(record, EntityType.HOSTING)
            record.client = new_profile
            update_fields = ['client', 'updated_at'] + accounting_service._refresh_hosting_snapshot(record)
            record.save(update_fields=update_fields)
            _log_diff(EntityType.HOSTING, record, old_values, user)
    for record in sets['incomes']:
        if record.pk in records['incomes_detach']:
            _detach_record(EntityType.INCOME, record, user)
            if record.kind == IncomeRecord.Kind.EXPECTED:
                accounting_service._cascade_project_to_liquid_children(record, user)
        elif record.pk in records['incomes_move']:
            old_values = accounting_service.snapshot_values(record, EntityType.INCOME)
            record.client = new_profile
            record.save(update_fields=['client', 'updated_at'])
            _log_diff(EntityType.INCOME, record, old_values, user)
            if record.kind == IncomeRecord.Kind.EXPECTED:
                accounting_service._cascade_client_to_liquid_children(record, user)
    for document in sets['draft_following'] + sets['draft_detaching']:
        if document.pk in records['draft_accounts_move']:
            _move_draft(document, new_profile, user)
        elif document.pk in records['draft_accounts_detach']:
            _detach_draft(document, user)

    # Updating a project only synchronizes existing managed threads. This
    # operation detached the old one, so explicitly provision its replacement.
    from content.services.project_communication_service import ensure_project_thread

    ensure_project_thread(project)

    logger.info(
        'Project %s changed client to profile %s (mode=%s): moved=%s detached=%s',
        project.pk, new_profile.pk, mode, moved, detached,
    )
    return {
        'moved': moved,
        'detached': detached,
        'detached_communications': detached_communications,
        'skipped': skipped,
    }


def deletion_blockers(project):
    """Counts that must be zero before a hard delete is allowed.

    Every status counts — even a cancelled cuenta loses its reference on a
    hard delete, which is exactly the silent SET_NULL blanking this guard
    exists to stop (PA-29: archive, never delete).
    """
    return {
        'hostings': HostingRecord.objects.filter(project=project).count(),
        'incomes': IncomeRecord.objects.filter(project=project).count(),
        'documents': Document.objects.filter(project=project).count(),
        'communication_threads': CommunicationThread.objects.filter(
            project=project,
        ).count(),
    }


def project_snapshot(project):
    """Pre-mutation snapshot for :func:`log_project_event` callers."""
    return accounting_service.snapshot_values(project, EntityType.PROJECT)


def log_project_event(project, action, old_values, user):
    """One audit row for a project-level mutation.

    ``old_values`` is the pre-mutation snapshot (empty dict for CREATED).
    For DELETED the diff is every non-empty tracked field going to '' —
    written BEFORE the delete so the row still has a pk to reference.
    """
    if action == Action.DELETED:
        changes = accounting_service._deletion_changes(
            EntityType.PROJECT, old_values,
        )
    elif action == Action.CREATED:
        new_values = accounting_service.snapshot_values(
            project, EntityType.PROJECT,
        )
        changes = [
            {'field': field, 'label': label, 'old': '', 'new': new_values[field]}
            for field, label in accounting_service.TRACKED_FIELDS[
                EntityType.PROJECT
            ]
            if new_values[field] != ''
        ]
    else:
        changes = accounting_service.compute_changes(
            EntityType.PROJECT, old_values,
            accounting_service.snapshot_values(project, EntityType.PROJECT),
        )
        if not changes:
            return None
    return accounting_service.log_accounting_change(
        entity_type=EntityType.PROJECT,
        object_id=project.pk,
        object_repr=accounting_service.object_repr(EntityType.PROJECT, project),
        action=action,
        changes=changes,
        actor=user,
    )
