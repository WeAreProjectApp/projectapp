"""Consulting PA-265 history must leave both current and historical content intact."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from content.models import Document, EntityHistory


@pytest.mark.django_db
@pytest.mark.parametrize('operation', ['list', 'version', 'compare'])
def test_consulting_history_preserves_document_content(operation):
    document = Document.objects.create(title='Histórico', content_markdown='# Original')
    document.content_markdown = '# Modificado'
    document.save()
    history = EntityHistory.objects.get(entity_type='document', object_id=document.pk)
    versions = list(history.entries.order_by('number').values('id', 'snapshot', 'changes'))
    client = APIClient()
    client.force_authenticate(get_user_model().objects.create_user(username='history-reader', is_staff=True))
    base = f'/api/entity-history/document/{document.pk}/'
    urls = {
        'list': base,
        'version': f'{base}versions/{versions[-1]["id"]}/',
        'compare': f'{base}compare/?from={versions[0]["id"]}&to={versions[-1]["id"]}',
    }

    response = client.get(urls[operation])

    assert response.status_code == 200
    document.refresh_from_db()
    assert document.content_markdown == '# Modificado'
    assert list(history.entries.order_by('number').values('id', 'snapshot', 'changes')) == versions
