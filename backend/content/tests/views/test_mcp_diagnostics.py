"""Tests for the Diagnostics MCP connector HTTP endpoint."""
import json
from unittest.mock import patch

import pytest

from accounts.services import proposal_client_service
from content.models import (
    DiagnosticChangeLog,
    McpConnector,
    WebAppDiagnostic,
)
from content.services import diagnostic_service
from content.tests.mcp_confirmation_helpers import call_confirmed, confirmed_payload


@pytest.fixture
def diagnostics_connector(db):
    connector, _ = McpConnector.objects.get_or_create(
        slug='diagnostics', defaults={'name': 'Gestor de Diagnósticos'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector, connector.generate_token()


@pytest.fixture
def a_client(db):
    return proposal_client_service.get_or_create_client_for_proposal(
        name='Cliente Diag', email='diagcli@x.com', phone='', company='',
    )


@pytest.fixture
def b_client(db):
    return proposal_client_service.get_or_create_client_for_proposal(
        name='Cliente Dos', email='diagcli2@x.com', phone='', company='',
    )


@pytest.fixture
def seeded_diagnostic(a_client):
    return diagnostic_service.create_diagnostic(
        client=a_client, language='es', title='Diag seed', created_by=None,
    )


def _url(token):
    return f'/api/mcp/diagnostics/{token}/'


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _call(api_client, token, name, arguments):
    return api_client.post(
        _url(token), _rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )


def _call_confirmed(api_client, token, name, arguments):
    return call_confirmed(api_client, _url(token), _rpc, name, arguments)


def _payload(response):
    return confirmed_payload(response)


@pytest.mark.django_db
class TestDiagnosticsMcp:
    def test_tool_list(self, api_client, diagnostics_connector):
        _, token = diagnostics_connector
        response = api_client.post(_url(token), _rpc('tools/list'), format='json')
        names = [t['name'] for t in response.data['result']['tools']]
        for expected in (
            'list_diagnostics', 'create_diagnostic', 'update_diagnostic_status',
            'send_initial', 'list_diagnostic_templates', 'delete_diagnostic',
        ):
            assert expected in names

    def test_create_requires_client(self, api_client, diagnostics_connector):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'create_diagnostic', {})
        assert response.data['result']['isError'] is True

    def test_create_and_get(self, api_client, diagnostics_connector, a_client):
        _, token = diagnostics_connector
        created = _call(api_client, token, 'create_diagnostic', {
            'client_id': a_client.pk, 'title': 'Diag inicial',
        })
        assert created.data['result']['isError'] is False
        diagnostic = WebAppDiagnostic.objects.get(client=a_client)
        got = _call(api_client, token, 'get_diagnostic', {'diagnostic_id': diagnostic.id})
        assert got.data['result']['isError'] is False

    def test_status_transition_rejects_invalid(self, api_client, diagnostics_connector, a_client):
        diagnostic = WebAppDiagnostic.objects.create(client=a_client, status='draft')
        _, token = diagnostics_connector
        # draft → accepted is not an allowed transition.
        response = _call(api_client, token, 'update_diagnostic_status', {
            'diagnostic_id': diagnostic.id, 'status': 'accepted',
        })
        assert response.data['result']['isError'] is True

    def test_delete_is_unrestricted(self, api_client, diagnostics_connector, a_client):
        diagnostic = WebAppDiagnostic.objects.create(client=a_client, status='sent')
        _, token = diagnostics_connector
        response = _call_confirmed(
            api_client, token, 'delete_diagnostic', {'diagnostic_id': diagnostic.id},
        )
        assert response.data['result']['isError'] is False
        assert not WebAppDiagnostic.objects.filter(pk=diagnostic.id).exists()

    def test_list_templates(self, api_client, diagnostics_connector):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'list_diagnostic_templates', {})
        assert response.data['result']['isError'] is False


