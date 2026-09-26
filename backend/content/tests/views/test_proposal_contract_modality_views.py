"""A negotiated deal closes with one contract or with a product and a service contract."""
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from content.models import ContractTemplate, ProposalChangeLog, ProposalDocument

pytestmark = pytest.mark.django_db

PARTY_PARAMS = {
    'contract_source': 'default',
    'client_full_name': 'Cliente Negociador',
    'client_cedula': '1.020.304.050',
    'client_email': 'cliente@example.com',
    'contractor_full_name': 'Project App S.A.S.',
    'contractor_nit': '900.123.456-7',
    'contractor_email': 'team@example.com',
    'bank_name': 'Banco',
    'bank_account_type': 'Ahorros',
    'bank_account_number': '123-456',
    'contract_city': 'Medellín',
    'contract_date': '2026-09-26',
}
SERVICE_TERMS = {
    'service_initial_term': 'doce (12) meses',
    'service_renewal_notice_days': 'treinta (30)',
    'service_termination_notice_days': 'quince (15)',
}


def _modality_url(proposal):
    return reverse('update-contract-modality', kwargs={'proposal_id': proposal.pk})


def _update_url(proposal):
    return reverse('update-contract-params', kwargs={'proposal_id': proposal.pk})


@pytest.fixture
def negotiated(negotiating_proposal):
    negotiating_proposal.contract_params = dict(PARTY_PARAMS)
    negotiating_proposal.save(update_fields=['contract_params'])
    return negotiating_proposal


@pytest.fixture
def split_proposal(negotiated):
    negotiated.contract_params = {**PARTY_PARAMS, **SERVICE_TERMS}
    negotiated.contract_modality = 'split'
    negotiated.save(update_fields=['contract_params', 'contract_modality'])
    return negotiated


def _stored_contract(proposal, doc_type, body=b'%PDF-1.4 stored'):
    doc = ProposalDocument.objects.create(
        proposal=proposal, document_type=doc_type, title=doc_type, is_generated=True,
        content_markdown=f'# {doc_type}',
    )
    doc.file.save(f'{doc_type}.pdf', ContentFile(body), save=True)
    return doc


def test_switching_to_split_generates_the_product_contract_and_logs_it(admin_client, negotiated):
    """Fails if the switch persists without producing the product document or its audit entry."""
    response = admin_client.patch(_modality_url(negotiated), {'contract_modality': 'split'}, format='json')

    assert response.status_code == 200
    assert response.data['contract_modality'] == 'split'
    product = ProposalDocument.objects.get(proposal=negotiated, document_type='contract_product')
    assert product.content_markdown.startswith('# CONTRATO DE PRESTACIÓN DE SERVICIOS')
    assert 'VIGÉSIMA PRIMERA' not in product.content_markdown
    assert not ProposalDocument.objects.filter(proposal=negotiated, document_type='contract_service').exists()
    assert ProposalChangeLog.objects.filter(proposal=negotiated, field_name='contract_modality', new_value='split').exists()


@patch('content.views.proposal._generate_and_save_contract_pdf')
def test_switching_back_keeps_the_separate_documents(mock_generate, admin_client, split_proposal):
    """Fails if returning to the single contract deletes the product or service documents."""
    _stored_contract(split_proposal, 'contract_product')
    _stored_contract(split_proposal, 'contract_service')

    response = admin_client.patch(_modality_url(split_proposal), {'contract_modality': 'single'}, format='json')

    assert response.status_code == 200
    assert ProposalDocument.objects.filter(proposal=split_proposal, document_type__startswith='contract_').count() == 2
    mock_generate.assert_called_once_with(split_proposal, 'combined')


@pytest.mark.parametrize('fixture_name', ['sent_proposal', 'accepted_proposal', 'rejected_proposal'])
def test_modality_is_locked_outside_negotiation(admin_client, request, fixture_name):
    """Fails if the closing modality changes after (or before) the negotiation."""
    proposal = request.getfixturevalue(fixture_name)

    response = admin_client.patch(_modality_url(proposal), {'contract_modality': 'split'}, format='json')

    proposal.refresh_from_db()
    assert response.status_code == 409
    assert response.data['code'] == 'modality_locked'
    assert proposal.contract_modality == 'single'


