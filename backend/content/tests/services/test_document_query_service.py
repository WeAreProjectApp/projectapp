"""The shared-source capability check must not grow with the document page."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from content.models import Document, DocumentType
from content.serializers.document import DocumentBrowseSerializer
from content.services.document_query_service import build_document_list_queryset
from content.services.document_write_service import document_capabilities

pytestmark = pytest.mark.django_db


@pytest.fixture
def ordinary_document_page(db):
    kind = DocumentType.objects.create(code='query-budget-markdown', name='Markdown')
    return Document.objects.bulk_create([
        Document(title=f'Ordinary document {index}', slug=f'query-budget-document-{index}', document_type=kind)
        for index in range(10)
    ])


def _binding_query_count(queries):
    return sum('content_proposaldocumentbinding' in query['sql'].lower() for query in queries)


def test_document_page_capabilities_keep_a_fixed_query_budget(ordinary_document_page):
    """Falla si comprobar la fuente compartida agrega una consulta por documento."""
    with CaptureQueriesContext(connection) as queries:
        documents = list(build_document_list_queryset({}, scope='active'))
        rows = DocumentBrowseSerializer(documents, many=True).data
        capabilities = list(map(document_capabilities, documents))

    assert len(queries) <= 6
    assert _binding_query_count(queries) == 1
    assert len(rows) == 10
    assert capabilities == [{
        'editable': True, 'movable': True, 'move_blockers': [],
        'content_editable': True, 'pdf_replaceable': False,
    }] * 10
