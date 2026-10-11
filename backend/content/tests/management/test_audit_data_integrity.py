"""audit_data_integrity: the operator's read-only scan prints counts and record ids, never client data."""
import io
import json
import os
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

pytestmark = pytest.mark.django_db

SYNTHETIC_COMPANY = 'Zafiro Sintético SAS'
SYNTHETIC_EMAIL = 'zafiro.sintetico@example.com'


def _run(*args):
    out = io.StringIO()
    call_command('audit_data_integrity', *args, stdout=out, stderr=io.StringIO())
    return out.getvalue()


@pytest.fixture
def orphan(make_client_profile):
    """A client with nothing linked: one CL4 finding whose label would carry client data."""
    return make_client_profile(company=SYNTHETIC_COMPANY, email=SYNTHETIC_EMAIL, username=SYNTHETIC_EMAIL)


def test_text_output_lists_counts_and_record_ids_without_client_data(orphan):
    """Fails if the scan misses the finding or prints a client's name or email instead of only ids."""
    output = _run('--rule', 'CL4')

    assert f'accounts.userprofile:{orphan.pk}' in output
    assert 'CL4' in output
    assert SYNTHETIC_COMPANY not in output
    assert SYNTHETIC_EMAIL not in output


def test_json_report_lands_in_a_new_private_file(orphan, tmp_path):
    """Fails if the report file is readable by others, carries labels, or silently overwrites a file."""
    target = tmp_path / 'scan.json'

    _run('--rule', 'CL4', '--format', 'json', '--output', str(target))

    report = json.loads(target.read_text(encoding='utf-8'))
    assert os.stat(target).st_mode & 0o777 == 0o600
    assert report['rules'] == [{'rule_id': 'CL4', 'domain': 'clients', 'severity': 'low', 'count': 1,
                                'records': [f'accounts.userprofile:{orphan.pk}']}]
    with pytest.raises(CommandError, match='already exists'):
        _run('--rule', 'CL4', '--output', str(target))


@pytest.mark.parametrize('root', ['BASE_DIR', 'STATIC_ROOT', 'MEDIA_ROOT', 'PRIVATE_MEDIA_ROOT'])
def test_output_inside_the_repository_or_media_is_refused(root):
    """Fails if a report could be written where the site serves files or where git would commit it."""
    target = Path(getattr(settings, root)) / 'scan.json'

    with pytest.raises(CommandError, match='must live outside'):
        _run('--output', str(target))

    assert not target.exists()


def test_output_in_a_missing_folder_fails_cleanly(tmp_path):
    """Fails if a bad --output path ends in a raw traceback instead of a clear command error."""
    target = tmp_path / 'missing' / 'scan.json'

    with pytest.raises(CommandError, match='Cannot create'):
        _run('--output', str(target))

    assert not target.exists()


def test_the_scan_writes_nothing(orphan):
    """Fails if the read-only scan ever inserts, updates or deletes a row."""
    with CaptureQueriesContext(connection) as queries:
        _run('--coverage')

    writes = [query['sql'] for query in queries.captured_queries
              if query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
    assert writes == []
