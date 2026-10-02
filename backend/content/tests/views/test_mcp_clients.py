"""Tests for the Clients MCP connector HTTP endpoint."""
import json
from datetime import date
from decimal import Decimal

import pytest

from accounts.models import (
    BugReport,
    ChangeRequest,
    Deliverable,
    HostingSubscription,
    Project,
    ProjectPhase,
)
from accounts.services import proposal_client_service
from content.models import BusinessProposal, McpConnector


@pytest.fixture
def clients_connector(db):
    connector, _ = McpConnector.objects.get_or_create(
        slug='clients', defaults={'name': 'Gestor de Clientes'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    return connector, token


def _url(token):
    return f'/api/mcp/clients/{token}/'


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _call(api_client, token, name, arguments):
    return api_client.post(
        _url(token),
        _rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )


def _make_client(name='ACME SAS', email='', phone='', company=''):
    return proposal_client_service.get_or_create_client_for_proposal(
        name=name, email=email, phone=phone, company=company,
    )


def _create_project_with_aggregates(profile):
    project = Project.objects.create(name='Nested project', client=profile.user)
    deliverable = Deliverable.objects.create(
        project=project,
        title='Nested deliverable',
        category=Deliverable.CATEGORY_OTHER,
        uploaded_by=profile.user,
    )
    proposal = BusinessProposal.objects.create(
        title='Nested proposal',
        client=profile,
        client_name='Nested client',
        total_investment=Decimal('765432.10'),
        deliverable=deliverable,
    )
    ProjectPhase.objects.create(project=project, business_proposal=proposal, order=1)
    BugReport.objects.create(
        project=project,
        reported_by=profile.user,
        title='Nested open bug',
        status=BugReport.STATUS_REPORTED,
    )
    ChangeRequest.objects.create(
        project=project,
        created_by=profile.user,
        title='Nested pending change',
        status=ChangeRequest.STATUS_PENDING,
    )
    HostingSubscription.objects.create(
        project=project,
        plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal('41152.00'),
        effective_monthly_amount=Decimal('41152.00'),
        billing_amount=Decimal('123456.00'),
        status=HostingSubscription.STATUS_ACTIVE,
        start_date=date(2026, 10, 1),
        next_billing_date=date(2026, 11, 15),
    )
    return project, proposal


@pytest.mark.django_db
class TestClientsMcpToolList:
    def test_exposes_the_six_tools(self, api_client, clients_connector):
        _, token = clients_connector
        response = api_client.post(_url(token), _rpc('tools/list'), format='json')
        names = [t['name'] for t in response.data['result']['tools']]
        assert names == [
            'search_clients', 'list_clients', 'get_client',
            'create_client', 'update_client', 'delete_client',
        ]


@pytest.mark.django_db
class TestClientsMcpReads:
    def test_search_matches_by_company(self, api_client, clients_connector):
        _make_client(name='Juan', company='Panadería Bogotá')
        _, token = clients_connector
        response = _call(api_client, token, 'search_clients', {'q': 'Panadería'})
        text = response.data['result']['content'][0]['text']
        assert 'Panadería Bogotá' in text

    def test_list_clients_returns_count(self, api_client, clients_connector):
        _make_client(name='Uno', email='uno@x.com')
        _make_client(name='Dos', email='dos@x.com')
        _, token = clients_connector
        response = _call(api_client, token, 'list_clients', {})
        assert response.data['result']['isError'] is False
        assert '"count"' in response.data['result']['content'][0]['text']

    def test_get_client_nests_related(self, api_client, clients_connector):
        """Fails if MCP client details lose concrete nested project aggregates."""
        profile = _make_client(name='Detalle', email='detalle@x.com')
        project, proposal = _create_project_with_aggregates(profile)
        _, token = clients_connector
        response = _call(api_client, token, 'get_client', {'client_id': profile.pk})

        assert response.data['result']['isError'] is False
        payload = json.loads(response.data['result']['content'][0]['text'])
        row = next(item for item in payload['projects'] if item['id'] == project.pk)
        assert {
            'proposal_count': len(payload['proposals']),
            'proposal_id': payload['proposals'][0]['id'],
            'proposal_title': payload['proposals'][0]['title'],
            'diagnostics': payload['diagnostics'],
        } == {
            'proposal_count': 1,
            'proposal_id': proposal.pk,
            'proposal_title': 'Nested proposal',
            'diagnostics': [],
        }
        assert {
            'proposal_id': row['proposal_id'],
            'proposal_title': row['proposal_title'],
            'bugs_open_count': row['bugs_open_count'],
            'changes_pending_count': row['changes_pending_count'],
            'phases_total_amount': row['phases_total_amount'],
            'next_hosting_payment': row['next_hosting_payment'],
        } == {
            'proposal_id': proposal.pk,
            'proposal_title': 'Nested proposal',
            'bugs_open_count': 1,
            'changes_pending_count': 1,
            'phases_total_amount': '765432.10',
            'next_hosting_payment': {
                'date': '2026-11-15',
                'amount': '123456.00',
                'plan': HostingSubscription.PLAN_QUARTERLY,
            },
        }

    def test_get_client_returns_the_canonical_billing_customer(self, api_client, clients_connector):
        """Fails if the MCP client read drops billing identity or address used by cobros."""
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Laura Ramírez',
            email='mcp-laura@example.com',
            cedula='1049654583',
            address='Carrera 7 # 72-41, Bogotá',
            billing_code='LAURARAM',
        )
        _, token = clients_connector

        response = _call(api_client, token, 'get_client', {'client_id': profile.pk})

        assert response.data['result']['isError'] is False
        payload = json.loads(response.data['result']['content'][0]['text'])
        assert payload['billing_code'] == 'LAURARAM'
        assert payload['billing_customer'] == {
            'name': 'Laura Ramírez',
            'email': 'mcp-laura@example.com',
            'identification': '1049654583',
            'identification_type': 'CC',
            'contact_name': 'Laura Ramírez',
            'address': 'Carrera 7 # 72-41, Bogotá',
        }

    def test_get_missing_client_errors(self, api_client, clients_connector):
        _, token = clients_connector
        response = _call(api_client, token, 'get_client', {'client_id': 999999})
        assert response.data['result']['isError'] is True


@pytest.mark.django_db
class TestClientsMcpWrites:
    def test_create_requires_some_identifier(self, api_client, clients_connector):
        _, token = clients_connector
        response = _call(api_client, token, 'create_client', {})
        assert response.data['result']['isError'] is True

    def test_create_client(self, api_client, clients_connector):
        _, token = clients_connector
        response = _call(api_client, token, 'create_client', {
            'name': 'Nuevo Cliente', 'email': 'nuevo@x.com',
        })
        assert response.data['result']['isError'] is False
        text = response.data['result']['content'][0]['text']
        assert 'Nuevo Cliente' in text

    def test_update_client(self, api_client, clients_connector):
        profile = _make_client(name='Viejo', email='viejo@x.com')
        _, token = clients_connector
        response = _call(api_client, token, 'update_client', {
            'client_id': profile.pk, 'company': 'Empresa X',
        })
        assert response.data['result']['isError'] is False
        assert 'Empresa X' in response.data['result']['content'][0]['text']

    def test_update_requires_a_field(self, api_client, clients_connector):
        profile = _make_client(name='Solo', email='solo@x.com')
        _, token = clients_connector
        response = _call(api_client, token, 'update_client', {'client_id': profile.pk})
        assert response.data['result']['isError'] is True

    def test_delete_orphan_client(self, api_client, clients_connector):
        profile = _make_client(name='Huérfano', email='orphan@x.com')
        _, token = clients_connector
        response = _call(api_client, token, 'delete_client', {'client_id': profile.pk})
        assert response.data['result']['isError'] is False


@pytest.fixture
def superuser_client(api_client, django_user_model):
    user = django_user_model.objects.create_user(
        username='root_clients_test', password='x', is_staff=True, is_superuser=True,
    )
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
class TestClientsConnectorPanel:
    def test_panel_lists_clients_connector_with_tools(self, superuser_client, clients_connector):
        response = superuser_client.get('/api/mcp-connectors/')
        entry = next(c for c in response.data if c['slug'] == 'clients')
        tool_names = [t['name'] for t in entry['tools']]
        assert 'search_clients' in tool_names
        assert 'create_client' in tool_names
