"""Approved document identities survive purges and dissolve only in fake resets."""
import hashlib
from io import StringIO
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import override_settings

from accounts.management.commands._seed_helpers import clear_fake_delivery
from accounts.models import Deliverable, Project, ProjectContract, UserProfile
from content.models import (
    BusinessProposal, Document, DocumentType, ProposalApprovalFile,
    ProposalApprovalPackage, ProposalDocumentBinding,
)
from content.services.project_force_deletion import (
    ProjectForceDeleteError, force_delete_project, forced_deletion_preview,
)

pytestmark = pytest.mark.django_db
APPROVED_BYTES = b'%PDF-1.4 approved fixture contract'
DRAFT_BYTES = b'%PDF-1.4 pending fixture contract'


@pytest.fixture
def packet_factory(admin_user):
    def create(prefix, *, shared_file_name=None):
        user = get_user_model().objects.create_user(username=f'{prefix}-client')
        profile = UserProfile.objects.create(user=user, role='client')
        project = Project.objects.create(name=f'{prefix} project', client=user)
        deliverable = Deliverable.objects.create(
            project=project, category='documents', title=f'{prefix} deliverable', uploaded_by=admin_user,
        )
        proposal = BusinessProposal.objects.create(
            title=f'{prefix} proposal', status='accepted', client=profile, deliverable=deliverable,
        )
        kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})
        document = Document.objects.create(
            document_type=kind, project=project, client_user=user,
            folder=project.document_root_folder, title=f'{prefix} shared contract', created_by=admin_user,
        )
        binding = ProposalDocumentBinding.objects.create(
            proposal=proposal, document=document, source_key='custom-contract',
        )
        first = ProposalApprovalPackage.objects.create(
            proposal=proposal, number=1, request_id=f'{prefix}-first', payload_hash='a' * 64,
            source_hash='b' * 64, created_by=admin_user,
        )
        original = ProposalApprovalFile(
            proposal=proposal, project=project, deliverable=deliverable, package=first, binding=binding,
            source_key='custom-contract', title='Approved contract', document_type='contract',
            filename='approved.pdf', sha256=hashlib.sha256(APPROVED_BYTES).hexdigest(),
            size=len(APPROVED_BYTES), created_by=admin_user,
        )
        if shared_file_name:
            original.file.name = shared_file_name
        else:
            original.file.save(f'{prefix}-approved.pdf', ContentFile(APPROVED_BYTES), save=False)
        original.save()
        second = ProposalApprovalPackage.objects.create(
            proposal=proposal, number=2, request_id=f'{prefix}-second', payload_hash='c' * 64,
            source_hash='d' * 64, created_by=admin_user,
        )
        current = ProposalApprovalFile.objects.create(
            proposal=proposal, project=project, deliverable=deliverable, package=second, binding=binding,
            source_key='custom-contract', title='Approved contract', document_type='contract',
            filename='approved.pdf', file=original.file.name,
            sha256=original.sha256, size=original.size, created_by=admin_user,
        )
        binding.current_file = current
        binding.draft_file.save(f'{prefix}-draft.pdf', ContentFile(DRAFT_BYTES), save=False)
        binding.draft_filename = 'draft.pdf'
        binding.draft_sha256 = hashlib.sha256(DRAFT_BYTES).hexdigest()
        binding.save()
        contract = ProjectContract.objects.create(
            project=project, key=f'{prefix}-contract', title='Approved delivery source', approval_file=current,
        )
        return SimpleNamespace(
            project=project, proposal=proposal, document=document, binding=binding,
            original=original, current=current, contract=contract, actor=admin_user,
        )
    return create


@pytest.fixture
def packet(packet_factory):
    return packet_factory('owned')


@pytest.fixture
def unassigned_packet(admin_user):
    proposal = BusinessProposal.objects.create(title='Historical proposal without project', status='accepted')
    document = Document.objects.create(title='Historical shared document')
    package = ProposalApprovalPackage.objects.create(
        proposal=proposal, number=1, request_id='unassigned-package', payload_hash='a' * 64,
        source_hash='b' * 64, created_by=admin_user,
    )
    binding = ProposalDocumentBinding.objects.create(
        proposal=proposal, document=document, source_key='commercial',
    )
    binding.draft_file.save('unassigned-draft.pdf', ContentFile(DRAFT_BYTES))
    return SimpleNamespace(package=package, binding=binding)


def _packet_counts(packet):
    return (
        ProposalApprovalFile.objects.filter(proposal=packet.proposal).count(),
        ProposalDocumentBinding.objects.filter(proposal=packet.proposal).count(),
        ProposalApprovalPackage.objects.filter(proposal=packet.proposal).count(),
    )


def _packet_files_exist(packet):
    return (
        packet.current.file.storage.exists(packet.current.file.name),
        packet.binding.draft_file.storage.exists(packet.binding.draft_file.name),
    )


def _full_force_preview(project, actor):
    initial = forced_deletion_preview(project, actor=actor)
    keys = [item['key'] for item in initial['dependencies']]
    return forced_deletion_preview(project, actor=actor, delete_keys=keys)


def test_confirmed_fake_reset_removes_the_protected_packet_graph(packet, unassigned_packet, django_capture_on_commit_callbacks):
    """Falla si el reinicio confirmado deja identidades protegidas o borra archivos antes del commit."""
    with django_capture_on_commit_callbacks(execute=True):
        call_command('delete_fake_data', '--confirm', stdout=StringIO())
        assert _packet_files_exist(packet) == (True, True)

    assert _packet_counts(packet) == (0, 0, 0)
    assert (Document.objects.count(), BusinessProposal.objects.count(), Project.objects.count()) == (0, 0, 0)
    assert _packet_files_exist(packet) == (False, False)
    assert unassigned_packet.binding.draft_file.storage.exists(unassigned_packet.binding.draft_file.name) is False
    assert get_user_model().objects.filter(pk=packet.actor.pk, is_staff=True).exists() is True


