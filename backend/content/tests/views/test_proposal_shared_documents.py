"""Shared identities preserve approved bytes while proposal sources evolve."""
from io import StringIO
import json

import pytest
from django.core import mail
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from accounts.models import Project
from content.models import (
    Document,
    DocumentFolder,
    ProposalApprovalFile,
    ProposalApprovalPackage,
    ProposalChangeLog,
    ProposalDocument,
    ProposalDocumentBinding,
)
from content.services.proposal_approval_service import load_proposal, source_hash
from content.services.proposal_shared_documents import reconfirm
from content.tests.views.test_proposal_approval import (
    _private_blob_names,
    approval_client,
    confirm,
    payload,
    pdf,
    reviewed_proposal,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def confirmed_proposal(reviewed_proposal, approval_client, admin_user):
    confirm(reviewed_proposal, approval_client, admin_user)
    return load_proposal(reviewed_proposal.pk)


def revision_payload(proposal, **changes):
    values = {
        'request_id': 'second-confirmation',
        'source_hash': source_hash(load_proposal(proposal.pk)),
        'use_proposal_contracts': False,
    }
    values.update(changes)
    return values


def test_approval_files_share_project_document_identity(
    reviewed_proposal, approval_client, admin_user,
):
    """Falla si el cierre crea copias editables sin vínculo a su archivo aprobado."""
    result = confirm(reviewed_proposal, approval_client, admin_user)

    project = Project.objects.get(pk=result['linked_project']['id'])
    root = DocumentFolder.objects.get(managed_project=project)
    assert list(root.children.filter(system_key__startswith='approval:project:').order_by('name').values_list('name', 'project_id', 'client_user_id')) == [
        ('Anexos', project.pk, approval_client.user_id),
        ('Contratos', project.pk, approval_client.user_id),
    ]
    assert list(ProposalDocumentBinding.objects.filter(proposal=reviewed_proposal).order_by('source_key').values_list('source_key', 'document__folder__name')) == [
        ('commercial', 'Anexos'),
        ('custom-contract', 'Contratos'),
        ('technical', 'Anexos'),
    ]
    assert ProposalApprovalPackage.objects.filter(proposal=reviewed_proposal).count() == 1
    assert ProposalDocumentBinding.objects.filter(proposal=reviewed_proposal, current_file__binding_id=None).count() == 0
    assert list(Document.objects.filter(proposal_binding__proposal=reviewed_proposal).order_by('pk').values_list('generated_file', flat=True)) == ['', '', '']


def test_approval_preview_never_provisions_documents(admin_client, reviewed_proposal):
    """Falla si consultar la revisión crea proyecto, carpetas o archivos legales."""
    response = admin_client.get(reverse('proposal-approval', args=[reviewed_proposal.pk]))

    assert response.status_code == 200
    assert response.json()['confirmed'] is False
    assert response.json()['shared_documents'] == []
    assert Project.objects.count() == 0
    assert DocumentFolder.objects.filter(system_key__startswith='approval:project:').count() == 0
    assert (ProposalApprovalFile.objects.count(), ProposalApprovalPackage.objects.count(), ProposalDocumentBinding.objects.count()) == (0, 0, 0)


def test_document_download_serves_the_approved_contract_bytes(admin_client, confirmed_proposal):
    """Falla si el gestor regenera o copia un contrato distinto del confirmado."""
    binding = confirmed_proposal.document_bindings.get(current_file__document_type='contract')

    response = admin_client.get(reverse('download-document-pdf', args=[binding.document_id]))

    assert response.status_code == 200
    assert b''.join(response.streaming_content) == b'%PDF-1.4 contract'
    assert response['Cache-Control'] == 'private, no-store'
    assert response['X-Content-Type-Options'] == 'nosniff'


def test_reconfirmation_preserves_the_document_identity(admin_user, confirmed_proposal):
    """Falla si sustituir el contrato crea otro documento o sobrescribe el aprobado."""
    binding = confirmed_proposal.document_bindings.get(current_file__document_type='contract')
    original = binding.current_file
    payload = revision_payload(confirmed_proposal, custom_documents=[{'title': 'Signed replacement', 'document_type': 'contract'}])

    package = reconfirm(confirmed_proposal.pk, payload, actor=admin_user, files=[pdf(content=b'%PDF-1.4 replacement')])

    binding.refresh_from_db()
    assert binding.current_file.package_id == package.pk
    assert binding.current_file.file.read() == b'%PDF-1.4 replacement'
    assert binding.document_id == original.binding.document_id
    assert original.file.read() == b'%PDF-1.4 contract'
    assert confirmed_proposal.document_bindings.count() == 3
    assert confirmed_proposal.approval_packages.count() == 2


@pytest.mark.parametrize('version', [None, 'outdated-version'])
def test_source_write_rejects_an_unmatched_version(admin_client, confirmed_proposal, version):
    """Falla si una edición sin versión vigente sobrescribe cambios compartidos."""
    original_title = confirmed_proposal.title

    response = admin_client.patch(
        reverse('update-proposal', args=[confirmed_proposal.pk]),
        {'title': 'Overwritten title'}, format='json',
        HTTP_X_PROPOSAL_VERSION=version or '',
    )

    confirmed_proposal.refresh_from_db()
    assert response.status_code == 409
    assert response.json()['code'] == 'stale_source'
    assert confirmed_proposal.title == original_title
    assert confirmed_proposal.approval_packages.count() == 1


def test_valid_source_write_marks_the_shared_document_pending(admin_client, confirmed_proposal):
    """Falla si editar la propuesta cambia el archivo vigente o no marca su borrador."""
    binding = confirmed_proposal.document_bindings.get(source_key='commercial')
    original_file_id = binding.current_file_id
    update = admin_client.patch(
        reverse('update-proposal', args=[confirmed_proposal.pk]),
        {'title': 'Revised shared title'}, format='json',
        HTTP_X_PROPOSAL_VERSION=source_hash(confirmed_proposal),
    )

    response = admin_client.get(reverse('document-proposal-source', args=[binding.document_id]))

    assert update.status_code == 200
    assert response.status_code == 200
    assert response.json()['document']['has_pending_changes'] is True
    assert response.json()['document']['current_file_id'] == original_file_id
    assert response.json()['document']['document_id'] == binding.document_id
    confirmed_proposal.refresh_from_db()
    assert confirmed_proposal.title == 'Revised shared title'
    assert confirmed_proposal.approval_packages.count() == 1


def test_service_approval_write_preserves_the_confirmed_package(admin_client, confirmed_proposal):
    """Fails if saving the service switch changes files from an already confirmed package."""
    confirmed_proposal.contract_modality = 'split'
    confirmed_proposal.save(update_fields=['contract_modality'])
    package = confirmed_proposal.approval_packages.get()
    original_file_ids = list(package.files.order_by('pk').values_list('pk', flat=True))

    response = admin_client.patch(
        reverse('update-proposal', args=[confirmed_proposal.pk]),
        {'service_contract_approved': True}, format='json',
        HTTP_X_PROPOSAL_VERSION=source_hash(confirmed_proposal),
    )

    confirmed_proposal.refresh_from_db()
    assert response.status_code == 200
    assert response.json()['service_contract_approved'] is True
    assert confirmed_proposal.service_contract_approved is True
    assert list(package.files.order_by('pk').values_list('pk', flat=True)) == original_file_ids


def test_reconciliation_restores_a_missing_annex_identity(admin_client, reviewed_proposal, approval_client, admin_user):
    """Fails if reconciling an annex regenerates its approved file or creates another package."""
    annex = ProposalDocument.objects.create(
        proposal=reviewed_proposal, document_type='legal_annex', title='Signed annex',
    )
    annex.file.save('annex.pdf', ContentFile(b'%PDF-1.4 annex'))
    confirm(reviewed_proposal, approval_client, admin_user)
    proposal = load_proposal(reviewed_proposal.pk)
    binding = proposal.document_bindings.get(source_key=f'original-{annex.pk}')
    contract_document_id = proposal.document_bindings.get(source_key='custom-contract').document_id
    approved = binding.current_file
    approved_id, approved_hash, approved_bytes = approved.pk, approved.sha256, approved.file.read()
    document = binding.document
    ProposalApprovalFile.objects.filter(pk=approved.pk).update(binding=None)
    binding.delete()
    document.delete()

    preview = admin_client.get(reverse('proposal-document-reconciliation', args=[proposal.pk]))
    response = admin_client.post(
        reverse('proposal-document-reconciliation', args=[proposal.pk]),
        {'expected_hash': preview.json()['expected_hash']}, format='json',
    )

    restored = proposal.document_bindings.get(source_key=f'original-{annex.pk}')
    assert preview.status_code == 200
    assert preview.json()['missing_documents'] == [{
        'source_key': f'original-{annex.pk}', 'title': 'Signed annex',
        'file_id': approved_id, 'folder': 'Anexos',
    }]
    assert response.status_code == 200
    assert (restored.current_file_id, restored.current_file.sha256, restored.current_file.file.read()) == (
        approved_id, approved_hash, approved_bytes,
    )
    assert restored.document.folder.name == 'Anexos'
    assert proposal.document_bindings.get(source_key='custom-contract').document_id == contract_document_id
    assert proposal.approval_packages.count() == 1


def test_reconciliation_rejects_a_malformed_expected_hash(admin_client, confirmed_proposal):
    """Fails if a malformed reconciliation version can alter approved document identities."""
    counts = (
        ProposalApprovalFile.objects.count(), Document.objects.count(),
        confirmed_proposal.document_bindings.count(),
    )

    response = admin_client.post(
        reverse('proposal-document-reconciliation', args=[confirmed_proposal.pk]),
        {'expected_hash': 'a' * 63}, format='json',
    )

    assert response.status_code == 400
    assert 'expected_hash' in response.json()
    assert (
        ProposalApprovalFile.objects.count(), Document.objects.count(),
        confirmed_proposal.document_bindings.count(),
    ) == counts


def test_reconciliation_rejects_a_stale_expected_hash(admin_client, confirmed_proposal):
    """Fails if a stale reconciliation preview can write a new document identity."""
    counts = (
        ProposalApprovalFile.objects.count(), Document.objects.count(),
        confirmed_proposal.document_bindings.count(),
    )

    response = admin_client.post(
        reverse('proposal-document-reconciliation', args=[confirmed_proposal.pk]),
        {'expected_hash': 'b' * 64}, format='json',
    )

    assert response.status_code == 409
    assert response.json()['code'] == 'stale_source'
    assert (
        ProposalApprovalFile.objects.count(), Document.objects.count(),
        confirmed_proposal.document_bindings.count(),
    ) == counts


def test_reconciliation_blocks_an_ambiguous_historical_document(admin_client, confirmed_proposal):
    """Fails if reconciliation duplicates a missing approved identity beside an unbound historical document."""
    binding = confirmed_proposal.document_bindings.get(source_key='custom-contract')
    approved = binding.current_file
    document = binding.document
    ProposalApprovalFile.objects.filter(pk=approved.pk).update(binding=None)
    binding.delete()
    document.delete()
    from content.models import DocumentType
    kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Documento'})
    Document.objects.create(
        document_type=kind, title='Old contract', project=confirmed_proposal.deliverable.project,
        client_user_id=confirmed_proposal.client.user_id, deliverable=confirmed_proposal.deliverable,
        created_by=confirmed_proposal.client.user, updated_by=confirmed_proposal.client.user,
        source_proposal=confirmed_proposal,
    )
    counts = (ProposalApprovalFile.objects.count(), Document.objects.count())

    response = admin_client.get(reverse('proposal-document-reconciliation', args=[confirmed_proposal.pk]))

    assert response.status_code == 200
    assert response.json()['can_reconcile'] is False
    assert 'documentos anteriores sin vínculo' in ' '.join(response.json()['blockers'])
    assert (ProposalApprovalFile.objects.count(), Document.objects.count()) == counts


def test_reconciliation_reports_a_corrupted_approved_file(admin_client, confirmed_proposal):
    """Fails if reconciliation treats altered approved bytes as safe to restore."""
    row = confirmed_proposal.approval_files.get(source_key='custom-contract')
    with row.file.storage.open(row.file.name, 'wb') as stream:
        stream.write(b'%PDF-1.4 altered')
    counts = (ProposalApprovalFile.objects.count(), Document.objects.count())

    preview = admin_client.get(reverse('proposal-document-reconciliation', args=[confirmed_proposal.pk]))
    response = admin_client.post(
        reverse('proposal-document-reconciliation', args=[confirmed_proposal.pk]),
        {'expected_hash': preview.json()['expected_hash']}, format='json',
    )

    assert preview.status_code == 200
    assert preview.json()['can_reconcile'] is False
    assert 'no está disponible o no coincide' in ' '.join(preview.json()['blockers'])
    assert response.status_code == 400
    assert (ProposalApprovalFile.objects.count(), Document.objects.count()) == counts


def test_reconciliation_rejects_a_non_administrator(api_client, approval_client, confirmed_proposal):
    """Fails if a client can inspect a proposal document-repair plan."""
    api_client.force_authenticate(user=approval_client.user)

    response = api_client.post(
        reverse('proposal-document-reconciliation', args=[confirmed_proposal.pk]),
        {'expected_hash': 'a' * 64}, format='json',
    )

    assert response.status_code == 403


def test_reconciliation_blocks_a_cross_project_document_identity(admin_client, confirmed_proposal):
    """Fails if reconciliation accepts a binding whose document belongs to another project."""
    other_project = Project.objects.create(client=confirmed_proposal.client.user, name='Other project')
    binding = confirmed_proposal.document_bindings.get(source_key='custom-contract')
    binding.document.project = other_project
    binding.document.save(update_fields=['project'])
    counts = (ProposalApprovalFile.objects.count(), Document.objects.count())

    preview = admin_client.get(reverse('proposal-document-reconciliation', args=[confirmed_proposal.pk]))
    response = admin_client.post(
        reverse('proposal-document-reconciliation', args=[confirmed_proposal.pk]),
        {'expected_hash': preview.json()['expected_hash']}, format='json',
    )

    assert preview.status_code == 200
    assert preview.json()['can_reconcile'] is False
    assert 'Revisa el vínculo existente' in ' '.join(preview.json()['blockers'])
    assert response.status_code == 400
    assert (ProposalApprovalFile.objects.count(), Document.objects.count()) == counts


def test_reconfirmation_retry_reuses_the_same_package(admin_user, confirmed_proposal):
    """Falla si repetir una confirmación vuelve a crear documentos o versiones."""
    payload = revision_payload(confirmed_proposal)
    first = reconfirm(confirmed_proposal.pk, payload, actor=admin_user)

    second = reconfirm(confirmed_proposal.pk, payload, actor=admin_user)

    assert second.pk == first.pk
    assert confirmed_proposal.approval_packages.count() == 2
    assert confirmed_proposal.document_bindings.count() == 3
    assert ProposalApprovalFile.objects.filter(proposal=confirmed_proposal).count() == 6
    assert Project.objects.count() == 1


@pytest.mark.parametrize('condition', ['', '   ', 'Solo si agregan soporte ilimitado'])
def test_public_acceptance_has_no_side_effects(api_client, viewed_proposal, condition):
    """Falla si aceptar públicamente evita la revisión obligatoria del cierre."""
    previous_log_count = ProposalChangeLog.objects.filter(proposal=viewed_proposal).count()
    previous_email_count = len(mail.outbox)
    response = api_client.post(
        reverse('respond-to-proposal', args=[viewed_proposal.uuid]),
        {'action': 'accepted', 'condition': condition}, format='json',
    )

    viewed_proposal.refresh_from_db()
    assert response.status_code == 400
    assert response.json()['code'] == 'invalid_action'
    assert viewed_proposal.status == 'viewed'
    assert viewed_proposal.responded_at is None
    assert ProposalChangeLog.objects.filter(proposal=viewed_proposal).count() == previous_log_count
    assert len(mail.outbox) == previous_email_count
    assert Project.objects.count() == 0


def test_historical_inventory_never_creates_documents(accepted_proposal):
    """Falla si inventariar una aprobación histórica fabrica un cierre no revisado."""
    output = StringIO()

    call_command('reconcile_proposal_documents', proposal=accepted_proposal.pk, stdout=output)

    result = json.loads(output.getvalue())
    assert result['inventory'][0]['proposal_id'] == accepted_proposal.pk
    assert result['inventory'][0]['confirmed'] is False
    assert result['inventory'][0]['incorporated'] is False
    assert result['inventory'][0]['files'] == []
    assert ProposalApprovalPackage.objects.count() == 0
    assert ProposalDocumentBinding.objects.count() == 0
    assert Project.objects.count() == 0


def test_archived_annex_is_excluded_from_the_confirmed_package(reviewed_proposal, approval_client, admin_user):
    """Falla si un anexo retirado reaparece como parte del cierre vigente."""
    annex = ProposalDocument.objects.create(proposal=reviewed_proposal, document_type='legal_annex', title='Withdrawn annex', is_archived=True)
    annex.file.save('withdrawn.pdf', ContentFile(b'%PDF-1.4 withdrawn'))

    result = confirm(reviewed_proposal, approval_client, admin_user)

    assert [row['document_type'] for row in result['confirmed_files']] == ['contract', 'commercial', 'technical']
    assert reviewed_proposal.document_bindings.filter(source_document=annex).count() == 0


@pytest.mark.parametrize('credential', ['anonymous', 'client'])
def test_source_preview_requires_an_administrator(api_client, approval_client, credential, confirmed_proposal):
    """Falla si un visitante o cliente puede consultar la fuente contractual privada."""
    binding = confirmed_proposal.document_bindings.get(source_key='commercial')
    user = {'anonymous': None, 'client': approval_client.user}[credential]
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse('document-proposal-source', args=[binding.document_id]))

    assert response.status_code == 403


