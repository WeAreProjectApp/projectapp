"""Undo refuses original communication contexts that no longer exist."""
import pytest

from content.models import CommunicationFolder, CommunicationThread
from content.services.data_integrity import engine
from content.services.project_deletion_service import delete_empty_project
from content.tests.data_integrity_helpers import (
    apply,
    make_project,
    only,
    scan,
    selection,
)

pytestmark = pytest.mark.django_db


def test_removed_original_project_blocks_thread_relink_undo(make_client_profile, superuser):
    """Fails if a relink undo is offered after its original project disappears."""
    client = make_client_profile()
    own = make_project(client)
    original = make_project(make_client_profile(), 'Anterior')
    CommunicationThread.objects.create(client=client, project=original, title='Consulta')
    [finding] = only(scan('client', client.pk, rule_ids=['CM1']), 'CM1')
    _, result = apply(superuser, [selection(finding, project=own.pk)])
    delete_empty_project(original.pk, actor=superuser)

    impact = engine.preview_undo(result['operation_id'])

    assert [entry['code'] for entry in impact['blockers']] == ['guard_changed']


def test_removed_original_folder_blocks_thread_relink_undo(make_client_profile, superuser):
    """Fails if a relink undo is offered after its dropped folder disappears."""
    client = make_client_profile()
    own = make_project(client)
    original = make_project(make_client_profile(), 'Anterior')
    folder = CommunicationFolder.objects.create(client=client, project=original, name='Archivo')
    CommunicationThread.objects.create(client=client, project=original, folder=folder, title='Consulta')
    [finding] = only(scan('client', client.pk, rule_ids=['CM1']), 'CM1')
    _, result = apply(superuser, [selection(finding, project=own.pk)])
    folder.delete()

    impact = engine.preview_undo(result['operation_id'])

    assert [entry['code'] for entry in impact['blockers']] == ['guard_changed']


def test_removed_original_folder_blocks_move_to_root_undo(make_client_profile, superuser):
    """Fails if undo is offered when the conversation's previous folder no longer exists."""
    client = make_client_profile()
    original = CommunicationFolder.objects.create(client=make_client_profile(), name='Archivo')
    CommunicationThread.objects.create(client=client, folder=original, title='Consulta')
    [finding] = only(scan(rule_ids=['CM2']), 'CM2')
    _, result = apply(superuser, [selection(finding)])
    original.delete()

    impact = engine.preview_undo(result['operation_id'])

    assert [entry['code'] for entry in impact['blockers']] == ['guard_changed']
