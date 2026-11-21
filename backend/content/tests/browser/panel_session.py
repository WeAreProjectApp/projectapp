"""Create one browser's staff session using Django's normal loopback login."""
import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import requests


def create_state(origin, actor_file):
    host = urlsplit(origin).hostname
    if host != '127.0.0.1':
        raise ValueError('The published panel fixture requires its loopback Django origin')
    actor = json.loads(actor_file.read_text())
    with requests.Session() as session:
        config = session.get(f'{origin}/api/auth/config/', timeout=10)
        config.raise_for_status()
        response = session.post(
            f'{origin}/admin/login/',
            data={**actor, 'csrfmiddlewaretoken': config.json()['csrf_token'], 'next': '/admin/'},
            allow_redirects=False, timeout=10,
        )
        if response.status_code != 302:
            raise RuntimeError(f'Django did not accept the disposable actor (HTTP {response.status_code})')
        access = session.get(f'{origin}/api/auth/check/', timeout=10)
        access.raise_for_status()
        if not access.json()['user']['is_superuser']:
            raise RuntimeError('The disposable actor cannot open the accounting panel')
        cookies = [
            {'name': cookie.name, 'value': cookie.value, 'domain': host,
             'path': cookie.path, 'expires': cookie.expires or -1, 'secure': cookie.secure,
             'httpOnly': cookie.has_nonstandard_attr('HttpOnly'), 'sameSite': 'Lax'}
            for cookie in session.cookies
        ]
    with tempfile.NamedTemporaryFile(mode='w', dir=actor_file.parent, delete=False) as output:
        json.dump({'cookies': cookies, 'origins': []}, output)
        return output.name


if __name__ == '__main__':
    print(create_state(sys.argv[1], Path(sys.argv[2])))
