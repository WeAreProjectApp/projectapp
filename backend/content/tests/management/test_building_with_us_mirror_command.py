"""Explicit initialization and protected-mirror cleanup in isolated test settings."""
import json
from io import StringIO

import pytest
from django.core.management import call_command

from content.models import BuildingWithUsContractMirror, BuildingWithUsContractRevision, Document
from content.services.building_with_us_contract_service import read_contract

pytestmark = pytest.mark.django_db


def test_command_initialization_is_idempotent(building_with_us_contract_folder, superuser):
    """Fails if dry-run writes or two applies create duplicate documents or notes."""
    dry, first, repeated = StringIO(), StringIO(), StringIO()

    call_command('initialize_building_with_us_contract_mirror', stdout=dry)
    assert json.loads(dry.getvalue())['status'] == 'not_initialized'
    assert BuildingWithUsContractMirror.objects.count() == 0
    call_command('initialize_building_with_us_contract_mirror', '--apply', '--folder-id', str(building_with_us_contract_folder.pk), stdout=first)
    call_command('initialize_building_with_us_contract_mirror', '--apply', '--folder-id', str(building_with_us_contract_folder.pk), stdout=repeated)
    created, noop = json.loads(first.getvalue()), json.loads(repeated.getvalue())

    assert created['outcome'] == 'create'
    assert noop['outcome'] == 'noop'
    assert created['mirror'] == noop['mirror']
    assert Document.objects.get(pk=created['mirror']['document_id']).document_notes.count() == 2


def test_fake_reset_preserves_contract_history(initialized_building_with_us_mirror):
    """Fails if a protected mirror blocks demo cleanup or the catalog is destroyed."""
    document_id = initialized_building_with_us_mirror.document_id
    before = read_contract()

    call_command('delete_fake_data', '--confirm', stdout=StringIO(), verbosity=0)

    assert not BuildingWithUsContractMirror.objects.exists()
    assert not Document.objects.filter(pk=document_id).exists()
    assert read_contract()['version_id'] == before['version_id']
    assert BuildingWithUsContractRevision.objects.count() == 1
