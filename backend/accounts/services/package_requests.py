"""Manual sizing, versioned offers and client-only atomic allowance consent."""
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import ChangeRequest
from accounts.models_requirement_packages import (
    PackageDecision, PackageMovement, PackageRequest, PackageSizingProposal,
)
from accounts.services.delivery_access import is_admin
from accounts.services.issue_context import save_context
from accounts.services.package_common import check_version, mutate, notify_client, notify_team, owned
from accounts.services.package_commerce import SIZES, balances, eligible_order
from accounts.services.package_examples import example_catalog
from content.services import calculator_calibration, requirement_calculator


def proposal_payload(row):
    try:
        decision = row.decision
    except PackageDecision.DoesNotExist:
        decision = None
    return {'id': row.pk, **row.public_snapshot, 'warranty': row.warranty,
            'created_at': row.created_at.isoformat(),
            'decision': {'decision': decision.decision, 'message': decision.message,
                         'created_at': decision.created_at.isoformat()} if decision else None}


def request_payload(row, *, detail=False):
    current = row.current_proposal
    available = None
    if current and current.public_snapshot['size'] in SIZES:
        size = current.public_snapshot['size']
        available = eligible_order(row.project, size)
        # Include the allowance a replacement would restore, without writing.
        previous = PackageMovement.objects.filter(decision__proposal__request=row, kind='debit',
            reversal__isnull=True, size=size, order__expires_at__gt=timezone.now(),
            order__status='paid', order__client_id=row.client_id).select_related('order').first()
        if previous and (available is None or (previous.order.expires_at, previous.order.created_at, str(previous.order_id)) <
                        (available.expires_at, available.created_at, str(available.pk))):
            available = previous.order
    result = {'id': row.pk, 'ticket_id': row.ticket_id, 'project_id': row.project_id,
              'project_name': row.project.name, 'title': row.ticket.title,
              'description': row.ticket.description, 'status': row.status, 'version': row.version,
              'proposal': proposal_payload(current) if current else None,
              'created_at': row.created_at.isoformat(),
              'suggested_order_id': str(available.pk) if available else None}
    if detail:
        result['proposals'] = [proposal_payload(proposal) for proposal in row.proposals.select_related('decision')[:50]]
    return result


def request_summary(row):
    return {'id': row.pk, 'ticket_id': row.ticket_id, 'project_id': row.project_id,
            'project_name': row.project.name, 'title': row.ticket.title,
            'status': row.status, 'version': row.version, 'created_at': row.created_at.isoformat()}


def request_queryset(project, *, detail=True):
    rows = PackageRequest.objects.filter(project=project, client_id=project.client_id,
                                         ticket__is_archived=False).select_related('ticket', 'project')
    return rows.select_related('current_proposal__decision') if detail else rows.defer('ticket__description')


def create_request(project_id, actor, data):
    def change(project):
        ticket = ChangeRequest.objects.create(project=project, created_by=actor,
            title=data['title'], description=data['description'])
        save_context(ticket, 'change', None, {'origin_kind': 'package', 'project_id': project.pk})
        row = PackageRequest.objects.create(project=project, client=project.client, ticket=ticket)
        notify_team(project, f'Nueva solicitud: {ticket.title}', request_id=row.pk)
        return request_payload(row)
    return mutate(project_id, actor, 'create_request', data, change)


def begin_evaluation(project_id, actor, request_id, data):
    def change(project):
        row = owned(request_queryset(project).select_for_update(), project, pk=request_id)
        check_version(row, data['expected_version'])
        if row.status not in ('pending', 'objected'):
            raise ValidationError('La solicitud no está pendiente de evaluación.')
        row.status, row.version = 'evaluating', row.version + 1
        row.save()
        row.ticket.status = ChangeRequest.STATUS_EVALUATING
        row.ticket.save(update_fields=['status', 'updated_at'])
        notify_client(project, f'Estamos evaluando: {row.ticket.title}', request_id=row.pk)
        return request_payload(row)
    return mutate(project_id, actor, f'evaluate:{request_id}', data, change, admin=True)