def test_rejects_an_unknown_modality(admin_client, negotiated):
    """Fails if a typo is stored as a closing modality."""
    response = admin_client.patch(_modality_url(negotiated), {'contract_modality': 'double'}, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'invalid_modality'


def test_split_is_refused_without_a_standalone_service_text(admin_client, negotiated):
    """Fails if the switch offers two documents the template cannot produce."""
    ContractTemplate.objects.filter(is_default=True).update(service_content_markdown='')

    response = admin_client.patch(_modality_url(negotiated), {'contract_modality': 'split'}, format='json')

    negotiated.refresh_from_db()
    assert response.status_code == 409
    assert response.data['code'] == 'split_unavailable'
    assert negotiated.contract_modality == 'single'


@patch('content.views.proposal._generate_and_save_contract_pdf')
def test_repeating_the_current_modality_changes_nothing(mock_generate, admin_client, negotiated):
    """Fails if a repeated click regenerates documents or writes a phantom audit entry."""
    response = admin_client.patch(_modality_url(negotiated), {'contract_modality': 'single'}, format='json')

    assert response.status_code == 200
    mock_generate.assert_not_called()
    assert not ProposalChangeLog.objects.filter(proposal=negotiated, field_name='contract_modality').exists()


def test_modality_requires_an_admin(api_client, negotiated):
    """Fails if an anonymous caller can decide how a deal closes."""
    response = api_client.patch(_modality_url(negotiated), {'contract_modality': 'split'}, format='json')

    assert response.status_code == 401


def test_generating_the_service_contract_needs_its_three_terms(admin_client, negotiated):
    """Fails if the service contract is generated with blank duration or notices."""
    negotiated.contract_modality = 'split'
    negotiated.save(update_fields=['contract_modality'])

    response = admin_client.patch(
        _update_url(negotiated), {'contract_params': {}, 'variant': 'service'}, format='json',
    )

    assert response.status_code == 400
    assert set(response.data) == {
        'service_initial_term', 'service_renewal_notice_days', 'service_termination_notice_days',
    }


def test_editing_one_document_keeps_the_other_documents_data(admin_client, negotiated):
    """Fails if saving the service terms drops a custom product text saved before."""
    negotiated.contract_modality = 'split'
    negotiated.contract_params = {
        **PARTY_PARAMS,
        'product_contract_source': 'custom',
        'product_custom_contract_markdown': '# Contrato de producto negociado',
    }
    negotiated.save(update_fields=['contract_modality', 'contract_params'])

    response = admin_client.patch(
        _update_url(negotiated), {'contract_params': SERVICE_TERMS, 'variant': 'service'}, format='json',
    )

    negotiated.refresh_from_db()
    assert response.status_code == 200
    assert negotiated.contract_params['product_custom_contract_markdown'] == '# Contrato de producto negociado'
    service = ProposalDocument.objects.get(proposal=negotiated, document_type='contract_service')
    assert 'duración inicial de doce (12) meses' in service.content_markdown
    product = ProposalDocument.objects.get(proposal=negotiated, document_type='contract_product')
    assert product.content_markdown == '# Contrato de producto negociado'


def test_a_custom_separate_document_needs_its_own_text(admin_client, split_proposal):
    """Fails if the service contract switches to a custom text without providing it."""
    response = admin_client.patch(
        _update_url(split_proposal),
        {'contract_params': {'service_contract_source': 'custom'}, 'variant': 'service'},
        format='json',
    )

    assert response.status_code == 400
    assert 'service_custom_contract_markdown' in response.data


def test_update_refuses_a_document_of_the_other_modality(admin_client, negotiated):
    """Fails if the single-contract proposal can generate a separate document."""
    response = admin_client.patch(
        _update_url(negotiated), {'contract_params': SERVICE_TERMS, 'variant': 'service'}, format='json',
    )

    assert response.status_code == 409
    assert response.data['code'] == 'inactive_variant'


@patch('content.views.proposal._generate_and_save_contract_pdf')
def test_first_generation_during_negotiation_uses_update(mock_generate, admin_client, negotiating_proposal):
    """Fails if a client-started negotiation, with no contract yet, cannot generate one."""
    response = admin_client.patch(
        _update_url(negotiating_proposal), {'contract_params': PARTY_PARAMS}, format='json',
    )

    assert response.status_code == 200
    mock_generate.assert_called_once_with(negotiating_proposal, 'combined')


def test_split_download_names_the_document(admin_client, split_proposal):
    """Fails if a split closing serves a document without saying which one."""
    _stored_contract(split_proposal, 'contract_service', b'%PDF-1.4 service')
    url = reverse('download-contract-pdf', kwargs={'proposal_id': split_proposal.pk})

    missing = admin_client.get(url)
    served = admin_client.get(url, {'variant': 'service'})

    assert missing.status_code == 400
    assert missing.data['code'] == 'variant_required'
    assert served.status_code == 200
    assert b''.join(served.streaming_content if served.streaming else [served.content]) == b'%PDF-1.4 service'
    assert 'Contrato_Servicio_Hosting' in served['Content-Disposition']


def test_documents_of_the_other_modality_are_not_served(admin_client, split_proposal):
    """Fails if the stale single contract of a split closing can still be downloaded."""
    _stored_contract(split_proposal, 'contract')
    url = reverse('download-contract-pdf', kwargs={'proposal_id': split_proposal.pk})

    response = admin_client.get(url, {'variant': 'combined'})

    assert response.status_code == 409
    assert response.data['code'] == 'inactive_variant'


def test_markdown_copy_follows_the_requested_document(admin_client, split_proposal):
    """Fails if copying the product contract returns another document's text."""
    _stored_contract(split_proposal, 'contract_product')
    url = reverse('contract-markdown', kwargs={'proposal_id': split_proposal.pk})

    response = admin_client.get(url, {'variant': 'product'})

    assert response.status_code == 200
    assert '# contract_product' in response.data['markdown']


def test_generated_contract_types_cannot_be_uploaded(admin_client, negotiated):
    """Fails if an upload impersonates the product or service contract."""
    upload = SimpleUploadedFile('p.pdf', b'%PDF-1.4', content_type='application/pdf')
    url = reverse('upload-proposal-document', kwargs={'proposal_id': negotiated.pk})

    response = admin_client.post(url, {'file': upload, 'document_type': 'contract_product'})

    assert response.status_code == 400
