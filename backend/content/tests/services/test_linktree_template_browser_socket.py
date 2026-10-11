"""The worker as its own process behind the unix socket; these tests run real headless Chromium."""
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from content.services.linktree_templates.render import render_document
from content.services.linktree_templates.validation import validate_in_browser
from linktree_sandbox import worker

WORKER = Path(worker.__file__)
HTML = '<main><h1>{{name}}</h1>{{#links}}<a data-link href="{{url}}">{{label}}</a>{{/links}}</main>'


class SocketActivation:
    """Emulate systemd Accept=yes: the accepted connection becomes a fresh worker's stdin and stdout."""

    def __init__(self, path):
        self.returncodes = []
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(path))
        self.listener.listen(1)
        self.listener.settimeout(60)
        self.thread = threading.Thread(target=self.serve_one, daemon=True)
        self.thread.start()

    def serve_one(self):
        connection, _ = self.listener.accept()
        environment = {key: value for key, value in os.environ.items() if not key.startswith('DJANGO')}
        with connection:
            # The parent's copy closes here, so the client sees EOF only when the worker exits.
            child = subprocess.Popen([sys.executable, '-E', '-s', str(WORKER)], stdin=connection.fileno(),
                                     stdout=connection.fileno(), stderr=subprocess.DEVNULL, env=environment)
        self.returncodes.append(child.wait(timeout=240))

    def close(self):
        """Wait for the worker process and report whether the server thread finished."""
        self.thread.join(240)
        self.listener.close()
        return not self.thread.is_alive()


def version(css):
    """Build a rendered candidate for real-browser validation."""
    template = SimpleNamespace(html=HTML, css=css, warnings=[], manifest={'fonts': [], 'motion': False, 'max_width': 480})
    profile = {'name': 'Socket test', 'contact': {'email': '', 'tel': ''}, 'buttons': [{
        'label': 'Visit site', 'url': 'https://example.com', 'key': '1', 'tier': 'primary', 'icon': 'globe',
        'kind': 'web',
    }]}
    row = SimpleNamespace(id=uuid4(), template=template, profile=profile, assets={})
    row.document = render_document(row)
    return row


def through_socket(settings, path, row):
    """Validate ``row`` with the worker running as its own process behind ``path``."""
    settings.LINKTREE_VALIDATOR_TRANSPORT = 'unix-socket'
    settings.LINKTREE_VALIDATOR_SOCKET = str(path)
    activation = SocketActivation(path)
    result = validate_in_browser(row)
    assert activation.close() and activation.returncodes == [0]
    return result


def test_worker_process_behind_the_socket_returns_three_captures(tmp_path_factory, settings):
    """Fails if the socket path loses captures or checks that the in-process path keeps."""
    row = version('body{background:#fff;color:#111;font-family:sans-serif}main{padding:20px}'
                  'a{display:flex;align-items:center;min-height:48px;color:#111;background:#fff}')

    report, screenshots = through_socket(settings, tmp_path_factory.mktemp('s') / 'v.sock', row)

    assert report['issues'] == []
    assert set(screenshots) == {'320', '375', '430'}


def test_socket_and_inprocess_tell_authors_the_same(tmp_path_factory, settings):
    """Fails if moving the worker behind the socket changes the issues authors are shown."""
    css = 'body{background:#fff;color:#aaa}main{width:350px}a{color:#aaa;font-size:10px}'
    in_process, _ = validate_in_browser(version(css))

    over_socket, _ = through_socket(settings, tmp_path_factory.mktemp('s') / 'v.sock', version(css))

    assert {'contrast', 'touch_target', 'overflow'} <= {issue['code'] for issue in over_socket['issues']}
    assert over_socket == in_process
