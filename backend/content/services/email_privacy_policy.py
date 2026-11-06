"""Credential-bearing channels cannot opt back into copies or retained secrets."""
import copy

PROTECTED_CHANNELS = frozenset({
    'login_code', 'client_invitation', 'admin_invitation', 'magic_link',
    'verification_code_onboarding', 'verification_code_password_reset',
    'verification_code_email_validation',
})
REDACTED_TEXT = 'Se envió un mensaje de acceso. El contenido confidencial no se conserva.'


def credential_email(template_key):
    from content.services.outbound_email_inventory import outbound_email_family
    from content.email_copy_families import SECURITY
    return template_key in PROTECTED_CHANNELS or (outbound_email_family(template_key) == SECURITY and template_key != 'password_changed')


def history_message(message, template_key):
    if not credential_email(template_key):
        return message
    safe = copy.copy(message)
    safe.subject = 'Mensaje de acceso — ProjectApp'
    safe.body = REDACTED_TEXT
    safe.alternatives = []
    safe.attachments = []
    safe.extra_headers = {}
    return safe


def protected_snapshot_payload():
    return {
        'has_body': False, 'snapshot_state': 'redacted',
        'snapshot_notice': REDACTED_TEXT, 'has_attachments': False,
        'attachment_count': 0, 'attachments': [], 'message_size_bytes': None,
        'attachment_size_bytes': None, 'links': {'content': [], 'template': []},
        'can_resend': False, 'resend_of_snapshot_id': None,
    }