def test_scoped_fake_reset_preserves_another_projects_packet(packet, packet_factory, django_capture_on_commit_callbacks):
    """Falla si limpiar entregas de un proyecto elimina la evidencia contractual de otro."""
    other = packet_factory('other')

    with django_capture_on_commit_callbacks(execute=True):
        clear_fake_delivery(Project.objects.filter(pk=packet.project.pk))

    assert _packet_counts(packet) == (0, 0, 0)
    assert _packet_counts(other) == (2, 1, 2)
    assert _packet_files_exist(packet) == (False, False)
    assert _packet_files_exist(other) == (True, True)
    assert ProjectContract.objects.filter(pk=other.contract.pk).exists() is True


def test_fake_reset_rollback_preserves_private_packet_files(packet, django_capture_on_commit_callbacks):
    """Falla si revertir el reinicio deja filas restauradas con archivos privados eliminados."""
    with pytest.raises(RuntimeError, match='cancel fixture reset'):
        with django_capture_on_commit_callbacks(execute=True):
            with transaction.atomic():
                clear_fake_delivery(Project.objects.filter(pk=packet.project.pk))
                raise RuntimeError('cancel fixture reset')

    packet.binding.refresh_from_db()
    assert _packet_counts(packet) == (2, 1, 2)
    assert packet.binding.current_file_id == packet.current.pk
    assert _packet_files_exist(packet) == (True, True)
    assert ProjectContract.objects.filter(pk=packet.contract.pk).exists() is True


@override_settings(FAKE_DATA_ALLOWED=False)
def test_disabled_fake_reset_preserves_the_packet(packet):
    """Falla si se puede retirar una aprobación sin habilitar explícitamente fake data."""
    with pytest.raises(CommandError, match='disabled'):
        clear_fake_delivery(Project.objects.filter(pk=packet.project.pk))

    assert _packet_counts(packet) == (2, 1, 2)
    assert _packet_files_exist(packet) == (True, True)


def test_shared_private_file_survives_a_scoped_fake_reset(packet, packet_factory, django_capture_on_commit_callbacks):
    """Falla si limpiar un paquete borra un archivo todavía referenciado por otro cierre."""
    other = packet_factory('shared-file', shared_file_name=packet.current.file.name)

    with django_capture_on_commit_callbacks(execute=True):
        clear_fake_delivery(Project.objects.filter(pk=packet.project.pk))

    assert _packet_counts(packet) == (0, 0, 0)
    assert _packet_counts(other) == (2, 1, 2)
    assert _packet_files_exist(packet) == (True, False)
    assert other.current.file.read() == APPROVED_BYTES


def test_external_current_file_blocks_a_scoped_fake_reset(packet, packet_factory):
    """Falla si retirar archivos compartidos desengancha la revisión vigente de otra propuesta."""
    other = packet_factory('external-reference')
    other.binding.current_file = packet.current
    other.binding.save(update_fields=['current_file'])

    with pytest.raises(CommandError, match='No se borraron datos ni archivos'):
        clear_fake_delivery(Project.objects.filter(pk=packet.project.pk))

    packet.binding.refresh_from_db()
    other.binding.refresh_from_db()
    assert _packet_counts(packet) == (2, 1, 2)
    assert packet.binding.current_file_id == packet.current.pk
    assert other.binding.current_file_id == packet.current.pk
    assert _packet_files_exist(packet) == (True, True)
    assert ProjectContract.objects.filter(pk=packet.contract.pk).exists() is True


def test_foreign_document_blocks_a_scoped_fake_reset(packet, packet_factory):
    """Falla si una identidad fuera del proyecto se disuelve al limpiar sólo sus entregas."""
    other = packet_factory('foreign-owner')
    foreign = Document.objects.create(title='Foreign shared window', project=other.project)
    packet.binding.document = foreign
    packet.binding.save(update_fields=['document'])

    with pytest.raises(CommandError, match='fuera del reinicio autorizado'):
        clear_fake_delivery(Project.objects.filter(pk=packet.project.pk))

    assert _packet_counts(packet) == (2, 1, 2)
    assert _packet_files_exist(packet) == (True, True)
    assert ProjectContract.objects.filter(pk=packet.contract.pk).exists() is True
    assert Document.objects.filter(pk=foreign.pk, project=other.project).exists() is True


@pytest.mark.parametrize('current', [True, False], ids=['current', 'historical'])
def test_force_delete_preserves_the_shared_document_identity(packet, superuser, current):
    """Falla si forzar el borrado trata el vínculo compartido como un dato descartable sin clasificar."""
    packet.binding.is_current = current
    packet.binding.save(update_fields=['is_current'])
    preview = _full_force_preview(packet.project, superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(
            packet.project.pk, actor=superuser, confirmation='DELETE',
            impact_token=preview['impact_token'], delete_keys=preview['delete_keys'],
        )

    assert error.value.code == 'project_force_delete_blocked'
    assert 'Este documento comparte el contrato o los anexos de una propuesta y debe conservarse con sus versiones aprobadas.' in [item['message'] for item in preview['blockers']]
    assert 'content.proposaldocumentbinding' not in [item['key'] for item in preview['blockers']]
    assert Document.objects.filter(pk=packet.document.pk).exists() is True
    assert _packet_counts(packet) == (2, 1, 2)
    assert _packet_files_exist(packet) == (True, True)
