"""Migration and retirement checks that preserve MCP consumer authority exactly."""
import importlib
import json
from datetime import datetime, timedelta, timezone as datetime_timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from content.mcp.connectors import PRE_SPLIT_TOOLS_BY_SLUG, tools_for_credential
from content.mcp.consumer_migration import required_owners, translated_grants
from content.models import McpConnector, McpCredential

pytestmark = pytest.mark.django_db


def _connector(slug, *, active=True):
    connector, _ = McpConnector.objects.update_or_create(
        slug=slug,
        defaults={'name': slug, 'is_active': active, 'retired_at': None, 'aliases_retired_at': None},
    )
    connector.credentials.all().delete()
    return connector


def _credential(
    connector, label, *, actor=None, catalog='legacy', allowed_tools=None,
    expires_at=None, migrated_at=None,
):
    return McpCredential.objects.create(
        connector=connector,
        label=label,
        actor=actor,
        catalog=catalog,
        token_hash=McpCredential.hash_token(label),
        allowed_tools=allowed_tools or [],
        expires_at=expires_at,
        migrated_at=migrated_at,
    )


def _preserve_consumers():
    migration = importlib.import_module('content.migrations.0293_mcp_module_unification')
    migration.preserve_consumers(django_apps, SimpleNamespace(connection=connection))
    return migration


def _segment_commercial_consumers():
    migration = importlib.import_module('content.migrations.0298_segment_commercial_mcps')
    migration.segment_connectors(django_apps, SimpleNamespace(connection=connection))
    return migration


def _segmented_connector(slug):
    connector, _ = McpConnector.objects.update_or_create(
        slug=slug,
        defaults={'name': slug, 'is_active': True, 'retired_at': None,
                  'aliases_retired_at': None},
    )
    if not connector.is_active:
        connector.is_active = True
        connector.save(update_fields=['is_active'])
    return connector


def _section_replacements(source, *, actor, expires_at):
    replacements = []
    for slug in sorted(required_owners(source)):
        grants, kinds = translated_grants(source, slug)
        replacements.append(_credential(
            _segmented_connector(slug), f'{slug} replacement', actor=actor,
            catalog='canonical', allowed_tools=grants, expires_at=expires_at,
        ))
        replacements[-1].income_kinds = kinds
        replacements[-1].save(update_fields=['income_kinds'])
    return replacements


def _replacement_with_extra_grant(replacement, _user_model, _expiry):
    replacement.allowed_tools = [*replacement.allowed_tools, 'get_hour_package_settings']
    replacement.save(update_fields=['allowed_tools'])


def _replacement_with_other_actor(replacement, user_model, _expiry):
    replacement.actor = user_model.objects.create_user(username='other-pre-split-actor')
    replacement.save(update_fields=['actor'])


def _replacement_with_later_expiry(replacement, _user_model, expiry):
    replacement.expires_at = expiry + timedelta(days=1)
    replacement.save(update_fields=['expires_at'])


@pytest.fixture
def segmented_commercial_consumers(superuser):
    commercial = _connector('commercial')
    preserved_expiry = datetime(2026, 12, 1, tzinfo=datetime_timezone.utc)
    commercial.aliases_retired_at = datetime(2026, 10, 1, tzinfo=datetime_timezone.utc)
    commercial.migration_started_at = datetime(2026, 9, 1, tzinfo=datetime_timezone.utc)
    commercial.consumers_verified_at = datetime(2026, 9, 2, tzinfo=datetime_timezone.utc)
    commercial.save(update_fields=['aliases_retired_at', 'migration_started_at', 'consumers_verified_at'])
    scoped = _credential(
        commercial, 'Scoped commercial consumer', actor=superuser, catalog='canonical',
        allowed_tools=['list_clients'], expires_at=preserved_expiry,
        migrated_at=datetime(2026, 10, 1, tzinfo=datetime_timezone.utc),
    )
    unrestricted = _credential(commercial, 'Unrestricted commercial consumer', catalog='canonical')
    legacy = _credential(commercial, 'Unchanged legacy consumer', catalog='legacy', allowed_tools=['list_clients'])
    migration = _segment_commercial_consumers()
    scoped.refresh_from_db()
    unrestricted.refresh_from_db()
    legacy.refresh_from_db()
    commercial.refresh_from_db()
    frozen_names = json.loads((Path(migration.__file__).parent.parent / 'mcp' / 'pre_split_commercial_names.json').read_text())

    return {
        'commercial': commercial,
        'frozen_names': frozen_names,
        'legacy': legacy,
        'migration': migration,
        'scoped': scoped,
        'unrestricted': unrestricted,
        'expiry': preserved_expiry,
        'superuser': superuser,
    }


def test_segment_migration_preserves_scoped_commercial_grant(segmented_commercial_consumers):
    """Fails if segmentation changes an explicit commercial credential identity or grant."""
    state = segmented_commercial_consumers
    scoped = state['scoped']

    assert (scoped.catalog, scoped.allowed_tools, scoped.actor_id, scoped.expires_at, scoped.migrated_at) == (
        'pre_split', ['list_clients'], state['superuser'].pk, state['expiry'], None,
    )


