"""Immutable evidence for outbound email deliveries."""

from __future__ import annotations

import hashlib
import logging
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from content.services.email_delivery_service import EmailMultiAlternatives
from content.storage import get_private_storage

logger = logging.getLogger(__name__)

_RAW_URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
_CONTENT_PATH_HINTS = (
    '/proposal', '/propuesta', '/diagnostic', '/document', '/platform',
    '/artifact', '/share', '/public/',
)
_STANDARD_HOSTS = {
    'facebook.com', 'instagram.com', 'linkedin.com', 'wa.me',
    'www.facebook.com', 'www.instagram.com', 'www.linkedin.com',
}


class EmailSnapshotCaptureError(RuntimeError):
    """The immutable evidence could not be retained, so SMTP must not run."""


class EmailSnapshotResendError(RuntimeError):
    """An exact resend was captured but the SMTP delivery failed."""


class _AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._href = None
        self._label = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'a':
            return
        self._href = dict(attrs).get('href')
        self._label = []

    def handle_data(self, data):
        if self._href is not None:
            self._label.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != 'a' or self._href is None:
            return
        self.links.append((self._href, ' '.join(self._label).strip()))
        self._href = None
        self._label = []


def _normalized_url(raw_url):
    url = (raw_url or '').strip().rstrip('.,;:!?)]}')
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ''
    if parsed.scheme.lower() not in {'http', 'https'} or not parsed.netloc:
        return ''
    return url


def _link_group(url):
    from content.models import EmailLinkSnapshot

    parsed = urlsplit(url)
    host = parsed.netloc.lower().split(':', 1)[0]
    path = (parsed.path or '/').lower()
    if parsed.query or any(hint in path for hint in _CONTENT_PATH_HINTS):
        return EmailLinkSnapshot.Group.CONTENT
    if host in _STANDARD_HOSTS:
        return EmailLinkSnapshot.Group.TEMPLATE
    if host in {'projectapp.co', 'www.projectapp.co'} and path in {'', '/'}:
        return EmailLinkSnapshot.Group.TEMPLATE
    return EmailLinkSnapshot.Group.CONTENT


def extract_body_links(text_body='', html_body=''):
    """Return de-duplicated user-facing HTTP(S) links in reading order."""
    candidates = []
    parser = _AnchorParser()
    if html_body:
        try:
            parser.feed(html_body)
        except Exception:
            logger.warning('Could not fully parse email HTML links.', exc_info=True)
        candidates.extend(parser.links)
    for raw_url in _RAW_URL_RE.findall(text_body or ''):
        candidates.append((raw_url, ''))

    seen = set()
    links = []
    for raw_url, label in candidates:
        url = _normalized_url(raw_url)
        if not url or url in seen:
            continue
        seen.add(url)
        links.append({
            'url': url,
            'label': (label or '')[:500],
            'group': _link_group(url),
        })
    return links


def message_bodies(message):
    text_body = str(getattr(message, 'body', '') or '')
    html_body = ''
    for alternative in getattr(message, 'alternatives', ()) or ():
        content = getattr(alternative, 'content', alternative[0])
        mimetype = getattr(alternative, 'mimetype', alternative[1])
        if mimetype == 'text/html':
            html_body = str(content or '')
            break
    return text_body, html_body


def _mime_attachments(mime_message):
    rows = []
    for part in mime_message.walk():
        if part.is_multipart():
            continue
        disposition = (part.get_content_disposition() or '').lower()
        filename = part.get_filename()
        if not filename and disposition != 'attachment':
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            raw_payload = part.get_payload() or ''
            charset = part.get_content_charset() or 'utf-8'
            payload = str(raw_payload).encode(charset, errors='replace')
        rows.append({
            'filename': Path(filename or 'adjunto').name[:255],
            'mime_type': (part.get_content_type() or 'application/octet-stream')[:255],
            'payload': payload,
        })
    return rows


def _format_kind(filename, mime_type):
    from content.models import EmailAttachmentSnapshot

    suffix = Path(filename or '').suffix.lower()
    mime_type = (mime_type or '').lower()
    if suffix == '.pdf' or mime_type == 'application/pdf':
        return EmailAttachmentSnapshot.FormatKind.PDF
    if suffix in {'.doc', '.docx', '.odt'} or 'word' in mime_type:
        return EmailAttachmentSnapshot.FormatKind.WORD
    if suffix in {'.xls', '.xlsx', '.csv', '.ods'} or any(
        token in mime_type for token in ('spreadsheet', 'excel', 'csv')
    ):
        return EmailAttachmentSnapshot.FormatKind.SPREADSHEET
    if mime_type.startswith('image/') or suffix in {
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg',
    }:
        return EmailAttachmentSnapshot.FormatKind.IMAGE
    return EmailAttachmentSnapshot.FormatKind.OTHER


