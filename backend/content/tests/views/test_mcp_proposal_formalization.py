"""Credential-owned Formalization packages through the Proposals MCP."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile

from content.models import (
    EmailLog,
    McpActionIntent,
    McpConnector,
    McpCredential,
    BusinessProposal,
    ProposalFormalization,
    ProposalSection,
)


def _rpc(name, arguments, message_id=1):
    return {
        'jsonrpc': '2.0', 'id': message_id, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }


def _call(api_client, token, name, arguments):
    return api_client.post(
        f'/api/mcp/proposals/{token}/', _rpc(name, arguments), format='json',
    ).data['result']


def _payload(result):
    return result['structuredContent']


def _final_receipt_failure(original_save):
    def save(intent, *args, **kwargs):
        if kwargs.get('update_fields') == ['result']:
            raise RuntimeError('result receipt store unavailable')
        return original_save(intent, *args, **kwargs)
    return save


@pytest.fixture
def formalization_tokens():
    connector, _ = McpConnector.objects.get_or_create(
        slug='proposals', defaults={'name': 'Proposal MCP'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    owner_token = connector.generate_token()
    other = McpCredential.objects.create(
        connector=connector,
        label='Other formalization caller',
        token_hash=McpCredential.hash_token('initial-other-token'),
    )
    return owner_token, other.generate_token()


@pytest.fixture
def formalization_proposal():
    return BusinessProposal.objects.create(
        title='Formalization scope', client_name='Acme Corp',
        client_email='contact@acme.com', total_investment=Decimal('15000.00'),
        currency='COP',
    )


@pytest.fixture
def formalization_arguments(formalization_proposal):
    sections = {
        'functional_requirements': {
            'groups': [{'id': 'orders', 'title': 'Orders', 'items': [{
                'id': 'create-order', 'name': 'Create order',
                'description': 'Stores the order.', 'is_required': True,
            }]}],
        },
        'investment': {'paymentOptions': [{'label': '100% on delivery', 'description': ''}]},
        'technical_document': {
            'purpose': 'Manage orders.',
            'epics': [{'epicKey': 'ORD', 'title': 'Orders', 'requirements': [{
                'flowKey': 'ORD-01', 'title': 'Create order',
                'description': 'Stores the order.', 'linked_item_ids': ['create-order'],
            }]}],
        },
    }
    for order, (section_type, content_json) in enumerate(sections.items()):
        ProposalSection.objects.create(
            proposal=formalization_proposal, section_type=section_type, title=section_type,
            order=order, content_json=content_json,
        )
    return {
        'proposal_id': formalization_proposal.pk,
        'documents': ['commercial', 'technical'],
        'additional_doc_ids': [],
        'subject': 'Formalization package',
        'greeting': 'Hello Acme,',
        'body': 'Attached are the documents you reviewed.',
        'footer': 'ProjectApp',
        'sections': [],
        'recipient_emails': ['contact@acme.com'],
        'cc_emails': [],
    }


def _prepare(api_client, token, arguments):
    result = _call(api_client, token, 'prepare_proposal_formalization', arguments)
    assert result['isError'] is False
    return _payload(result)


@pytest.mark.django_db(transaction=True)
class TestProposalMcpFormalization:
    def test_preparation_is_visible_only_to_its_creating_credential(
        self, api_client, formalization_tokens, formalization_arguments,
    ):
        """Fails if another Proposals credential can read a private review package."""
        owner_token, other_token = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        preparation = ProposalFormalization.objects.get(pk=prepared['id'])

        owner_result = _call(api_client, owner_token, 'get_proposal_formalization', {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'],
        })
        other_result = _call(api_client, other_token, 'get_proposal_formalization', {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'],
        })

        assert preparation.mcp_credential_id is not None
        assert owner_result['isError'] is False
        assert _payload(owner_result)['id'] == prepared['id']
        assert other_result['isError'] is True
        assert _payload(other_result)['error']['code'] == 'NOT_FOUND'

    def test_panel_preparation_without_a_credential_is_not_visible_to_mcp(
        self, api_client, formalization_tokens, formalization_arguments,
    ):
        """Fails if an MCP caller can retrieve an older package created only by the Panel."""
        owner_token, _ = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        ProposalFormalization.objects.filter(pk=prepared['id']).update(mcp_credential=None)

        result = _call(api_client, owner_token, 'get_proposal_formalization', {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'],
        })

        assert result['isError'] is True
        assert _payload(result)['error']['code'] == 'NOT_FOUND'
        assert ProposalFormalization.objects.get(pk=prepared['id']).mcp_credential_id is None

    def test_prepared_file_download_is_an_owner_scoped_artifact(
        self, api_client, formalization_tokens, formalization_arguments,
    ):
        """Fails if a prepared attachment is exposed inline or downloadable by another credential."""
        owner_token, other_token = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        file_id = prepared['files'][0]['file_id']
        arguments = {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'], 'file_id': file_id,
        }

        owner_result = _call(
            api_client, owner_token, 'download_proposal_formalization_file', arguments,
        )
        other_result = _call(
            api_client, other_token, 'download_proposal_formalization_file', arguments,
        )

        assert owner_result['isError'] is False
        assert 'asset_id' in _payload(owner_result)
        assert 'content' not in _payload(owner_result)
        assert other_result['isError'] is True
        assert _payload(other_result)['error']['code'] == 'NOT_FOUND'

    def test_expired_preparation_is_not_readable(
        self, api_client, formalization_tokens, formalization_arguments,
    ):
        """Fails if a formalization package remains available after its review window expires."""
        owner_token, _ = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        preparation = ProposalFormalization.objects.get(pk=prepared['id'])
        ProposalFormalization.objects.filter(pk=prepared['id']).update(
            expires_at=preparation.created_at - timedelta(seconds=1),
        )

        result = _call(api_client, owner_token, 'get_proposal_formalization', {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'],
        })

        assert result['isError'] is True
        assert _payload(result)['error']['code'] == 'EXPIRED_PREPARATION'

    def test_expired_preparation_cannot_be_previewed_for_delivery(
        self, api_client, formalization_tokens, formalization_arguments,
    ):
        """Fails if an expired review package can still create a delivery confirmation."""
        owner_token, _ = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        preparation = ProposalFormalization.objects.get(pk=prepared['id'])
        ProposalFormalization.objects.filter(pk=prepared['id']).update(
            expires_at=preparation.created_at - timedelta(seconds=1),
        )

        result = _call(api_client, owner_token, 'send_proposal_formalization', {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'],
        })

        assert result['isError'] is True
        assert _payload(result)['error']['code'] == 'EXPIRED_PREPARATION'

    def test_changed_prepared_file_is_not_downloaded_as_an_artifact(
        self, api_client, formalization_tokens, formalization_arguments,
    ):
        """Fails if a file altered after review is exposed through the MCP artifact download."""
        owner_token, _ = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        preparation = ProposalFormalization.objects.get(pk=prepared['id'])
        attachment = preparation.files.first()
        attachment.file.save('changed-after-review.pdf', ContentFile(b'changed content'), save=True)

        result = _call(api_client, owner_token, 'download_proposal_formalization_file', {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'], 'file_id': attachment.pk,
        })

        assert result['isError'] is True
        assert _payload(result)['error']['code'] == 'ATTACHMENT_CHANGED'

    @patch('content.services.proposal_formalization_service.EmailDeliveryGateway.send', return_value=True)
    def test_confirmation_replay_returns_cached_result_without_resending(
        self, delivery, api_client, formalization_tokens, formalization_arguments,
    ):
        """Fails if preview sends immediately or confirming the same package sends a second email."""
        owner_token, _ = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        send_arguments = {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'],
        }

        preview = _call(api_client, owner_token, 'send_proposal_formalization', send_arguments)
        assert _payload(preview)['confirmation_required'] is True
        assert EmailLog.objects.filter(template_key='proposal_formalization').count() == 0

        first = _call(api_client, owner_token, 'confirm_action', {
            'confirmation_id': _payload(preview)['confirmation_id'],
        })
        replay = _call(api_client, owner_token, 'confirm_action', {
            'confirmation_id': _payload(preview)['confirmation_id'],
        })

        preparation = ProposalFormalization.objects.get(pk=prepared['id'])
        assert _payload(first)['replayed'] is False
        assert preparation.status == ProposalFormalization.Status.SENT
        assert EmailLog.objects.filter(template_key='proposal_formalization').count() == 1
        assert _payload(replay)['replayed'] is True
        assert delivery.call_count == 1

    @patch('content.services.proposal_formalization_service.EmailDeliveryGateway.send', return_value=True)
    def test_confirmation_rejects_a_package_changed_after_preview(
        self, delivery, api_client, formalization_tokens, formalization_arguments,
        formalization_proposal,
    ):
        """Fails if confirmation delivers a package after its proposal changed since review."""
        owner_token, _ = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        preview = _call(api_client, owner_token, 'send_proposal_formalization', {
            'proposal_id': formalization_proposal.pk, 'preparation_id': prepared['id'],
        })
        formalization_proposal.title = 'Scope changed after preview'
        formalization_proposal.save(update_fields=['title'])

        confirmed = _call(api_client, owner_token, 'confirm_action', {
            'confirmation_id': _payload(preview)['confirmation_id'],
        })

        assert confirmed['isError'] is True
        assert _payload(confirmed)['error']['code'] == 'STALE_PREPARATION'
        assert delivery.call_count == 0

    @pytest.mark.parametrize(
        ('gateway_options', 'expected_status'),
        [
            ({'return_value': False}, ProposalFormalization.Status.FAILED),
            ({'side_effect': RuntimeError('delivery uncertain')}, ProposalFormalization.Status.UNKNOWN),
        ],
    )
    def test_unsuccessful_delivery_is_consumed_without_a_retry(
        self, gateway_options, expected_status, api_client, formalization_tokens,
        formalization_arguments,
    ):
        """Fails if a failed or uncertain delivery can resend the same reviewed package."""
        owner_token, _ = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        preview = _call(api_client, owner_token, 'send_proposal_formalization', {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'],
        })

        with patch(
            'content.services.proposal_formalization_service.EmailDeliveryGateway.send', **gateway_options,
        ) as delivery:
            first = _call(api_client, owner_token, 'confirm_action', {
                'confirmation_id': _payload(preview)['confirmation_id'],
            })
            replay = _call(api_client, owner_token, 'confirm_action', {
                'confirmation_id': _payload(preview)['confirmation_id'],
            })

        preparation = ProposalFormalization.objects.get(pk=prepared['id'])
        assert _payload(first)['result']['status'] == expected_status
        assert preparation.status == expected_status
        assert _payload(replay)['replayed'] is True
        assert delivery.call_count == 1

    @patch('content.services.proposal_formalization_service.EmailDeliveryGateway.send', return_value=True)
    def test_replay_does_not_resend_after_the_post_delivery_receipt_write_fails(
        self, delivery, api_client, formalization_tokens, formalization_arguments,
    ):
        """Fails if an audit-write failure after delivery leaves the confirmation able to send again."""
        owner_token, _ = formalization_tokens
        prepared = _prepare(api_client, owner_token, formalization_arguments)
        preview = _call(api_client, owner_token, 'send_proposal_formalization', {
            'proposal_id': formalization_arguments['proposal_id'],
            'preparation_id': prepared['id'],
        })
        original_save = McpActionIntent.save

        with patch.object(
            McpActionIntent, 'save', autospec=True,
            side_effect=_final_receipt_failure(original_save),
        ):
            failed_confirmation = _call(api_client, owner_token, 'confirm_action', {
                'confirmation_id': _payload(preview)['confirmation_id'],
            })
        replay = _call(api_client, owner_token, 'confirm_action', {
            'confirmation_id': _payload(preview)['confirmation_id'],
        })

        assert failed_confirmation['isError'] is True
        assert ProposalFormalization.objects.get(pk=prepared['id']).status == ProposalFormalization.Status.SENT
        assert EmailLog.objects.filter(template_key='proposal_formalization').count() == 1
        assert _payload(replay)['replayed'] is True
        assert delivery.call_count == 1