def test_reconfirmation_rejects_a_stale_source(admin_user, confirmed_proposal):
    """Falla si confirmar una revisión vieja altera el paquete vigente."""
    payload = revision_payload(confirmed_proposal)
    confirmed_proposal.title = 'Concurrent change'
    confirmed_proposal.save(update_fields=['title'])

    with pytest.raises(ValidationError) as caught:
        reconfirm(confirmed_proposal.pk, payload, actor=admin_user)

    assert caught.value.status_code == 409
    assert str(caught.value.detail['code']) == 'stale_source'
    assert confirmed_proposal.approval_packages.count() == 1
    assert ProposalApprovalFile.objects.filter(proposal=confirmed_proposal).count() == 3


def test_binary_source_replacement_preserves_the_approved_revision(admin_client, confirmed_proposal):
    """Falla si subir un borrador desde el gestor reemplaza silenciosamente lo aprobado."""
    binding = confirmed_proposal.document_bindings.get(current_file__document_type='contract')
    original_file_id = binding.current_file_id

    response = admin_client.post(
        reverse('document-proposal-source', args=[binding.document_id]),
        {'source_hash': source_hash(confirmed_proposal), 'file': pdf(content=b'%PDF-1.4 draft replacement')},
        format='multipart',
    )

    binding.refresh_from_db()
    assert response.status_code == 200
    assert response.json()['document']['has_pending_changes'] is True
    assert binding.current_file_id == original_file_id
    assert binding.current_file.file.read() == b'%PDF-1.4 contract'
    assert binding.draft_file.read() == b'%PDF-1.4 draft replacement'
    assert confirmed_proposal.approval_packages.count() == 1


