"""The unix-socket transport to the Linktree browser worker, without systemd."""
import json
import socket
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest

from content.models import Linktree, LinktreeTemplate, LinktreeTemplateVersion
from content.services.linktree_templates import transport
from content.services.linktree_templates.contract import ValidatorError
from content.services.linktree_templates.service import run_validation
from content.services.linktree_templates.validation import validate_in_browser


class FakeWorker:
    """A one-connection Unix server that reads the request to EOF, then answers or stalls."""

    def __init__(self, path, reply=None):
        self.reply, self.received, self.release = reply, [], threading.Event()
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(path))
        self.listener.listen(1)
        self.listener.settimeout(10)
        self.thread = threading.Thread(target=self.answer, daemon=True)
        self.thread.start()

    def answer(self):
        connection, _ = self.listener.accept()
        with connection:
            chunks = []
            while chunk := connection.recv(65536):
                chunks.append(chunk)
            self.received.append(b''.join(chunks))
            if self.reply is None:
                self.release.wait(10)
            else:
                connection.sendall(self.reply)

    def close(self):
        """Release a stalled answer and report whether the server thread finished."""
        self.release.set()
        self.thread.join(10)
        self.listener.close()
        return not self.thread.is_alive()


@pytest.fixture
def socket_path(tmp_path_factory):
    """A short path: AF_UNIX addresses are limited to 107 bytes."""
    return tmp_path_factory.mktemp('s') / 'v.sock'


def test_socket_round_trip_delivers_the_request_and_a_checked_reply(socket_path, settings):
    """Fails if the socket client truncates the request or the reply, or skips the contract check."""
    settings.LINKTREE_VALIDATOR_TRANSPORT = 'unix-socket'
    settings.LINKTREE_VALIDATOR_SOCKET = str(socket_path)
    document = '<main>Hola</main>'
    fake = FakeWorker(socket_path, reply=json.dumps({
        'v': 1, 'issues': [], 'page_bytes': len(document.encode()), 'fonts_requested': [], 'screenshots': {},
    }).encode())
    template = SimpleNamespace(warnings=[], manifest={'fonts': [], 'motion': False})
    candidate = SimpleNamespace(id=uuid4(), template=template, profile={}, assets={}, document=document)

    report, screenshots = validate_in_browser(candidate)

    assert fake.close()
    assert json.loads(fake.received[0])['document'] == document
    assert report == {'issues': [], 'page_bytes': len(document.encode()), 'widths': [320, 375, 430]}
    assert screenshots == {}


@pytest.mark.django_db
def test_worker_slower_than_the_timeout_leaves_the_version_invalid(socket_path, settings):
    """Fails if a hung validator leaves the version pending and blocks every later upload."""
    settings.LINKTREE_VALIDATOR_TRANSPORT = 'unix-socket'
    settings.LINKTREE_VALIDATOR_SOCKET = str(socket_path)
    settings.LINKTREE_VALIDATOR_TIMEOUT = 0.3
    fake = FakeWorker(socket_path)
    tree = Linktree.objects.create(handle='validator-socket', name='Validator socket')
    template = LinktreeTemplate.objects.create(
        owner=tree, name='Editorial', manifest={'editable_assets': [], 'fonts': [], 'motion': False},
        html='<main>{{name}}</main>', assets={},
    )
    version = LinktreeTemplateVersion.objects.create(linktree=tree, template=template, profile={},
                                                     profile_digest='0' * 64)

    run_validation(version.pk)

    version.refresh_from_db()
    assert fake.close()
    assert version.status == 'invalid'
    assert [issue['code'] for issue in version.report['issues']] == ['validator_unavailable']


def test_reply_over_the_size_cap_is_refused(socket_path):
    """Fails if an oversized reply is buffered instead of being cut off at the cap."""
    fake = FakeWorker(socket_path, reply=b'x' * 64)

    with pytest.raises(ValidatorError, match='response_too_large'):
        transport.unix_socket_exchange(str(socket_path), b'{}', timeout=5, limit=16)

    assert fake.close()


def test_absent_validator_socket_is_an_error_not_a_reply(tmp_path):
    """Fails if a validator that is not running is mistaken for an empty reply."""
    with pytest.raises(ValidatorError, match='transport_'):
        transport.unix_socket_exchange(str(tmp_path / 'absent.sock'), b'{}', timeout=1)


def test_unknown_transport_fails_closed(settings):
    """Fails if a mistyped transport silently falls back instead of keeping candidates invalid."""
    settings.LINKTREE_VALIDATOR_TRANSPORT = 'carrier-pigeon'

    with pytest.raises(ValidatorError, match='unknown_transport'):
        transport.exchange(b'{}')
