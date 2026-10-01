"""The shared source engine accepts an opaque ticket provider without changing it."""
import copy

import pytest
from django.contrib.auth.models import User
from django.db import transaction
from freezegun import freeze_time
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import BugComment, BugReport, DeliveryMessage, DeliveryPromptContext, RequirementReview
from accounts.services import delivery_contract_reply as replies
from accounts.services.delivery_access import DeliveryConflict
from accounts.tests.delivery_authoring_helpers import build_authoring_context, other_contract, reply_payload
from accounts.tests.delivery_helpers import RECORDED_AT, version

pytestmark = pytest.mark.django_db


class TicketProvider:
    """Test boundary adapter reading real ticket rows, not a second source engine."""

    def __init__(self, context):
        self.ticket = BugReport.objects.create(project=context.project, reported_by=context.client,
                                               title='Cannot create a record', description='Save displays an error.')
        self.origin = {'origin_kind': 'general', 'project_id': context.project.pk}
        self.ticket_version = 1
        self.client_override = None

    def __call__(self, *, project, actor, destination, lock=False):
        rows = BugReport.objects.select_related('project')
        if lock:
            rows = rows.select_for_update()
        ticket = rows.get(pk=destination['id'])
        return {
            'kind': 'bug', 'id': ticket.pk, 'project_id': ticket.project_id,
            'project_client_id': self.client_override or ticket.project.client_id,
            'ticket_version': self.ticket_version, 'is_archived': ticket.is_archived,
            'origin': self.origin,
            'ticket': {'title': ticket.title, 'description': ticket.description},
            'conversation': list(ticket.comments.filter(is_internal=False).order_by('created_at', 'id').values(
                'id', 'user_id', 'content',
            )),
        }


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT):
        yield build_authoring_context()


@pytest.fixture
def provider(context):
    return TicketProvider(context)


def prepare(context, provider, **overrides):
    data = {'request_id': 'prepare-ticket-reply', 'expected_version': version(context),
            'expected_ticket_version': 1, 'destination': {'kind': 'bug', 'id': provider.ticket.pk},
            'contract_id': context.contract.pk}
    data.update(overrides)
    return replies.create_contract_reply_context(context.project.pk, context.admin, data, target_provider=provider)


def preview(context, provider, prepared, **overrides):
    data = reply_payload(prepared)
    data.update(overrides)
    return replies.preview_contract_reply(context.project.pk, context.admin, data,
                                          expected_version=version(context), expected_ticket_version=1,
                                          target_provider=provider)


def publish_data(context, provider, prepared):
    payload = reply_payload(prepared)
    return {'context_id': prepared['id'], 'message': payload['response_text'],
            'classifications': payload['classifications'],
            'source_references': payload['classifications'][0]['citations'], 'human_reviewed': True,
            'expected_version': version(context), 'expected_ticket_version': 1,
            'destination': {'kind': 'bug', 'id': provider.ticket.pk}}


def test_ticket_capture_freezes_public_origin_without_mutating_delivery(context, provider):
    """Fails if ticket preparation alters approvals, publishes responses or includes private comments."""
    BugComment.objects.create(bug_report=provider.ticket, user=context.client, content='PUBLIC_REQUEST')
    BugComment.objects.create(bug_report=provider.ticket, user=context.admin, content='INTERNAL_SECRET', is_internal=True)

    prepared = prepare(context, provider)

    assert prepared['destination']['ticket_version'] == 1
    assert prepared['conversation']['origin'] == provider.origin
    assert prepared['conversation']['conversation'][0]['content'] == 'PUBLIC_REQUEST'
    assert 'INTERNAL_SECRET' not in prepared['prompt']
    assert RequirementReview.objects.count() == 0
    assert DeliveryMessage.objects.count() == 0
    assert version(context) == 0


def test_ticket_without_contract_remains_indeterminate(context, provider):
    """Fails if a general bug needs a guessed contract or gains a contractual conclusion."""
    prepared = prepare(context, provider, contract_id=None)
    payload = copy.deepcopy(prepared['template'])

    result = replies.preview_contract_reply(context.project.pk, context.admin, payload,
                                            expected_version=0, expected_ticket_version=1, target_provider=provider)

    assert prepared['contract_id'] is None
    assert prepared['complete'] is False
    assert result['classifications'][0]['classification'] == 'indeterminate'
    assert result['source_references'] == []
    assert DeliveryPromptContext.objects.get(pk=prepared['id']).contract_id is None


@pytest.mark.parametrize('classification', ['inside_scope', 'outside_scope'])
def test_no_contract_blocks_definitive_scope_claim(context, provider, classification):
    """Fails if a missing contract is replaced by client statements or a delivery guide as authority."""
    prepared = prepare(context, provider, contract_id=None)
    payload = copy.deepcopy(prepared['template'])
    payload['classifications'][0]['classification'] = classification

    with pytest.raises(ValidationError, match='indeterminate'):
        replies.preview_contract_reply(context.project.pk, context.admin, payload,
                                        expected_version=0, expected_ticket_version=1, target_provider=provider)

    assert DeliveryMessage.objects.count() == 0


