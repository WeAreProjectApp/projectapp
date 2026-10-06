"""Session-owned previews and immutable contract recovery for the panel."""
from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import BusinessProposal, ProposalContractChangeIntent, ProposalContractSnapshot
from content.serializers.proposal import ProposalDetailSerializer
from content.services import proposal_contract_modality as service


def error_response(exc):
    return Response({'error': str(exc), 'code': exc.code, 'details': exc.details, **exc.details}, status=exc.status)


def proposal_response(proposal, result, request):
    detail = ProposalDetailSerializer(proposal, context={'request': request, 'is_admin': True}).data
    return {**detail, 'contract_change': result}


@api_view(['POST'])
@permission_classes([IsAdminUser])
def preview_contract_change(request, proposal_id):
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    arguments = dict(request.data)
    restore = 'snapshot_id' in arguments
    try:
        plan = service.prepare(proposal, arguments, restore=restore)
    except service.ContractModalityError as exc:
        return error_response(exc)
    intent = ProposalContractChangeIntent.objects.create(proposal=proposal, owner=request.user,
        arguments={'payload': plan['arguments'], 'restore': restore}, source_hash=plan['source_hash'],
        expires_at=timezone.now() + timedelta(minutes=10))
    return Response({'confirmation_id': str(intent.pk), 'expires_at': intent.expires_at.isoformat(), 'impact': plan})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def confirm_contract_change(request, proposal_id):
    try:
        identifier = UUID(str(request.data.get('confirmation_id')))
    except (ValueError, TypeError, AttributeError):
        return Response({'error': 'Selecciona una confirmación válida.'}, status=400)
    with transaction.atomic():
        intent = get_object_or_404(ProposalContractChangeIntent.objects.select_for_update(),
                                  pk=identifier, proposal_id=proposal_id, owner=request.user)
        if intent.status == 'executed':
            return Response(intent.result)
        if intent.status != 'pending' or intent.expires_at <= timezone.now():
            return Response({'error': 'La confirmación venció o fue cancelada.', 'code': 'CONFIRMATION_EXPIRED'}, status=409)
        try:
            proposal, result = service.apply(proposal_id, intent.arguments['payload'], actor=request.user,
                confirmed=True, expected_hash=intent.source_hash, restore=intent.arguments['restore'])
        except service.ContractModalityError as exc:
            return error_response(exc)
        intent.status, intent.result = 'executed', proposal_response(proposal, result, request)
        intent.save(update_fields=['status', 'result'])
    return Response(intent.result)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def cancel_contract_change(request, proposal_id):
    try:
        identifier = UUID(str(request.data.get('confirmation_id')))
    except (ValueError, TypeError, AttributeError):
        return Response({'error': 'Selecciona una confirmación válida.'}, status=400)
    changed = ProposalContractChangeIntent.objects.filter(pk=identifier, owner=request.user,
        proposal_id=proposal_id, status='pending').update(status='cancelled')
    if not changed:
        return Response({'error': 'No existe esa confirmación pendiente.'}, status=404)
    return Response({'cancelled': True})


def snapshot_summary(snapshot):
    return {'snapshot_id': snapshot.pk, 'created_at': snapshot.created_at.isoformat(),
        'actor': snapshot.actor_label, 'source': snapshot.source, 'change_note': snapshot.change_note,
        'from_modality': snapshot.from_modality, 'to_modality': snapshot.to_modality,
        'restored_from_id': snapshot.restored_from_id}


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_contract_snapshots(request, proposal_id):
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    try:
        offset = int(request.query_params.get('offset', 0))
        if offset < 0:
            raise ValueError
    except ValueError:
        return Response({'error': 'offset debe ser un entero positivo o cero.'}, status=400)
    rows = proposal.contract_snapshots.all()
    return Response({'total': rows.count(), 'snapshots': [snapshot_summary(row) for row in rows[offset:offset + 20]]})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def read_contract_snapshot(request, proposal_id, snapshot_id):
    row = get_object_or_404(ProposalContractSnapshot, pk=snapshot_id, proposal_id=proposal_id)
    return Response({**snapshot_summary(row), 'payload': row.payload})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def download_contract_snapshot(request, proposal_id, snapshot_id, document_id):
    row = get_object_or_404(ProposalContractSnapshot, pk=snapshot_id, proposal_id=proposal_id)
    file = get_object_or_404(row.files, source_document_id=document_id)
    response = HttpResponse(bytes(file.pdf_content), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="contract-snapshot-{snapshot_id}-{document_id}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response
