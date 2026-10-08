"""One persisted notice per public operation, with an after-commit SMTP claim."""
import hashlib
import json
import logging
from datetime import timedelta
from functools import partial
from smtplib import SMTPRecipientsRefused, SMTPSenderRefused

from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
    EmailMultiAlternatives,
    matching_delivery_trace,
)
from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from accounts.models import (
    DeliveryMessage,
    DeliveryStage,
    Notification,
    Project,
    UserProfile,
)
from accounts.models_delivery_notifications import (
    DeliveryNotificationAttempt,
    DeliveryNotificationEvent,
)
from accounts.services.delivery_access import (
    DeliveryConflict,
    fail,
    is_admin,
    project_for_actor,
    require_admin,
)

logger = logging.getLogger(__name__)
STATUS = DeliveryNotificationEvent.Status
CLAIM_TIMEOUT = timedelta(minutes=15)


def _client_active(client):
    profile = getattr(client, 'profile', None)
    return client.is_active and not (profile and profile.archived_at)


def _project_active(project):
    state = project.current_state.system_key if project.current_state_id else project.status
    return state not in (Project.STATUS_ARCHIVED, Project.STATUS_DECOMMISSIONED)


def _operation_context(project, actor, operation, result, data):
    kind = (result or {}).get('kind')
    stage, decisions, message = None, [], ''
    if kind == 'publications':
        stage = DeliveryStage.objects.get(publications__pk=result['id'])
        event_type, audience = 'delivery_published_client', 'client'
        title = f'Etapa disponible: {stage.title}'
        message = 'Puede revisar los comportamientos publicados y registrar sus resultados.'
    elif kind == 'reviews' and operation.endswith(':False'):
        # Positive results remain in the portal. Notify the team when attention is needed.
        needs_attention = any(row['decision'] != 'approved' for row in data['decisions'])
        if not needs_attention and not data.get('message'):
            return None
        stage = DeliveryStage.objects.get(pk=result['stage_id'])
        event_type, audience = 'delivery_reviewed_team', 'team'
        title, message = f'Revisión con observaciones: {stage.title}', data.get('message', '')
        snapshots = {row['id']: row for row in stage.publications.first().payload['requirements']}
        labels = {'approved': 'Conforme', 'objected': 'Con observaciones', 'rejected': 'Rechazado'}
        decisions = [{'title': snapshots[row['requirement_id']]['title'],
                      'result': labels[row['decision']], 'message': row.get('message', '')}
                     for row in data['decisions']]
    elif kind == 'messages':
        msg = DeliveryMessage.objects.get(pk=result['id'])
        if msg.is_internal:
            return None
        audience = 'client' if is_admin(actor) else 'team'
        event_type, title, message = f'delivery_message_{audience}', 'Nueva respuesta de seguimiento', msg.message
        if msg.level == 'stage':
            stage = DeliveryStage.objects.get(pk=msg.target_id)
        elif msg.level == 'requirement':
            requirement = msg.requirements.select_related('stage').first()
            stage = requirement.stage if requirement else None
    else:
        return None
    path = f'/es-co/platform/projects/{project.pk}/delivery'
    if stage:
        path += f'?stage={stage.pk}'
    return {'event_type': event_type, 'audience': audience, 'title': title,
            'project_name': project.name, 'stage_id': stage.pk if stage else None,
            'stage_title': stage.title if stage else '', 'message': message, 'decisions': decisions,
            'url': getattr(settings, 'FRONTEND_URL', 'https://projectapp.co').rstrip('/') + path}


def _queue(attempt_id):
    from accounts.tasks import send_delivery_notification_task
    try:
        send_delivery_notification_task(attempt_id)
    except Exception:  # noqa: BLE001 — preserve the outbox when the queue is unavailable.
        # Keep the durable pending attempt for the periodic dispatcher.
        logger.error('Delivery notice queue unavailable attempt_id=%s code=queue_unavailable', attempt_id)


