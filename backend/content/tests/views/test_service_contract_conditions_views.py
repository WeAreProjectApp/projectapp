"""Contract endpoints reject service documents whose economic inputs are incomplete."""

import pytest
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from content.models import ProposalDocument, ProposalSection
from content.services.contract_pdf_service import resolve_contract_content

pytestmark = pytest.mark.django_db


SERVICE_TERMS = {
    'contractor_full_name': 'ProjectApp S.A.S.',
    'contractor_nit': '900123456-7',
    'client_full_name': 'Acme Corp',
    'client_cedula': '1234567890',
    'contract_date': '2026-09-29',
    'service_initial_term': 'doce (12) meses',
    'service_renewal_notice_days': 'treinta (30)',
    'service_termination_notice_days': 'treinta (30)',
}


def _ordinary_documents(proposal):
    return [
        ProposalDocument(
            proposal=proposal,
            document_type=ProposalDocument.DOC_TYPE_LEGAL_ANNEX,
            title=f'Anexo {number}',
        )
        for number in range(20)
    ]


@pytest.fixture
def split_proposal_without_hosting_price(negotiating_proposal):
    negotiating_proposal.contract_modality = 'split'
    negotiating_proposal.total_investment = 0
    negotiating_proposal.save(update_fields=['contract_modality', 'total_investment'])
    ProposalSection.objects.create(
        proposal=negotiating_proposal,
        section_type='investment',
        title='Inversión',
        order=1,
        content_json={'hostingPlan': {'billingTiers': [{'label': 'Trimestral', 'months': 3}]}},
    )
    return negotiating_proposal


def test_updating_service_contract_rejects_missing_hosting_conditions(
    admin_client, split_proposal_without_hosting_price,
):
    """Fails if the service endpoint stores terms while the price alternatives cannot be rendered."""
    response = admin_client.patch(
        reverse('update-contract-params', kwargs={'proposal_id': split_proposal_without_hosting_price.pk}),
        {'contract_params': SERVICE_TERMS, 'variant': 'service'},
        format='json',
    )

    split_proposal_without_hosting_price.refresh_from_db()
    assert response.status_code == 422
    assert response.data['code'] == 'service_conditions_missing'
    assert split_proposal_without_hosting_price.contract_params == {}


def test_service_draft_rejects_missing_hosting_conditions(
    admin_client, split_proposal_without_hosting_price,
):
    """Fails if the draft endpoint presents a service PDF whose required price options are absent."""
    response = admin_client.get(
        reverse('download-draft-contract-pdf', kwargs={'proposal_id': split_proposal_without_hosting_price.pk}),
        {'variant': 'service'},
    )

    assert response.status_code == 422
    assert response.data['code'] == 'service_conditions_missing'


def test_switching_to_split_rejects_missing_service_conditions(
    admin_client, split_proposal_without_hosting_price,
):
    """Fails if changing modality persists a split deal after the service conditions cannot render."""
    split_proposal_without_hosting_price.contract_modality = 'single'
    split_proposal_without_hosting_price.contract_params = SERVICE_TERMS
    split_proposal_without_hosting_price.save(update_fields=['contract_modality', 'contract_params'])

    response = admin_client.patch(
        reverse('update-contract-modality', kwargs={'proposal_id': split_proposal_without_hosting_price.pk}),
        {'contract_modality': 'split'},
        format='json',
    )

    split_proposal_without_hosting_price.refresh_from_db()
    assert response.status_code == 422
    assert response.data['code'] == 'service_conditions_missing'
    assert split_proposal_without_hosting_price.contract_modality == 'single'
    assert not split_proposal_without_hosting_price.proposal_documents.filter(
        document_type='contract_service',
    ).exists()


def test_negotiation_start_rejects_missing_service_conditions(
    admin_client, sent_proposal,
):
    """Fails if negotiation starts after the service price alternatives fail to resolve."""
    sent_proposal.contract_modality = 'split'
    sent_proposal.total_investment = 0
    sent_proposal.save(update_fields=['contract_modality', 'total_investment'])
    ProposalSection.objects.create(
        proposal=sent_proposal, section_type='investment', title='Inversión', order=1,
        content_json={'hostingPlan': {'billingTiers': [{'label': 'Trimestral', 'months': 3}]}},
    )

    response = admin_client.post(
        reverse('save-contract-and-negotiate', kwargs={'proposal_id': sent_proposal.pk}),
        {'contract_params': SERVICE_TERMS},
        format='json',
    )

    sent_proposal.refresh_from_db()
    assert response.status_code == 422
    assert response.data['code'] == 'service_conditions_missing'
    assert sent_proposal.status == 'sent'
    assert sent_proposal.contract_params == {}
    assert not sent_proposal.proposal_documents.exists()


def test_document_list_keeps_constant_queries_as_unrelated_documents_grow(
    admin_client, negotiating_proposal, contract_template,
):
    """Fails if each additional document recomputes the service snapshot in the Documents tab."""
    proposal = negotiating_proposal
    proposal.contract_modality = 'split'
    proposal.hosting_percent = 10
    proposal.contract_params = SERVICE_TERMS
    proposal.save()
    ProposalSection.objects.create(
        proposal=proposal, section_type='investment', title='Inversión', order=1,
        content_json={'hostingPlan': {'billingTiers': [{'label': 'Cada 9 meses', 'months': 9}]}},
    )
    service = ProposalDocument.objects.create(
        proposal=proposal,
        document_type=ProposalDocument.DOC_TYPE_CONTRACT_SERVICE,
        title='Contrato de servicio',
        is_generated=True,
        content_markdown=resolve_contract_content(proposal, variant='service')['snapshot'],
    )
    service.file.save('service.pdf', ContentFile(b'%PDF-1.4 snapshot'), save=True)
    url = reverse('list-proposal-documents', kwargs={'proposal_id': proposal.pk})

    with CaptureQueriesContext(connection) as one_document:
        response = admin_client.get(url)

    ProposalDocument.objects.bulk_create(_ordinary_documents(proposal))
    with CaptureQueriesContext(connection) as twenty_one_documents:
        response = admin_client.get(url)

    assert response.status_code == 200
    assert len(one_document) == len(twenty_one_documents)
    assert len(twenty_one_documents) <= 6
