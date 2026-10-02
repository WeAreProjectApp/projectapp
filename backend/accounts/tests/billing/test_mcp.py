"""Behavioral MCP coverage for explicit project-billing context."""
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from accounts.billing_models import (
    BillingContextEvent,
    CollectionAccountContext,
    ProjectHosting,
    ProjectHostingAccountingSource,
)
from accounts.models import Project, ProjectContract, UserProfile
from accounts.services.hosting_context import reconcile_hosting
from content.mcp.common_tools import build_common_tools
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.contracts import MCP_MODEL_CONTRACTS
from content.mcp.platform_billing_tools import PLATFORM_BILLING_TOOLS
from content.mcp.principal import service_actor_for_connector
from content.mcp.protocol import handle_message
from content.mcp.registry import normalize_tools
from content.models import Document, DocumentCollectionAccount, DocumentType, McpConnector


pytestmark = pytest.mark.django_db


def _rpc(name, arguments, msg_id=1):
    return {
        'jsonrpc': '2.0',
        'id': msg_id,
        'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }


def _billing_tools():
    tools = []
    tools.extend(normalize_tools(
        [*PLATFORM_BILLING_TOOLS, *build_common_tools('accounting-billing', lambda: tools)],
        'accounting-billing',
    ))
    return tools


def _call(tools, context, name, arguments):
    with use_mcp_context(context):
        _, response = handle_message(_rpc(name, arguments), tools, context=context)
    return response['result']['structuredContent']


@pytest.fixture
def billing_runtime():
    connector = McpConnector.objects.create(slug='billing-test', name='Cobros de prueba', is_active=True)
    connector.generate_token()
    credential = connector.credentials.get(label='Default')
    actor = service_actor_for_connector(connector)
    return _billing_tools(), McpExecutionContext(
        connector=connector,
        credential=credential,
        request_id='billing-mcp-test',
        actor=actor,
        request=SimpleNamespace(),
    )


def test_mcp_billing_read_rejects_a_client_actor_but_admin_reads_project_options(
    billing_runtime, client_user, project, contract,
):
    """Falla si un cliente puede usar el MCP administrativo o el admin pierde opciones del proyecto."""
    tools, admin_context = billing_runtime
    client_context = McpExecutionContext(
        connector=admin_context.connector,
        credential=admin_context.credential,
        request_id='billing-client-test',
        actor=client_user,
        request=SimpleNamespace(),
    )

    denied = _call(tools, client_context, 'get_project_billing_options', {'project_id': project.pk})
    allowed = _call(tools, admin_context, 'get_project_billing_options', {'project_id': project.pk})

    assert denied['error']['code'] == 'FORBIDDEN'
    assert allowed['project_id'] == project.pk
    assert allowed['contracts'] == [{'id': contract.pk, 'title': 'Contrato A', 'amendments': []}]
    assert allowed['hosting_id'] is None


def test_mcp_confirmation_associates_an_account_to_its_explicit_contract(
    billing_runtime, project, contract, account,
):
    """Falla si confirmar una asociación MCP no deja la cuenta ligada al contrato elegido."""
    tools, context = billing_runtime
    arguments = {
        'project_id': project.pk,
        'account_id': account.pk,
        'payload': {
            'expected_version': 0,
            'reason': 'Contrato firmado verificado',
            'billing_nature': 'contract',
            'contract_id': contract.pk,
            'amendment_id': None,
            'project_hosting_id': None,
            'hosting_payment_id': None,
        },
    }

    preview = _call(tools, context, 'associate_collection_account_context', arguments)
    confirmed = _call(tools, context, 'confirm_action', {'confirmation_id': preview['confirmation_id']})

    context_row = CollectionAccountContext.objects.get(document=account)
    assert preview['confirmation_required'] is True
    assert confirmed['result']['nature'] == 'contract'
    assert context_row.contract_id == contract.pk
    assert context_row.hosting_id is None
    assert context_row.version == 1
    assert BillingContextEvent.objects.get(document=account).reason == 'Contrato firmado verificado'


def test_mcp_confirmation_rejects_contract_from_another_project_without_association(
    billing_runtime, project, account, client_user,
):
    """Falla si MCP puede asociar la cuenta de un proyecto con el contrato de otro proyecto."""
    User = get_user_model()
    foreign_user = User.objects.create_user(username='billing-foreign@example.test')
    UserProfile.objects.create(user=foreign_user, role=UserProfile.ROLE_CLIENT)
    foreign_project = Project.objects.create(name='Proyecto ajeno', client=foreign_user)
    foreign_document = Document.objects.create(
        title='Contrato ajeno', project=foreign_project, client_user=foreign_user,
    )
    foreign_contract = ProjectContract.objects.create(
        project=foreign_project, key='foreign-contract', title='Contrato ajeno', document=foreign_document,
    )
    tools, context = billing_runtime

    preview = _call(tools, context, 'associate_collection_account_context', {
        'project_id': project.pk,
        'account_id': account.pk,
        'payload': {
            'expected_version': 0,
            'reason': 'Intento de cruce',
            'billing_nature': 'contract',
            'contract_id': foreign_contract.pk,
            'amendment_id': None,
            'project_hosting_id': None,
            'hosting_payment_id': None,
        },
    })
    rejected = _call(tools, context, 'confirm_action', {'confirmation_id': preview['confirmation_id']})

    assert rejected['error']['code'] == 'VALIDATION_ERROR'
    assert CollectionAccountContext.objects.filter(document=account).count() == 0


def test_mcp_account_context_rejects_an_account_from_another_project(
    billing_runtime, project, contract,
):
    """Falla si una vista previa asocia la cuenta válida de otro proyecto."""
    User = get_user_model()
    other_user = User.objects.create_user(username='billing-account-owner@example.test')
    UserProfile.objects.create(user=other_user, role=UserProfile.ROLE_CLIENT)
    other = Project.objects.create(name='Proyecto de cuenta ajena', client=other_user)
    document_type, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Cuenta de cobro'})
    other_account = Document.objects.create(title='Cuenta B', project=other, client_user=other_user, document_type=document_type, commercial_status='issued')
    DocumentCollectionAccount.objects.create(document=other_account, customer_name='Titular B')
    tools, context = billing_runtime

    result = _call(tools, context, 'associate_collection_account_context', {
        'project_id': project.pk, 'account_id': other_account.pk,
        'payload': {'expected_version': 0, 'reason': 'Cruce rechazado', 'billing_nature': 'contract',
                    'contract_id': contract.pk, 'amendment_id': None, 'project_hosting_id': None,
                    'hosting_payment_id': None},
    })

    assert result['error']['code'] == 'VALIDATION_ERROR'
    assert CollectionAccountContext.objects.count() == 0
    assert BillingContextEvent.objects.count() == 0
    assert other_account.is_archived is False


def test_mcp_account_context_rejects_commercial_status_input(billing_runtime, project, contract):
    """Falla si el MCP permite cambiar estado comercial al asociar una cuenta de cobro."""
    tools, context = billing_runtime
    document_type, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Cuenta de cobro'})
    account = Document.objects.create(title='Cuenta pactada', project=project, client_user=project.client, document_type=document_type, commercial_status='issued')
    DocumentCollectionAccount.objects.create(document=account, customer_name='Titular')
    before = (account.is_archived, CollectionAccountContext.objects.count())

    result = _call(tools, context, 'associate_collection_account_context', {
        'project_id': project.pk, 'account_id': account.pk,
        'payload': {'expected_version': 0, 'reason': 'Campo no permitido', 'billing_nature': 'contract',
                    'contract_id': contract.pk, 'amendment_id': None, 'project_hosting_id': None,
                    'hosting_payment_id': None, 'commercial_status': 'paid'},
    })

    assert result['error']['code'] == 'VALIDATION_ERROR'
    assert result['error']['details']['fields'] == ['commercial_status']
    assert (account.is_archived, CollectionAccountContext.objects.count()) == before


def test_mcp_hosting_preview_validates_identity_without_creating_context_or_financial_rows(
    billing_runtime, project, subscription, hosting_record,
):
    """Falla si la previsualización MCP convierte orígenes existentes en un hosting o cobra algo."""
    tools, context = billing_runtime
    arguments = {
        'project_id': project.pk,
        'payload': {
            'expected_version': 0,
            'reason': 'Comparar orígenes heredados',
            'subscription_id': subscription.pk,
            'hosting_record_ids': [hosting_record.pk],
            'operational_record_id': hosting_record.pk,
        },
    }

    preview = _call(tools, context, 'preview_project_hosting_reconciliation', arguments)

    assert preview['proposal'] == {
        'subscription_id': subscription.pk,
        'add_record_ids': [hosting_record.pk],
        'operational_record_id': hosting_record.pk,
        'financial_effect': 'none',
    }
    assert ProjectHosting.objects.filter(project=project).count() == 0
    assert ProjectHostingAccountingSource.objects.filter(hosting__project=project).count() == 0
    assert BillingContextEvent.objects.filter(project=project).count() == 0


def test_mcp_hosting_reconciliation_rejects_an_unknown_project_without_writes(billing_runtime, subscription, hosting_record):
    """Falla si reconciliar hosting para un proyecto inexistente crea intención o hechos financieros."""
    tools, context = billing_runtime
    result = _call(tools, context, 'reconcile_project_hosting', {
        'project_id': 999999, 'payload': {'expected_version': 0, 'reason': 'Proyecto inexistente',
        'subscription_id': subscription.pk, 'hosting_record_ids': [hosting_record.pk], 'operational_record_id': hosting_record.pk},
    })

    assert result['error']['code'] == 'NOT_FOUND'
    assert ProjectHosting.objects.count() == 0
    assert BillingContextEvent.objects.count() == 0


def test_mcp_reconciliation_confirmation_creates_only_explicit_hosting_relationships(
    billing_runtime, project, subscription, hosting_record, payment,
):
    """Falla si confirmar la conciliación MCP no fija el hosting único o altera pagos existentes."""
    tools, context = billing_runtime
    arguments = {
        'project_id': project.pk,
        'payload': {
            'expected_version': 0,
            'reason': 'Conciliación administrativa comprobada',
            'subscription_id': subscription.pk,
            'hosting_record_ids': [hosting_record.pk],
            'operational_record_id': hosting_record.pk,
        },
    }

    preview = _call(tools, context, 'reconcile_project_hosting', arguments)
    confirmed = _call(tools, context, 'confirm_action', {'confirmation_id': preview['confirmation_id']})

    hosting = ProjectHosting.objects.get(project=project)
    source = ProjectHostingAccountingSource.objects.get(hosting=hosting)
    payment.refresh_from_db()
    assert confirmed['result'] == {
        'id': hosting.pk,
        'subscription_id': subscription.pk,
        'hosting_record_ids': [hosting_record.pk],
        'operational_record_id': hosting_record.pk,
        'version': 1,
    }
    assert source.hosting_record_id == hosting_record.pk
    assert payment.status == 'paid'
    assert payment.amount == 150000


def test_mcp_confirmation_rejects_a_hosting_identity_changed_after_preview(
    billing_runtime, project, subscription, hosting_record,
):
    """Falla si una confirmación MCP antigua puede sobrescribir una conciliación posterior."""
    tools, context = billing_runtime
    arguments = {
        'project_id': project.pk,
        'payload': {
            'expected_version': 0,
            'reason': 'Vista previa inicial',
            'subscription_id': subscription.pk,
            'hosting_record_ids': [hosting_record.pk],
            'operational_record_id': hosting_record.pk,
        },
    }
    preview = _call(tools, context, 'reconcile_project_hosting', arguments)
    reconcile_hosting(project.pk, context.actor, {
        **arguments['payload'],
        'reason': 'Conciliación posterior',
    })

    stale = _call(tools, context, 'confirm_action', {'confirmation_id': preview['confirmation_id']})

    hosting = ProjectHosting.objects.get(project=project)
    assert stale['error']['code'] == 'STALE_VERSION'
    assert hosting.version == 1
    assert ProjectHostingAccountingSource.objects.filter(hosting=hosting).count() == 1


def test_mcp_billing_registry_and_model_contract_expose_the_explicit_context_surface():
    """Falla si el conector contable deja de registrar las herramientas o modelos de contexto que administra."""
    from content.views.mcp_blog import TOOLS_BY_SLUG

    tool_names = {tool['name'] for tool in TOOLS_BY_SLUG['accounting-billing']}
    contracts = {contract.model_label: contract for contract in MCP_MODEL_CONTRACTS['accounting-billing']}

    assert {
        'get_project_billing_options', 'get_project_hosting', 'get_project_hosting_inventory',
        'get_collection_account_context', 'associate_collection_account_context',
        'preview_project_hosting_reconciliation', 'reconcile_project_hosting',
        'preview_hosting_evidence', 'reconcile_hosting_evidence',
    } <= tool_names
    assert contracts['accounts.CollectionAccountContext'].read_write == frozenset({
        'nature', 'contract', 'amendment', 'hosting',
    })
    assert contracts['accounts.ProjectHosting'].read_only == frozenset({
        'id', 'project', 'version', 'created_at', 'updated_at',
    })
    assert contracts['accounts.BillingContextEvent'].read_only == frozenset({
        'id', 'project', 'document', 'actor', 'operation', 'reason', 'before', 'after', 'created_at',
    })
