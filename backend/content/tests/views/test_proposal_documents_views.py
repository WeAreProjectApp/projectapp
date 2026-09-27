"""Tests for proposal document & contract API views.

Covers: save_contract_and_negotiate, upload/delete/list proposal documents,
download contract PDFs, company settings, default contract template,
send documents to client.
"""
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from content.models import ProposalChangeLog, ProposalDocument

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Save contract & negotiate
# ---------------------------------------------------------------------------

class TestSaveContractAndNegotiate:
    URL_NAME = 'save-contract-and-negotiate'

    def _url(self, proposal):
        return reverse(self.URL_NAME, kwargs={'proposal_id': proposal.pk})

    def _valid_params(self):
        return {
            'contract_params': {
                'client_cedula': '123456789',
                'client_full_name': 'Test Client',
                'contractor_full_name': 'Contractor',
                'contractor_nit': '987654321',
                'contract_source': 'default',
            }
        }

    @patch('content.views.proposal._generate_and_save_contract_pdf')
    def test_returns_200_for_sent_proposal(self, mock_gen, admin_client, sent_proposal):
        response = admin_client.post(self._url(sent_proposal), self._valid_params(), format='json')
        assert response.status_code == 200

    @patch('content.views.proposal._generate_and_save_contract_pdf')
    def test_returns_200_for_viewed_proposal(self, mock_gen, admin_client, viewed_proposal):
        response = admin_client.post(self._url(viewed_proposal), self._valid_params(), format='json')
        assert response.status_code == 200

    @patch('content.views.proposal._generate_and_save_contract_pdf')
    def test_returns_400_when_transition_not_allowed(self, mock_gen, admin_client, proposal):
        # draft → negotiating is not allowed
        response = admin_client.post(self._url(proposal), self._valid_params(), format='json')
        assert response.status_code == 400

    @patch('content.views.proposal._generate_and_save_contract_pdf')
    def test_returns_400_when_client_cedula_missing(self, mock_gen, admin_client, sent_proposal):
        data = {'contract_params': {'client_full_name': 'Test Client'}}
        response = admin_client.post(self._url(sent_proposal), data, format='json')
        assert response.status_code == 400

    @patch('content.views.proposal._generate_and_save_contract_pdf')
    def test_sets_status_to_negotiating(self, mock_gen, admin_client, sent_proposal):
        admin_client.post(self._url(sent_proposal), self._valid_params(), format='json')
        sent_proposal.refresh_from_db()
        assert sent_proposal.status == 'negotiating'

    @patch('content.views.proposal._generate_and_save_contract_pdf')
    def test_saves_contract_params(self, mock_gen, admin_client, sent_proposal):
        admin_client.post(self._url(sent_proposal), self._valid_params(), format='json')
        sent_proposal.refresh_from_db()
        assert sent_proposal.contract_params['client_cedula'] == '123456789'

    @patch('content.views.proposal._generate_and_save_contract_pdf')
    def test_creates_changelog_entry(self, mock_gen, admin_client, sent_proposal):
        admin_client.post(self._url(sent_proposal), self._valid_params(), format='json')
        log = ProposalChangeLog.objects.filter(proposal=sent_proposal, change_type='negotiating')
        assert log.exists()


# ---------------------------------------------------------------------------
# Upload proposal document
# ---------------------------------------------------------------------------

class TestUploadProposalDocument:
    URL_NAME = 'upload-proposal-document'

    def _url(self, proposal):
        return reverse(self.URL_NAME, kwargs={'proposal_id': proposal.pk})

    def test_returns_201_with_valid_pdf(self, admin_client, negotiating_proposal):
        file = SimpleUploadedFile('test.pdf', b'%PDF-1.4 content', content_type='application/pdf')
        response = admin_client.post(self._url(negotiating_proposal), {
            'file': file, 'title': 'Test doc', 'document_type': 'legal_annex',
        })
        assert response.status_code == 201
        assert response.data['document_type'] == 'legal_annex'

    def test_returns_400_when_no_file(self, admin_client, negotiating_proposal):
        response = admin_client.post(self._url(negotiating_proposal), {
            'title': 'No file', 'document_type': 'other',
        })
        assert response.status_code == 400

    def test_returns_400_for_disallowed_extension(self, admin_client, negotiating_proposal):
        file = SimpleUploadedFile('bad.exe', b'MZ content', content_type='application/octet-stream')
        response = admin_client.post(self._url(negotiating_proposal), {
            'file': file, 'document_type': 'other',
        })
        assert response.status_code == 400

    @pytest.mark.parametrize('doc_type', ['contract', 'contract_product', 'contract_service'])
    def test_returns_400_for_contract_type(self, admin_client, negotiating_proposal, doc_type):
        """Fails if any of the three generated contract types can be impersonated by an upload."""
        file = SimpleUploadedFile('c.pdf', b'%PDF-1.4', content_type='application/pdf')
        response = admin_client.post(self._url(negotiating_proposal), {
            'file': file, 'document_type': doc_type,
        })
        assert response.status_code == 400
        assert response.data['error'] == f'Invalid document_type: {doc_type}'
        assert not ProposalDocument.objects.filter(proposal=negotiating_proposal, document_type=doc_type).exists()

    def test_stores_custom_type_label_for_other(self, admin_client, negotiating_proposal):
        file = SimpleUploadedFile('x.pdf', b'%PDF-1.4', content_type='application/pdf')
        response = admin_client.post(self._url(negotiating_proposal), {
            'file': file, 'document_type': 'other', 'custom_type_label': 'Designs',
        })
        assert response.status_code == 201
        assert response.data['custom_type_label'] == 'Designs'

    def test_ignores_custom_label_for_non_other(self, admin_client, negotiating_proposal):
        file = SimpleUploadedFile('x.pdf', b'%PDF-1.4', content_type='application/pdf')
        response = admin_client.post(self._url(negotiating_proposal), {
            'file': file, 'document_type': 'amendment', 'custom_type_label': 'Should be ignored',
        })
        assert response.status_code == 201
        assert response.data['custom_type_label'] == ''


