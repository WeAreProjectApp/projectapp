"""Recovery snapshots preserve exact proposal contract evidence."""

import hashlib

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    Document,
    ProposalChangeLog,
    ProposalContractChangeIntent,
    ProposalContractSnapshot,
    ProposalContractSnapshotFile,
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
EXACT_MARKDOWN = '# Signed contract\n\nExact negotiated clauses.\n'
EXACT_PDF = b'%PDF-1.4 signed contract bytes\x00%%EOF'


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


def _snapshot_row(proposal, *, note='Retained legal evidence', payload=None):
    return ProposalContractSnapshot(
        proposal=proposal,
        payload=payload if payload is not None else {},
        actor_label='Admin',
        source='panel',
        change_note=note,
        from_modality='single',
        to_modality='split',
    )


def _save_snapshot(proposal, *, note='Retained legal evidence', payload=None):
    snapshot = _snapshot_row(proposal, note=note, payload=payload)
    snapshot.save()
    return snapshot


def _snapshot_with_file(proposal, source_document):
    payload = {
        'contract_modality': 'single',
        'contract_params': {
            'contract_source': 'custom',
            'custom_contract_markdown': EXACT_MARKDOWN,
        },
        'documents': [{
            'variant': 'combined',
            'document_id': source_document.pk,
            'document_type': 'contract',
            'title': source_document.title,
            'file_name': source_document.file.name,
            'markdown': EXACT_MARKDOWN,
            'source': 'custom',
            'is_archived': False,
        }],
        'linked_documents': [],
    }
    snapshot = _save_snapshot(proposal, payload=payload)
    snapshot_file = ProposalContractSnapshotFile.objects.create(
        snapshot=snapshot,
        source_document_id=source_document.pk,
        pdf_content=EXACT_PDF,
        sha256=hashlib.sha256(EXACT_PDF).hexdigest(),
    )
    return snapshot, snapshot_file


def _history_evidence_url(proposal, _snapshot, _source_document):
    return _url(proposal, 'list-contract-snapshots')


def _detail_evidence_url(proposal, snapshot, _source_document):
    return _url(proposal, 'read-contract-snapshot', snapshot_id=snapshot.pk)


def _file_evidence_url(proposal, snapshot, source_document):
    return _url(
        proposal,
        'download-contract-snapshot',
        snapshot_id=snapshot.pk,
        document_id=source_document.pk,
    )


def _missing_snapshot_id(_proposal):
    return 2_147_483_647


def _foreign_snapshot_id(proposal):
    return _save_snapshot(proposal, note='Foreign proposal evidence').pk


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


@freeze_time('2026-10-06 12:00:00')
def test_snapshot_history_paginates_only_requested_proposal(admin_client, accepted_contract, proposal):
    """Fails if retained history leaks another proposal or skips the fixed 20-row page boundary."""
    history = ProposalContractSnapshot.objects.bulk_create([
        _snapshot_row(accepted_contract, note=f'Retained evidence {index}')
        for index in range(22)
    ])
    foreign = _save_snapshot(proposal, note='Other proposal evidence')

    first_page = admin_client.get(_url(accepted_contract, 'list-contract-snapshots'))
    last_page = admin_client.get(_url(accepted_contract, 'list-contract-snapshots'), {'offset': 20})

    assert (first_page.status_code, last_page.status_code) == (200, 200)
    assert (first_page.data['total'], last_page.data['total']) == (22, 22)
    assert (len(first_page.data['snapshots']), len(last_page.data['snapshots'])) == (20, 2)
    assert [row['snapshot_id'] for row in first_page.data['snapshots']] == [
        row.pk for row in reversed(history[2:])
    ]
    assert [row['snapshot_id'] for row in last_page.data['snapshots']] == [history[1].pk, history[0].pk]
    assert foreign.pk not in {
        row['snapshot_id']
        for row in first_page.data['snapshots'] + last_page.data['snapshots']
    }


@pytest.mark.parametrize('offset', ['-1', 'not-an-integer'])
def test_snapshot_history_rejects_invalid_offset(admin_client, accepted_contract, offset):
    """Fails if malformed pagination reaches the immutable history query."""
    snapshot = _save_snapshot(accepted_contract)

    response = admin_client.get(
        _url(accepted_contract, 'list-contract-snapshots'),
        {'offset': offset},
    )

    assert response.status_code == 400
    assert response.data == {'error': 'offset debe ser un entero positivo o cero.'}
    assert ProposalContractSnapshot.objects.filter(pk=snapshot.pk).exists()


def test_snapshot_detail_returns_exact_contract_evidence(admin_client, accepted_contract):
    """Fails if detail retrieval changes the stored custom Markdown or its source-file metadata."""
    source = _contract(accepted_contract, EXACT_MARKDOWN, EXACT_PDF)
    snapshot, snapshot_file = _snapshot_with_file(accepted_contract, source)

    response = admin_client.get(
        _url(accepted_contract, 'read-contract-snapshot', snapshot_id=snapshot.pk),
    )

    document = response.data['payload']['documents'][0]
    assert response.status_code == 200
    assert response.data['snapshot_id'] == snapshot.pk
    assert response.data['payload'] == snapshot.payload
    assert document['markdown'] == EXACT_MARKDOWN
    assert document['file_name'] == source.file.name
    assert snapshot_file.sha256 == hashlib.sha256(EXACT_PDF).hexdigest()


