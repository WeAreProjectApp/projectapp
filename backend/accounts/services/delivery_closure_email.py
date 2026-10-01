"""Manual, reviewed emails that close an approved delivery stage.

Preparing the email persists the exact body, approved-history summary and
selected public document snapshots.  Sending only claims an already prepared
record before crossing the SMTP boundary; it never regenerates content.
"""
from __future__ import annotations

import hashlib
import io
import json
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from accounts.models import (
    DeliveryDocumentSnapshot,
    DeliveryMessage,
    DeliveryOperation,
    DeliveryStage,
    DeliveryWorkspace,
    RequirementReview,
)
from accounts.models_delivery_email import (
    DeliveryEvidenceEmail,
    DeliveryEvidenceEmailAttempt,
    DeliveryEvidenceEmailFile,
)
from accounts.serializers_delivery_email import (
    PrepareStageEmailSerializer,
    ResendStageEmailSerializer,
    SendStageEmailSerializer,
)
from accounts.services.delivery_access import DeliveryConflict, fail, project_for_actor, require_admin
from accounts.services.delivery_documents import DeliveryDocumentIndex, artifact_scope, store_private_pdf
from accounts.services.delivery_workflow import _level_visible, _stage_approved


TEMPLATE_KEY = 'delivery_stage_approved_client'
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


def _validated(serializer_type, value):
    serializer = serializer_type(data=value)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _workspace_version(project):
    return DeliveryWorkspace.objects.filter(project=project).values_list('version', flat=True).first() or 0


def _stage_for_project(project, stage_id, *, lock=False):
    queryset = DeliveryStage.objects.select_related(
        'phase__scope__contract__project__client', 'phase__scope__amendment',
    ).filter(phase__scope__contract__project=project, pk=stage_id)
    if lock:
        queryset = queryset.select_for_update()
    stage = queryset.first()
    if stage is None:
        raise NotFound('Etapa no encontrada.')
    return stage


def _require_current_owner(preparation, project, actor, *, mcp_credential=None):
    require_admin(actor)
    if preparation.project_id != project.pk:
        raise NotFound('Correo de cierre no encontrado.')
    if preparation.client_id != project.client_id:
        raise DeliveryConflict('El cliente del proyecto cambió. Prepara de nuevo el correo de cierre.')
    if preparation.prepared_by_id != actor.pk:
        raise PermissionDenied('Solo quien preparó el correo puede acceder a esta evidencia.')
    if preparation.mcp_credential_id != getattr(mcp_credential, 'pk', None):
        # NotFound keeps a connector from learning that another channel's
        # immutable evidence exists.
        raise NotFound('Correo de cierre no encontrado.')


def _validate_credential(actor, credential):
    """Bind MCP evidence to the usable credential that owns its service actor."""
    if credential is None:
        return None
    if not credential.is_usable or credential.actor_id != actor.pk:
        raise PermissionDenied('La credencial MCP no puede preparar este correo de cierre.')
    return credential


def _require_preparation_credential(preparation, credential):
    """A credential-owned preview cannot be sent by a different connector key."""
    if preparation.mcp_credential_id != getattr(credential, 'pk', None):
        raise NotFound('Correo de cierre no encontrado.')


def _safe_text(user):
    return user.get_full_name() or user.email


def _public_requirement_snapshot(snapshot):
    """Keep only the guide fields a client could read in a publication."""
    return {
        field: snapshot.get(field)
        for field in (
            'id', 'key', 'title', 'description', 'created_at', 'updated_at',
            'guide', 'order', 'version', 'review_status',
        )
        if field in snapshot
    }


def _review_channel(review):
    channel = review.source_snapshot.get('channel', 'platform')
    return channel if channel in {'platform', 'email', 'whatsapp', 'meeting'} else 'platform'


def _closure_cutoff(project, stage, final_reviews):
    # Historical decisions retain the date the client acted. Their capture and
    # the public message accompanying the closing review happen later, within
    # one serialized operation whose receipt is written after both records.
    last_review = max(final_reviews, key=lambda review: (review.created_at, review.pk))
    completed_at = DeliveryOperation.objects.filter(
        project=project, created_at__gte=last_review.created_at,
        response__result__kind='reviews', response__result__stage_id=stage.pk,
    ).order_by('created_at', 'id').values_list('created_at', flat=True).first()
    return completed_at or last_review.created_at


