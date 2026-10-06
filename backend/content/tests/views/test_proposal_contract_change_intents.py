"""Non-negotiating contract changes require owned, current confirmations."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from content.models import (
    ProposalContractChangeIntent,
    ProposalContractSnapshot,
    ProposalSection,
)

pytestmark = pytest.mark.django_db

PARTY = {
    'client_full_name': 'Intent client', 'client_cedula': '1020304050', 'client_email': 'intent@example.com',
    'contractor_full_name': 'Project App S.A.S.', 'contractor_nit': '900123456-7',
    'contractor_email': 'team@example.com', 'bank_name': 'Banco', 'bank_account_type': 'Ahorros',
    'bank_account_number': '123', 'contract_city': 'Medellín', 'contract_date': '2026-10-06',
}
TERMS = {
    'service_initial_term': 'doce meses', 'service_renewal_notice_days': 'treinta',
    'service_termination_notice_days': 'quince',
}


def _url(proposal, name):
    return reverse(name, kwargs={'proposal_id': proposal.pk})


def _pdf(_proposal, *, resolved_content, **_kwargs):
    return b'%PDF-1.4 intent\n' + resolved_content['snapshot'].encode()


def _prepare(proposal, template):
    template.product_content_markdown = '# Product {client_full_name}'
    template.save(update_fields=['product_content_markdown'])
    proposal.contract_params = dict(PARTY)
    proposal.save(update_fields=['contract_params'])
    ProposalSection.objects.create(
        proposal=proposal, section_type='investment', title='Investment', order=1,
        content_json={'hostingPlan': {'billingTiers': [{'label': 'Monthly', 'months': 1}]}},
    )
    return proposal


@pytest.mark.parametrize('fixture_name', ['sent_proposal', 'viewed_proposal', 'accepted_proposal', 'rejected_proposal'])
def test_non_negotiating_direct_patch_requires_confirmation(admin_client, request, contract_template, fixture_name):
    """Fails if a post-negotiation proposal can change modality without a review confirmation."""
    proposal = _prepare(request.getfixturevalue(fixture_name), contract_template)

    response = admin_client.patch(_url(proposal, 'update-contract-modality'), {
        'contract_modality': 'split', 'change_note': 'Must preview', 'contract_params': TERMS,
    }, format='json')

    proposal.refresh_from_db()
    assert response.status_code == 409
    assert response.data['code'] == 'CONFIRMATION_REQUIRED'
    assert proposal.contract_modality == 'single'
    assert ProposalContractSnapshot.objects.filter(proposal=proposal).count() == 0


def test_negotiating_direct_patch_applies_without_change_intent(admin_client, negotiating_proposal, contract_template, monkeypatch):
    """Fails if a negotiating proposal unnecessarily requires the post-negotiation confirmation flow."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _pdf)
    proposal = _prepare(negotiating_proposal, contract_template)

    response = admin_client.patch(_url(proposal, 'update-contract-modality'), {
        'contract_modality': 'split', 'contract_params': TERMS,
    }, format='json')

    proposal.refresh_from_db()
    assert response.status_code == 200
    assert proposal.contract_modality == 'split'
    assert ProposalContractChangeIntent.objects.filter(proposal=proposal).count() == 0


