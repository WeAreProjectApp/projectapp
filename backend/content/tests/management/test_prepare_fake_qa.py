"""DevQA profile contract for the isolated bootstrap and its real API consumers."""

import json
import os
import re
import secrets
import subprocess
import sys
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from accounts.models import ChangeRequest, Project, UserProfile
from content.fake_data import SeedContext
from content.fake_qa_profiles import (
    LIMITED_CLIENT, STAFF_ACTOR, SUPERUSER, profile_actors, profile_baseline, seed_profile,
)
from content.management.commands import prepare_fake_qa
from content.models import Document


SEED = 231
ANCHOR = date(2026, 11, 6)
CONTEXT = SeedContext(SEED, ANCHOR, 'qa-contract')
TEST_SHA = '1' * 40


def _private_file(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)


def _bootstrap_copy(root):
    """Exercise manage.py against a truly separate database with real settings."""
    root.mkdir(mode=0o700)
    private = root / 'private'
    private.mkdir(mode=0o700)
    _private_file(private / 'django-key', secrets.token_urlsafe(32).encode())
    _private_file(private / 'access-key', Fernet.generate_key())
    backend = Path(__file__).resolve().parents[3]
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=backend, text=True).strip()
    env = {**os.environ, 'DJANGO_ENV': 'development', 'FAKE_DATA_ROOT': str(root), 'RECAPTCHA_ENABLED': 'false'}

    def run(command, *args):
        result = subprocess.run(
            [sys.executable, 'manage.py', command, '--settings=projectapp.settings_fake_data', *args],
            cwd=backend, env=env, capture_output=True, text=True, timeout=240,
        )
        assert result.returncode == 0, result.stderr

    run('migrate', '--noinput', '--verbosity=0')

    def prepare():
        run('prepare_fake_qa', '--profile=b04', f'--expected-sha={sha}',
            '--count=2', f'--seed={SEED}', f'--anchor-date={ANCHOR}')
        return json.loads((root / 'qa-manifest.json').read_text())

    return prepare


def _b04_natural_baseline(manifest):
    baseline = manifest['baseline']
    return {
        'recipe': manifest['recipe'],
        'roles': [(actor['key'], actor['role'], actor['staff'], actor['superuser']) for actor in baseline['actors']],
        'project': baseline['project']['key'],
        'tickets': [(row['key'], row['status']) for row in baseline['tickets'].values()],
        'guide': baseline['published_requirement']['key'],
        'stage': (baseline['draft_stage']['key'], baseline['draft_stage']['status']),
        'permission_checks': baseline['permission_checks'],
    }


def test_bootstrap_reproduces_b04_in_two_disposable_copies(tmp_path):
    first = _bootstrap_copy(tmp_path / 'first')()
    second = _bootstrap_copy(tmp_path / 'second')()

    assert first['mode'] == second['mode'] == 'generado'
    assert _b04_natural_baseline(first) == _b04_natural_baseline(second)
    assert first['copy']['database'] != second['copy']['database']


@pytest.fixture
def b04(db, tmp_path, monkeypatch):
    """Use the same producer with the CI database for API and failure tests."""
    (tmp_path / 'private').mkdir(mode=0o700)
    monkeypatch.setattr(prepare_fake_qa, '_configured_copy', lambda sha: (tmp_path, {'source': 'test-copy'}))

    def setup_base(command, **kwargs):
        assert command == 'create_fake_data'

    monkeypatch.setattr(prepare_fake_qa, 'call_command', setup_base)

    def prepare(*args):
        call_command('prepare_fake_qa', '--profile=b04', f'--expected-sha={TEST_SHA}',
                     f'--seed={SEED}', f'--anchor-date={ANCHOR}', *args, stdout=StringIO())
        return json.loads((tmp_path / 'qa-manifest.json').read_text())

    manifest = prepare()
    return manifest, tmp_path, prepare


def _login(actor, root, profile='b04'):
    access = json.loads((root / 'private' / f'{profile}-access.json').read_text())
    browser = APIClient()
    response = browser.post('/api/accounts/login/', {
        'email': actor['key'], 'password': access[actor['key']],
    }, format='json')
    assert response.status_code == 200
    browser.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['tokens']['access'])
    return browser


def test_compatible_reuse_preserves_actors_access(b04):
    generated, root, prepare = b04
    credential_file = root / 'private' / 'b04-access.json'
    access_before = credential_file.stat()

    reused = prepare()

    assert reused['mode'] == 'reutilizado'
    assert reused['baseline'] == generated['baseline']
    access_after = credential_file.stat()
    assert access_after.st_ino == access_before.st_ino
    assert access_after.st_mtime_ns == access_before.st_mtime_ns
    assert access_after.st_mode & 0o777 == 0o600
    includes_password = any(
        password in json.dumps(reused) for password in json.loads(credential_file.read_text()).values()
    )
    assert not includes_password