def _closure_history(project, stage):
    """Freeze public rounds, decisions and discussion through the final approval."""
    current_versions = dict(stage.requirements.values_list('pk', 'version'))
    reviews = RequirementReview.objects.filter(
        requirement__stage=stage, decision='approved',
    ).select_related('actor', 'publication').order_by('requirement_id', '-reviewed_at', '-id')
    final = {}
    for review in reviews:
        if review.requirement_id not in final and current_versions.get(review.requirement_id) == review.requirement_version:
            final[review.requirement_id] = review
    missing = set(current_versions) - set(final)
    if missing:
        fail('La etapa no tiene una aprobación vigente para cada requerimiento.', 'stage_not_approved')
    requirements = [
        {
            'requirement_id': requirement.pk,
            'requirement_key': requirement.key,
            'requirement_title': requirement.title,
            'requirement_version': review.requirement_version,
            'publication_id': review.publication_id,
            'publication_round': review.publication.round,
            'reviewed_at': review.reviewed_at.isoformat(),
            'reviewer': review.original_reviewer or _safe_text(review.actor),
            'channel': _review_channel(review),
        }
        for requirement in stage.requirements.order_by('order', 'id')
        for review in [final[requirement.pk]]
    ]
    closed_at = _closure_cutoff(project, stage, final.values())
    publications = list(stage.publications.filter(created_at__lte=closed_at).select_related(
        'published_by',
    ).order_by('round', 'id'))
    document_index = DeliveryDocumentIndex(project, project.client, publications=publications)
    all_reviews = RequirementReview.objects.filter(
        requirement__stage=stage, created_at__lte=closed_at,
    ).select_related('actor', 'publication').order_by('reviewed_at', 'id')
    public_reviews = [
        {
            'id': review.pk, 'requirement_id': review.requirement_id,
            'requirement_version': review.requirement_version,
            'publication_id': review.publication_id,
            'publication_round': review.publication.round,
            'guide': _public_requirement_snapshot(review.content_snapshot),
            'decision': review.decision, 'message': review.message,
            'environment': review.environment,
            'author': _safe_text(review.actor),
            'author_id': review.actor_id,
            'reviewer': review.original_reviewer or _safe_text(review.actor),
            'channel': _review_channel(review),
            'is_external': review.is_external,
            'reviewed_at': review.reviewed_at.isoformat(),
            'created_at': review.created_at.isoformat(),
        }
        for review in all_reviews
    ]
    requirement_ids = set(current_versions)
    public_messages = DeliveryMessage.objects.filter(
        project=project, is_internal=False, created_at__lte=closed_at,
    ).filter(
        Q(level='stage', target_id=stage.pk)
        | Q(level='requirement', target_id__in=requirement_ids)
    ).select_related('actor').prefetch_related('requirements', 'documents').order_by('created_at', 'id')
    from accounts.services.delivery_documents import visible_message_documents
    return {
        'closed_at': closed_at.isoformat(),
        'requirements': requirements,
        'publications': [
            {
                'id': publication.pk, 'round': publication.round,
                'created_at': publication.created_at.isoformat(),
                'published_by': _safe_text(publication.published_by),
                'published_by_id': publication.published_by_id,
                'payload': {
                    key: publication.payload.get(key)
                    for key in ('id', 'key', 'title', 'description', 'version')
                    if key in publication.payload
                } | {
                    'requirements': [
                        _public_requirement_snapshot(item)
                        for item in publication.payload.get('requirements', [])
                    ],
                },
            }
            for publication in publications
        ],
        'reviews': public_reviews,
        'messages': [
            {
                'id': message.pk, 'level': message.level, 'target_id': message.target_id,
                'requirement_ids': [requirement.pk for requirement in message.requirements.all()],
                'message': message.message, 'author': _safe_text(message.actor),
                'author_id': message.actor_id,
                'created_at': message.created_at.isoformat(),
                'attachments': [
                    {
                        key: document.get(key)
                        for key in ('document_id', 'title', 'snapshot_id', 'sha256')
                    }
                    for document in visible_message_documents(
                        project, project.client, message, index=document_index,
                    )
                ],
            }
            for message in public_messages
        ],
    }


