"""How the Django side reaches the Linktree browser worker.

``inprocess`` (the default) calls the worker inside this process. ``unix-socket``
talks to the systemd socket unit that runs it as another user without network.
Every failure raises ValidatorError, which run_validation reports as
validator_unavailable.
"""
import socket
import time

from django.conf import settings

from linktree_sandbox import worker
from .contract import ValidatorError

CHUNK_BYTES = 1024 * 1024


def exchange(payload):
    """Send one encoded request to the configured worker and return its raw reply."""
    transport = settings.LINKTREE_VALIDATOR_TRANSPORT
    if transport == 'inprocess':
        return worker.serve(payload, executable_path=settings.LINKTREE_CHROMIUM_EXECUTABLE or None)
    if transport == 'unix-socket':
        return unix_socket_exchange(settings.LINKTREE_VALIDATOR_SOCKET, payload, settings.LINKTREE_VALIDATOR_TIMEOUT)
    raise ValidatorError('unknown_transport')


def unix_socket_exchange(path, payload, timeout, limit=None):
    """Send the request, half-close and read the reply within one total deadline and a size cap."""
    limit = worker.MAX_RESPONSE_BYTES if limit is None else limit
    deadline = time.monotonic() + timeout

    def remaining():
        left = deadline - time.monotonic()
        if left <= 0:
            raise ValidatorError('timeout')
        return left

    reply = bytearray()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(remaining())
            client.connect(path)
            client.settimeout(remaining())
            client.sendall(payload)
            client.shutdown(socket.SHUT_WR)
            while True:
                client.settimeout(remaining())
                chunk = client.recv(CHUNK_BYTES)
                if not chunk:
                    return bytes(reply)
                reply.extend(chunk)
                if len(reply) > limit:
                    raise ValidatorError('response_too_large')
    except OSError as error:
        raise ValidatorError(f'transport_{type(error).__name__}') from error
