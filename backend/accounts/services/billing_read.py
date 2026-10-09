"""Public financial projections with prefetched relations and no mutations."""
from django.db.models import Prefetch, Q
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import ContractAmendment, HostingSubscription, Project, ProjectContract, ProjectHosting
from accounts.services.billing_access import billing_project, documents_for_actor, is_billing_admin
from accounts.services.billing_context import context_data
from content.models import Document, HostingRecord


CONTEXT_RELATIONS = (
    'billing_context__contract', 'billing_context__amendment', 'billing_context__hosting',
)


def account_queryset():
    return Document.objects.filter(document_type__code='collection_account').select_related(
        'project', 'client_user', 'document_type', 'issuer', 'collection_account', *CONTEXT_RELATIONS,
    ).prefetch_related('items', 'payment_methods')


def visible_accounts(actor, filters=None):
    qs = documents_for_actor(account_queryset(), actor)
    filters = filters or {}
    for key, lookup in (
        ('project_id', 'project_id'), ('contract_id', 'billing_context__contract_id'),
        ('amendment_id', 'billing_context__amendment_id'), ('hosting_id', 'billing_context__hosting_id'),
    ):
        if filters.get(key):
            try:
                value = int(filters[key])
                if value < 1:
                    raise ValueError()
            except (TypeError, ValueError):
                raise ValidationError({key: 'Identificador inválido.'})
            qs = qs.filter(**{lookup: value})
    nature = filters.get('nature')
    if nature:
        if nature == 'pending':
            qs = qs.filter(billing_context__isnull=True, project__isnull=False)
        elif nature in ('contract', 'hosting'):
            qs = qs.filter(billing_context__nature=nature)
        else:
            raise ValidationError({'nature': 'Naturaleza inválida.'})
    status = filters.get('commercial_status')
    if status:
        if status not in Document.CommercialStatus.values:
            raise ValidationError({'commercial_status': 'Estado inválido.'})
        qs = qs.filter(commercial_status=status)
    return qs.order_by('-created_at', '-pk')


def account_for_actor(account_id, actor):
    document = visible_accounts(actor).filter(pk=account_id).first()
    if not document:
        raise NotFound('Cuenta de cobro no encontrada.')
    return document


def project_billing_options(project_id, actor):
    project = billing_project(project_id, actor)
    # These are billing reference names, never document/signature access grants.
    contracts = ProjectContract.objects.filter(project=project).order_by('pk')
    amendments = ContractAmendment.objects.all()
    if not is_billing_admin(actor):
        accounts = visible_accounts(actor).filter(project=project)
        contracts = contracts.filter(collection_contexts__document__in=accounts).distinct()
        amendments = amendments.filter(collection_contexts__document__in=accounts).distinct()
    contracts = contracts.prefetch_related(Prefetch('amendments', queryset=amendments))
    hosting = ProjectHosting.objects.filter(project=project).first()
    result = {'project_id': project.pk, 'project_name': project.name,
            'contracts': [{'id': contract.pk, 'title': contract.title,
                           'amendments': [{'id': row.pk, 'title': row.title} for row in contract.amendments.all()]} for contract in contracts],
            'hosting_id': hosting.pk if hosting else None}
    if is_billing_admin(actor):
        from accounts.models import DeliveryWorkspace
        from accounts.services.billing_contracts import contract_source_options
        result['contract_sources'] = contract_source_options(project)
        result['delivery_version'] = DeliveryWorkspace.objects.filter(project=project).values_list('version', flat=True).first() or 0
    return result


def payment_data(payment):
    return {name: getattr(payment, name) for name in (
        'id', 'amount', 'description', 'billing_period_start', 'billing_period_end', 'due_date',
        'status', 'paid_at', 'created_at', 'is_archived', 'archived_at',
    )}


def cycle_data(cycle):
    return {name: getattr(cycle, name) for name in (
        'id', 'hosting_record_id', 'modality', 'amount', 'paid_at', 'period_from', 'period_to', 'cycles_represented',
    )}


