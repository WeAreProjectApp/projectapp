"""Build metadata: freeze backend identity at startup, observe frontend on disk.

The manifest travels in the existing transactional artifact roots. Neither
startup nor HTTP requests consult Git or trust a runtime environment SHA.
"""

import json
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

_COMMIT_RE = re.compile(r'[0-9a-f]{40}')
_MAX_MANIFEST_BYTES = 4096
_captured = False
_backend_commit = None


def read_build_commit(manifest_path):
    """Return only a validated identity; malformed artifacts remain unknown."""
    try:
        with Path(manifest_path).open('rb') as manifest_file:
            raw = manifest_file.read(_MAX_MANIFEST_BYTES + 1)
        if len(raw) > _MAX_MANIFEST_BYTES:
            return None
        document = json.loads(raw)
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(document, dict):
        return None
    commit = document.get('commit')
    if (
        type(document.get('schema_version')) is not int
        or document['schema_version'] != 1
        or document.get('project') != 'projectapp'
        or not isinstance(commit, str)
        or _COMMIT_RE.fullmatch(commit) is None
    ):
        return None
    return commit


def capture_backend_version():
    """Called by AppConfig.ready, before lazy URL imports or any requests."""
    global _captured, _backend_commit
    if not _captured:
        _backend_commit = read_build_commit(
            Path(settings.STATIC_ROOT) / 'frontend' / 'version.json',
        )
        # Unknown identity is frozen too: a later artifact swap cannot relabel
        # an existing process whose original build metadata was absent.
        _captured = True


def _version_response(commit):
    return JsonResponse(
        {'schema_version': 1, 'project': 'projectapp', 'commit': commit},
        status=200 if commit is not None else 503,
    )


@never_cache
@transaction.non_atomic_requests
@require_safe
def backend_version(request):
    return _version_response(_backend_commit)


@never_cache
@require_safe
def frontend_version(request):
    return _version_response(read_build_commit(
        Path(settings.BASE_DIR) / 'static' / 'frontend' / 'version.json',
    ))
