"""Folder corrections preserve ownership and undo only their recorded change."""
import pytest

from content.services.data_integrity import engine
from content.services.data_integrity.types import IntegrityConflict
from content.services.data_integrity.scope import resolve_scope
from content.tests.data_integrity_documents_factories import make_document, make_folder
from content.tests.data_integrity_helpers import apply, scan, selection, undo

pytestmark = pytest.mark.django_db


def test_unfiled_document_moves_to_selected_folder(superuser):
    document = make_document('Acta')
    folder = make_folder('Destino')
    [finding] = scan(rule_ids=['DC11'])

    apply(superuser, [selection(finding, 'relink', folder_id=folder.pk)])

    document.refresh_from_db()
    assert document.folder_id == folder.pk
    assert document.client_user_id is None


def test_move_preserves_an_unowned_document(make_client_profile, superuser):
    owner = make_client_profile()
    folder = make_folder('Cliente', client_user=owner.user)
    document = make_document('Acta')
    [finding] = scan(rule_ids=['DC11'])

    apply(superuser, [selection(finding, 'relink', folder_id=folder.pk)])

    document.refresh_from_db()
    assert document.client_user_id is None


def test_undo_restores_unfiled_location(superuser):
    document = make_document('Acta')
    folder = make_folder('Destino')
    [finding] = scan(rule_ids=['DC11'])
    _, result = apply(superuser, [selection(finding, 'relink', folder_id=folder.pk)])

    undo(superuser, result['operation_id'])

    document.refresh_from_db()
    assert document.folder_id is None


def test_archived_destination_blocks_preview(superuser):
    make_document('Acta')
    folder = make_folder('Archivada', is_archived=True)
    [finding] = scan(rule_ids=['DC11'])

    preview = engine.preview_fixes(resolve_scope('all'), [selection(finding, 'relink', folder_id=folder.pk)], actor=superuser)

    assert preview['blocked'] is True


def test_two_documents_can_share_a_destination(superuser):
    first, second = make_document('Uno'), make_document('Dos')
    folder = make_folder('Destino')
    findings = scan(rule_ids=['DC11'])
    selections = [selection(row, 'relink', folder_id=folder.pk) for row in findings]

    apply(superuser, selections)

    assert list(type(first).objects.filter(pk__in=[first.pk, second.pk]).values_list('folder_id', flat=True)) == [folder.pk, folder.pk]


def test_destination_change_invalidates_preview(superuser):
    document = make_document('Acta')
    folder = make_folder('Destino')
    [finding] = scan(rule_ids=['DC11'])
    batch = [selection(finding, 'relink', folder_id=folder.pk)]
    preview = engine.preview_fixes(resolve_scope('all'), batch, actor=superuser)
    type(folder).objects.filter(pk=folder.pk).update(name='Renombrada')

    with pytest.raises(IntegrityConflict, match='stale_impact'):
        engine.apply_fixes(resolve_scope('all'), batch, actor=superuser, reason='Prueba',
            request_id='changed-folder', expected_impact_hash=preview['impact_hash'])

    document.refresh_from_db()
    assert document.folder_id is None


def test_destination_change_blocks_undo(superuser):
    make_document('Acta')
    folder = make_folder('Destino')
    [finding] = scan(rule_ids=['DC11'])
    _, result = apply(superuser, [selection(finding, 'relink', folder_id=folder.pk)])
    type(folder).objects.filter(pk=folder.pk).update(is_archived=True)

    preview = engine.preview_undo(result['operation_id'])

    assert preview['blocked'] is True
    assert preview['blockers'][0]['code'] == 'guard_changed'