def test_binary_draft_confirmation_promotes_the_same_document(admin_client, admin_user, confirmed_proposal):
    """Falla si confirmar el borrador binario pierde su identidad o altera la versión anterior."""
    binding = confirmed_proposal.document_bindings.get(current_file__document_type='contract')
    original = binding.current_file
    replacement = admin_client.post(
        reverse('document-proposal-source', args=[binding.document_id]),
        {'source_hash': source_hash(confirmed_proposal), 'file': pdf(content=b'%PDF-1.4 draft replacement')},
        format='multipart',
    )
    assert replacement.status_code == 200

    package = reconfirm(confirmed_proposal.pk, revision_payload(confirmed_proposal), actor=admin_user)

    binding.refresh_from_db()
    assert binding.current_file.package_id == package.pk
    assert binding.current_file.file.read() == b'%PDF-1.4 draft replacement'
    assert original.file.read() == b'%PDF-1.4 contract'
    assert binding.document_id == original.binding.document_id
    assert confirmed_proposal.document_bindings.count() == 3


def test_missing_project_folder_rolls_back_the_approval(admin_client, reviewed_proposal, approval_client):
    """Falla si un proyecto histórico sin carpeta deja el cierre o sus archivos a medias."""
    historical = Project(client=approval_client.user, name='Historical project')
    Project.objects.bulk_create([historical])
    values = payload(reviewed_proposal, approval_client)
    values.pop('new_project')
    values['project_id'] = historical.pk
    previous_files = _private_blob_names()

    response = admin_client.post(
        reverse('proposal-approval', args=[reviewed_proposal.pk]),
        {'payload': json.dumps(values), 'custom_files[]': pdf()}, format='multipart',
    )

    reviewed_proposal.refresh_from_db()
    assert response.status_code == 400
    assert 'PA-108' in response.json()['project_id']
    assert (reviewed_proposal.status, reviewed_proposal.deliverable_id, reviewed_proposal.platform_approval_manifest) == ('negotiating', None, {})
    assert (ProposalApprovalPackage.objects.count(), ProposalApprovalFile.objects.count(), ProposalDocumentBinding.objects.count()) == (0, 0, 0)
    assert _private_blob_names() == previous_files


def test_a_legal_annex_cannot_replace_the_contract(admin_client, reviewed_proposal, approval_client):
    """Falla si un anexo legal por sí solo satisface la confirmación del contrato vigente."""
    values = payload(reviewed_proposal, approval_client)
    values['custom_documents'] = [{'title': 'Legal annex only', 'document_type': 'legal_annex'}]

    response = admin_client.post(
        reverse('proposal-approval', args=[reviewed_proposal.pk]),
        {'payload': json.dumps(values), 'custom_files[]': pdf()}, format='multipart',
    )

    reviewed_proposal.refresh_from_db()
    assert response.status_code == 400
    assert response.json()['custom_documents'] == 'Identifica el contrato vigente: uno combinado o producto y servicio separados.'
    assert reviewed_proposal.status == 'negotiating'
    assert Project.objects.count() == 0
    assert ProposalApprovalFile.objects.count() == 0
