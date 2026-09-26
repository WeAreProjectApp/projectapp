"""Authoritative inventory for every email emitted by ProjectApp.

Every production sender must use :class:`EmailDeliveryGateway`, and every
template key accepted by the gateway must appear here. This makes copying an
outbound email the default construction: a new channel cannot silently bypass
the configured BCC audience.
"""

from content.email_copy_families import (
    ACCOUNTING,
    COLLECTIONS,
    DIAGNOSTICS,
    DOCUMENTS_COMMUNICATIONS,
    PLATFORM,
    PROPOSALS,
    SECURITY,
    TASKS_OPERATIONS,
)


OUTBOUND_EMAIL_CHANNELS = {
    # Commercial proposal lifecycle — customer messages.
    'proposal_sent_client': PROPOSALS,
    'proposal_multi_sent_client': PROPOSALS,
    'proposal_reminder': PROPOSALS,
    'proposal_urgency': PROPOSALS,
    'proposal_urgency_no_discount': PROPOSALS,
    'proposal_accepted_client': PROPOSALS,
    'proposal_finished_client': PROPOSALS,
    'proposal_rejected_client': PROPOSALS,
    'proposal_reengagement': PROPOSALS,
    'proposal_abandonment_followup': PROPOSALS,
    'proposal_investment_interest_followup': PROPOSALS,
    'proposal_scheduled_followup': PROPOSALS,
    'proposal_negotiation_confirmation': PROPOSALS,
    'magic_link': PROPOSALS,

    # Commercial proposal lifecycle — agency notifications.
    'proposal_response_notification': PROPOSALS,
    'proposal_first_view_notification': PROPOSALS,
    'proposal_comment_notification': PROPOSALS,
    'proposal_revisit_alert': PROPOSALS,
    'proposal_share_notification': PROPOSALS,
    'proposal_stakeholder_detected': PROPOSALS,
    'seller_inactivity_escalation': PROPOSALS,
    'proposal_negotiation_notification': PROPOSALS,
    'post_rejection_revisit_alert': PROPOSALS,
    'daily_pipeline_digest': PROPOSALS,
    'proposal_post_expiration_visit': PROPOSALS,
    'proposal_stage_warning_notification': PROPOSALS,
    'proposal_stage_overdue_notification': PROPOSALS,

    # Technical diagnostic lifecycle.
    'diagnostic_initial_sent': DIAGNOSTICS,
    'diagnostic_final_sent': DIAGNOSTICS,
    'diagnostic_custom_email': DIAGNOSTICS,
    'diagnostic_documents_sent': DIAGNOSTICS,

    # Attachments, manual messages and the future Communications delivery seam.
    'proposal_formalization': DOCUMENTS_COMMUNICATIONS,
    'proposal_documents_sent': DOCUMENTS_COMMUNICATIONS,
    'branded_email': DOCUMENTS_COMMUNICATIONS,
    'proposal_email': DOCUMENTS_COMMUNICATIONS,
    # Internal notice of a client-created secure link; never carries the
    # link token or the protected content.
    'secure_link_received_team': DOCUMENTS_COMMUNICATIONS,

    # Billing documents sent to customers.
    'collection_account_sent': COLLECTIONS,

    # Accounting and hosting notices sent to the agency.
    'accounting_change': ACCOUNTING,
    'accounting_card_reminder': ACCOUNTING,
    'accounting_statement_reminder': ACCOUNTING,
    'accounting_payment_calendar': ACCOUNTING,
    'payment_status_team': ACCOUNTING,

    # Client-platform milestones.
    'document_signed_client': PLATFORM,
    'client_flow_first_login_team': PLATFORM,
    'client_flow_email_validated_team': PLATFORM,
    'client_flow_document_signed_team': PLATFORM,

    # Operational alerts and diagnostic tooling.
    'task_deadline_notification': TASKS_OPERATIONS,
    'task_alert_notification': TASKS_OPERATIONS,
    'generic_internal_notification': TASKS_OPERATIONS,
    'frontend_build_failure': TASKS_OPERATIONS,
    'linkedin_token_expiry': TASKS_OPERATIONS,
    'proposal_notification_diagnostic': TASKS_OPERATIONS,

    # Authentication and credential-bearing messages. Product policy
    # explicitly requires these to be copied and retained in full.
    'client_invitation': SECURITY,
    'admin_invitation': SECURITY,
    'password_changed': SECURITY,
    'verification_code_onboarding': SECURITY,
    'verification_code_password_reset': SECURITY,
    'verification_code_email_validation': SECURITY,
}


def outbound_email_family(template_key):
    """Return the configured family for a registered outbound channel."""
    return OUTBOUND_EMAIL_CHANNELS.get(template_key)
