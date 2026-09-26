"""Tests for doc_refs parsing and resolution.

Covers:
  - parse_doc_refs_field: valid JSON, invalid JSON, non-list, already-list, empty
  - _resolve_proposal_doc_refs via branded-email/send/ endpoint
  - _resolve_diagnostic_doc_refs via diagnostics email/send/ endpoint
"""
import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from content.models import (
    BusinessProposal,
    DiagnosticAttachment,
    ProposalDocument,
)
from content.tests.email_stubs import stub_email_message

pytestmark = pytest.mark.django_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def proposal(db):
    return BusinessProposal.objects.create(
        title='DocRefs Proposal',
        client_name='Test Client',
        client_email='client@test.com',
        language='es',
        total_investment=Decimal('5000000'),
        currency='COP',
        status='sent',
        expires_at=timezone.now() + timezone.timedelta(days=10),
    )


@pytest.fixture
def proposal_with_uploaded_doc(db, proposal):
    doc = ProposalDocument.objects.create(
        proposal=proposal,
        document_type=ProposalDocument.DOC_TYPE_LEGAL_ANNEX,
        title='Otrosí de prueba',
        is_generated=False,
    )
    doc.file.save('annex.pdf', ContentFile(b'%PDF-1.4 annex'), save=True)
    return doc


@pytest.fixture
def diagnostic_with_attachment(db, diagnostic):
    att = DiagnosticAttachment.objects.create(
        diagnostic=diagnostic,
        title='Informe adjunto',
        document_type='other',
    )
    att.file.save('informe.pdf', ContentFile(b'%PDF-1.4 informe'), save=True)
    return att


def _send_url(proposal_id, variant='branded-email'):
    return reverse(
        'send-branded-email' if variant == 'branded-email' else 'send-proposal-email',
        kwargs={'proposal_id': proposal_id},
    )


def _diag_send_url(diagnostic_id):
    return reverse('send-diagnostic-email', kwargs={'diagnostic_id': diagnostic_id})


def _base_payload(**overrides):
    data = {
        'recipient_email': 'dest@example.com',
        'subject': 'Asunto de prueba',
        'greeting': 'Hola',
        'sections': json.dumps(['Contenido de sección.']),
        'footer': 'Pie de correo.',
    }
    data.update(overrides)
    return data


def _email_service_patches(module):
    return [
        patch(f'{module}.render_to_string', return_value='<html>OK</html>'),
        patch(f'{module}.EmailMultiAlternatives', return_value=stub_email_message()),
    ]


# ── parse_doc_refs_field ──────────────────────────────────────────────────────

class _FakeRequest:
    """Minimal stand-in for request.data in parse_doc_refs_field tests."""

    def __init__(self, data):
        self.data = data


class TestParseDocRefsField:

    def _call(self, data):
        from content.views._doc_refs import parse_doc_refs_field
        return parse_doc_refs_field(_FakeRequest(data))

    def test_valid_json_list_returns_list(self):
        result, err = self._call({'doc_refs': json.dumps([{'source': 'commercial_pdf'}])})
        assert err is None
        assert result == [{'source': 'commercial_pdf'}]

    def test_missing_field_returns_empty_list(self):
        result, err = self._call({})
        assert err is None
        assert result == []

    def test_empty_json_list_returns_empty_list(self):
        result, err = self._call({'doc_refs': '[]'})
        assert err is None
        assert result == []

    def test_invalid_json_returns_400_response(self):
        result, err = self._call({'doc_refs': '{not json'})
        assert result is None
        assert err is not None
        assert err.status_code == 400

    def test_non_list_json_returns_400_response(self):
        result, err = self._call({'doc_refs': json.dumps({'source': 'x'})})
        assert result is None
        assert err is not None
        assert err.status_code == 400


# ── _resolve_proposal_doc_refs via endpoint ───────────────────────────────────

