"""A scoped response stays a reviewed draft until the team explicitly shares it."""
import json

import pytest
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError

from accounts.models import DeliveryMessage, DeliveryPromptContext, DeliveryStage, Notification, Requirement
from accounts.services import delivery_authoring as authoring
from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_access import DeliveryConflict
from accounts.tests.delivery_authoring_helpers import (
    api_for, build_authoring_context, captured_citation, endpoint, other_contract,
    reference, reply_message, reply_payload, signed_amendment, source_document,
)
from accounts.tests.delivery_helpers import GUIDE, RECORDED_AT, decisions, prepare_prompt, publish, stage_data, version

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT):
        yield build_authoring_context()


def prepare_reply(context, **overrides):
    return prepare_prompt(context, mode='reply', stage_id=context.stage.pk, **overrides)


def message(context, text, *, internal=False, actor=None, request_id='observation'):
    return delivery.add_message(context.project.pk, actor or context.admin, {
        'expected_version': version(context), 'request_id': request_id,
        'level': 'stage', 'target_id': context.stage.pk, 'message': text, 'is_internal': internal,
    })


def sibling_stage(context):
    stage = DeliveryStage.objects.create(phase=context.phase, key='sibling', title='SIBLING_STAGE_GUIDE')
    Requirement.objects.create(stage=stage, key='sibling-guide', title='SIBLING_REQUIREMENT', guide=GUIDE)
    delivery.publish_stage(context.project.pk, context.admin, stage.pk,
                           {'expected_version': version(context), 'request_id': 'publish-sibling'})
    delivery.add_message(context.project.pk, context.client, {
        'expected_version': version(context), 'request_id': 'sibling-observation',
        'level': 'stage', 'target_id': stage.pk, 'message': 'SIBLING_STAGE_OBSERVATION',
    })


def test_reply_requires_a_stage(context):
    """Fails if a response is prepared without identifying the client review stage."""
    with pytest.raises(ValidationError, match='Selecciona la etapa'):
        authoring.create_prompt_context(context.project.pk, context.admin, {
            'expected_version': 0, 'request_id': 'reply-without-stage', 'mode': 'reply',
        })

    assert DeliveryPromptContext.objects.count() == 0


def test_reply_requires_a_published_guide(context):
    """Fails if an internal draft is presented as a published client review context."""
    with pytest.raises(ValidationError, match='publicación'):
        prepare_reply(context)

    assert DeliveryPromptContext.objects.count() == 0


def test_reply_derives_its_contractual_selection_from_the_stage(context):
    """Fails if a response uses a contract or scope unrelated to its stage."""
    publish(context)

    prepared = authoring.create_prompt_context(context.project.pk, context.admin, {
        'expected_version': version(context), 'request_id': 'stage-derived-reply',
        'mode': 'reply', 'stage_id': context.stage.pk,
    })

    assert prepared['contract_id'] == context.contract.pk
    assert prepared['scope_id'] == context.scope.pk
    assert prepared['stage_id'] == context.stage.pk
    assert prepared['conversation']['publication_id'] == context.stage.publications.get().pk


def test_reply_includes_the_stage_applicable_amendment(context):
    """Fails if a response omits the amendment defining its stage scope."""
    amendment = signed_amendment(context)
    context.scope.amendment = amendment
    context.scope.save(update_fields=['amendment'])
    publish(context)

    prepared = prepare_reply(context)

    assert prepared['amendment_ids'] == [amendment.pk]
    assert prepared['sources'][1]['role'] == 'amendment'


def test_reply_cannot_override_the_stage_contract(context):
    """Fails if a response can replace its stage contract with another agreement."""
    other = other_contract(context)
    publish(context)

    with pytest.raises(ValidationError, match='conservar el contrato'):
        prepare_reply(context, contract_id=other.pk)

    assert DeliveryPromptContext.objects.count() == 0


def test_reply_retains_relevant_prior_review_rounds(context):
    """Fails if earlier observations disappear from the captured response history."""
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'objected')))
    message(context, 'Please clarify creation.', actor=context.client)
    message(context, 'PRIVATE_ADMIN_NOTE', internal=True, request_id='internal')
    publish(context, request_id='second-round')

    prepared = prepare_reply(context)

    assert len(prepared['conversation']['publications']) == 2
    assert prepared['conversation']['reviews'][1]['message'] == 'El registro no se guarda'
    assert prepared['conversation']['messages'][0]['message'] == 'Please clarify creation.'
    assert 'PRIVATE_ADMIN_NOTE' not in json.dumps(prepared)


def test_reply_preview_keeps_the_response_unsent(context, mailoutbox):
    """Fails if preview sends a response or creates client notifications."""
    publish(context)
    prepared = prepare_reply(context)
    notifications = Notification.objects.count()

    result = authoring.preview_reply(context.project.pk, context.admin, reply_payload(prepared), version(context))

    assert result['valid'] is True
    assert result['human_review_required'] is True
    assert DeliveryMessage.objects.count() == 0
    assert Notification.objects.count() == notifications
    assert mailoutbox == []


def test_missing_sources_block_a_definitive_outside_scope_claim(context):
    """Fails if incomplete evidence permits a definitive rejection as outside the contract."""
    publish(context)
    prepared = prepare_reply(context, missing_sources=['Signed annex cited in the agreement.'])

    with pytest.raises(ValidationError, match='incompletas'):
        authoring.preview_reply(context.project.pk, context.admin, reply_payload(prepared, classification='outside_scope'))

    assert DeliveryMessage.objects.count() == 0


