"""A new project owner cannot inherit the previous client's delivery history."""
from hashlib import sha256

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from freezegun import freeze_time
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import (
    ContractAmendment, ContractSignatureEvidence, DeliveryMessage,
    DeliveryOperation, DeliveryPhase, DeliveryPromptContext, DeliveryPromptSource,
    DeliveryPublication, DeliveryScope, DeliveryStage, DeliveryWorkspace,
    Project, ProjectAccessNote, ProjectAdminAccess, ProjectContract, Requirement,
    UserProfile,
)
from accounts.services.delivery_access import DeliveryConflict, project_for_actor
from accounts.services.delivery_client_transfer import assert_delivery_client_transfer_safe
from accounts.tests.delivery_authoring_helpers import pdf_bytes, signed_amendment, source_document
from accounts.tests.delivery_helpers import RECORDED_AT, build_delivery_context, prepare_prompt
from content.models import (
    AccountingChangeLog, CommunicationThread, Document, DocumentFolder,
    EntityHistory, EntityRevision,
)
from content.services import project_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT):
        result = build_delivery_context()
        result.document.signed_at = None
        result.document.signed_by = None
        result.document.signature_name = ''
        result.document.save(update_fields=['signed_at', 'signed_by', 'signature_name'])
        yield result


@pytest.fixture
def new_client(context):
    user = User.objects.create_user('transfer-client', 'new-client@example.test', 'test-password')
    return UserProfile.objects.create(user=user, role='client', is_onboarded=True, email_verified=True)


def transfer_state():
    """Keep owners, access data, frozen evidence and both audit trails observable."""
    models = (
        Project, ProjectAdminAccess, ProjectAccessNote, Document, DocumentFolder,
        CommunicationThread, ProjectContract, ContractAmendment, DeliveryScope,
        DeliveryPhase, DeliveryStage, Requirement, DeliveryWorkspace,
        DeliveryPublication, ContractSignatureEvidence, DeliveryPromptContext,
        DeliveryPromptSource, DeliveryMessage, DeliveryOperation,
        AccountingChangeLog, EntityHistory, EntityRevision,
    )
    return {model.__name__: list(model.objects.order_by('pk').values()) for model in models}


def create_publication(context):
    requirements = [
        {'id': requirement.pk, 'key': requirement.key, 'title': requirement.title,
         'version': requirement.version, 'guide': requirement.guide}
        for requirement in (context.first, context.second)
    ]
    return DeliveryPublication.objects.create(
        stage=context.stage, round=1, published_by=context.admin,
        payload={'id': context.stage.pk, 'key': context.stage.key,
                 'title': context.stage.title, 'version': context.stage.version,
                 'requirements': requirements},
    )


def create_amendment(context):
    document = source_document(context, 'Borrador del alcance adicional.')
    return ContractAmendment.objects.create(
        contract=context.contract, key='unsigned-amendment',
        title='Otrosí en borrador', document=document,
    )


def create_signature(context, *, amendment=None):
    body = pdf_bytes('Signed original contractual evidence.')
    parent = {'amendment': amendment} if amendment else {'contract': context.contract}
    return ContractSignatureEvidence.objects.create(
        **parent, file=ContentFile(body, name='signed-evidence.pdf'),
        sha256=sha256(body).hexdigest(), signer_name='Cliente anterior',
        signed_at=RECORDED_AT, attestation='Firma externa comprobada por el administrador.',
        attested_by=context.admin, source_snapshot={'title': 'Copia contractual firmada'},
    )


def create_amendment_signature(context):
    return create_signature(context, amendment=create_amendment(context))


def sign_contract_document(context):
    context.document.signed_at = RECORDED_AT
    context.document.signed_by = context.client
    context.document.signature_name = 'Cliente anterior'
    context.document.save(update_fields=['signed_at', 'signed_by', 'signature_name'])
    return context.document


def create_message(context, *, is_internal=False):
    return DeliveryMessage.objects.create(
        project=context.project, level='project', target_id=context.project.pk,
        actor=context.admin, message='Observación conservada del cliente anterior.',
        is_internal=is_internal,
    )


HISTORY_BUILDERS = {
    'publication': create_publication,
    'prompt_context': prepare_prompt,
    'contract_signature_evidence': create_signature,
    'amendment_signature_evidence': create_amendment_signature,
    'signed_contract_document': sign_contract_document,
    'signed_amendment_document': signed_amendment,
    'public_message': create_message,
}


