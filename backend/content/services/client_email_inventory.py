"""Authoritative inventory of outbound emails whose recipient is a client.

The delivery gateway refuses an unregistered ``client`` classification. A
new customer-facing channel therefore cannot start sending until it is added
here and assigned to one of the administrable copy families.
"""

from content.email_copy_families import (
    COLLECTIONS,
    DIAGNOSTICS,
    DOCUMENTS_MANUAL,
    PLATFORM,
    PROPOSALS,
)
from content.services.outbound_email_inventory import outbound_email_family


CLIENT_EMAIL_CHANNELS = {
    # Commercial proposal lifecycle.
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

    # Technical diagnostic lifecycle.
    'diagnostic_initial_sent': DIAGNOSTICS,
    'diagnostic_final_sent': DIAGNOSTICS,
    'diagnostic_custom_email': DIAGNOSTICS,
    'diagnostic_documents_sent': DIAGNOSTICS,

    # Attachments and manually composed customer communication.
    'proposal_formalization': DOCUMENTS_MANUAL,
    'proposal_documents_sent': DOCUMENTS_MANUAL,
    'branded_email': DOCUMENTS_MANUAL,
    'proposal_email': DOCUMENTS_MANUAL,
    'delivery_stage_approved_client': DOCUMENTS_MANUAL,

    # Billing documents sent to the customer. Initial issue, resend and retry
    # intentionally share one key and one family.
    'collection_account_sent': COLLECTIONS,

    # Platform operational confirmations (security credentials are excluded).
    'document_signed_client': PLATFORM,
    'delivery_published_client': PLATFORM,
    'delivery_message_client': PLATFORM,
}


def client_email_family(template_key):
    """Return the configured family for a client template, or ``None``."""
    if template_key not in CLIENT_EMAIL_CHANNELS:
        return None
    return outbound_email_family(template_key)
