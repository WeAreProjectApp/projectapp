"""Explicitly register an existing project source for billing, without copying it."""
from datetime import datetime
import re
import unicodedata

from django.db import transaction
from django.db.models import Q

from accounts.models import ProjectContract
from accounts.services.billing_access import billing_project, invalid, require_billing_admin
from accounts.services.delivery_workflow import mutate_node
from content.models import Document, DocumentFolder, ProposalDocument


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


def normalize_source_search(value):
    """Same substring normalization as the panel: accents/case/underscores."""
    value = unicodedata.normalize('NFD', value)
    value = ''.join(char for char in value if not unicodedata.category(char).startswith('M'))
    # Unicode White_Space plus BOM; identical to the panel's search rule.
    return re.sub(
        r'[_\u0009-\u000d\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+',
        ' ', value.lower(),
    ).strip(' ')


def filter_contract_source_options(options, query=''):
    needle = normalize_source_search(query)
    return [row for row in options if needle in normalize_source_search(row['title'])]


def _source_folder_paths(documents):
    """Load only source folders and ancestors, in batches rather than per row."""
    folders = {}
    pending = {row.folder_id for row in documents if row.folder_id}
    while pending:
        batch = DocumentFolder.objects.filter(pk__in=pending).values_list('id', 'name', 'parent_id')
        parents = set()
        for folder_id, name, parent_id in batch:
            folders[folder_id] = (name, parent_id)
            if parent_id:
                parents.add(parent_id)
        pending = parents - folders.keys()
    paths = {}
    for folder_id in {row.folder_id for row in documents if row.folder_id}:
        parts, seen = [], set()
        current = folder_id
        while current in folders and current not in seen:
            seen.add(current)
            name, current = folders[current]
            parts.append(name)
        paths[folder_id] = ' / '.join(reversed(parts))
    return paths


def contract_source_options(project):
    documents, proposals = contract_sources(project)
    documents = list(documents.select_related('document_type').only(
        'id', 'title', 'created_at', 'folder_id', 'document_type__code',
    ))
    proposals = proposals.select_related('proposal').only('id', 'title', 'created_at', 'document_type', 'proposal__title')
    paths = _source_folder_paths(documents)
    options = []
    contract_types = ProposalDocument.CONTRACT_DOC_TYPES | {'amendment'}
    for kind, label, rows in (
        ('document', 'Documento del proyecto', documents),
        ('proposal_document', 'Contrato de propuesta', proposals),
    ):
        for row in rows:
            document_type = (row.document_type.code if row.document_type else '') if kind == 'document' else row.document_type
            words = set(re.findall(r'\w+', normalize_source_search(row.title)))
            options.append({
                'source_type': kind, 'id': row.pk, 'title': row.title, 'origin_label': label,
                'created_at': row.created_at.isoformat(),
                'folder_path': paths.get(row.folder_id, '') if kind == 'document' else '',
                'proposal_title': row.proposal.title if kind == 'proposal_document' else '',
                'is_contract_like': document_type in contract_types or bool(
                    words & {'contrato', 'contract', 'otrosi', 'amendment'}
                ),
            })
    return sorted(options, key=lambda row: (
        not row['is_contract_like'], -datetime.fromisoformat(row['created_at']).timestamp(),
        -row['id'], row['source_type'],
    ))


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
