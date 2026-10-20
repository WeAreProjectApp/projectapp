"""Explicit canonical schemas introduced by MCP module consolidation."""

import pytest

from content.mcp.connectors import TOOLS_BY_SLUG
from content.mcp.protocol import ToolError
from content.mcp.schema_backlog import (
    DEFERRED_SCHEMA_BACKLOG,
    GENERIC_ADAPTER_BACKLOG,
    UNDESCRIBED_ARGUMENT_BACKLOG,
)
from content.mcp.schema_policy import is_generic, schema_problems, undescribed_root_properties
from content.models import AccountingSettings, McpActionIntent, McpConnector, McpCredential
from content.tests.mcp_parity import call_tool_inprocess


CANONICAL_SCHEMA_TOOLS = (
    ('accounting', 'duplicate_income'),
    ('accounting', 'get_accounting_dashboard'),
    ('accounting', 'get_accounting_settings'),
    ('accounting', 'list_ads_records'),
    ('accounting', 'list_card_snapshots'),
    ('accounting', 'list_expenses'),
    ('accounting', 'list_hostings'),
    ('accounting', 'list_incomes'),
    ('accounting', 'list_notification_recipients'),
    ('accounting', 'list_pocket_movements'),
    ('accounting', 'list_recurring_payments'),
    ('accounting', 'update_accounting_settings'),
    ('communications', 'create_communication_folder'),
    ('communications', 'delete_communication_folder'),
    ('communications', 'list_communication_folders'),
    ('communications', 'update_communication_folder'),
)


@pytest.mark.parametrize(('slug', 'name'), CANONICAL_SCHEMA_TOOLS, ids=lambda value: value)
def test_consolidated_tool_uses_an_explicit_schema_without_exception(slug, name):
    tool = next(tool for tool in TOOLS_BY_SLUG[slug] if tool['name'] == name)

    assert is_generic(tool) is False
    assert undescribed_root_properties(tool) == []
    assert schema_problems(tool) == []
    assert name not in GENERIC_ADAPTER_BACKLOG
    assert name not in UNDESCRIBED_ARGUMENT_BACKLOG
    assert name not in DEFERRED_SCHEMA_BACKLOG


@pytest.fixture
def accounting_credential(db, superuser):
    connector, _ = McpConnector.objects.update_or_create(
        slug='accounting',
        defaults={
            'name': 'Contabilidad',
            'is_active': True,
            'retired_at': None,
            'aliases_retired_at': None,
        },
    )
    connector.credentials.all().delete()
    return McpCredential.objects.create(
        connector=connector,
        actor=superuser,
        label='Canonical accounting schemas',
        catalog='canonical',
    )


@pytest.fixture
def accounting_settings(db):
    settings, _ = AccountingSettings.objects.update_or_create(
        pk=1,
        defaults={'notifications_enabled': True},
    )
    return settings


def _invoke(credential, name, arguments):
    payload = call_tool_inprocess('accounting', name, arguments, credential=credential)
    if payload.get('ok') is False:
        error = payload['error']
        raise ToolError(error['message'], code=error['code'], details=error.get('details', {}))
    return payload


def test_accounting_settings_write_requires_confirmation(accounting_credential, accounting_settings):
    preview = _invoke(
        accounting_credential,
        'update_accounting_settings',
        {'notifications_enabled': False},
    )
    accounting_settings.refresh_from_db()

    assert preview['confirmation_required'] is True
    assert accounting_settings.notifications_enabled is True

    confirmed = _invoke(
        accounting_credential,
        'confirm_action',
        {'confirmation_id': preview['confirmation_id']},
    )
    current = _invoke(accounting_credential, 'get_accounting_settings', {})
    accounting_settings.refresh_from_db()

    assert confirmed['confirmed'] is True
    assert accounting_settings.notifications_enabled is False
    assert current['notifications_enabled'] is False


def test_accounting_settings_unknown_field_creates_no_intent(
    accounting_credential,
    accounting_settings,
):
    with pytest.raises(ToolError) as rejected:
        _invoke(
            accounting_credential,
            'update_accounting_settings',
            {'notifications_enabled': False, 'unexpected_setting': True},
        )

    accounting_settings.refresh_from_db()
    assert rejected.value.code == 'unknown_field'
    assert accounting_settings.notifications_enabled is True
    assert not McpActionIntent.objects.exists()
