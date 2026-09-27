"""Gap tests for content/views/proposal.py — uncovered branches.

Targets:
- _resolve_proposal_doc_refs: contract_pdf, contract_draft, technical_pdf, non-dict ref
- _parse_composed_email: file attachment exceeding 15 MB size limit
- send_documents_to_client: technical doc type generation
"""
import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from content.models import BusinessProposal

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def proposal(db):
    return BusinessProposal.objects.create(
        title='Gap Proposal',
        client_name='Gap Client',
        client_email='gap@test.com',
        language='es',
        total_investment=Decimal('5000000'),
        currency='COP',
        status='sent',
        expires_at=timezone.now() + timezone.timedelta(days=10),
    )


def _email_payload(**overrides):
    data = {
        'recipient_email': 'dest@example.com',
        'subject': 'Test Subject',
        'greeting': 'Hola',
        'sections': json.dumps(['Sección de contenido.']),
        'footer': 'Pie de correo.',
    }
    data.update(overrides)
    return data


def _send_url(proposal_id):
    return reverse('send-branded-email', kwargs={'proposal_id': proposal_id})


def _send_docs_url(proposal_id):
    return reverse('send-documents-to-client', kwargs={'proposal_id': proposal_id})


# ---------------------------------------------------------------------------
# _resolve_proposal_doc_refs — contract_pdf source
# ---------------------------------------------------------------------------

class TestResolveDocRefsContractPdf:
    @patch('content.services.proposal_email_service.ProposalEmailService.send_branded_email', return_value=True)
    @patch('content.services.contract_pdf_service.generate_contract_pdf', return_value=b'%PDF-1.4 contract')
    def test_contract_pdf_ref_resolves_and_sends(self, mock_contract, mock_email, admin_client, proposal):
        payload = _email_payload(
            doc_refs=json.dumps([{'source': 'contract_pdf'}]),
        )
        response = admin_client.post(_send_url(proposal.id), payload, format='json')
        assert response.status_code == 200
        mock_contract.assert_called_once_with(proposal, draft=False, variant='combined')

    @patch('content.services.contract_pdf_service.generate_contract_pdf', return_value=None)
    def test_contract_pdf_ref_returns_400_when_pdf_fails(self, mock_contract, admin_client, proposal):
        payload = _email_payload(
            doc_refs=json.dumps([{'source': 'contract_pdf'}]),
        )
        response = admin_client.post(_send_url(proposal.id), payload, format='json')
        assert response.status_code == 400
        assert 'error' in response.json()


# ---------------------------------------------------------------------------
# _resolve_proposal_doc_refs — contract_draft source
# ---------------------------------------------------------------------------

class TestResolveDocRefsContractDraft:
    @patch('content.services.proposal_email_service.ProposalEmailService.send_branded_email', return_value=True)
    @patch('content.services.pdf_utils.add_watermark_to_pdf', return_value=b'%PDF-1.4 watermarked')
    @patch('content.services.contract_pdf_service.generate_contract_pdf', return_value=b'%PDF-1.4 draft')
    def test_contract_draft_ref_resolves_and_sends(self, mock_contract, mock_wm, mock_email, admin_client, proposal):
        payload = _email_payload(
            doc_refs=json.dumps([{'source': 'contract_draft'}]),
        )
        response = admin_client.post(_send_url(proposal.id), payload, format='json')
        assert response.status_code == 200
        mock_contract.assert_called_once_with(proposal, draft=True, variant='combined')
        mock_wm.assert_called_once()

    @patch('content.services.contract_pdf_service.generate_contract_pdf', return_value=None)
    def test_contract_draft_ref_returns_400_when_pdf_fails(self, mock_contract, admin_client, proposal):
        payload = _email_payload(
            doc_refs=json.dumps([{'source': 'contract_draft'}]),
        )
        response = admin_client.post(_send_url(proposal.id), payload, format='json')
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# _resolve_proposal_doc_refs — technical_pdf source
# ---------------------------------------------------------------------------

class TestResolveDocRefsTechnicalPdf:
    @patch('content.services.proposal_email_service.ProposalEmailService.send_branded_email', return_value=True)
    @patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=b'%PDF-1.4 tech')
    def test_technical_pdf_ref_resolves_and_sends(self, mock_tech, mock_email, admin_client, proposal):
        payload = _email_payload(
            doc_refs=json.dumps([{'source': 'technical_pdf'}]),
        )
        response = admin_client.post(_send_url(proposal.id), payload, format='json')
        assert response.status_code == 200
        mock_tech.assert_called_once_with(proposal)

    @patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=None)
    def test_technical_pdf_ref_returns_400_when_pdf_fails(self, mock_tech, admin_client, proposal):
        payload = _email_payload(
            doc_refs=json.dumps([{'source': 'technical_pdf'}]),
        )
        response = admin_client.post(_send_url(proposal.id), payload, format='json')
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# _resolve_proposal_doc_refs — non-dict item raises DocRefError
# ---------------------------------------------------------------------------

def test_resolve_doc_refs_non_dict_ref_returns_400(admin_client, proposal):
    payload = _email_payload(
        doc_refs=json.dumps(['not-a-dict-item']),
    )
    response = admin_client.post(_send_url(proposal.id), payload, format='json')
    assert response.status_code == 400
    assert 'error' in response.json()


# ---------------------------------------------------------------------------
# _parse_composed_email — attachment exceeds 15 MB size limit
# ---------------------------------------------------------------------------

def test_parse_composed_email_oversized_attachment_returns_400(admin_client, proposal):
    oversized = SimpleUploadedFile(
        'big.pdf',
        b'x' * (15 * 1024 * 1024 + 1),
        content_type='application/pdf',
    )
    data = {
        'recipient_email': 'dest@example.com',
        'subject': 'Test',
        'greeting': 'Hola',
        'sections': json.dumps(['Content.']),
        'attachments': oversized,
    }
    response = admin_client.post(_send_url(proposal.id), data, format='multipart')
    assert response.status_code == 400
    assert 'error' in response.json()


# ---------------------------------------------------------------------------
# send_documents_to_client — technical doc type
# ---------------------------------------------------------------------------

class TestSendDocumentsTechnicalType:
    @patch('content.services.proposal_email_service.ProposalEmailService.send_documents_to_client', return_value=True)
    @patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=b'%PDF-1.4 tech')
    def test_technical_doc_type_generates_pdf_and_sends(self, mock_tech, mock_email, admin_client, proposal):
        payload = {
            'documents': ['technical'],
            'additional_doc_ids': [],
            'subject': 'Technical Doc',
        }
        response = admin_client.post(_send_docs_url(proposal.id), payload, format='json')
        assert response.status_code == 200
        mock_tech.assert_called_once_with(proposal)

    @patch('content.services.proposal_email_service.ProposalEmailService.send_documents_to_client', return_value=True)
    @patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=None)
    def test_technical_doc_type_skips_when_pdf_fails_and_returns_400(self, mock_tech, mock_email, admin_client, proposal):
        payload = {
            'documents': ['technical'],
            'additional_doc_ids': [],
            'subject': 'Technical Doc',
        }
        response = admin_client.post(_send_docs_url(proposal.id), payload, format='json')
        assert response.status_code == 400
