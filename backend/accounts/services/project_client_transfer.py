"""Read the history that prevents changing a project's client."""

from content.models import Document, HostingRecord
from django.db import transaction
from django.db.models import Q

from accounts.models import (
    BugReport,
    ChangeRequest,
    CollectionAccountContext,
    ContractAmendment,
    ContractSignatureEvidence,
    DeliveryMessage,
    DeliveryPromptContext,
    DeliveryPublication,
    HostingSubscription,
    Project,
    ProjectContract,
    ProjectHosting,
)

BILLING_CODE = 'client_change_financial_history'
BILLING_MESSAGE = 'El proyecto tiene cuentas o hosting con historia financiera; no puede trasladarse a otro cliente.'
DELIVERY_CODE = 'delivery_client_history_frozen'
DELIVERY_MESSAGE = (
    'Este proyecto conserva entregas, firmas, fuentes o conversaciones del cliente actual. '
    'No puedes transferirlo a otra persona porque expondría esa historia. '
    'Crea un proyecto separado para el nuevo cliente.'
)
ISSUE_CODE = 'issue_client_transfer_history'
ISSUE_MESSAGE = (
    'El proyecto conserva bugs o solicitudes del cliente actual. '
    'Cambiar de cliente expondría esa historia.'
)
MAX_BLOCKERS_PER_RESOURCE = 100


def transfer_history_querysets(project, *, lock=False):
    """Keep the guard predicates and their order in one place."""
    project = project.pk
    accounts = Document.objects.filter(project=project, document_type__code='collection_account')
    resources = (
        (BILLING_CODE, BILLING_MESSAGE, 'hosting_subscription', HostingSubscription.objects.filter(project=project)),
        (BILLING_CODE, BILLING_MESSAGE, 'project_hosting', ProjectHosting.objects.filter(project=project)),
        (BILLING_CODE, BILLING_MESSAGE, 'hosting_record', HostingRecord.objects.filter(project=project)),
        (BILLING_CODE, BILLING_MESSAGE, 'collection_account', accounts),
        (BILLING_CODE, BILLING_MESSAGE, 'collection_account_context', CollectionAccountContext.objects.filter(document__in=accounts)),
        (DELIVERY_CODE, DELIVERY_MESSAGE, 'delivery_publication', DeliveryPublication.objects.filter(stage__phase__scope__contract__project=project)),
        (DELIVERY_CODE, DELIVERY_MESSAGE, 'delivery_prompt_context', DeliveryPromptContext.objects.filter(project=project)),
        (DELIVERY_CODE, DELIVERY_MESSAGE, 'contract_signature_evidence', ContractSignatureEvidence.objects.filter(
            Q(contract__project=project) | Q(amendment__contract__project=project),
        )),
        (DELIVERY_CODE, DELIVERY_MESSAGE, 'project_contract', ProjectContract.objects.filter(project=project, document__signed_at__isnull=False)),
        (DELIVERY_CODE, DELIVERY_MESSAGE, 'contract_amendment', ContractAmendment.objects.filter(contract__project=project, document__signed_at__isnull=False)),
        (DELIVERY_CODE, DELIVERY_MESSAGE, 'delivery_message', DeliveryMessage.objects.filter(project=project, is_internal=False)),
        (ISSUE_CODE, ISSUE_MESSAGE, 'bug_report', BugReport.objects.filter(project=project)),
        (ISSUE_CODE, ISSUE_MESSAGE, 'change_request', ChangeRequest.objects.filter(project=project)),
    )
    return tuple(
        (code, message, kind, qs.order_by('pk').select_for_update() if lock else qs.order_by('pk'))
        for code, message, kind, qs in resources
    )


def transfer_history_ids(project, *, lock=False):
    """Uncapped identities also cover blockers omitted from the response."""
    identities = {}
    account_ids = []
    for _code, _message, kind, qs in transfer_history_querysets(project, lock=lock):
        if kind == 'collection_account':
            # The billing guard locks drafts as well: a context can freeze a
            # draft, and issuance cannot race with the ownership check.
            accounts = list(qs.only('pk', 'commercial_status'))
            account_ids = [row.pk for row in accounts]
            identities[kind] = [row.pk for row in accounts if row.commercial_status != 'draft']
        else:
            if kind == 'collection_account_context':
                qs = CollectionAccountContext.objects.filter(document_id__in=account_ids).order_by('pk')
                if lock:
                    qs = qs.select_for_update()
            identities[kind] = list(qs.values_list('pk', flat=True))
    return identities


@transaction.atomic
def client_transfer_blockers(project, new_client, *, lock=False):
    """Evaluate all three transfer guards without mutating any history.

    Locking reads must run under the caller's project write transaction. The
    nested atomic block also lets standalone guards retain their old API.
    Financial resources are all reported; delivery and ticket lists are capped
    per resource type, with exact totals even when the response is truncated.
    """
    resources = transfer_history_querysets(project, lock=lock)
    counts = {kind: 0 for _code, _message, kind, _qs in resources}
    if project.pk is None:
        return {'blockers': [], 'blocker_counts': counts}
    current = Project.objects.select_for_update() if lock else Project.objects.all()
    owner_id = current.values_list('client_id', flat=True).get(pk=project.pk)
    if owner_id == (new_client.pk if new_client is not None else None):
        return {'blockers': [], 'blocker_counts': counts}
    blockers = []
    identities = transfer_history_ids(project, lock=lock)
    for code, message, kind, _qs in resources:
        # Aggregate SQL ignores FOR UPDATE on MySQL. Materialize identities so
        # totals and the capped payload both use the current locking read.
        ids = identities[kind]
        counts[kind] = len(ids)
        if code != BILLING_CODE:
            ids = ids[:MAX_BLOCKERS_PER_RESOURCE]
        blockers.extend({
            'code': code, 'message': message, 'resource_type': kind,
            'resource_id': pk if isinstance(pk, int) else str(pk),
            'resolution': 'create_new_project',
        } for pk in ids)
    return {'blockers': blockers, 'blocker_counts': counts}
