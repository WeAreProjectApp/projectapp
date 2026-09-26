"""
Standalone branded email endpoints — send, defaults, history.

These endpoints are NOT tied to a specific proposal. They allow the admin
to send generic branded emails to any recipient, similar to how the
Documents module works for PDF documents.
"""
import json
import mimetypes
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import Document, EmailLog
from content.views.history_pagination import email_body_response

_ALLOWED_EXT = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg'}
_MAX_FILE = 15 * 1024 * 1024  # 15 MB
_TEMPLATE_KEY = 'branded_email'


def _parse_sections_field(raw_sections):
    """Parse a request ``sections`` field (JSON string or list).

    Returns ``(sections, error_message)`` where ``sections`` is the
    normalized ``[{'text', 'markdown'}]`` list. Accepts the legacy
    plain-string shape and the new ``{text, markdown}`` dicts.
    """
    from content.services.email_markdown import normalize_sections

    try:
        sections = json.loads(raw_sections) if isinstance(raw_sections, str) else raw_sections
    except (json.JSONDecodeError, TypeError):
        return None, 'Las secciones deben ser un JSON válido.'
    if sections is None:
        sections = []
    if not isinstance(sections, list):
        return None, 'Las secciones deben ser un JSON válido.'
    return normalize_sections(sections), None