def test_segment_migration_freezes_unrestricted_commercial_grants(segmented_commercial_consumers):
    """Fails if an unrestricted commercial credential loses the frozen compatibility catalog."""
    state = segmented_commercial_consumers
    unrestricted = state['unrestricted']
    legacy_launch = next(
        tool for tool in tools_for_credential('commercial', unrestricted)
        if tool['name'] == 'launch_proposal_to_platform'
    )

    assert unrestricted.catalog == 'pre_split'
    assert unrestricted.allowed_tools == state['frozen_names']
    assert state['migration'].PRE_SPLIT_NAMES == state['frozen_names']
    assert legacy_launch['_hidden'] is True
    assert 'launch_proposal_to_platform' in {
        tool['name'] for tool in PRE_SPLIT_TOOLS_BY_SLUG['commercial']
    }


def test_segment_migration_preserves_legacy_retirement_state(segmented_commercial_consumers):
    """Fails if the new commercial epoch rewrites legacy credentials or retirement evidence."""
    state = segmented_commercial_consumers
    legacy = state['legacy']
    commercial = state['commercial']

    assert (legacy.catalog, legacy.allowed_tools) == ('legacy', ['list_clients'])
    assert (commercial.aliases_retired_at, commercial.migration_started_at, commercial.consumers_verified_at) == (
        datetime(2026, 10, 1, tzinfo=datetime_timezone.utc),
        datetime(2026, 9, 1, tzinfo=datetime_timezone.utc),
        datetime(2026, 9, 2, tzinfo=datetime_timezone.utc),
    )
    assert commercial.pre_split_started_at is not None
    assert commercial.pre_split_consumers_verified_at is None


def test_segment_migration_provisions_inactive_destination_connectors(segmented_commercial_consumers):
    """Fails if segmentation creates an active destination or a credential before operator activation."""
    destinations = McpConnector.objects.in_bulk(['offerings', 'programs'], field_name='slug')

    assert (destinations['offerings'].is_active, destinations['offerings'].credentials.count()) == (False, 0)
    assert (destinations['programs'].is_active, destinations['programs'].credentials.count()) == (False, 0)


def test_pre_split_consumer_requires_one_exact_replacement_per_section(superuser):
    """Fails if one replacement can mark a client, offering, and program credential as migrated."""
    commercial = _connector('commercial')
    expiry = datetime(2026, 12, 1, tzinfo=datetime_timezone.utc)
    source = _credential(
        commercial, 'Cross-section commercial consumer', actor=superuser, catalog='pre_split',
        allowed_tools=['list_clients', 'list_hour_packages', 'get_building_with_us_program'],
        expires_at=expiry,
    )
    replacements = _section_replacements(source, actor=superuser, expires_at=expiry)

    assert required_owners(source) == {'commercial', 'offerings', 'programs'}
    assert {replacement.connector.slug for replacement in replacements} == {
        'commercial', 'offerings', 'programs',
    }
    with pytest.raises(CommandError, match='Faltan destinos canónicos'):
        call_command(
            'mcp_retirement', '--slug', 'commercial', '--catalog', 'pre_split',
            '--migrated-credential', str(source.pk),
            '--replacement-credential', str(replacements[0].pk), '--apply',
        )
    source.refresh_from_db()
    assert source.migrated_at is None

    call_command(
        'mcp_retirement', '--slug', 'commercial', '--catalog', 'pre_split',
        '--migrated-credential', str(source.pk),
        *[item for replacement in replacements for item in ('--replacement-credential', str(replacement.pk))],
        '--apply',
    )

    source.refresh_from_db()
    assert source.migrated_at is not None


@pytest.mark.parametrize(
    'mutate',
    [_replacement_with_extra_grant, _replacement_with_other_actor, _replacement_with_later_expiry],
    ids=['extra_grant', 'other_actor', 'later_expiry'],
)
def test_pre_split_consumer_rejects_non_equivalent_section_replacement(
    superuser, django_user_model, mutate,
):
    """Fails if acknowledging segmented access accepts extra grants or changes actor or expiry."""
    commercial = _connector('commercial')
    expiry = datetime(2026, 12, 1, tzinfo=datetime_timezone.utc)
    source = _credential(
        commercial, 'Invalid replacement', actor=superuser, catalog='pre_split',
        allowed_tools=['list_clients', 'list_hour_packages', 'get_building_with_us_program'],
        expires_at=expiry,
    )
    replacements = _section_replacements(source, actor=superuser, expires_at=expiry)
    altered = next(item for item in replacements if item.connector.slug == 'offerings')
    mutate(altered, django_user_model, expiry)

    with pytest.raises(CommandError, match='conservar exactamente permisos, actor y vencimiento'):
        call_command(
            'mcp_retirement', '--slug', 'commercial', '--catalog', 'pre_split',
            '--migrated-credential', str(source.pk),
            *[item for replacement in replacements for item in ('--replacement-credential', str(replacement.pk))],
            '--apply',
        )

    source.refresh_from_db()
    assert source.migrated_at is None


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