def publish_proposal(project_id, actor, request_id, data):
    def change(project):
        row = owned(request_queryset(project).select_for_update(), project, pk=request_id)
        check_version(row, data['expected_version'])
        if row.status == 'cancelled':
            raise ValidationError('La solicitud está anulada.')
        context = requirement_calculator.calculator_context(project_id=project.pk)
        recorded = calculator_calibration.record_estimate({
            'request_id': data['request_id'], 'revision_id': context['revision_id'],
            'project_id': project.pk, 'project_version_id': context['project_version_id'],
            'definition_digest': context['definition_digest'],
            'requirement': data['scope'], 'size': data['size'], 'signal_ids': data['signal_ids'],
            'explanation': data['explanation'],
        }, actor=actor)
        snapshot = {key: str(data[key]) for key in ('size', 'scope', 'explanation', 'assumptions',
                                                   'delivery_from', 'delivery_until', 'schedule_conditions')}
        examples = example_catalog(project.pk, language=data['language'])
        snapshot['examples'] = next(item['examples'] for item in examples['sizes'] if item['size'] == data['size'])
        snapshot['definition_digest'] = context['definition_digest']
        snapshot['revision_id'] = context['revision_id']
        proposal = PackageSizingProposal.objects.create(request=row, estimate_id=recorded['id'],
            public_snapshot=snapshot, warranty=data['warranty'], author=actor)
        row.current_proposal, row.status, row.version = proposal, 'offered', row.version + 1
        row.save()
        row.ticket.status, row.ticket.admin_response = ChangeRequest.STATUS_EVALUATING, data['explanation']
        row.ticket.estimated_time = f'{data["delivery_from"]} — {data["delivery_until"]}'
        row.ticket.save(update_fields=['status', 'admin_response', 'estimated_time', 'updated_at'])
        notify_client(project, f'Revisa la talla propuesta: {row.ticket.title}', request_id=row.pk)
        return request_payload(row, detail=True)
    return mutate(project_id, actor, f'offer:{request_id}', data, change, admin=True)


def _reverse_previous(row, actor):
    previous = PackageMovement.objects.filter(decision__proposal__request=row, kind='debit',
        reversal__isnull=True).select_related('order').first()
    if previous:
        PackageMovement.objects.create(order=previous.order, size=previous.size, quantity=1,
            kind='reversal', reverses=previous, actor=actor,
            reason='Sustituido por otra propuesta aceptada expresamente por el cliente.')


def decide(project_id, actor, request_id, data, *, impersonated=False):
    if is_admin(actor) or impersonated:
        raise PermissionDenied('La aceptación corresponde al cliente, desde su propia sesión.')

    def change(project):
        if project.client_id != actor.pk:
            raise PermissionDenied('Sólo el titular del proyecto puede decidir.')
        row = owned(request_queryset(project).select_for_update(), project, pk=request_id)
        check_version(row, data['expected_version'])
        proposal = row.current_proposal
        if row.status != 'offered' or not proposal or proposal.pk != data['proposal_id']:
            raise ValidationError('La propuesta ya cambió o fue respondida. Consulta la respuesta vigente.')
        order = None
        size = proposal.public_snapshot['size']
        if data['decision'] == 'accept':
            if not proposal.warranty and size not in SIZES:
                raise ValidationError('L, XL y Proyecto requieren una cotización independiente; no consumen cupos.')
            # Reversing a prior acceptance and debiting its replacement share this transaction.
            _reverse_previous(row, actor)
            if not proposal.warranty:
                order = eligible_order(project, size)
                if order is None:
                    raise ValidationError('No tienes un cupo vigente de esta talla. Puedes comprar otro paquete.')
                if str(order.pk) != str(data.get('order_id', '')):
                    raise ValidationError('El origen del cupo cambió. Revisa el saldo antes de aceptar.')
        decision = PackageDecision.objects.create(proposal=proposal, actor=actor,
            decision=data['decision'], message=data['message'])
        if order:
            PackageMovement.objects.create(order=order, size=size, quantity=-1, kind='debit',
                decision=decision, actor=actor)
        row.status = 'accepted' if data['decision'] == 'accept' else 'objected'
        row.version += 1
        row.save()
        row.ticket.status = ChangeRequest.STATUS_APPROVED if row.status == 'accepted' else ChangeRequest.STATUS_EVALUATING
        row.ticket.save(update_fields=['status', 'updated_at'])
        notify_team(project, f'{"Aceptación" if row.status == "accepted" else "Objeción"}: {row.ticket.title}', request_id=row.pk)
        return {'request': request_payload(row, detail=True), 'balances': balances(project)}
    return mutate(project_id, actor, f'decide:{request_id}', data, change)
