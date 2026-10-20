"""Module ownership and the finite compatibility policy for MCP connectors."""

MODULE_CONNECTORS = {
    'operations': ('overview', ('operations',)),
    'commercial': ('commercial', (
        'commercial', 'clients', 'proposals', 'diagnostics', 'additional-modules',
        'partnership-program', 'building-with-us', 'building-on-demand',
    )),
    'projects': ('platform', ('projects',)),
    'documents': ('documents', ('documents',)),
    'communications': ('communications', ('communications',)),
    'content': ('site', ('content', 'blog', 'linkedin-personal')),
    'accounting': ('accounting', (
        'accounting', 'accounting-ledger', 'accounting-billing', 'accounting-cards',
    )),
    'tasks': ('tasks', ('tasks',)),
}
CANONICAL_FOR = {
    source: canonical
    for canonical, (_, sources) in MODULE_CONNECTORS.items() for source in sources
}
INFRASTRUCTURE_TOOLS = frozenset({
    'describe_capabilities', 'confirm_action', 'cancel_action',
    'begin_upload', 'upload_asset_chunk', 'complete_upload', 'abort_upload',
})
FINANCIAL_PROJECT_TOOLS = frozenset({
    'get_project_billing_options', 'link_project_billing_contract',
    'get_project_hosting', 'get_project_hosting_inventory',
    'get_collection_account_context', 'associate_collection_account_context',
    'preview_project_hosting_reconciliation', 'reconcile_project_hosting',
    'preview_hosting_evidence', 'reconcile_hosting_evidence',
    'preview_hosting_subscription_change', 'change_hosting_subscription',
})
ACCOUNTING_REPLACEMENTS = {
    'get_settings': 'get_accounting_settings',
    'get_accounting_settings_full': 'get_accounting_settings',
    'update_settings': 'update_accounting_settings',
    'update_accounting_settings_full': 'update_accounting_settings',
    'list_change_logs': 'list_accounting_change_logs',
    'get_dashboard': 'get_accounting_dashboard',
}
ACCOUNTING_SUPERSEDED = frozenset({'get_settings', 'update_settings', 'list_change_logs'})


def canonical_name(name, slug):
    """Qualified resources prevent ambiguous names across module catalogs."""
    if slug == 'accounting' and name in ACCOUNTING_REPLACEMENTS:
        return ACCOUNTING_REPLACEMENTS[name]
    if slug == 'documents' and name == 'list_folders':
        return 'get_document_folder_index'
    if name in {'list_folders', 'create_folder', 'update_folder', 'delete_folder'}:
        resource = 'communication' if slug == 'communications' else 'document'
        return name.replace('_folder', f'_{resource}_folder', 1)
    plural = {
        'income': 'incomes', 'expense': 'expenses', 'hosting': 'hostings',
        'pocket': 'pocket_movements', 'recurring': 'recurring_payments',
        'ads': 'ads_records', 'card_snapshot': 'card_snapshots',
        'notification_recipient': 'notification_recipients',
    }
    if name.startswith('list_') and name[5:] in plural:
        return f'list_{plural[name[5:]]}'
    return name


def catalog_problems(connectors, tools_by_slug):
    """Fail closed on extra modules, duplicate names or duplicate operations."""
    problems, modules, names, operations = [], {}, {}, {}
    for slug, spec in connectors.items():
        if spec.compatibility:
            if slug not in CANONICAL_FOR or CANONICAL_FOR.get(slug) != spec.canonical_area:
                problems.append(f'{slug}: replacement missing')
            continue
        module = spec.module_id
        if not module or module in modules:
            problems.append(f'{slug}: duplicate or missing module {module}')
        modules[module] = slug
        for tool in tools_by_slug[slug]:
            name = tool['name']
            if name in INFRASTRUCTURE_TOOLS:
                continue
            if name in names:
                problems.append(f'{name}: duplicate domain name in {names[name]} and {slug}')
            names[name] = slug
            operation = tool['operation_id']
            if operation in operations:
                problems.append(f'{name}: duplicate operation {operation} in {operations[operation]} and {slug}')
            operations[operation] = slug
    if set(modules) != {module for module, _ in MODULE_CONNECTORS.values()}:
        problems.append('canonical module set differs from module catalog')
    return problems