def test_incompatible_recipe_preserves_prepared_data(b04):
    generated, root, prepare = b04

    with pytest.raises(CommandError, match='recipe'):
        prepare('--count=3')

    assert json.loads((root / 'qa-manifest.json').read_text()) == generated


def test_consumed_b04_baseline_requires_another_copy(b04):
    generated, root, prepare = b04
    pending = generated['baseline']['tickets']['pending']
    ChangeRequest.objects.filter(pk=pending['id']).update(status=ChangeRequest.STATUS_EVALUATING)

    with pytest.raises(CommandError, match=re.escape(pending['key'])):
        prepare()

    assert ChangeRequest.objects.get(pk=pending['id']).status == ChangeRequest.STATUS_EVALUATING
    assert json.loads((root / 'qa-manifest.json').read_text()) == generated


def test_missing_actor_reports_its_locator(b04):
    generated, _, prepare = b04
    admin = generated['baseline']['actors'][0]
    get_user_model().objects.filter(pk=admin['id']).update(is_active=False)

    with pytest.raises(CommandError, match=re.escape(admin['key'])):
        prepare()


@pytest.mark.parametrize('actor_index', [0, 1])
def test_b04_login_can_list_owned_requests(b04, actor_index):
    manifest, root, _ = b04
    case = manifest['baseline']
    browser = _login(case['actors'][actor_index], root)

    response = browser.get(f"/api/accounts/projects/{case['project']['id']}/change-requests/")

    assert response.status_code == 200
    assert {row['id'] for row in response.data} == {row['id'] for row in case['tickets'].values()}


@pytest.mark.parametrize(('actor_index', 'expected'), [(0, 200), (1, 403)])
def test_b04_evaluation_respects_platform_role(b04, actor_index, expected):
    manifest, root, _ = b04
    case = manifest['baseline']
    pending = case['tickets']['pending']
    browser = _login(case['actors'][actor_index], root)

    response = browser.post(
        f"/api/accounts/projects/{case['project']['id']}/change-requests/{pending['id']}/evaluate/",
        {'status': 'evaluating', 'expected_version': pending['version']}, format='json',
    )

    assert response.status_code == expected


def test_b04_can_convert_into_the_seeded_draft(b04):
    manifest, root, _ = b04
    case = manifest['baseline']
    approved = case['tickets']['approved']
    browser = _login(case['actors'][0], root)

    response = browser.post(
        f"/api/accounts/projects/{case['project']['id']}/change-requests/{approved['id']}/convert/",
        {'stage_id': case['draft_stage']['id'], 'expected_version': case['workspace_version'],
         'issue_version': approved['version']}, format='json',
    )

    assert response.status_code == 201
    requirement = ChangeRequest.objects.get(pk=approved['id']).linked_requirement
    assert requirement.stage_id == case['draft_stage']['id']


@pytest.fixture
def base_roles(db):
    owner = get_user_model().objects.create_user(username='seed-owner@example.test')
    UserProfile.objects.create(user=owner, role='client')
    Project.objects.create(name='Proyecto de siembra', client=owner)
    call_command('create_fake_platform_cases', '--seed', str(SEED), '--anchor-date', str(ANCHOR),
                 '--skip-accounting', stdout=StringIO())


@pytest.fixture
def staff_corpus(base_roles, tmp_path):
    seed_profile('staff', CONTEXT)
    actors = profile_actors('staff')
    return profile_baseline('staff', actors, CONTEXT, tmp_path), actors


@pytest.mark.parametrize(('order', 'first', 'last'), [('recent', 21, 1), ('oldest', 1, 21)])
def test_document_history_paginates_seeded_revisions(staff_corpus, order, first, last):
    baseline, actors = staff_corpus
    browser = APIClient()
    browser.force_login(actors[STAFF_ACTOR])
    path = f"/api/entity-history/document/{baseline['documents']['history']['id']}/"

    page_one = browser.get(path, {'order': order})
    page_two = browser.get(path, {'order': order, 'page': 2})

    assert page_one.data['count'] == 21
    assert len(page_one.data['results']) == 20
    assert page_one.data['results'][0]['number'] == first
    assert [row['number'] for row in page_two.data['results']] == [last]


def test_document_seed_provides_a_readable_comparison(staff_corpus):
    baseline, actors = staff_corpus
    browser = APIClient()
    browser.force_login(actors[STAFF_ACTOR])
    before, after = baseline['history']['comparison']

    response = browser.get(
        f"/api/entity-history/document/{baseline['documents']['history']['id']}/compare/",
        {'from': before['id'], 'to': after['id']},
    )

    assert response.status_code == 200
    assert any('Revisión de referencia 21.' in str(change['new']) for change in response.data['changes'])


