"""Protect explicit billing associations when accounting labels are reassigned."""
from copy import copy

from content.models import Document
from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.models import (
    CollectionAccountContext,
    ProjectHosting,
    ProjectHostingAccountingSource,
)
from accounts.services.billing_access import invalid
from accounts.services.billing_context import _lock_context, resolve_context
from accounts.services.project_client_transfer import (
    BILLING_CODE,
    BILLING_MESSAGE,
    client_transfer_blockers,
)


@transaction.atomic
def validate_project_billing_reassignment(project, client):
    """Central project writers call this before changing a financial owner."""
    if not project.pk:
        return
    evaluation = client_transfer_blockers(project, client, lock=True)
    if any(row['code'] == BILLING_CODE for row in evaluation['blockers']):
        error = ValidationError({'detail': BILLING_MESSAGE})
        error.detail.update(evaluation)
        raise error


@transaction.atomic
def validate_amendment_billing_reassignment(amendment, contract):
    if amendment.pk and contract.pk != amendment.contract_id and amendment.collection_contexts.select_for_update().exists():
        invalid('El otrosí tiene cuentas asociadas y no puede trasladarse a otro contrato.')


def validate_document_reassignment(document, *, changes=None, lock=False):
    if document._meta.model_name != 'document':
        return
    proposed = copy(document)
    for field, value in (changes or {}).items():
        setattr(proposed, field, value)
    context = (_lock_context(document) if lock else
               CollectionAccountContext.objects.filter(document_id=document.pk).first())
    if context:
        if not proposed.project_id:
            invalid('No se puede desvincular el proyecto de una cuenta ya asociada.')
        # Reassignment validates relationships. Readiness to emit is a separate
        # check: a historical association can still await evidence reconciliation.
        resolve_context(proposed, {
            'billing_nature': context.nature, 'contract_id': context.contract_id,
            'amendment_id': context.amendment_id, 'project_hosting_id': context.hosting_id,
        }, lock_relations=lock)
    elif proposed.project_id and proposed.client_user_id and proposed.project.client_id != proposed.client_user_id:
        invalid('La cuenta y el proyecto deben pertenecer al mismo cliente.')


def validate_financial_reassignment(record, changes):
    if record._meta.model_name not in ('hostingrecord', 'incomerecord'):
        return
    proposed = copy(record)
    for key, value in changes.items():
        setattr(proposed, key, value)
    source = (ProjectHostingAccountingSource.objects.select_for_update().filter(hosting_record_id=record.pk).first()
              if record._meta.model_name == 'hostingrecord' else None)
    if source:
        hosting = ProjectHosting.objects.select_for_update().get(pk=source.hosting_id)
        project = record.project
        if (not project or hosting.project_id != project.pk or proposed.project_id != project.pk
                or not proposed.client_id or proposed.client.user_id != project.client_id):
            invalid('El origen está asociado al hosting del proyecto; corrige la conciliación antes de reasignarlo.')
    relation = 'hosting_record_id' if record._meta.model_name == 'hostingrecord' else 'income_record_id'
    documents = Document.objects.select_for_update().filter(**{relation: record.pk}).order_by('pk')
    for document in documents:
        if not CollectionAccountContext.objects.select_for_update().filter(document=document).exists():
            continue
        if (not proposed.project_id or proposed.project_id != document.project_id or not proposed.client_id
                or proposed.client.user_id != proposed.project.client_id):
            invalid('El origen tiene cuentas asociadas; no puede moverse a otro proyecto o cliente.')
