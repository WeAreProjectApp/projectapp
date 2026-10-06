"""Plan, preserve and atomically change a proposal's contracts, never its templates."""
from copy import copy, deepcopy
import hashlib
import json
import logging

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q

from content.models import (
    BusinessProposal, CompanySettings, ContractTemplate, Document, ProposalDocument,
    ProposalContractSnapshot, ProposalContractSnapshotFile,
)
from content.serializers.proposal_contract_modality import ContractModalitySerializer, ContractRestoreSerializer
from content.services import contract_variants as variants
from content.services.entity_history import history_operation, link_evidence
from content.services.proposal_audit import log_proposal_change

logger = logging.getLogger(__name__)
MAX_PDF_BYTES = 18 * 1024 * 1024


class ContractModalityError(ValueError):
    def __init__(self, message, code='VALIDATION_ERROR', status=422, details=None):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details or {}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _read(doc):
    try:
        with doc.file.open('rb') as source:
            data = source.read(MAX_PDF_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise ContractModalityError(f'No se puede conservar el archivo de {doc.title}.', 'FILE_UNAVAILABLE', 409) from exc
    if not data or len(data) > MAX_PDF_BYTES:
        raise ContractModalityError('El contrato está vacío o supera 18 MB.', 'INVALID_CONTRACT_FILE', 409)
    return data


def _documents(proposal):
    """At most three recovery files: the latest stored document of each variant."""
    result = {}
    for doc in proposal.proposal_documents.filter(is_generated=True, document_type__in=variants.CONTRACT_DOC_TYPES).order_by('-updated_at', '-pk'):
        key = variants.DOC_TYPE_VARIANTS[doc.document_type]
        if key not in result:
            result[key] = doc
    return result


def _linked_documents(proposal):
    from content.services.contract_mirror_service import mirror_binding
    # Historical links retain the original row IDs across repeated changes.
    ids = list(proposal.proposal_documents.filter(document_type__in=variants.CONTRACT_DOC_TYPES).values_list('pk', flat=True))
    rows = Document.objects.filter(Q(source_proposal=proposal) | Q(metadata__proposal_id=proposal.pk)
        | Q(metadata__proposal_document_id__in=ids) | Q(metadata__source_proposal_document_id__in=ids)).order_by('pk')
    return [row for row in rows if not mirror_binding(row)]


def resource_hash(proposal):
    docs = _documents(proposal)
    template = ContractTemplate.objects.filter(is_default=True).first()
    company = CompanySettings.objects.first()
    return _hash({
        'proposal': {key: getattr(proposal, key) for key in (
            'id', 'status', 'contract_modality', 'contract_params', 'updated_at', 'title', 'client_id',
            'total_investment', 'currency', 'hosting_percent', 'hosting_discount_nine_month',
            'hosting_discount_semiannual', 'hosting_discount_quarterly', 'selected_modules',
        )},
        'sections': list(proposal.sections.order_by('pk').values('id', 'content_json', 'is_enabled', 'order')),
        'documents': [[key, doc.pk, doc.document_type, doc.title, doc.is_archived, doc.content_markdown,
            hashlib.sha256(_read(doc)).hexdigest()] for key, doc in sorted(docs.items())],
        'linked': [[row.pk, row.updated_at, row.metadata, row.signed_at, row.is_archived, row.content_markdown]
            for row in _linked_documents(proposal)],
        'template': [template.pk, template.updated_at, template.content_markdown,
            template.product_content_markdown, template.service_content_markdown] if template else None,
        'company': [company.pk, company.updated_at] if company else None,
    })


def _validated(serializer):
    if not serializer.is_valid():
        raise ContractModalityError('Revisa los datos del cambio de contrato.', details=serializer.errors)
    return dict(serializer.validated_data)


def _literal(params, key, docs):
    spec = variants.VARIANTS[key]
    doc = docs.get(key)
    text = doc.content_markdown if doc and doc.content_markdown else params.get(spec.custom_key, '')
    if not text.strip():
        raise ContractModalityError('El contrato personalizado no contiene Markdown guardado.', 'CUSTOM_TEXT_MISSING', 409)
    return text


def _restore_snapshot(proposal, snapshot_id):
    snapshot = ProposalContractSnapshot.objects.filter(proposal=proposal, pk=snapshot_id).first()
    if snapshot is None:
        raise ContractModalityError('No existe esa instantánea en esta propuesta.', 'NOT_FOUND', 404)
    return snapshot


def prepare(proposal, arguments, *, restore=False):
    payload = _validated((ContractRestoreSerializer if restore else ContractModalitySerializer)(data=arguments))
    docs = _documents(proposal)
    snapshot = _restore_snapshot(proposal, payload['snapshot_id']) if restore else None
    target = snapshot.from_modality if restore else payload['contract_modality']
    noop = not restore and target == proposal.contract_modality
    note = payload.get('change_note', '')
    if not noop and (restore or proposal.status != 'negotiating') and not note.strip():
        raise ContractModalityError('Escribe una nota para explicar el cambio.', details={'change_note': 'Este dato es obligatorio fuera de negociación.'})
    params = deepcopy(snapshot.payload['contract_params'] if restore else proposal.contract_params or {})
    params.update(payload.get('contract_params', {}))
    actions = []
    if restore:
        actions = [{'variant': row['variant'], 'action': 'restore', 'source': row['source'],
                    'document_id': row['document_id']} for row in snapshot.payload['documents']]
    elif not noop:
        origin, destination = ('combined', 'product') if target == 'split' else ('product', 'combined')
        origin_custom = variants.contract_source(params, origin) == 'custom'
        destination_custom = variants.contract_source(params, destination) == 'custom'
        if origin_custom:
            text = _literal(params, origin, docs)
            if destination_custom and _literal(params, destination, docs) != text and payload.get('conflict_resolution') != 'use_origin':
                raise ContractModalityError('El destino contiene otro contrato personalizado. Conserva una copia y confirma explícitamente el traslado del origen.',
                    'CUSTOM_CONTRACT_CONFLICT', 409, {'conflict_resolution': 'use_origin'})
            params[variants.VARIANTS[destination].source_key] = 'custom'
            params[variants.VARIANTS[destination].custom_key] = text
            actions.append({'variant': destination, 'action': 'move', 'source': 'custom', 'from_variant': origin})
        else:
            if destination_custom and payload.get('conflict_resolution') != 'use_origin':
                raise ContractModalityError('El destino contiene un contrato personalizado. Confirma conservarlo archivado antes de usar la plantilla.',
                    'CUSTOM_CONTRACT_CONFLICT', 409, {'conflict_resolution': 'use_origin'})
            params[variants.VARIANTS[destination].source_key] = 'default'
            actions.append({'variant': destination, 'action': 'create', 'source': 'default'})
        if target == 'split':
            missing = {key: 'Indica este dato del contrato de servicio.' for key in variants.SERVICE_PARAM_KEYS
                       if not str(params.get(key) or '').strip()}
            if missing:
                raise ContractModalityError('Faltan los plazos del contrato de servicio.', details=missing)
            service_custom = variants.contract_source(params, 'service') == 'custom'
            params['service_contract_source'] = 'custom' if service_custom else 'default'
            if service_custom:
                params['service_custom_contract_markdown'] = _literal(params, 'service', docs)
            actions.append({'variant': 'service', 'action': 'reuse' if service_custom else 'create',
                            'source': 'custom' if service_custom else 'default'})
        candidate = copy(proposal)
        candidate.contract_modality, candidate.contract_params = target, params
        for key in variants.MODALITY_VARIANTS[target]:
            missing = variants.missing_generation_params(params, key)
            if missing:
                raise ContractModalityError('Completa los parámetros necesarios para generar el contrato.', details={field: 'Este dato es obligatorio.' for field in missing})
            if variants.contract_source(params, key) == 'default':
                template = ContractTemplate.objects.filter(is_default=True).first()
                if not variants.template_markdown(template, key).strip():
                    raise ContractModalityError('Falta la plantilla de este contrato.', 'TEMPLATE_UNAVAILABLE', 409, {'variant': key})
        if target == 'split' and variants.contract_source(params, 'service') == 'default':
            from content.services.proposal_hosting_terms import ServiceConditionsError, service_conditions_markdown
            try:
                service_conditions_markdown(candidate)
            except ServiceConditionsError as exc:
                raise ContractModalityError(str(exc), 'service_conditions_missing') from exc
    links = _linked_documents(proposal)
    linked_variants = {str(pk): variants.DOC_TYPE_VARIANTS[doc_type]
                       for pk, doc_type in proposal.proposal_documents.filter(document_type__in=variants.CONTRACT_DOC_TYPES).values_list('pk', 'document_type')}
    warnings = []
    if links or proposal.platform_approval_manifest or proposal.email_logs.filter(template_key='proposal_documents_sent').exists():
        warnings.append('Los documentos enviados, aprobados o firmados se conservan. Este cambio no envía documentos ni solicita nuevas firmas.')
    return {
        'arguments': payload, 'contract_modality': target, 'previous_modality': proposal.contract_modality,
        'contract_params': params, 'noop': noop, 'contracts': actions,
        'archive': [{'variant': key, 'document_id': doc.pk} for key, doc in docs.items()
                    if not noop and key not in variants.MODALITY_VARIANTS[target]],
        'linked_documents': [{'document_id': row.pk, 'title': row.title, 'signed': bool(row.signed_at),
            'relationship': 'historical', 'variant': row.metadata.get('contract_variant') or linked_variants.get(str(row.metadata.get('proposal_document_id', row.metadata.get('source_proposal_document_id')))),
            'proposal_document_id': row.metadata.get('proposal_document_id', row.metadata.get('source_proposal_document_id'))}
            for row in links],
        'warnings': warnings, 'source_hash': resource_hash(proposal),
    }


def _capture(proposal, plan, actor, restore):
    docs = _documents(proposal)
    payload = {'contract_modality': proposal.contract_modality, 'contract_params': deepcopy(proposal.contract_params or {}),
        'documents': [{'variant': key, 'document_id': doc.pk, 'document_type': doc.document_type,
            'title': doc.title, 'file_name': doc.file.name, 'markdown': doc.content_markdown,
            'source': variants.contract_source(proposal.contract_params, key), 'is_archived': doc.is_archived}
            for key, doc in docs.items()], 'linked_documents': plan['linked_documents']}
    from content.mcp.context import current_mcp_context
    context = current_mcp_context()
    snapshot = ProposalContractSnapshot.objects.create(proposal=proposal, payload=payload,
        actor_id_snapshot=actor.pk, actor_label=(actor.get_full_name() or actor.username)[:255],
        source=f'mcp:{context.connector.slug}' if context else 'panel', change_note=plan['arguments'].get('change_note', ''),
        from_modality=proposal.contract_modality, to_modality=plan['contract_modality'],
        restored_from_id=plan['arguments'].get('snapshot_id') if restore else None)
    for doc in docs.values():
        pdf = _read(doc)
        ProposalContractSnapshotFile.objects.create(snapshot=snapshot, source_document_id=doc.pk,
            pdf_content=pdf, sha256=hashlib.sha256(pdf).hexdigest())
    return snapshot


def _store(proposal, key, markdown, pdf, written, *, title=None):
    spec = variants.VARIANTS[key]
    doc = ProposalDocument(proposal=proposal, document_type=spec.doc_type, title=title or spec.document_title,
                           is_generated=True, content_markdown=markdown)
    doc.file.save(f'contract-{proposal.pk}-{key}.pdf', ContentFile(pdf), save=False)
    written.append((doc.file.storage, doc.file.name))
    doc.save()
    return doc


def _activate(proposal, plan, written, restore):
    old_docs = _documents(proposal)
    proposal.contract_params, proposal.contract_modality = plan['contract_params'], plan['contract_modality']
    if restore:
        restored = _restore_snapshot(proposal, plan['arguments']['snapshot_id'])
        files = {row.source_document_id: row for row in restored.files.all()}
        for item in restored.payload['documents']:
            pdf = bytes(files[item['document_id']].pdf_content)
            if hashlib.sha256(pdf).hexdigest() != files[item['document_id']].sha256:
                raise ContractModalityError('La instantánea no conserva su huella.', 'SNAPSHOT_CORRUPT', 409)
            doc = _store(proposal, item['variant'], item['markdown'], pdf, written, title=item['title'])
            # Historical rows retain their own archival flag; only prior active variants become active.
            doc.is_archived = item['is_archived'] or item['variant'] not in variants.active_variants(proposal)
            doc.save(update_fields=['is_archived'])
    else:
        from content.services.contract_pdf_service import generate_contract_pdf, resolve_contract_content, _build_params
        for item in plan['contracts']:
            key = item['variant']
            if item['source'] == 'custom':
                source_key = item.get('from_variant', key)
                source = old_docs.get(source_key)
                markdown = plan['contract_params'][variants.VARIANTS[key].custom_key]
                if source:
                    pdf = _read(source)
                else:
                    content = {'source': 'custom', 'params': _build_params(plan['contract_params']),
                               'markdown': markdown, 'snapshot': markdown, 'variant': key}
                    pdf = generate_contract_pdf(proposal, resolved_content=content)
            else:
                content = resolve_contract_content(proposal, variant=key)
                markdown = content['snapshot']
                pdf = generate_contract_pdf(proposal, resolved_content=content)
            if not pdf:
                raise ContractModalityError('No se pudo generar el contrato. No se aplicó el cambio.', 'CONTRACT_GENERATION_FAILED', 409)
            _store(proposal, key, markdown, pdf, written)
    proposal.save(update_fields=['contract_params', 'contract_modality', 'updated_at'])


def result(proposal, *, snapshot=None, plan=None):
    docs = _documents(proposal)
    return {'contract_modality': proposal.contract_modality, 'snapshot_id': snapshot.pk if snapshot else None,
        'contracts': [{'variant': key, 'source': variants.contract_source(proposal.contract_params, key),
            'document_id': docs[key].pk if key in docs else None, 'active': key in variants.active_variants(proposal) and key in docs and not docs[key].is_archived,
            'historical_document_ids': [row['document_id'] for row in (plan or {}).get('linked_documents', [])
                if row['variant'] in {key, next((item.get('from_variant', key) for item in (plan or {}).get('contracts', []) if item['variant'] == key), key)}]}
            for key in variants.VARIANTS],
        'linked_documents': (plan or {}).get('linked_documents', []), 'warnings': (plan or {}).get('warnings', [])}


def apply(proposal_id, arguments, *, actor, confirmed=False, expected_hash=None, restore=False):
    if not actor or not actor.is_active or not actor.is_staff:
        raise ContractModalityError('Esta acción requiere acceso administrativo.', 'FORBIDDEN', 403)
    written = []
    try:
        with history_operation(actor=actor, source='panel'), transaction.atomic():
            proposal = BusinessProposal.objects.select_for_update().get(pk=proposal_id)
            list(proposal.proposal_documents.select_for_update().values_list('pk', flat=True))
            list(proposal.sections.select_for_update().values_list('pk', flat=True))
            # Serialize template edits and linked-document changes while comparing the preview.
            list(ContractTemplate.objects.select_for_update().filter(is_default=True))
            list(CompanySettings.objects.select_for_update().all())
            list(Document.objects.select_for_update().filter(pk__in=[row.pk for row in _linked_documents(proposal)]))
            plan = prepare(proposal, arguments, restore=restore)
            if plan['noop']:
                return proposal, result(proposal, plan=plan)
            if (restore or proposal.status != 'negotiating') and (not confirmed or not expected_hash):
                raise ContractModalityError('Revisa y confirma la vista previa antes de aplicar el cambio.', 'CONFIRMATION_REQUIRED', 409)
            if expected_hash and expected_hash != plan['source_hash']:
                raise ContractModalityError('Los contratos cambiaron desde la vista previa. Revisa nuevamente.', 'STALE_VERSION', 409)
            snapshot = _capture(proposal, plan, actor, restore)
            # Keep every previous row and byte available to delivery and signature evidence.
            proposal.proposal_documents.filter(is_generated=True, document_type__in=variants.CONTRACT_DOC_TYPES).update(is_archived=True)
            _activate(proposal, plan, written, restore)
            log_proposal_change(proposal, 'updated', field_name='contract_modality',
                old_value=snapshot.from_modality, new_value=proposal.contract_modality,
                description=f'{snapshot.actor_label}: {snapshot.from_modality} → {proposal.contract_modality}. '
                    f'{snapshot.change_note} [instantánea {snapshot.pk}]')
            link_evidence('proposal', proposal.pk, f'contract_snapshot:{snapshot.pk}')
            return proposal, result(proposal, snapshot=snapshot, plan=plan)
    except Exception:
        for storage, name in written:
            try:
                storage.delete(name)
            except OSError:
                logger.exception('Could not clean rolled-back contract %s', name)
        raise