def _onion_snapshot(project, stage):
    phase = stage.phase
    scope = phase.scope
    contract = scope.contract
    amendment = scope.amendment
    return {
        'project': {'id': project.pk, 'name': project.name},
        'contract': {'id': contract.pk, 'key': contract.key, 'title': contract.title, 'version': contract.version},
        'amendment': (
            {'id': amendment.pk, 'key': amendment.key, 'title': amendment.title, 'version': amendment.version}
            if amendment else None
        ),
        'scope': {'id': scope.pk, 'key': scope.key, 'title': scope.title, 'version': scope.version},
        'phase': {'id': phase.pk, 'key': phase.key, 'title': phase.title, 'version': phase.version},
        'stage': {'id': stage.pk, 'key': stage.key, 'title': stage.title, 'version': stage.version},
    }


def _available_snapshots(project, stage):
    publications = list(stage.publications.order_by('-round', '-id'))
    index = DeliveryDocumentIndex(project, project.client, publications=publications)
    snapshots = list(
        DeliveryDocumentSnapshot.objects.filter(publication__stage=stage)
        .select_related('link__document', 'publication')
        .order_by('publication__round', 'id')
    )
    result = []
    for snapshot in snapshots:
        # Only expose the exact public copy the current client portal would
        # resolve for this link. Historical rounds remain in the immutable
        # publication trail but cannot be attached after they lose currency.
        if not index.visible(snapshot.link) or index.snapshot(snapshot.link).pk != snapshot.pk:
            continue
        result.append(snapshot)
    return result


def _requested_snapshots(project, stage, identifiers):
    available = {snapshot.pk: snapshot for snapshot in _available_snapshots(project, stage)}
    identifiers = list(identifiers or [])
    if len(identifiers) != len(set(identifiers)):
        fail('No repitas documentos publicados en el correo.', 'attachment_duplicate')
    selected = []
    for identifier in identifiers:
        snapshot = available.get(identifier)
        if snapshot is None:
            raise NotFound('El documento publicado no está disponible para este cierre.')
        selected.append(snapshot)
    return selected


def _read_snapshot(snapshot):
    try:
        with snapshot.file.open('rb') as stream:
            content = stream.read(MAX_ATTACHMENT_BYTES + 1)
    except (OSError, ValueError):
        fail('No se pudo leer una copia publicada para adjuntarla.', 'attachment_unavailable')
    if len(content) > MAX_ATTACHMENT_BYTES:
        fail('Un documento publicado supera el límite de 10 MB.', 'attachment_too_large')
    if hashlib.sha256(content).hexdigest() != snapshot.sha256:
        fail('La copia publicada no coincide con su hash.', 'attachment_integrity')
    return content


def _record_pdf(project, stage, history, onion):
    """Small optional summary; source files stay separately selected snapshots."""
    from html import escape
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    stream = io.BytesIO()
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(stream, pagesize=A4, title='Constancia de cierre de etapa', invariant=1)
    lines = [
        f'Proyecto: {project.name}', f'Etapa: {stage.title}',
        'Trazabilidad contractual: ' + ' / '.join(
            item['title'] for item in (
                onion['contract'], onion['amendment'], onion['scope'], onion['phase'], onion['stage'],
            ) if item
        ),
        f'Cierre registrado: {history["closed_at"]}',
        'Constancia de requerimientos aprobados:',
        *[
            f'{item["requirement_title"]} (v{item["requirement_version"]}, ronda {item["publication_round"]}) — '
            f'{item["reviewer"]}, {item["reviewed_at"]}, {item["channel"]}'
            for item in history['requirements']
        ],
        f'Registro público congelado: {len(history["publications"])} rondas y {len(history["reviews"])} decisiones.',
    ]
    story = [Paragraph('Constancia de cierre de etapa', styles['Heading1'])]
    for line in lines:
        story.extend([Paragraph(escape(line), styles['BodyText']), Spacer(1, 8)])
    document.build(story)
    return stream.getvalue()


