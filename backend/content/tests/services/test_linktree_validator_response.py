"""Forged worker replies never make a Linktree candidate valid."""
import base64
import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from content.models import Linktree, LinktreeTemplate, LinktreeTemplateVersion
from content.services.linktree_templates.contract import KNOWN_CODES
from content.services.linktree_templates.render import snapshot_document
from content.services.linktree_templates.service import run_validation
from content.storage import get_private_storage
from linktree_sandbox import worker

ISSUE = {'severity': 'error', 'code': 'touch_target', 'message': 'El área tocable debe medir al menos 44 × 44 px.',
         'file': 'template.html', 'line': 1, 'node': '3', 'width': 320}


def png(width, height):
    """A blank PNG of the given size, base64-encoded as the worker sends it."""
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), 'white').save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def pending_version():
    """Create a pending candidate exactly as an upload leaves it."""
    tree = Linktree.objects.create(handle='validator-reply', name='Validator reply')
    template = LinktreeTemplate.objects.create(
        owner=tree, name='Editorial', manifest={'editable_assets': [], 'fonts': [], 'motion': False},
        html='<main>{{name}}</main>', assets={},
    )
    return LinktreeTemplateVersion.objects.create(
        linktree=tree, template=template, profile={}, profile_digest='0' * 64,
    )


def reply(version, **changes):
    """A well-formed worker reply for ``version`` with ``changes`` applied."""
    body = {'v': 1, 'issues': [], 'page_bytes': len(snapshot_document(version).encode()),
            'fonts_requested': [], 'screenshots': {'320': png(320, 40)}}
    body.update(changes)
    return json.dumps(body).encode()


FORGED = {
    'unknown_key': (lambda version: reply(version, extra=True), worker.MAX_RESPONSE_BYTES),
    'unknown_code': (lambda version: reply(version, issues=[{**ISSUE, 'code': 'made_up'}]), worker.MAX_RESPONSE_BYTES),
    'too_many_issues': (lambda version: reply(version, issues=[{**ISSUE, 'line': n + 1} for n in range(151)]),
                        worker.MAX_RESPONSE_BYTES),
    'not_png': (lambda version: reply(version, screenshots={'320': base64.b64encode(b'GIF89a' + bytes(32)).decode()}),
                worker.MAX_RESPONSE_BYTES),
    'wrong_width': (lambda version: reply(version, screenshots={'320': png(321, 40)}), worker.MAX_RESPONSE_BYTES),
    'too_tall': (lambda version: reply(version, screenshots={'320': png(320, 12001)}), worker.MAX_RESPONSE_BYTES),
    'over_limit': (lambda version: reply(version), 64),
    'truncated_json': (lambda version: reply(version)[:-7], worker.MAX_RESPONSE_BYTES),
}


@pytest.mark.django_db
@pytest.mark.parametrize('case', sorted(FORGED))
def test_forged_reply_leaves_candidate_invalid(monkeypatch, case):
    """Fails if a compromised worker can mark a candidate valid or slip in an arbitrary image."""
    version = pending_version()
    forge, limit = FORGED[case]
    monkeypatch.setattr(worker, 'MAX_RESPONSE_BYTES', limit)
    monkeypatch.setattr(worker, 'serve', lambda payload, executable_path=None: forge(version))

    run_validation(version.pk)

    version.refresh_from_db()
    assert version.status == 'invalid'
    assert [issue['code'] for issue in version.report['issues']] == ['validator_unavailable']
    assert version.screenshots == {}


@pytest.mark.django_db
def test_well_formed_reply_is_accepted_and_its_capture_stored(monkeypatch):
    """Fails if the contract check rejects a genuine reply, which would block every publication."""
    version = pending_version()
    monkeypatch.setattr(worker, 'serve', lambda payload, executable_path=None: reply(version))

    run_validation(version.pk)

    version.refresh_from_db()
    assert version.status == 'valid'
    assert set(version.screenshots) == {'320'}
    with get_private_storage().open(version.screenshots['320'], 'rb') as stored:
        assert stored.read(8) == b'\x89PNG\r\n\x1a\n'


def test_known_codes_match_what_the_browser_step_emits():
    """Fails if a browser check emits a code the contract rejects, which would make every validation unavailable."""
    folder = Path(worker.__file__).parent
    sources = (folder / 'audit.js').read_text() + (folder / 'worker.py').read_text()

    emitted = set(re.findall(r"add\('([a-z_]+)'", sources)) | set(re.findall(r"'code': '([a-z_]+)'", sources))

    assert emitted == KNOWN_CODES
