"""Public effects require an exact owned preview; private preparation stays direct."""
import pytest
from accounts.models import (
    BugComment,
    BugReport,
    DeliveryDocumentLink,
    DeliveryMessage,
    IssueResponse,
    ProjectContract,
)
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from content.models import Document
from content.tests.views.test_mcp_delivery import (
    SIGNED_PDF,
    current_version,
)
from content.tests.views.test_mcp_delivery import call_projects as call_projects
from content.tests.views.test_mcp_delivery import draft as draft

pytestmark = pytest.mark.django_db


@pytest.fixture
def public_project(draft):
    """Use the real client recipient and preserve the contract's existing source."""
    draft.client.email = 'public-recipient@example.test'
    draft.client.save(update_fields=['email'])
    return draft


def message_arguments(call, context, *, internal=False):
    """Select the actual project audience without impersonating its client."""
    return {'project_id': context.project.pk, 'level': 'project', 'target_id': context.project.pk,
        'message': 'Exact reviewed response', 'is_internal': internal,
        'expected_version': current_version(call, context.project), 'request_id': 'public-reviewed-message'}


@pytest.fixture
def attachment(public_project):
    """Keep actual canonical PDF bytes under the authorized project/client."""
    source = public_project.document
    doc = Document.objects.create(document_type=source.document_type, project=public_project.project,
        client_user=public_project.client, title='Exact reviewed attachment', is_client_visible=True)
    doc.generated_file.save('reviewed.pdf', ContentFile(SIGNED_PDF))
    return doc


@pytest.fixture
def issue(call_projects, public_project):
    """Create the real ticket through MCP before evaluating its public response."""
    return call_projects('create_bug_report', {'project_id': public_project.project.pk,
        'payload': {'title': 'General failure'}})


def test_public_delivery_message_preview_keeps_the_portal_unchanged(call_projects, public_project):
    """Fails if a default public message writes before its explicit confirmation."""
    preview = call_projects('add_delivery_message', message_arguments(call_projects, public_project))
    assert preview['confirmation_required'] is True
    assert DeliveryMessage.objects.count() == 0


def test_public_delivery_message_preview_identifies_the_exact_recipient(call_projects, public_project):
    """Fails if the confirmation omits its actual audience or reviewed message."""
    arguments = message_arguments(call_projects, public_project)
    preview = call_projects('add_delivery_message', arguments)
    assert preview['impact']['recipient']['user_id'] == public_project.client.pk
    assert preview['impact']['recipient']['email'] == public_project.client.email
    assert preview['impact']['selection']['message'] == arguments['message']


def test_internal_delivery_message_executes_without_a_public_confirmation(call_projects, public_project):
    """Fails if private preparation inherits the external communication gate."""
    call_projects('add_delivery_message', message_arguments(call_projects, public_project, internal=True))
    message = DeliveryMessage.objects.get()
    assert message.is_internal is True
    assert message.message == 'Exact reviewed response'


def test_confirmed_public_message_persists_only_once(call_projects, public_project):
    """Fails if confirmation replay creates another visible communication."""
    preview = call_projects('add_delivery_message', message_arguments(call_projects, public_project))
    payload = {'confirmation_id': preview['confirmation_id']}
    call_projects('confirm_action', payload)
    replay = call_projects('confirm_action', payload)
    assert replay['replayed'] is True
    assert DeliveryMessage.objects.count() == 1


def test_public_confirmation_rejects_a_changed_project_recipient(call_projects, public_project, django_user_model):
    """Fails if the same workspace version lets another client receive the message."""
    preview = call_projects('add_delivery_message', message_arguments(call_projects, public_project))
    other = django_user_model.objects.create_user('changed-public-owner', email='other@example.test')
    public_project.project.client = other
    public_project.project.save(update_fields=['client'])
    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)
    assert error['code'] == 'STALE_VERSION'
    assert DeliveryMessage.objects.count() == 0


def test_public_confirmation_rejects_a_changed_recipient_email(call_projects, public_project):
    """Fails if the recipient's address changes without a workspace-version bump."""
    preview = call_projects('add_delivery_message', message_arguments(call_projects, public_project))
    public_project.client.email = 'changed-recipient@example.test'
    public_project.client.save(update_fields=['email'])
    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)
    assert error['code'] == 'STALE_VERSION'
    assert DeliveryMessage.objects.count() == 0


