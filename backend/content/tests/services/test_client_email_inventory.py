"""Contracts for client email inventory and its delivery boundary."""
import re
from pathlib import Path

import pytest

from content.email_copy_families import (
    COLLECTIONS,
    DIAGNOSTICS,
    DOCUMENTS_MANUAL,
    PLATFORM,
    PROPOSALS,
)
from content.services.client_email_inventory import (
    CLIENT_EMAIL_CHANNELS,
    client_email_family,
)
from content.services.proposal_email_service import CLIENT_FACING_TEMPLATE_KEYS

EXPECTED_CHANNELS = (
    ('proposal_sent_client', PROPOSALS),
    ('proposal_multi_sent_client', PROPOSALS),
    ('proposal_reminder', PROPOSALS),
    ('proposal_urgency', PROPOSALS),
    ('proposal_urgency_no_discount', PROPOSALS),
    ('proposal_accepted_client', PROPOSALS),
    ('proposal_finished_client', PROPOSALS),
    ('proposal_rejected_client', PROPOSALS),
    ('proposal_reengagement', PROPOSALS),
    ('proposal_abandonment_followup', PROPOSALS),
    ('proposal_investment_interest_followup', PROPOSALS),
    ('proposal_scheduled_followup', PROPOSALS),
    ('proposal_negotiation_confirmation', PROPOSALS),
    ('magic_link', PROPOSALS),
    ('diagnostic_initial_sent', DIAGNOSTICS),
    ('diagnostic_final_sent', DIAGNOSTICS),
    ('diagnostic_custom_email', DIAGNOSTICS),
    ('diagnostic_documents_sent', DIAGNOSTICS),
    ('proposal_documents_sent', DOCUMENTS_MANUAL),
    ('proposal_formalization', DOCUMENTS_MANUAL),
    ('branded_email', DOCUMENTS_MANUAL),
    ('proposal_email', DOCUMENTS_MANUAL),
    ('delivery_stage_approved_client', DOCUMENTS_MANUAL),
    ('collection_account_sent', COLLECTIONS),
    ('income_payment_received_client', COLLECTIONS),
    ('document_signed_client', PLATFORM),
    ('delivery_published_client', PLATFORM),
    ('delivery_message_client', PLATFORM),
)

SEND_CALL = re.compile(r'\.send\s*\(')
CDP_DOM_SNAPSHOT_ARGUMENT = re.compile(
    r"\s*['\"]DOMSnapshot\.captureSnapshot['\"]\s*,",
)


@pytest.mark.parametrize(('template_key', 'family'), EXPECTED_CHANNELS)
def test_client_channel_resolves_copy_family(template_key, family):
    assert client_email_family(template_key) == family


def test_proposal_audience_set_matches_inventory():
    assert CLIENT_FACING_TEMPLATE_KEYS == frozenset(CLIENT_EMAIL_CHANNELS)


def _has_unapproved_send(line):
    for call in SEND_CALL.finditer(line):
        receiver = line[:call.start()].rstrip()
        argument = line[call.end():]
        if receiver.endswith('EmailDeliveryGateway'):
            continue
        if receiver.endswith('session') and CDP_DOM_SNAPSHOT_ARGUMENT.match(argument):
            continue
        return True
    return False


def _mail_io_offenders(backend=None):
    backend = Path(backend) if backend is not None else Path(__file__).resolve().parents[3]
    gateway = backend / 'content/services/email_delivery_service.py'
    offenders = []
    for path in backend.rglob('*.py'):
        if path == gateway or 'tests' in path.parts or 'migrations' in path.parts:
            continue
        source = path.read_text(encoding='utf-8')
        if re.search(r'^\s*(?:from|import)\s+django\.core\.mail', source, re.MULTILINE):
            offenders.append(str(path.relative_to(backend)))
        if re.search(r'\b(?:send_mail|mail_admins)\s*\(', source):
            offenders.append(str(path.relative_to(backend)))
        for line in source.splitlines():
            if _has_unapproved_send(line):
                offenders.append(str(path.relative_to(backend)))
                break
    return sorted(set(offenders))


def test_smtp_io_is_confined_to_gateway():
    assert _mail_io_offenders() == []


@pytest.mark.parametrize('separator', ['\n', '; '], ids=('next-line', 'same-line'))
def test_smtp_send_is_reported_when_source_uses_dom_snapshot(tmp_path, separator):
    """Fails if a neighboring CDP command masks an unapproved SMTP send call."""
    service = tmp_path / 'content/services/unapproved_mailer.py'
    service.parent.mkdir(parents=True)
    service.write_text(
        "session.send('DOMSnapshot.captureSnapshot', {})"
        f'{separator}smtp_connection.send(message)\n',
        encoding='utf-8',
    )

    assert _mail_io_offenders(tmp_path) == [
        'content/services/unapproved_mailer.py',
    ]
