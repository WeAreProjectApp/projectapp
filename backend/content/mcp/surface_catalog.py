"""Reviewed module assignments and non-delegable UI surfaces for PA-221.

Assignments identify the responsible module, never certify functional coverage.
The matrix retains the UI feature descriptions for the functional reviewer.
"""

EXEMPTIONS = {
    '/panel/login': 'identity-bootstrap',
    '/panel/admins': 'privilege-administration',
    '/panel/mcps': 'credential-bootstrap',
    '/panel/views': 'reference-only',
    '/panel/styleguide': 'reference-only',
    '/platform/login': 'identity-bootstrap',
    '/platform/admin-login': 'identity-bootstrap',
    '/platform/verify': 'identity-bootstrap',
    '/platform/forgot-password': 'identity-bootstrap',
    '/platform/reset-password': 'identity-bootstrap',
    '/platform/verify-code': 'identity-bootstrap',
    '/platform/complete-profile': 'identity-bound-profile',
    '/platform/profile': 'identity-bound-profile',
    '/platform/unavailable': 'reference-only',
    '/platform/notifications': 'identity-bound-private-inbox',
}
EXEMPTION_REASONS = {
    'identity-bootstrap': 'Autenticación y recuperación de la identidad interactiva; el actor técnico no suplanta una sesión.',
    'privilege-administration': 'Asignación de privilegios humanos desde sesión administrativa; no se delega al propio acceso técnico.',
    'credential-bootstrap': 'Crear o ampliar el acceso del propio MCP requiere sesión de superusuario y CSRF en el Panel.',
    'reference-only': 'Referencia de navegación o diseño sin una operación de datos de negocio que delegar.',
    'identity-bound-profile': 'Perfil propio vinculado a la identidad JWT; no equivale al cliente gestionado en Comercial.',
    'identity-bound-private-inbox': 'Bandeja privada que filtra Notification.user=request.user; no se amplía mediante user_id.',
    'redirect': 'Redirección de navegación; las operaciones se inventarían en la vista de destino.',
}

# Reviewed feature-to-resource candidates. A new feature without a decision is a
# gap; belonging to the same connector does not make arbitrary tools equivalent.
FEATURE_TOOL_PATTERNS = {
    'panel-procurement-workspace': ('procurement',),
    'panel-command-center': ('get_operations_dashboard',),
    'panel-additional-modules': ('additional_module',),
    'panel-financing': ('partnership', 'financing'),
    'panel-requirement-calculator': ('calculator',),
    'panel-consulting': ('consulting',),
    'panel-building-with-us': ('building_with_us',),
    'panel-building-on-demand': ('building_on_demand',),
    'panel-proposals': ('proposal',),
    'panel-commercial-settings': ('default', 'email', 'template', 'settings'),
    'panel-clients-offers': ('client',),
    'panel-editorial-content': ('blog', 'post', 'connection_status'),
    'panel-portfolio-content': ('portfolio',),
    'panel-shareable-resources': ('qr_card', 'linktree'),
    'panel-hour-packages': ('hour_package',),
    'panel-documents': ('document', 'folder', 'tag', 'note'),
    'panel-client-threads': ('thread', 'message', 'communication_folder', 'draft'),
    'panel-secure-links': ('secure_link',),
    'panel-email-center': ('email',),
    'panel-diagnostics': ('diagnostic',),
    'panel-team-tasks': ('task',),
    'panel-account-access': ('list_accesses', 'get_access', 'create_client_access', 'change_access'),
    'panel-project-portfolio': ('project',),
    'panel-project-ideas': ('idea',),
    'panel-project-lifecycle': ('project_state',),
    'panel-platform-help': ('platform_help', 'guided_tour', 'tour_progress'),
    'panel-platform-ai': ('platform_ai',),
    'panel-monitoring': ('monitoring',),
    'panel-project-hosting-control': ('hosting_control',),
    'panel-requirement-packages': ('package',),
    'panel-platform-features': ('platform_feature',),
    'platform-requirement-packages': ('package',),
    'panel-financial-flow': ('income', 'expense', 'accounting_dashboard', 'accounting_stats'),
    'panel-service-revenue': ('hosting', 'collection_account', 'income', 'recurring', 'ads'),
    'panel-cash-credit': ('pocket', 'card', 'statement', 'transaction', 'recurring', 'partner', 'split'),
    'panel-billing-context': ('hosting', 'collection_account', 'billing'),
    'panel-financial-governance': ('accounting_settings', 'change_logs', 'recipient'),
    'panel-data-integrity': ('integrity',),
    'platform-client-secure-links': ('secure_link',),
    'platform-project-payments': ('income', 'hosting', 'billing'),
    'platform-collection-accounts': ('collection_account',),
    'platform-document-portal': ('document',),
    'platform-project-portfolio': ('project',),
    'platform-project-board': ('delivery', 'project_resource'),
    'platform-bug-follow-up': ('issue', 'bug_report'),
    'platform-change-requests': ('issue', 'change_request'),
    'platform-data-model': ('project_data_model',),
    'platform-deliverable-library': ('project_resource',),
    'platform-client-administration': ('client',),
    'platform-project-ideas': ('idea',),
    'platform-project-access': ('project_client_access',),
}


