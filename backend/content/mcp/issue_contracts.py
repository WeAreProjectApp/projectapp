"""Explicit ticket model-field review, kept apart from delivery contracts."""


def build_issue_contracts(contract):
    return (
        contract('accounts.BugReport',
                 read_only='id project reported_by version created_at updated_at archived_at',
                 read_write='title description severity steps_to_reproduce expected_behavior actual_behavior environment device_browser is_recurring status admin_response linked_bug source_requirement is_archived screenshot'),
        contract('accounts.ChangeRequest',
                 read_only='id project created_by version linked_requirement created_at updated_at archived_at',
                 read_write='title description module_or_screen suggested_priority is_urgent status admin_response estimated_cost estimated_time source_requirement is_archived screenshot'),
        contract('accounts.BugComment', read_only='id bug_report user created_at', read_write='content is_internal'),
        contract('accounts.ChangeRequestComment', read_only='id change_request user created_at', read_write='content is_internal'),
        contract('accounts.IssueContext', read_only='id project bug_report change_request publication snapshot created_at'),
        contract('accounts.IssueResponse', read_only='id bug_report change_request actor scope_result created_at',
                 read_write='message status is_internal contract',
                 excluded={'review_evidence': 'Procedencia privada; get_issue_report sólo expone el DTO público permitido y la referencia de auditoría para admin.'}),
        contract('accounts.IssueAttachment', read_only='id response bug_comment change_comment document title sha256 created_at',
                 excluded={'file': 'Almacenamiento privado; download_issue_attachment devuelve un artefacto autorizado.'}),
        contract('accounts.IssueEvent', read_only='id project bug_report change_request actor action previous_status status is_internal created_at',
                 excluded={name: 'Recibo de reintentos propiedad del servidor, nunca se edita ni expone.' for name in ('request_id', 'fingerprint', 'receipt')}),
    )
