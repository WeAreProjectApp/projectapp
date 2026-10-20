"""Complete contracts for resources introduced by module consolidation."""
import json

from content.mcp.panel_bridge import panel_operation
from content.mcp.proposal_schemas import writable_schema
from content.mcp.schema_policy import closed_object
from content.serializers.accounting import AccountingSettingsSerializer


_ACCOUNTING_LISTS = frozenset({
    'list_incomes', 'list_expenses', 'list_hostings', 'list_pocket_movements',
    'list_recurring_payments', 'list_ads_records', 'list_card_snapshots',
    'list_notification_recipients', 'get_accounting_dashboard',
})
_FILTER_DESCRIPTIONS = {
    'year': 'Año contable por el que se filtran los registros.',
    'amount_min': 'Monto mínimo del registro, incluido en el filtro.',
    'amount_max': 'Monto máximo del registro, incluido en el filtro.',
    'is_active': 'Filtra registros activos con true e inactivos con false.',
    'is_receivable_candidate': 'Filtra por inclusión manual en la previsión de cobro.',
}
_FOLDER_DESCRIPTIONS = {
    'name': 'Nombre de la carpeta de comunicaciones, hasta 120 caracteres.',
    'parent': 'ID de la carpeta padre del mismo cliente/proyecto; null sitúa la carpeta en la raíz.',
    'client': 'ID del perfil del cliente propietario; no se cambia al actualizar una carpeta.',
    'project': 'ID del proyecto del cliente, o null sin proyecto; no se cambia al actualizar una carpeta.',
    'client_id': 'Filtra las carpetas por ID del perfil del cliente propietario.',
    'project_id': 'Filtra las carpetas por ID del proyecto del cliente.',
    'folder_id': 'ID positivo de la carpeta de comunicaciones que se modifica o elimina.',
}
_SETTINGS_DESCRIPTIONS = {
    'notifications_enabled': 'Activa o pausa todos los correos automatizados del módulo contable.',
    'card_reminder_enabled': 'Activa los recordatorios de actualización de deuda de tarjetas.',
    'statement_reminder_enabled': 'Activa los recordatorios de extractos pendientes del mes anterior.',
    'hosting_expiry_reminder_enabled': 'Incluye los vencimientos de hosting en el calendario de pagos.',
    'payment_calendar_enabled': 'Activa el correo diario consolidado del calendario de pagos.',
    'overdue_reminder_frequency': 'Frecuencia de recordatorios de ingresos esperados vencidos: semanal o quincenal.',
    'usd_exchange_rate': 'Pesos colombianos por dólar para convertir los indicadores; mínimo 1.',
    'income_default_view_mode': 'Vista inicial de ingresos: grouped agrupa y classic muestra la lista clásica.',
    'collection_accounts_view_mode': 'Vista de cuentas de cobro: grouped agrupa y classic muestra la lista clásica.',
    'collection_accounts_group_by': 'Agrupa las cuentas de cobro por cliente o por proyecto.',
}


def complete_canonical_schema(tool, slug):
    """Keep legacy schemas intact while publishing complete canonical inputs."""
    name = tool['name']
    properties = tool['input_schema'].get('properties', {})
    if slug == 'accounting' and name in _ACCOUNTING_LISTS:
        tool['strict_arguments'] = True
        for field, description in _FILTER_DESCRIPTIONS.items():
            if field in properties:
                properties[field].setdefault('description', description)
        if name == 'list_incomes':
            properties['q']['description'] = 'Texto que se busca en el concepto o las notas del ingreso.'
    if slug == 'accounting' and name == 'duplicate_income':
        tool['strict_arguments'] = True
        properties['overrides']['description'] = 'Campos que reemplazan los valores del ingreso original al duplicarlo.'
    if slug == 'communications' and name in {
        'list_communication_folders', 'create_communication_folder',
        'update_communication_folder', 'delete_communication_folder',
    }:
        tool['strict_arguments'] = True
        for field, schema in properties.items():
            schema['description'] = _FOLDER_DESCRIPTIONS[field]
    if slug == 'accounting' and name in {'get_accounting_settings', 'update_accounting_settings'}:
        operation = tool['_panel_operation']
        schemas = {'query_schema': closed_object({})}
        if operation['method'] != 'GET':
            # DRF emits Decimal limits; JSON Schema requires JSON numbers.
            payload = json.loads(json.dumps(
                writable_schema(AccountingSettingsSerializer, partial=True), default=float,
            ))
            for field, schema in payload['properties'].items():
                schema['description'] = _SETTINGS_DESCRIPTIONS[field]
            schemas = {'payload_schema': payload}
        tool.update(panel_operation(
            name, tool['description'], operation['route_name'],
            method=operation['method'], envelope_aliases=False,
            risk='read' if operation['method'] == 'GET' else 'sensitive',
            requires_confirmation=operation['method'] != 'GET',
            confirmation_message=tool.get('confirmation_message', ''), **schemas,
        ))
        tool['strict_arguments'] = True