@pytest.mark.django_db
class TestDiagnosticsMcpHandlers:
    def test_list_filters_by_status(self, api_client, diagnostics_connector, a_client):
        WebAppDiagnostic.objects.create(client=a_client, status='draft')
        WebAppDiagnostic.objects.create(client=a_client, status='sent')
        _, token = diagnostics_connector
        response = _call(api_client, token, 'list_diagnostics', {'status': 'sent'})
        assert len(_payload(response)['results']) == 1

    def test_list_filters_by_client(
        self, api_client, diagnostics_connector, a_client, b_client,
    ):
        WebAppDiagnostic.objects.create(client=a_client, status='draft')
        WebAppDiagnostic.objects.create(client=b_client, status='draft')
        _, token = diagnostics_connector
        response = _call(api_client, token, 'list_diagnostics', {'client': b_client.pk})
        assert len(_payload(response)['results']) == 1

    def test_get_unknown_diagnostic_errors(self, api_client, diagnostics_connector):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'get_diagnostic', {'diagnostic_id': 999999})
        assert response.data['result']['isError'] is True

    def test_create_with_unknown_client_errors(self, api_client, diagnostics_connector):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'create_diagnostic', {'client_id': 999999})
        assert response.data['result']['isError'] is True

    def test_create_normalizes_unknown_language_to_spanish(
        self, api_client, diagnostics_connector, a_client,
    ):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'create_diagnostic', {
            'client_id': a_client.pk, 'language': 'fr',
        })
        assert response.data['result']['isError'] is False
        assert WebAppDiagnostic.objects.get(client=a_client).language == 'es'

    def test_update_changes_title_and_logs_change(
        self, api_client, diagnostics_connector, seeded_diagnostic,
    ):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'update_diagnostic', {
            'diagnostic_id': seeded_diagnostic.id, 'title': 'Título nuevo',
        })
        assert response.data['result']['isError'] is False
        seeded_diagnostic.refresh_from_db()
        assert seeded_diagnostic.title == 'Título nuevo'
        assert seeded_diagnostic.change_logs.filter(
            change_type=DiagnosticChangeLog.ChangeType.UPDATED,
        ).exists()

    def test_update_without_fields_errors(
        self, api_client, diagnostics_connector, seeded_diagnostic,
    ):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'update_diagnostic', {
            'diagnostic_id': seeded_diagnostic.id,
        })
        assert response.data['result']['isError'] is True

    def test_update_with_invalid_payload_errors(
        self, api_client, diagnostics_connector, seeded_diagnostic,
    ):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'update_diagnostic', {
            'diagnostic_id': seeded_diagnostic.id,
            'investment_amount': 'no-es-numero',
        })
        assert response.data['result']['isError'] is True

    def test_update_propagates_client_profile_when_flagged(
        self, api_client, diagnostics_connector, seeded_diagnostic, a_client,
    ):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'update_diagnostic', {
            'diagnostic_id': seeded_diagnostic.id,
            'client_phone': '3001112233',
            'propagate_client_updates': True,
        })
        assert response.data['result']['isError'] is False
        a_client.refresh_from_db()
        assert a_client.phone == '3001112233'

    def test_update_section_changes_title_and_logs(
        self, api_client, diagnostics_connector, seeded_diagnostic,
    ):
        section = seeded_diagnostic.sections.first()
        _, token = diagnostics_connector
        response = _call(api_client, token, 'update_diagnostic_section', {
            'diagnostic_id': seeded_diagnostic.id,
            'section_id': section.id,
            'title': 'Sección renombrada',
        })
        assert _payload(response)['title'] == 'Sección renombrada'
        assert seeded_diagnostic.change_logs.filter(
            change_type=DiagnosticChangeLog.ChangeType.SECTION_UPDATED,
        ).exists()

    def test_update_section_unknown_id_errors(
        self, api_client, diagnostics_connector, seeded_diagnostic,
    ):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'update_diagnostic_section', {
            'diagnostic_id': seeded_diagnostic.id,
            'section_id': 999999,
            'title': 'X',
        })
        assert response.data['result']['isError'] is True

    def test_bulk_update_applies_valid_and_skips_unknown(
        self, api_client, diagnostics_connector, seeded_diagnostic,
    ):
        section = seeded_diagnostic.sections.first()
        _, token = diagnostics_connector
        response = _call(api_client, token, 'bulk_update_diagnostic_sections', {
            'diagnostic_id': seeded_diagnostic.id,
            'sections': [
                {'id': section.id, 'title': 'Bulk actualizada'},
                {'id': 999999, 'title': 'Fantasma'},
            ],
        })
        assert response.data['result']['isError'] is False
        section.refresh_from_db()
        assert section.title == 'Bulk actualizada'

    def test_bulk_update_rejects_non_list_payload(
        self, api_client, diagnostics_connector, seeded_diagnostic,
    ):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'bulk_update_diagnostic_sections', {
            'diagnostic_id': seeded_diagnostic.id, 'sections': 'nope',
        })
        assert response.data['result']['isError'] is True

    def test_update_status_applies_valid_transition(
        self, api_client, diagnostics_connector, seeded_diagnostic,
    ):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'update_diagnostic_status', {
            'diagnostic_id': seeded_diagnostic.id, 'status': 'sent',
        })
        assert response.data['result']['isError'] is False
        seeded_diagnostic.refresh_from_db()
        assert seeded_diagnostic.status == 'sent'

    @patch(
        'content.services.diagnostic_email_service.DiagnosticEmailService.send_initial_to_client',
        return_value=True,
    )
    def test_send_initial_transitions_and_flags_email_ok(
        self, _mock_send, api_client, diagnostics_connector, seeded_diagnostic,  # noqa: PT019
    ):
        _, token = diagnostics_connector
        response = _call_confirmed(api_client, token, 'send_initial', {
            'diagnostic_id': seeded_diagnostic.id,
        })
        assert _payload(response)['email_ok'] is True
        seeded_diagnostic.refresh_from_db()
        assert seeded_diagnostic.status == 'sent'

    @patch(
        'content.services.diagnostic_email_service.DiagnosticEmailService.send_initial_to_client',
        side_effect=Exception('SMTP down'),
    )
    def test_send_initial_flags_email_failure(
        self, _mock_send, api_client, diagnostics_connector, seeded_diagnostic,  # noqa: PT019
    ):
        _, token = diagnostics_connector
        response = _call_confirmed(api_client, token, 'send_initial', {
            'diagnostic_id': seeded_diagnostic.id,
        })
        assert _payload(response)['email_ok'] is False

    def test_mark_in_analysis_moves_sent_to_negotiating(
        self, api_client, diagnostics_connector, a_client,
    ):
        diagnostic = WebAppDiagnostic.objects.create(client=a_client, status='sent')
        _, token = diagnostics_connector
        response = _call(api_client, token, 'mark_in_analysis', {
            'diagnostic_id': diagnostic.id,
        })
        assert response.data['result']['isError'] is False
        diagnostic.refresh_from_db()
        assert diagnostic.status == 'negotiating'

    def test_get_template_returns_markdown(self, api_client, diagnostics_connector):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'get_diagnostic_template', {
            'slug': 'diagnostico-aplicacion',
        })
        payload = _payload(response)
        assert payload['slug'] == 'diagnostico-aplicacion'
        assert payload['content_markdown']

    def test_get_template_unknown_slug_errors(self, api_client, diagnostics_connector):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'get_diagnostic_template', {
            'slug': 'no-existe',
        })
        assert response.data['result']['isError'] is True

    def test_get_template_interpolates_pending_investment(
        self, api_client, diagnostics_connector, seeded_diagnostic,
    ):
        _, token = diagnostics_connector
        response = _call(api_client, token, 'get_diagnostic_template', {
            'slug': 'diagnostico-aplicacion',
            'diagnostic_id': seeded_diagnostic.id,
        })
        assert 'pendiente de definir' in _payload(response)['content_markdown']