# ---------------------------------------------------------------------------
# Delete proposal document
# ---------------------------------------------------------------------------

class TestDeleteProposalDocument:
    URL_NAME = 'delete-proposal-document'

    def _url(self, proposal, doc_id):
        return reverse(self.URL_NAME, kwargs={'proposal_id': proposal.pk, 'doc_id': doc_id})

    def test_returns_204_for_user_uploaded(self, admin_client, negotiating_proposal, proposal_document):
        response = admin_client.delete(self._url(negotiating_proposal, proposal_document.pk))
        assert response.status_code == 204

    def test_returns_400_for_generated_doc(self, admin_client, negotiating_proposal, generated_contract_document):
        response = admin_client.delete(self._url(negotiating_proposal, generated_contract_document.pk))
        assert response.status_code == 400

    def test_returns_404_for_nonexistent(self, admin_client, negotiating_proposal):
        response = admin_client.delete(self._url(negotiating_proposal, 99999))
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# List proposal documents
# ---------------------------------------------------------------------------

class TestListProposalDocuments:
    URL_NAME = 'list-proposal-documents'

    def _url(self, proposal):
        return reverse(self.URL_NAME, kwargs={'proposal_id': proposal.pk})

    def test_returns_200_with_documents(self, admin_client, negotiating_proposal, proposal_document):
        response = admin_client.get(self._url(negotiating_proposal))
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_returns_empty_list_without_docs(self, admin_client, negotiating_proposal):
        response = admin_client.get(self._url(negotiating_proposal))
        assert response.status_code == 200
        assert isinstance(response.data, list)

    def test_returns_403_for_anonymous(self, api_client, negotiating_proposal):
        response = api_client.get(self._url(negotiating_proposal))
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Download contract PDF
# ---------------------------------------------------------------------------

class TestDownloadContractPdf:
    URL_NAME = 'download-contract-pdf'

    def _url(self, proposal):
        return reverse(self.URL_NAME, kwargs={'proposal_id': proposal.pk})

    def test_returns_pdf_when_exists(self, admin_client, negotiating_proposal, generated_contract_document):
        response = admin_client.get(self._url(negotiating_proposal))
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'

    def test_returns_404_when_not_generated(self, admin_client, negotiating_proposal):
        response = admin_client.get(self._url(negotiating_proposal))
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Download draft contract PDF (with watermark)
# ---------------------------------------------------------------------------

