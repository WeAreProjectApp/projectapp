"""Frozen contractual replies reject stale ownership, wording and incomplete scope."""
import pytest
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.models import (
    BugComment, BugReport, ChangeRequest, ChangeRequestComment, DeliveryMessage,
    DeliveryPublication, DeliveryWorkspace, Notification, Project, Requirement,
    RequirementReview, UserProfile,
)
from accounts.services import delivery_authoring as authoring
from accounts.services import delivery_contract_reply as replies
from accounts.services.delivery_access import DeliveryConflict
from accounts.tests.delivery_authoring_helpers import reply_payload
from accounts.tests.delivery_helpers import prepare_prompt, publish, version
from accounts.tests.test_delivery_contract_reply import (
    context as context, prepare, preview, provider as provider, publish_data,
)
from accounts.tests.test_delivery_prompt_retention import retained_proof_state

pytestmark = pytest.mark.django_db


def mutation_state():
    models = (
        Project, BugReport, BugComment, ChangeRequest, ChangeRequestComment,
        Requirement, RequirementReview, DeliveryPublication, DeliveryMessage,
        DeliveryWorkspace, Notification,
    )
    return {model.__name__: list(model.objects.order_by('pk').values()) for model in models}


class ChangeProvider:
    """Read real change-request evidence across the same opaque provider boundary."""

    def __init__(self, context):
        self.ticket = ChangeRequest.objects.create(
            project=context.project, created_by=context.client,
            title='Add the missing creation step',
            description='Expose the creation form described by the agreement.',
        )
        self.ticket_version = 1
        self.origin = {'origin_kind': 'general', 'project_id': context.project.pk}

    def __call__(self, *, project, actor, destination, lock=False):
        rows = ChangeRequest.objects.select_related('project')
        if lock:
            rows = rows.select_for_update()
        ticket = rows.get(pk=destination['id'], project=project)
        return {
            'kind': 'change', 'id': ticket.pk, 'project_id': ticket.project_id,
            'project_client_id': ticket.project.client_id, 'ticket_version': self.ticket_version,
            'is_archived': ticket.is_archived, 'origin': self.origin,
            'ticket': {'title': ticket.title, 'description': ticket.description},
            'conversation': list(ticket.comments.filter(is_internal=False).order_by('created_at', 'id').values(
                'id', 'user_id', 'content',
            )),
        }


@pytest.fixture
def change_provider(context):
    result = ChangeProvider(context)
    ChangeRequestComment.objects.create(
        change_request=result.ticket, user=context.client,
        content='Please include the missing creation step.',
    )
    ChangeRequestComment.objects.create(
        change_request=result.ticket, user=context.admin,
        content='PRIVATE_CHANGE_NOTE', is_internal=True,
    )
    return result


def test_incomplete_stage_sources_require_indeterminate(context):
    """Fails if a cited contract turns an incomplete stage context into a definitive inclusion."""
    publish(context)
    prepared = prepare_prompt(context, mode='reply', stage_id=context.stage.pk,
                              missing_sources=['Signed additional scope attachment.'])
    before = mutation_state()

    with pytest.raises(ValidationError) as caught:
        authoring.preview_reply(context.project.pk, context.admin, reply_payload(prepared), version(context))
    clarification = authoring.preview_reply(
        context.project.pk, context.admin, reply_payload(prepared, classification='indeterminate'), version(context),
    )

    assert caught.value.detail['code'] == 'scope_indeterminate'
    assert prepared['complete'] is False
    assert clarification['classifications'][0]['classification'] == 'indeterminate'
    assert mutation_state() == before
    assert DeliveryMessage.objects.count() == 0


def test_changed_project_owner_rejects_reply_publication(context, provider):
    """Fails if a captured reply exposes the previous owner's evidence after an external reassignment."""
    prepared = prepare(context, provider)
    replacement = User.objects.create_user('replacement-owner', 'replacement@example.test', 'test-password')
    UserProfile.objects.create(user=replacement, role='client')
    Project.objects.filter(pk=context.project.pk).update(client=replacement)
    before = mutation_state()
    evidence = retained_proof_state(context)

    with transaction.atomic(), pytest.raises(DeliveryConflict) as caught:
        replies.validate_contract_reply_for_publish(context.project.pk, context.admin,
                                                    publish_data(context, provider, prepared), target_provider=provider)

    assert caught.value.status_code == 409
    assert Project.objects.get(pk=context.project.pk).client_id == replacement.pk
    assert retained_proof_state(context) == evidence
    assert mutation_state() == before
    assert DeliveryMessage.objects.count() == 0


def test_another_administrator_cannot_publish_a_captured_reply(context, provider):
    """Fails if another active staff member can reuse a preparation owned by its original reviewer."""
    prepared = prepare(context, provider)
    other_admin = User.objects.create_user('other-reviewer', 'reviewer@example.test', 'test-password', is_staff=True)
    before = mutation_state()
    evidence = retained_proof_state(context)

    with transaction.atomic(), pytest.raises(ValidationError) as caught:
        replies.validate_contract_reply_for_publish(context.project.pk, other_admin,
                                                    publish_data(context, provider, prepared), target_provider=provider)

    assert caught.value.detail['code'] == 'context_owner'
    assert retained_proof_state(context) == evidence
    assert mutation_state() == before
    assert DeliveryMessage.objects.count() == 0


def test_changed_report_wording_invalidates_reply_publication(context, provider):
    """Fails if unchanged ticket versions hide report edits between preview and locked publication."""
    prepared = prepare(context, provider)
    accepted = preview(context, provider, prepared)
    BugReport.objects.filter(pk=provider.ticket.pk).update(description='The reported error now affects editing.')
    before = mutation_state()
    evidence = retained_proof_state(context)

    with transaction.atomic(), pytest.raises(DeliveryConflict) as caught:
        replies.validate_contract_reply_for_publish(context.project.pk, context.admin,
                                                    publish_data(context, provider, prepared), target_provider=provider)

    assert accepted['valid'] is True
    assert provider.ticket_version == prepared['destination']['ticket_version'] == 1
    assert caught.value.status_code == 409
    assert retained_proof_state(context) == evidence
    assert mutation_state() == before
    assert DeliveryMessage.objects.count() == 0


def test_change_request_uses_contractual_reply_without_state_mutation(context, change_provider):
    """Fails if a real change request needs a separate source engine or changes state during contractual review."""
    destination = {'kind': 'change', 'id': change_provider.ticket.pk}
    before = mutation_state()
    prepared = prepare(context, change_provider, destination=destination)
    accepted = preview(context, change_provider, prepared)
    data = publish_data(context, change_provider, prepared)
    data['destination'] = destination

    with transaction.atomic():
        result = replies.validate_contract_reply_for_publish(context.project.pk, context.admin, data,
                                                              target_provider=change_provider)

    assert accepted['destination']['kind'] == 'change'
    assert prepared['conversation']['origin'] == change_provider.origin
    assert prepared['conversation']['conversation'][0]['content'] == 'Please include the missing creation step.'
    assert 'PRIVATE_CHANGE_NOTE' not in prepared['prompt']
    assert result['scope_result'] == 'within_scope'
    assert result['contract_id'] == context.contract.pk
    assert mutation_state() == before
