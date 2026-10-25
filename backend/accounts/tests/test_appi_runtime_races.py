"""Race regressions for Appi workers crossing provider I/O boundaries."""
from uuid import uuid4

import pytest

from accounts.models import Project
from accounts.models_ai import PlatformAIQuotaReservation
from accounts.models_appi import AppiConversation, AppiTurn
from accounts.services import appi, appi_cache
from accounts.services.platform_ai import AIUnavailable, cache_version

from .appi_test_support import conversation
from .test_appi_jev import ProviderReply, routing_payload

pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.appi_test_support',)


def grounded_payload():
    """Return the valid closed Jev decision that accepts a writer's supplied facts."""
    return {'answers': {'grounded': {
        'type': 'choice',
        'choice': 'supported',
        'confidence': 0.99,
        'probabilities': {'supported': 1, 'unsupported': 0},
    }}, 'usage': {'input_tokens': 5}}


def writer_payload():
    """Return a bounded writer response whose summary is grounded by the initial status fact."""
    return {
        'content': [{'type': 'text', 'text': '{"summary":"El proyecto tiene avance registrado.","fact_ids":["f1"]}'}],
        'stop_reason': 'end_turn',
        'usage': {'input_tokens': 8, 'output_tokens': 6},
    }


class AppiHttpDispatcher:
    """Route Jev and writer HTTP calls through real Appi provider adapters deterministically."""

    def __init__(self, *, after_writer=None, first_routing_status=200):
        """Record requests and optionally interleave one database action during writer I/O."""
        self.after_writer = after_writer
        self.first_routing_status = first_routing_status
        self.routing_calls = 0
        self.writer_calls = 0

    def __call__(self, url, **kwargs):
        """Return the closed provider reply selected by the outbound endpoint and payload shape."""
        if 'typesafe.ai' in url:
            self.routing_calls += 1
            if self.routing_calls == 1 and self.first_routing_status != 200:
                response = ProviderReply({})
                response.status_code = self.first_routing_status
                return response
            if set(kwargs['json']['questions']) == {'grounded'}:
                return ProviderReply(grounded_payload())
            return ProviderReply(routing_payload())
        self.writer_calls += 1
        if self.after_writer:
            self.after_writer()
        return ProviderReply(writer_payload())


class ProgressChange:
    """Persist a progress update while the external writer request is in flight."""

    def __init__(self, project):
        """Keep the project whose fresh snapshot must supersede the writer draft."""
        self.project = project

    def __call__(self):
        """Replace the recorded project progress with the newer source-of-truth value."""
        Project.objects.filter(pk=self.project.pk).update(progress=75)


class ConversationDeletion:
    """Delete a conversation while its writer call is in flight."""

    def __init__(self, actor, conversation_id):
        """Keep the private conversation targeted by the real deletion service."""
        self.actor = actor
        self.conversation_id = conversation_id

    def __call__(self):
        """Delete the conversation and refund its active turn through the production service."""
        appi.delete_conversation(self.actor, self.conversation_id)


def submit_question(context, item, request_id):
    """Submit one explainable status question without running the queued task callback."""
    return appi.submit(
        context.actor,
        item.pk,
        {'question': 'Explícame el estado del proyecto', 'request_id': request_id},
    )


def test_writer_race_uses_fresh_template_after_project_progress_changes(appi_context, monkeypatch):
    """Fails if a successful writer summary survives after the project progress changes during its HTTP call."""
    item = conversation(appi_context)
    dispatcher = AppiHttpDispatcher(after_writer=ProgressChange(appi_context.project))
    monkeypatch.setattr('accounts.services.appi_jev.requests.post', dispatcher)
    turn = submit_question(appi_context, item, uuid4())

    appi.process(str(turn.pk))

    turn.refresh_from_db()
    quota = PlatformAIQuotaReservation.objects.get(pk=turn.quota_id)
    assert turn.status == 'ready'
    assert turn.answer['provenance'] == 'template'
    assert '75 %' in turn.answer['text']
    assert 'El proyecto tiene avance registrado.' not in turn.answer['text']
    assert quota.status == 'consumed'
    assert dispatcher.writer_calls == 1
    assert dispatcher.routing_calls == 2


def test_delete_conversation_during_writer_does_not_resurrect_private_turn(appi_context, monkeypatch):
    """Fails if a worker recreates a deleted conversation, answer, cache entry, or charged reservation after writer I/O."""
    item = conversation(appi_context)
    dispatcher = AppiHttpDispatcher(after_writer=ConversationDeletion(appi_context.actor, item.pk))
    monkeypatch.setattr('accounts.services.appi_jev.requests.post', dispatcher)
    turn = submit_question(appi_context, item, uuid4())
    quota_id = turn.quota_id
    exact_key = turn.exact_key

    appi.process(str(turn.pk))

    quota = PlatformAIQuotaReservation.objects.get(pk=quota_id)
    cached = appi_cache.lookup(
        appi_context.actor,
        appi_context.project.pk,
        'exact',
        exact_key,
        appi_context.config,
        cache_version('chatbot'),
    )
    assert not AppiConversation.objects.filter(pk=item.pk).exists()
    assert not AppiTurn.objects.filter(pk=turn.pk).exists()
    assert quota.status == 'refunded'
    assert cached is None
    assert dispatcher.writer_calls == 1


def test_failed_jev_request_reuses_the_original_logical_request(appi_context, monkeypatch):
    """Fails if a failed Jev routing request cannot retry with its original turn and reservation."""
    item = conversation(appi_context)
    request_id = uuid4()
    dispatcher = AppiHttpDispatcher(first_routing_status=503)
    monkeypatch.setattr('accounts.services.appi_jev.requests.post', dispatcher)
    first = submit_question(appi_context, item, request_id)

    with pytest.raises(AIUnavailable):
        appi.process(str(first.pk))

    first.refresh_from_db()
    failed_quota = PlatformAIQuotaReservation.objects.get(pk=first.quota_id)
    assert first.status == 'failed'
    assert failed_quota.status == 'refunded'

    retried = submit_question(appi_context, item, request_id)
    appi.process(str(retried.pk))
    retried.refresh_from_db()
    quota = PlatformAIQuotaReservation.objects.get(pk=retried.quota_id)

    assert retried.pk == first.pk
    assert retried.quota_id == first.quota_id
    assert retried.status == 'ready'
    assert quota.status == 'consumed'
    assert AppiTurn.objects.filter(actor=appi_context.actor).count() == 1
    assert PlatformAIQuotaReservation.objects.filter(actor=appi_context.actor).count() == 1
    assert dispatcher.routing_calls == 3
