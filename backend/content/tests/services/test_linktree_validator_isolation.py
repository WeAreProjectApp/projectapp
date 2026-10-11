"""The Linktree browser worker runs on its own, without Django or the project."""
import json
import os
import subprocess
import sys
from pathlib import Path

from linktree_sandbox import worker

WORKER = Path(worker.__file__)


def test_worker_answers_by_path_without_django_or_project_imports(tmp_path):
    """Fails if a new import drags Django or project code into the isolated worker."""
    environment = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(tmp_path), 'LANG': 'C.UTF-8'}

    completed = subprocess.run(
        [sys.executable, '-E', '-s', '-X', 'importtime', str(WORKER)],
        input=b'{}', capture_output=True, env=environment, timeout=120, check=False,
    )

    imported = {line.rsplit('|', 1)[-1].strip() for line in completed.stderr.decode().splitlines()
                if line.startswith('import time:')}
    assert json.loads(completed.stdout) == {'v': 1, 'error': 'invalid_request'}
    assert {'json', 'playwright.sync_api'} <= imported
    assert not {name for name in imported if name.split('.')[0] in {'django', 'content', 'projectapp'}}
