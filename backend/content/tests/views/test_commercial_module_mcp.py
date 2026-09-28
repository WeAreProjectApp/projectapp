"""Smoke coverage for dedicated commercial-module MCP connectors."""

import pytest

from content.models import (
    AdditionalModuleCategory,
    AdditionalModule,
    FinancingAgreement,
    FinancingAgreementTemplate,
    FinancingPolicyRevision,
    McpConnector,
)
from content.services.financing_agreement_service import (
    DEFAULT_FINANCING_TEMPLATE_MARKDOWN,
    create_agreement,
)
from content.services.additional_module_catalog_service import next_category_order
from content.serializers.financing import FinancingAgreementWriteSerializer


pytestmark = pytest.mark.django_db


def _rpc(name, arguments):
    return {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }


def _call(api_client, slug, token, name, arguments):
    response = api_client.post(
        f'/api/mcp/{slug}/{token}/', _rpc(name, arguments), format='json',
    )
    assert response.status_code == 200
    result = response.data['result']
    assert result['isError'] is False, result
    return result['structuredContent']


def _agreement_data(client_id):
    return {
        'client_id': client_id,
        'original_contract_reference': 'Contrato de desarrollo 014',
        'original_contract_date': '2026-01-10',
        'project_name': 'Vástago',
        'financed_scope': 'Implementación de analítica.',
        'modality': 'five_year',
        'partnership_start_date': '2026-02-01',
        'currency': 'COP',
        'total_value': '25000000.00',
        'initial_payment': '5000000.00',
        'hosting_value': '500000.00',
        'hosting_period': 'monthly',
        'first_installment_date': '2026-03-05',
    }


def _module_data(category_id):
    return {
        'category': category_id,
        'slug': 'automation',
        'icon': '⚙️',
        'name_es': 'Automatización',
        'name_en': 'Automation',
        'summary_es': 'Automatiza una operación comercial.',
        'summary_en': 'Automates a commercial operation.',
        'what_is_es': 'Una capacidad integrada al producto.',
        'what_is_en': 'A product-integrated capability.',
        'purpose_es': 'Reducir trabajo manual.',
        'purpose_en': 'Reduce manual work.',
        'problems_solved_es': ['Evita tareas repetidas.'],
        'problems_solved_en': ['Avoids repeated tasks.'],
        'integrations_es': ['Se conecta al flujo comercial.'],
        'integrations_en': ['Connects to the commercial flow.'],
        'implementation_requirements_es': ['Definir la regla del negocio.'],
        'implementation_requirements_en': ['Define the business rule.'],
    }


def _catalog_category():
    return AdditionalModuleCategory.objects.create(
        slug='operations', name_es='Operaciones', name_en='Operations',
        order=next_category_order(),
    )


