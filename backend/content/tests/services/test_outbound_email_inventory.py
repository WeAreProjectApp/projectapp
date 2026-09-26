"""Contract for the complete outbound-email inventory.

Each family assertion names every registered channel explicitly. A sender can
only reach SMTP through the gateway, and the gateway rejects a key that is not
listed here, so these tests are the channel-by-channel completeness check for
the universal-copy rule.
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
from content.services.outbound_email_inventory import OUTBOUND_EMAIL_CHANNELS


def _channels_for(family):
    return {
        template_key
        for template_key, registered_family in OUTBOUND_EMAIL_CHANNELS.items()
        if registered_family == family
    }


def test_proposal_inventory_lists_every_channel():
    assert _channels_for(PROPOSALS) == {
        'proposal_sent_client',
        'proposal_multi_sent_client',
        'proposal_reminder',
        'proposal_urgency',
        'proposal_urgency_no_discount',
        'proposal_accepted_client',
        'proposal_finished_client',
        'proposal_rejected_client',
        'proposal_reengagement',
        'proposal_abandonment_followup',
        'proposal_investment_interest_followup',
        'proposal_scheduled_followup',
        'proposal_negotiation_confirmation',
        'magic_link',
        'proposal_response_notification',
        'proposal_first_view_notification',
        'proposal_comment_notification',
        'proposal_revisit_alert',
        'proposal_share_notification',
        'proposal_stakeholder_detected',
        'seller_inactivity_escalation',
        'proposal_negotiation_notification',
        'post_rejection_revisit_alert',
        'daily_pipeline_digest',
        'proposal_post_expiration_visit',
        'proposal_stage_warning_notification',
        'proposal_stage_overdue_notification',
    }


def test_diagnostic_inventory_lists_every_channel():
    assert _channels_for(DIAGNOSTICS) == {
        'diagnostic_initial_sent',
        'diagnostic_final_sent',
        'diagnostic_custom_email',
        'diagnostic_documents_sent',
    }


def test_documents_inventory_lists_every_channel():
    assert _channels_for(DOCUMENTS_COMMUNICATIONS) == {
        'proposal_formalization',
        'proposal_documents_sent',
        'branded_email',
        'proposal_email',
        'secure_link_received_team',
    }


def test_collection_inventory_lists_every_channel():
    assert _channels_for(COLLECTIONS) == {'collection_account_sent'}


def test_accounting_inventory_lists_every_channel():
    assert _channels_for(ACCOUNTING) == {
        'accounting_change',
        'accounting_card_reminder',
        'accounting_statement_reminder',
        'accounting_payment_calendar',
        'payment_status_team',
    }


def test_platform_inventory_lists_every_channel():
    assert _channels_for(PLATFORM) == {
        'document_signed_client',
        'client_flow_first_login_team',
        'client_flow_email_validated_team',
        'client_flow_document_signed_team',
    }


def test_operations_inventory_lists_every_channel():
    assert _channels_for(TASKS_OPERATIONS) == {
        'task_deadline_notification',
        'task_alert_notification',
        'generic_internal_notification',
        'frontend_build_failure',
        'linkedin_token_expiry',
        'proposal_notification_diagnostic',
    }


def test_security_inventory_lists_every_channel():
    assert _channels_for(SECURITY) == {
        'client_invitation',
        'admin_invitation',
        'password_changed',
        'verification_code_onboarding',
        'verification_code_password_reset',
        'verification_code_email_validation',
    }


def test_inventory_contains_58_unique_channels():
    assert len(OUTBOUND_EMAIL_CHANNELS) == 58