class TestDownloadDraftContractPdf:
    URL_NAME = 'download-draft-contract-pdf'

    def _url(self, proposal):
        return reverse(self.URL_NAME, kwargs={'proposal_id': proposal.pk})

    @patch('content.services.pdf_utils.add_watermark_to_pdf', return_value=b'watermarked-pdf')
    def test_returns_watermarked_pdf(self, mock_wm, admin_client, negotiating_proposal, generated_contract_document):
        response = admin_client.get(self._url(negotiating_proposal))
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        mock_wm.assert_called_once()

    @patch('content.services.contract_pdf_service.generate_contract_pdf', return_value=None)
    def test_returns_500_when_generation_fails(self, mock_gen, admin_client, negotiating_proposal):
        response = admin_client.get(self._url(negotiating_proposal))
        assert response.status_code == 500

    def test_returns_400_when_split_proposal_omits_variant(self, admin_client, negotiating_proposal):
        """Fails if a split closing's draft endpoint stops requiring which document to name."""
        negotiating_proposal.contract_modality = 'split'
        negotiating_proposal.save(update_fields=['contract_modality'])

        response = admin_client.get(self._url(negotiating_proposal))

        assert response.status_code == 400
        assert response.data['code'] == 'variant_required'

    def test_returns_409_for_a_variant_outside_the_split_modality(self, admin_client, negotiating_proposal):
        """Fails if a split closing's draft endpoint still serves the retired single contract."""
        negotiating_proposal.contract_modality = 'split'
        negotiating_proposal.save(update_fields=['contract_modality'])

        response = admin_client.get(self._url(negotiating_proposal), {'variant': 'combined'})

        assert response.status_code == 409
        assert response.data['code'] == 'inactive_variant'

    @patch('content.services.contract_pdf_service.generate_contract_pdf', return_value=b'%PDF-1.4 fake-service-draft')
    @patch('content.services.pdf_utils.add_watermark_to_pdf', return_value=b'watermarked-service-draft')
    def test_serves_the_named_variant_of_a_split_proposal(
        self, mock_wm, mock_gen, admin_client, negotiating_proposal,
    ):
        """Fails if a split closing's service draft is served under the product's or combined's filename."""
        negotiating_proposal.contract_modality = 'split'
        negotiating_proposal.save(update_fields=['contract_modality'])

        response = admin_client.get(self._url(negotiating_proposal), {'variant': 'service'})

        assert response.status_code == 200
        assert 'Borrador_Contrato_Servicio_Hosting' in response['Content-Disposition']
        mock_gen.assert_called_once_with(negotiating_proposal, draft=True, variant='service')


# ---------------------------------------------------------------------------
# Company settings
# ---------------------------------------------------------------------------

class TestGetCompanySettings:
    URL_NAME = 'get-company-settings'

    def test_returns_200_with_data(self, admin_client, company_settings):
        url = reverse(self.URL_NAME)
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.data['contractor_full_name'] == 'CARLOS MARIO BLANCO PEREZ'

    def test_creates_singleton_on_first_access(self, admin_client):
        url = reverse(self.URL_NAME)
        response = admin_client.get(url)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Default contract template
# ---------------------------------------------------------------------------

class TestGetDefaultContractTemplate:
    URL_NAME = 'get-default-contract-template'

    def test_returns_200_with_data(self, admin_client, contract_template):
        url = reverse(self.URL_NAME)
        response = admin_client.get(url)
        assert response.status_code == 200
        assert 'content_markdown' in response.data

    def test_returns_404_when_no_default(self, admin_client):
        from content.models import ContractTemplate
        ContractTemplate.objects.all().update(is_default=False)
        url = reverse(self.URL_NAME)
        response = admin_client.get(url)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Send documents to client
# ---------------------------------------------------------------------------