def _render(project, stage, client, message, attachment_names, *, onion, history):
    from content.services.proposal_email_service import ProposalEmailService

    subject = f'{project.name}: etapa aprobada — {stage.title}'[:500]
    greeting = f'Hola {_safe_text(client)},'
    sections = [
        f'La etapa «{stage.title}» quedó aprobada. Conservamos esta constancia como cierre de la revisión.',
        'Trazabilidad contractual: ' + ' → '.join(
            item['title']
            for item in (
                onion['contract'], onion['amendment'], onion['scope'], onion['phase'], onion['stage'],
            )
            if item
        ),
        'Aprobaciones finales: ' + '; '.join(
            f'{item["requirement_title"]} v{item["requirement_version"]} — {item["reviewer"]} ({item["reviewed_at"]})'
            for item in history['requirements']
        ),
        f'Registro público congelado: {len(history["publications"])} rondas, '
        f'{len(history["reviews"])} decisiones y {len(history["messages"])} conversaciones hasta el cierre.',
    ]
    if message:
        sections.append(message)
    html_body, text_body = ProposalEmailService.render_composed_email(
        TEMPLATE_KEY, None, subject, greeting, sections,
        'Quedamos atentos a cualquier inquietud.', attachment_names,
    )
    return subject, ProposalEmailService._get_from_email(), html_body, text_body


def _manifest(*, recipients, subject, from_email, html_body, text_body, onion, history, attachments):
    payload = {
        'to': recipients, 'subject': subject, 'from_email': from_email,
        'html_body': html_body, 'text_body': text_body, 'onion': onion,
        'closure_history': history, 'attachments': attachments,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def _file_data(item, email_id):
    return {
        'id': item.pk, 'title': item.filename, 'filename': item.filename,
        'sha256': item.sha256, 'version': item.delivery_snapshot.publication.round if item.delivery_snapshot_id else None,
        'download_url': f'/api/accounts/projects/{email_id.project_id}/delivery/closure-emails/{email_id.pk}/attachments/{item.pk}/download/',
    }


def _attempt_data(attempt):
    return {
        'id': attempt.pk, 'request_id': attempt.request_id, 'status': attempt.status,
        'error_message': attempt.error_message, 'claimed_at': attempt.claimed_at.isoformat() if attempt.claimed_at else None,
        'sent_at': attempt.sent_at.isoformat() if attempt.sent_at else None,
        'finished_at': attempt.finished_at.isoformat() if attempt.finished_at else None,
        'created_at': attempt.created_at.isoformat(),
    }


def _prepared_query():
    return DeliveryEvidenceEmail.objects.prefetch_related(
        Prefetch('attachments', queryset=DeliveryEvidenceEmailFile.objects.select_related(
            'delivery_snapshot__publication',
        ).order_by('position', 'id'), to_attr='_prepared_files'),
        Prefetch('attempts', queryset=DeliveryEvidenceEmailAttempt.objects.order_by(
            'created_at', 'id',
        ), to_attr='_ordered_attempts'),
    )


def _dto(email, project=None, *, current_version=None):
    attempts = getattr(email, '_ordered_attempts', None)
    if attempts is None:
        attempts = list(email.attempts.order_by('created_at', 'id'))
    files = getattr(email, '_prepared_files', None)
    if files is None:
        files = email.attachments.select_related('delivery_snapshot__publication').order_by('position', 'id')
    if current_version is None:
        current_version = _workspace_version(project) if project is not None else email.captured_version
    latest = attempts[-1] if attempts else None
    status = latest.status if latest else 'prepared'
    return {
        'id': str(email.pk), 'project_id': email.project_id, 'stage_id': email.stage_id,
        'to': email.to_recipients, 'from_email': email.from_email, 'subject': email.subject,
        'text_body': email.text_body, 'html_body': email.html_body,
        'manifest_sha256': email.manifest_sha256, 'captured_version': email.captured_version,
        'closure_history': email.closure_history,
        'version': current_version,
        'attachments': [_file_data(item, email) for item in files],
        'status': status, 'error_message': latest.error_message if latest else '',
        'attempts': [_attempt_data(item) for item in attempts],
        'created_at': email.created_at.isoformat(),
    }


def _persist_file(email, *, content, filename, mime_type, position, snapshot=None):
    attachment = DeliveryEvidenceEmailFile(
        email=email, delivery_snapshot=snapshot, filename=filename[:255], mime_type=mime_type,
        size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), position=position,
    )
    store_private_pdf(attachment, content, filename)
    attachment.save()
    return attachment


