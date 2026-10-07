"""Proposal MCP parity behavior over the public JSON-RPC endpoint."""
from datetime import timedelta

import pytest
from accounts.models import Deliverable, Project, ProjectPhase, UserProfile
from django.contrib.auth import get_user_model

from content.models import (
    BusinessProposal,
    EntityHistory,
    EntityRevision,
    McpConnector,
    ProposalDefaultConfig,
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


def _list_tools(api_client, token):
    return api_client.post(
        f'/api/mcp/proposals/{token}/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, format='json',
    ).data['result']['tools']


def _payload(result):
    return result['structuredContent']


@pytest.fixture
def proposals_token(db):
    connector, _ = McpConnector.objects.get_or_create(
        slug='proposals', defaults={'name': 'Proposal MCP'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


@pytest.mark.django_db
class TestProposalMcpSettings:
    def test_reassignment_requires_mcp_confirmation_before_moving_the_phase(
        self, api_client, proposals_token,
    ):
        """Fails if MCP applies a proposal project correction before the caller confirms its reviewed impact."""
        User = get_user_model()
        client_user = User.objects.create_user(username='mcp-reassignment-client', password='test')
        client = UserProfile.objects.create(user=client_user, role=UserProfile.ROLE_CLIENT)
        source = Project.objects.create(name='MCP source', client=client_user)
        target = Project.objects.create(name='MCP target', client=client_user)
        proposal = BusinessProposal.objects.create(
            title='MCP proposal correction', client=client, client_name='MCP client',
            client_email='mcp-client@example.test', total_investment=1,
            status=BusinessProposal.Status.ACCEPTED,
        )
        package = Deliverable.objects.create(project=source, title='MCP package', uploaded_by=client_user)
        proposal.deliverable = package
        proposal.save(update_fields=['deliverable'])
        phase = ProjectPhase.objects.create(project=source, business_proposal=proposal, order=1)
        preview = _payload(_call(api_client, proposals_token, 'preview_proposal_project_reassignment', {
            'proposal_id': proposal.pk, 'target_project_id': target.pk,
        }))

        pending = _call(api_client, proposals_token, 'reassign_proposal_project', {
            'proposal_id': proposal.pk, 'target_project_id': target.pk,
            'reason': 'Correct MCP project association',
            'expected_impact_hash': preview['impact_hash'], 'request_id': 'mcp-confirmation-request',
        })
        phase.refresh_from_db()
        assert _payload(pending)['confirmation_required'] is True
        assert phase.project_id == source.pk
        confirmed = _call(api_client, proposals_token, 'confirm_action', {
            'confirmation_id': _payload(pending)['confirmation_id'],
        })

        phase.refresh_from_db()
        assert phase.project_id == target.pk
        assert confirmed['isError'] is False

    def test_history_tool_redacts_private_file_paths_from_a_real_mcp_response(
        self, api_client, proposals_token, proposal,
    ):
        """Fails if MCP history reads reveal a stored file path in snapshots or change values."""
        history, _ = EntityHistory.objects.get_or_create(
            entity_type='proposal', object_id=proposal.pk,
            defaults={'object_label': proposal.title},
        )
        revision = EntityRevision.objects.create(
            history=history, number=999, action='updated',
            snapshot={'generated_file': 'private/proposals/contract.pdf', 'title': proposal.title},
            changes=[
                {'field': 'generated_file', 'old': 'private/proposals/old.pdf',
                 'new': 'private/proposals/contract.pdf', 'lines': ['private/proposals/contract.pdf']},
                {'field': 'title', 'old': 'Before', 'new': 'After'},
            ],
        )

        result = _call(api_client, proposals_token, 'get_proposal_history_version', {
            'object_id': proposal.pk, 'revision_id': revision.pk,
        })
        payload = _payload(result)

        assert result['isError'] is False
        assert payload['snapshot'] == {'title': proposal.title}
        assert payload['changes'] == [{'field': 'generated_file'}, {'field': 'title', 'old': 'Before', 'new': 'After'}]
        assert 'private/proposals' not in str(payload)

    def test_restricted_credential_does_not_gain_proposal_write_tools(self, api_client, proposals_token):
        """Fails if a restricted credential discovers proposal mutations outside its explicit allowlist."""
        connector = McpConnector.objects.get(slug='proposals')
        credential = connector.credential_for_token(proposals_token)
        credential.allowed_tools = ['get_proposal_defaults']
        credential.save(update_fields=['allowed_tools'])

        names = {tool['name'] for tool in _list_tools(api_client, proposals_token)}

        assert 'get_proposal_defaults' in names
        assert 'update_proposal_contract' not in names
        assert 'send_proposal_formalization' not in names

    def test_partial_settings_update_preserves_omitted_metadata(
        self, api_client, proposals_token, proposal,
    ):
        """Fails if a one-field MCP update erases proposal metadata not sent by the caller."""
        original_email = proposal.client_email

        result = _call(api_client, proposals_token, 'update_proposal_settings', {
            'proposal_id': proposal.pk, 'title': 'Scope revised by MCP',
        })

        proposal.refresh_from_db()
        assert result['isError'] is False
        assert proposal.title == 'Scope revised by MCP'
        assert proposal.client_email == original_email

    def test_settings_update_records_the_mcp_actor_in_entity_history(
        self, api_client, proposals_token, proposal,
    ):
        """Fails if ordinary MCP settings writes stop recording their technical actor in history."""
        result = _call(api_client, proposals_token, 'update_proposal_settings', {
            'proposal_id': proposal.pk, 'title': 'History audited by MCP',
        })

        revision = EntityHistory.objects.get(
            entity_type='proposal', object_id=proposal.pk,
        ).entries.get(action='updated')
        assert result['isError'] is False
        assert revision.source == 'mcp:proposals'
        credential = McpConnector.objects.get(slug='proposals').credential_for_token(proposals_token)
        assert revision.actor_id_snapshot == credential.actor.pk

    def test_unknown_settings_field_is_rejected_without_a_write(
        self, api_client, proposals_token, proposal,
    ):
        """Fails if a misspelled MCP setting is accepted as a silent successful no-op."""
        original_title = proposal.title

        result = _call(api_client, proposals_token, 'update_proposal_settings', {
            'proposal_id': proposal.pk, 'titlle': 'Typo must not persist',
        })

        proposal.refresh_from_db()
        assert result['isError'] is True
        assert _payload(result)['error']['code'] == 'VALIDATION_ERROR'
        assert proposal.title == original_title

    def test_defaults_read_uses_the_requested_english_language(
        self, api_client, proposals_token,
    ):
        """Fails if the MCP defaults bridge drops the requested language selector."""
        result = _call(api_client, proposals_token, 'get_proposal_defaults', {'lang': 'en'})

        assert result['isError'] is False
        assert _payload(result)['language'] == 'en'

    def test_defaults_reject_a_stale_sections_replacement(
        self, api_client, proposals_token,
    ):
        """Fails if an MCP defaults write replaces sections loaded before another editor saved."""
        first_read = _call(api_client, proposals_token, 'get_proposal_defaults', {'lang': 'en'})
        current = _payload(first_read)
        config = ProposalDefaultConfig.objects.create(
            language='en', sections_json=current['sections_json'], expiration_days=21,
        )
        loaded = _payload(_call(api_client, proposals_token, 'get_proposal_defaults', {'lang': 'en'}))
        concurrent_sections = loaded['sections_json'][:-1]
        ProposalDefaultConfig.objects.filter(pk=config.pk).update(
            sections_json=concurrent_sections,
            updated_at=config.updated_at + timedelta(seconds=1),
        )

        result = _call(api_client, proposals_token, 'update_proposal_defaults', {
            'language': 'en', 'sections_json': loaded['sections_json'],
            'base_updated_at': loaded['updated_at'],
        })

        assert result['isError'] is True
        assert _payload(result)['error']['code'] == 'STALE_DEFAULTS'
        config.refresh_from_db()
        assert config.sections_json == concurrent_sections

    def test_defaults_update_keeps_the_requested_english_language(
        self, api_client, proposals_token,
    ):
        """Fails if an MCP defaults update stores English values under the Spanish configuration."""
        current = _payload(_call(api_client, proposals_token, 'get_proposal_defaults', {'lang': 'en'}))

        result = _call(api_client, proposals_token, 'update_proposal_defaults', {
            'language': 'en', 'expiration_days': 28,
        })

        assert result['isError'] is False
        assert _payload(result)['language'] == 'en'
        assert _payload(result)['expiration_days'] == 28
        assert ProposalDefaultConfig.objects.get(language='en').sections_json == current['sections_json']

    def test_service_settings_sorts_a_valid_catalog_before_persisting(
        self, api_client, proposals_token, company_settings,
    ):
        """Fails if valid service-term options are persisted in caller order instead of canonical order."""
        settings = {
            'duration_options': [12, 3, 6],
            'notice_options': [90, 30, 60],
            'default_duration': 6,
            'default_renewal_notice': 30,
            'default_termination_notice': 60,
        }

        result = _call(api_client, proposals_token, 'update_proposal_service_settings', {
            'service_contract_settings': settings,
        })

        company_settings.refresh_from_db()
        assert result['isError'] is False
        assert company_settings.service_contract_settings['duration_options'] == [3, 6, 12]
        assert company_settings.service_contract_settings['notice_options'] == [30, 60, 90]

    def test_service_settings_reject_an_unlisted_default_without_overwriting_catalog(
        self, api_client, proposals_token, company_settings,
    ):
        """Fails if the MCP accepts a service default that cannot be selected in its catalog."""
        before = company_settings.service_contract_settings
        invalid = {
            'duration_options': [3, 6],
            'notice_options': [30, 60],
            'default_duration': 12,
            'default_renewal_notice': 30,
            'default_termination_notice': 60,
        }

        result = _call(api_client, proposals_token, 'update_proposal_service_settings', {
            'service_contract_settings': invalid,
        })

        company_settings.refresh_from_db()
        assert result['isError'] is True
        assert _payload(result)['error']['code'] == 'VALIDATION_ERROR'
        assert company_settings.service_contract_settings == before


@pytest.mark.django_db
class TestProposalMcpContractMarkdown:
    @pytest.mark.parametrize(
        ('modality', 'variant', 'source_key', 'markdown_key', 'initial_params'),
        [
            ('single', 'combined', 'contract_source', 'custom_contract_markdown', {
                'client_cedula': '900123456',
            }),
            ('split', 'product', 'product_contract_source', 'product_custom_contract_markdown', {
                'client_cedula': '900123456',
                'service_contract_source': 'custom',
                'service_custom_contract_markdown': '# Existing service terms',
            }),
        ],
    )
    def test_custom_contract_markdown_round_trips_in_its_own_variant(
        self, api_client, proposals_token, proposal, modality, variant, source_key, markdown_key,
        initial_params,
    ):
        """Fails if custom contract text is written to or read from a different contract variant."""
        proposal.status = BusinessProposal.Status.NEGOTIATING
        proposal.contract_modality = modality
        proposal.contract_params = initial_params
        proposal.save(update_fields=['status', 'contract_modality', 'contract_params'])
        markdown = f'# {variant.title()} contractual scope'

        updated = _call(api_client, proposals_token, 'update_proposal_contract', {
            'proposal_id': proposal.pk,
            'variant': variant,
            'contract_params': {source_key: 'custom', markdown_key: markdown},
        })
        read = _call(api_client, proposals_token, 'read_proposal_contract_markdown', {
            'proposal_id': proposal.pk, 'variant': variant,
        })

        proposal.refresh_from_db()
        assert updated['isError'] is False
        assert proposal.contract_params[markdown_key] == markdown
        assert read['isError'] is False
        assert _payload(read)['markdown'].strip() == markdown

    def test_custom_service_contract_appends_generated_conditions_after_custom_prose(
        self, api_client, proposals_token, proposal,
    ):
        """Fails if the service read drops custom prose or its automatic economic conditions."""
        markdown = '# Service contractual scope'
        proposal.status = BusinessProposal.Status.NEGOTIATING
        proposal.contract_modality = 'split'
        proposal.contract_params = {
            'client_cedula': '900123456',
            'product_contract_source': 'custom',
            'product_custom_contract_markdown': '# Existing product terms',
        }
        proposal.save(update_fields=['status', 'contract_modality', 'contract_params'])

        updated = _call(api_client, proposals_token, 'update_proposal_contract', {
            'proposal_id': proposal.pk,
            'variant': 'service',
            'contract_params': {
                'service_contract_source': 'custom',
                'service_custom_contract_markdown': markdown,
            },
        })
        read = _call(api_client, proposals_token, 'read_proposal_contract_markdown', {
            'proposal_id': proposal.pk, 'variant': 'service',
        })

        proposal.refresh_from_db()
        rendered = _payload(read)['markdown'].strip()
        assert updated['isError'] is False
        assert proposal.contract_params['service_custom_contract_markdown'] == markdown
        assert read['isError'] is False
        assert rendered.startswith(f'{markdown}\n\n### Condiciones particulares del servicio')
        assert '**Condiciones de renovación**' in rendered

    def test_service_edit_preserves_product_custom_markdown(
        self, api_client, proposals_token, proposal,
    ):
        """Fails if a service contract update overwrites the product contract custom Markdown."""
        product_markdown = '# Product terms stay intact'
        proposal.status = BusinessProposal.Status.NEGOTIATING
        proposal.contract_modality = 'split'
        proposal.contract_params = {
            'client_cedula': '900123456',
            'product_contract_source': 'custom',
            'product_custom_contract_markdown': product_markdown,
        }
        proposal.save(update_fields=['status', 'contract_modality', 'contract_params'])

        result = _call(api_client, proposals_token, 'update_proposal_contract', {
            'proposal_id': proposal.pk,
            'variant': 'service',
            'contract_params': {
                'service_contract_source': 'custom',
                'service_custom_contract_markdown': '# Service terms',
            },
        })

        proposal.refresh_from_db()
        assert result['isError'] is False
        assert proposal.contract_params['product_custom_contract_markdown'] == product_markdown
        assert proposal.contract_params['service_custom_contract_markdown'] == '# Service terms'

    def test_resetting_one_split_contract_to_default_preserves_the_other_markdown(
        self, api_client, proposals_token, proposal,
    ):
        """Fails if restoring a product template deletes the independent service custom text."""
        service_markdown = '# Service terms remain private'
        proposal.status = BusinessProposal.Status.NEGOTIATING
        proposal.contract_modality = 'split'
        proposal.contract_params = {
            'client_cedula': '900123456', 'contractor_nit': '900123456-7',
            'product_contract_source': 'custom',
            'product_custom_contract_markdown': '# Product terms',
            'service_contract_source': 'custom',
            'service_custom_contract_markdown': service_markdown,
        }
        proposal.save(update_fields=['status', 'contract_modality', 'contract_params'])

        result = _call(api_client, proposals_token, 'update_proposal_contract', {
            'proposal_id': proposal.pk, 'variant': 'product',
            'contract_params': {'product_contract_source': 'default'},
        })

        proposal.refresh_from_db()
        assert result['isError'] is False
        assert proposal.contract_params['product_contract_source'] == 'default'
        assert proposal.contract_params['service_custom_contract_markdown'] == service_markdown

    def test_single_contract_rejects_the_service_variant(
        self, api_client, proposals_token, proposal,
    ):
        """Fails if the MCP edits a service document that does not exist in a single closing."""
        proposal.status = BusinessProposal.Status.NEGOTIATING
        proposal.contract_modality = 'single'
        proposal.contract_params = {'client_cedula': '900123456'}
        proposal.save(update_fields=['status', 'contract_modality', 'contract_params'])

        result = _call(api_client, proposals_token, 'update_proposal_contract', {
            'proposal_id': proposal.pk,
            'variant': 'service',
            'contract_params': {
                'service_contract_source': 'custom',
                'service_custom_contract_markdown': '# Inactive contract',
            },
        })

        assert result['isError'] is True
        assert _payload(result)['error']['code'] == 'INACTIVE_VARIANT'
