"""Translate an existing consumer's grants without widening its authority."""
from content.mcp.connectors import LEGACY_TOOLS_BY_SLUG, TOOLS_BY_SLUG
from content.mcp.module_catalog import CANONICAL_FOR, FINANCIAL_PROJECT_TOOLS, INFRASTRUCTURE_TOOLS, MODULE_CONNECTORS, canonical_name
from content.mcp.protocol import ToolError

INCOME_REPLACEMENTS = {
    'list_income': 'list_incomes', 'list_expected_incomes': 'list_incomes',
    'get_expected_income': 'get_income', 'get_income_detail': 'get_income',
    'create_expected_income': 'create_income', 'update_expected_income': 'update_income',
    'duplicate_expected_income': 'duplicate_income',
    'launch_proposal_to_platform': 'review_proposal_approval',
}


def translated_grants(source, target_slug):
    if target_slug not in MODULE_CONNECTORS:
        raise ToolError('El destino debe ser un conector canónico.', code='CONFLICT')
    legacy = LEGACY_TOOLS_BY_SLUG[source.connector.slug]
    names = {tool['name'] for tool in legacy if source.allows(tool['name'])}
    translated = set()
    for name in names:
        if name in INFRASTRUCTURE_TOOLS:
            continue
        owner = 'accounting' if name in FINANCIAL_PROJECT_TOOLS else CANONICAL_FOR[source.connector.slug]
        if owner == target_slug:
            translated.add(INCOME_REPLACEMENTS.get(name, canonical_name(name, owner)))
    available = {tool['name'] for tool in TOOLS_BY_SLUG[target_slug]}
    missing = translated - available
    if missing:
        raise ToolError('Falta un reemplazo equivalente para la credencial.', code='CONFLICT')
    # A specialized expected-income grant must not gain access to liquid/lost.
    general = {'list_income', 'get_income', 'get_income_detail', 'create_income', 'update_income', 'duplicate_income'}
    income_specific = any('expected_income' in name for name in names)
    kinds = ['expected'] if income_specific and not (names & general) else list(source.income_kinds)
    if not translated:
        raise ToolError('La credencial no tiene funciones de negocio en ese destino.', code='FORBIDDEN')
    return sorted(translated), kinds


def equivalent_replacement(source, replacement):
    if source.actor_id != replacement.actor_id:
        return False
    if source.expires_at and (replacement.expires_at is None or replacement.expires_at > source.expires_at):
        return False
    grants, kinds = translated_grants(source, replacement.connector.slug)
    actual = {tool['name'] for tool in TOOLS_BY_SLUG[replacement.connector.slug]
              if tool['name'] not in INFRASTRUCTURE_TOOLS and replacement.allows(tool['name'])}
    return actual == set(grants) and set(replacement.income_kinds) == set(kinds)
