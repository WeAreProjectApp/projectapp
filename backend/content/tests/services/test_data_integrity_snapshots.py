"""Undo records guards only for rows with changed business fields."""
import pytest

from content.services.data_integrity.snapshots import diff_items


@pytest.mark.parametrize(('guard', 'value'), [('updated_at', '2026-10-09T10:00:00+00:00'),
                                        ('retention_context_id', None)])
def test_changed_row_records_its_unchanged_guard(guard, value):
    key = ('content.document', 1)
    before = {key: {'title': 'Antes', guard: value}}
    after = {key: {'title': 'Después', guard: value}}

    items = diff_items(before, after)

    assert {'model': key[0], 'pk': 1, 'field': guard, 'before': value, 'after': value, 'guard': True} in items


def test_unchanged_row_has_no_items():
    key = ('content.document', 1)
    snapshot = {key: {'title': 'Documento', 'updated_at': '2026-10-09T10:00:00+00:00'}}

    assert diff_items(snapshot, snapshot) == []


def test_guard_only_change_has_no_items():
    key = ('content.document', 1)
    before = {key: {'title': 'Documento', 'updated_at': '2026-10-09T10:00:00+00:00'}}
    after = {key: {'title': 'Documento', 'updated_at': '2026-10-09T10:01:00+00:00'}}

    assert diff_items(before, after) == []
