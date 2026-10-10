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


# Initial ceilings stay fixed when the corresponding snapshots shrink.
INITIAL_OPEN_SCHEMA_COUNT = 231
INITIAL_ALIAS_COUNT = 18
INITIAL_DRIFT_COUNT = 3

OPEN_SCHEMA_BACKLOG = frozenset({
    ('documents', 'abort_upload'),
    ('documents', 'add_document_note'),
    ('documents', 'adopt_folder_as_project_root'),
    ('documents', 'append_document'),
    ('documents', 'apply_folder_migration'),
    ('documents', 'archive_document'),
    ('documents', 'archive_folder'),
    ('documents', 'begin_upload'),
    ('documents', 'browse_documents'),
    ('documents', 'cancel_action'),
    ('documents', 'change_folder_client'),
    ('documents', 'close_document_state'),
    ('documents', 'complete_upload'),
    ('documents', 'confirm_action'),
    ('documents', 'correct_document_state_opening'),
    ('documents', 'create_document'),
    ('documents', 'create_document_state'),
    ('documents', 'create_document_state_group'),
    ('documents', 'create_document_tag'),
    ('documents', 'create_document_thread'),
    ('documents', 'create_folder'),
    ('documents', 'delete_document'),
    ('documents', 'delete_document_notes'),
    ('documents', 'delete_document_tag'),
    ('documents', 'delete_folder'),
    ('documents', 'describe_capabilities'),
    ('documents', 'dissolve_document_thread'),
    ('documents', 'duplicate_document'),
    ('documents', 'finish_document_note'),
    ('documents', 'get_document_communication_usage'),
    ('documents', 'get_document_counts'),
    ('documents', 'get_document_email_usage'),
    ('documents', 'get_document_navigation'),
    ('documents', 'get_document_thread'),
    ('documents', 'get_folder_migration'),
    ('documents', 'get_project_folder_readiness'),
    ('documents', 'list_deleted_document_notes'),
    ('documents', 'list_document_folders'),
    ('documents', 'list_document_note_events'),
    ('documents', 'list_document_state_catalog'),
    ('documents', 'list_document_state_groups'),
    ('documents', 'list_document_state_history'),
    ('documents', 'list_document_states'),
    ('documents', 'list_document_tags'),
    ('documents', 'list_document_threads'),
    ('documents', 'list_documents'),
    ('documents', 'merge_document_state'),
    ('documents', 'move_documents'),
    ('documents', 'preview_folder_client_change'),
    ('documents', 'preview_folder_migration'),
    ('documents', 'preview_folder_migration_undo'),
    ('documents', 'preview_move'),
    ('documents', 'read_document'),
    ('documents', 'render_document_pdf'),
    ('documents', 'reorder_folders'),
    ('documents', 'restore_document_note'),
    ('documents', 'retire_document_state'),
    ('documents', 'set_document_state'),
    ('documents', 'suggest_document_states'),
    ('documents', 'unarchive_document'),
    ('documents', 'unarchive_folder'),
    ('documents', 'undo_folder_migration'),
    ('documents', 'update_document'),
    ('documents', 'update_document_note'),
    ('documents', 'update_document_state_catalog_item'),
    ('documents', 'update_document_state_group'),
    ('documents', 'update_document_tag'),
    ('documents', 'update_document_thread'),
    ('documents', 'update_folder'),
    ('documents', 'upload_asset_chunk'),
    ('projects', 'abort_upload'),
    ('projects', 'add_delivery_message'),
    ('projects', 'add_project_commercial_phase'),
    ('projects', 'apply_delivery_import'),
    ('projects', 'apply_project_state_transition'),
    ('projects', 'archive_issue_report'),
    ('projects', 'archive_project_idea'),
    ('projects', 'archive_project_resource'),
    ('projects', 'assign_project_unlinked_records'),
    ('projects', 'associate_collection_account_context'),
    ('projects', 'attest_external_delivery_signature'),
    ('projects', 'begin_upload'),
    ('projects', 'bulk_evaluate_issue_reports'),
    ('projects', 'cancel_action'),
    ('projects', 'change_hosting_subscription'),
    ('projects', 'change_project_client'),
    ('projects', 'comment_issue_report'),
    ('projects', 'complete_upload'),
    ('projects', 'confirm_action'),
    ('projects', 'convert_change_request'),
    ('projects', 'create_bug_report'),
    ('projects', 'create_change_request'),
    ('projects', 'create_delivery_amendment'),
    ('projects', 'create_delivery_contract'),
    ('projects', 'create_delivery_guide_prompt'),
    ('projects', 'create_delivery_phase'),
    ('projects', 'create_delivery_reply_prompt'),
    ('projects', 'create_delivery_requirement'),
    ('projects', 'create_delivery_scope'),
    ('projects', 'create_delivery_stage'),
    ('projects', 'create_project'),
    ('projects', 'create_project_idea'),
    ('projects', 'create_project_idea_collection'),
    ('projects', 'create_project_resource'),
    ('projects', 'create_project_resource_folder'),
    ('projects', 'create_project_state'),
    ('projects', 'create_project_state_group'),
    ('projects', 'delete_delivery_amendment'),
    ('projects', 'delete_delivery_contract'),
    ('projects', 'delete_delivery_phase'),
    ('projects', 'delete_delivery_requirement'),
    ('projects', 'delete_delivery_scope'),
    ('projects', 'delete_delivery_stage'),
    ('projects', 'delete_empty_retained_containers'),
    ('projects', 'delete_project'),
    ('projects', 'delete_project_brand_asset'),
    ('projects', 'delete_project_resource_folder'),
    ('projects', 'describe_capabilities'),
    ('projects', 'download_delivery_contract_pdf'),
    ('projects', 'download_delivery_contract_source'),
    ('projects', 'download_delivery_document_pdf'),
    ('projects', 'download_delivery_prompt_source'),
    ('projects', 'download_delivery_stage_closure_email_attachment'),
    ('projects', 'download_issue_attachment'),
    ('projects', 'download_issue_reply_source'),
    ('projects', 'download_project_brand_asset'),
    ('projects', 'download_project_resource_file'),
    ('projects', 'evaluate_issue_report'),
    ('projects', 'get_collection_account_context'),
    ('projects', 'get_delivery_amendment'),
    ('projects', 'get_delivery_authoring_contract'),
    ('projects', 'get_delivery_contract'),
    ('projects', 'get_delivery_document'),
    ('projects', 'get_delivery_notification_event'),
    ('projects', 'get_delivery_overview'),
    ('projects', 'get_delivery_phase'),
    ('projects', 'get_delivery_prompt_context'),
    ('projects', 'get_delivery_requirement'),
    ('projects', 'get_delivery_scope'),
    ('projects', 'get_delivery_stage'),
    ('projects', 'get_delivery_stage_closure_email'),
    ('projects', 'get_issue_context_options'),
    ('projects', 'get_issue_reply_context'),
    ('projects', 'get_issue_reply_options'),
    ('projects', 'get_issue_report'),
    ('projects', 'get_project'),
    ('projects', 'get_project_billing_options'),
    ('projects', 'get_project_brand'),
    ('projects', 'get_project_client_access_policy'),
    ('projects', 'get_project_data_model'),
    ('projects', 'get_project_data_model_template'),
    ('projects', 'get_project_hosting'),
    ('projects', 'get_project_hosting_inventory'),
    ('projects', 'get_project_idea'),
    ('projects', 'get_project_idea_collection'),
    ('projects', 'get_project_resource'),
    ('projects', 'import_project_data_model'),
    ('projects', 'link_delivery_document'),
    ('projects', 'link_project_billing_contract'),
    ('projects', 'list_delivery_approval_evidence'),
    ('projects', 'list_delivery_document_options'),
    ('projects', 'list_delivery_documents'),
    ('projects', 'list_delivery_notification_events'),
    ('projects', 'list_delivery_prompt_contexts'),
    ('projects', 'list_delivery_stage_closure_emails'),
    ('projects', 'list_issue_reports'),
    ('projects', 'list_project_client_access_events'),
    ('projects', 'list_project_commercial_phases'),
    ('projects', 'list_project_idea_collections'),
    ('projects', 'list_project_idea_revisions'),
    ('projects', 'list_project_ideas'),
    ('projects', 'list_project_resource_attachments'),
    ('projects', 'list_project_resource_client_files'),
    ('projects', 'list_project_resource_folders'),
    ('projects', 'list_project_resources'),
    ('projects', 'list_project_retention_contexts'),
    ('projects', 'list_project_state_groups'),
    ('projects', 'list_project_state_history'),
    ('projects', 'list_project_states'),
    ('projects', 'list_project_unlinked_records'),
    ('projects', 'list_projects'),
    ('projects', 'merge_project_state'),
    ('projects', 'prepare_delivery_stage_closure_email'),
    ('projects', 'prepare_delivery_stage_closure_email_resend'),
    ('projects', 'prepare_issue_reply'),
    ('projects', 'preview_delivery_import'),
    ('projects', 'preview_delivery_notification_retry'),
    ('projects', 'preview_delivery_reply'),
    ('projects', 'preview_hosting_evidence'),
    ('projects', 'preview_hosting_subscription_change'),
    ('projects', 'preview_issue_reply'),
    ('projects', 'preview_project_client_access'),
    ('projects', 'preview_project_client_change'),
    ('projects', 'preview_project_data_model'),
    ('projects', 'preview_project_delete'),
    ('projects', 'preview_project_hosting_reconciliation'),
    ('projects', 'preview_project_state_transition'),
    ('projects', 'preview_retained_container_cleanup'),
    ('projects', 'preview_retained_operation_undo'),
    ('projects', 'publish_delivery_stage'),
    ('projects', 'reconcile_hosting_evidence'),
    ('projects', 'reconcile_project_hosting'),
    ('projects', 'record_external_delivery_approval'),
    ('projects', 'remove_project_commercial_phase'),
    ('projects', 'reorder_project_commercial_phases'),
    ('projects', 'restore_project_idea'),
    ('projects', 'restore_project_resource'),
    ('projects', 'retire_project_state'),
    ('projects', 'retry_delivery_notification_event'),
    ('projects', 'send_delivery_stage_closure_email'),
    ('projects', 'set_project_client_access_policy'),
    ('projects', 'suggest_project_states'),
    ('projects', 'undo_retained_operation'),
    ('projects', 'unlink_delivery_document'),
    ('projects', 'update_delivery_amendment'),
    ('projects', 'update_delivery_contract'),
    ('projects', 'update_delivery_phase'),
    ('projects', 'update_delivery_requirement'),
    ('projects', 'update_delivery_scope'),
    ('projects', 'update_delivery_stage'),
    ('projects', 'update_project'),
    ('projects', 'update_project_commercial_phase'),
    ('projects', 'update_project_idea'),
    ('projects', 'update_project_resource'),
    ('projects', 'update_project_resource_folder'),
    ('projects', 'update_project_state'),
    ('projects', 'upload_asset_chunk'),
    ('projects', 'upload_project_brand_asset'),
    ('projects', 'upload_project_resource_attachment'),
    ('projects', 'upload_project_resource_client_file'),
    ('projects', 'upload_project_resource_version'),
})

