"""Ownership changes, archived accounts and replacement boundaries fail closed."""

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps

from secure_links import services
from secure_links.models import SecureLink

from .test_platform_api import base

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('path', ['', 'events/', 'link/', 'revoke/'])
def test_reassigned_project_hides_old_owned_link(platform_client, project, create_owned, staff_user, path):
    link, _, _ = create_owned()
    project.client = staff_user
    project.save(update_fields=['client'])

    response = platform_client.generic('GET' if path in ('', 'events/') else 'POST', f'{base(project)}{link.pk}/{path}', '{}', content_type='application/json')

    assert response.status_code == 404


def test_archived_owner_loses_access(platform_client, project, client_profile):
    from django.utils import timezone

    client_profile.archived_at = timezone.now()
    client_profile.save(update_fields=['archived_at'])

    response = platform_client.get(base(project))

    assert response.status_code == 403


def test_replacement_cannot_cross_project(create_owned, project, client_profile):
    from accounts.models import Project

    previous, _, _ = create_owned()
    services.revoke(previous, actor=client_profile.user)
    other = Project.objects.create(client=client_profile.user, name='Otro proyecto')

    with pytest.raises(services.SecureLinkError) as error:
        create_owned(project_id=other.pk, replaces=previous.pk)

    assert error.value.status == 404
    assert SecureLink.objects.count() == 1


def test_backfill_keeps_legacy_tokens_and_no_owner(make_link):
    legacy, _ = make_link()
    old = SecureLink.objects.values().get(pk=legacy.pk)
    SecureLink.objects.filter(pk=legacy.pk).update(audience='team')
    migration = importlib.import_module('secure_links.migrations.0004_platform_ownership')

    migration.preserve_legacy_audience(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))

    legacy.refresh_from_db()
    assert legacy.audience == 'bearer'
    assert legacy.owner_id is None
    assert legacy.token_encrypted == old['token_encrypted']
    assert legacy.payload_encrypted == old['payload_encrypted']
