"""Single registry of MCP connector identities and ordered tool sources."""
from dataclasses import dataclass, replace

from content.mcp import registry
from content.mcp.accounting_tools import ACCOUNTING_TOOLS
from content.mcp.building_on_demand_contract_tools import BUILDING_ON_DEMAND_CONTRACT_TOOLS
from content.mcp.building_on_demand_tools import BUILDING_ON_DEMAND_TOOLS
from content.mcp.building_with_us_tools import BUILDING_WITH_US_TOOLS
from content.mcp.client_tools import CLIENT_TOOLS
from content.mcp.commercial_module_tools import (
    ADDITIONAL_MODULE_TOOLS,
    PARTNERSHIP_PROGRAM_TOOLS,
)
from content.mcp.common_tools import build_common_tools
from content.mcp.communication_tools import COMMUNICATION_TOOLS
from content.mcp.diagnostic_tools import DIAGNOSTIC_TOOLS
from content.mcp.document_thread_tools import DOCUMENT_THREAD_TOOLS
from content.mcp.document_tools import DOCUMENT_TOOLS
from content.mcp.expected_income_tools import EXPECTED_INCOME_TOOLS
from content.mcp.linkedin_tools import LINKEDIN_TOOLS
from content.mcp.linktree_template_tools import LINKTREE_TEMPLATE_TOOLS
from content.mcp.operation_catalogs import (
    BILLING_PARITY_TOOLS,
    CARD_PARITY_TOOLS,
    COMMERCIAL_PARITY_TOOLS,
    COMMUNICATION_EMAIL_TOOLS,
    CONTENT_PARITY_TOOLS,
    DOCUMENT_PARITY_TOOLS,
    LEDGER_PARITY_TOOLS,
    OPERATIONS_TOOLS,
    PROJECT_TOOLS,
)
from content.mcp.platform_billing_tools import PLATFORM_BILLING_TOOLS
from content.mcp.platform_secure_link_tools import PLATFORM_SECURE_LINK_TOOLS
from content.mcp.proposal_formalization_tools import PROPOSAL_FORMALIZATION_TOOLS
from content.mcp.proposal_operations import PROPOSAL_PARITY_TOOLS
from content.mcp.proposal_tools import PROPOSAL_TOOLS
from content.mcp.secure_link_tools import SECURE_LINK_TOOLS
from content.mcp.task_tools import TASK_TOOLS
from content.mcp.tools import BLOG_TOOLS
from content.mcp.video_tools import PROPOSAL_VIDEO_TOOLS


BASE = (
    'Usa tools/list o describe_capabilities para conocer las acciones de este '
    'conector: ambos publican el mismo esquema y respetan el alcance de tu '
    'credencial. Envía sólo los argumentos que declara cada esquema.'
)
CONFIRMATION_NOTICE = (
    'Las acciones con requires_confirmation=true devuelven primero una vista '
    'previa con confirmation_id: ejecútala con confirm_action o descártala '
    'con cancel_action.'
)
DIRECT_EXECUTION_NOTICE = (
    'Este conector está en retirada. Migra al conector {canonical_area}. '
    'Las acciones sensibles conservan la vista previa y se confirman aquí '
    'con confirm_action o se descartan con cancel_action.'
)
UPLOAD_NOTICE = (
    'Para adjuntar un archivo, inicia begin_upload, transfiere sus bytes '
    'mediante PUT a la upload_url firmada o mediante upload_asset_chunk, '
    'valida la carga con complete_upload y envía el asset_id resultante a la '
    'acción que lo usa; abort_upload cancela una carga aún no consumida.'
)
ACCOUNTING_NOTE = (
    'Los recurrentes (recurring) son gastos periódicos y suscripciones que la '
    'empresa paga, no ingresos. Los ingresos (income) usan kind expected '
    '(por cobrar), liquid (recibido) o lost (perdido).'
    ' Para abonar uno o varios esperados sin emitir cuenta usa bulk_settle_incomes; '
    'settle_income y bulk_settle_incomes comparten deducciones y participaciones. Usa preview_income_settlement antes de registrar. Para corregir '
    'todo el abono usa update_income_abono y para deshacerlo delete_income_abono, '
    'con record_id del movimiento de bolsillo, consultable en get_pocket. Para consultar, corregir o revertir cualquier liquidación, incluso sin bolsillo, usa get_income_settlement, update_income_settlement y reverse_income_settlement con settlement_id.'
)


