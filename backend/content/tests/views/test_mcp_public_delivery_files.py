"""Canonical signed bytes and explicit unsigned render provenance remain usable."""
import hashlib

import pytest
from accounts.models import DeliveryDocumentLink, DeliveryMessage, ProjectContract

from content.tests.views.test_mcp_delivery import (
    SIGNED_PDF,
    current_version,
    sign_contract,
)
from content.tests.views.test_mcp_delivery import call_projects as call_projects
from content.tests.views.test_mcp_delivery import draft as draft
from content.tests.views.test_mcp_public_delivery_confirmation import (
    attachment as attachment,
)
from content.tests.views.test_mcp_public_delivery_confirmation import (
    public_project as public_project,
)

pytestmark = pytest.mark.django_db


def contract_arguments(call, context):
    """Edit a visible title without changing its signed contractual source."""
    return {'project_id': context.project.pk, 'node_id': context.contract.pk,
        'expected_version': current_version(call, context.project), 'title': 'Reviewed public title'}


def document_arguments(call, context, doc):
    """Use the same owned source and actual public project association."""
    return {'project_id': context.project.pk, 'level': 'project', 'target_id': context.project.pk,
        'document_id': doc.pk, 'expected_version': current_version(call, context.project)}


def test_signed_contract_preview_uses_the_evidence_when_live_cache_is_missing(call_projects, public_project, superuser):
    """Fails if signed authority is replaced by a requirement for the live cache."""
    sign_contract(public_project, superuser)
    public_project.document.generated_file = ''
    public_project.document.save(update_fields=['generated_file'])
    preview = call_projects('update_delivery_contract', contract_arguments(call_projects, public_project))
    assert preview['confirmation_required'] is True
    assert preview['impact']['files'][0]['sha256'] == hashlib.sha256(SIGNED_PDF).hexdigest()


def test_signed_contract_confirmation_ignores_an_unexposed_live_draft_edit(call_projects, public_project, superuser):
    """Fails if a draft not served to the client invalidates its signed source."""
    sign_contract(public_project, superuser)
    arguments = contract_arguments(call_projects, public_project)
    arguments.pop('title')
    arguments['client_visible'] = False
    preview = call_projects('update_delivery_contract', arguments)
    public_project.document.content_markdown = '# Changed live draft only'
    public_project.document.save(update_fields=['content_markdown'])
    call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']})
    assert ProjectContract.objects.get(pk=public_project.contract.pk).client_visible is False


def test_staff_client_private_draft_link_remains_direct(call_projects, public_project, attachment):
    """Fails if a client's staff flag changes the real JWT visibility projection."""
    public_project.client.is_staff = True
    public_project.client.save(update_fields=['is_staff'])
    attachment.is_client_visible = False
    attachment.save(update_fields=['is_client_visible'])
    call_projects('link_delivery_document', {**document_arguments(call_projects, public_project, attachment),
        'level': 'stage', 'target_id': public_project.stage.pk})
    assert DeliveryDocumentLink.objects.get().stage_id == public_project.stage.pk


def test_staff_client_draft_message_cannot_become_public(call_projects, public_project):
    """Fails if a staff recipient makes an unpublished stage look client-visible."""
    public_project.client.is_staff = True
    public_project.client.save(update_fields=['is_staff'])
    call_projects('add_delivery_message', {'project_id': public_project.project.pk,
        'level': 'stage', 'target_id': public_project.stage.pk, 'message': 'Not published',
        'expected_version': current_version(call_projects, public_project.project), 'request_id': 'staff-hidden'},
        expect_error=True)
    assert DeliveryMessage.objects.count() == 0


def test_unsigned_source_without_pdf_shows_render_provenance_without_writing(call_projects, public_project, attachment):
    """Fails if preview invents a binary hash or generates a hidden PDF cache."""
    attachment.generated_file = ''
    attachment.content_markdown = '# Reviewed unsigned content'
    attachment.save(update_fields=['generated_file', 'content_markdown'])
    preview = call_projects('link_delivery_document', document_arguments(call_projects, public_project, attachment))
    source = preview['impact']['files'][0]
    assert source['source_mode'] == 'render_on_read'
    assert source['file'] is None
    assert source['content_markdown'] == '# Reviewed unsigned content'
    assert source['renderer_provenance']['renderer'] == 'DocumentPdfService'
    attachment.content_markdown = '# Revised unsigned content'
    attachment.save(update_fields=['content_markdown'])
    revised = call_projects('link_delivery_document',
        document_arguments(call_projects, public_project, attachment))['impact']['files'][0]
    assert revised['content_markdown'] == '# Revised unsigned content'
    assert revised['renderer_provenance'] == source['renderer_provenance']
    assert revised['content_sha256'] != source['content_sha256']
    assert revised['file'] is None
    assert DeliveryDocumentLink.objects.count() == 0
    attachment.refresh_from_db()
    assert not attachment.generated_file


def test_unsigned_source_without_pdf_can_complete_the_reviewed_action(call_projects, public_project, attachment):
    """Fails if a truthfully described render source leaves the workflow blocked."""
    attachment.generated_file = ''
    attachment.content_markdown = '# Reviewed unsigned content'
    attachment.save(update_fields=['generated_file', 'content_markdown'])
    preview = call_projects('link_delivery_document', document_arguments(call_projects, public_project, attachment))
    call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']})
    assert DeliveryDocumentLink.objects.get().document_id == attachment.pk


def test_unsigned_source_change_rejects_the_prepared_confirmation(call_projects, public_project, attachment):
    """Fails if an unsigned render source changes without a workspace bump."""
    attachment.generated_file = ''
    attachment.content_markdown = '# Initially reviewed content'
    attachment.save(update_fields=['generated_file', 'content_markdown'])
    preview = call_projects('link_delivery_document', document_arguments(call_projects, public_project, attachment))
    attachment.content_markdown = '# Changed after review'
    attachment.save(update_fields=['content_markdown'])
    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)
    assert error['code'] == 'STALE_VERSION'
    assert DeliveryDocumentLink.objects.count() == 0
