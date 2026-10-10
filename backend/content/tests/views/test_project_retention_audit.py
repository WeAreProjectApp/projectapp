"""Global audit of data retained by forced project deletions (panel + MCP)."""
import json
from decimal import Decimal

import pytest
from accounts.models import Deliverable, Project, ProjectPhase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from content.models import (
    BusinessProposal,
    IncomeRecord,
    McpConnector,
    ProjectRetentionContext,
)

pytestmark = pytest.mark.django_db
AUDIT_URL = '/api/projects/retained-data/audit/'


def _income(profile, concept, **fields):
    return IncomeRecord.objects.create(
        concept=concept, kind=IncomeRecord.Kind.EXPECTED, period_date='2026-10-01',
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'), client=profile, **fields,
    )


def _context(profile, admin_user, original_project_id, name):
    return ProjectRetentionContext.objects.create(
        client=profile.user, original_project_id=original_project_id, project_name=name,
        retained_records={}, category_counts={}, created_by=admin_user,
    )


@pytest.fixture
def littigio(admin_user, make_client_profile, proposal):
    profile = make_client_profile(company='Littigio')
    context = _context(profile, admin_user, 9014, 'Littigio anterior')
    still_retained = _income(profile, 'Inicio Fase 1', project=None, retention_context=context)
    # Listed at deletion, no longer carrying the marker (e.g. later adopted).
    adopted = _income(profile, 'Entrega Fase 1')
    deliverable = Deliverable.objects.create(
        project=None, retention_context=context, title='Paquete aprobado',
        uploaded_by=admin_user, category=Deliverable.CATEGORY_DOCUMENTS,
    )
    phase = ProjectPhase.objects.create(project=None, business_proposal=proposal, order=1, retention_context=context)
    BusinessProposal.objects.filter(pk=proposal.pk).update(deliverable=deliverable)
    context.retained_records = {
        'content.incomerecord': [str(still_retained.pk), str(adopted.pk)],
        'accounts.deliverable': [str(deliverable.pk)],
        'accounts.projectphase': [str(phase.pk)],
    }
    context.category_counts = {'content.incomerecord': 2, 'accounts.deliverable': 1, 'accounts.projectphase': 1}
    context.save(update_fields=['retained_records', 'category_counts'])
    return {'profile': profile, 'context': context, 'income': still_retained, 'adopted': adopted,
            'deliverable': deliverable, 'phase': phase, 'proposal': proposal}


def test_audit_requires_staff(api_client, littigio):
    """Fails if anyone outside the staff can read client retention data."""
    response = api_client.get(AUDIT_URL)

    assert response.status_code in (401, 403)


def test_audit_compares_deletion_index_with_live_rows(admin_client, littigio):
    """Fails if the audit trusts the deletion index instead of the rows that still carry the marker."""
    response = admin_client.get(AUDIT_URL)

    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    result = response.data['results'][0]
    assert (result['id'], result['original_project_id'], result['project_name']) == (
        littigio['context'].pk, 9014, 'Littigio anterior',
    )
    assert result['client']['profile_id'] == littigio['profile'].pk
    incomes = next(row for row in result['categories'] if row['model'] == 'content.incomerecord')
    assert (incomes['at_deletion'], incomes['remaining'], incomes['ids']) == (2, 1, [str(littigio['income'].pk)])
    assert result['pending_total'] == 3


def test_audit_lists_proposals_whose_deliverable_or_phase_stayed_retained(admin_client, littigio):
    """Fails if a proposal broken by the deletion is missing from the audit."""
    result = admin_client.get(AUDIT_URL).data['results'][0]

    assert result['proposals'] == [{
        'id': littigio['proposal'].pk, 'title': littigio['proposal'].title,
        'status': littigio['proposal'].status, 'deliverable_id': littigio['deliverable'].pk,
        'phase_ids': [littigio['phase'].pk],
    }]


def test_audit_filters_by_client_profile(admin_client, admin_user, make_client_profile, littigio):
    """Fails if one client's retention leaks into another client's audit."""
    other = make_client_profile(company='Otro cliente')
    _context(other, admin_user, 9099, 'Proyecto ajeno')

    response = admin_client.get(AUDIT_URL, {'client_profile_id': littigio['profile'].pk})

    assert response.data['count'] == 1
    assert [row['project_name'] for row in response.data['results']] == ['Littigio anterior']


def test_audit_rejects_a_non_numeric_client_filter(admin_client, littigio):
    """Fails if an invalid client filter silently returns every client."""
    response = admin_client.get(AUDIT_URL, {'client_profile_id': 'littigio'})

    assert response.status_code == 400
    assert 'client_profile_id' in response.data


def test_audit_integrity_flags_retained_rows_that_regained_a_project(admin_client, littigio):
    """Fails if a write path that bypassed the guard leaves an undetected half-retained row."""
    project = Project.objects.create(name='Littigio', client=littigio['profile'].user)
    IncomeRecord.objects.filter(pk=littigio['income'].pk).update(project=project)

    response = admin_client.get(AUDIT_URL, {'integrity': '1'})

    assert {'model': 'content.incomerecord', 'key': 'incomes', 'issue': 'retained_with_project', 'count': 1} in response.data['integrity']


def test_audit_query_count_does_not_grow_with_contexts(admin_client, admin_user, make_client_profile, littigio):
    """Fails if each retention context adds its own queries (N+1)."""
    admin_client.get(AUDIT_URL)  # warm one-time caches before measuring
    with CaptureQueriesContext(connection) as single:
        admin_client.get(AUDIT_URL)
    for number in range(3):
        profile = make_client_profile(company=f'Cliente {number}')
        context = _context(profile, admin_user, 9100 + number, f'Proyecto {number}')
        _income(profile, f'Ingreso {number}', project=None, retention_context=context)

    with CaptureQueriesContext(connection) as several:
        response = admin_client.get(AUDIT_URL)

    assert response.data['count'] == 4
    assert len(several.captured_queries) == len(single.captured_queries)


@pytest.fixture
def projects_token():
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def test_mcp_tool_returns_the_same_audit(api_client, projects_token, littigio):
    """Fails if the MCP connector cannot measure retained data without the panel session."""
    response = api_client.post(f'/api/mcp/projects/{projects_token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': 'list_project_retention_contexts',
                   'arguments': {'client_profile_id': littigio['profile'].pk}},
    }, format='json')

    result = json.loads(response.data['result']['content'][0]['text'])
    assert result['count'] == 1
    assert result['results'][0]['project_name'] == 'Littigio anterior'


def test_audit_route_is_named_for_the_panel_bridge():
    """Fails if the MCP adapter cannot resolve the audit route by name."""
    assert reverse('panel-projects-retained-data-audit') == AUDIT_URL