def test_public_contract_visibility_requires_confirmation(call_projects, public_project):
    """Fails if enabling a client-visible contract bypasses the public gate."""
    ProjectContract.objects.filter(pk=public_project.contract.pk).update(client_visible=False)
    preview = call_projects('update_delivery_contract', {'project_id': public_project.project.pk,
        'node_id': public_project.contract.pk, 'expected_version': current_version(call_projects, public_project.project),
        'data': {'client_visible': True}})
    assert preview['confirmation_required'] is True
    assert ProjectContract.objects.get(pk=public_project.contract.pk).client_visible is False


def test_private_contract_creation_remains_direct(call_projects, public_project):
    """Fails if an unsigned private draft requires public-communication approval."""
    call_projects('create_delivery_contract', {'project_id': public_project.project.pk,
        'expected_version': current_version(call_projects, public_project.project),
        'data': {'key': 'private-only', 'title': 'Private draft', 'document_id': public_project.document.pk,
                 'client_visible': False}})
    assert ProjectContract.objects.get(key='private-only').client_visible is False


def test_public_document_link_preview_creates_no_association(call_projects, public_project, attachment):
    """Fails if a project-level document becomes client-visible before review."""
    preview = call_projects('link_delivery_document', {'project_id': public_project.project.pk,
        'expected_version': current_version(call_projects, public_project.project),
        'level': 'project', 'target_id': public_project.project.pk, 'document_id': attachment.pk})
    assert preview['confirmation_required'] is True
    assert DeliveryDocumentLink.objects.count() == 0


def test_public_issue_response_preview_creates_no_response(call_projects, public_project, issue):
    """Fails if the team sends a public answer without showing its exact content."""
    preview = call_projects('evaluate_issue_report', {'project_id': public_project.project.pk,
        'kind': 'bug', 'ticket_id': issue['id'], 'payload': {'expected_version': issue['version'],
        'admin_response': 'Exact public issue response'}})
    assert preview['confirmation_required'] is True
    assert IssueResponse.objects.count() == 0
    ticket = BugReport.objects.get(pk=issue['id'])
    assert (ticket.status, ticket.version) == ('reported', issue['version'])


def test_internal_issue_response_remains_direct(call_projects, public_project, issue):
    """Fails if a private note with no public status change needs confirmation."""
    call_projects('evaluate_issue_report', {'project_id': public_project.project.pk,
        'kind': 'bug', 'ticket_id': issue['id'], 'payload': {'expected_version': issue['version'],
        'admin_response': 'Private team note', 'is_internal': True}})
    assert IssueResponse.objects.get().is_internal is True


def test_public_issue_status_requires_confirmation_for_an_internal_note(call_projects, public_project, issue):
    """Fails if an internal flag hides a public ticket status mutation."""
    preview = call_projects('evaluate_issue_report', {'project_id': public_project.project.pk,
        'kind': 'bug', 'ticket_id': issue['id'], 'payload': {'expected_version': issue['version'],
        'admin_response': 'Private team note', 'is_internal': True, 'status': 'resolved'}})
    assert preview['confirmation_required'] is True
    assert IssueResponse.objects.count() == 0


def test_public_issue_comment_requires_confirmation(call_projects, public_project, issue):
    """Fails if a visible comment bypasses the same communication gate."""
    preview = call_projects('comment_issue_report', {'project_id': public_project.project.pk,
        'kind': 'bug', 'ticket_id': issue['id'], 'payload': {'expected_version': issue['version'],
        'content': 'Exact visible comment'}})
    assert preview['confirmation_required'] is True
    assert BugComment.objects.count() == 0
    ticket = BugReport.objects.get(pk=issue['id'])
    assert (ticket.status, ticket.version) == ('reported', issue['version'])


def test_public_issue_bulk_preview_keeps_every_response_unwritten(call_projects, public_project, issue):
    """Fails if bulk publication writes any public response before approval."""
    preview = call_projects('bulk_evaluate_issue_reports', {'project_id': public_project.project.pk,
        'kind': 'bug', 'items': [{'id': issue['id'], 'expected_version': issue['version'],
        'admin_response': 'Exact visible batch entry'}]})
    assert preview['confirmation_required'] is True
    assert IssueResponse.objects.count() == 0


