"""Shared ticket lifecycle for Platform, session administration and MCP."""
import hashlib
import json
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from accounts.models import (
    BugComment, BugReport, ChangeRequest, ChangeRequestComment, DeliveryStage,
    IssueEvent, IssueResponse, Notification,
)
from accounts.services.delivery_access import (
    DeliveryConflict, fail, is_admin, project_for_actor, require_admin,
)
from accounts.services.delivery_documents import artifact_scope
from accounts.services.issue_context import applicable_contract, capture_context, original_context, save_context
from accounts.services.issue_evidence import attach_documents
from accounts.services.notifications import notify_project_admins, notify_project_client


MODELS = {'bug': BugReport, 'change': ChangeRequest}
RELATIONS = {'bug': 'bug_report', 'change': 'change_request'}
CREATE_FIELDS = {
    'bug': ('title', 'description', 'severity', 'steps_to_reproduce', 'expected_behavior',
            'actual_behavior', 'environment', 'device_browser', 'is_recurring', 'screenshot'),
    'change': ('title', 'description', 'module_or_screen', 'suggested_priority', 'is_urgent', 'screenshot'),
}


def serializer_context(project, actor, **extra):
    return {'project': project, 'request': SimpleNamespace(
        user=actor, build_absolute_uri=lambda url: url,
    ), **extra}


def _serializer(kind, operation):
    from accounts import serializers as api
    names = {
        ('bug', 'create'): api.CreateBugReportSerializer,
        ('change', 'create'): api.CreateChangeRequestSerializer,
        ('bug', 'evaluate'): api.EvaluateBugReportSerializer,
        ('change', 'evaluate'): api.EvaluateChangeRequestSerializer,
        ('bug', 'comment'): api.CreateBugCommentSerializer,
        ('change', 'comment'): api.CreateChangeRequestCommentSerializer,
    }
    return names[(kind, operation)]


