"""Contract modality changes preserve contract evidence in every proposal state."""

import copy

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from content.models import (
    ContractTemplate,
    ProposalContractSnapshot,
    ProposalDocument,
    ProposalSection,
)

pytestmark = pytest.mark.django_db

PARTY_PARAMS = {
    'client_full_name': 'Cliente Negociador', 'client_cedula': '1.020.304.050',
    'client_email': 'cliente@example.com', 'contractor_full_name': 'Project App S.A.S.',
    'contractor_nit': '900.123.456-7', 'contractor_email': 'team@example.com',
    'bank_name': 'Banco', 'bank_account_type': 'Ahorros', 'bank_account_number': '123-456',
    'contract_city': 'Medellín', 'contract_date': '2026-09-26',
}
SERVICE_TERMS = {
    'service_initial_term': 'doce (12) meses',
    'service_renewal_notice_days': 'treinta (30)',
    'service_termination_notice_days': 'quince (15)',
}


def _url(proposal, name):
    return reverse(name, kwargs={'proposal_id': proposal.pk})


def _update_url(proposal):
    return reverse('update-contract-params', kwargs={'proposal_id': proposal.pk})


def _store_contract(proposal, document_type, markdown, pdf):
    document = ProposalDocument.objects.create(
        proposal=proposal, document_type=document_type, title=document_type,
        is_generated=True, content_markdown=markdown,
    )
    document.file.save(f'{proposal.pk}-{document_type}.pdf', ContentFile(pdf), save=True)
    return document


def _ready_for_service(proposal):
    ProposalSection.objects.create(
        proposal=proposal, section_type='investment', title='Inversión', order=1,
        content_json={'hostingPlan': {'billingTiers': [{'label': 'Mensual', 'months': 1}]}},
    )
    return proposal


def _fake_pdf(_proposal, *, resolved_content, **_kwargs):
    return b'%PDF-1.4 generated\n' + resolved_content['snapshot'].encode()


@pytest.fixture
def ready_accepted(accepted_proposal, contract_template):
    contract_template.product_content_markdown = '# Producto para {client_full_name}'
    contract_template.save(update_fields=['product_content_markdown'])
    accepted_proposal.contract_params = dict(PARTY_PARAMS)
    accepted_proposal.save(update_fields=['contract_params'])
    return _ready_for_service(accepted_proposal)


@pytest.fixture
def ready_negotiating(negotiating_proposal, contract_template):
    contract_template.product_content_markdown = '# Producto para {client_full_name}'
    contract_template.save(update_fields=['product_content_markdown'])
    negotiating_proposal.contract_params = dict(PARTY_PARAMS)
    negotiating_proposal.save(update_fields=['contract_params'])
    return _ready_for_service(negotiating_proposal)


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


def _preview(client, proposal, payload):
    return client.post(_url(proposal, 'preview-contract-change'), payload, format='json')


def _confirm(client, proposal, confirmation_id):
    return client.post(_url(proposal, 'confirm-contract-change'), {'confirmation_id': confirmation_id}, format='json')