def record_operation_notice(project, actor, operation, result, data):
    context = _operation_context(project, actor, operation, result, data)
    if context is None and _project_active(project) and (result or {}).get('kind') == 'reviews':
        # Keep the existing in-app receipt for approvals/historical entries without email.
        from accounts.services.delivery_workflow import _notify
        stage = DeliveryStage.objects.get(pk=result['stage_id'])
        _notify(project, actor, f'Revisión recibida: {stage.title}', stage_id=stage.pk)
    if context is None or not _project_active(project):
        return None
    client = project.client
    if context['audience'] == 'client':
        if not _client_active(client):
            return None
        recipients = [client.email] if client.email else []
        users = [client.pk] if client.pk != actor.pk else []
    else:
        from content.services.proposal_email_service import ProposalEmailService
        recipients = ProposalEmailService._get_notification_recipients()
        users = list(UserProfile.objects.filter(role='admin', user__is_active=True)
                     .exclude(user_id=actor.pk).values_list('user_id', flat=True))
    event, created = DeliveryNotificationEvent.objects.get_or_create(
        project=project, operation_key=data['request_id'], defaults={
            'actor': actor, 'client': client, 'event_type': context['event_type'],
            'audience': context['audience'], 'recipients': sorted(set(recipients)),
            'from_email': settings.DEFAULT_FROM_EMAIL, 'subject': context['title'][:500],
            'text_body': render_to_string('emails/delivery_activity.txt', context),
            'html_body': render_to_string('emails/delivery_activity.html', context), 'public_context': context,
        },
    )
    if not created:
        return event
    Notification.objects.bulk_create([
        Notification(user_id=user_id, type='general', title=context['title'][:300],
                     message=context['message'][:500], project=project,
                     related_object_type='delivery_stage' if context['stage_id'] else 'project',
                     related_object_id=context['stage_id'] or project.pk)
        for user_id in sorted(set(users))
    ])
    from content.mcp.context import current_mcp_context
    mcp = current_mcp_context()
    attempt = DeliveryNotificationAttempt.objects.create(event=event, request_id='initial', requested_by=actor,
                                                         credential=mcp.credential if mcp else None)
    transaction.on_commit(partial(_queue, attempt.pk))
    return event


def _finish(attempt_id, status, code='', snapshot=None):
    with transaction.atomic():
        event_id = DeliveryNotificationAttempt.objects.filter(pk=attempt_id).values_list('event_id', flat=True).first()
        if event_id is None:
            return
        event = DeliveryNotificationEvent.objects.select_for_update().get(pk=event_id)
        attempt = DeliveryNotificationAttempt.objects.select_for_update().get(pk=attempt_id)
        if attempt.status != STATUS.SENDING:
            return
        attempt.status, attempt.error_code, attempt.finished_at = status, code, timezone.now()
        attempt.gateway_snapshot = snapshot
        attempt.save(update_fields=['status', 'error_code', 'finished_at', 'gateway_snapshot'])
        if event.retention_context_id:
            return
        event.status, event.error_code = status, code
        event.version += 1
        event.save(update_fields=['status', 'error_code', 'version', 'updated_at'])
    logger.info('Delivery notice event_id=%s attempt_id=%s status=%s code=%s', event.pk, attempt_id, status, code)


def _recipient_current(event, project):
    return (project and project.client_id == event.client_id and _project_active(project)
            and _client_active(project.client)
            and (event.audience != 'client' or event.recipients == [project.client.email]))


def send_attempt(attempt_id):
    with transaction.atomic():
        event_id = DeliveryNotificationAttempt.objects.filter(pk=attempt_id).values_list('event_id', flat=True).first()
        if event_id is None:
            return False
        event = DeliveryNotificationEvent.objects.select_for_update().get(pk=event_id)
        attempt = DeliveryNotificationAttempt.objects.select_for_update().select_related('credential').get(pk=attempt_id)
        if event.retention_context_id:
            return False
        if attempt.status != STATUS.PENDING or event.status != STATUS.PENDING:
            return False
        project = Project.objects.select_related('client__profile', 'current_state').filter(pk=event.project_id).first()
        attempt.status, attempt.claimed_at = STATUS.SENDING, timezone.now()
        attempt.save(update_fields=['status', 'claimed_at'])
        event.status, event.version = STATUS.SENDING, event.version + 1
        event.save(update_fields=['status', 'version', 'updated_at'])
        cancelled = not _recipient_current(event, project) or (
            attempt.credential_id and not attempt.credential.is_usable)
    if cancelled:
        _finish(attempt_id, STATUS.CANCELLED, 'recipient_or_credential_changed')
        return False
    if not event.recipients:
        _finish(attempt_id, STATUS.FAILED, 'recipients_missing')
        return False
    from content.services.proposal_email_service import ProposalEmailService
    if not ProposalEmailService._is_template_active(event.event_type):
        _finish(attempt_id, STATUS.CANCELLED, 'template_disabled')
        return False
    connection = EmailDeliveryGateway.bounded_connection(timeout_seconds=20)
    message = EmailMultiAlternatives(subject=event.subject, body=event.text_body,
                                     from_email=event.from_email, to=event.recipients, connection=connection)
    message.attach_alternative(event.html_body, 'text/html')
    status, code = STATUS.UNKNOWN, 'transport_result_unknown'
    try:
        sent = EmailDeliveryGateway.send(message, template_key=event.event_type,
                                        classification=(DeliveryClassification.CLIENT if event.audience == 'client'
                                                        else DeliveryClassification.INTERNAL))
        status, code = (STATUS.SENT, '') if sent else (STATUS.FAILED, 'transport_rejected')
    except (SMTPRecipientsRefused, SMTPSenderRefused):
        status, code = STATUS.FAILED, 'transport_rejected'
    except Exception:  # noqa: BLE001 — any uncertain SMTP outcome must not be replayed.
        logger.error('Delivery notice uncertain event_id=%s attempt_id=%s code=%s', event.pk, attempt_id, code)
    finally:
        trace = matching_delivery_trace(event.event_type, event.recipients)
        _finish(attempt_id, status, code, trace.snapshot if trace else None)
    return status == STATUS.SENT


