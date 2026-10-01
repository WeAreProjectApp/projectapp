"""A second attachment path cannot publish a guide still in preparation."""
import pytest
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import DeliveryMessage, Notification
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import build_delivery_context, publish, version
from content.models import Document

pytestmark = pytest.mark.django_db


def private_guide(context):
    return Document.objects.create(project=context.project, client_user=context.client,
                                   title='Guía en preparación', content_markdown='# Guía\nContenido privado.',
                                   include_portada=False, include_subportada=False, include_contraportada=False)


def attach(context, doc, level, target_id):
    result = delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': level, 'target_id': target_id, 'document_id': doc.pk,
    })
    return result['result']['id']


def test_project_attachment_cannot_bypass_draft_guide_publication():
    context = build_delivery_context()
    doc = private_guide(context)
    attach(context, doc, 'stage', context.stage.pk)
    root_link_id = attach(context, doc, 'project', context.project.pk)

    with pytest.raises(NotFound):
        delivery.document_pdf(context.project.pk, context.client, root_link_id)

    assert delivery.list_documents(context.project.pk, context.client)['documents'] == []


def test_project_reply_cannot_publish_a_draft_guide_attachment():
    context = build_delivery_context()
    doc = private_guide(context)
    attach(context, doc, 'requirement', context.first.pk)
    data = {'expected_version': version(context), 'request_id': 'private-attachment', 'level': 'project',
            'target_id': context.project.pk, 'message': 'Esta guía aún no fue revisada.', 'document_ids': [doc.pk]}

    with pytest.raises(ValidationError):
        delivery.add_message(context.project.pk, context.admin, data)

    assert not DeliveryMessage.objects.exists()
    assert not Notification.objects.filter(user=context.client).exists()


def test_published_reply_can_share_an_unassociated_private_document():
    context = build_delivery_context()
    publish(context)
    doc = private_guide(context)
    data = {'expected_version': version(context), 'request_id': 'public-attachment', 'level': 'stage',
            'target_id': context.stage.pk, 'message': 'Documento de respuesta.', 'document_ids': [doc.pk]}

    delivery.add_message(context.project.pk, context.admin, data)

    links = delivery.list_documents(context.project.pk, context.client, 'stage', context.stage.pk)['documents']
    assert links[0]['document_id'] == doc.pk
    assert links[0]['snapshot_id'] is not None
