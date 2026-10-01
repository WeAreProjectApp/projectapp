"""Test settings select a memory mailer without a per-test backend override."""
import pytest
from django.core import mail

from content.models import EmailDeliverySnapshot
from content.services.email_delivery_service import EmailDeliveryGateway, EmailMultiAlternatives


@pytest.mark.django_db
def test_default_gateway_delivers_into_memory(mailoutbox):
    """Fails if the inherited test configuration reaches SMTP instead of its outbox."""
    message = EmailMultiAlternatives(
        subject='Isolated gateway evidence', body='Retained only in memory.',
        from_email='sender@example.test', to=['fixture@example.test'],
    )

    sent = EmailDeliveryGateway.send(message, template_key='branded_email')

    assert sent == 1
    assert [(item.subject, item.to) for item in mail.outbox] == [
        ('Isolated gateway evidence', ['fixture@example.test']),
    ]
    assert EmailDeliverySnapshot.objects.get().subject == 'Isolated gateway evidence'