def _prepare(project, actor, stage, values, *, mcp_credential=None, resend_of=None):
    client = project.client
    if not client.email:
        fail('El cliente actual no tiene un correo para recibir el cierre.', 'client_email_required')
    if not _stage_approved(stage):
        fail('La etapa debe estar aprobada por completo antes de preparar el correo.', 'stage_not_approved')
    if not _level_visible(project, client, 'stage', stage):
        fail('La etapa debe seguir visible para el cliente antes de preparar el correo.', 'stage_not_client_visible')
    selected = _requested_snapshots(project, stage, values.get('document_snapshot_ids', []))
    history = _closure_history(project, stage)
    onion = _onion_snapshot(project, stage)
    attachments = []
    for snapshot in selected:
        content = _read_snapshot(snapshot)
        filename = snapshot.title if snapshot.title.lower().endswith('.pdf') else snapshot.title + '.pdf'
        attachments.append((snapshot, content, filename, 'application/pdf'))
    if values.get('include_record_pdf'):
        attachments.append((None, _record_pdf(project, stage, history, onion), 'constancia-cierre-etapa.pdf', 'application/pdf'))
    subject, from_email, html_body, text_body = _render(
        project, stage, client, values.get('message', ''), [item[2] for item in attachments],
        onion=onion, history=history,
    )
    manifest_attachments = [
        {'snapshot_id': snapshot.pk if snapshot else None, 'filename': filename,
         'sha256': hashlib.sha256(content).hexdigest(), 'size_bytes': len(content)}
        for snapshot, content, filename, _ in attachments
    ]
    manifest = _manifest(
        recipients=[client.email.strip().lower()], subject=subject, from_email=from_email,
        html_body=html_body, text_body=text_body, onion=onion, history=history,
        attachments=manifest_attachments,
    )
    existing = DeliveryEvidenceEmail.objects.filter(project=project, request_id=values['request_id']).first()
    if existing:
        if (
            existing.prepared_by_id != actor.pk
            or existing.mcp_credential_id != getattr(mcp_credential, 'pk', None)
            or existing.manifest_sha256 != manifest
        ):
            raise DeliveryConflict('El identificador ya corresponde a otra preparación de cierre.')
        return existing
    email = DeliveryEvidenceEmail(
        project=project, stage=stage, prepared_by=actor, client=client,
        mcp_credential=mcp_credential,
        to_recipients=[client.email.strip().lower()], from_email=from_email,
        subject=subject, html_body=html_body, text_body=text_body,
        snapshot_payload={'onion': onion, 'attachments': manifest_attachments},
        closure_history=history, captured_version=_workspace_version(project),
        request_id=values['request_id'], manifest_sha256=manifest, resend_of=resend_of,
    )
    email.save()
    for position, (snapshot, content, filename, mime_type) in enumerate(attachments):
        _persist_file(email, content=content, filename=filename, mime_type=mime_type,
                      position=position, snapshot=snapshot)
    return email


def prepare_stage_email(project_id, actor, stage_id, data, *, mcp_credential=None):
    values = _validated(PrepareStageEmailSerializer, data)
    with artifact_scope(), transaction.atomic():
        project = project_for_actor(project_id, actor, lock=True)
        require_admin(actor)
        credential = _validate_credential(actor, mcp_credential)
        if values['expected_version'] != _workspace_version(project):
            raise DeliveryConflict()
        stage = _stage_for_project(project, stage_id, lock=True)
        email = _prepare(project, actor, stage, values, mcp_credential=credential)
    return _dto(email, project)