def test_editing_independent_document_preserves_reference_history(staff_corpus):
    baseline, actors = staff_corpus
    browser = APIClient()
    browser.force_login(actors[STAFF_ACTOR])
    editable = baseline['documents']['editable']['id']
    reference = baseline['documents']['history']['id']
    url = f'/api/entity-history/document/{reference}/'
    history_before = browser.get(url).data

    response = browser.patch(f'/api/documents/{editable}/update/',
                             {'content_markdown': '# Cambio reversible'}, format='json')

    assert response.status_code == 200
    assert browser.get(url).data == history_before


@pytest.fixture
def pdf_reader(staff_corpus, request):
    baseline, actors = staff_corpus
    browser = APIClient()
    if request.param:
        browser.force_login(actors[request.param])
    return browser, baseline['pdf']['download']


@pytest.mark.parametrize(('pdf_reader', 'status'), [
    (STAFF_ACTOR, 200), (LIMITED_CLIENT, 403), (None, 401),
], indirect=['pdf_reader'])
def test_private_pdf_enforces_the_download_boundary(pdf_reader, status):
    browser, download_url = pdf_reader

    response = browser.get(download_url)

    assert response.status_code == status


def test_private_pdf_manifest_matches_document_bytes(staff_corpus):
    baseline, actors = staff_corpus
    browser = APIClient()
    browser.force_login(actors[STAFF_ACTOR])

    response = browser.get(baseline['pdf']['download'], {'inline': 1})

    assert response['Content-Type'] == baseline['pdf']['content_type']
    assert len(b''.join(response.streaming_content)) == baseline['pdf']['size']
    assert Document.objects.get(pk=baseline['documents']['pdf']['id']).pdf_version == baseline['pdf']['version'] == 1


@pytest.fixture
def su_corpus(base_roles, tmp_path):
    seed_profile('su', CONTEXT)
    actors = profile_actors('su')
    return profile_baseline('su', actors, CONTEXT, tmp_path), actors, tmp_path


def test_accounting_filters_find_the_expected_extreme(su_corpus):
    baseline, actors, _ = su_corpus
    browser = APIClient()
    browser.force_login(actors[SUPERUSER])
    large = baseline['incomes']['large']

    listing = browser.get('/api/accounting/incomes/', baseline['filters'])
    detail = browser.get(large['detail'])

    row = next(item for item in listing.data['results'] if item['id'] == large['id'])
    assert row['total_amount'] == detail.data['income']['total_amount'] == '999999999999.99'
    assert detail.data['income']['pending_amount'] == '999999999999.99'


@pytest.mark.parametrize(('variant', 'parts'), [
    ('automatic', {}), ('manual', {'gustavo_amount': '50.25', 'carlos_amount': '60.50'}), ('whole', {}),
])
def test_settlement_preview_keeps_accounting_baseline(su_corpus, variant, parts):
    baseline, actors, mail = su_corpus
    browser = APIClient()
    browser.force_login(actors[SUPERUSER])
    expected = baseline['previews'][variant]
    payload = {
        'income_ids': [baseline['incomes'][variant]['id']],
        'period_date': baseline['filters']['date_from'], 'total_amount': expected['received'],
        'send_payment_confirmation': False, **parts,
    }

    response = browser.post('/api/accounting/incomes/settlement-preview/', payload, format='json')

    assert response.status_code == 200
    plan = response.data
    remainder = Decimal(plan['total_amount']) - Decimal(plan['gustavo_amount']) - Decimal(plan['carlos_amount'])
    assert tuple(str(plan[key]) for key in ('gustavo_amount', 'carlos_amount', 'pending_after')) == (
        expected['gustavo'], expected['carlos'], expected['pending'],
    )
    assert remainder == Decimal(expected['projectapp'])
    assert profile_baseline('su', actors, CONTEXT, mail) == baseline


@pytest.mark.parametrize(('role', 'path', 'status'), [
    (STAFF_ACTOR, '/api/accounts/admins/', 403),
    (SUPERUSER, '/api/accounts/admins/', 200),
    (STAFF_ACTOR, '/api/accounting/incomes/', 403),
])
def test_seeded_panel_roles_enforce_endpoint_permissions(su_corpus, role, path, status):
    _, actors, _ = su_corpus
    browser = APIClient()
    browser.force_login(actors[role])

    assert browser.get(path).status_code == status


@pytest.mark.parametrize(('endpoint', 'status'), [
    ('change-requests', 200), ('bug-reports', 403),
])
def test_limited_client_capability_on_its_project(staff_corpus, endpoint, status):
    baseline, actors = staff_corpus
    browser = APIClient()
    browser.force_authenticate(actors[LIMITED_CLIENT])

    assert browser.get(f"/api/accounts/projects/{baseline['project']['id']}/{endpoint}/").status_code == status


def test_limited_client_cannot_read_another_project(staff_corpus):
    _, actors = staff_corpus
    browser = APIClient()
    browser.force_authenticate(actors[LIMITED_CLIENT])
    other_id = Project.objects.get(name='Proyecto de siembra').pk

    assert browser.get(f'/api/accounts/projects/{other_id}/change-requests/').status_code == 403
