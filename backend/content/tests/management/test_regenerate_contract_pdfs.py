"""Regenerating contracts touches only the documents of each proposal's closing modality."""
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command

from content.models import ProposalDocument

pytestmark = pytest.mark.django_db


def _store(proposal, doc_type):
    doc = ProposalDocument.objects.create(
        proposal=proposal, document_type=doc_type, title=doc_type, is_generated=True,
    )
    doc.file.save(f'{doc_type}.pdf', ContentFile(b'%PDF-1.4'), save=True)
    return doc


@patch('content.management.commands.regenerate_contract_pdfs._generate_and_save_contract_pdf')
def test_split_closing_regenerates_its_two_documents_only(mock_generate, negotiating_proposal):
    """Fails if the command rewrites the inactive single contract of a split closing."""
    negotiating_proposal.contract_modality = 'split'
    negotiating_proposal.save(update_fields=['contract_modality'])
    for doc_type in ('contract', 'contract_product', 'contract_service'):
        _store(negotiating_proposal, doc_type)
    out = StringIO()

    call_command('regenerate_contract_pdfs', stdout=out)

    regenerated = sorted(call.args[1] for call in mock_generate.call_args_list)
    assert regenerated == ['product', 'service']
    assert '[skip inactive]' in out.getvalue()


@patch('content.management.commands.regenerate_contract_pdfs._generate_and_save_contract_pdf')
def test_custom_document_text_is_never_regenerated(mock_generate, negotiating_proposal):
    """Fails if a negotiated custom product text is replaced by the standard template."""
    negotiating_proposal.contract_modality = 'split'
    negotiating_proposal.contract_params = {'product_contract_source': 'custom'}
    negotiating_proposal.save(update_fields=['contract_modality', 'contract_params'])
    _store(negotiating_proposal, 'contract_product')
    _store(negotiating_proposal, 'contract_service')

    call_command('regenerate_contract_pdfs', stdout=StringIO())

    assert [call.args[1] for call in mock_generate.call_args_list] == ['service']


@patch('content.management.commands.regenerate_contract_pdfs._generate_and_save_contract_pdf')
def test_default_modality_regenerates_its_single_contract(mock_generate, negotiating_proposal):
    """Fails if the command stops regenerating the single contract every non-split proposal has."""
    _store(negotiating_proposal, 'contract')
    out = StringIO()

    call_command('regenerate_contract_pdfs', stdout=out)

    mock_generate.assert_called_once_with(negotiating_proposal, 'combined')
    assert '[regenerated]' in out.getvalue()
    assert '[skip inactive]' not in out.getvalue()
