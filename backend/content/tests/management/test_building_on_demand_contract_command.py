"""Explicit cell contract synchronization remains inspectable and author-attributed."""
import json
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from content.models import BuildingOnDemandContract, BuildingOnDemandContractMirror, Document, DocumentFolder, DocumentNote
from content.services import building_on_demand_contract_service as service

pytestmark = pytest.mark.django_db
COMMAND = 'sync_building_on_demand_contract_mirror'


def test_sync_command_inspects_without_applying(building_on_demand_contract):
    """Fails if the default command requires an author or writes the missing mirror."""
    output = StringIO()
    before_documents = Document.objects.count()
    before_notes = DocumentNote.objects.count()

    call_command(COMMAND, stdout=output)

    assert json.loads(output.getvalue()) == service.mirror_status()
    assert json.loads(output.getvalue())['status'] == 'not_initialized'
    assert not BuildingOnDemandContractMirror.objects.exists()
    assert Document.objects.count() == before_documents
    assert DocumentNote.objects.count() == before_notes


def test_sync_command_uses_the_pinned_folder(building_on_demand_contract, pinned_contracts_folder, superuser):
    """Fails if an apply cannot initialize the pinned folder without an explicit folder id."""
    output = StringIO()

    call_command(COMMAND, '--apply', stdout=output)
    result = json.loads(output.getvalue())
    mirror = BuildingOnDemandContractMirror.objects.select_related('document').get(contract=building_on_demand_contract)

    assert result['outcome'] == 'create'
    assert result['mirror']['status'] == 'synchronized'
    assert mirror.document.folder_id == pinned_contracts_folder.pk
    assert mirror.document.created_by_id == superuser.pk
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert mirror.document.document_notes.get(title='Inventario de decisiones pendientes (v1)').content == service.PENDING_DECISIONS_V1


def test_sync_command_accepts_an_explicit_staff_author(
    building_on_demand_contract, unpinned_contracts_folder, admin_user,
):
    """Fails if the command requires superuser privileges for an explicit active staff author."""
    output = StringIO()

    call_command(COMMAND, '--apply', '--folder-id', str(unpinned_contracts_folder.pk),
                 '--actor-id', str(admin_user.pk), stdout=output)
    result = json.loads(output.getvalue())
    mirror = BuildingOnDemandContractMirror.objects.select_related('document').get(contract=building_on_demand_contract)

    assert result['outcome'] == 'create'
    assert result['mirror']['folder_id'] == unpinned_contracts_folder.pk
    assert mirror.document.created_by_id == admin_user.pk
    assert set(mirror.document.document_notes.values_list('created_by_id', flat=True)) == {admin_user.pk}


def test_sync_command_skips_a_synchronized_mirror(building_on_demand_contract, pinned_contracts_folder, superuser):
    """Fails if repeating an explicit apply renders again or appends synchronization notes."""
    initial = service.sync_mirror(actor=superuser)
    mirror = BuildingOnDemandContractMirror.objects.get(contract=building_on_demand_contract)
    before_notes = mirror.document.document_notes.count()
    output = StringIO()

    with patch('content.services.document_pdf_service.DocumentPdfService.generate_from_markdown',
               side_effect=AssertionError('A synchronized command apply must not render again.')):
        call_command(COMMAND, '--apply', stdout=output)

    assert json.loads(output.getvalue()) == {'outcome': 'noop', 'mirror': initial['mirror']}
    assert BuildingOnDemandContractMirror.objects.count() == 1
    assert mirror.document.document_notes.count() == before_notes


def test_sync_command_repairs_the_existing_document(building_on_demand_contract, pinned_contracts_folder, superuser):
    """Fails if a resync leaves an archived contract document or replaces its stable identity."""
    service.sync_mirror(actor=superuser)
    mirror = BuildingOnDemandContractMirror.objects.get(contract=building_on_demand_contract)
    document_id = mirror.document_id
    Document.objects.filter(pk=document_id).update(is_archived=True, title='Título alterado')
    output = StringIO()

    call_command(COMMAND, '--apply', stdout=output)
    mirror.refresh_from_db()
    mirror.document.refresh_from_db()

    assert json.loads(output.getvalue())['outcome'] == 'resync'
    assert json.loads(output.getvalue())['mirror']['status'] == 'synchronized'
    assert mirror.document_id == document_id
    assert mirror.document.title == service.CONTRACT_TITLE
    assert mirror.document.is_archived is False
    assert mirror.document.document_notes.count() == 3


