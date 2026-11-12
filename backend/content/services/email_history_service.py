"""Query and representation helpers for the global outbound email history."""

from django.db.models import Prefetch, Q


def history_queryset():
    from content.models import EmailAttachmentSnapshot, EmailLog, EmailLinkSnapshot

    return (
        EmailLog.objects.filter(delivery_role=EmailLog.DeliveryRole.PRIMARY)
        .select_related('body', 'snapshot__body', 'proposal', 'client')
        .prefetch_related(
            'targets',
            Prefetch(
                'snapshot__attachments',
                queryset=EmailAttachmentSnapshot.objects.select_related(
                    'source_document',
                ).order_by('position', 'id'),
            ),
            Prefetch(
                'snapshot__links',
                queryset=EmailLinkSnapshot.objects.order_by('position', 'id'),
            ),
        )
        .order_by('-sent_at', '-id')
    )


def apply_attachment_filters(queryset, params):
    """Apply trustworthy snapshot filters; legacy false is never inferred."""
    from content.models import EmailAttachmentSnapshot

    has_attachments = (params.get('has_attachments') or '').strip().lower()
    if has_attachments == 'true':
        legacy_ids = [
            pk
            for pk, metadata in queryset.filter(snapshot__isnull=True).values_list(
                'pk', 'metadata',
            )
            if isinstance((metadata or {}).get('attachment_names'), list)
            and bool((metadata or {}).get('attachment_names'))
        ]
        queryset = queryset.filter(
            Q(snapshot__attachment_count__gt=0) | Q(pk__in=legacy_ids),
        )
    elif has_attachments == 'false':
        queryset = queryset.filter(snapshot__attachment_count=0)

    attachment_type = (params.get('attachment_type') or '').strip()
    if ':' not in attachment_type:
        return queryset
    category, value = attachment_type.split(':', 1)
    if category == 'format' and value in EmailAttachmentSnapshot.FormatKind.values:
        return queryset.filter(
            snapshot__attachments__format_kind=value,
        ).distinct()
    if category == 'business' and value:
        return queryset.filter(
            snapshot__attachments__business_kind=value,
        ).distinct()
    return queryset


def attachment_type_options():
    from content.models import EmailAttachmentSnapshot

    defaults = [
        ('collection_account', 'Cuenta de cobro'),
        ('document', 'Documento'),
        ('proposal', 'Propuesta'),
        ('diagnostic', 'Diagnóstico'),
        ('contract', 'Contrato'),
        ('platform_guide', 'Guía de plataforma'),
    ]
    dynamic = EmailAttachmentSnapshot.objects.exclude(
        business_kind='',
    ).values_list('business_kind', 'business_kind_label').distinct()
    labels = {code: label for code, label in defaults}
    for code, label in dynamic:
        labels.setdefault(code, label or code.replace('_', ' ').title())
    return [
        {
            'value': f'business:{code}',
            'label': label,
            'group': 'business',
        }
        for code, label in labels.items()
    ] + [
        {
            'value': f'format:{value}',
            'label': label,
            'group': 'format',
        }
        for value, label in EmailAttachmentSnapshot.FormatKind.choices
    ]


def _attachment_payload(attachment, log_id):
    source_document = attachment.source_document
    return {
        'id': attachment.pk,
        'filename': attachment.filename,
        'mime_type': attachment.mime_type,
        'size_bytes': attachment.size_bytes,
        'sha256': attachment.sha256,
        'format_kind': attachment.format_kind,
        'format_label': attachment.get_format_kind_display(),
        'business_kind': attachment.business_kind,
        'business_kind_label': attachment.business_kind_label,
        'exact_available': True,
        'source_document': (
            {
                'id': source_document.pk,
                'title': source_document.title,
                'type_code': attachment.source_document_type_code,
                'type_name': attachment.source_document_type_name,
            }
            if source_document else None
        ),
        'download_url': (
            f'/api/emails/history/{log_id}/attachments/{attachment.pk}/'
        ),
        'preview_url': (
            f'/api/emails/history/{log_id}/attachments/{attachment.pk}/?inline=1'
            if attachment.format_kind == 'pdf' else ''
        ),
    }


def _link_payload(link):
    return {
        'id': getattr(link, 'pk', None),
        'url': link.url if hasattr(link, 'url') else link['url'],
        'label': (
            link.label if hasattr(link, 'label') else link.get('label', '')
        ),
        'group': link.group if hasattr(link, 'group') else link['group'],
    }


def snapshot_payload(log):
    """Serialize exact evidence or an explicit legacy information gap."""
    from content.services.email_snapshot_service import extract_body_links

    from content.services.email_privacy_policy import credential_email, protected_snapshot_payload
    if credential_email(log.template_key):
        return protected_snapshot_payload()
    if log.snapshot_id:
        attachments = [
            _attachment_payload(attachment, log.pk)
            for attachment in log.snapshot.attachments.all()
        ]
        links = [_link_payload(link) for link in log.snapshot.links.all()]
        return {
            'snapshot_state': 'captured',
            'snapshot_notice': '',
            'has_attachments': bool(attachments),
            'attachment_count': len(attachments),
            'attachments': attachments,
            'message_size_bytes': log.snapshot.message_size_bytes,
            'attachment_size_bytes': log.snapshot.attachment_size_bytes,
            'links': {
                'content': [item for item in links if item['group'] == 'content'],
                'template': [item for item in links if item['group'] == 'template'],
            },
            'can_resend': True,
            'resend_of_snapshot_id': log.snapshot.resend_of_id,
        }

    legacy_names = (log.metadata or {}).get('attachment_names')
    if not isinstance(legacy_names, list):
        legacy_names = []
    attachments = [
        {
            'id': None,
            'filename': str(name),
            'mime_type': '',
            'size_bytes': None,
            'sha256': '',
            'format_kind': '',
            'format_label': 'Tipo no archivado',
            'business_kind': '',
            'business_kind_label': '',
            'exact_available': False,
            'source_document': None,
            'download_url': '',
            'preview_url': '',
        }
        for name in legacy_names if name
    ]
    body = log.body
    legacy_links = extract_body_links(
        body.text if body else '',
        body.html if body else '',
    )
    state = 'legacy_partial' if attachments else 'legacy_unknown'
    return {
        'snapshot_state': state,
        'snapshot_notice': (
            'Este correo es anterior al archivo exacto. Se conocen algunos '
            'datos, pero el archivo enviado no está disponible.'
            if state == 'legacy_partial'
            else 'No hay información histórica suficiente para confirmar si llevaba adjuntos.'
        ),
        'has_attachments': True if attachments else None,
        'attachment_count': len(attachments) if attachments else None,
        'attachments': attachments,
        'message_size_bytes': None,
        'attachment_size_bytes': None,
        'links': {
            'content': [item for item in legacy_links if item['group'] == 'content'],
            'template': [item for item in legacy_links if item['group'] == 'template'],
        },
        'can_resend': False,
        'resend_of_snapshot_id': None,
    }