def _fingerprint(kind, action, ticket_id, values):
    def normalize(value):
        if hasattr(value, 'read'):
            position = value.tell()
            digest = hashlib.sha256(value.read()).hexdigest()
            value.seek(position)
            return {'name': value.name, 'sha256': digest}
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items() if key != 'request_id'}
        if isinstance(value, (list, tuple)):
            return [normalize(item) for item in value]
        return value if value is None or isinstance(value, (str, bool, int, float)) else str(value)
    payload = [kind, action, ticket_id, normalize(values)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def get_ticket(project_id, actor, kind, ticket_id, *, include_archived=False, lock=False):
    project_for_actor(project_id, actor)
    return _load_ticket(project_id, actor, kind, ticket_id,
                        include_archived=include_archived, lock=lock)


def _load_ticket(project_id, actor, kind, ticket_id, *, include_archived=False, lock=False):
    qs = MODELS[kind].objects.select_related('issue_context')
    if lock:
        qs = qs.select_for_update()
    ticket = qs.filter(pk=ticket_id, project_id=project_id).first()
    if ticket is None or (ticket.is_archived and not (include_archived and is_admin(actor))):
        raise NotFound('Ticket no encontrado.')
    return ticket


def _run(project_id, actor, kind, action, data, change, *, ticket_id=None, admin=False):
    if admin:
        require_admin(actor)
    with artifact_scope(), transaction.atomic():
        # The project lock also serializes creation retries before the ticket exists.
        project = project_for_actor(project_id, actor, lock=True)
        ticket = _load_ticket(project_id, actor, kind, ticket_id, lock=True,
                              include_archived=action == 'archive') if ticket_id else None
        if ticket:
            ticket.project = project
        if action in ('create', 'evaluate', 'comment'):
            serializer = _serializer(kind, action)(data=data, context=serializer_context(
                project, actor, bug=ticket,
            ), partial=action == 'evaluate')
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
        else:
            from accounts.serializers_issue_reports import IssueWriteFields
            serializer = IssueWriteFields(data=data)
            serializer.is_valid(raise_exception=True)
            values = {**data, **serializer.validated_data}
        fingerprint = _fingerprint(kind, action, ticket_id, values)
        request_id = values.get('request_id')
        previous = IssueEvent.objects.filter(project=project, actor=actor, request_id=request_id).first() if request_id else None
        if previous:
            if previous.fingerprint != fingerprint:
                raise DeliveryConflict('El identificador del reintento pertenece a otra operación.')
            result = get_ticket(project_id, actor, kind, previous.receipt['ticket_id'], include_archived=True)
            return result, previous.receipt
        if ticket and ticket.is_archived:
            raise NotFound('Ticket no encontrado.')
        if ticket and values.get('expected_version', ticket.version) != ticket.version:
            raise DeliveryConflict('El ticket cambió. Actualiza antes de responder.')
        previous_status = ticket.status if ticket else ''
        ticket, receipt = change(project, ticket, values)
        ticket.version += 1
        ticket.save()
        IssueEvent.objects.create(
            project=project, actor=actor, action=receipt.pop('action', action),
            previous_status=previous_status, status=ticket.status,
            is_internal=receipt.pop('is_internal', bool(values.get('is_internal'))) and previous_status == ticket.status,
            request_id=request_id, fingerprint=fingerprint,
            receipt={'ticket_id': ticket.pk, 'ticket_version': ticket.version, **receipt}, **{RELATIONS[kind]: ticket},
        )
        return ticket, {'ticket_id': ticket.pk, **receipt}


def _notify(ticket, actor, kind, *, created=False, reopened=False):
    project = ticket.project
    notification_type = (Notification.TYPE_BUG_REPORTED if kind == 'bug' else Notification.TYPE_CR_CREATED) if created else (
        Notification.TYPE_BUG_STATUS_CHANGED if kind == 'bug' else Notification.TYPE_CR_STATUS_CHANGED
    )
    notify = notify_project_client if is_admin(actor) else notify_project_admins
    title = ('Bug reportado' if kind == 'bug' else 'Nueva solicitud de cambio') if created else (
        'Bug actualizado' if kind == 'bug' else 'Solicitud actualizada'
    )
    notify(project, notification_type, f'{title}: {ticket.title}',
           message='El cliente indica que sigue fallando.' if reopened else f'Estado cambiado a "{ticket.get_status_display()}".',
           related_object_type='bug_report' if kind == 'bug' else 'change_request',
           related_object_id=ticket.pk, exclude_user=actor)


def create_ticket(project_id, actor, kind, data):
    def change(project, ticket, values):
        publication, snapshot = capture_context(project, actor, values)
        fields = {key: values[key] for key in CREATE_FIELDS[kind] if key in values}
        ticket = MODELS[kind].objects.create(
            project=project, source_requirement_id=values.get('source_requirement_id'),
            **{'reported_by' if kind == 'bug' else 'created_by': actor}, **fields,
        )
        save_context(ticket, kind, publication, snapshot)
        _notify(ticket, actor, kind, created=True)
        return ticket, {}
    return _run(project_id, actor, kind, 'create', data, change)[0]


def evaluate_ticket(project_id, actor, kind, ticket_id, data):
    def change(project, ticket, values):
        from accounts.services.issue_contract_reply import validate_reply
        fields = ('status', 'linked_bug_id') if kind == 'bug' else ('status', 'estimated_cost', 'estimated_time')
        if not any(key in values for key in (*fields, 'admin_response')):
            fail('Indica un estado o una respuesta.', 'issue_empty_response')
        contract = applicable_contract(project, ticket, values.get('contract_id'))
        reviewed = validate_reply(project, actor, kind, ticket, values)
        changed_status = values.get('status', ticket.status) != ticket.status
        for field in fields:
            if field in values:
                setattr(ticket, field, values[field])
        message = values.get('admin_response', '').strip()
        internal = values.get('is_internal', False)
        if values.get('document_ids') and not message:
            fail('Escribe una respuesta para asociar sus documentos.', 'issue_message_required')
        if message:
            response = IssueResponse.objects.create(
                actor=actor, message=message, status=ticket.status,
                is_internal=internal, contract=contract, **(reviewed or {}), **{RELATIONS[kind]: ticket},
            )
            attach_documents(project, actor, ticket, values.get('document_ids', []),
                             public=not internal, response=response, contract=contract)
            if not internal:
                ticket.admin_response = message
        if changed_status or (message and not internal) or 'status' in values:
            _notify(ticket, actor, kind)
        return ticket, {'response_id': response.pk} if message else {}
    return _run(project_id, actor, kind, 'evaluate', data, change, ticket_id=ticket_id, admin=True)[0]


def comment_ticket(project_id, actor, kind, ticket_id, data):
    def change(project, ticket, values):
        reopen = values.get('reopen', False)
        if reopen:
            if kind != 'bug' or ticket.status != BugReport.STATUS_RESOLVED:
                fail('Solo se puede reabrir un bug resuelto por equipo.', 'issue_reopen_state')
            ticket.status = BugReport.STATUS_REPORTED
        internal = values.get('is_internal', False) and is_admin(actor)
        if reopen and internal:
            fail('La respuesta «sigue fallando» debe ser visible para ambas partes.', 'issue_reopen_internal')
        model = BugComment if kind == 'bug' else ChangeRequestComment
        comment = model.objects.create(user=actor, content=values['content'], is_internal=internal,
                                       **{RELATIONS[kind]: ticket})
        attach_documents(project, actor, ticket, values.get('document_ids', []), public=not internal,
                         **{'bug_comment' if kind == 'bug' else 'change_comment': comment})
        if reopen:
            _notify(ticket, actor, kind, reopened=True)
        return ticket, {'comment_id': comment.pk, 'action': 'reopened' if reopen else 'comment', 'is_internal': internal}
    _, receipt = _run(project_id, actor, kind, 'comment', data, change, ticket_id=ticket_id)
    model = BugComment if kind == 'bug' else ChangeRequestComment
    return model.objects.select_related('user').prefetch_related('issue_attachments').get(pk=receipt['comment_id'])


def archive_ticket(project_id, actor, kind, ticket_id, data):
    if not is_admin(actor):
        raise PermissionDenied('Solo los administradores pueden eliminar '
                               + ('reportes de bugs.' if kind == 'bug' else 'solicitudes de cambio.'))
    def change(project, ticket, values):
        ticket.is_archived, ticket.archived_at = True, timezone.now()
        return ticket, {}
    return _run(project_id, actor, kind, 'archive', data, change, ticket_id=ticket_id, admin=True)[0]


def bulk_evaluate(project_id, actor, kind, items):
    require_admin(actor)
    project_for_actor(project_id, actor)
    from rest_framework.exceptions import ValidationError
    if not isinstance(items, list):
        raise ValidationError({'detail': 'Se espera un array JSON de evaluaciones.'})
    if len(items) > 500:
        raise ValidationError({'detail': 'Máximo 500 evaluaciones por carga.'})
    from rest_framework.exceptions import APIException
    updated, errors = [], []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append({'index': index, 'detail': 'Item no es un objeto.'})
            continue
        if item.get('id') is None:
            errors.append({'index': index, 'detail': 'Falta el campo id.'})
            continue
        raw_id = item['id']
        # Preserve the existing integer-key aliases without coercing strings or
        # truncating fractional IDs. Malformed JSON containers become item errors.
        ticket_id = int(raw_id) if isinstance(raw_id, (int, float)) and (
            isinstance(raw_id, int) or raw_id.is_integer()
        ) else None
        if ticket_id is None or ticket_id < 1 or ticket_id > 2 ** 63 - 1:
            errors.append({'index': index, 'id': raw_id, 'detail':
                           'No encontrado en el proyecto.' if kind == 'bug' else 'No encontrada en el proyecto.'})
            continue
        try:
            evaluate_ticket(project_id, actor, kind, ticket_id, {key: value for key, value in item.items() if key != 'id'})
            updated.append(ticket_id)
        except APIException as exc:
            detail = ('No encontrado en el proyecto.' if kind == 'bug' else 'No encontrada en el proyecto.') if isinstance(exc, NotFound) else exc.detail
            errors.append({'index': index, 'id': raw_id, 'detail': detail})
    return {'updated': len(updated), 'updated_ids': updated, 'errors': errors}


def convert_request(project_id, actor, ticket_id, data):
    from accounts.services.delivery_workflow import mutate_node
    from rest_framework import serializers

    class ConversionSerializer(serializers.Serializer):
        stage_id = serializers.IntegerField(min_value=1)
        expected_version = serializers.IntegerField(min_value=0)
        issue_version = serializers.IntegerField(min_value=0, required=False)
        request_id = serializers.UUIDField(required=False)

    require_admin(actor)
    # Preserve the legacy not-found response before validating conversion fields.
    get_ticket(project_id, actor, 'change', ticket_id)
    payload = ConversionSerializer(data=data)
    payload.is_valid(raise_exception=True)
    values = payload.validated_data
    operation = {**values, 'expected_version': values.get('issue_version')} if 'issue_version' in values else {
        key: value for key, value in values.items() if key != 'expected_version'
    }
    operation['workspace_version'] = values['expected_version']

    def change(project, ticket, ignored):
        if ticket.status != ChangeRequest.STATUS_APPROVED or ticket.linked_requirement_id:
            fail('Solo se pueden convertir solicitudes aprobadas sin requerimiento vinculado.', 'issue_convert_state')
        stage = DeliveryStage.objects.select_related('phase__scope').filter(
            pk=values['stage_id'], phase__scope__contract__project=project,
        ).first()
        if not stage:
            raise NotFound('Etapa no encontrada en este proyecto.')
        origin = original_context(ticket)
        if not origin.get('contract_id') and ticket.source_requirement_id:
            origin = {'contract_id': ticket.source_requirement.stage.phase.scope.contract_id}
        if origin.get('contract_id') and stage.phase.scope.contract_id != origin['contract_id']:
            fail('La ampliación debe conservar el contrato aplicable.', 'issue_convert_contract')
        result = mutate_node(project.pk, actor, 'requirements', {
            'stage_id': stage.pk, 'expected_version': values['expected_version'],
            'key': f'change-request-{ticket.pk}', 'title': ticket.title,
            'description': ticket.description, 'guide': {},
        })
        ticket.linked_requirement_id = result['result']['id']
        return ticket, {}
    return _run(project_id, actor, 'change', 'converted', operation, change, ticket_id=ticket_id, admin=True)[0]