def list_stage_emails(project_id, actor, stage_id, *, mcp_credential=None):
    project = project_for_actor(project_id, actor)
    require_admin(actor)
    credential = _validate_credential(actor, mcp_credential)
    stage = _stage_for_project(project, stage_id)
    available = [
        {'id': item.pk, 'title': item.title, 'filename': item.file.name.rsplit('/', 1)[-1],
         'version': item.publication.round, 'sha256': item.sha256, 'round': item.publication.round}
        for item in _available_snapshots(project, stage)
    ]
    emails = _prepared_query().filter(
        project=project, stage=stage, prepared_by=actor, mcp_credential=credential,
    ).order_by('-created_at')
    current_version = _workspace_version(project)
    return {'version': current_version, 'stage_id': stage.pk,
            'available_documents': available,
            'emails': [_dto(item, project, current_version=current_version) for item in emails]}


def get_preparation(project_id, actor, preparation_id, *, mcp_credential=None):
    project = project_for_actor(project_id, actor)
    require_admin(actor)
    credential = _validate_credential(actor, mcp_credential)
    email = _prepared_query().filter(project=project, pk=preparation_id).first()
    if email is None:
        raise NotFound('Correo de cierre no encontrado.')
    _require_current_owner(email, project, actor, mcp_credential=credential)
    return _dto(email, project)


def _claim_send(project, actor, email, values, credential):
    if values['expected_version'] != _workspace_version(project):
        raise DeliveryConflict()
    if values['preview_sha256'] != email.manifest_sha256:
        raise DeliveryConflict('El correo preparado no coincide con la vista revisada.')
    _require_preparation_credential(email, credential)
    existing = DeliveryEvidenceEmailAttempt.objects.filter(email=email, request_id=values['request_id']).first()
    if existing:
        if existing.actor_id != actor.pk:
            raise DeliveryConflict('El identificador ya corresponde a otro intento de envío.')
        return existing, False
    # A prepared evidence record represents one deliberate send decision.
    # Retrying a failed, unknown or completed decision requires the explicit
    # resend preparation, which captures a separate human review.
    previous = email.attempts.order_by('-created_at', '-id').first()
    if previous is not None:
        return previous, False
    previous_attempt = None
    if email.resend_of_id:
        previous_attempt = email.resend_of.attempts.order_by('-created_at', '-id').first()
    attempt = DeliveryEvidenceEmailAttempt.objects.create(
        email=email, request_id=values['request_id'], actor=actor, mcp_credential=credential,
        resend_of=previous_attempt,
        status=DeliveryEvidenceEmailAttempt.Status.SENDING, claimed_at=timezone.now(),
    )
    return attempt, True


def _message_from_preparation(email):
    from content.services.email_delivery_service import EmailMultiAlternatives

    message = EmailMultiAlternatives(
        subject=email.subject, body=email.text_body, from_email=email.from_email,
        to=email.to_recipients,
    )
    message.attach_alternative(email.html_body, 'text/html')
    sources = []
    for attachment in email.attachments.select_related('delivery_snapshot__link__document').order_by('position', 'id'):
        try:
            with attachment.file.open('rb') as stream:
                content = stream.read(MAX_ATTACHMENT_BYTES + 1)
        except (OSError, ValueError):
            fail('No se pudo leer el adjunto conservado para enviarlo.', 'attachment_unavailable')
        if len(content) > MAX_ATTACHMENT_BYTES or hashlib.sha256(content).hexdigest() != attachment.sha256:
            fail('El adjunto conservado no coincide con su evidencia.', 'attachment_integrity')
        message.attach(attachment.filename, content, attachment.mime_type)
        source_document = attachment.delivery_snapshot.link.document_id if attachment.delivery_snapshot_id else None
        sources.append({'document_id': source_document} if source_document else {})
    return message, sources