def test_public_document_confirmation_rejects_changed_bytes(call_projects, public_project, attachment):
    """Fails if source bytes can change without updating the workspace version."""
    preview = call_projects('link_delivery_document', {'project_id': public_project.project.pk,
        'expected_version': current_version(call_projects, public_project.project),
        'level': 'project', 'target_id': public_project.project.pk, 'document_id': attachment.pk})
    attachment.generated_file.save('changed.pdf', ContentFile(SIGNED_PDF + b'changed bytes'))
    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)
    assert error['code'] == 'STALE_VERSION'
    assert DeliveryDocumentLink.objects.count() == 0


def test_public_visibility_rejects_a_coercing_boolean(call_projects, public_project):
    """Fails if a string flag becomes public in DRF after bypassing the predicate."""
    ProjectContract.objects.filter(pk=public_project.contract.pk).update(client_visible=False)
    call_projects('update_delivery_contract', {'project_id': public_project.project.pk,
        'node_id': public_project.contract.pk, 'expected_version': current_version(call_projects, public_project.project),
        'data': {'client_visible': 'true'}}, expect_error=True)
    assert ProjectContract.objects.get(pk=public_project.contract.pk).client_visible is False


def test_private_draft_document_link_remains_direct(call_projects, public_project, attachment):
    """Fails if a private draft association is treated as a public release."""
    attachment.is_client_visible = False
    attachment.save(update_fields=['is_client_visible'])
    call_projects('link_delivery_document', {'project_id': public_project.project.pk,
        'expected_version': current_version(call_projects, public_project.project),
        'level': 'stage', 'target_id': public_project.stage.pk, 'document_id': attachment.pk})
    assert DeliveryDocumentLink.objects.get().stage_id == public_project.stage.pk


class ChangeRecipientOnRead:
    """Change the recipient at the external file-read boundary after preview."""

    def __init__(self, opener, user_id):
        """Keep the real storage opener and mutate the recipient only once."""
        self.opener, self.user_id, self.changed = opener, user_id, False

    def __call__(self, name, mode='rb', **kwargs):
        if not self.changed:
            self.changed = True
            get_user_model().objects.filter(pk=self.user_id).update(email='raced-recipient@example.test')
        return self.opener(name, mode, **kwargs)


def test_public_apply_rechecks_recipient_after_the_optimistic_etag(call_projects, public_project, attachment, monkeypatch):
    """Fails if recipient validation occurs only before the project is locked."""
    arguments = {**message_arguments(call_projects, public_project), 'document_ids': [attachment.pk]}
    preview = call_projects('add_delivery_message', arguments)
    storage = attachment.generated_file.storage
    monkeypatch.setattr(storage, 'open', ChangeRecipientOnRead(storage.open, public_project.client.pk))
    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)
    assert error['code'] == 'STALE_VERSION'
    assert DeliveryMessage.objects.count() == 0


def test_public_document_unlink_preview_keeps_the_visible_association(call_projects, public_project, attachment, superuser):
    """Fails if removing a visible association bypasses public-effect approval."""
    link = DeliveryDocumentLink.objects.create(project=public_project.project, document=attachment,
        level='project', created_by=superuser)
    preview = call_projects('unlink_delivery_document', {'project_id': public_project.project.pk,
        'expected_version': current_version(call_projects, public_project.project), 'link_id': link.pk})
    assert preview['confirmation_required'] is True
    assert DeliveryDocumentLink.objects.filter(pk=link.pk).exists()


def test_public_file_impact_contains_the_actual_canonical_hash(call_projects, public_project, attachment):
    """Fails if the preview describes ids without the exact canonical file bytes."""
    import hashlib
    preview = call_projects('link_delivery_document', {'project_id': public_project.project.pk,
        'expected_version': current_version(call_projects, public_project.project),
        'level': 'project', 'target_id': public_project.project.pk, 'document_id': attachment.pk})
    assert preview['impact']['files'][0]['file']['sha256'] == hashlib.sha256(SIGNED_PDF).hexdigest()