def test_accepted_custom_combined_contract_moves_literal_text_and_pdf_to_product(
    admin_client, ready_accepted, monkeypatch,
):
    """Fails if changing an accepted proposal rewrites negotiated custom product wording or its PDF."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _fake_pdf)
    markdown = '# Texto\n\nCon espacios finales  \n'
    pdf = b'%PDF-1.4 signed custom bytes\x00'
    proposal = ready_accepted
    proposal.contract_params = {**PARTY_PARAMS, 'contract_source': 'custom', 'custom_contract_markdown': markdown}
    proposal.save(update_fields=['contract_params'])
    _store_contract(proposal, 'contract', markdown, pdf)

    preview = _preview(admin_client, proposal, {
        'contract_modality': 'split', 'change_note': 'Separar documentos firmados',
        'contract_params': SERVICE_TERMS,
    })
    _confirm(admin_client, proposal, preview.data['confirmation_id'])

    proposal.refresh_from_db()
    product = proposal.proposal_documents.get(document_type='contract_product', is_archived=False)
    service = proposal.proposal_documents.get(document_type='contract_service', is_archived=False)
    assert proposal.contract_modality == 'split'
    assert proposal.contract_params['product_contract_source'] == 'custom'
    assert product.content_markdown == markdown
    assert product.file.read() == pdf
    assert proposal.contract_params['service_contract_source'] == 'default'
    assert {key: proposal.contract_params[key] for key in SERVICE_TERMS} == SERVICE_TERMS
    assert service.content_markdown.startswith('# CONTRATO DE PRESTACIÓN DEL SERVICIO')


def test_split_preview_rejects_blank_service_terms_without_changing_contract_evidence(
    admin_client, ready_accepted,
):
    """Fails if modality conversion fills service terms from company defaults or creates a partial change."""
    proposal = ready_accepted
    original = _store_contract(proposal, 'contract', '# Existing', b'%PDF-1.4 existing')
    before_params = copy.deepcopy(proposal.contract_params)

    response = _preview(admin_client, proposal, {
        'contract_modality': 'split', 'change_note': 'Datos pendientes',
        'contract_params': {key: ' ' for key in SERVICE_TERMS},
    })

    proposal.refresh_from_db()
    assert response.status_code == 422
    assert set(response.data['details']) == {
        'service_initial_term', 'service_renewal_notice_days', 'service_termination_notice_days',
    }
    assert proposal.contract_modality == 'single'
    assert proposal.contract_params == before_params
    assert proposal.proposal_documents.get(pk=original.pk).file.read() == b'%PDF-1.4 existing'
    assert ProposalContractSnapshot.objects.filter(proposal=proposal).count() == 0


def test_template_transition_archives_previous_rows_without_changing_template_or_other_proposal(
    admin_client, ready_negotiating, proposal, monkeypatch,
):
    """Fails if a template transition edits its template, another proposal, or deletes historical contract rows."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _fake_pdf)
    source = _store_contract(ready_negotiating, 'contract', '# Previous combined', b'%PDF-1.4 old')
    unrelated = _store_contract(proposal, 'contract', '# Other proposal', b'%PDF-1.4 other')
    template = ContractTemplate.get_default()
    template_before = (template.content_markdown, template.product_content_markdown, template.service_content_markdown)

    admin_client.patch(_url(ready_negotiating, 'update-contract-modality'), {
        'contract_modality': 'split', 'contract_params': SERVICE_TERMS,
    }, format='json')

    ready_negotiating.refresh_from_db()
    source.refresh_from_db()
    template.refresh_from_db()
    product = ready_negotiating.proposal_documents.get(document_type='contract_product', is_archived=False)
    service = ready_negotiating.proposal_documents.get(document_type='contract_service', is_archived=False)
    assert source.is_archived is True
    assert service.content_markdown.startswith('# CONTRATO DE PRESTACIÓN DEL SERVICIO')
    assert (template.content_markdown, template.product_content_markdown, template.service_content_markdown) == template_before
    assert ProposalDocument.objects.get(pk=unrelated.pk).file.read() == b'%PDF-1.4 other'

    admin_client.patch(_url(ready_negotiating, 'update-contract-modality'), {'contract_modality': 'single'}, format='json')

    product.refresh_from_db()
    service.refresh_from_db()
    combined = ready_negotiating.proposal_documents.get(document_type='contract', is_archived=False)
    assert product.is_archived is True
    assert service.is_archived is True
    assert combined.content_markdown.startswith('# CONTRATO DE PRESTACIÓN DE SERVICIOS')


def test_custom_destination_conflict_requires_explicit_resolution_without_writing(
    admin_client, ready_negotiating,
):
    """Fails if custom product terms overwrite distinct custom combined terms without an explicit decision."""
    proposal = ready_negotiating
    proposal.contract_modality = 'split'
    proposal.contract_params = {
        **PARTY_PARAMS, **SERVICE_TERMS, 'product_contract_source': 'custom',
        'product_custom_contract_markdown': '# Product wording', 'contract_source': 'custom',
        'custom_contract_markdown': '# Combined wording',
    }
    proposal.save(update_fields=['contract_modality', 'contract_params'])
    _store_contract(proposal, 'contract_product', '# Product wording', b'%PDF-1.4 product')

    response = _preview(admin_client, proposal, {'contract_modality': 'single'})

    proposal.refresh_from_db()
    assert response.status_code == 409
    assert response.data['code'] == 'CUSTOM_CONTRACT_CONFLICT'
    assert response.data['details'] == {'conflict_resolution': 'use_origin'}
    assert proposal.contract_modality == 'split'
    assert proposal.contract_params['custom_contract_markdown'] == '# Combined wording'
    assert ProposalContractSnapshot.objects.filter(proposal=proposal).count() == 0


