"""Closed diagnostic catalogs; business messages never become audit content."""

import re

# These are identifiers from the MCP/domain contracts, not patterns that could
# admit a caller's arbitrary text. Owning modules explicitly register new codes.
_MCP_DOMAIN_CODES = frozenset('''
    ATTACHMENT_CHANGED CONFIRMATION_EXPIRED CONFLICT EXPIRED_PREPARATION
    FORBIDDEN INTERNAL_ERROR INVALID_TEMPLATE NOT_EDITABLE NOT_FOUND
    PREPARATION_CONSUMED STALE_VERSION TOOL_ERROR VALIDATION_ERROR
    amendment_contract amendment_unsigned approved_frozen attachment_duplicate
    attachment_integrity attachment_too_large attachment_unavailable
    billing_conflict citation_limit citation_message citation_normative
    citation_quote citation_source client_already_archived client_email_required
    client_evidence_required client_not_archived content_unavailable
    confirmation_required income_locked not_expected_income
    context_contract_required context_destination context_mode context_owner
    context_required context_retained context_scope context_stage_required
    context_too_large context_unpublished contract_unsigned decision_reason_required
    delivery_client_history_frozen delivery_conflict delivery_integrity
    document_context document_not_published document_unpublished duplicate_key
    duplicate_requirement empty_stage folder_cycle guide_incomplete guide_role_source
    human_review_required immutable_ownership import_drafts_only import_fields
    import_schema invalid invalid_language invalid_link_state invalid_reactivation
    invalid_replacement invalid_request_id invalid_send_state invalid_validity
    issue_contract_context issue_convert_contract issue_convert_state
    issue_document_context issue_empty_response issue_kind issue_message_required
    issue_pdf_too_large issue_reopen_internal issue_reopen_state issue_reply_payload
    issue_source_invalid issue_source_required link_not_found not_found pdf_invalid
    pdf_too_large pdf_unavailable project_client_access_unavailable
    project_client_mismatch project_collaboration_conflict projects_changed
    published_frozen reply_destination_archived reply_destination_snapshot
    reply_provider_unavailable reply_transaction_required request_id_conflict
    request_id_required retained_project retained_source review_round_closed scope_indeterminate
    secure_links_unavailable signed_source_frozen source_contract source_duplicate
    staff_only stage_not_approved stage_not_client_visible suspended_state_missing
    target_unpublished unknown_field version_conflict
'''.split())
_MCP_ERROR_CODES = _MCP_DOMAIN_CODES | {
    code.upper() for code in _MCP_DOMAIN_CODES
}
_REGISTERED_MCP_DOMAIN_CODES = set()
_MCP_DOMAIN_CODE_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_]{1,63}$')
_JSONRPC_ERROR_CODES = frozenset({
    -32600, -32601, -32602, -32603, -32020, -32022,
})


def register_mcp_domain_codes(*codes):
    """Extend the diagnostic catalog with identifiers owned by domain modules."""
    for code in codes:
        if not isinstance(code, str) or not _MCP_DOMAIN_CODE_PATTERN.fullmatch(code):
            raise ValueError('MCP domain codes must be 2–64 character identifiers.')
    _REGISTERED_MCP_DOMAIN_CODES.update(codes)
    _REGISTERED_MCP_DOMAIN_CODES.update(code.upper() for code in codes)


def safe_mcp_error_code(value):
    """Keep recognized identifiers while discarding arbitrary error content."""
    if type(value) is int and value in _JSONRPC_ERROR_CODES:
        return str(value)
    if isinstance(value, str) and (
        value in _MCP_ERROR_CODES or value in _REGISTERED_MCP_DOMAIN_CODES
    ):
        return value
    return 'TOOL_ERROR'


EMAIL_DIAGNOSTIC_CATALOG = {
    'attachment_unavailable': 'No se pudo leer el adjunto conservado para enviarlo.',
    'attachment_integrity': 'El adjunto conservado no coincide con su evidencia.',
    'snapshot_capture_failed': 'No se pudo archivar el correo exacto antes de enviarlo.',
    'email_transport_failed': 'No se pudo completar el envío de correo.',
    'email_backend_rejected': 'El backend de correo no aceptó el envío.',
    'email_copy_failed': 'No se pudo completar la copia del correo.',
    'email_copy_backend_rejected': 'El backend de correo no aceptó la copia.',
    'email_copy_configuration_failed': 'No se pudo resolver la configuración de copias.',
    'email_copy_already_primary': 'Ya era destinatario del envío principal.',
    'email_audit_incomplete': 'Correo aceptado; no se completó el registro posterior.',
}
_EMAIL_DIAGNOSTIC_MESSAGES = frozenset(EMAIL_DIAGNOSTIC_CATALOG.values())


def email_diagnostic_message(code):
    """Project a known failure category to fixed, readable technical text."""
    return EMAIL_DIAGNOSTIC_CATALOG.get(
        code, EMAIL_DIAGNOSTIC_CATALOG['email_transport_failed'],
    )


def safe_email_diagnostic(value, *, default_code='email_transport_failed'):
    """Close every diagnostic sink, including reads of older stored errors."""
    if value is None or (isinstance(value, str) and value == ''):
        return ''
    if isinstance(value, str) and value in _EMAIL_DIAGNOSTIC_MESSAGES:
        return value
    return email_diagnostic_message(default_code)


def email_exception_diagnostic(exc, *, default_code='email_transport_failed'):
    """Classify domain failures without formatting their message or details."""
    detail = getattr(exc, 'detail', None)
    code = detail.get('code') if isinstance(detail, dict) else None
    if isinstance(code, (list, tuple)):
        code = code[0] if code else None
    if isinstance(code, str) and code in {
        'attachment_unavailable', 'attachment_integrity',
    }:
        return email_diagnostic_message(code)
    # The snapshot module imports the gateway. Selecting its fixed category by
    # class name keeps this helper pure and avoids that import cycle.
    if type(exc).__name__ == 'EmailSnapshotCaptureError':
        return email_diagnostic_message('snapshot_capture_failed')
    return email_diagnostic_message(default_code)
