"""The Projects-to-integrity migration preserves legacy credential authority."""
import importlib
from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection

from content.models import McpConnector, McpCredential

pytestmark = pytest.mark.django_db


def _projects_connector():
    McpConnector.objects.filter(slug='data-integrity').delete()
    connector, _ = McpConnector.objects.update_or_create(
        slug='projects', defaults={'name': 'Proyectos', 'is_active': True},
    )
    connector.credentials.all().delete()
    return connector


def _credential(connector, label, *, actor, allowed_tools, expires_at):
    return McpCredential.objects.create(
        connector=connector, label=label, actor=actor, catalog='canonical',
        token_hash=McpCredential.hash_token(label), allowed_tools=allowed_tools,
        expires_at=expires_at,
    )


def _split_projects():
    migration = importlib.import_module('content.migrations.0306_data_integrity_connector')
    migration.split_projects(django_apps, SimpleNamespace(connection=connection))
    return migration


def test_project_split_preserves_explicit_credential_identity(superuser):
    """Fails if separating integrity changes an explicitly scoped Projects consumer or its expiration."""
    connector = _projects_connector()
    expiry = datetime(2026, 12, 1, tzinfo=datetime_timezone.utc)
    credential = _credential(
        connector, 'Explicit project scope', actor=superuser,
        allowed_tools=['list_projects'], expires_at=expiry,
    )

    _split_projects()

    credential.refresh_from_db()
    assert (credential.catalog, credential.allowed_tools, credential.actor_id,
            credential.expires_at, credential.migrated_at) == (
        'pre_split', ['list_projects'], superuser.pk, expiry, None,
    )


def test_project_split_freezes_empty_grants_with_inactive_destination(superuser):
    """Fails if an unrestricted legacy Projects consumer loses compatibility or the new destination starts active."""
    connector = _projects_connector()
    credential = _credential(
        connector, 'Full project scope', actor=superuser,
        allowed_tools=[], expires_at=None,
    )

    migration = _split_projects()

    credential.refresh_from_db()
    destination = McpConnector.objects.get(slug='data-integrity')
    assert credential.catalog == 'pre_split'
    assert credential.allowed_tools == migration.PRE_SPLIT_NAMES
    assert (destination.is_active, destination.credentials.count()) == (False, 0)
