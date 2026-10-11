"""How the Django side reaches the Linktree browser worker."""
from django.conf import settings

from linktree_sandbox import worker


def exchange(payload):
    """Send one encoded request to the worker and return its raw reply."""
    return worker.serve(payload, executable_path=settings.LINKTREE_CHROMIUM_EXECUTABLE or None)
