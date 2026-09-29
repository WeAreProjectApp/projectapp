"""Prepare once, review exact bytes, then deliver one private formal package."""
from datetime import timedelta
import hashlib
import json
import logging
import mimetypes

from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import get_template
from django.utils import timezone

from content.models import BusinessProposal, ProposalFormalization, ProposalFormalizationFile
from content.services import contract_variants
from content.services.email_delivery_service import EmailDeliveryGateway, EmailMultiAlternatives
from content.services.email_recipient_service import recipient_log_contexts
from content.services.email_snapshot_service import EmailSnapshotCaptureError
from content.services.formalization_content import FormalContent, FormalizationError
from content.services.formalization_pdf import generate_formal_pdf
from content.services.pdf_utils import safe_pdf_filename
from content.services.proposal_email_service import ProposalEmailService, _build_design_context

logger = logging.getLogger(__name__)
TEMPLATE_KEY = 'proposal_formalization'
MAX_ATTACHMENT_BYTES = 18 * 1024 * 1024
# A contract key is the stored document type of its variant; the deal's
# closing modality decides which ones a package may carry.
CONTRACT_KEYS = contract_variants.DOC_TYPE_VARIANTS
DOCUMENTS = {
    **{
        spec.doc_type: (spec.label, spec.description)
        for spec in contract_variants.VARIANTS.values()
    },
    'commercial': ('Propuesta comercial formal', 'Alcance, entregables y condiciones económicas del proyecto.'),
    'technical': ('Detalle técnico formal', 'Especificaciones y criterios verificables del alcance incluido.'),
}
MISSING_CONTRACT_NAMES = {
    contract_variants.COMBINED: 'el contrato final',
    contract_variants.PRODUCT: 'el contrato de producto',
    contract_variants.SERVICE: 'el contrato de servicio',
}
SOURCE_FIELDS = (
    'title', 'client_name', 'client_email', 'client_id', 'language', 'currency',
    'total_investment', 'selected_modules', 'contract_params',
    'hosting_percent', 'email_signed_by',
)
# Fingerprint version 3 also covers the closing modality.
SOURCE_VERSION = 3
# A switch of modality leaves a prepared package pointing at documents that
# are no longer the deal's contracts; that is a stale preparation.
STALE_CONTRACT_CODES = ('contract_missing', 'modality_mismatch')


def document_keys(proposal):
    """Attachable documents for the proposal's closing modality, in order."""
    contracts = [
        contract_variants.VARIANTS[variant].doc_type
        for variant in contract_variants.active_variants(proposal)
    ]
    return [*contracts, 'commercial', 'technical']


def load_proposal(pk):
    return BusinessProposal.objects.prefetch_related('sections').select_related('client').get(pk=pk)


def defaults(proposal):
    resolved = ProposalEmailService._resolve_content(TEMPLATE_KEY, {
        'client_name': proposal.client_name, 'title': proposal.title,
    })
    return {key: resolved.get(key, '') for key in ('subject', 'greeting', 'body', 'footer')}


