"""Tests for the Proposals MCP connector HTTP endpoint."""
import json
from unittest import mock

import pytest
from accounts.services import proposal_client_service
from django.db.models import ProtectedError

from content.models import (
    BusinessProposal,
    McpConnector,
    ProposalChangeLog,
    ProposalSection,
    ProposalShareLink,
)
from content.tests.proposal_traceability import (
    TRACEABILITY_ITEM_ID,
    create_traced_proposal_sections,
    technical_document,
)


@pytest.fixture
def proposals_connector(db):
    connector, _ = McpConnector.objects.get_or_create(
        slug='proposals', defaults={'name': 'Gestor de Propuestas'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector, connector.generate_token()


def _url(token):
    return f'/api/mcp/proposals/{token}/'


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _call(api_client, token, name, arguments):
    response = api_client.post(
        _url(token), _rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )
    payload = response.data.get('result', {}).get('structuredContent', {})
    if payload.get('confirmation_required'):
        response = api_client.post(
            _url(token), _rpc('tools/call', {
                'name': 'confirm_action',
                'arguments': {'confirmation_id': payload['confirmation_id']},
            }), format='json',
        )
        result = response.data['result']
        if not result['isError']:
            payload = result['structuredContent']['result']
            result['content'][0]['text'] = json.dumps(payload, default=str)
            result['structuredContent'] = payload
    return response


@pytest.mark.django_db
class TestProposalsMcp:
    def test_tool_list(self, api_client, proposals_connector):
        """Fails if full-scope discovery hides an available proposal workflow."""
        _, token = proposals_connector
        response = api_client.post(_url(token), _rpc('tools/list'), format='json')
        names = {tool['name'] for tool in response.data['result']['tools']}
        expected = {
            'get_proposal_template', 'list_proposals', 'create_proposal',
            'update_proposal', 'update_proposal_status', 'send_proposal',
            'delete_proposal', 'duplicate_proposal', 'create_share_link',
            'update_proposal_settings', 'get_proposal_defaults',
            'update_proposal_defaults', 'reset_proposal_defaults',
            'get_proposal_company_settings', 'update_proposal_service_settings',
            'get_proposal_contract_template', 'update_proposal_contract',
            'update_proposal_contract_modality', 'read_proposal_contract_markdown',
            'list_proposal_documents', 'upload_proposal_document',
            'read_proposal_document_markdown', 'download_proposal_document',
            'list_email_templates', 'update_email_template', 'send_multi_proposal',
            'send_branded_email', 'send_custom_proposal_email',
            'render_proposal_email_markdown_pdf', 'export_proposal_analytics_csv',
            'get_proposal_formalization_options', 'render_proposal_formalization_pdf',
            'read_proposal_formalization_markdown', 'prepare_proposal_formalization',
            'get_proposal_formalization', 'download_proposal_formalization_file',
            'send_proposal_formalization', 'confirm_action',
            'list_proposal_activity', 'preview_proposal_project_reassignment',
            'reassign_proposal_project', 'list_proposal_history',
            'get_proposal_history_version', 'compare_proposal_history',
        }
        assert expected <= names

    def test_project_reassignment_schema_requires_a_complete_correction_payload(
        self, api_client, proposals_connector,
    ):
        """Fails if MCP can invoke a project correction without its target, reason, impact version, or request identity."""
        _, token = proposals_connector
        response = api_client.post(_url(token), _rpc('tools/list'), format='json')
        tools = {tool['name']: tool for tool in response.data['result']['tools']}
        schema = tools['reassign_proposal_project']['inputSchema']

        payload_schema = schema['properties'].get('data', schema)
        assert {'target_project_id', 'reason', 'expected_impact_hash', 'request_id'} <= set(payload_schema['required'])
        assert payload_schema['additionalProperties'] is False
        assert not {'anyOf', 'oneOf', 'allOf'} & schema.keys()

    def test_project_reassignment_rejects_an_unknown_argument(self, api_client, proposals_connector):
        """Fails if a misspelled reassignment argument reaches a partially defined correction."""
        _, token = proposals_connector
        response = _call(api_client, token, 'reassign_proposal_project', {
            'proposal_id': 1,
            'target_project_id': 2,
            'reason': 'Correction',
            'expected_impact_hash': 'a' * 64,
            'request_id': 'strict-mcp-request',
            'target_projecct_id': 2,
        })

        assert response.data['result']['isError'] is True
        # The incoming central validator classifies unknown root fields separately.
        assert response.data['result']['structuredContent']['error']['code'] in {'VALIDATION_ERROR', 'unknown_field'}

    def test_template_has_required_fields(self, api_client, proposals_connector):
        _, token = proposals_connector
        response = _call(api_client, token, 'get_proposal_template', {'lang': 'es'})
        text = response.data['result']['content'][0]['text']
        assert 'general.clientName' in text
        assert 'email_intro' in text

    def test_resend_tool_exposes_editable_message(self, api_client, proposals_connector):
        _, token = proposals_connector

        response = api_client.post(_url(token), _rpc('tools/list'), format='json')

        tools = {tool['name']: tool for tool in response.data['result']['tools']}
        schema = tools['resend_proposal']['inputSchema']
        assert schema['properties']['email_intro']['type'] == 'string'
        assert 'email_intro' not in schema['required']

    def test_create_requires_general_client_name(self, api_client, proposals_connector):
        _, token = proposals_connector
        response = _call(api_client, token, 'create_proposal', {
            'title': 'Propuesta X', 'client_name': 'ACME', 'sections': {},
        })
        # sections without a general.clientName is rejected by the serializer.
        assert response.data['result']['isError'] is True

    def test_create_and_list_and_get(self, api_client, proposals_connector):
        _, token = proposals_connector
        created = _call(api_client, token, 'create_proposal', {
            'title': 'Propuesta Kore',
            'client_name': 'Kore SAS',
            'client_email': 'kore@x.com',
            'sections': {'general': {'clientName': 'Kore SAS'}},
        })
        assert created.data['result']['isError'] is False
        proposal = BusinessProposal.objects.get(title='Propuesta Kore')
        # Sections were seeded from defaults.
        assert proposal.sections.exists()

        listed = _call(api_client, token, 'list_proposals', {})
        assert 'Propuesta Kore' in listed.data['result']['content'][0]['text']

        got = _call(api_client, token, 'get_proposal', {'proposal_id': proposal.id})
        assert got.data['result']['isError'] is False

    def test_duplicate_resets_to_draft(self, api_client, proposals_connector):
        original = BusinessProposal.objects.create(
            title='Base', client_name='C', status=BusinessProposal.Status.SENT,
        )
        _, token = proposals_connector
        response = _call(api_client, token, 'duplicate_proposal', {'proposal_id': original.id})
        assert response.data['result']['isError'] is False
        copy_obj = BusinessProposal.objects.get(title='Base (copia)')
        assert copy_obj.status == BusinessProposal.Status.DRAFT

    def test_forced_status_transition_succeeds_without_side_effects(
        self, api_client, proposals_connector,
    ):
        proposal = BusinessProposal.objects.create(
            title='T', client_name='C', status=BusinessProposal.Status.DRAFT,
        )
        _, token = proposals_connector
        # draft → accepted is a forced admin jump: allowed, no onboarding.
        with mock.patch('content.tasks.run_platform_onboarding') as mock_task:
            response = _call(api_client, token, 'update_proposal_status', {
                'proposal_id': proposal.id, 'status': 'accepted',
            })
        assert response.data['result']['isError'] is False
        proposal.refresh_from_db()
        assert proposal.status == BusinessProposal.Status.ACCEPTED
        mock_task.assert_not_called()

    def test_unknown_status_errors(self, api_client, proposals_connector):
        proposal = BusinessProposal.objects.create(
            title='T2', client_name='C', status=BusinessProposal.Status.DRAFT,
        )
        _, token = proposals_connector
        response = _call(api_client, token, 'update_proposal_status', {
            'proposal_id': proposal.id, 'status': 'bogus',
        })
        assert response.data['result']['isError'] is True

    def test_delete_proposal(self, api_client, proposals_connector):
        proposal = BusinessProposal.objects.create(title='Borrable', client_name='C')
        _, token = proposals_connector
        response = _call(api_client, token, 'delete_proposal', {'proposal_id': proposal.id})
        assert response.data['result']['isError'] is False
        assert not BusinessProposal.objects.filter(pk=proposal.id).exists()


def _payload(response):
    return json.loads(response.data['result']['content'][0]['text'])


@pytest.mark.django_db
class TestProposalsMcpHandlers:
    def test_get_unknown_proposal_errors(self, api_client, proposals_connector):
        _, token = proposals_connector
        response = _call(api_client, token, 'get_proposal', {'proposal_id': 999999})
        assert response.data['result']['isError'] is True

    def test_template_falls_back_to_spanish_for_unknown_lang(
        self, api_client, proposals_connector,
    ):
        _, token = proposals_connector
        response = _call(api_client, token, 'get_proposal_template', {'lang': 'fr'})
        assert response.data['result']['isError'] is False
        assert 'general' in _payload(response)['template']

    def test_list_filters_by_status(self, api_client, proposals_connector):
        BusinessProposal.objects.create(title='D', client_name='C', status='draft')
        BusinessProposal.objects.create(title='S', client_name='C', status='sent')
        _, token = proposals_connector
        response = _call(api_client, token, 'list_proposals', {'status': 'sent'})
        assert len(_payload(response)['results']) == 1

    def test_list_filters_by_client(self, api_client, proposals_connector):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Cliente MCP', email='mcpcli@x.com', phone='', company='',
        )
        BusinessProposal.objects.create(title='Suya', client_name='C', client=profile)
        BusinessProposal.objects.create(title='Otra', client_name='C')
        _, token = proposals_connector
        response = _call(api_client, token, 'list_proposals', {'client_id': profile.pk})
        assert len(_payload(response)['results']) == 1

    def test_create_reports_unmapped_section_keys(self, api_client, proposals_connector):
        _, token = proposals_connector
        response = _call(api_client, token, 'create_proposal', {
            'title': 'Con extras',
            'client_name': 'ACME',
            'sections': {
                'general': {'clientName': 'ACME'},
                'seccionInventada': {'x': 1},
            },
        })
        assert response.data['result']['isError'] is False
        assert 'seccionInventada' in _payload(response)['warnings'][0]

    def test_update_proposal_changes_title(self, api_client, proposals_connector):
        _, token = proposals_connector
        _call(api_client, token, 'create_proposal', {
            'title': 'Original',
            'client_name': 'ACME',
            'sections': {'general': {'clientName': 'ACME'}},
        })
        proposal = BusinessProposal.objects.get(title='Original')
        response = _call(api_client, token, 'update_proposal', {
            'proposal_id': proposal.id,
            'title': 'Renovada',
            'client_name': 'ACME',
            'sections': {'general': {'clientName': 'ACME'}},
        })
        assert response.data['result']['isError'] is False
        proposal.refresh_from_db()
        assert proposal.title == 'Renovada'

    def test_update_with_invalid_payload_errors(self, api_client, proposals_connector):
        proposal = BusinessProposal.objects.create(title='T', client_name='C')
        _, token = proposals_connector
        response = _call(api_client, token, 'update_proposal', {
            'proposal_id': proposal.id, 'sections': {},
        })
        assert response.data['result']['isError'] is True

    def test_update_rejects_untraced_technical_document_atomically(
        self, api_client, proposals_connector,
    ):
        proposal = BusinessProposal.objects.create(
            title='Original MCP title', client_name='MCP Client',
        )
        technical_section = create_traced_proposal_sections(proposal)
        _, token = proposals_connector

        response = _call(api_client, token, 'update_proposal', {
            'proposal_id': proposal.id,
            'title': 'Title that must roll back',
            'client_name': proposal.client_name,
            'sections': {
                'general': {'clientName': proposal.client_name},
                'technicalDocument': technical_document([]),
            },
        })

        assert response.data['result']['isError'] is True
        assert 'Inicio de sesión' in response.data['result']['content'][0]['text']
        proposal.refresh_from_db()
        technical_section.refresh_from_db()
        assert proposal.title == 'Original MCP title'
        stored_requirement = technical_section.content_json['epics'][0]['requirements'][0]
        assert stored_requirement['linked_item_ids'] == [TRACEABILITY_ITEM_ID]

    @mock.patch('content.mcp.proposal_tools.ProposalService.send_proposal')
    def test_send_proposal_dispatches_and_logs(
        self, mock_send, api_client, proposals_connector,  # noqa: PT019
    ):
        proposal = BusinessProposal.objects.create(
            title='Enviar', client_name='C', client_email='c@x.com',
        )
        _, token = proposals_connector
        response = _call(api_client, token, 'send_proposal', {'proposal_id': proposal.id})
        assert response.data['result']['isError'] is False
        mock_send.assert_called_once()
        assert ProposalChangeLog.objects.filter(
            proposal=proposal, change_type='sent',
        ).exists()

    @mock.patch(
        'content.mcp.proposal_tools.ProposalService.send_proposal',
        side_effect=ValueError('estado inválido'),
    )
    def test_send_proposal_invalid_state_errors(
        self, _mock_send, api_client, proposals_connector,  # noqa: PT019
    ):
        proposal = BusinessProposal.objects.create(title='T', client_name='C')
        _, token = proposals_connector
        response = _call(api_client, token, 'send_proposal', {'proposal_id': proposal.id})
        assert response.data['result']['isError'] is True

    @mock.patch('content.mcp.proposal_tools.ProposalService.resend_proposal')
    def test_resend_proposal_returns_detail(
        self, mock_resend, api_client, proposals_connector,  # noqa: PT019
    ):
        proposal = BusinessProposal.objects.create(
            title='Reenviar', client_name='C', status='sent',
        )
        _, token = proposals_connector
        message = 'El nuevo mensaje explica el resultado esperado.'
        response = _call(api_client, token, 'resend_proposal', {
            'proposal_id': proposal.id,
            'email_intro': message,
        })
        assert response.data['result']['isError'] is False
        mock_resend.assert_called_once_with(proposal, email_intro=message)

    @mock.patch(
        'content.mcp.proposal_tools.ProposalService.resend_proposal',
        side_effect=ValueError('aún en borrador'),
    )
    def test_resend_proposal_invalid_state_errors(
        self, _mock_resend, api_client, proposals_connector,  # noqa: PT019
    ):
        proposal = BusinessProposal.objects.create(title='T', client_name='C')
        _, token = proposals_connector
        response = _call(api_client, token, 'resend_proposal', {'proposal_id': proposal.id})
        assert response.data['result']['isError'] is True

    @mock.patch.object(
        BusinessProposal, 'delete',
        side_effect=ProtectedError('protegida', set()),
    )
    def test_delete_protected_proposal_errors(
        self, _mock_delete, api_client, proposals_connector,  # noqa: PT019
    ):
        proposal = BusinessProposal.objects.create(title='Ligada', client_name='C')
        _, token = proposals_connector
        response = _call(api_client, token, 'delete_proposal', {'proposal_id': proposal.id})
        result = response.data['result']
        assert result['isError'] is True
        assert 'Desvincula el proyecto' in result['content'][0]['text']

    def test_duplicate_copies_sections(self, api_client, proposals_connector):
        original = BusinessProposal.objects.create(title='ConSecciones', client_name='C')
        ProposalSection.objects.create(
            proposal=original, section_type='general', title='General',
            order=1, is_enabled=True, content_json={'clientName': 'C'},
        )
        _, token = proposals_connector
        response = _call(api_client, token, 'duplicate_proposal', {
            'proposal_id': original.id,
        })
        assert response.data['result']['isError'] is False
        copy_obj = BusinessProposal.objects.get(title='ConSecciones (copia)')
        assert copy_obj.sections.count() == 1
        assert copy_obj.sections.first().section_type == 'general'

    @mock.patch(
        'content.services.proposal_email_service.ProposalEmailService.send_share_notification',
    )
    def test_create_share_link_creates_and_returns(
        self, mock_notify, api_client, proposals_connector,  # noqa: PT019
    ):
        proposal = BusinessProposal.objects.create(
            title='Compartible', client_name='C', is_active=True,
        )
        _, token = proposals_connector
        response = _call(api_client, token, 'create_share_link', {
            'proposal_id': proposal.id, 'name': 'María', 'email': 'maria@x.com',
        })
        assert response.data['result']['isError'] is False
        link = ProposalShareLink.objects.get(proposal=proposal)
        assert link.shared_by_name == 'María'
        mock_notify.assert_called_once()

    def test_create_share_link_requires_name(self, api_client, proposals_connector):
        proposal = BusinessProposal.objects.create(
            title='SinNombre', client_name='C', is_active=True,
        )
        _, token = proposals_connector
        response = _call(api_client, token, 'create_share_link', {
            'proposal_id': proposal.id, 'name': '  ',
        })
        assert response.data['result']['isError'] is True
        assert not ProposalShareLink.objects.filter(proposal=proposal).exists()

    def test_create_share_link_inactive_proposal_errors(
        self, api_client, proposals_connector,
    ):
        proposal = BusinessProposal.objects.create(
            title='Inactiva', client_name='C', is_active=False,
        )
        _, token = proposals_connector
        response = _call(api_client, token, 'create_share_link', {
            'proposal_id': proposal.id, 'name': 'María',
        })
        assert response.data['result']['isError'] is True
