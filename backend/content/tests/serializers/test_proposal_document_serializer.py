"""Tests for serialize_proposal_document function."""
import pytest

from content.models import ProposalDocument
from content.serializers.proposal import serialize_proposal_document

pytestmark = pytest.mark.django_db


class TestSerializeProposalDocument:
    @pytest.mark.parametrize('is_archived', [False, True], ids=['active', 'archived'])
    def test_exposes_document_metadata_with_archive_state(self, proposal_document, is_archived):
        proposal_document.is_archived = is_archived

        result = serialize_proposal_document(proposal_document)
        expected_keys = {
            'id', 'document_type', 'document_type_display',
            'custom_type_label', 'title', 'file', 'is_generated', 'created_at',
            'is_archived', 'updated_at', 'needs_regeneration',
        }
        assert set(result.keys()) == expected_keys
        assert result['is_archived'] is is_archived

    def test_uses_custom_type_label_for_other_type(self, negotiating_proposal):
        doc = ProposalDocument.objects.create(
            proposal=negotiating_proposal,
            document_type='other',
            custom_type_label='Designs',
            title='Design doc',
        )
        result = serialize_proposal_document(doc)
        assert result['document_type_display'] == 'Designs'

    def test_uses_display_for_non_other_type(self, proposal_document):
        result = serialize_proposal_document(proposal_document)
        # legal_annex → "Anexo legal"
        assert result['document_type_display'] == proposal_document.get_document_type_display()
