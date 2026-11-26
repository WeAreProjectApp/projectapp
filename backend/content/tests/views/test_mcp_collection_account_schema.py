"""Public MCP schema for the collection-account preview/create pair."""

import pytest

from content.mcp.operation_catalogs import BILLING_PARITY_TOOLS


_TOOLS = {tool['name']: tool for tool in BILLING_PARITY_TOOLS}


@pytest.mark.parametrize(
    'operation', ['preview_collection_account', 'create_collection_account'],
)
def test_collection_account_mcp_schema_describes_optional_vat_presentation(
    operation,
):
    """MCP clients must be able to hide IVA without changing the money."""
    schema = _TOOLS[operation]['input_schema']
    properties = schema['properties']

    assert 'show_vat' not in schema['required']
    assert properties['show_vat']['type'] == 'boolean'
    assert properties['show_vat']['description'] == (
        'Mostrar el desglose de IVA en el documento y correo. Por defecto true; '
        'no cambia los importes.'
    )


@pytest.mark.parametrize(
    'operation', ['preview_collection_account', 'create_collection_account'],
)
def test_collection_account_mcp_schema_describes_optional_deadline_mode(
    operation,
):
    """MCP clients need the explicit zero-day and no-deadline distinction."""
    schema = _TOOLS[operation]['input_schema']
    properties = schema['properties']

    assert 'due_date_mode' not in schema['required']
    assert properties['due_date_mode']['enum'] == ['legacy', 'dated', 'none']
    assert properties['due_date_mode']['description'] == (
        'dated calcula el vencimiento, incluso con cero días; none omite fecha '
        'y plazo; legacy conserva la regla histórica.'
    )