def _active_connector(slug):
    connector, _ = McpConnector.objects.get_or_create(
        slug=slug, defaults={'name': slug},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def _agreement_environment(make_client_profile):
    client = make_client_profile(
        company='Semilla SAS', nit='901234567-8', email='ana@semilla.co',
        first_name='Ana', last_name='Semilla',
    )
    FinancingAgreementTemplate.objects.get_or_create(
        name='MCP agreement', version=1,
        defaults={
            'is_default': True,
            'content_markdown': DEFAULT_FINANCING_TEMPLATE_MARKDOWN,
        },
    )
    FinancingPolicyRevision.objects.get_or_create(version=1)
    return client


def _draft_agreement(make_client_profile, django_user_model):
    client = _agreement_environment(make_client_profile)
    serializer = FinancingAgreementWriteSerializer(data=_agreement_data(client.id))
    assert serializer.is_valid(), serializer.errors
    actor = django_user_model.objects.create_user('agreement-author')
    return create_agreement(serializer.validated_data, actor=actor)


def test_partnership_mcp_creates_a_draft_agreement(api_client, make_client_profile, django_user_model):
    """Fails if the partnership connector cannot persist a Panel-valid draft agreement."""
    client = _agreement_environment(make_client_profile)
    token = _active_connector('partnership-program')

    created = _call(
        api_client, 'partnership-program', token,
        'create_partnership_agreement', {'data': _agreement_data(client.id)},
    )

    stored = FinancingAgreement.objects.get(pk=created['id'])
    assert stored.client_id == client.id
    assert stored.status == FinancingAgreement.Status.DRAFT


def test_partnership_mcp_updates_a_draft_agreement(
    api_client, make_client_profile, django_user_model,
):
    """Fails if the partnership connector cannot persist an edit to a draft agreement."""
    agreement = _draft_agreement(make_client_profile, django_user_model)
    token = _active_connector('partnership-program')

    updated = _call(
        api_client, 'partnership-program', token,
        'update_partnership_agreement', {
            'agreement_id': agreement.id,
            'data': {'project_name': 'Vástago actualizado'},
        },
    )

    agreement.refresh_from_db()
    assert updated['project_name'] == 'Vástago actualizado'
    assert agreement.project_name == 'Vástago actualizado'


def test_partnership_mcp_lists_draft_agreements(
    api_client, make_client_profile, django_user_model,
):
    """Fails if the partnership connector omits an active draft from its list."""
    agreement = _draft_agreement(make_client_profile, django_user_model)
    token = _active_connector('partnership-program')

    listed = _call(
        api_client, 'partnership-program', token,
        'list_partnership_agreements', {},
    )

    assert [row['id'] for row in listed['results']] == [agreement.id]


def test_partnership_mcp_gets_draft_agreement(
    api_client, make_client_profile, django_user_model,
):
    """Fails if the partnership connector cannot read an agreement by its identifier."""
    agreement = _draft_agreement(make_client_profile, django_user_model)
    token = _active_connector('partnership-program')

    fetched = _call(
        api_client, 'partnership-program', token,
        'get_partnership_agreement', {'agreement_id': agreement.id},
    )

    assert fetched['id'] == agreement.id


def test_partnership_mcp_archives_cancelled_agreement(
    api_client, make_client_profile, django_user_model,
):
    """Fails if a confirmed partnership archive does not retire a cancelled agreement."""
    agreement = _draft_agreement(make_client_profile, django_user_model)
    agreement.status = FinancingAgreement.Status.CANCELLED
    agreement.save(update_fields=['status', 'updated_at'])
    token = _active_connector('partnership-program')
    preview = _call(
        api_client, 'partnership-program', token,
        'transition_partnership_agreement', {
            'agreement_id': agreement.id, 'action': 'archive',
        },
    )

    confirmed = _call(
        api_client, 'partnership-program', token, 'confirm_action', {
            'confirmation_id': preview['confirmation_id'],
        },
    )

    agreement.refresh_from_db()
    assert confirmed['result']['is_archived'] is True
    assert agreement.is_archived is True


def test_additional_modules_mcp_creates_catalog_module(api_client, monkeypatch):
    """Fails if the dedicated catalog connector cannot persist a Panel-valid module."""
    monkeypatch.setattr(
        'content.views.additional_modules.schedule_rebuild_after_publish',
        lambda: None,
    )
    token = _active_connector('additional-modules')

    category = _catalog_category()
    module = _call(
        api_client, 'additional-modules', token, 'create_additional_module',
        {'data': _module_data(category.id)},
    )

    stored = AdditionalModule.objects.get(pk=module['id'])
    assert stored.category_id == category.id
    assert stored.is_active is True


def test_additional_modules_mcp_reads_catalog_module(api_client):
    """Fails if the dedicated connector omits an existing module from the catalog."""
    category = _catalog_category()
    module_data = _module_data(category.id)
    module_data['category'] = category
    module = AdditionalModule.objects.create(**module_data)
    token = _active_connector('additional-modules')

    catalog = _call(
        api_client, 'additional-modules', token,
        'get_additional_modules_catalog', {},
    )

    assert module.id in {row['id'] for row in catalog['modules']}


def test_additional_modules_mcp_updates_catalog_module(api_client, monkeypatch):
    """Fails if the dedicated catalog connector cannot persist an existing module edit."""
    monkeypatch.setattr(
        'content.views.additional_modules.schedule_rebuild_after_publish',
        lambda: None,
    )
    category = _catalog_category()
    module_data = _module_data(category.id)
    module_data['category'] = category
    module = AdditionalModule.objects.create(**module_data)
    token = _active_connector('additional-modules')
    updated = _call(
        api_client, 'additional-modules', token, 'update_additional_module', {
            'module_id': module.id, 'data': {'summary_es': 'Automatiza ventas.'},
        },
    )

    stored = AdditionalModule.objects.get(pk=module.id)
    assert updated['summary_es'] == 'Automatiza ventas.'
    assert stored.summary_es == 'Automatiza ventas.'


def test_additional_modules_mcp_retires_catalog_module(api_client, monkeypatch):
    """Fails if a connector retirement leaves a catalog module publicly active."""
    monkeypatch.setattr(
        'content.views.additional_modules.schedule_rebuild_after_publish',
        lambda: None,
    )
    category = _catalog_category()
    module_data = _module_data(category.id)
    module_data['category'] = category
    module = AdditionalModule.objects.create(**module_data)
    token = _active_connector('additional-modules')

    retired = _call(
        api_client, 'additional-modules', token,
        'set_additional_module_status', {
            'module_id': module.id, 'action': 'retire',
        },
    )

    module.refresh_from_db()
    assert retired['is_active'] is False
    assert module.is_active is False