def _parse_standalone_email(request):
    """Validate and parse a standalone composed-email request.

    Returns ``(parsed_data, None)`` on success or ``(None, Response)`` on error.
    """
    # ── Rate limit: 1 email per minute for standalone ──
    one_min_ago = timezone.now() - timedelta(minutes=1)
    if EmailLog.objects.filter(
        proposal__isnull=True, template_key=_TEMPLATE_KEY,
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
        sent_at__gte=one_min_ago,
    ).exists():
        return None, Response(
            {'error': 'Espera al menos 1 minuto entre envíos.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # ── Required text fields ──
    from content.services.email_recipient_service import (
        EmailRecipientValidationError,
        parse_email_recipients,
    )

    try:
        recipient_emails, cc_emails = parse_email_recipients(request.data)
    except EmailRecipientValidationError as exc:
        return None, Response(
            {'error': str(exc), 'code': exc.code, 'field': exc.field},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subject = (request.data.get('subject') or '').strip()
    if not subject:
        return None, Response(
            {'error': 'El asunto es obligatorio.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    greeting = (request.data.get('greeting') or '').strip()
    footer = (request.data.get('footer') or '').strip()

    # ── Sections (JSON-encoded string in multipart) ──
    sections, sections_error = _parse_sections_field(request.data.get('sections', '[]'))
    if sections_error:
        return None, Response(
            {'error': sections_error},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not sections:
        return None, Response(
            {'error': 'Debe incluir al menos una sección con contenido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── File attachments ──
    attachments = []
    attachment_sources = []
    for f in request.FILES.getlist('attachments'):
        ext = Path(f.name).suffix.lower()
        if ext not in _ALLOWED_EXT:
            return None, Response(
                {'error': f'Tipo de archivo {ext} no permitido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if f.size > _MAX_FILE:
            return None, Response(
                {'error': f'El archivo "{f.name}" excede el límite de 15 MB.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mime_type = mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        attachments.append((f.name, f.read(), mime_type))
        attachment_sources.append({})

    # ── Document references (PDFs generated server-side) ──
    raw_doc_ids = request.data.get('document_ids', '[]')
    try:
        document_ids = json.loads(raw_doc_ids) if isinstance(raw_doc_ids, str) else raw_doc_ids
    except (json.JSONDecodeError, TypeError):
        return None, Response(
            {'error': 'document_ids debe ser JSON válido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(document_ids, list):
        document_ids = []
    document_ids = [int(d) for d in document_ids if isinstance(d, (int, str)) and str(d).isdigit()]

    document_targets = []
    if document_ids:
        from content.services.document_content import resolve_blocks
        from content.services.document_pdf_service import DocumentPdfService
        documents = Document.objects.filter(pk__in=document_ids)
        for doc in documents:
            if doc.is_contract_mirror:
                # The contract window stores no text: attach the contract itself,
                # the same draft the panel downloads.
                from content.services.contract_mirror_service import mirror_pdf
                pdf_bytes = mirror_pdf()
            else:
                # `resolve_blocks` y no `content_json['blocks']`: un documento
                # cuyo writer se saltó el parseo se descarga bien desde el panel
                # y desaparecía del correo sin avisar. Mismo criterio que la
                # vista de descarga (`views/document.py`).
                if not resolve_blocks(doc):
                    continue
                pdf_bytes = DocumentPdfService.generate(doc)
            if not pdf_bytes:
                continue
            filename = f'{doc.title or f"documento-{doc.pk}"}.pdf'
            attachments.append((filename, pdf_bytes, 'application/pdf'))
            attachment_sources.append({
                'document_id': doc.pk,
                'business_kind': (
                    doc.document_type.code if doc.document_type else 'document'
                ),
                'business_kind_label': (
                    doc.document_type.name if doc.document_type else 'Documento'
                ),
            })
            document_targets.append({
                'entity_type': 'document',
                'object_id': doc.pk,
                'object_repr': doc.title,
            })

    return {
        'recipient_emails': recipient_emails,
        'cc_emails': cc_emails,
        'subject': subject,
        'greeting': greeting,
        'sections': sections,
        'footer': footer,
        'attachments': attachments or None,
        'attachment_sources': attachment_sources,
        'document_targets': document_targets,
    }, None


@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_standalone_email(request):
    """Send a standalone branded email (not tied to any proposal)."""
    parsed, error_response = _parse_standalone_email(request)
    if error_response:
        return error_response

    from content.services.proposal_email_service import ProposalEmailService
    sent, logs = ProposalEmailService.send_standalone_branded_email(
        recipient_emails=parsed['recipient_emails'],
        cc_emails=parsed['cc_emails'],
        subject=parsed['subject'],
        greeting=parsed['greeting'],
        sections=parsed['sections'],
        footer=parsed['footer'],
        attachments=parsed['attachments'],
        attachment_sources=parsed['attachment_sources'],
        targets=parsed['document_targets'],
        return_logs=True,
    )

    if sent:
        return Response(
            {
                'message': (
                    f'Correo enviado a {len(parsed["recipient_emails"])} '
                    f'destinatario(s) con {len(parsed["cc_emails"])} CC.'
                ),
                'email_log_id': logs[0].pk if logs else None,
                'delivery_id': str(logs[0].delivery_id) if logs else None,
                'recipient_emails': parsed['recipient_emails'],
                'cc_emails': parsed['cc_emails'],
                'document_ids': [
                    target['object_id'] for target in parsed['document_targets']
                ],
                'offer_sent_transition': bool(parsed['document_targets']),
            },
            status=status.HTTP_200_OK,
        )
    return Response(
        {'error': 'Error al enviar el correo. Intenta de nuevo.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def preview_composed_email(request):
    """Render the branded email HTML exactly as the send path would.

    Feeds the composers' "Vista previa" iframe: no email is sent, nothing
    is logged in ``EmailLog`` and the send rate limit does not apply.
    Accepts an optional ``proposal_id`` so the proposal composer's preview
    resolves the same signature as its send path.
    """
    subject = (request.data.get('subject') or '').strip()
    greeting = (request.data.get('greeting') or '').strip()
    footer = (request.data.get('footer') or '').strip()

    sections, sections_error = _parse_sections_field(request.data.get('sections', []))
    if sections_error:
        return Response(
            {'error': sections_error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    attachment_names = request.data.get('attachment_names') or []
    if not isinstance(attachment_names, list):
        attachment_names = []
    attachment_names = [n.strip() for n in attachment_names if isinstance(n, str) and n.strip()]

    proposal = None
    proposal_id = request.data.get('proposal_id')
    if proposal_id:
        from content.models import BusinessProposal
        proposal = BusinessProposal.objects.filter(pk=proposal_id).first()

    from content.services.proposal_email_service import ProposalEmailService
    html_content, _ = ProposalEmailService.render_composed_email(
        _TEMPLATE_KEY, proposal, subject, greeting,
        sections, footer, attachment_names,
    )
    return Response(
        {'subject': subject, 'html_preview': html_content},
        status=status.HTTP_200_OK,
    )


def _available_signers():
    """Return the signers configured in settings as ``[{key, name, role}]``."""
    signatures = getattr(settings, 'EMAIL_SIGNATURES', {}) or {}
    return [
        {'key': key, 'name': sig.get('name', ''), 'role': sig.get('role', '')}
        for key, sig in signatures.items()
    ]


def _defaults_payload():
    """Build the standalone composer defaults payload (GET/PUT response).

    Top-level ``greeting``/``footer`` keep the historical shape consumed by
    the composer (overrides merged over defaults, variables substituted).
    ``config`` carries the raw editable values for the defaults form and
    ``defaults`` the registry/settings values used by "restore defaults".
    """
    from content.models import EmailTemplateConfig
    from content.services.email_template_registry import (
        get_default_field_values, get_template_entry,
    )
    from content.services.proposal_email_service import ProposalEmailService

    config = EmailTemplateConfig.objects.filter(template_key=_TEMPLATE_KEY).first()
    overrides = (config.content_overrides if config else {}) or {}
    defaults = get_default_field_values(_TEMPLATE_KEY)
    default_signer = getattr(settings, 'EMAIL_DEFAULT_SIGNER', 'gustavo')
    entry = get_template_entry(_TEMPLATE_KEY) or {}

    context = {'client_name': '', 'title': ''}
    field_values = ProposalEmailService._resolve_content(_TEMPLATE_KEY, context)

    return {
        **field_values,
        'config': {
            'greeting': overrides.get('greeting') or defaults.get('greeting', ''),
            'footer': overrides.get('footer') or defaults.get('footer', ''),
            'signer': overrides.get('signer') or default_signer,
        },
        'defaults': {
            'greeting': defaults.get('greeting', ''),
            'footer': defaults.get('footer', ''),
            'signer': default_signer,
        },
        'is_customized': bool(overrides),
        'available_signers': _available_signers(),
        'available_variables': entry.get('available_variables', []),
    }


@api_view(['GET', 'PUT'])
@permission_classes([IsAdminUser])
def standalone_email_defaults(request):
    """GET/PUT admin-configurable defaults for the standalone email composer.

    PUT stores ``greeting``/``footer``/``signer`` as ``content_overrides`` on
    the ``branded_email`` template config. Values that are empty or equal to
    the registry/settings default are dropped, so submitting the defaults (or
    blanks) restores the original behavior.
    """
    if request.method == 'GET':
        return Response(_defaults_payload(), status=status.HTTP_200_OK)

    from content.models import EmailTemplateConfig
    from content.services.email_template_registry import get_default_field_values

    greeting = (request.data.get('greeting') or '').strip()
    footer = (request.data.get('footer') or '').strip()
    signer = (request.data.get('signer') or '').strip()

    signatures = getattr(settings, 'EMAIL_SIGNATURES', {}) or {}
    if signer and signer not in signatures:
        return Response(
            {'error': 'El firmante seleccionado no es válido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    defaults = get_default_field_values(_TEMPLATE_KEY)
    default_signer = getattr(settings, 'EMAIL_DEFAULT_SIGNER', 'gustavo')

    overrides = {}
    if greeting and greeting != defaults.get('greeting'):
        overrides['greeting'] = greeting
    if footer and footer != defaults.get('footer'):
        overrides['footer'] = footer
    if signer and signer != default_signer:
        overrides['signer'] = signer

    config = EmailTemplateConfig.objects.filter(template_key=_TEMPLATE_KEY).first()
    if config:
        config.content_overrides = overrides
        config.save(update_fields=['content_overrides', 'updated_at'])
    elif overrides:
        EmailTemplateConfig.objects.create(
            template_key=_TEMPLATE_KEY,
            content_overrides=overrides,
        )

    return Response(_defaults_payload(), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_standalone_emails(request):
    """List email history, with ``scope=all`` for the global delivery log.

    The default remains the historical standalone-only scope for API
    compatibility. The Emails panel explicitly requests the global scope.
    """
    from content.services.email_history_service import (
        apply_attachment_filters,
        attachment_type_options,
        history_queryset,
        snapshot_payload,
    )

    logs = history_queryset()
    if request.query_params.get('scope') != 'all':
        logs = logs.filter(
            proposal__isnull=True,
            template_key=_TEMPLATE_KEY,
        )

    from content.email_copy_families import EMAIL_COPY_FAMILY_CHOICES
    from content.services.outbound_email_inventory import (
        OUTBOUND_EMAIL_CHANNELS,
        outbound_email_family,
    )

    family = (request.query_params.get('family') or '').strip()
    if family:
        family_keys = [
            key for key, value in OUTBOUND_EMAIL_CHANNELS.items()
            if value == family
        ]
        logs = logs.filter(template_key__in=family_keys)
    template_key = (request.query_params.get('template_key') or '').strip()
    if template_key:
        logs = logs.filter(template_key=template_key)
    email_status = (request.query_params.get('status') or '').strip()
    recipient = (request.query_params.get('recipient') or '').strip()
    date_from = parse_date(request.query_params.get('date_from') or '')
    date_to = parse_date(request.query_params.get('date_to') or '')
    if date_from:
        logs = logs.filter(sent_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(sent_at__date__lte=date_to)
    email_id = (request.query_params.get('email_id') or '').strip()
    logs = apply_attachment_filters(logs, request.query_params)

    from content.services.email_log_service import (
        attach_delivery_copies,
        attach_delivery_recipients,
        delivery_copy_payloads,
        delivery_recipient_payloads,
        filter_delivery_log_id,
        filter_delivery_recipient,
        filter_delivery_status,
        representative_delivery_queryset,
    )

    logs = filter_delivery_recipient(logs, recipient)
    if email_status in EmailLog.Status.values:
        logs = filter_delivery_status(logs, email_status)
    if email_id.isdigit():
        logs = filter_delivery_log_id(logs, int(email_id))
    logs = representative_delivery_queryset(logs)

    total = logs.count()
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    page_size = 20
    offset = (page - 1) * page_size

    from content.serializers.client_emails import ClientEmailLogSerializer

    page_logs = attach_delivery_recipients(
        attach_delivery_copies(logs[offset:offset + page_size]),
    )
    family_labels = dict(EMAIL_COPY_FAMILY_CHOICES)
    data = []
    for log in page_logs:
        data.append({
            'id': log.pk,
            'delivery_id': str(log.delivery_id) if log.delivery_id else None,
            'template_key': log.template_key,
            'template_label': ClientEmailLogSerializer().get_template_label(log),
            'family': outbound_email_family(log.template_key),
            'family_label': family_labels.get(
                outbound_email_family(log.template_key),
                'Sin familia',
            ),
            'recipient': log.recipient,
            'subject': log.subject,
            'status': log.status,
            'status_label': log.get_status_display(),
            'audience': log.audience,
            'audience_label': log.get_audience_display(),
            'sent_at': log.sent_at.isoformat(),
            'metadata': log.metadata,
            'has_body': log.body_id is not None,
            'copies': delivery_copy_payloads(log),
            **delivery_recipient_payloads(log),
            **snapshot_payload(log),
        })
    return Response({
        'results': data,
        'total': total,
        'page': page,
        'page_size': page_size,
        'has_next': offset + page_size < total,
        'attachment_type_options': attachment_type_options(),
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def standalone_email_body(request, log_id):
    """Return the retained body for any primary outbound email."""
    log = get_object_or_404(
        EmailLog.objects.select_related('body').filter(
            delivery_role=EmailLog.DeliveryRole.PRIMARY,
        ),
        pk=log_id,
    )
    return email_body_response(log)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def standalone_email_attachment(request, log_id, attachment_id):
    """Stream retained bytes only through an authorized history record."""
    from content.models import EmailAttachmentSnapshot

    log = get_object_or_404(
        EmailLog.objects.filter(
            delivery_role=EmailLog.DeliveryRole.PRIMARY,
        ),
        pk=log_id,
    )
    attachment = get_object_or_404(
        EmailAttachmentSnapshot.objects.select_related('snapshot'),
        pk=attachment_id,
        snapshot_id=log.snapshot_id,
    )
    inline = (
        request.query_params.get('inline') == '1'
        and attachment.format_kind == EmailAttachmentSnapshot.FormatKind.PDF
    )
    response = FileResponse(
        attachment.file.open('rb'),
        as_attachment=not inline,
        filename=attachment.filename,
        content_type=(
            'application/pdf'
            if inline else (attachment.mime_type or 'application/octet-stream')
        ),
    )
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    if inline:
        response['X-Frame-Options'] = 'SAMEORIGIN'
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
def resend_standalone_email(request, log_id):
    """Resend exact retained content; only the destination may change."""
    from content.services.email_recipient_service import (
        EmailRecipientValidationError,
        parse_email_recipients,
    )

    try:
        recipients, cc_recipients = parse_email_recipients(
            request.data,
            legacy_to_fields=('recipient', 'recipient_email'),
        )
    except EmailRecipientValidationError as exc:
        return Response(
            {
                'detail': str(exc),
                'code': exc.code,
                'field': exc.field,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    log = get_object_or_404(
        EmailLog.objects.filter(
            delivery_role=EmailLog.DeliveryRole.PRIMARY,
        ).select_related(
            'snapshot__body', 'proposal', 'client',
        ).prefetch_related(
            'targets', 'snapshot__attachments__source_document',
        ),
        pk=log_id,
    )
    if not log.snapshot_id:
        return Response(
            {
                'detail': 'Este correo es anterior al archivo exacto y no se puede reenviar.',
                'code': 'email_snapshot_unavailable',
            },
            status=status.HTTP_409_CONFLICT,
        )

    from content.services.email_snapshot_service import (
        EmailSnapshotCaptureError,
        EmailSnapshotResendError,
        resend_email_log,
    )
    try:
        resent_log = resend_email_log(log, recipients, cc_recipients)
    except EmailSnapshotCaptureError as exc:
        return Response(
            {'detail': str(exc), 'code': 'email_snapshot_capture_failed'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except EmailSnapshotResendError as exc:
        return Response(
            {'detail': str(exc), 'code': 'email_resend_failed'},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response({
        'message': (
            f'Correo reenviado a {len(recipients)} destinatario(s) '
            f'con {len(cc_recipients)} CC.'
        ),
        'email_log_id': resent_log.pk,
        'delivery_id': str(resent_log.delivery_id),
        'resend_of_email_log_id': log.pk,
        'recipient_emails': recipients,
        'cc_emails': cc_recipients,
        'copy_notice': (
            'Las copias BCC configuradas se intentaron después del envío principal.'
        ),
    })
