"""Optimistic writes to shared proposal sources, under the aggregate lock."""
from functools import wraps
from django.db import transaction
from rest_framework.response import Response
from content.models import BusinessProposal, ProposalDocument, ProposalSection


def proposal_source_write(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        from content.services.proposal_approval_service import source_hash, load_proposal
        proposal_id = kwargs.get('proposal_id')
        if proposal_id is None and kwargs.get('section_id'):
            proposal_id = ProposalSection.objects.filter(pk=kwargs['section_id']).values_list('proposal_id', flat=True).first()
        if proposal_id is None and kwargs.get('doc_id'):
            proposal_id = ProposalDocument.objects.filter(pk=kwargs['doc_id']).values_list('proposal_id', flat=True).first()
        with transaction.atomic():
            proposal = BusinessProposal.objects.select_for_update().filter(pk=proposal_id).first()
            if proposal and proposal.approval_packages.exists():
                expected = request.headers.get('X-Proposal-Version') or request.headers.get('If-Match') or request.data.get('source_hash')
                actual = source_hash(load_proposal(proposal_id))
                if expected != actual:
                    return Response({'detail': 'La propuesta cambió. Conserva tus cambios y revisa la versión actual.',
                                     'code': 'stale_source', 'source_hash': actual}, status=409)
            response = view(request, *args, **kwargs)
            if proposal and 200 <= response.status_code < 300:
                response['X-Proposal-Version'] = source_hash(load_proposal(proposal_id))
            return response
    return guarded