def read_document(doc):
    try:
        with doc.file.open('rb') as source:
            data = source.read(MAX_ATTACHMENT_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise FormalizationError(f'No se puede leer el documento: {doc.title}.', 'document_unavailable') from exc
    if not data:
        raise FormalizationError(f'El documento {doc.title} está vacío.', 'document_empty')
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise FormalizationError('Los adjuntos superan el límite de 18 MB.', 'attachments_too_large')
    return data


def contract_attachments(proposal, keys):
    """The stored contract documents behind *keys*, in order, validated for sending."""
    active_keys = document_keys(proposal)
    result = []
    for key in keys:
        variant = CONTRACT_KEYS.get(key)
        if variant is None:
            continue
        if key not in active_keys:
            raise FormalizationError(
                'Ese contrato no corresponde a la modalidad de cierre elegida. Prepara nuevamente el correo.',
                'modality_mismatch',
            )
        contract = contract_variants.contract_document(proposal, variant)
        if not contract:
            raise FormalizationError(f'Genera {MISSING_CONTRACT_NAMES[variant]} desde Documentos.', 'contract_missing')
        missing = contract_variants.missing_final_params(proposal.contract_params, variant)
        if missing:
            raise FormalizationError('Completa los parámetros del contrato final: ' + ', '.join(missing) + '.', 'contract_incomplete')
        result.append((key, contract))
    return result


def related_documents(proposal, payload):
    requested = payload.get('additional_doc_ids', [])
    found = {doc.pk: doc for doc in proposal.proposal_documents.filter(pk__in=requested)}
    if set(requested) != set(found):
        raise FormalizationError('Uno de los adjuntos no pertenece a esta propuesta o fue eliminado.', 'invalid_attachment')
    extras = [(f'additional-{pk}', found[pk]) for pk in requested]
    contracts = contract_attachments(proposal, payload.get('documents', []))
    if any(doc.document_type in contract_variants.CONTRACT_DOC_TYPES for _key, doc in extras):
        raise FormalizationError('Selecciona el contrato mediante su casilla principal.', 'duplicate_contract')
    return contracts + extras


def source_hash(proposal, payload):
    # Existing preparations retain their original fingerprint and frozen bytes.
    # New layouts use section titles, so only version 2 fingerprints include them.
    section_fields = ('section_type', 'content_json', 'is_enabled', 'order')
    if payload.get('_source_version', 1) >= 2:
        section_fields += ('title',)
    proposal_fields = SOURCE_FIELDS
    if payload.get('_source_version', 1) >= 3:
        proposal_fields += ('contract_modality',)
    document_sources = []
    for key, doc in related_documents(proposal, payload):
        document_sources.append([key, doc.pk, doc.title, doc.file.name, hashlib.sha256(read_document(doc)).hexdigest()])
    sources = {
        'proposal': {field: getattr(proposal, field) for field in proposal_fields},
        'confirmed_selection': proposal.has_confirmed_module_selection,
        'sections': [
            {field: getattr(section, field) for field in section_fields}
            for section in proposal.sections.all()
        ],
        'files': document_sources,
        'signature': _build_design_context(proposal),
        'template_html': get_template('emails/proposal_formalization.html').template.source,
        'template_text': get_template('emails/proposal_formalization.txt').template.source,
    }
    return hashlib.sha256(json.dumps(sources, sort_keys=True, default=str).encode()).hexdigest()


def document_bytes(proposal, kind, *, issued_at=None, reference=None, content=None):
    issued_at = issued_at or timezone.now()
    if kind not in DOCUMENTS:
        raise FormalizationError('Tipo de documento inválido.', 'invalid_document')
    if kind in CONTRACT_KEYS:
        doc = contract_attachments(proposal, [kind])[0][1]
        data = read_document(doc)
        if not data.startswith(b'%PDF-'):
            raise FormalizationError('El contrato guardado no es un PDF válido.', 'invalid_contract')
        return data
    return generate_formal_pdf(content or FormalContent(proposal), kind, issued_at, reference or f'PROP-{proposal.pk}')


def availability(proposal):
    content = FormalContent(proposal)
    result = []
    for key in document_keys(proposal):
        label, description = DOCUMENTS[key]
        error = ''
        try:
            if key in CONTRACT_KEYS:
                document_bytes(proposal, key)
            elif key == 'commercial':
                content.commercial()
            else:
                content.technical()
        except FormalizationError as exc:
            error = str(exc)
        result.append({'key': key, 'label': label, 'description': description, 'available': not error, 'error': error})
    return result


def prepare(proposal, user, payload, *, mcp_credential=None):
    if not ProposalEmailService._is_template_active(TEMPLATE_KEY):
        raise FormalizationError('La plantilla de formalización está desactivada.', 'template_disabled')
    payload = {**payload, '_source_version': SOURCE_VERSION}
    captured_hash = source_hash(proposal, payload)
    now = timezone.now()
    preparation = ProposalFormalization(proposal=proposal, created_by=user, mcp_credential=mcp_credential, payload=payload, source_hash=captured_hash, expires_at=now + timedelta(hours=24))
    reference = f'PROP-{proposal.pk} / {str(preparation.id)[:8]}'
    content = FormalContent(proposal)
    attachments = []

    def append_attachment(key, name, description, mime, data):
        # Reject as soon as the cumulative budget is exceeded, before loading more files.
        if sum(len(item[4]) for item in attachments) + len(data) > MAX_ATTACHMENT_BYTES:
            raise FormalizationError('Los adjuntos superan el límite de 18 MB.', 'attachments_too_large')
        attachments.append((key, name, description, mime, data))

    for key in payload['documents']:
        data = document_bytes(proposal, key, issued_at=now, reference=reference, content=content)
        label, description = DOCUMENTS[key]
        name = safe_pdf_filename(label, proposal.title, now.strftime('%Y-%m-%d'))
        append_attachment(key, name, description, 'application/pdf', data)
    for key, doc in related_documents(proposal, payload):
        if key in CONTRACT_KEYS:
            continue
        name = doc.file.name.rsplit('/', 1)[-1]
        append_attachment(key, name, doc.title, mimetypes.guess_type(name)[0] or 'application/octet-stream', read_document(doc))
    if captured_hash != source_hash(load_proposal(proposal.pk), payload):
        raise FormalizationError('La propuesta cambió durante la preparación. Vuelve a preparar el correo.', 'stale_preparation', 409)
    descriptions = '\n'.join(f'{name} — {description}' for _, name, description, _, _ in attachments)
    sections = [{'text': payload['body'], 'markdown': False}, {'text': 'Documentos adjuntos:\n' + descriptions, 'markdown': False}, *payload['sections']]
    preparation.html_body, preparation.text_body = ProposalEmailService.render_composed_email(
        TEMPLATE_KEY, proposal, payload['subject'], payload['greeting'], sections, payload['footer'],
    )
    preparation.payload = {**payload, 'from_email': ProposalEmailService._get_from_email()}
    written_files = []
    try:
        with transaction.atomic():
            preparation.save()
            for key, name, description, mime, data in attachments:
                item = ProposalFormalizationFile(preparation=preparation, key=key, filename=name, description=description, mime_type=mime, sha256=hashlib.sha256(data).hexdigest(), size=len(data))
                item.file.save(name, ContentFile(data), save=False)
                written_files.append((item.file.storage, item.file.name))
                item.save()
    except Exception:
        for storage, path in written_files:
            storage.delete(path)
        raise
    return preparation


def check_current(preparation):
    if preparation.expires_at <= timezone.now():
        raise FormalizationError('La preparación venció. Prepara nuevamente el correo.', 'expired_preparation', 410)
    stale = FormalizationError('Los datos de origen cambiaron. Prepara y revisa nuevamente el correo.', 'stale_preparation', 409)
    try:
        current = source_hash(load_proposal(preparation.proposal_id), preparation.payload)
    except FormalizationError as exc:
        if exc.code in STALE_CONTRACT_CODES:
            raise stale from exc
        raise
    if preparation.source_hash != current:
        raise stale


def send_preparation(preparation):
    check_current(preparation)
    if not ProposalEmailService._is_template_active(TEMPLATE_KEY):
        raise FormalizationError('La plantilla de formalización está desactivada.', 'template_disabled')
    data = preparation.payload
    message = EmailMultiAlternatives(subject=data['subject'], body=preparation.text_body, from_email=data['from_email'], to=data['recipient_emails'], cc=data['cc_emails'])
    message.attach_alternative(preparation.html_body, 'text/html')
    sources = []
    for attachment in preparation.files.all():
        try:
            with attachment.file.open('rb') as stored:
                raw = stored.read(MAX_ATTACHMENT_BYTES + 1)
        except (OSError, ValueError) as exc:
            raise FormalizationError('Un adjunto ya no está disponible. Prepara nuevamente el correo.', 'attachment_changed', 409) from exc
        if hashlib.sha256(raw).hexdigest() != attachment.sha256:
            raise FormalizationError('Un adjunto cambió. Prepara nuevamente el correo.', 'attachment_changed', 409)
        message.attach(attachment.filename, raw, attachment.mime_type)
        sources.append({'business_kind': f'formalization_{attachment.key.split("-")[0]}', 'business_kind_label': attachment.description})
    claimed = ProposalFormalization.objects.filter(pk=preparation.pk, status='prepared', expires_at__gt=timezone.now()).update(status='sending')
    if not claimed:
        raise FormalizationError('Esta preparación ya fue enviada o tiene un envío en curso. Consulta el historial.', 'preparation_consumed', 409)
    delivery_status = 'unknown'
    error = ''
    try:
        accepted = EmailDeliveryGateway.send(message, template_key=TEMPLATE_KEY, attachment_sources=sources)
        delivery_status = 'sent' if accepted else 'failed'
        if not accepted:
            error = 'El servicio de correo no aceptó el envío. Consulta el historial antes de preparar otro.'
    except EmailSnapshotCaptureError:
        delivery_status = 'failed'
        error = 'No se pudo guardar la evidencia del envío; el correo no fue enviado.'
        logger.exception('Formalization snapshot failed for %s', preparation.pk)
    except Exception:
        error = 'No se pudo confirmar la entrega. Consulta el historial antes de preparar otro envío.'
        logger.exception('Formalization delivery uncertain for %s', preparation.pk)
    ProposalFormalization.objects.filter(pk=preparation.pk).update(status=delivery_status, sent_at=timezone.now() if delivery_status == 'sent' else None, error=error)
    proposal = preparation.proposal
    ProposalEmailService._log_email(
        TEMPLATE_KEY, recipients=data['recipient_emails'] + data['cc_emails'],
        recipient_contexts=recipient_log_contexts(data['recipient_emails'], data['cc_emails'], contextual_client=proposal.client),
        subject=data['subject'], proposal=proposal, status='sent' if delivery_status == 'sent' else 'failed',
        error_message=error, html_body=preparation.html_body, text_body=preparation.text_body,
        metadata={'formalization_id': str(preparation.pk), 'delivery_status': delivery_status},
    )
    preparation.refresh_from_db()
    return preparation


def cleanup_expired():
    # Delivery snapshots already own their own copies; expiration only removes preparations.
    count = 0
    # Give an already claimed send time to finish across the expiry boundary.
    now = timezone.now()
    ProposalFormalization.objects.filter(expires_at__lte=now - timedelta(hours=1), status='sending').update(
        status='unknown', error='La entrega no se confirmó antes del vencimiento.',
    )
    for preparation in ProposalFormalization.objects.filter(expires_at__lte=now).exclude(status='sending').iterator(chunk_size=100):
        preparation.delete()
        count += 1
    return count