def _inferred_business_kind(template_key, filename):
    normalized = f'{template_key} {filename}'.lower()
    if 'collection_account' in normalized or 'cuenta' in normalized:
        return 'collection_account', 'Cuenta de cobro'
    if 'contract' in normalized or 'contrato' in normalized:
        return 'contract', 'Contrato'
    if 'diagnostic' in normalized or 'diagnóstico' in normalized:
        return 'diagnostic', 'Diagnóstico'
    if 'proposal' in normalized or 'propuesta' in normalized:
        return 'proposal', 'Propuesta'
    if 'guide' in normalized or 'guía' in normalized or 'guia' in normalized:
        return 'platform_guide', 'Guía de plataforma'
    return '', ''


def _attachment_source(source, *, template_key, filename):
    from content.models import Document

    source = source or {}
    document_id = source.get('document_id') or source.get('source_document_id')
    document = None
    document_type_code = ''
    document_type_name = ''
    if document_id:
        document = Document.objects.select_related('document_type').get(pk=document_id)
        if document.document_type:
            document_type_code = document.document_type.code
            document_type_name = document.document_type.name

    business_kind = source.get('business_kind') or document_type_code
    business_label = source.get('business_kind_label') or document_type_name
    if not business_kind:
        business_kind, business_label = _inferred_business_kind(
            template_key, filename,
        )
    return {
        'source_document': document,
        'source_document_type_code': document_type_code,
        'source_document_type_name': document_type_name,
        'business_kind': str(business_kind or '')[:64],
        'business_kind_label': str(business_label or '')[:128],
    }


def capture_delivery_snapshot(
    message,
    *,
    delivery_id,
    template_key,
    classification,
    family,
    attachment_sources=None,
    resend_of=None,
    private_attachments=False,
):
    """Persist exact evidence before SMTP; private resends cannot become public."""
    from content.models import (
        EmailAttachmentSnapshot,
        EmailBody,
        EmailDeliverySnapshot,
        EmailLinkSnapshot,
    )
    from content.models.email_delivery_snapshot import PRIVATE_ATTACHMENT_PREFIX

    stored_files = []
    try:
        private_attachments = private_attachments or (
            resend_of is not None
            and resend_of.attachments.filter(file__startswith=PRIVATE_ATTACHMENT_PREFIX).exists()
        )
        mime_message = message.message()
        raw_message = mime_message.as_bytes()
        attachments = _mime_attachments(mime_message)
        sources = list(attachment_sources or [])
        if sources and len(sources) != len(attachments):
            raise EmailSnapshotCaptureError(
                'La procedencia de los adjuntos no coincide con el mensaje.',
            )
        if not sources:
            sources = [{} for _ in attachments]

        text_body, html_body = message_bodies(message)
        links = extract_body_links(text_body, html_body)
        total_attachment_bytes = sum(len(item['payload']) for item in attachments)

        with transaction.atomic():
            body = EmailBody.objects.create(text=text_body, html=html_body)
            snapshot = EmailDeliverySnapshot.objects.create(
                delivery_id=delivery_id,
                template_key=template_key,
                classification=classification,
                family=family or '',
                subject=(getattr(message, 'subject', '') or '')[:500],
                from_email=(getattr(message, 'from_email', '') or '')[:320],
                to_recipients=[
                    (value or '').strip().lower()
                    for value in (getattr(message, 'to', ()) or ())
                    if (value or '').strip()
                ],
                cc_recipients=[
                    (value or '').strip().lower()
                    for value in (getattr(message, 'cc', ()) or ())
                    if (value or '').strip()
                ],
                body=body,
                message_size_bytes=len(raw_message),
                attachment_size_bytes=total_attachment_bytes,
                attachment_count=len(attachments),
                resend_of=resend_of,
            )
            for position, (item, source) in enumerate(zip(attachments, sources)):
                source_fields = _attachment_source(
                    source,
                    template_key=template_key,
                    filename=item['filename'],
                )
                attachment = EmailAttachmentSnapshot(
                    snapshot=snapshot,
                    filename=item['filename'],
                    mime_type=item['mime_type'],
                    size_bytes=len(item['payload']),
                    sha256=hashlib.sha256(item['payload']).hexdigest(),
                    position=position,
                    format_kind=_format_kind(
                        item['filename'], item['mime_type'],
                    ),
                    **source_fields,
                )
                # This opt-in belongs to the server-side capture, never to an upload.
                attachment._private_attachments = bool(private_attachments)
                if private_attachments:
                    attachment.file.storage = get_private_storage()
                attachment.file.save(
                    item['filename'],
                    ContentFile(item['payload']),
                    save=False,
                )
                stored_files.append((attachment.file.storage, attachment.file.name))
                attachment.save()
            for position, link in enumerate(links):
                EmailLinkSnapshot.objects.create(
                    snapshot=snapshot,
                    url=link['url'],
                    label=link['label'],
                    group=link['group'],
                    position=position,
                )
        return snapshot
    except EmailSnapshotCaptureError:
        for storage, name in stored_files:
            storage.delete(name)
        raise
    except Exception as exc:
        for storage, name in stored_files:
            try:
                storage.delete(name)
            except Exception:
                logger.exception('Could not clean failed email snapshot file %s.', name)
        raise EmailSnapshotCaptureError(
            'No se pudo archivar el correo exacto antes de enviarlo.',
        ) from exc