def dispatch_pending():
    stale = DeliveryNotificationAttempt.objects.filter(status=STATUS.SENDING, event__project__isnull=False,
                                                       claimed_at__lt=timezone.now() - CLAIM_TIMEOUT)
    for attempt_id in stale.values_list('pk', flat=True)[:50]:
        _finish(attempt_id, STATUS.UNKNOWN, 'worker_result_unknown')
    for attempt_id in DeliveryNotificationAttempt.objects.filter(status=STATUS.PENDING, event__project__isnull=False).values_list('pk', flat=True)[:50]:
        _queue(attempt_id)


def _event(project_id, actor, event_id, *, lock=False):
    require_admin(actor)
    project = project_for_actor(project_id, actor, lock=lock)
    query = DeliveryNotificationEvent.objects.filter(project=project)
    if lock:
        query = query.select_for_update()
    event = query.filter(pk=event_id).first()
    if event is None:
        raise NotFound('Aviso de entrega no encontrado.')
    return project, event


def event_data(event):
    return {'id': str(event.pk), 'project_id': event.project_id, 'event_type': event.event_type,
            'status': event.status, 'version': event.version, 'error_code': event.error_code,
            'subject': event.subject, 'recipients': event.recipients, 'text_body': event.text_body,
            'created_at': event.created_at.isoformat(),
            'attempts': [{'id': row.pk, 'status': row.status, 'error_code': row.error_code,
                          'created_at': row.created_at.isoformat(),
                          'finished_at': row.finished_at.isoformat() if row.finished_at else None}
                         for row in event.attempts.all()]}


def get_event(project_id, actor, event_id):
    return event_data(_event(project_id, actor, event_id)[1])


def list_events(project_id, actor, page=1, status=None):
    require_admin(actor)
    project_for_actor(project_id, actor)
    if type(page) is not int or page < 1:
        fail('La página debe ser un entero positivo.')
    if status is not None and status not in STATUS.values:
        fail('Estado de aviso inválido.')
    query = DeliveryNotificationEvent.objects.filter(project_id=project_id).prefetch_related('attempts')
    if status is not None:
        query = query.filter(status=status)
    return {'count': query.count(), 'page': page,
            'results': [event_data(row) for row in query[(page - 1) * 20:page * 20]]}


def _retry_manifest(project, event, expected_version):
    if type(expected_version) is not int or event.version != expected_version:
        raise DeliveryConflict()
    if not _recipient_current(event, project):
        raise DeliveryConflict('El destinatario o proyecto cambió. No se puede reenviar esta copia.')
    if event.status != STATUS.FAILED:
        fail('Sólo se reintenta un fallo confirmado; un resultado desconocido requiere revisión.', 'notice_not_retryable')
    payload = {'event_id': str(event.pk), 'version': event.version, 'client_id': project.client_id,
               'from_email': event.from_email,
               'recipients': event.recipients, 'subject': event.subject,
               'text_body': event.text_body, 'html_body': event.html_body}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def retry_impact(project_id, actor, event_id, expected_version):
    project, event = _event(project_id, actor, event_id)
    return {**event_data(event), 'preview_sha256': _retry_manifest(project, event, expected_version)}


def retry_event(project_id, actor, event_id, expected_version, request_id, preview_sha256, credential=None):
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 100 or request_id == 'initial':
        fail('Usa un identificador de reintento nuevo y estable.', 'request_id_required')
    if credential is not None and (not credential.is_usable or credential.actor_id != actor.pk):
        raise PermissionDenied('La credencial no permite reintentar este aviso.')
    with transaction.atomic():
        project, event = _event(project_id, actor, event_id, lock=True)
        previous = event.attempts.filter(request_id=request_id).first()
        if previous:
            if previous.requested_by_id != actor.pk or previous.credential_id != getattr(credential, 'pk', None):
                raise NotFound('Reintento no encontrado.')
            if previous.preview_sha256 != preview_sha256:
                raise DeliveryConflict('El identificador ya pertenece a otra copia del aviso.')
            return event_data(event)
        if _retry_manifest(project, event, expected_version) != preview_sha256:
            raise DeliveryConflict('Revisa la copia exacta antes de reintentar el aviso.')
        attempt = DeliveryNotificationAttempt.objects.create(event=event, request_id=request_id,
                                                              requested_by=actor, credential=credential,
                                                              preview_sha256=preview_sha256)
        event.status, event.error_code = STATUS.PENDING, ''
        event.version += 1
        event.save(update_fields=['status', 'error_code', 'version', 'updated_at'])
        transaction.on_commit(partial(_queue, attempt.pk))
        return event_data(event)