class TestResolveProposalDocRefsViaEndpoint:

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate',
           return_value=b'%PDF-1.4 commercial')
    def test_commercial_pdf_ref_resolves_and_sends(
        self, mock_pdf_svc, mock_render, mock_email_cls, admin_client, proposal
    ):
        mock_render.return_value = '<html>OK</html>'
        mock_email_cls.return_value = stub_email_message()

        payload = _base_payload(
            doc_refs=json.dumps([{'source': 'commercial_pdf'}]),
        )
        response = admin_client.post(_send_url(proposal.id), payload)
        assert response.status_code == 200
        mock_pdf_svc.assert_called_once()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_proposal_document_ref_resolves_uploaded_file(
        self, mock_render, mock_email_cls, admin_client, proposal, proposal_with_uploaded_doc
    ):
        mock_render.return_value = '<html>OK</html>'
        mock_email_cls.return_value = stub_email_message()

        payload = _base_payload(
            doc_refs=json.dumps([{
                'source': 'proposal_document',
                'id': proposal_with_uploaded_doc.id,
            }]),
        )
        response = admin_client.post(_send_url(proposal.id), payload)
        assert response.status_code == 200
        mock_render.assert_called()

    def test_invalid_doc_refs_json_returns_400(self, admin_client, proposal):
        payload = _base_payload(doc_refs='{bad json}')
        response = admin_client.post(_send_url(proposal.id), payload)
        assert response.status_code == 400

    def test_unknown_doc_ref_source_returns_400(self, admin_client, proposal):
        payload = _base_payload(
            doc_refs=json.dumps([{'source': 'totally_unknown_source'}]),
        )
        response = admin_client.post(_send_url(proposal.id), payload)
        assert response.status_code == 400

    def test_proposal_document_ref_with_missing_id_returns_400(self, admin_client, proposal):
        payload = _base_payload(
            doc_refs=json.dumps([{'source': 'proposal_document', 'id': 99999}]),
        )
        response = admin_client.post(_send_url(proposal.id), payload)
        assert response.status_code == 400

    def test_split_contract_ref_must_name_the_document(self, admin_client, proposal):
        """Fails if a split closing attaches an unnamed contract, which could be the stale single one."""
        proposal.contract_modality = 'split'
        proposal.save(update_fields=['contract_modality'])

        payload = _base_payload(doc_refs=json.dumps([{'source': 'contract_pdf'}]))
        response = admin_client.post(_send_url(proposal.id), payload)

        assert response.status_code == 400
        assert 'producto o servicio' in response.data['error']

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    @patch('content.services.contract_pdf_service.generate_contract_pdf', return_value=b'%PDF-1.4 service')
    def test_split_contract_ref_attaches_the_named_document(
        self, mock_contract, mock_render, mock_email_cls, admin_client, proposal,
    ):
        """Fails if the composer attaches another document than the service contract it names."""
        mock_render.return_value = '<html>OK</html>'
        mock_email_cls.return_value = stub_email_message()
        proposal.contract_modality = 'split'
        proposal.save(update_fields=['contract_modality'])

        payload = _base_payload(doc_refs=json.dumps([{'source': 'contract_pdf', 'variant': 'service'}]))
        response = admin_client.post(_send_url(proposal.id), payload)

        assert response.status_code == 200
        assert mock_contract.call_args.kwargs == {'draft': False, 'variant': 'service'}


# ── _resolve_diagnostic_doc_refs via endpoint ─────────────────────────────────

class TestResolveDiagnosticDocRefsViaEndpoint:

    @patch('content.services.diagnostic_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_template_ref_resolves_md_file(
        self, mock_render, mock_email_cls, admin_client, diagnostic
    ):
        mock_render.return_value = '<html>OK</html>'
        mock_email_cls.return_value = stub_email_message()

        payload = _base_payload(
            doc_refs=json.dumps([{'source': 'template', 'slug': 'diagnostico-aplicacion'}]),
        )
        response = admin_client.post(_diag_send_url(diagnostic.id), payload)
        assert response.status_code == 200
        mock_render.assert_called()

    @patch('content.services.diagnostic_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_attachment_ref_resolves_uploaded_file(
        self, mock_render, mock_email_cls, admin_client, diagnostic, diagnostic_with_attachment
    ):
        mock_render.return_value = '<html>OK</html>'
        mock_email_cls.return_value = stub_email_message()

        payload = _base_payload(
            doc_refs=json.dumps([{
                'source': 'attachment',
                'id': diagnostic_with_attachment.id,
            }]),
        )
        response = admin_client.post(_diag_send_url(diagnostic.id), payload)
        assert response.status_code == 200
        mock_render.assert_called()

    @patch('content.services.diagnostic_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    @patch('content.services.confidentiality_pdf_service.generate_confidentiality_pdf',
           return_value=b'%PDF-1.4 nda')
    def test_nda_final_ref_resolves_generated_pdf(
        self, mock_nda, mock_render, mock_email_cls, admin_client, diagnostic
    ):
        mock_render.return_value = '<html>OK</html>'
        mock_email_cls.return_value = stub_email_message()

        payload = _base_payload(
            doc_refs=json.dumps([{'source': 'nda_final'}]),
        )
        response = admin_client.post(_diag_send_url(diagnostic.id), payload)
        assert response.status_code == 200
        mock_nda.assert_called_once_with(diagnostic)

    def test_invalid_doc_refs_json_returns_400(self, admin_client, diagnostic):
        payload = _base_payload(doc_refs='{bad}')
        response = admin_client.post(_diag_send_url(diagnostic.id), payload)
        assert response.status_code == 400

    def test_unknown_source_returns_400(self, admin_client, diagnostic):
        payload = _base_payload(
            doc_refs=json.dumps([{'source': 'nonexistent_source'}]),
        )
        response = admin_client.post(_diag_send_url(diagnostic.id), payload)
        assert response.status_code == 400

    def test_template_ref_with_unknown_slug_returns_400(self, admin_client, diagnostic):
        payload = _base_payload(
            doc_refs=json.dumps([{'source': 'template', 'slug': 'no-such-template'}]),
        )
        response = admin_client.post(_diag_send_url(diagnostic.id), payload)
        assert response.status_code == 400