@pytest.mark.parametrize('history', HISTORY_BUILDERS)
def test_client_history_rejects_transfer(context, new_client, history):
    """Fails if any frozen delivery fact exposes the previous client to a new owner."""
    HISTORY_BUILDERS[history](context)
    before = transfer_state()

    with pytest.raises(ValidationError) as caught:
        assert_delivery_client_transfer_safe(context.project, new_client.user, actor=context.admin)

    assert caught.value.detail['code'] == 'delivery_client_history_frozen'
    assert transfer_state() == before
    assert project_for_actor(context.project.pk, context.client).client_id == context.client.pk
    with pytest.raises(NotFound):
        project_for_actor(context.project.pk, new_client.user)


def test_client_cannot_authorize_transfer(context, new_client):
    """Fails if a client can invoke the administrative transfer boundary."""
    before = transfer_state()

    with pytest.raises(PermissionDenied) as caught:
        assert_delivery_client_transfer_safe(context.project, new_client.user, actor=context.client)

    assert caught.value.status_code == 403
    assert transfer_state() == before


def test_inactive_administrator_cannot_authorize_transfer(context, new_client):
    """Fails if deactivating an administrator leaves transfer authority available."""
    context.admin.is_active = False
    context.admin.save(update_fields=['is_active'])
    before = transfer_state()

    with pytest.raises(PermissionDenied) as caught:
        assert_delivery_client_transfer_safe(context.project, new_client.user, actor=context.admin)

    assert caught.value.status_code == 403
    assert transfer_state() == before


def test_stale_owner_rejects_transfer(context, new_client):
    """Fails if an old project instance can overwrite an ownership change."""
    Project.objects.filter(pk=context.project.pk).update(client=new_client.user)
    before = transfer_state()

    with pytest.raises(DeliveryConflict) as caught:
        assert_delivery_client_transfer_safe(context.project, new_client.user, actor=context.admin)

    assert caught.value.status_code == 409
    assert Project.objects.get(pk=context.project.pk).client_id == new_client.user_id
    assert transfer_state() == before


def test_same_owner_remains_allowed_with_client_history(context):
    """Fails if retaining the current owner is rejected because frozen history exists."""
    prepare_prompt(context)
    sign_contract_document(context)
    create_publication(context)
    create_message(context)
    before = transfer_state()

    result = assert_delivery_client_transfer_safe(context.project, context.client, actor=context.admin)

    assert result.pk == context.project.pk
    assert result.client_id == context.client.pk
    assert transfer_state() == before


def test_empty_project_remains_allowed_beside_another_project_history(context, new_client):
    """Fails if another project's history prevents transferring an empty project."""
    create_publication(context)
    project = Project.objects.create(name='Proyecto sin entregas', client=context.client)
    before = transfer_state()

    result = assert_delivery_client_transfer_safe(project, new_client.user)

    assert result.pk == project.pk
    assert result.client_id == context.client.pk
    assert transfer_state() == before


def test_unsigned_delivery_drafts_remain_allowed(context, new_client):
    """Fails if unsigned contract drafts or unpublished guides freeze ownership."""
    create_amendment(context)
    before = transfer_state()

    result = assert_delivery_client_transfer_safe(context.project, new_client.user, actor=context.admin)

    assert result.pk == context.project.pk
    assert result.client_id == context.client.pk
    assert transfer_state() == before


def test_internal_message_remains_allowed(context, new_client):
    """Fails if a private administrative note is treated as a client conversation."""
    note = create_message(context, is_internal=True)
    before = transfer_state()

    result = assert_delivery_client_transfer_safe(context.project, new_client.user, actor=context.admin)

    assert result.pk == context.project.pk
    assert DeliveryMessage.objects.get(pk=note.pk).is_internal is True
    assert transfer_state() == before


@pytest.mark.parametrize('mode', [project_service.MODE_MOVE, project_service.MODE_DETACH])
def test_project_change_client_preserves_frozen_history(context, new_client, mode):
    """Fails if the real project transfer bypasses delivery guards before cascading writes."""
    create_publication(context)
    before = transfer_state()

    with pytest.raises(ValidationError) as caught:
        project_service.change_client_apply(context.project, new_client, mode, context.admin)

    assert caught.value.detail['code'] == 'delivery_client_history_frozen'
    assert transfer_state() == before
    assert Project.objects.get(pk=context.project.pk).client_id == context.client.pk
    assert ProjectContract.objects.get(pk=context.contract.pk).document_id == context.document.pk