def feature_tools(feature_id, names):
    patterns = FEATURE_TOOL_PATTERNS.get(feature_id, ())
    return sorted(name for name in names if any(pattern in name for pattern in patterns))

# Specific prefixes before general prefixes. Shared Platform views deliberately
# retain the module owning the business operation, not a new all-powerful MCP.
OWNERS = (
    ('/panel/procurement', 'procurement'), ('/panel/data-integrity', 'data-integrity'),
    ('/panel/accounting', 'accounting'), ('/panel/monitoring', 'operations'),
    ('/panel/requirement-packages', 'projects'),
    ('/panel/requirement-calculator', 'commercial'), ('/panel/consulting', 'commercial'),
    ('/panel/clients', 'commercial'), ('/panel/proposals', 'commercial'), ('/panel/defaults', 'commercial'),
    ('/panel/diagnostics', 'commercial'), ('/panel/partnership-program', 'programs'),
    ('/panel/financing', 'programs'), ('/panel/building-with-us', 'programs'), ('/panel/cells', 'programs'),
    ('/panel/hour-packages', 'offerings'), ('/panel/additional-modules', 'offerings'),
    ('/panel/documents', 'documents'), ('/panel/communications', 'communications'),
    ('/panel/secure-links', 'communications'), ('/panel/emails', 'communications'),
    ('/panel/blog', 'content'), ('/panel/linkedin', 'content'), ('/panel/portfolio', 'content'),
    ('/panel/qr-cards', 'content'), ('/panel/linktrees', 'content'), ('/panel/tasks', 'tasks'),
    ('/panel/projects', 'projects'), ('/panel/platform', 'projects'), ('/panel/access', 'projects'),
    ('/platform/clients', 'commercial'), ('/platform/documents', 'documents'),
    ('/platform/collection-accounts', 'accounting'), ('/platform/payments', 'accounting'),
    ('/platform/projects/:id/collection-accounts', 'accounting'),
    ('/platform/projects/:id/payments', 'accounting'),
    ('/platform/projects/:id/secure-links', 'communications'),
    ('/platform/projects', 'projects'), ('/platform/board', 'projects'),
    ('/platform/dashboard', 'projects'), ('/platform/bugs', 'projects'),
    ('/platform/changes', 'projects'), ('/platform/deliverables', 'projects'),
    ('/platform/access', 'projects'),
)


def assignment(surface):
    key = EXEMPTIONS.get(surface['id'])
    if surface['view_type'] == 'redirect':
        key = 'redirect'
    if key:
        return {'result': 'exempt', 'exemption': key, 'reason': EXEMPTION_REASONS[key]}
    owner = {'/panel': 'operations'}.get(surface['id']) or next((owner for prefix, owner in OWNERS
                  if surface['id'] == prefix or surface['id'].startswith(prefix + '/')), None)
    return {'connector': owner, 'result': 'mapped_unverified' if owner else 'gap'}
