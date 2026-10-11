"""Periodic cell contract repair converges through real transactional service writes."""
import logging
from unittest.mock import patch

import pytest

from content.models import BuildingOnDemandContractMirror, BuildingOnDemandContractRevision, Document, DocumentNote, EntityRevision
from content.services import building_on_demand_contract_service as service
from content.tasks import reconcile_building_on_demand_contract_mirror

pytestmark = pytest.mark.django_db
TASK_SOURCE = 'task:building-on-demand-contract-mirror'
SERVICE_LOGGER = 'content.services.building_on_demand_contract_service'


def test_contract_task_creates_the_pinned_mirror(building_on_demand_contract, pinned_contracts_folder, superuser):
    """Fails if the periodic wrapper does not create a synchronized private contract document."""
    reconcile_building_on_demand_contract_mirror.call_local()
    mirror = BuildingOnDemandContractMirror.objects.select_related('document').get(contract=building_on_demand_contract)

    assert service.mirror_status()['status'] == 'synchronized'
    assert mirror.document.folder_id == pinned_contracts_folder.pk
    assert mirror.document.created_by_id == superuser.pk
    assert mirror.document.is_client_visible is False
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert mirror.document.document_notes.count() == 2
    assert mirror.document.document_notes.get(title='Inventario de decisiones pendientes (v1)').content == service.PENDING_DECISIONS_V1


def test_contract_task_preserves_a_synchronized_artifact(building_on_demand_contract, pinned_contracts_folder, superuser):
    """Fails if a healthy periodic run renders another PDF or creates redundant notes or history."""
    reconcile_building_on_demand_contract_mirror.call_local()
    mirror = BuildingOnDemandContractMirror.objects.get(contract=building_on_demand_contract)
    before = service.mirror_status()
    before_pdf = bytes(mirror.pdf_content)
    before_notes = mirror.document.document_notes.count()
    before_history = EntityRevision.objects.filter(source=TASK_SOURCE).count()

    with patch('content.services.document_pdf_service.DocumentPdfService.generate_from_markdown',
               side_effect=AssertionError('An already synchronized task must not render again.')):
        reconcile_building_on_demand_contract_mirror.call_local()
    mirror.refresh_from_db()

    assert service.mirror_status() == before
    assert bytes(mirror.pdf_content) == before_pdf
    assert mirror.document.document_notes.count() == before_notes
    assert EntityRevision.objects.filter(source=TASK_SOURCE).count() == before_history


def test_contract_task_resynchronizes_an_outdated_revision(building_on_demand_contract, pinned_contracts_folder, superuser):
    """Fails if the periodic wrapper leaves a prior revision in the existing Gestor document."""
    service.sync_mirror(actor=superuser)
    mirror = BuildingOnDemandContractMirror.objects.get(contract=building_on_demand_contract)
    document_id = mirror.document_id
    revision = BuildingOnDemandContractRevision.objects.create(
        version=2, markdown='# CONTRATO ACTUALIZADO\n\nTexto vigente para la célula.', change_note='Cambio externo de prueba.',
    )
    building_on_demand_contract.current_revision = revision
    building_on_demand_contract.save(update_fields=['current_revision', 'updated_at'])

    reconcile_building_on_demand_contract_mirror.call_local()
    mirror.refresh_from_db()

    assert mirror.revision_id == revision.pk
    assert mirror.document_id == document_id
    assert service.mirror_status()['status'] == 'synchronized'
    assert service.mirror_status()['version'] == 2
    assert mirror.document.document_notes.count() == 3


def test_contract_task_records_attributed_document_history(building_on_demand_contract, pinned_contracts_folder, superuser):
    """Fails if task-created documents lose their audit source or active administrator author."""
    reconcile_building_on_demand_contract_mirror.call_local()
    mirror = BuildingOnDemandContractMirror.objects.get(contract=building_on_demand_contract)
    entry = EntityRevision.objects.get(
        history__entity_type='document', history__object_id=mirror.document_id, source=TASK_SOURCE,
    )

    assert entry.action == 'created'
    assert entry.actor_id_snapshot == superuser.pk
    assert entry.actor_label == superuser.username
    assert entry.snapshot['title'] == service.CONTRACT_TITLE


