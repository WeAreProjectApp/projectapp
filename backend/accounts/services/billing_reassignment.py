"""Protect explicit billing associations when accounting labels are reassigned."""
from copy import copy
from django.db import models
from accounts.models import CollectionAccountContext, HostingSubscription, ProjectHosting, ProjectHostingAccountingSource
from accounts.services.billing_access import invalid
from accounts.services.billing_context import resolve_context
from content.models import Document, HostingRecord


def validate_project_billing_reassignment(project, client):
    """Central project writers call this before changing a financial owner."""
    if not project.pk or client.pk == project.client_id:
        return
    has_accounts = Document.objects.filter(project=project, document_type__code='collection_account').filter(
        models.Q(billing_context__isnull=False) | ~models.Q(commercial_status='draft'),
    ).exists()
    has_hosting = (ProjectHosting.objects.filter(project=project).exists()
                   or HostingSubscription.objects.filter(project=project).exists()
                   or HostingRecord.objects.filter(project=project).exists())
    if has_accounts or has_hosting:
        invalid('El proyecto tiene cuentas o hosting con historia financiera; no puede trasladarse a otro cliente.')


def validate_amendment_billing_reassignment(amendment, contract):
    if amendment.pk and contract.pk != amendment.contract_id and amendment.collection_contexts.exists():
        invalid('El otrosí tiene cuentas asociadas y no puede trasladarse a otro contrato.')


def validate_document_reassignment(document, *, changes=None):
    proposed = copy(document)
    for field, value in (changes or {}).items():
        setattr(proposed, field, value)
    context = CollectionAccountContext.objects.filter(document_id=document.pk).first()
    if context:
        if not proposed.project_id:
            invalid('No se puede desvincular el proyecto de una cuenta ya asociada.')
        # Reassignment validates relationships. Readiness to emit is a separate
        # check: a historical association can still await evidence reconciliation.
        resolve_context(proposed, {
            'billing_nature': context.nature, 'contract_id': context.contract_id,
            'amendment_id': context.amendment_id, 'project_hosting_id': context.hosting_id,
        })
    elif proposed.project_id and proposed.client_user_id and proposed.project.client_id != proposed.client_user_id:
        invalid('La cuenta y el proyecto deben pertenecer al mismo cliente.')


def validate_financial_reassignment(record, changes):
    if record._meta.model_name not in ('hostingrecord', 'incomerecord'):
        return
    proposed = copy(record)
    for key, value in changes.items():
        setattr(proposed, key, value)
    if hasattr(record, 'billing_source'):
        source = ProjectHostingAccountingSource.objects.select_related('hosting__project').get(hosting_record_id=record.pk)
        project = source.hosting.project
        if proposed.project_id != project.pk or not proposed.client_id or proposed.client.user_id != project.client_id:
            invalid('El origen está asociado al hosting del proyecto; corrige la conciliación antes de reasignarlo.')
    relation = 'hosting_record_id' if record._meta.model_name == 'hostingrecord' else 'income_record_id'
    documents = Document.objects.filter(**{relation: record.pk}).select_related('project')
    for document in documents:
        if not CollectionAccountContext.objects.filter(document=document).exists():
            continue
        if proposed.project_id != document.project_id or not proposed.client_id or proposed.client.user_id != document.project.client_id:
            invalid('El origen tiene cuentas asociadas; no puede moverse a otro proyecto o cliente.')