class TestSendDocumentsToClient:
    URL_NAME = 'send-documents-to-client'

    def _url(self, proposal):
        return reverse(self.URL_NAME, kwargs={'proposal_id': proposal.pk})

    def _base_payload(self):
        return {
            'documents': ['commercial'],
            'additional_doc_ids': [],
            'subject': 'Test subject',
            'greeting': 'Hola',
            'body': 'Test body',
            'footer': 'Footer',
            'document_descriptions': [{'name': 'Propuesta', 'description': 'Desc'}],
        }

    @patch('content.services.proposal_email_service.ProposalEmailService.send_documents_to_client', return_value=True)
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    def test_returns_200_on_success(self, mock_pdf, mock_email, admin_client, negotiating_proposal):
        response = admin_client.post(self._url(negotiating_proposal), self._base_payload(), format='json')
        assert response.status_code == 200

    def test_returns_400_when_no_client_email(self, admin_client, negotiating_proposal):
        negotiating_proposal.client_email = ''
        negotiating_proposal.save(update_fields=['client_email'])
        response = admin_client.post(self._url(negotiating_proposal), self._base_payload(), format='json')
        assert response.status_code == 400

    def test_returns_400_for_invalid_doc_keys(self, admin_client, negotiating_proposal):
        payload = self._base_payload()
        payload['documents'] = ['invalid_key']
        response = admin_client.post(self._url(negotiating_proposal), payload, format='json')
        assert response.status_code == 400

    def test_returns_400_when_no_documents_selected(self, admin_client, negotiating_proposal):
        payload = self._base_payload()
        payload['documents'] = []
        payload['additional_doc_ids'] = []
        response = admin_client.post(self._url(negotiating_proposal), payload, format='json')
        assert response.status_code == 400

    @patch('content.services.proposal_email_service.ProposalEmailService.send_documents_to_client', return_value=True)
    @patch('content.services.pdf_utils.add_watermark_to_pdf', return_value=b'watermarked')
    def test_includes_draft_contract_attachment(
        self, mock_wm, mock_email, admin_client, negotiating_proposal, generated_contract_document,
    ):
        payload = self._base_payload()
        payload['documents'] = ['draft_contract']
        response = admin_client.post(self._url(negotiating_proposal), payload, format='json')
        assert response.status_code == 200
        mock_wm.assert_called_once()

    @patch('content.services.proposal_email_service.ProposalEmailService.send_documents_to_client', return_value=True)
    def test_includes_additional_uploaded_docs(self, mock_email, admin_client, negotiating_proposal, proposal_document):
        payload = self._base_payload()
        payload['documents'] = []
        payload['additional_doc_ids'] = [proposal_document.pk]
        response = admin_client.post(self._url(negotiating_proposal), payload, format='json')
        assert response.status_code == 200

    @patch('content.services.proposal_email_service.ProposalEmailService.send_documents_to_client', return_value=False)
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    def test_returns_500_when_email_fails(self, mock_pdf, mock_email, admin_client, negotiating_proposal):
        response = admin_client.post(self._url(negotiating_proposal), self._base_payload(), format='json')
        assert response.status_code == 500

    @patch('content.services.proposal_email_service.ProposalEmailService.send_documents_to_client', return_value=True)
    @patch('content.services.contract_pdf_service.generate_contract_pdf', return_value=None)
    def test_skips_missing_contract_gracefully(self, mock_gen_pdf, mock_email, admin_client, negotiating_proposal):
        # draft_contract selected but generate_contract_pdf fails — should skip it
        payload = self._base_payload()
        payload['documents'] = ['draft_contract']
        response = admin_client.post(self._url(negotiating_proposal), payload, format='json')
        assert response.status_code == 400  # no attachments generated

    @patch('content.services.proposal_email_service.ProposalEmailService.send_documents_to_client', return_value=True)
    @patch('content.services.pdf_utils.add_watermark_to_pdf', return_value=b'watermarked')
    @patch('content.services.contract_pdf_service.generate_contract_pdf', return_value=b'%PDF-1.4 draft')
    def test_split_proposal_attaches_a_draft_per_active_variant(
        self, mock_gen, mock_wm, mock_email, admin_client, negotiating_proposal,
    ):
        """Fails if a split closing's client email attaches only one of its two contracts."""
        negotiating_proposal.contract_modality = 'split'
        negotiating_proposal.save(update_fields=['contract_modality'])
        payload = self._base_payload()
        payload['documents'] = ['draft_contract']

        response = admin_client.post(self._url(negotiating_proposal), payload, format='json')

        assert response.status_code == 200
        assert mock_wm.call_count == 2
        assert [call.kwargs.get('variant') for call in mock_gen.call_args_list] == ['product', 'service']


class TestUpdateContractParams:
    """PATCH /proposals/:id/contract/update/ — update existing contract params."""

    def _url(self, proposal):
        return f'/api/proposals/{proposal.pk}/contract/update/'

    def _valid_params(self):
        return {
            'contract_params': {
                'contract_source': 'default',
                'client_full_name': 'Updated Client',
                'client_cedula': '9876543210',
                'client_email': 'updated@client.com',
                'contractor_full_name': 'Contractor',
                'contractor_nit': '1037635428',
                'contractor_email': 'team@projectapp.co',
                'bank_name': 'Bancolombia',
                'bank_account_type': 'Ahorros',
                'bank_account_number': '26292039530',
                'contract_city': 'Medellín',
            },
        }

    @patch('content.views.proposal._generate_and_save_contract_pdf')
    def test_returns_200_with_valid_params(self, mock_gen, admin_client, negotiating_proposal):
        """Updating contract params with valid data returns 200."""
        response = admin_client.patch(
            self._url(negotiating_proposal), self._valid_params(), format='json',
        )
        assert response.status_code == 200

    @patch('content.views.proposal._generate_and_save_contract_pdf')
    def test_persists_updated_params(self, mock_gen, admin_client, negotiating_proposal):
        """Updated contract_params are saved to the proposal."""
        admin_client.patch(
            self._url(negotiating_proposal), self._valid_params(), format='json',
        )
        negotiating_proposal.refresh_from_db()
        assert negotiating_proposal.contract_params['client_full_name'] == 'Updated Client'

    def test_returns_400_for_missing_required_fields(self, admin_client, negotiating_proposal):
        """Missing required fields returns 400."""
        response = admin_client.patch(
            self._url(negotiating_proposal),
            {'contract_params': {}},
            format='json',
        )
        assert response.status_code == 400

    def test_returns_401_for_unauthenticated(self, api_client, negotiating_proposal):
        """Unauthenticated requests are rejected."""
        response = api_client.patch(
            self._url(negotiating_proposal), self._valid_params(), format='json',
        )
        assert response.status_code == 401
