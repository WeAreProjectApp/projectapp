"""Proposal email attachments survive the confirmed MCP multipart bridge."""
import pytest

from content.mcp.upload_tools import store_artifact
from content.models import McpConnector, McpUpload

pytestmark = pytest.mark.django_db


def rpc_call(client, token, name, arguments):
    return client.post(f'/api/mcp/proposals/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }, format='json').data['result']


@pytest.fixture
def delivery_access():
    connector, _ = McpConnector.objects.get_or_create(slug='proposals')
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    return token, connector.credentials.get(label='Default')


@pytest.fixture
def email_assets(delivery_access):
    _, credential = delivery_access
    return [store_artifact(
        connector=credential.connector, credential=credential,
        filename=name, content_type='application/pdf',
        content=b'%PDF-1.4 attachment', request=None,
    )['asset_id'] for name in ('scope.pdf', 'terms.pdf')]


@pytest.fixture
def email_arguments(proposal, email_assets):
    return {
        'proposal_id': proposal.pk,
        'recipient_emails': ['reader@example.com'], 'cc_emails': ['copy@example.com'],
        'subject': 'Documentos revisados', 'greeting': 'Hola', 'footer': '',
        'sections': [{'text': 'Adjuntamos **dos** documentos.', 'markdown': True}],
        'attachment_asset_ids': email_assets,
    }


@pytest.mark.parametrize('tool', ['send_branded_email', 'send_custom_proposal_email'])
def test_confirmed_email_delivers_each_selected_asset(
    api_client, delivery_access, email_arguments, mailoutbox, tool,
):
    """Fails if multipart drops an asset or corrupts nested email recipient/section data."""
    token, _ = delivery_access
    preview = rpc_call(api_client, token, tool, email_arguments)['structuredContent']

    result = rpc_call(api_client, token, 'confirm_action', {
        'confirmation_id': preview['confirmation_id'],
    })

    assert result['isError'] is False
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ['reader@example.com']
    assert mailoutbox[0].cc == ['copy@example.com']
    assert {item[0] for item in mailoutbox[0].attachments} == {'scope.pdf', 'terms.pdf'}
    assert 'dos' in mailoutbox[0].body


def test_email_preview_does_not_consume_uploads(
    api_client, delivery_access, email_arguments, email_assets, mailoutbox,
):
    """Fails if previewing the delivery consumes the user's attachments before confirmation."""
    token, _ = delivery_access

    result = rpc_call(api_client, token, 'send_branded_email', email_arguments)

    assert result['structuredContent']['confirmation_required'] is True
    assert mailoutbox == []
    assert list(McpUpload.objects.filter(pk__in=email_assets).values_list('status', flat=True)) == [
        McpUpload.STATUS_COMPLETE, McpUpload.STATUS_COMPLETE,
    ]


def test_validation_failure_preserves_completed_assets(
    api_client, delivery_access, email_arguments, email_assets, mailoutbox,
):
    """Fails if validation rejection loses assets that have not been delivered."""
    token, _ = delivery_access
    email_arguments['sections'] = []
    preview = rpc_call(api_client, token, 'send_branded_email', email_arguments)['structuredContent']

    result = rpc_call(api_client, token, 'confirm_action', {
        'confirmation_id': preview['confirmation_id'],
    })

    assert result['isError'] is True
    assert mailoutbox == []
    assert McpUpload.objects.filter(pk__in=email_assets, status=McpUpload.STATUS_COMPLETE).count() == 2


def test_confirmed_email_marks_delivered_uploads_consumed(
    api_client, delivery_access, email_arguments, email_assets,
):
    """Fails if a delivered asset remains reusable by an unrelated subsequent write."""
    token, _ = delivery_access
    preview = rpc_call(api_client, token, 'send_branded_email', email_arguments)['structuredContent']

    rpc_call(api_client, token, 'confirm_action', {'confirmation_id': preview['confirmation_id']})

    assert McpUpload.objects.filter(pk__in=email_assets, status=McpUpload.STATUS_CONSUMED).count() == 2


def test_legacy_recipient_field_still_delivers_through_the_mcp(
    api_client, delivery_access, email_arguments, mailoutbox,
):
    """Fails if typed MCP arguments reject the Panel's legacy recipient_email alias."""
    token, _ = delivery_access
    email_arguments['recipient_email'] = email_arguments.pop('recipient_emails')[0]
    preview = rpc_call(api_client, token, 'send_branded_email', email_arguments)['structuredContent']

    result = rpc_call(api_client, token, 'confirm_action', {
        'confirmation_id': preview['confirmation_id'],
    })

    assert result['isError'] is False
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ['reader@example.com']