@dataclass(frozen=True)
class ConnectorSpec:
    slug: str
    version: str
    sources: tuple[list[dict], ...]
    compatibility: bool = False
    uploads: bool = False
    confirm_sensitive: bool = False
    canonical_area: str = ''
    notes: tuple[str, ...] = ()
    module_id: str = ''

    @property
    def server_name(self):
        return f'projectapp-{self.slug}-mcp'

    @property
    def server_info(self):
        return {'name': self.server_name, 'version': self.version}

    @property
    def instructions(self):
        parts = [BASE]
        if any(tool.get('requires_confirmation') for tool in TOOLS_BY_SLUG[self.slug]):
            parts.append(CONFIRMATION_NOTICE)
        if self.compatibility:
            parts.append(DIRECT_EXECUTION_NOTICE.format(canonical_area=self.canonical_area))
        if self.uploads:
            parts.append(UPLOAD_NOTICE)
        parts.extend(self.notes)
        return ' '.join(parts)


def accounting_area(area):
    invalid = [
        tool['name'] for tool in ACCOUNTING_TOOLS
        if tool.get('area') not in {'ledger', 'billing', 'cards'}
    ]
    if invalid:
        raise RuntimeError(f'Invalid MCP accounting areas: {", ".join(invalid)}')
    return [tool for tool in ACCOUNTING_TOOLS if tool['area'] == area]