ALIAS_BACKLOG = frozenset({
    ('documents', 'change_folder_client'),
    ('documents', 'move_documents'),
    ('documents', 'preview_folder_client_change'),
    ('documents', 'update_folder'),
    ('projects', 'add_project_commercial_phase'),
    ('projects', 'archive_project_idea'),
    ('projects', 'change_project_client'),
    ('projects', 'create_project_idea'),
    ('projects', 'create_project_idea_collection'),
    ('projects', 'delete_empty_retained_containers'),
    ('projects', 'preview_project_client_change'),
    ('projects', 'reorder_project_commercial_phases'),
    ('projects', 'restore_project_idea'),
    ('projects', 'set_project_client_access_policy'),
    ('projects', 'undo_retained_operation'),
    ('projects', 'update_project_commercial_phase'),
    ('projects', 'update_project_idea'),
    ('projects', 'upload_project_brand_asset'),
})

DRIFT_BACKLOG = frozenset({
    ('projects', 'change_project_client', 'data', 'communication_thread_ids'),
    ('projects', 'change_project_client', 'data', 'hosting_ids'),
    ('projects', 'change_project_client', 'data', 'income_ids'),
})

EXCLUDED_TOOLS = {
    ('projects', 'list_project_history'): 'owned by PR #503',
    ('projects', 'get_project_history_version'): 'owned by PR #503',
    ('projects', 'compare_project_history'): 'owned by PR #503',
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