@pytest.mark.parametrize(('is_active', 'is_staff'), [(True, False), (False, True)])
def test_sync_command_rejects_an_ineligible_author(
    building_on_demand_contract, pinned_contracts_folder, django_user_model, is_active, is_staff,
):
    """Fails if an inactive or non-staff author can create a contractual mirror."""
    actor = django_user_model.objects.create_user(username='ineligible-author', is_active=is_active, is_staff=is_staff)

    with pytest.raises(CommandError, match='administrador activo'):
        call_command(COMMAND, '--apply', '--actor-id', str(actor.pk), stdout=StringIO())

    assert not BuildingOnDemandContractMirror.objects.exists()


@pytest.mark.parametrize('actor_id', [0, -1, 999999])
def test_sync_command_rejects_a_missing_explicit_author(
    building_on_demand_contract, pinned_contracts_folder, superuser, actor_id,
):
    """Fails if a missing explicit author silently falls back to an unrelated superuser."""
    with pytest.raises(CommandError, match='administrador activo'):
        call_command(COMMAND, '--apply', '--actor-id', str(actor_id), stdout=StringIO())

    assert not BuildingOnDemandContractMirror.objects.exists()


def test_sync_command_requires_a_default_active_author(
    building_on_demand_contract, pinned_contracts_folder, django_user_model,
):
    """Fails if applying without an active superuser creates an unattributed contract document."""
    django_user_model.objects.filter(is_superuser=True).update(is_active=False)

    with pytest.raises(CommandError, match='administrador activo'):
        call_command(COMMAND, '--apply', stdout=StringIO())

    assert not BuildingOnDemandContractMirror.objects.exists()


def test_sync_command_selects_the_first_active_superuser(
    building_on_demand_contract, pinned_contracts_folder, django_user_model,
):
    """Fails if default attribution selects an inactive or later superuser."""
    django_user_model.objects.filter(is_superuser=True).update(is_active=False)
    django_user_model.objects.create_superuser(username='inactive-cell-author', is_active=False)
    first_active = django_user_model.objects.create_superuser(username='first-cell-author')
    django_user_model.objects.create_superuser(username='later-cell-author')

    call_command(COMMAND, '--apply', stdout=StringIO())
    mirror = BuildingOnDemandContractMirror.objects.select_related('document').get(contract=building_on_demand_contract)

    assert mirror.document.created_by_id == first_active.pk
    assert set(mirror.document.document_notes.values_list('created_by_id', flat=True)) == {first_active.pk}


def test_sync_command_rejects_a_foreign_folder(
    building_on_demand_contract, pinned_contracts_folder, superuser,
):
    """Fails if an explicit folder id can move the mirror outside the configured contract pin."""
    other_root = DocumentFolder.objects.create(name='Otra raíz')
    foreign_folder = DocumentFolder.objects.create(name='Contratos', parent=other_root)

    with pytest.raises(CommandError):
        call_command(COMMAND, '--apply', '--folder-id', str(foreign_folder.pk), stdout=StringIO())

    assert not BuildingOnDemandContractMirror.objects.exists()
    assert not Document.objects.filter(title=service.CONTRACT_TITLE).exists()


def test_sync_command_refuses_an_unpinned_implicit_folder(
    building_on_demand_contract, unpinned_contracts_folder, superuser,
):
    """Fails if an implicit unpinned apply guesses a folder instead of requiring an explicit choice."""
    with pytest.raises(CommandError):
        call_command(COMMAND, '--apply', stdout=StringIO())

    assert not BuildingOnDemandContractMirror.objects.exists()
    assert not Document.objects.filter(title=service.CONTRACT_TITLE).exists()


def test_sync_command_reports_a_missing_contract(building_on_demand_contract):
    """Fails if a missing singleton produces uncaught service errors during status inspection."""
    BuildingOnDemandContract.objects.filter(pk=building_on_demand_contract.pk).delete()

    with pytest.raises(CommandError, match='El contrato no está configurado'):
        call_command(COMMAND, stdout=StringIO())

    assert not BuildingOnDemandContractMirror.objects.exists()


def test_sync_command_rolls_back_a_failed_render(building_on_demand_contract, pinned_contracts_folder, superuser):
    """Fails if PDF rendering failure leaves an incomplete document, mirror, or private note."""
    before_documents = Document.objects.count()
    before_notes = DocumentNote.objects.count()

    with patch('content.services.document_pdf_service.DocumentPdfService.generate_from_markdown',
               side_effect=RuntimeError('PDF renderer unavailable.')):
        with pytest.raises(CommandError):
            call_command(COMMAND, '--apply', stdout=StringIO())

    assert not BuildingOnDemandContractMirror.objects.exists()
    assert Document.objects.count() == before_documents
    assert DocumentNote.objects.count() == before_notes
