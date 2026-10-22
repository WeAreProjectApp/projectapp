"""Administrative windows onto the same proposal sources and approved revisions."""
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import serializers
from content.models import Document, BusinessProposal
from content.services.proposal_shared_documents import binding_for, reconfirm, summary
from content.views.proposal_approval import decode_payload, _download


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def document_proposal_source(request, document_id):
    document = get_object_or_404(Document, pk=document_id)
    binding = binding_for(document)
    if binding is None:
        return Response({'detail': 'Este documento no pertenece a un cierre de propuesta.'}, status=404)
    if request.method == 'POST':
        from content.services.proposal_shared_documents import replace_binary_source
        binding = replace_binary_source(binding.pk, request.data, request.FILES.get('file'), actor=request.user)
    from content.services.proposal_approval_service import preview, load_proposal
    return Response({'document': summary(binding), 'approval': preview(load_proposal(binding.proposal_id))})


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def confirm_proposal_revision(request, proposal_id):
    get_object_or_404(BusinessProposal, pk=proposal_id)
    files = request.FILES.getlist('custom_files[]') or request.FILES.getlist('custom_files')
    package = reconfirm(proposal_id, decode_payload(request), actor=request.user, files=files)
    from content.services.proposal_approval_service import preview, load_proposal
    return Response(dict(preview(load_proposal(proposal_id)), confirmed_package=package.number))


class ProposalReconciliationSerializer(serializers.Serializer):
    expected_hash = serializers.CharField(min_length=64, max_length=64)


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def reconcile_proposal_documents(request, proposal_id):
    get_object_or_404(BusinessProposal, pk=proposal_id)
    from content.services import proposal_document_reconciliation as service
    from content.services.proposal_approval_service import load_proposal
    if request.method == 'GET':
        return Response(service.preview(load_proposal(proposal_id)))
    payload = ProposalReconciliationSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    return Response(service.reconcile(proposal_id, actor=request.user, **payload.validated_data))


def shared_document_download(document):
    binding = binding_for(document)
    if binding is None:
        return None
    if not binding.current_file:
        return Response({'detail': 'El documento aún no tiene una revisión aprobada.'}, status=409)
    return _download(binding.current_file)
