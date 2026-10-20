"""Migration and retirement checks that preserve MCP consumer authority exactly."""
import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from content.models import McpConnector, McpCredential

pytestmark = pytest.mark.django_db


def _connector(slug, *, active=True):
    connector, _ = McpConnector.objects.update_or_create(
        slug=slug,
        defaults={'name': slug, 'is_active': active, 'retired_at': None, 'aliases_retired_at': None},
    )
    connector.credentials.all().delete()
    return connector


def _credential(connector, label, *, actor=None, catalog='legacy', allowed_tools=None):
    return McpCredential.objects.create(
        connector=connector,
        label=label,
        actor=actor,
        catalog=catalog,
        token_hash=McpCredential.hash_token(label),
        allowed_tools=allowed_tools or [],
    )


def _preserve_consumers():
    migration = importlib.import_module('content.migrations.0293_mcp_module_unification')
    migration.preserve_consumers(django_apps, SimpleNamespace(connection=connection))
    return migration


def test_data_migration_freezes_empty_blog_scope_without_secure_link_reads():
    """Fails if a formerly unrestricted Blog credential gains post-consolidation secure-link reads."""
    connector = _connector('blog')
    credential = _credential(connector, 'Empty scope')

    migration = _preserve_consumers()

    credential.refresh_from_db()
    assert credential.catalog == 'legacy'
    assert credential.allowed_tools == migration.LEGACY_NAMES['blog']
    assert credential.allows('reveal_secure_link_content') is False


def test_data_migration_preserves_an_explicit_secret_grant():
    """Fails if preserving consumers drops an explicitly granted secure-link read."""
    connector = _connector('communications')
    credential = _credential(
        connector, 'Explicit secret', allowed_tools=['reveal_secure_link_content'],
    )

    _preserve_consumers()

    credential.refresh_from_db()
    assert credential.catalog == 'legacy'
    assert credential.allowed_tools == ['reveal_secure_link_content']
    assert credential.allows('reveal_secure_link_content') is True


def _consumer_pair(superuser, *, replacement_actor=None, replacement_tools=None):
    source_connector = _connector('blog')
    target_connector = _connector('content')
    source = _credential(
        source_connector, 'Legacy consumer', actor=superuser,
        allowed_tools=['list_blog_posts'],
    )
    replacement = _credential(
        target_connector, 'Replacement', actor=replacement_actor or superuser,
        catalog='canonical', allowed_tools=replacement_tools or ['list_blog_posts'],
    )
    return source, replacement


def test_retirement_ack_rejects_a_replacement_with_expanded_scope(superuser):
    """Fails if acknowledging a consumer migration accepts more canonical permissions than the source had."""
    source, replacement = _consumer_pair(
        superuser, replacement_tools=['list_blog_posts', 'get_blog_post'],
    )

    with pytest.raises(CommandError, match='conservar exactamente permisos'):
        call_command(
            'mcp_retirement', '--slug', 'blog', '--migrated-credential', str(source.pk),
            '--replacement-credential', str(replacement.pk), '--apply',
        )

    source.refresh_from_db()
    assert source.migrated_at is None


def test_retirement_ack_rejects_a_replacement_owned_by_another_actor(
    superuser, django_user_model,
):
    """Fails if acknowledging migration transfers a consumer to another actor."""
    other = django_user_model.objects.create_user(username='other-mcp-actor')
    source, replacement = _consumer_pair(superuser, replacement_actor=other)

    with pytest.raises(CommandError, match='conservar exactamente permisos, actor y vencimiento'):
        call_command(
            'mcp_retirement', '--slug', 'blog', '--migrated-credential', str(source.pk),
            '--replacement-credential', str(replacement.pk), '--apply',
        )

    source.refresh_from_db()
    assert source.migrated_at is None


def test_retirement_ack_rejects_a_replacement_with_narrower_income_kinds(superuser):
    """Fails if a general income grant is acknowledged as expected-only access."""
    source_connector = _connector('accounting-ledger')
    target_connector = _connector('accounting')
    source = _credential(
        source_connector, 'All income kinds', actor=superuser,
        allowed_tools=['list_income'],
    )
    replacement = _credential(
        target_connector, 'Expected-only replacement', actor=superuser,
        catalog='canonical', allowed_tools=['list_incomes'],
    )
    replacement.income_kinds = ['expected']
    replacement.save(update_fields=['income_kinds'])

    with pytest.raises(CommandError, match='conservar exactamente permisos'):
        call_command(
            'mcp_retirement', '--slug', 'accounting-ledger',
            '--migrated-credential', str(source.pk),
            '--replacement-credential', str(replacement.pk), '--apply',
        )

    source.refresh_from_db()
    assert source.migrated_at is None


def test_panel_migrates_expected_income_scope_to_canonical_income_kinds(super_client, superuser):
    """Fails if moving an expected-income consumer grants liquid or lost access on canonical accounting."""
    source_connector = _connector('accounting-ledger')
    target_connector = _connector('accounting')
    source = _credential(
        source_connector, 'Expected income source', actor=superuser,
        allowed_tools=['list_expected_incomes'],
    )

    response = super_client.post(
        f'/api/mcp-connectors/{target_connector.slug}/credentials/',
        {'label': 'Expected income replacement', 'migrate_from_credential_id': source.pk},
        format='json',
    )

    replacement = McpCredential.objects.get(pk=response.data['id'])
    assert response.status_code == 201
    assert replacement.allowed_tools == ['list_incomes']
    assert replacement.income_kinds == ['expected']
    assert replacement.actor_id == source.actor_id