@pytest.mark.parametrize('classification', ['inside_scope', 'outside_scope'])
def test_incomplete_ticket_sources_require_indeterminate(context, provider, classification):
    """Fails if incomplete frozen sources permit a definitive inclusion or rejection."""
    prepared = prepare(context, provider, missing_sources=['Signed technical annex.'])
    payload = reply_payload(prepared, classification=classification)

    with pytest.raises(ValidationError, match='indeterminate'):
        replies.preview_contract_reply(context.project.pk, context.admin, payload,
                                        expected_version=0, expected_ticket_version=1, target_provider=provider)

    assert RequirementReview.objects.count() == 0


def test_ticket_preview_rejects_a_forged_contract_quote(context, provider):
    """Fails if the generic destination bypasses core exact-source citation validation."""
    prepared = prepare(context, provider)
    payload = reply_payload(prepared)
    payload['classifications'][0]['citations'][0]['quote'] = 'Invented contractual clause.'

    with pytest.raises(ValidationError, match='cita no existe'):
        replies.preview_contract_reply(context.project.pk, context.admin, payload,
                                        expected_version=0, expected_ticket_version=1, target_provider=provider)

    assert DeliveryMessage.objects.count() == 0


def test_ticket_preview_revalidates_public_conversation(context, provider):
    """Fails if another public observation is ignored when reusing the prepared reply."""
    prepared = prepare(context, provider)
    BugComment.objects.create(bug_report=provider.ticket, user=context.client, content='Another observation.')

    with pytest.raises(DeliveryConflict, match='conversación'):
        preview(context, provider, prepared)

    assert DeliveryMessage.objects.count() == 0


def test_ticket_preview_revalidates_frozen_origin(context, provider):
    """Fails if a mutable issue origin can change under a captured contractual response."""
    prepared = prepare(context, provider)
    provider.origin['requirement_version'] = 99

    with pytest.raises(DeliveryConflict, match='origen'):
        preview(context, provider, prepared)

    assert DeliveryPromptContext.objects.get(pk=prepared['id']).conversation['origin'] == {
        'origin_kind': 'general', 'project_id': context.project.pk,
    }


def test_ticket_preview_rejects_a_stale_ticket_version(context, provider):
    """Fails if workspace freshness substitutes for the independent ticket version."""
    prepared = prepare(context, provider)
    provider.ticket_version = 2

    with pytest.raises(DeliveryConflict, match='ticket cambió'):
        preview(context, provider, prepared)

    assert version(context) == 0


def test_ticket_provider_cannot_supply_a_foreign_owner(context, provider):
    """Fails if a ticket provider introduces evidence from another project client."""
    foreign = User.objects.create_user('foreign-ticket-owner', 'other@example.test')
    provider.client_override = foreign.pk

    with pytest.raises(NotFound):
        prepare(context, provider)

    assert DeliveryPromptContext.objects.count() == 0


def test_published_ticket_origin_keeps_its_contract(context, provider):
    """Fails if selecting sources from another contract overrides the ticket's frozen delivery origin."""
    provider.origin.update(origin_kind='published', contract_id=context.contract.pk)
    alternate = other_contract(context)

    with pytest.raises(ValidationError, match='Conserva el contrato'):
        prepare(context, provider, contract_id=alternate.pk)

    assert DeliveryPromptContext.objects.count() == 0


def test_unreviewed_ticket_reply_cannot_be_published(context, provider):
    """Fails if the publication adapter accepts machine-prepared wording without human review."""
    prepared = prepare(context, provider)
    data = publish_data(context, provider, prepared)
    data['human_reviewed'] = False

    with pytest.raises(ValidationError, match='Revisa el texto'):
        replies.validate_contract_reply_for_publish(context.project.pk, context.admin, data, target_provider=provider)

    assert DeliveryMessage.objects.count() == 0


def test_public_ticket_review_evidence_excludes_private_sources(context, provider):
    """Fails if public IssueResponse evidence receives prompt fragments or private captured context."""
    prepared = prepare(context, provider)

    with transaction.atomic():
        result = replies.validate_contract_reply_for_publish(context.project.pk, context.admin,
                                                              publish_data(context, provider, prepared), target_provider=provider)

    assert result['scope_result'] == 'within_scope'
    assert set(result['review_evidence']) == {'scope_result', 'human_reviewed', 'contract_id',
                                             'prepared_at', 'source_text_not_shared'}
    assert result['review_evidence']['human_reviewed'] is True
    assert result['context_id'] == prepared['id']
    assert RequirementReview.objects.count() == 0
    assert DeliveryMessage.objects.count() == 0


def test_reply_publication_keeps_destination_identity(context, provider):
    """Fails if an approved draft can be posted to a different ticket."""
    prepared = prepare(context, provider)
    data = publish_data(context, provider, prepared)
    data['destination'] = {'kind': 'bug', 'id': provider.ticket.pk + 1}

    with pytest.raises(ValidationError, match='destino'):
        replies.validate_contract_reply_for_publish(context.project.pk, context.admin, data, target_provider=provider)

    assert DeliveryMessage.objects.count() == 0


def test_ticket_capture_replay_keeps_one_immutable_context(context, provider):
    """Fails if repeating preparation duplicates frozen evidence or silently edits its origin."""
    first = prepare(context, provider)

    repeated = prepare(context, provider)

    assert repeated['id'] == first['id']
    assert DeliveryPromptContext.objects.count() == 1
    captured = DeliveryPromptContext.objects.get(pk=first['id'])
    captured.destination = {}
    with pytest.raises(ValueError, match='cannot be edited'):
        captured.save()