def test_snapshot_file_download_returns_original_pdf(admin_client, accepted_contract):
    """Fails if recovery download changes signed bytes or permits intermediary caching."""
    source = _contract(accepted_contract, EXACT_MARKDOWN, EXACT_PDF)
    snapshot, _snapshot_file = _snapshot_with_file(accepted_contract, source)

    response = admin_client.get(_file_evidence_url(accepted_contract, snapshot, source))

    assert response.status_code == 200
    assert response.content == EXACT_PDF
    assert response['Content-Type'] == 'application/pdf'
    assert response['Content-Disposition'] == (
        f'attachment; filename="contract-snapshot-{snapshot.pk}-{source.pk}.pdf"'
    )
    assert response['Cache-Control'] == 'private, no-store'


@pytest.mark.parametrize(
    'url_builder',
    [_history_evidence_url, _detail_evidence_url, _file_evidence_url],
    ids=['history', 'detail', 'file'],
)
def test_snapshot_evidence_requires_admin(api_client, accepted_contract, url_builder):
    """Fails if a non-admin can read recovery history, Markdown, or stored PDF bytes."""
    source = _contract(accepted_contract, EXACT_MARKDOWN, EXACT_PDF)
    snapshot, snapshot_file = _snapshot_with_file(accepted_contract, source)
    viewer = get_user_model().objects.create_user(
        username='snapshot_viewer',
        email='snapshot-viewer@example.com',
    )
    api_client.force_authenticate(user=viewer)

    response = api_client.get(url_builder(accepted_contract, snapshot, source))

    snapshot_file.refresh_from_db()
    assert response.status_code == 403
    assert EXACT_MARKDOWN.encode() not in response.content
    assert EXACT_PDF not in response.content
    assert bytes(snapshot_file.pdf_content) == EXACT_PDF


def test_snapshot_detail_hides_missing_identifier(admin_client, accepted_contract):
    """Fails if a missing recovery identifier returns content or creates history."""
    response = admin_client.get(
        _url(accepted_contract, 'read-contract-snapshot', snapshot_id=_missing_snapshot_id(accepted_contract)),
    )

    assert response.status_code == 404
    assert EXACT_MARKDOWN.encode() not in response.content
    assert not ProposalContractSnapshot.objects.filter(proposal=accepted_contract).exists()


def test_snapshot_file_download_rejects_unknown_document(admin_client, accepted_contract):
    """Fails if a valid snapshot can serve bytes under an unrelated document identifier."""
    source = _contract(accepted_contract, EXACT_MARKDOWN, EXACT_PDF)
    snapshot, snapshot_file = _snapshot_with_file(accepted_contract, source)

    response = admin_client.get(_url(
        accepted_contract,
        'download-contract-snapshot',
        snapshot_id=snapshot.pk,
        document_id=source.pk + 10_000,
    ))

    snapshot_file.refresh_from_db()
    assert response.status_code == 404
    assert EXACT_PDF not in response.content
    assert bytes(snapshot_file.pdf_content) == EXACT_PDF


def test_snapshot_file_download_rejects_foreign_proposal(
    admin_client, accepted_contract, proposal,
):
    """Fails if a proposal URL can download another proposal's retained contract."""
    source = _contract(accepted_contract, EXACT_MARKDOWN, EXACT_PDF)
    snapshot, snapshot_file = _snapshot_with_file(accepted_contract, source)

    response = admin_client.get(_file_evidence_url(proposal, snapshot, source))

    snapshot_file.refresh_from_db()
    assert response.status_code == 404
    assert EXACT_PDF not in response.content
    assert bytes(snapshot_file.pdf_content) == EXACT_PDF


@pytest.mark.parametrize(
    'snapshot_id_builder',
    [_missing_snapshot_id, _foreign_snapshot_id],
    ids=['missing', 'other-proposal'],
)
def test_restore_preview_rejects_unknown_snapshot(
    admin_client, accepted_contract, proposal, snapshot_id_builder,
):
    """Fails if restore accepts missing or foreign evidence and mutates the target proposal."""
    snapshot_id = snapshot_id_builder(proposal)

    response = admin_client.post(_url(accepted_contract, 'preview-contract-change'), {
        'snapshot_id': snapshot_id,
        'change_note': 'Attempt invalid restore',
    }, format='json')

    accepted_contract.refresh_from_db()
    assert response.status_code == 404
    assert response.data['code'] == 'NOT_FOUND'
    assert accepted_contract.contract_modality == 'single'
    assert not accepted_contract.contract_snapshots.exists()
    assert not ProposalContractChangeIntent.objects.filter(proposal=accepted_contract).exists()


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
