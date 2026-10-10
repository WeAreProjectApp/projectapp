"""Test-only schema policy for the documents/projects explicitness sweep.

The structural rules mirror PR #503's ``schema_policy.schema_problems``.
This sweep additionally forbids published root data/query envelopes and keeps
auditing declared children of marked open objects. Backlogs are snapshots,
never computed at import time: improvements must remove entries.
"""

import ast
from pathlib import Path

OPEN_REASON_KEY = 'x-mcp-open-reason'
COMBINATORS = ('anyOf', 'oneOf', 'allOf')
CONNECTORS = ('documents', 'projects')


def _nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def undescribed_root_properties(tool):
    properties = tool.get('input_schema', {}).get('properties', {})
    if not isinstance(properties, dict):
        return []
    return sorted(
        name for name, schema in properties.items()
        if not isinstance(schema, dict)
        or not _nonempty_text(schema.get('description'))
    )


def _typed(schema):
    if not isinstance(schema, dict):
        return False
    if schema.get('type') or 'enum' in schema or 'const' in schema:
        return True
    return any(
        isinstance(schema.get(key), list) and bool(schema[key])
        and all(_typed(branch) for branch in schema[key])
        for key in COMBINATORS
    )


def _pointer(path, key):
    escaped = str(key).replace('~', '~0').replace('/', '~1')
    return f'{path}/{escaped}'


def schema_problems(tool, *, generic_ok=False, undescribed_ok=False):
    """Report policy violations as escaped JSON pointers into input_schema."""
    problems = []
    name = tool.get('name', '<unnamed>')
    root = tool.get('input_schema')

    def report(path, message):
        problems.append(f'{name}:{path or "/"}: {message}')

    if not isinstance(root, dict):
        report('', 'root must be an object schema with a properties dict')
        return problems
    if root.get('type') != 'object':
        report('/type', 'root type must be object')
    if not isinstance(root.get('properties'), dict):
        report('/properties', 'root properties must be a dict')
    if root.get('additionalProperties') is not False and not generic_ok:
        report('/additionalProperties', 'root must set additionalProperties to false')

    def walk(node, path, parent_properties=None, needs_type=False):
        if not isinstance(node, dict):
            report(path, 'node must be a schema dict')
            return
        if needs_type and not _typed(node):
            report(path, 'property or items must declare a type, enum, const or typed combinator')

        node_type = node.get('type')
        object_typed = node_type == 'object' or (
            isinstance(node_type, list) and 'object' in node_type
        )
        additional = node.get('additionalProperties')
        if OPEN_REASON_KEY in node:
            if not object_typed or additional is False:
                report(path, 'open marker must belong to an open object')
            if not _nonempty_text(node.get('description')):
                report(_pointer(path, 'description'), 'open object needs a description')
            if not _nonempty_text(node[OPEN_REASON_KEY]):
                report(_pointer(path, OPEN_REASON_KEY), 'open object needs a non-empty reason')

        # An openness reason permits a free-form object without properties; it
        # cannot waive closure or typing of declared children (P2's checklist).
        properties = node.get('properties')
        if object_typed:
            if 'properties' in node:
                if additional is not False:
                    report(_pointer(path, 'additionalProperties'), 'object with properties must be closed')
            elif not isinstance(additional, dict) and OPEN_REASON_KEY not in node:
                report(path, 'object without properties needs a typed map or an open reason')
        if 'properties' in node and not isinstance(properties, dict):
            report(_pointer(path, 'properties'), 'properties must be a dict')

        constraint = bool(node) and set(node) <= {'required', 'not'}
        available = parent_properties if constraint else properties
        available = available if isinstance(available, dict) else {}
        required = node.get('required', [])
        if not isinstance(required, list):
            report(_pointer(path, 'required'), 'required must be a list')
        else:
            for index, required_name in enumerate(required):
                if not isinstance(required_name, str) or required_name not in available:
                    report(_pointer(_pointer(path, 'required'), index), 'required name is absent from properties')

        if isinstance(properties, dict):
            for key, child in properties.items():
                walk(child, _pointer(_pointer(path, 'properties'), key), needs_type=True)
        if 'items' in node:
            items = node['items']
            if isinstance(items, list):
                for index, child in enumerate(items):
                    walk(child, _pointer(_pointer(path, 'items'), index), needs_type=True)
            else:
                walk(items, _pointer(path, 'items'), needs_type=True)
        if isinstance(additional, dict):
            walk(additional, _pointer(path, 'additionalProperties'), needs_type=True)
        for key in COMBINATORS:
            if key not in node:
                continue
            branches = node[key]
            if not isinstance(branches, list):
                report(_pointer(path, key), 'combinator branches must be a list')
                continue
            for index, branch in enumerate(branches):
                scope = properties if isinstance(properties, dict) else parent_properties
                walk(branch, _pointer(_pointer(path, key), index), scope)
        if 'not' in node:
            walk(node['not'], _pointer(path, 'not'), available)

    if not generic_ok:
        for key in COMBINATORS:
            if key in root:
                report(_pointer('', key), 'root combinators are not supported by MCP clients')
        walk(root, '')
    if not undescribed_ok:
        for key in undescribed_root_properties(tool):
            report(_pointer(_pointer('', 'properties'), key), 'root property needs a description')
    properties = root.get('properties', {})
    if isinstance(properties, dict):
        for alias in sorted({'data', 'query'} & properties.keys()):
            report(_pointer('/properties', alias), 'published root data/query aliases are forbidden')
    return problems


# Wave 2 closed every in-scope contract and documented deliberate Panel-only reads.
INITIAL_OPEN_SCHEMA_COUNT = 0
INITIAL_DRIFT_COUNT = 0
# Wave 3 rejects legacy envelopes in every in-scope bridge.
INITIAL_ALIAS_COUNT = 0