SOURCE_CONNECTORS: dict[str, ConnectorSpec] = {
    'blog': ConnectorSpec(
        'blog', '1.1.0', (BLOG_TOOLS,),
        compatibility=True, canonical_area='content',
    ),
    'documents': ConnectorSpec(
        'documents', '6.0.0',
        (DOCUMENT_TOOLS, DOCUMENT_THREAD_TOOLS, DOCUMENT_PARITY_TOOLS),
        uploads=True, confirm_sensitive=True,
        notes=(
            'Los espejos de contrato (is_contract_mirror=true) son de solo lectura '
            'y no se mueven: revisa editable, movable y move_blockers antes de '
            'editar o mover.',
        ),
    ),
    'clients': ConnectorSpec(
        'clients', '1.1.0', (CLIENT_TOOLS,),
        compatibility=True, canonical_area='commercial',
    ),
    'communications': ConnectorSpec(
        'communications', '2.1.1',
        (COMMUNICATION_TOOLS, COMMUNICATION_EMAIL_TOOLS, SECURE_LINK_TOOLS,
         PLATFORM_SECURE_LINK_TOOLS),
        uploads=True, confirm_sensitive=True,
    ),
    'tasks': ConnectorSpec(
        'tasks', '2.1.0', (TASK_TOOLS,), confirm_sensitive=True,
    ),
    'accounting': ConnectorSpec(
        'accounting', '1.4.1', (ACCOUNTING_TOOLS, EXPECTED_INCOME_TOOLS),
        compatibility=True,
        canonical_area='accounting-ledger, accounting-billing o accounting-cards',
        notes=(ACCOUNTING_NOTE,),
    ),
    'diagnostics': ConnectorSpec(
        'diagnostics', '1.1.0', (DIAGNOSTIC_TOOLS,),
        compatibility=True, canonical_area='commercial',
    ),
    'proposals': ConnectorSpec(
        'proposals', '4.0.0',
        (PROPOSAL_TOOLS, PROPOSAL_PARITY_TOOLS, PROPOSAL_VIDEO_TOOLS,
         PROPOSAL_FORMALIZATION_TOOLS),
        uploads=True, confirm_sensitive=True,
    ),
    'linkedin-personal': ConnectorSpec(
        'linkedin-personal', '1.1.0', (LINKEDIN_TOOLS,),
        compatibility=True, canonical_area='content',
    ),
    'operations': ConnectorSpec('operations', '2.1.0', (OPERATIONS_TOOLS,)),
    'building-with-us': ConnectorSpec(
        'building-with-us', '1.0.0', (BUILDING_WITH_US_TOOLS,), confirm_sensitive=True,
    ),
    'building-on-demand': ConnectorSpec(
        'building-on-demand', '1.0.0', (BUILDING_ON_DEMAND_TOOLS, BUILDING_ON_DEMAND_CONTRACT_TOOLS), confirm_sensitive=True,
    ),
    'partnership-program': ConnectorSpec(
        'partnership-program', '2.1.1', (PARTNERSHIP_PROGRAM_TOOLS,),
        uploads=True, confirm_sensitive=True,
    ),
    'additional-modules': ConnectorSpec(
        'additional-modules', '2.1.1', (ADDITIONAL_MODULE_TOOLS,),
        uploads=True, confirm_sensitive=True,
    ),
    'commercial': ConnectorSpec(
        'commercial', '4.0.0',
        (CLIENT_TOOLS, PROPOSAL_TOOLS, DIAGNOSTIC_TOOLS, COMMERCIAL_PARITY_TOOLS,
         PROPOSAL_VIDEO_TOOLS, PROPOSAL_FORMALIZATION_TOOLS,
         [tool for tool in ADDITIONAL_MODULE_TOOLS + PARTNERSHIP_PROGRAM_TOOLS
          if tool['name'] not in {existing['name'] for existing in COMMERCIAL_PARITY_TOOLS}]),
        uploads=True, confirm_sensitive=True,
    ),
    'projects': ConnectorSpec(
        'projects', '3.0.0', (PROJECT_TOOLS,), uploads=True,
    ),
    'content': ConnectorSpec(
        'content', '2.1.1',
        (BLOG_TOOLS, LINKEDIN_TOOLS, CONTENT_PARITY_TOOLS, LINKTREE_TEMPLATE_TOOLS),
        uploads=True, confirm_sensitive=True,
    ),
    'accounting-ledger': ConnectorSpec(
        'accounting-ledger', '2.4.1', (accounting_area('ledger'), LEDGER_PARITY_TOOLS, EXPECTED_INCOME_TOOLS),
        confirm_sensitive=True, notes=(ACCOUNTING_NOTE,),
    ),
    'accounting-billing': ConnectorSpec(
        'accounting-billing', '2.1.1',
        (accounting_area('billing'), BILLING_PARITY_TOOLS, PLATFORM_BILLING_TOOLS),
        confirm_sensitive=True,
    ),
    'accounting-cards': ConnectorSpec(
        'accounting-cards', '2.1.1', (accounting_area('cards'), CARD_PARITY_TOOLS),
        uploads=True, confirm_sensitive=True,
    ),
}


# Preserve pre-consolidation catalogs for existing scoped credentials.
from content.mcp.consolidation import build_catalogs  # noqa: E402

CONNECTORS, TOOLS_BY_SLUG, LEGACY_TOOLS_BY_SLUG = build_catalogs(
    SOURCE_CONNECTORS, replace, build_common_tools,
)


def tools_for_credential(slug, credential):
    if credential is not None and getattr(credential, 'catalog', '') == 'legacy':
        return LEGACY_TOOLS_BY_SLUG[slug]
    from content.mcp.module_catalog import FINANCIAL_PROJECT_TOOLS

    public = TOOLS_BY_SLUG[slug]
    if credential is not None and credential.connector.aliases_retired_at:
        return public
    names = {tool['name'] for tool in public}
    aliases = [
        {**tool, '_hidden': True}
        for tool in LEGACY_TOOLS_BY_SLUG[slug]
        if tool['name'] not in names
        and not (slug == 'projects' and tool['name'] in FINANCIAL_PROJECT_TOOLS)
    ]
    return [*public, *aliases]