def test_technical_reference_cannot_establish_a_scope_classification(context):
    """Fails if a technical reference alone decides whether a request belongs to the contract."""
    publish(context)
    document = source_document(context, 'Technical implementation note.')
    prepared = prepare_reply(context, sources=[reference(document)])
    payload = reply_payload(prepared)
    payload['classifications'][0]['citations'] = [captured_citation(prepared, 'reference')]

    with pytest.raises(ValidationError, match='contrato u otrosí'):
        authoring.preview_reply(context.project.pk, context.admin, payload)


def test_published_guide_alone_cannot_prove_a_request_is_outside_scope(context):
    """Fails if omission from a validation guide is treated as exclusion from the contract."""
    publish(context)
    prepared = prepare_reply(context)
    payload = reply_payload(prepared, classification='outside_scope')
    payload['classifications'][0]['citations'] = [captured_citation(prepared, 'published_guides')]

    with pytest.raises(ValidationError, match='contrato u otrosí'):
        authoring.preview_reply(context.project.pk, context.admin, payload)


def test_guides_context_cannot_be_used_for_a_stage_response(context):
    """Fails if a guide drafting context can impersonate a stage response context."""
    prepared = prepare_prompt(context)

    with pytest.raises(ValidationError, match='contexto de respuesta'):
        authoring.preview_reply(context.project.pk, context.admin, reply_payload(prepared))


def test_malformed_response_classification_returns_400(context):
    """Fails if an invalid response classification causes a server error or writes a message."""
    publish(context)
    prepared = prepare_reply(context)
    payload = reply_payload(prepared)
    payload['classifications'] = [None]

    response = api_for(context.admin).post(endpoint(context, 'reply/preview/'),
                                           {'expected_version': version(context), 'payload': payload}, format='json')

    assert response.status_code == 400
    assert DeliveryMessage.objects.count() == 0


def test_unreviewed_response_creates_no_notification(context):
    """Fails if a response reaches the client before explicit human review."""
    publish(context)
    prepared = prepare_reply(context)
    notifications = Notification.objects.count()

    with pytest.raises(ValidationError, match='Revisa el texto'):
        delivery.add_message(context.project.pk, context.admin, reply_message(context, prepared, human_reviewed=False))

    assert DeliveryMessage.objects.count() == 0
    assert Notification.objects.count() == notifications


def test_reviewed_response_can_be_shared_without_documents(context):
    """Fails if a reviewed response requires an unnecessary attached document."""
    publish(context)
    prepared = prepare_reply(context)

    result = delivery.add_message(context.project.pk, context.admin, reply_message(context, prepared))

    record = DeliveryMessage.objects.get()
    assert str(record.context_id) == prepared['id']
    assert record.documents.count() == 0
    assert record.source_references == reply_payload(prepared)['classifications'][0]['citations']
    assert result['version'] == 2


def test_response_cannot_be_shared_at_another_level(context):
    """Fails if a captured stage response can be sent to a different delivery level."""
    publish(context)
    prepared = prepare_reply(context)

    with pytest.raises(ValidationError, match='conservar la etapa'):
        delivery.add_message(context.project.pk, context.admin,
                             reply_message(context, prepared, level='project', target_id=context.project.pk))

    assert DeliveryMessage.objects.count() == 0


def test_new_client_observation_invalidates_the_prepared_response(context):
    """Fails if a response ignores client observations received after its context was captured."""
    publish(context)
    prepared = prepare_reply(context)
    message(context, 'A new request arrived.', actor=context.client)

    with pytest.raises(DeliveryConflict, match='observaciones cambiaron'):
        delivery.add_message(context.project.pk, context.admin, reply_message(context, prepared))

    assert DeliveryMessage.objects.count() == 1
    assert DeliveryMessage.objects.get().actor_id == context.client.pk


def test_client_response_view_excludes_private_source_provenance(context):
    """Fails if client message reads reveal private drafting source references."""
    publish(context)
    prepared = prepare_reply(context)
    delivery.add_message(context.project.pk, context.admin, reply_message(context, prepared))

    client_message = stage_data(delivery.overview(context.project.pk, context.client))['messages'][0]

    assert client_message['message'] == reply_payload(prepared)['response_text']
    assert 'context_id' not in client_message
    assert 'source_references' not in client_message


def test_reply_context_excludes_sibling_stage_observations(context):
    """Fails if another stage conversation enters the selected response context."""
    publish(context)
    sibling_stage(context)

    prepared = prepare_reply(context)

    assert 'SIBLING_STAGE_OBSERVATION' not in prepared['prompt']
    assert 'SIBLING_STAGE_GUIDE' not in prepared['prompt']


def test_message_citations_require_their_captured_context(context):
    """Fails if a message claims source citations without a retained context."""
    publish(context)
    prepared = prepare_reply(context)
    values = reply_message(context, prepared)
    values.pop('context_id')

    with pytest.raises(ValidationError, match='necesitan su contexto'):
        delivery.add_message(context.project.pk, context.admin, values)

    assert DeliveryMessage.objects.count() == 0


def test_response_prompt_explains_the_next_action_for_each_classification(context):
    """Fails if the response instructions omit the concrete action for a scope classification."""
    publish(context)

    prepared = prepare_reply(context)

    assert 'completar la guía pendiente' in prepared['prompt']
    assert 'propone una ampliación separada' in prepared['prompt']
    assert 'pide la aclaración concreta' in prepared['prompt']


def test_sending_mismatched_reply_citations_creates_no_message(context):
    """Fails if a reviewed reply can be shared with citations that differ from its validated classification."""
    publish(context)
    prepared = prepare_reply(context)
    values = reply_message(context, prepared)
    values['source_references'][0]['quote'] = 'creating records.'
    notifications = Notification.objects.count()
    current_version = version(context)

    response = api_for(context.admin).post(endpoint(context, 'messages/'), values, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'citation_message'
    assert DeliveryMessage.objects.count() == 0
    assert Notification.objects.count() == notifications
    assert version(context) == current_version
