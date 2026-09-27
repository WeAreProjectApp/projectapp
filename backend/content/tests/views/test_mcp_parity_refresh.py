"""Behavior checks for fields and workflows found during the MCP parity pass."""
import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from accounts.models import Project
from accounts.services import proposal_client_service
from content.models import (
    BlogPost,
    BusinessProposal,
    CommunicationThread,
    Document,
    DocumentType,
    IncomeRecord,
    McpConnector,
)
from content.services import accounting_service, diagnostic_service


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mute_accounting_notifications():
    with patch.object(accounting_service, '_notify'):
        yield


def activate_connector(slug):
    connector, _ = McpConnector.objects.get_or_create(
        slug=slug,
        defaults={'name': f'{slug.title()} MCP'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def call_tool(api_client, slug, token, name, arguments):
    return api_client.post(
        f'/api/mcp/{slug}/{token}/',
        {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        },
        format='json',
    )


def payload(response):
    return json.loads(response.data['result']['content'][0]['text'])


def make_client(name, email):
    return proposal_client_service.get_or_create_client_for_proposal(
        name=name,
        email=email,
        phone='',
        company='',
    )


@pytest.fixture
def markdown_type():
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown',
        defaults={'name': 'Markdown', 'label': 'Markdown'},
    )
    return document_type


def test_get_blog_post_returns_the_complete_editable_payload(api_client):
    post = BlogPost.objects.create(
        title_es='Paridad MCP',
        title_en='MCP parity',
        slug='paridad-mcp',
        content_json_es={'sections': [{'heading': 'Uno', 'content': 'Texto'}]},
        content_json_en={'sections': [{'heading': 'One', 'content': 'Copy'}]},
        sources=[{'name': 'Fuente', 'url': 'https://example.com'}],
        linkedin_summary_es='Resumen para LinkedIn',
        meta_description_es='Descripción completa',
    )
    token = activate_connector('blog')

    response = call_tool(
        api_client, 'blog', token, 'get_blog_post', {'post_id': post.id},
    )

    result = payload(response)
    assert result['content_json_es'] == post.content_json_es
    assert result['content_json_en'] == post.content_json_en
    assert result['sources'] == post.sources
    assert result['linkedin_summary_es'] == post.linkedin_summary_es
    assert result['meta_description_es'] == post.meta_description_es


def test_create_document_derives_the_client_from_its_project(
    api_client, superuser, markdown_type,
):
    client = make_client('Cliente proyecto', 'doc-project@example.com')
    project = Project.objects.create(name='Portal documental', client=client.user)
    token = activate_connector('documents')

    response = call_tool(api_client, 'documents', token, 'create_document', {
        'title': 'Acta de entrega',
        'markdown': '# Entrega',
        'project_id': project.id,
    })

    result = payload(response)
    document = Document.objects.get(pk=result['id'])
    assert document.client_user_id == client.user_id
    assert result['client_id'] == client.id
    assert result['project_id'] == project.id


def test_create_document_rejects_a_project_from_another_client(
    api_client, superuser, markdown_type,
):
    selected = make_client('Cliente seleccionado', 'doc-selected@example.com')
    owner = make_client('Dueño proyecto', 'doc-owner@example.com')
    project = Project.objects.create(name='Proyecto ajeno', client=owner.user)
    token = activate_connector('documents')

    response = call_tool(api_client, 'documents', token, 'create_document', {
        'title': 'Documento inválido',
        'markdown': '# No guardar',
        'client_id': selected.id,
        'project_id': project.id,
    })

    assert response.data['result']['isError'] is True
    assert not Document.objects.filter(title='Documento inválido').exists()


def test_list_documents_filters_by_client(
    api_client, superuser, markdown_type,
):
    selected = make_client('Cliente visible', 'doc-visible@example.com')
    other = make_client('Cliente oculto', 'doc-hidden@example.com')
    selected_document = Document.objects.create(
        title='Documento visible', document_type=markdown_type,
        client_user=selected.user,
    )
    Document.objects.create(
        title='Documento oculto', document_type=markdown_type,
        client_user=other.user,
    )
    token = activate_connector('documents')

    response = call_tool(api_client, 'documents', token, 'list_documents', {
        'client_id': selected.id,
    })

    assert [row['id'] for row in payload(response)['results']] == [
        selected_document.id,
    ]


def test_update_document_unlinks_project_when_client_changes(
    api_client, superuser, markdown_type,
):
    original = make_client('Cliente original', 'doc-original@example.com')
    replacement = make_client('Cliente nuevo', 'doc-new@example.com')
    project = Project.objects.create(name='Proyecto original', client=original.user)
    document = Document.objects.create(
        title='Documento reasignado',
        document_type=markdown_type,
        client_user=original.user,
        project=project,
    )
    token = activate_connector('documents')

    response = call_tool(api_client, 'documents', token, 'update_document', {
        'document_id': document.id,
        'client_id': replacement.id,
    })

    assert response.data['result']['isError'] is False
    document.refresh_from_db()
    assert document.client_user_id == replacement.user_id
    assert document.project_id is None


def test_list_clients_does_not_classify_a_client_with_a_thread_as_orphan(
    api_client,
):
    client = make_client('Cliente comunicado', 'client-thread@example.com')
    CommunicationThread.objects.create(client=client, title='Seguimiento')
    token = activate_connector('clients')

    response = call_tool(api_client, 'clients', token, 'list_clients', {
        'orphans': True,
    })

    assert client.id not in {row['id'] for row in payload(response)['results']}


def test_update_diagnostic_accepts_current_identity_fields(api_client, superuser):
    original = make_client('Cliente diagnóstico', 'diag-original@example.com')
    replacement = make_client('Cliente reasignado', 'diag-new@example.com')
    diagnostic = diagnostic_service.create_diagnostic(
        client=original,
        language='es',
        title='Diagnóstico original',
        created_by=superuser,
    )
    token = activate_connector('diagnostics')

    response = call_tool(api_client, 'diagnostics', token, 'update_diagnostic', {
        'diagnostic_id': diagnostic.id,
        'client_id': replacement.id,
        'slug': 'diagnostico-reasignado',
        'expires_at': '2026-09-30T18:00:00Z',
    })

    assert response.data['result']['isError'] is False
    diagnostic.refresh_from_db()
    assert diagnostic.client_id == replacement.id
    assert diagnostic.slug == 'diagnostico-reasignado'
    assert diagnostic.expires_at.isoformat() == '2026-09-30T18:00:00+00:00'


def test_create_proposal_persists_current_commercial_metadata(api_client):
    """Fails if MCP creation ignores an explicit welcome-video preference."""
    token = activate_connector('proposals')

    response = call_tool(api_client, 'proposals', token, 'create_proposal', {
        'title': 'Propuesta internacional',
        'client_name': 'Acme Inc.',
        'project_type': 'other',
        'project_type_custom': 'Marketplace especializado',
        'market_type': 'other',
        'market_type_custom': 'B2B2C',
        'nationality': 'USA',
        'show_contract_terms': False,
        'show_explainer_video': False,
        'sections': {'general': {'clientName': 'Acme Inc.'}},
    })

    assert response.data['result']['isError'] is False
    proposal = BusinessProposal.objects.get(title='Propuesta internacional')
    assert proposal.project_type_custom == 'Marketplace especializado'
    assert proposal.market_type_custom == 'B2B2C'
    assert proposal.nationality == 'USA'
    assert proposal.show_contract_terms is False
    assert proposal.show_explainer_video is False


def test_create_proposal_defaults_welcome_video_visible(api_client):
    """Fails if MCP creation hides the welcome video when the preference is omitted."""
    token = activate_connector('proposals')

    response = call_tool(api_client, 'proposals', token, 'create_proposal', {
        'title': 'Propuesta con video predeterminado',
        'client_name': 'Cliente predeterminado',
        'sections': {'general': {'clientName': 'Cliente predeterminado'}},
    })

    assert response.data['result']['isError'] is False
    proposal = BusinessProposal.objects.get(
        title='Propuesta con video predeterminado',
    )
    assert proposal.show_explainer_video is True


def test_update_proposal_persists_current_commercial_metadata(api_client):
    """Fails if MCP updates discard an explicit welcome-video preference."""
    proposal = BusinessProposal.objects.create(
        title='Propuesta local',
        client_name='Acme',
        nationality='COL',
    )
    token = activate_connector('proposals')

    response = call_tool(api_client, 'proposals', token, 'update_proposal', {
        'proposal_id': proposal.id,
        'title': proposal.title,
        'client_name': proposal.client_name,
        'project_type_custom': 'Sistema regulado',
        'market_type_custom': 'Exportación',
        'nationality': 'EXT',
        'show_contract_terms': False,
        'show_explainer_video': False,
        'sections': {'general': {'clientName': proposal.client_name}},
    })

    assert response.data['result']['isError'] is False
    proposal.refresh_from_db()
    assert proposal.project_type_custom == 'Sistema regulado'
    assert proposal.market_type_custom == 'Exportación'
    assert proposal.nationality == 'EXT'
    assert proposal.show_contract_terms is False
    assert proposal.show_explainer_video is False


def test_update_proposal_keeps_welcome_video_preference_when_omitted(api_client):
    """Fails if an MCP update resets a hidden welcome video that its payload omits."""
    proposal = BusinessProposal.objects.create(
        title='Propuesta sin video',
        client_name='Acme',
        show_explainer_video=False,
    )
    token = activate_connector('proposals')

    response = call_tool(api_client, 'proposals', token, 'update_proposal', {
        'proposal_id': proposal.id,
        'title': proposal.title,
        'client_name': proposal.client_name,
        'sections': {'general': {'clientName': proposal.client_name}},
    })

    assert response.data['result']['isError'] is False
    proposal.refresh_from_db()
    assert proposal.show_explainer_video is False


def test_update_proposal_honors_an_explicit_client_reference(api_client):
    original = make_client('Cliente original', 'proposal-old@example.com')
    replacement = make_client('Cliente correcto', 'proposal-new@example.com')
    proposal = BusinessProposal.objects.create(
        title='Propuesta reasignable',
        client=original,
        client_name='Cliente original',
        client_email='proposal-old@example.com',
    )
    token = activate_connector('proposals')

    response = call_tool(api_client, 'proposals', token, 'update_proposal', {
        'proposal_id': proposal.id,
        'title': proposal.title,
        'client_name': 'Este snapshot no debe ganar',
        'client_id': replacement.id,
        'sections': {'general': {'clientName': 'Cliente correcto'}},
    })

    assert response.data['result']['isError'] is False
    proposal.refresh_from_db()
    assert proposal.client_id == replacement.id
    assert proposal.client_email == 'proposal-new@example.com'


def test_duplicate_proposal_copies_current_commercial_metadata(api_client):
    """Fails if MCP duplication resets a source proposal's welcome-video preference."""
    original = BusinessProposal.objects.create(
        title='Propuesta base',
        client_name='Acme',
        project_type='other',
        project_type_custom='Aplicación de nicho',
        market_type='other',
        market_type_custom='Gobierno',
        show_contract_terms=False,
        show_explainer_video=False,
    )
    token = activate_connector('proposals')

    response = call_tool(api_client, 'proposals', token, 'duplicate_proposal', {
        'proposal_id': original.id,
    })

    assert response.data['result']['isError'] is False
    duplicate = BusinessProposal.objects.get(title='Propuesta base (copia)')
    assert duplicate.project_type_custom == original.project_type_custom
    assert duplicate.market_type_custom == original.market_type_custom
    assert duplicate.show_contract_terms is False
    assert duplicate.show_explainer_video is False


def test_create_hosting_income_returns_its_covered_period(
    api_client, superuser,
):
    token = activate_connector('accounting')

    response = call_tool(api_client, 'accounting', token, 'create_income', {
        'concept': 'Hosting anual 2026',
        'kind': 'expected',
        'period_date': '2026-01',
        'period_start': '2026-01',
        'period_end': '2026-12-31',
        'period_cadence': 'annual',
        'total_amount': '1200000.00',
        'origin': 'hosting',
    })

    result = payload(response)
    assert response.data['result']['isError'] is False
    assert result['period_start'] == '2026-01-01'
    assert result['period_end'] == '2026-12-31'
    assert result['period_cadence'] == 'annual'


def test_settle_income_registers_a_partial_payment(
    api_client, superuser, make_income,
):
    income = make_income(
        total_amount=Decimal('1000.00'),
        gustavo_amount=Decimal('500.00'),
        carlos_amount=Decimal('500.00'),
    )
    token = activate_connector('accounting')

    response = call_tool(api_client, 'accounting', token, 'settle_income', {
        'record_id': income.id,
        'concept': 'Abono parcial',
        'period_date': '2026-08-26',
        'total_amount': '400.00',
    })

    result = payload(response)
    assert response.data['result']['isError'] is False
    assert result['income']['payment_status'] == 'partial'
    assert result['income']['paid_amount'] == '400.00'
    assert result['income']['pending_amount'] == '600.00'
    assert result['liquid']['expected_income'] == income.id


def test_get_income_detail_includes_partial_payment_history(
    api_client, superuser, make_income,
):
    income = make_income(
        total_amount=Decimal('1000.00'),
        gustavo_amount=Decimal('500.00'),
        carlos_amount=Decimal('500.00'),
    )
    token = activate_connector('accounting')
    call_tool(api_client, 'accounting', token, 'settle_income', {
        'record_id': income.id,
        'concept': 'Primer abono',
        'period_date': '2026-08-26',
        'destination': 'pocket',
        'total_amount': '250.00',
    })

    response = call_tool(api_client, 'accounting', token, 'get_income_detail', {
        'record_id': income.id,
    })

    result = payload(response)
    assert result['income']['payment_status'] == 'partial'
    assert result['liquid'][0]['total_amount'] == '250.00'
    assert result['liquid'][0]['movement']['amount'] == '250.00'


def test_settle_income_rejects_a_liquid_record(
    api_client, superuser, make_income,
):
    income = make_income(kind=IncomeRecord.Kind.LIQUID)
    token = activate_connector('accounting')

    response = call_tool(api_client, 'accounting', token, 'settle_income', {
        'record_id': income.id,
        'concept': 'Pago imposible',
        'period_date': '2026-08-26',
        'total_amount': '100.00',
    })

    assert response.data['result']['isError'] is True
    assert income.liquid_records.count() == 0


def test_bulk_settle_incomes_creates_one_shared_movement(
    api_client, superuser, make_income,
):
    first = make_income(
        concept='Factura uno',
        total_amount=Decimal('500.00'),
        gustavo_amount=Decimal('250.00'),
        carlos_amount=Decimal('250.00'),
    )
    second = make_income(
        concept='Factura dos',
        total_amount=Decimal('300.00'),
        gustavo_amount=Decimal('150.00'),
        carlos_amount=Decimal('150.00'),
    )
    token = activate_connector('accounting')

    response = call_tool(api_client, 'accounting', token, 'bulk_settle_incomes', {
        'allocations': [
            {'income_id': first.id, 'amount': '500.00'},
            {'income_id': second.id, 'amount': '100.00'},
        ],
        'total_amount': '600.00',
        'period_date': '2026-08-26',
        'notes': 'Transferencia conjunta',
    })

    result = payload(response)
    assert response.data['result']['isError'] is False
    assert result['updated'] == 2
    assert result['movement']['amount'] == '600.00'
    assert len(result['movement']['allocations']) == 2
    movement_ids = {
        row['pocket_movement']
        for row in result['results']
        if row['kind'] == IncomeRecord.Kind.LIQUID
    }
    assert movement_ids == {result['movement']['id']}


def test_bulk_settle_incomes_rejects_a_repeated_income(
    api_client, superuser, make_income,
):
    income = make_income()
    token = activate_connector('accounting')

    response = call_tool(api_client, 'accounting', token, 'bulk_settle_incomes', {
        'allocations': [
            {'income_id': income.id, 'amount': '100.00'},
            {'income_id': income.id, 'amount': '100.00'},
        ],
        'total_amount': '200.00',
        'period_date': '2026-08-26',
    })

    assert response.data['result']['isError'] is True
    assert income.liquid_records.count() == 0
