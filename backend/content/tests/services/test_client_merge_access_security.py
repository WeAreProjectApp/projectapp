"""Client merges preserve authentication ownership and security evidence."""

from datetime import timedelta

import pytest
from accounts.access_models import AccessEvent, GoogleIdentity, LoginChallenge
from accounts.services import access
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError

from content.models import DocumentState, DocumentStateGroup
from content.services import client_merge
from content.tests.data_integrity_merge_factories import client_pair, run_client_merge
from hosting_control.models import Control, Event
from monitoring.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def project_lifecycle_catalog(db):
    group, _ = DocumentStateGroup.objects.get_or_create(
        catalog='projects',
        name='Client merge lifecycle',
        defaults={'selection_mode': 'exclusive'},
    )
    DocumentState.objects.get_or_create(
        catalog='projects',
        system_key='suspended',
        defaults={
            'group': group,
            'name': 'Suspendido',
            'operational_effect': 'suspended',
        },
    )


def test_merge_preserves_access_event_principals(superuser):
    survivor, duplicate = client_pair()
    event = AccessEvent.objects.create(
        user=duplicate.user,
        actor=duplicate.user,
        action='disabled',
    )

    run_client_merge(superuser, survivor, duplicate)

    event.refresh_from_db()
    assert (event.user_id, event.actor_id) == (duplicate.user_id, duplicate.user_id)


def test_merge_preserves_hosting_event_author(superuser):
    survivor, duplicate = client_pair()
    resource = Resource.objects.create(key='hosting-audit', name='Sitio de prueba', kind='project')
    control = Control.objects.create(resource=resource)
    event = Event.objects.create(control=control, actor=duplicate.user, actor_name=duplicate.user.username,
                                 source='panel', before={'mode': 'normal'}, after={'mode': 'banner'}, version=1)

    run_client_merge(superuser, survivor, duplicate)

    event.refresh_from_db()
    assert event.actor_id == duplicate.user_id
    assert event.actor_name == duplicate.user.username


def test_merge_preview_has_no_policy_drift():
    survivor, duplicate = client_pair()

    plan = client_merge.plan_client_merge(survivor, duplicate)

    assert 'relation_policy_missing' not in {
        row['code'] for row in plan['preview']['blockers']
    }


def test_merge_blocks_google_identity_owner_rewrite():
    survivor, duplicate = client_pair()
    identity = GoogleIdentity.objects.create(user=duplicate.user, subject='duplicate-google-subject')

    plan = client_merge.plan_client_merge(survivor, duplicate)

    blocker = next(
        row for row in plan['preview']['blockers']
        if row.get('relation') == 'accounts.GoogleIdentity.user'
    )
    identity.refresh_from_db()
    assert blocker['code'] == 'duplicate_has_privileges'
    assert identity.user_id == duplicate.user_id


@freeze_time('2026-11-05T12:00:00Z')
def test_retired_duplicate_rejects_login_challenge(superuser):
    survivor, duplicate = client_pair(user_values={'is_active': True})
    browser = 'merge-security-browser'
    code = '314159'
    challenge = LoginChallenge.objects.create(
        user=duplicate.user,
        surface='platform',
        browser_digest=access.digest(browser),
        identity_digest=access.identity_digest(duplicate.user),
        access_version=duplicate.access_version,
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    LoginChallenge.objects.filter(pk=challenge.pk).update(
        code_digest=access.digest(f'{challenge.pk}:{code}'),
    )

    run_client_merge(superuser, survivor, duplicate)

    with pytest.raises(ValidationError):
        access.verify_code(
            challenge_id=challenge.pk,
            code=code,
            surface='platform',
            browser=browser,
        )
    challenge.refresh_from_db()
    assert challenge.user_id == duplicate.user_id
    assert challenge.closed is True
    assert challenge.code_digest == ''
