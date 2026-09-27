"""The formalization package carries the contracts of the deal's closing modality."""
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile

from content.models import ProposalDocument
from content.services.formalization_content import FormalContent, FormalizationError
from content.services.proposal_formalization_service import (
    availability,
    prepare,
    send_preparation,
)

pytestmark = pytest.mark.django_db

PARAMS = {
    'contractor_full_name': 'ProjectApp S.A.S.', 'contractor_email': 'legal@projectapp.co',
    'contract_city': 'Medellín', 'bank_name': 'Banco de Prueba', 'bank_account_number': '123456789',
    'contractor_nit': '900123456-7', 'client_full_name': 'Acme Corp', 'client_cedula': '1234567890',
    'client_email': 'contact@acme.com', 'contract_date': '2026-09-26',
}
SERVICE_TERMS = {
    'service_initial_term': 'doce (12) meses',
    'service_renewal_notice_days': 'treinta (30)',
    'service_termination_notice_days': 'treinta (30)',
}


@pytest.fixture
def payload():
    return {
        'documents': ['contract_product', 'contract_service'],
        'additional_doc_ids': [],
        'subject': 'Documentación para formalización',
        'greeting': 'Hola Acme,',
        'body': 'Adjuntamos los contratos para su revisión.',
        'footer': 'Equipo ProjectApp',
        'sections': [],
        'recipient_emails': ['contact@acme.com'],
        'cc_emails': [],
    }


def _store(proposal, doc_type, body=None, generated=True):
    doc = ProposalDocument.objects.create(
        proposal=proposal, document_type=doc_type, title=doc_type, is_generated=generated,
    )
    doc.file.save(f'{doc_type}.pdf', ContentFile(body or f'%PDF-1.4 {doc_type}'.encode()), save=True)
    return doc


@pytest.fixture
def split_proposal(proposal):
    proposal.contract_modality = 'split'
    proposal.contract_params = {**PARAMS, **SERVICE_TERMS}
    proposal.save(update_fields=['contract_modality', 'contract_params'])
    _store(proposal, 'contract_product')
    _store(proposal, 'contract_service')
    return proposal


def test_availability_offers_both_separate_contracts(split_proposal):
    """Fails if a split closing still offers the single contract or hides one of its documents."""
    options = availability(split_proposal)

    assert [option['key'] for option in options] == [
        'contract_product', 'contract_service', 'commercial', 'technical',
    ]
    assert options[0]['available']
    assert options[1]['available']
    assert options[1]['label'] == 'Contrato de servicio (hosting, mantenimiento y soporte)'


def test_prepare_attaches_product_then_service_contract(split_proposal, admin_user, payload):
    """Fails if the frozen package drops a contract or swaps their order."""
    preparation = prepare(split_proposal, admin_user, payload)

    files = list(preparation.files.order_by('pk'))
    assert [item.key for item in files] == ['contract_product', 'contract_service']
    assert files[0].filename.startswith('Contrato de producto')
    assert preparation.payload['_source_version'] == 3


def test_prepare_rejects_the_contract_of_the_other_modality(split_proposal, admin_user, payload):
    """Fails if a split closing can send the single contract it no longer keeps current."""
    _store(split_proposal, 'contract')

    with pytest.raises(FormalizationError) as error:
        prepare(split_proposal, admin_user, {**payload, 'documents': ['contract']})

    assert error.value.code == 'modality_mismatch'


def test_service_contract_needs_its_terms_before_sending(split_proposal, admin_user, payload):
    """Fails if the service contract travels to the client with a blank duration or notice."""
    split_proposal.contract_params = dict(PARAMS)
    split_proposal.save(update_fields=['contract_params'])

    with pytest.raises(FormalizationError) as error:
        prepare(split_proposal, admin_user, payload)

    assert error.value.code == 'contract_incomplete'
    assert 'service_initial_term' in str(error.value)


def test_a_separate_contract_cannot_ride_as_an_extra_attachment(split_proposal, admin_user, payload):
    """Fails if an extra attachment duplicates a contract outside its main checkbox."""
    product = ProposalDocument.objects.get(proposal=split_proposal, document_type='contract_product')

    with pytest.raises(FormalizationError) as error:
        prepare(split_proposal, admin_user, {
            **payload, 'documents': ['contract_service'], 'additional_doc_ids': [product.pk],
        })

    assert error.value.code == 'duplicate_contract'


@patch('content.services.proposal_formalization_service.EmailDeliveryGateway.send')
def test_switching_modality_makes_a_prepared_package_stale(delivery, split_proposal, admin_user, payload):
    """Fails if a package reviewed for two contracts can be sent after returning to one."""
    preparation = prepare(split_proposal, admin_user, payload)
    split_proposal.contract_modality = 'single'
    split_proposal.save(update_fields=['contract_modality'])

    with pytest.raises(FormalizationError) as error:
        send_preparation(preparation)

    assert error.value.code == 'stale_preparation'
    assert error.value.status == 409
    delivery.assert_not_called()


def test_commercial_annex_points_at_both_contracts_when_split(split_proposal):
    """Fails if the curated annex still defers obligations to a single development contract."""
    note = FormalContent(split_proposal).contract_note()

    assert 'contrato de producto' in note
    assert 'contrato de servicio (hosting, mantenimiento y soporte)' in note


def test_commercial_annex_points_at_the_single_contract_by_default(proposal):
    """Fails if a non-split proposal's annex note describes the two-contract split instead."""
    note = FormalContent(proposal).contract_note()

    assert note == (
        'Las garantías y obligaciones se rigen por el contrato de desarrollo de '
        'software asociado a esta propuesta.'
    )