def resend_email_log(log, recipients, cc_recipients=()):
    """Send a new delivery from the exact retained body and attachment bytes."""
    from content.models import EmailLog
    from content.services import email_log_service
    from content.services.email_delivery_service import EmailDeliveryGateway

    snapshot = log.snapshot
    recipients = [recipients] if isinstance(recipients, str) else list(recipients)
    cc_recipients = (
        [cc_recipients]
        if isinstance(cc_recipients, str)
        else list(cc_recipients)
    )
    message = EmailMultiAlternatives(
        subject=snapshot.subject,
        body=snapshot.body.text,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', snapshot.from_email),
        to=recipients,
        cc=cc_recipients,
    )
    if snapshot.body.html:
        message.attach_alternative(snapshot.body.html, 'text/html')

    attachment_sources = []
    for attachment in snapshot.attachments.select_related('source_document').all():
        with attachment.file.open('rb') as retained_file:
            message.attach(
                attachment.filename,
                retained_file.read(),
                attachment.mime_type,
            )
        attachment_sources.append({
            'source_document_id': attachment.source_document_id,
            'business_kind': attachment.business_kind,
            'business_kind_label': attachment.business_kind_label,
        })

    metadata = dict(log.metadata or {})
    metadata['resend_of_email_log_id'] = log.pk
    metadata['to_recipients'] = recipients
    metadata['cc_recipients'] = cc_recipients
    targets = [
        (target.entity_type, target.object_id, target.object_repr)
        for target in log.targets.all()
    ]
    from content.services.email_recipient_service import recipient_log_contexts

    recipient_contexts = recipient_log_contexts(
        recipients,
        cc_recipients,
        contextual_client=log.client,
    )
    common_log_fields = {
        'template_key': snapshot.template_key,
        'recipients': recipients + cc_recipients,
        'recipient_contexts': recipient_contexts,
        'subject': snapshot.subject,
        'metadata': metadata,
        'targets': targets,
        'html_body': snapshot.body.html,
        'text_body': snapshot.body.text,
        'proposal': log.proposal,
        'client': None,
        'audience': log.audience,
    }
    try:
        sent_count = EmailDeliveryGateway.send(
            message,
            template_key=snapshot.template_key,
            classification=snapshot.classification,
            attachment_sources=attachment_sources,
            resend_of=snapshot,
        )
    except EmailSnapshotCaptureError:
        raise
    except Exception as exc:
        email_log_service.record_send(
            **common_log_fields,
            status=EmailLog.Status.FAILED,
            error_message=str(exc)[:1000],
        )
        raise EmailSnapshotResendError(
            'El correo quedó archivado, pero el servidor no aceptó el reenvío.',
        ) from exc

    if not sent_count:
        email_log_service.record_send(
            **common_log_fields,
            status=EmailLog.Status.FAILED,
            error_message='El backend de correo no aceptó el reenvío.',
        )
        raise EmailSnapshotResendError(
            'El correo quedó archivado, pero el servidor no aceptó el reenvío.',
        )
    return email_log_service.record_send(
        **common_log_fields,
        status=EmailLog.Status.SENT,
    )[0]