def _record_gateway_send(email, *, status, error_message=''):
    from content.models import EmailLog
    from content.services.email_log_service import record_send

    logs = record_send(
        template_key=TEMPLATE_KEY, recipients=email.to_recipients, subject=email.subject,
        status=status, error_message=error_message, html_body=email.html_body,
        text_body=email.text_body, client=getattr(email.client, 'profile', None),
        audience=EmailLog.Audience.CLIENT,
        metadata={'delivery_closure_email_id': str(email.pk), 'stage_id': email.stage_id},
    )
    return logs[0] if logs else None


def _gateway_snapshot(email):
    """Read the gateway's pre-SMTP snapshot without making another log write."""
    from content.services.email_delivery_service import matching_delivery_trace

    trace = matching_delivery_trace(TEMPLATE_KEY, email.to_recipients)
    return trace.snapshot if trace is not None else None


def _finish_attempt(attempt, *, status, error_message='', log=None, snapshot=None):
    with transaction.atomic():
        current = DeliveryEvidenceEmailAttempt.objects.select_for_update().get(pk=attempt.pk)
        current.status = status
        current.error_message = error_message[:1000]
        current.email_log = log
        current.gateway_snapshot = snapshot or getattr(log, 'snapshot', None)
        current.finished_at = timezone.now()
        if status == DeliveryEvidenceEmailAttempt.Status.SENT:
            current.sent_at = current.finished_at
        current.save(update_fields=[
            'status', 'error_message', 'email_log', 'gateway_snapshot',
            'sent_at', 'finished_at', 'updated_at',
        ])


def send_stage_email(project_id, actor, preparation_id, data, *, mcp_credential=None):
    values = _validated(SendStageEmailSerializer, data)
    with transaction.atomic(durable=True):
        project = project_for_actor(project_id, actor, lock=True)
        email = DeliveryEvidenceEmail.objects.select_for_update().select_related('client').filter(
            project=project, pk=preparation_id,
        ).first()
        if email is None:
            raise NotFound('Correo de cierre no encontrado.')
        credential = _validate_credential(actor, mcp_credential)
        _require_current_owner(email, project, actor, mcp_credential=credential)
        _require_preparation_credential(email, credential)
        stage = _stage_for_project(project, email.stage_id, lock=True)
        if not _stage_approved(stage):
            fail('La etapa debe seguir aprobada para enviar el correo.', 'stage_not_approved')
        if not _level_visible(project, project.client, 'stage', stage):
            fail('La etapa debe seguir visible para el cliente antes de enviar el correo.', 'stage_not_client_visible')
        attempt, claimed = _claim_send(project, actor, email, values, credential)
    if not claimed:
        return _dto(email, project)

    try:
        from content.services.email_delivery_service import DeliveryClassification, EmailDeliveryGateway

        message, sources = _message_from_preparation(email)
        sent = EmailDeliveryGateway.send(
            message, template_key=TEMPLATE_KEY, classification=DeliveryClassification.CLIENT,
            attachment_sources=sources, private_attachments=True,
            resend_of=getattr(attempt.resend_of, 'gateway_snapshot', None),
        )
        if not sent:
            raise RuntimeError('El backend de correo no aceptó el envío.')
    except Exception as exc:
        try:
            log = _record_gateway_send(email, status='failed', error_message=str(exc)[:1000])
        except Exception:
            log = None
        _finish_attempt(
            attempt, status=DeliveryEvidenceEmailAttempt.Status.FAILED,
            error_message=str(exc), log=log, snapshot=_gateway_snapshot(email),
        )
    else:
        snapshot = _gateway_snapshot(email)
        try:
            log = _record_gateway_send(email, status='sent')
            _finish_attempt(
                attempt, status=DeliveryEvidenceEmailAttempt.Status.SENT,
                log=log, snapshot=snapshot,
            )
        except Exception as exc:
            # SMTP already accepted the frozen message. A later audit-write
            # error cannot turn that observed delivery into a failed send or
            # license an automatic retry.
            _finish_attempt(
                attempt, status=DeliveryEvidenceEmailAttempt.Status.UNKNOWN,
                error_message=f'Correo aceptado; no se completó el registro posterior: {exc}',
                snapshot=snapshot,
            )
    email.refresh_from_db()
    return _dto(email, project)