def test_contract_task_rolls_back_initial_render_failure(
    building_on_demand_contract, pinned_contracts_folder, superuser, caplog,
):
    """Fails if a failing task leaves an incomplete mirror or repeated failure logs."""
    before_documents = Document.objects.count()
    before_notes = DocumentNote.objects.count()
    before_history = EntityRevision.objects.count()

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        with patch('content.services.document_pdf_service.DocumentPdfService.generate_from_markdown',
                   side_effect=RuntimeError('PDF renderer unavailable.')):
            reconcile_building_on_demand_contract_mirror.call_local()

    assert not BuildingOnDemandContractMirror.objects.exists()
    assert Document.objects.count() == before_documents
    assert DocumentNote.objects.count() == before_notes
    assert EntityRevision.objects.count() == before_history
    assert len(caplog.records) == 1


def test_contract_task_keeps_the_existing_artifact_after_failure(
    building_on_demand_contract, pinned_contracts_folder, superuser, caplog,
):
    """Fails if a failed periodic resync destroys the earlier PDF or appends private notes."""
    service.sync_mirror(actor=superuser)
    mirror = BuildingOnDemandContractMirror.objects.get(contract=building_on_demand_contract)
    before_pdf = bytes(mirror.pdf_content)
    before_revision = mirror.revision_id
    before_synced_at = mirror.synced_at
    revision = BuildingOnDemandContractRevision.objects.create(
        version=2, markdown='# CONTRATO NUEVO\n\nCambios pendientes de sincronizar.', change_note='Cambio externo de prueba.',
    )
    building_on_demand_contract.current_revision = revision
    building_on_demand_contract.save(update_fields=['current_revision', 'updated_at'])

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        with patch('content.services.document_pdf_service.DocumentPdfService.generate_from_markdown',
                   side_effect=RuntimeError('PDF renderer unavailable.')):
            reconcile_building_on_demand_contract_mirror.call_local()
    mirror.refresh_from_db()

    assert service.mirror_status()['status'] == 'out_of_sync'
    assert mirror.revision_id == before_revision
    assert mirror.synced_at == before_synced_at
    assert bytes(mirror.pdf_content) == before_pdf
    assert mirror.document.document_notes.count() == 2
    assert not EntityRevision.objects.filter(source=TASK_SOURCE).exists()
    assert len(caplog.records) == 1


def test_contract_task_skips_without_a_folder_pin(
    building_on_demand_contract, unpinned_contracts_folder, superuser, caplog,
):
    """Fails if periodic reconciliation guesses an unpinned folder or writes a warning note."""
    before_notes = DocumentNote.objects.count()

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        reconcile_building_on_demand_contract_mirror.call_local()

    assert not BuildingOnDemandContractMirror.objects.exists()
    assert not Document.objects.filter(title=service.CONTRACT_TITLE).exists()
    assert DocumentNote.objects.count() == before_notes
    assert len(caplog.records) == 1


def test_contract_task_skips_without_an_active_superuser(
    building_on_demand_contract, pinned_contracts_folder, django_user_model, caplog,
):
    """Fails if periodic reconciliation creates an unattributed document without an active author."""
    django_user_model.objects.filter(is_superuser=True).update(is_active=False)
    before_notes = DocumentNote.objects.count()

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        reconcile_building_on_demand_contract_mirror.call_local()

    assert not BuildingOnDemandContractMirror.objects.exists()
    assert not Document.objects.filter(title=service.CONTRACT_TITLE).exists()
    assert DocumentNote.objects.count() == before_notes
    assert len(caplog.records) == 1


def test_contract_task_selects_the_first_active_superuser(
    building_on_demand_contract, pinned_contracts_folder, django_user_model,
):
    """Fails if periodic attribution selects an inactive or later administrator."""
    django_user_model.objects.filter(is_superuser=True).update(is_active=False)
    django_user_model.objects.create_superuser(username='inactive-task-author', is_active=False)
    first_active = django_user_model.objects.create_superuser(username='first-task-author')
    django_user_model.objects.create_superuser(username='later-task-author')

    reconcile_building_on_demand_contract_mirror.call_local()
    mirror = BuildingOnDemandContractMirror.objects.select_related('document').get(contract=building_on_demand_contract)

    assert mirror.document.created_by_id == first_active.pk
    assert set(mirror.document.document_notes.values_list('created_by_id', flat=True)) == {first_active.pk}