def project_hosting_read(project_id, actor):
    project = billing_project(project_id, actor)
    hosting = ProjectHosting.objects.select_related('operational_accounting_source').filter(project=project).first()
    subscription = HostingSubscription.objects.filter(project=project).first()
    records = HostingRecord.objects.filter(project=project).select_related('client', 'billing_source').prefetch_related('cycles').order_by('pk')
    if not is_billing_admin(actor):
        records = records.filter(client__user=project.client)
    mapped_ids = set(hosting.accounting_sources.values_list('hosting_record_id', flat=True)) if hosting else set()
    source_rows = [{
        'id': row.pk, 'domain_url': row.domain_url, 'payment_modality': row.payment_modality,
        'is_active': row.is_active, 'monthly_value': row.monthly_value,
        'payment_per_cycle': row.payment_per_cycle, 'valid_from': row.valid_from,
        'valid_to': row.valid_to, 'total_paid': row.total_paid,
        'associated': row.pk in mapped_ids,
        'operational': bool(hosting and hosting.operational_accounting_source_id and hosting.operational_accounting_source.hosting_record_id == row.pk),
        'cycles': [cycle_data(cycle) for cycle in row.cycles.all()],
    } for row in records]
    groups = []
    visible_document_ids = set(visible_accounts(actor).filter(project=project).values_list('pk', flat=True))
    visible_cycle_ids = {cycle['id'] for row in source_rows for cycle in row['cycles']}
    if hosting:
        for group in hosting.evidence_groups.prefetch_related('evidence__payment', 'evidence__cycle', 'evidence__document').order_by('pk'):
            references = []
            for evidence in group.evidence.all():
                if evidence.payment_id and subscription and evidence.payment.subscription_id == subscription.pk:
                    references.append({'kind': 'payment', 'id': evidence.payment_id,
                                       'amount': evidence.payment.amount, 'status': evidence.payment.status})
                elif evidence.cycle_id and evidence.cycle_id in visible_cycle_ids:
                    references.append({'kind': 'cycle', 'id': evidence.cycle_id,
                                       'amount': evidence.cycle.amount, 'status': 'paid'})
                elif evidence.document_id in visible_document_ids:
                    references.append({'kind': 'account', 'id': evidence.document_id,
                                       'amount': evidence.document.total, 'status': evidence.document.commercial_status})
            groups.append({'id': group.pk, 'label': group.label, 'evidence': references,
                           'amounts_differ': len({str(row['amount']) for row in references}) > 1,
                           'statuses_differ': len({row['status'] for row in references}) > 1})
    subscription_data = None
    if subscription:
        subscription_data = {name: getattr(subscription, name) for name in (
            'id', 'plan', 'status', 'base_monthly_amount', 'effective_monthly_amount', 'billing_amount',
            'start_date', 'next_billing_date', 'card_brand', 'card_last_four',
        )}
        subscription_data['associated'] = bool(hosting and hosting.subscription_id == subscription.pk)
        subscription_data['payments'] = [payment_data(row) for row in subscription.payments.order_by('-billing_period_start', '-pk')]
    return {
        'project_id': project.pk, 'project_name': project.name,
        'hosting_id': hosting.pk if hosting else None, 'version': hosting.version if hosting else 0,
        'has_hosting': bool(hosting or subscription or source_rows),
        'reconciliation_required': bool((subscription and (not hosting or hosting.subscription_id != subscription.pk))
                                        or any(not row['associated'] for row in source_rows)),
        'subscription': subscription_data, 'accounting_sources': source_rows, 'evidence_groups': groups,
    }


def project_hosting_list(actor):
    qs = Project.objects.filter(Q(billing_hosting__isnull=False) | Q(hosting_subscription__isnull=False)
                                | Q(hosting_records__isnull=False)).distinct().order_by('name', 'pk')
    if not is_billing_admin(actor):
        qs = qs.filter(client=actor)
    return list(qs.values('id', 'name'))