def prepare_stage_email_resend(project_id, actor, preparation_id, data, *, mcp_credential=None):
    values = _validated(ResendStageEmailSerializer, data)
    with artifact_scope(), transaction.atomic():
        project = project_for_actor(project_id, actor, lock=True)
        require_admin(actor)
        credential = _validate_credential(actor, mcp_credential)
        if values['expected_version'] != _workspace_version(project):
            raise DeliveryConflict()
        original = DeliveryEvidenceEmail.objects.select_for_update().select_related('stage', 'client').filter(
            project=project, pk=preparation_id,
        ).first()
        if original is None:
            raise NotFound('Correo de cierre no encontrado.')
        _require_current_owner(original, project, actor, mcp_credential=credential)
        _require_preparation_credential(original, credential)
        existing = DeliveryEvidenceEmail.objects.filter(project=project, request_id=values['request_id']).first()
        if existing:
            if (
                existing.resend_of_id != original.pk
                or existing.prepared_by_id != actor.pk
                or existing.mcp_credential_id != getattr(credential, 'pk', None)
            ):
                raise DeliveryConflict('El identificador ya corresponde a otra preparación de reenvío.')
            return _dto(existing, project)
        stage = _stage_for_project(project, original.stage_id, lock=True)
        if not _stage_approved(stage):
            fail('La etapa debe seguir aprobada para preparar un reenvío.', 'stage_not_approved')
        if not _level_visible(project, project.client, 'stage', stage):
            fail('La etapa debe seguir visible para el cliente antes de preparar un reenvío.', 'stage_not_client_visible')
        clone = DeliveryEvidenceEmail(
            project=project, stage=stage, prepared_by=actor, client=project.client,
            mcp_credential=credential,
            to_recipients=list(original.to_recipients), from_email=original.from_email,
            subject=original.subject, html_body=original.html_body, text_body=original.text_body,
            snapshot_payload=original.snapshot_payload, closure_history=original.closure_history,
            captured_version=original.captured_version, request_id=values['request_id'],
            manifest_sha256=original.manifest_sha256, resend_of=original,
        )
        clone.save()
        for source in original.attachments.select_related('delivery_snapshot').order_by('position', 'id'):
            try:
                with source.file.open('rb') as stream:
                    content = stream.read(MAX_ATTACHMENT_BYTES + 1)
            except (OSError, ValueError):
                fail('No se pudo leer un adjunto del correo original.', 'attachment_unavailable')
            if len(content) > MAX_ATTACHMENT_BYTES or hashlib.sha256(content).hexdigest() != source.sha256:
                fail('Un adjunto del correo original no coincide con su evidencia.', 'attachment_integrity')
            _persist_file(clone, content=content, filename=source.filename, mime_type=source.mime_type,
                          position=source.position, snapshot=source.delivery_snapshot)
    return _dto(clone, project)


def download_attachment(project_id, actor, preparation_id, file_id, *, mcp_credential=None):
    project = project_for_actor(project_id, actor)
    require_admin(actor)
    credential = _validate_credential(actor, mcp_credential)
    email = DeliveryEvidenceEmail.objects.filter(project=project, pk=preparation_id).first()
    if email is None:
        raise NotFound('Correo de cierre no encontrado.')
    _require_current_owner(email, project, actor, mcp_credential=credential)
    attachment = DeliveryEvidenceEmailFile.objects.filter(email=email, pk=file_id).first()
    if attachment is None:
        raise NotFound('Adjunto de cierre no encontrado.')
    try:
        with attachment.file.open('rb') as stream:
            content = stream.read(MAX_ATTACHMENT_BYTES + 1)
    except (OSError, ValueError):
        fail('No se pudo leer el adjunto de cierre.', 'attachment_unavailable')
    if len(content) > MAX_ATTACHMENT_BYTES or hashlib.sha256(content).hexdigest() != attachment.sha256:
        fail('El adjunto de cierre no coincide con su evidencia.', 'attachment_integrity')
    return content, attachment.filename, attachment.mime_type
