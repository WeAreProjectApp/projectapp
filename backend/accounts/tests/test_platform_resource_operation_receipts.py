"""Resource receipt invariants shared by Platform and the native MCP manager."""
from types import SimpleNamespace

import pytest
from django.core.files.base import ContentFile
from django.db import transaction

from accounts.models import (
    Deliverable,
    DeliveryOperation,
    DeliveryWorkspace,
    Project,
    UserProfile,
)
from accounts.services import platform_resources
from accounts.services.delivery_access import DeliveryConflict

pytestmark = pytest.mark.django_db
REQUEST_ID = 'reviewed-resource-update'
ORIGINAL_BYTES = b'original resource bytes'
CONFIRMED_TITLE = 'Reviewed resource'
CONFIRMED_DESCRIPTION = 'Confirmed resource scope'


@pytest.fixture
def receipt_context(django_user_model):
    """Create actual administrator profiles and the client's isolated resource."""
    with transaction.atomic():
        admin = django_user_model.objects.create_user('receipt-admin', email='receipt-admin@example.test')
        other_admin = django_user_model.objects.create_user('receipt-other-admin', email='receipt-other-admin@example.test')
        client = django_user_model.objects.create_user('receipt-client', email='receipt-client@example.test')
        UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN)
        UserProfile.objects.create(user=other_admin, role=UserProfile.ROLE_ADMIN)
        UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT)
    project = Project.objects.create(name='Receipted resource project', client=client)
    resource = Deliverable.objects.create(
        project=project, uploaded_by=admin, title='Original resource',
        category=Deliverable.CATEGORY_DOCUMENTS,
        file=ContentFile(ORIGINAL_BYTES, name='resource.pdf'),
    )
    DeliveryWorkspace.objects.create(project=project, version=0)
    return SimpleNamespace(project=project, resource=resource, admin=admin, other_admin=other_admin)


@pytest.fixture
def reviewed_payload():
    """Keep the reviewed update payload identical across receipt retries."""
    return {'title': CONFIRMED_TITLE, 'description': CONFIRMED_DESCRIPTION}


def test_resource_update_receipt_replay_preserves_one_mutation(receipt_context, reviewed_payload):
    """Fail if receipt replay reapplies an already confirmed resource update."""
    context = receipt_context
    initial = platform_resources.update_resource(
        context.project.pk, context.admin, context.resource.pk, reviewed_payload,
        expected_version=0, request_id=REQUEST_ID,
    )
    context.resource.refresh_from_db()
    applied_at = context.resource.updated_at

    replay = platform_resources.update_resource(
        context.project.pk, context.admin, context.resource.pk, reviewed_payload,
        expected_version=0, request_id=REQUEST_ID,
    )

    context.resource.refresh_from_db()
    receipt = DeliveryOperation.objects.get(project=context.project, request_id=REQUEST_ID)
    assert replay == initial
    assert (context.resource.title, context.resource.description, context.resource.updated_at) == (
        CONFIRMED_TITLE, CONFIRMED_DESCRIPTION, applied_at,
    )
    assert DeliveryOperation.objects.filter(project=context.project).count() == 1
    assert DeliveryWorkspace.objects.get(project=context.project).version == 1
    assert (receipt.actor_id, receipt.response) == (context.admin.pk, initial)
    with context.resource.file.open('rb') as source:
        assert source.read() == ORIGINAL_BYTES


def test_resource_update_receipt_rejects_different_content(receipt_context, reviewed_payload):
    """Fail if one request identifier can apply a different resource update."""
    context = receipt_context
    initial = platform_resources.update_resource(
        context.project.pk, context.admin, context.resource.pk, reviewed_payload,
        expected_version=0, request_id=REQUEST_ID,
    )
    context.resource.refresh_from_db()
    applied_at = context.resource.updated_at
    original_fingerprint = DeliveryOperation.objects.get(
        project=context.project, request_id=REQUEST_ID,
    ).fingerprint

    with pytest.raises(DeliveryConflict, match='otra operación') as rejected:
        platform_resources.update_resource(
            context.project.pk, context.admin, context.resource.pk,
            {'title': 'Unreviewed replacement', 'description': CONFIRMED_DESCRIPTION},
            expected_version=1, request_id=REQUEST_ID,
        )

    context.resource.refresh_from_db()
    receipt = DeliveryOperation.objects.get(project=context.project, request_id=REQUEST_ID)
    assert rejected.value.status_code == 409
    assert (context.resource.title, context.resource.description, context.resource.updated_at) == (
        CONFIRMED_TITLE, CONFIRMED_DESCRIPTION, applied_at,
    )
    assert DeliveryOperation.objects.filter(project=context.project).count() == 1
    assert DeliveryWorkspace.objects.get(project=context.project).version == 1
    assert (receipt.actor_id, receipt.fingerprint, receipt.response) == (
        context.admin.pk, original_fingerprint, initial,
    )
    with context.resource.file.open('rb') as source:
        assert source.read() == ORIGINAL_BYTES


def test_resource_update_receipt_rejects_another_administrator(receipt_context, reviewed_payload):
    """Fail if another administrator can reuse the original actor's receipt."""
    context = receipt_context
    initial = platform_resources.update_resource(
        context.project.pk, context.admin, context.resource.pk, reviewed_payload,
        expected_version=0, request_id=REQUEST_ID,
    )
    context.resource.refresh_from_db()
    applied_at = context.resource.updated_at
    original_fingerprint = DeliveryOperation.objects.get(
        project=context.project, request_id=REQUEST_ID,
    ).fingerprint

    with pytest.raises(DeliveryConflict, match='otra operación') as rejected:
        platform_resources.update_resource(
            context.project.pk, context.other_admin, context.resource.pk, reviewed_payload,
            expected_version=1, request_id=REQUEST_ID,
        )

    context.resource.refresh_from_db()
    receipt = DeliveryOperation.objects.get(project=context.project, request_id=REQUEST_ID)
    assert rejected.value.status_code == 409
    assert (context.resource.title, context.resource.description, context.resource.updated_at) == (
        CONFIRMED_TITLE, CONFIRMED_DESCRIPTION, applied_at,
    )
    assert DeliveryOperation.objects.filter(project=context.project).count() == 1
    assert DeliveryWorkspace.objects.get(project=context.project).version == 1
    assert (receipt.actor_id, receipt.fingerprint, receipt.response) == (
        context.admin.pk, original_fingerprint, initial,
    )
    with context.resource.file.open('rb') as source:
        assert source.read() == ORIGINAL_BYTES