def test_cancelled_contract_change_intent_cannot_apply(admin_client, accepted_proposal, contract_template):
    """Fails if a cancelled review can still mutate an accepted proposal's contract modality."""
    proposal = _prepare(accepted_proposal, contract_template)
    preview = admin_client.post(_url(proposal, 'preview-contract-change'), {
        'contract_modality': 'split', 'change_note': 'Review then cancel', 'contract_params': TERMS,
    }, format='json')

    cancelled = admin_client.post(_url(proposal, 'cancel-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')
    response = admin_client.post(_url(proposal, 'confirm-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')

    proposal.refresh_from_db()
    assert cancelled.status_code == 200
    assert response.status_code == 409
    assert response.data['code'] == 'CONFIRMATION_EXPIRED'
    assert proposal.contract_modality == 'single'


def test_non_negotiating_preview_requires_a_change_note(admin_client, accepted_proposal, contract_template):
    """Fails if an accepted proposal can enter contract review without an accountable change note."""
    proposal = _prepare(accepted_proposal, contract_template)

    response = admin_client.post(_url(proposal, 'preview-contract-change'), {
        'contract_modality': 'split', 'contract_params': TERMS,
    }, format='json')

    assert response.status_code == 422
    assert response.data['details'] == {'change_note': 'Este dato es obligatorio fuera de negociación.'}
    assert ProposalContractChangeIntent.objects.filter(proposal=proposal).count() == 0


def test_contract_change_intent_belongs_only_to_its_previewing_admin(admin_client, accepted_proposal, contract_template):
    """Fails if a second administrator can confirm another user's contract change preview."""
    proposal = _prepare(accepted_proposal, contract_template)
    preview = admin_client.post(_url(proposal, 'preview-contract-change'), {
        'contract_modality': 'split', 'change_note': 'Owned review', 'contract_params': TERMS,
    }, format='json')
    other = get_user_model().objects.create_user(
        username='second_admin', email='second@example.com', password='safe-pass', is_staff=True,
    )
    other_client = APIClient()
    other_client.force_authenticate(user=other)

    response = other_client.post(_url(proposal, 'confirm-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')

    assert response.status_code == 404
    assert ProposalContractChangeIntent.objects.get(pk=preview.data['confirmation_id']).status == 'pending'


@freeze_time('2026-10-06 12:00:00')
def test_expired_contract_change_intent_cannot_apply(admin_client, accepted_proposal, contract_template):
    """Fails if an expired review remains usable to change a legally closed proposal."""
    proposal = _prepare(accepted_proposal, contract_template)
    preview = admin_client.post(_url(proposal, 'preview-contract-change'), {
        'contract_modality': 'split', 'change_note': 'Expires', 'contract_params': TERMS,
    }, format='json')
    ProposalContractChangeIntent.objects.filter(pk=preview.data['confirmation_id']).update(
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    response = admin_client.post(_url(proposal, 'confirm-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')

    assert response.status_code == 409
    assert response.data['code'] == 'CONFIRMATION_EXPIRED'


def test_stale_contract_change_intent_cannot_overwrite_newer_contract_params(
    admin_client, accepted_proposal, contract_template,
):
    """Fails if confirmation applies a preview after the proposal's contract data changed."""
    proposal = _prepare(accepted_proposal, contract_template)
    preview = admin_client.post(_url(proposal, 'preview-contract-change'), {
        'contract_modality': 'split', 'change_note': 'Must remain current', 'contract_params': TERMS,
    }, format='json')
    proposal.contract_params = {**PARTY, 'client_full_name': 'Changed after preview'}
    proposal.save(update_fields=['contract_params'])

    response = admin_client.post(_url(proposal, 'confirm-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')

    proposal.refresh_from_db()
    assert response.status_code == 409
    assert response.data['code'] == 'STALE_VERSION'
    assert proposal.contract_params['client_full_name'] == 'Changed after preview'


def test_replayed_contract_change_confirmation_returns_its_first_result(admin_client, accepted_proposal, contract_template, monkeypatch):
    """Fails if replaying a confirmed change creates a second legal recovery snapshot."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _pdf)
    proposal = _prepare(accepted_proposal, contract_template)
    preview = admin_client.post(_url(proposal, 'preview-contract-change'), {
        'contract_modality': 'split', 'change_note': 'Replay safely', 'contract_params': TERMS,
    }, format='json')

    first = admin_client.post(_url(proposal, 'confirm-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')
    replay = admin_client.post(_url(proposal, 'confirm-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.data == first.data
    assert ProposalContractSnapshot.objects.filter(proposal=proposal).count() == 1