def test_custom_product_moves_literal_markdown_and_pdf_to_combined_after_resolution(
    admin_client, ready_negotiating, monkeypatch,
):
    """Fails if split-to-single conversion rewrites custom product evidence after the operator resolves a conflict."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _fake_pdf)
    proposal = ready_negotiating
    product_markdown = '# Product exact\n\nSigned scope  \n'
    product_pdf = b'%PDF-1.4 product evidence\x00'
    proposal.contract_modality = 'split'
    proposal.contract_params = {
        **PARTY_PARAMS, **SERVICE_TERMS, 'product_contract_source': 'custom',
        'product_custom_contract_markdown': product_markdown, 'contract_source': 'custom',
        'custom_contract_markdown': '# Other combined wording',
    }
    proposal.save(update_fields=['contract_modality', 'contract_params'])
    _store_contract(proposal, 'contract_product', product_markdown, product_pdf)

    preview = _preview(admin_client, proposal, {
        'contract_modality': 'single', 'conflict_resolution': 'use_origin',
    })
    response = _confirm(admin_client, proposal, preview.data['confirmation_id'])

    proposal.refresh_from_db()
    combined = proposal.proposal_documents.get(document_type='contract', is_archived=False)
    assert response.status_code == 200
    assert proposal.contract_modality == 'single'
    assert proposal.contract_params['contract_source'] == 'custom'
    assert combined.content_markdown == product_markdown
    assert combined.file.read() == product_pdf


def test_existing_custom_service_is_reused_without_regenerating_its_pdf(admin_client, ready_negotiating, monkeypatch):
    """Fails if single-to-split conversion regenerates an already negotiated custom service contract."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _fake_pdf)
    proposal = ready_negotiating
    service_markdown = '# Service exact\n\nNo template substitution.\n'
    service_pdf = b'%PDF-1.4 service evidence\x00'
    proposal.contract_params = {
        **PARTY_PARAMS, **SERVICE_TERMS, 'contract_source': 'custom',
        'custom_contract_markdown': '# Combined exact', 'service_contract_source': 'custom',
        'service_custom_contract_markdown': service_markdown,
    }
    proposal.save(update_fields=['contract_params'])
    _store_contract(proposal, 'contract', '# Combined exact', b'%PDF-1.4 combined')
    _store_contract(proposal, 'contract_service', service_markdown, service_pdf)

    response = admin_client.patch(_url(proposal, 'update-contract-modality'), {
        'contract_modality': 'split', 'contract_params': SERVICE_TERMS,
    }, format='json')

    proposal.refresh_from_db()
    service = proposal.proposal_documents.get(document_type='contract_service', is_archived=False)
    assert response.status_code == 200
    assert proposal.contract_params['service_contract_source'] == 'custom'
    assert service.content_markdown == service_markdown
    assert service.file.read() == service_pdf


def test_anonymous_caller_cannot_preview_a_contract_change(api_client, ready_accepted):
    """Fails if an unauthenticated caller can inspect or initiate an accepted proposal contract change."""
    response = _preview(api_client, ready_accepted, {
        'contract_modality': 'split', 'change_note': 'Unauthorized', 'contract_params': SERVICE_TERMS,
    })

    assert response.status_code == 401


def test_generating_service_contract_rejects_blank_terms(admin_client, negotiated, company_settings):
    """Fails if the service endpoint generates a contract after every standalone term was cleared."""
    company_settings.service_contract_settings = {
        **company_settings.service_contract_settings,
        'default_duration': '', 'default_renewal_notice': '', 'default_termination_notice': '',
    }
    company_settings.save(update_fields=['service_contract_settings'])
    negotiated.contract_modality = 'split'
    negotiated.save(update_fields=['contract_modality'])

    response = admin_client.patch(_update_url(negotiated), {
        'contract_params': {key: ' ' for key in SERVICE_TERMS}, 'variant': 'service',
    }, format='json')

    assert response.status_code == 400
    assert set(response.data) == {
        'service_initial_term', 'service_renewal_notice_days', 'service_termination_notice_days',
    }