OPEN_SCHEMA_BACKLOG = frozenset()

ALIAS_BACKLOG = frozenset()

DRIFT_BACKLOG = frozenset()

EXCLUDED_TOOLS = {
    ('documents', 'cancel_action'): 'owned by PR #503',
    ('documents', 'confirm_action'): 'owned by PR #503',
    ('documents', 'describe_capabilities'): 'owned by PR #503',
    ('projects', 'cancel_action'): 'owned by PR #503',
    ('projects', 'compare_project_history'): 'owned by PR #503',
    ('projects', 'confirm_action'): 'owned by PR #503',
    ('projects', 'describe_capabilities'): 'owned by PR #503',
    ('projects', 'get_project_history_version'): 'owned by PR #503',
    ('projects', 'list_project_history'): 'owned by PR #503',
}

# Evidence names a scenario, not just a file containing unrelated preview and
# apply tests. The scanner follows its same-file helpers without importing tests.
PARITY_PAIRS = {
    ('documents', 'preview_move'): (
        'content/tests/views/test_ownership_parity.py', 'test_mcp_move_matches_preview',
        ('move_documents', 'update_folder', 'update_document'),
    ),
    ('documents', 'preview_folder_migration'): (
        'content/tests/views/test_mcp_folder_migration.py', 'test_real_projectapp_migration_preserves_contracts',
        ('apply_folder_migration', 'confirm_action'),
    ),
    ('documents', 'preview_folder_migration_undo'): (
        'content/tests/views/test_mcp_folder_migration.py', 'test_real_projectapp_migration_preserves_contracts',
        ('undo_folder_migration', 'confirm_action'),
    ),
    ('projects', 'preview_project_client_change'): (
        'content/tests/views/test_mcp_project_client_change.py', 'test_confirmed_transfer_matches_the_selected_plan',
        ('change_project_client', 'confirm_action'),
    ),
    ('projects', 'preview_hosting_subscription_change'): (
        'content/tests/views/test_mcp_hosting_subscription.py', 'test_confirmed_cancel_preserves_paid_history',
        ('change_hosting_subscription', 'confirm_action'),
    ),
    ('projects', 'preview_delivery_notification_retry'): (
        'content/tests/views/test_mcp_delivery_notifications.py', 'test_notice_confirmation_records_the_credential_owner',
        ('retry_delivery_notification_event', 'confirm_action'),
    ),
    ('projects', 'preview_retained_operation_undo'): (
        'content/tests/services/test_retained_adoption.py', 'test_mcp_undo_needs_the_preview_backed_confirmation',
        ('undo_retained_operation', 'confirm_action'),
    ),
    ('projects', 'preview_retained_container_cleanup'): (
        'content/tests/services/test_retained_adoption.py', 'test_mcp_cleanup_deletes_only_after_a_preview_backed_confirmation',
        ('delete_empty_retained_containers', 'confirm_action'),
    ),
    ('projects', 'preview_issue_reply'): (
        'content/tests/views/test_mcp_issues.py', 'test_mcp_reply_pipeline_rejects_unreviewed_publish_without_writing',
        ('evaluate_issue_report',),
    ),
}

UNPAIRED_PREVIEWS = {
    ('documents', 'preview_folder_client_change'):
        'Preview and confirmed portal-policy coverage are separate scenarios; no single MCP preview/apply pair.',
    ('projects', 'preview_project_delete'):
        'Dependency preview and confirmed deletion have separate tests; no explicit preview/apply scenario.',
    ('projects', 'preview_project_state_transition'):
        'No MCP scenario pairs the financial preview with apply_project_state_transition.',
    ('projects', 'preview_delivery_reply'):
        'Citation preview is tested separately from publishing the reviewed reply through add_delivery_message.',
    ('projects', 'preview_delivery_import'):
        'Read-only preview and confirmed import are separate tests; no single preview/apply scenario.',
    ('projects', 'preview_project_client_access'):
        'Read-only redacted projection of current access; it has no corresponding apply tool.',
    ('projects', 'preview_project_hosting_reconciliation'):
        'Accounting-billing tests exercise preview and reconciliation separately; projects has no paired scenario.',
    ('projects', 'preview_hosting_evidence'):
        'Registry coverage does not exercise preview_hosting_evidence paired with reconcile_hosting_evidence.',
    ('projects', 'preview_project_data_model'):
        'Model preview and confirmed replacement are separate tests; no single preview/import scenario.',
}


def parity_evidence_problems(backend_root=None):
    """Reject stale pair entries if a scenario or either operation disappears."""
    backend_root = backend_root or Path(__file__).resolve().parents[2]
    problems = {}
    for key, (filename, scenario, apply_tools) in PARITY_PAIRS.items():
        path = backend_root / filename
        if not path.is_file():
            problems[key] = f'Missing parity file: {filename}'
            continue
        tree = ast.parse(path.read_text())
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        if scenario not in functions:
            problems[key] = f'Missing parity scenario: {scenario}'
            continue
        reached, pending, operations = set(), [scenario], set()
        while pending:
            name = pending.pop()
            if name in reached:
                continue
            reached.add(name)
            for node in ast.walk(functions[name]):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id in functions:
                    pending.append(node.func.id)
                # Parameterized tool names in decorators also count as calls.
                for argument in (*node.args, *(kw.value for kw in node.keywords)):
                    operations.update(child.value for child in ast.walk(argument)
                                      if isinstance(child, ast.Constant) and isinstance(child.value, str))
        missing = {key[1], *apply_tools} - operations
        if missing:
            problems[key] = f'Scenario no longer references operations: {sorted(missing)}'
    return problems
