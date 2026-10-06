"""Recovery snapshots preserve exact proposal contract evidence."""

import hashlib

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    Document,
    ProposalChangeLog,
    ProposalContractSnapshot,
    ProposalDocument,
    ProposalSection,
)

pytestmark = pytest.mark.django_db

PARTY = {
    'client_full_name': 'Snapshot client', 'client_cedula': '1020304050', 'client_email': 'snapshot@example.com',
    'contractor_full_name': 'Project App S.A.S.', 'contractor_nit': '900123456-7',
    'contractor_email': 'team@example.com', 'bank_name': 'Banco', 'bank_account_type': 'Ahorros',
    'bank_account_number': '123', 'contract_city': 'Medellín', 'contract_date': '2026-10-06',
}
TERMS = {
    'service_initial_term': 'doce meses', 'service_renewal_notice_days': 'treinta',
    'service_termination_notice_days': 'quince',
}


def _url(proposal, name, **kwargs):
    return reverse(name, kwargs={'proposal_id': proposal.pk, **kwargs})


def _pdf(_proposal, *, resolved_content, **_kwargs):
    return b'%PDF-1.4 generated\n' + resolved_content['snapshot'].encode()


def _contract(proposal, markdown, pdf):
    document = ProposalDocument.objects.create(
        proposal=proposal, document_type='contract', title='Contract', is_generated=True,
        content_markdown=markdown,
    )
    document.file.save('snapshot-source.pdf', ContentFile(pdf), save=True)
    return document


@pytest.fixture
def accepted_contract(accepted_proposal, contract_template):
    contract_template.product_content_markdown = '# Product {client_full_name}'
    contract_template.save(update_fields=['product_content_markdown'])
    accepted_proposal.contract_params = {**PARTY, 'contract_source': 'custom', 'custom_contract_markdown': '# Exact source\n'}
    accepted_proposal.save(update_fields=['contract_params'])
    ProposalSection.objects.create(
        proposal=accepted_proposal, section_type='investment', title='Investment', order=1,
        content_json={'hostingPlan': {'billingTiers': [{'label': 'Monthly', 'months': 1}]}},
    )
    return accepted_proposal