def test_generating_service_contract_uses_company_term_defaults(admin_client, negotiated, company_settings):
    """Fails if ordinary service-document generation stops applying configured company defaults."""
    company_settings.service_contract_settings = {
        'duration_options': [6, 12], 'notice_options': [30, 60],
        'default_duration': 12, 'default_renewal_notice': 30, 'default_termination_notice': 60,
    }
    company_settings.save(update_fields=['service_contract_settings'])
    negotiated.contract_modality = 'split'
    negotiated.save(update_fields=['contract_modality'])

    response = admin_client.patch(_update_url(negotiated), {'contract_params': {}, 'variant': 'service'}, format='json')

    negotiated.refresh_from_db()
    service = ProposalDocument.objects.get(proposal=negotiated, document_type='contract_service')
    assert response.status_code == 200
    assert {key: negotiated.contract_params[key] for key in SERVICE_TERMS} == {
        'service_initial_term': 'doce (12) meses',
        'service_renewal_notice_days': 'treinta (30)',
        'service_termination_notice_days': 'sesenta (60)',
    }
    assert 'duración inicial de doce (12) meses' in service.content_markdown


def test_service_term_update_preserves_custom_product_markdown(admin_client, negotiated):
    """Fails if saving service terms drops independently negotiated product contract text."""
    negotiated.contract_modality = 'split'
    negotiated.contract_params = {
        **PARTY_PARAMS, 'product_contract_source': 'custom',
        'product_custom_contract_markdown': '# Contrato de producto negociado',
    }
    negotiated.save(update_fields=['contract_modality', 'contract_params'])

    response = admin_client.patch(_update_url(negotiated), {
        'contract_params': SERVICE_TERMS, 'variant': 'service',
    }, format='json')

    negotiated.refresh_from_db()
    product = ProposalDocument.objects.get(proposal=negotiated, document_type='contract_product')
    assert response.status_code == 200
    assert negotiated.contract_params['product_custom_contract_markdown'] == '# Contrato de producto negociado'
    assert product.content_markdown == '# Contrato de producto negociado'


def test_custom_service_contract_requires_its_own_text(admin_client, split_proposal):
    """Fails if the service contract can switch to custom source without its own Markdown."""
    response = admin_client.patch(_update_url(split_proposal), {
        'contract_params': {'service_contract_source': 'custom'}, 'variant': 'service',
    }, format='json')

    assert response.status_code == 400
    assert 'service_custom_contract_markdown' in response.data


def test_update_refuses_contract_variant_outside_current_modality(admin_client, negotiated):
    """Fails if a single-contract proposal can generate its inactive service variant."""
    response = admin_client.patch(_update_url(negotiated), {
        'contract_params': SERVICE_TERMS, 'variant': 'service',
    }, format='json')

    assert response.status_code == 409
    assert response.data['code'] == 'inactive_variant'


def test_first_negotiation_generation_uses_contract_update(admin_client, negotiating_proposal):
    """Fails if a negotiation without a contract cannot create its first combined document."""
    response = admin_client.patch(_update_url(negotiating_proposal), {'contract_params': PARTY_PARAMS}, format='json')

    negotiating_proposal.refresh_from_db()
    contract = ProposalDocument.objects.get(proposal=negotiating_proposal, document_type='contract')
    assert response.status_code == 200
    assert negotiating_proposal.contract_params['client_full_name'] == PARTY_PARAMS['client_full_name']
    assert contract.content_markdown.startswith('# CONTRATO DE PRESTACIÓN DE SERVICIOS')


def test_split_download_requires_the_requested_variant(admin_client, split_proposal):
    """Fails if split-contract download returns an ambiguous document without a variant selector."""
    _store_contract(split_proposal, 'contract_service', '# Service', b'%PDF-1.4 service')
    url = reverse('download-contract-pdf', kwargs={'proposal_id': split_proposal.pk})

    missing = admin_client.get(url)
    served = admin_client.get(url, {'variant': 'service'})

    assert missing.status_code == 400
    assert missing.data['code'] == 'variant_required'
    assert served.status_code == 200
    assert b''.join(served.streaming_content if served.streaming else [served.content]) == b'%PDF-1.4 service'
