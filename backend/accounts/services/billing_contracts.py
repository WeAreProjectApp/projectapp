"""Explicitly register an existing project source for billing, without copying it."""
from django.db import transaction
from django.db.models import Q

from accounts.models import ProjectContract
from accounts.services.billing_access import billing_project, invalid, require_billing_admin
from accounts.services.delivery_workflow import mutate_node
from content.models import Document, ProposalDocument


def contract_sources(project):
    """Sources have an explicit project boundary; names never establish ownership."""
    documents = Document.objects.filter(project=project, is_archived=False).filter(
        Q(client_user__isnull=True) | Q(client_user_id=project.client_id),
    ).exclude(document_type__code='collection_account').exclude(
        contract_template__isnull=False,
    ).exclude(contract_mirror__isnull=False).only('id', 'title').order_by('title', 'pk')
    proposals = ProposalDocument.objects.filter(
        Q(proposal__project_phases__project=project) | Q(proposal__deliverable__project=project),
        document_type__in=ProposalDocument.CONTRACT_DOC_TYPES,
        proposal__client__user_id=project.client_id,
    ).only('id', 'title').distinct().order_by('title', 'pk')
    return documents, proposals


def contract_source_options(project):
    documents, proposals = contract_sources(project)
    return [
        {'source_type': kind, 'id': row.pk, 'title': row.title,
         'origin_label': label}
        for kind, label, rows in (
            ('document', 'Documento del proyecto', documents),
            ('proposal_document', 'Contrato de propuesta', proposals),
        )
        for row in rows
    ]


@transaction.atomic
def link_billing_contract(project_id, actor, data):
    require_billing_admin(actor)
    project = billing_project(project_id, actor, lock=True)
    documents, proposals = contract_sources(project)
    kind = data['source_type']
    source = (documents if kind == 'document' else proposals).filter(pk=data['source_id']).first()
    if source is None:
        invalid('Selecciona un contrato existente de este proyecto y cliente.')
    field = f'{kind}_id'
    existing = ProjectContract.objects.filter(project=project, **{field: source.pk}).order_by('pk').first()
    if existing:
        return {'id': existing.pk, 'title': existing.title, 'reused': True}
    # Reuse delivery's version, ownership, history and signature-evidence rules.
    result = mutate_node(project.pk, actor, 'contracts', {
        'key': f'billing-{kind.replace("_", "-")}-{source.pk}',
        'title': source.title,
        field: source.pk,
        'expected_version': data['expected_version'],
        'request_id': data['request_id'],
        'client_visible': False,
    })
    contract = ProjectContract.objects.get(pk=result['result']['id'], project=project)
    return {'id': contract.pk, 'title': contract.title, 'reused': False}