def test_snapshot_captures_contract_bytes_and_restore_recreates_exact_contract(
    admin_client, accepted_contract, monkeypatch,
):
    """Fails if restore loses the prior custom Markdown or PDF bytes captured before conversion."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _pdf)
    original_pdf = b'%PDF-1.4 signed bytes unlike markdown\x00'
    original = _contract(accepted_contract, '# Exact source\n', original_pdf)

    preview = admin_client.post(_url(accepted_contract, 'preview-contract-change'), {
        'contract_modality': 'split', 'change_note': 'Separate the signed agreement', 'contract_params': TERMS,
    }, format='json')
    admin_client.post(_url(accepted_contract, 'confirm-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')

    snapshot = ProposalContractSnapshot.objects.get(proposal=accepted_contract, from_modality='single')
    snapshot_file = snapshot.files.get(source_document_id=original.pk)
    assert snapshot.change_note == 'Separate the signed agreement'
    assert snapshot.payload['documents'][0]['markdown'] == '# Exact source\n'
    assert bytes(snapshot_file.pdf_content) == original_pdf
    assert snapshot_file.sha256 == hashlib.sha256(original_pdf).hexdigest()

    restore_preview = admin_client.post(_url(accepted_contract, 'preview-contract-change'), {
        'snapshot_id': snapshot.pk, 'change_note': 'Restore signed agreement',
    }, format='json')
    admin_client.post(_url(accepted_contract, 'confirm-contract-change'), {
        'confirmation_id': restore_preview.data['confirmation_id'],
    }, format='json')

    accepted_contract.refresh_from_db()
    recovered = accepted_contract.proposal_documents.get(document_type='contract', is_archived=False)
    assert recovered.content_markdown == '# Exact source\n'
    assert recovered.file.read() == original_pdf
    assert ProposalContractSnapshot.objects.filter(proposal=accepted_contract).count() == 2


def test_snapshot_read_is_scoped_to_its_proposal(admin_client, accepted_contract, proposal):
    """Fails if a snapshot URL exposes recovery evidence belonging to a different proposal."""
    snapshot = ProposalContractSnapshot.objects.create(
        proposal=accepted_contract, payload={}, actor_label='Admin', source='panel', change_note='reason',
        from_modality='single', to_modality='split',
    )

    response = admin_client.get(_url(proposal, 'read-contract-snapshot', snapshot_id=snapshot.pk))

    assert response.status_code == 404


def test_saved_contract_snapshot_cannot_be_edited(accepted_contract):
    """Fails if a recovery point can be edited after it records contract evidence."""
    snapshot = ProposalContractSnapshot.objects.create(
        proposal=accepted_contract, payload={}, actor_label='Admin', source='panel', change_note='reason',
        from_modality='single', to_modality='split',
    )
    snapshot.change_note = 'rewritten'

    with pytest.raises(ValueError, match='cannot be edited'):
        snapshot.save()


def test_saved_contract_snapshot_rejects_queryset_rewrite(accepted_contract):
    """Fails if bulk queryset updates bypass immutable recovery evidence."""
    snapshot = ProposalContractSnapshot.objects.create(
        proposal=accepted_contract, payload={}, actor_label='Admin', source='panel', change_note='reason',
        from_modality='single', to_modality='split',
    )

    with pytest.raises(ValueError, match='cannot be edited'):
        ProposalContractSnapshot.objects.filter(pk=snapshot.pk).update(change_note='rewritten')


def test_contract_snapshot_records_actor_note_modalities_and_audit_entry(
    admin_client, admin_user, accepted_contract, monkeypatch,
):
    """Fails if a confirmed contract change lacks attributable recovery and proposal-history evidence."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _pdf)
    _contract(accepted_contract, '# Exact source\n', b'%PDF-1.4 evidence')
    preview = admin_client.post(_url(accepted_contract, 'preview-contract-change'), {
        'contract_modality': 'split', 'change_note': 'Legal split decision', 'contract_params': TERMS,
    }, format='json')
    admin_client.post(_url(accepted_contract, 'confirm-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')

    snapshot = ProposalContractSnapshot.objects.get(proposal=accepted_contract)
    audit = ProposalChangeLog.objects.get(proposal=accepted_contract, field_name='contract_modality')
    assert snapshot.actor_id_snapshot == admin_user.pk
    assert snapshot.actor_label == admin_user.username
    assert snapshot.change_note == 'Legal split decision'
    assert snapshot.from_modality == 'single'
    assert snapshot.to_modality == 'split'
    assert snapshot.created_at is not None
    assert 'Legal split decision' in audit.description


@freeze_time('2026-10-06 12:00:00')
def test_signed_linked_document_remains_historical_after_contract_split(
    admin_client, accepted_contract, monkeypatch,
):
    """Fails if splitting a contract changes a signed linked document instead of preserving its historical mapping."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _pdf)
    source = _contract(accepted_contract, '# Exact source\n', b'%PDF-1.4 evidence')
    signed_at = timezone.now()
    linked = Document.objects.create(
        title='Signed contract mirror', source_proposal=accepted_contract, content_markdown='# Signed historic text',
        signed_at=signed_at, metadata={
            'proposal_id': accepted_contract.pk, 'proposal_document_id': source.pk, 'contract_variant': 'combined',
        },
    )
    preview = admin_client.post(_url(accepted_contract, 'preview-contract-change'), {
        'contract_modality': 'split', 'change_note': 'Keep signed history', 'contract_params': TERMS,
    }, format='json')
    confirmed = admin_client.post(_url(accepted_contract, 'confirm-contract-change'), {
        'confirmation_id': preview.data['confirmation_id'],
    }, format='json')

    linked.refresh_from_db()
    impact = preview.data['impact']['linked_documents'][0]
    assert impact['document_id'] == linked.pk
    assert impact['proposal_document_id'] == source.pk
    assert impact['variant'] == 'combined'
    assert impact['signed'] is True
    assert linked.signed_at == signed_at
    assert linked.content_markdown == '# Signed historic text'
    assert linked.pk in next(
        row['historical_document_ids']
        for row in confirmed.data['contract_change']['contracts']
        if row['variant'] == 'product'
    )
