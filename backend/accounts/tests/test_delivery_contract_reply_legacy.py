"""A provider's legitimate legacy version zero is a version, not missing data."""
import pytest

from accounts.models import DeliveryPromptContext
from accounts.services import delivery_contract_reply as replies
from accounts.services.delivery_access import DeliveryConflict
from accounts.tests.delivery_authoring_helpers import reply_payload
from accounts.tests.test_delivery_contract_reply import context, prepare, provider  # noqa: F401

pytestmark = pytest.mark.django_db


def test_legacy_ticket_version_zero_can_prepare_contractual_preview(context, provider):
    """Fails if the first grounded response to a real legacy ticket requires rewriting its version."""
    provider.ticket_version = 0
    original_status = provider.ticket.status
    prepared = prepare(context, provider, expected_ticket_version=0)

    result = replies.preview_contract_reply(context.project.pk, context.admin, reply_payload(prepared),
                                            expected_version=0, expected_ticket_version=0, target_provider=provider)

    assert prepared['destination']['ticket_version'] == 0
    assert result['ticket_version'] == 0
    assert result['classifications'][0]['classification'] == 'inside_scope'
    assert DeliveryPromptContext.objects.get(pk=prepared['id']).destination['ticket_version'] == 0
    provider.ticket.refresh_from_db()
    assert provider.ticket.status == original_status


def test_legacy_ticket_version_change_rejects_prepared_preview(context, provider):
    """Fails if accepting version zero disables the independent stale-ticket conflict guard."""
    provider.ticket_version = 0
    prepared = prepare(context, provider, expected_ticket_version=0)
    provider.ticket_version = 1

    with pytest.raises(DeliveryConflict, match='ticket cambió'):
        replies.preview_contract_reply(context.project.pk, context.admin, reply_payload(prepared),
                                        expected_version=0, expected_ticket_version=0, target_provider=provider)

    assert DeliveryPromptContext.objects.get(pk=prepared['id']).destination['ticket_version'] == 0
    assert DeliveryPromptContext.objects.count() == 1
