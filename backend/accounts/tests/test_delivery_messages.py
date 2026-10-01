"""Messages inherit publication, including the text sent to notifications."""
import pytest
from rest_framework.exceptions import ValidationError

from accounts.models import DeliveryMessage, Notification
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import build_delivery_context

pytestmark = pytest.mark.django_db


def test_public_reply_cannot_expose_a_draft():
    context = build_delivery_context()
    data = {'expected_version': 0, 'request_id': 'draft-reply', 'level': 'stage',
            'target_id': context.stage.pk, 'message': 'Contenido en revisión interna'}

    with pytest.raises(ValidationError):
        delivery.add_message(context.project.pk, context.admin, data)

    assert not DeliveryMessage.objects.exists()
    assert not Notification.objects.filter(user=context.client).exists()


def test_internal_draft_note_does_not_notify_client():
    context = build_delivery_context()
    data = {'expected_version': 0, 'request_id': 'internal-note', 'level': 'stage',
            'target_id': context.stage.pk, 'message': 'Nota del equipo', 'is_internal': True}

    delivery.add_message(context.project.pk, context.admin, data)

    assert DeliveryMessage.objects.get().is_internal is True
    assert not Notification.objects.filter(user=context.client).exists()
    assert delivery.overview(context.project.pk, context.client)['scopes'] == []


def test_project_reply_cannot_reference_private_requirement():
    context = build_delivery_context()
    data = {'expected_version': 0, 'request_id': 'private-reference', 'level': 'project',
            'target_id': context.project.pk, 'requirement_ids': [context.first.pk],
            'message': 'El requerimiento todavía está en preparación'}

    with pytest.raises(ValidationError):
        delivery.add_message(context.project.pk, context.admin, data)

    assert not DeliveryMessage.objects.exists()
    assert not Notification.objects.filter(user=context.client).exists()
