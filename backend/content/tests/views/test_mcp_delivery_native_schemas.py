"""Explicit delivery inputs exercise the native services through MCP transport."""

from unittest.mock import Mock

import pytest
from accounts.models import (
    ContractAmendment,
    DeliveryPhase,
    DeliveryScope,
    DeliveryStage,
    ProjectContract,
    Requirement,
)
from accounts.services import delivery_authoring, delivery_workflow
from accounts.tests.delivery_helpers import build_delivery_context, version
from django.core.files.base import ContentFile

from content.mcp.delivery_notification_tools import DELIVERY_NOTIFICATION_TOOLS
from content.mcp.delivery_source_tools import DELIVERY_SOURCE_TOOLS
from content.mcp.delivery_tools import DELIVERY_TOOLS
from content.models import Document, McpConnector, McpCredential
from content.tests.mcp_parity import assert_no_writes, call_tool_inprocess
from content.tests.mcp_schema_rules import schema_problems
from content.tests.views.test_mcp_delivery import SIGNED_PDF
from content.views.mcp_blog import TOOLS_BY_SLUG

pytestmark = pytest.mark.django_db

NODE_MODELS = {
    'contract': ProjectContract, 'amendment': ContractAmendment,
    'scope': DeliveryScope, 'phase': DeliveryPhase,
    'stage': DeliveryStage, 'requirement': Requirement,
}
ROLE_GUIDE = {
    'role': 'Responsable de pruebas', 'access': 'Cuenta del cliente asignada.',
    'allowed_actions': 'Crear un registro.', 'blocked_actions': 'Ver otro cliente.',
    'blocked_steps': ['Abrir un enlace de otro cliente.'],
    'blocked_result': 'Acceso denegado.', 'dependencies': 'Completar la etapa previa.',
    'environment': 'Staging', 'preparation': 'Iniciar sesión.', 'data': 'Registro de prueba.',
    'steps': ['Crear el registro.'], 'expected_result': 'El registro aparece.',
    'failure_signals': 'No aparece el registro.',
}


@pytest.fixture
def native_context():
    context = build_delivery_context()
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Proyectos'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    credential = McpCredential.objects.create(connector=connector, actor=context.admin, label='Delivery schemas')
    context.credential = credential
    context.source = Document.objects.create(
        project=context.project, client_user=context.client, title='Fuente revisada',
        content_markdown='# Acuerdo revisado', is_client_visible=True,
    )
    context.source.generated_file.save('reviewed-source.pdf', ContentFile(SIGNED_PDF))
    return context


def _call(context, name, arguments):
    return call_tool_inprocess('projects', name, arguments, credential=context.credential)


def _node_fields(context, singular):
    return {
        'contract': {'document_id': context.source.pk, 'client_visible': False},
        'amendment': {'contract_id': context.contract.pk, 'document_id': context.source.pk,
                      'proposal_document_id': None, 'client_visible': False},
        'scope': {'contract_id': context.contract.pk, 'amendment_id': None, 'description': 'Alcance plano.'},
        'phase': {'scope_id': context.scope.pk, 'commercial_phase_id': None, 'order': 2},
        'stage': {'phase_id': context.phase.pk, 'order': 3},
        'requirement': {'stage_id': context.stage.pk, 'guide': ROLE_GUIDE,
                        'context_id': None, 'source_references': [], 'order': 4},
    }[singular]


@pytest.mark.parametrize(('catalog', 'count'), [
    pytest.param(DELIVERY_TOOLS, 52, id='delivery-including-seven-public-wrappers'),
    pytest.param(DELIVERY_SOURCE_TOOLS, 1, id='contract-source'),
    pytest.param(DELIVERY_NOTIFICATION_TOOLS, 4, id='notifications'),
])
def test_native_delivery_catalog_satisfies_the_explicit_schema_policy(catalog, count):
    published = {tool['name']: tool for tool in TOOLS_BY_SLUG['projects']}

    offenders = {tool['name']: schema_problems(published[tool['name']])
                 for tool in catalog if schema_problems(published[tool['name']])}

    assert len(catalog) == count
    assert len({tool['name'] for tool in catalog}) == count
    assert not offenders, offenders


@pytest.mark.parametrize('name', ['preview_delivery_import', 'apply_delivery_import'])
def test_import_tools_embed_the_existing_versioned_authoring_contracts(name):
    tool = next(tool for tool in DELIVERY_TOOLS if tool['name'] == name)

    schema = tool['input_schema']
    payload = schema['properties']['payload']

    assert payload['oneOf'] == [delivery_workflow.import_schema(), delivery_authoring.guides_schema()]
    assert payload['description']
    assert not {'oneOf', 'anyOf', 'allOf'} & schema.keys()
    assert not {'data', 'query'} & schema['properties'].keys()


@pytest.mark.parametrize('singular', list(NODE_MODELS))
def test_flat_node_mutations_persist_the_selected_delivery_shape(native_context, singular):
    context = native_context
    fields = _node_fields(context, singular)

    created = _call(context, f'create_delivery_{singular}', {
        'project_id': context.project.pk, 'expected_version': version(context),
        'key': f'flat-{singular}', 'title': 'Borrador plano', **fields,
    })
    assert 'error' not in created, created
    updated = _call(context, f'update_delivery_{singular}', {
        'project_id': context.project.pk, 'node_id': created['result']['id'],
        'expected_version': version(context), 'title': 'Edición plana', **fields,
    })

    assert 'error' not in updated, updated
    node = NODE_MODELS[singular].objects.get(pk=created['result']['id'])
    persisted = {name: getattr(node, name) for name in fields}
    assert persisted == fields
    assert node.title == 'Edición plana'
    assert version(context) == 2


@pytest.mark.parametrize('name', ['create_delivery_contract', 'update_delivery_contract'])
def test_legacy_data_is_rejected_before_delivery_callbacks(native_context, monkeypatch, name):
    tool = next(tool for tool in TOOLS_BY_SLUG['projects'] if tool['name'] == name)
    boundary = Mock(side_effect=AssertionError('Unknown arguments reached a delivery callback.'))
    monkeypatch.setitem(tool, 'handler', boundary)
    monkeypatch.setitem(tool, 'confirmation_predicate', boundary)
    monkeypatch.setitem(tool, 'prepare_arguments', boundary)
    arguments = {
        'project_id': native_context.project.pk, 'expected_version': version(native_context),
        'node_id': native_context.contract.pk, 'key': 'legacy', 'title': 'Legacy',
        'data': {'title': 'Envelope rechazado'},
    }
    arguments = {key: value for key, value in arguments.items()
                 if key in tool['input_schema']['properties'] or key == 'data'}

    result = assert_no_writes(_call, native_context, name, arguments)

    assert {'field': 'data', 'code': 'unknown_field', 'message': 'Campo desconocido o de solo lectura.'} in result['error']['details']['errors']
    assert boundary.call_count == 0
    assert version(native_context) == 0


@pytest.mark.parametrize('singular', ['contract', 'amendment'])
def test_public_flat_creation_previews_the_selected_contract_source(native_context, singular):
    context = native_context
    fields = {**_node_fields(context, singular), 'document_id': context.source.pk, 'client_visible': True}
    arguments = {
        'project_id': context.project.pk, 'expected_version': version(context),
        'key': f'public-{singular}', 'title': 'Acuerdo público revisado', **fields,
    }

    preview = _call(context, f'create_delivery_{singular}', arguments)

    assert preview['confirmation_required'] is True
    assert preview['impact']['selection'] == arguments
    assert preview['impact']['files'][0]['document_id'] == context.source.pk
    assert preview['impact']['recipient']['user_id'] == context.client.pk
    assert not NODE_MODELS[singular].objects.filter(key=f'public-{singular}').exists()
    confirmed = _call(context, 'confirm_action', {'confirmation_id': preview['confirmation_id']})
    assert 'error' not in confirmed, confirmed
    node = NODE_MODELS[singular].objects.get(key=f'public-{singular}')
    assert node.document_id == context.source.pk
    assert node.client_visible is True


@pytest.mark.parametrize('singular', ['contract', 'amendment'])
def test_public_flat_source_replacement_revalidates_the_reviewed_bytes(native_context, singular):
    context = native_context
    create_fields = {
        'contract': {'project': context.project},
        'amendment': {'contract': context.contract},
    }[singular]
    node = NODE_MODELS[singular].objects.create(
        key='private-replacement', title='Acuerdo privado', document=context.source,
        client_visible=False, **create_fields,
    )
    replacement = Document.objects.create(
        project=context.project, client_user=context.client, title='Fuente de reemplazo',
        content_markdown='# Reemplazo revisado', is_client_visible=True,
    )
    replacement.generated_file.save('replacement.pdf', ContentFile(SIGNED_PDF))
    preview = _call(context, f'update_delivery_{singular}', {
        'project_id': context.project.pk, 'node_id': node.pk,
        'expected_version': version(context), 'document_id': replacement.pk,
        'client_visible': True,
    })
    assert preview['impact']['files'][0]['document_id'] == replacement.pk
    replacement.generated_file.save('changed-source.pdf', ContentFile(SIGNED_PDF + b'changed'))

    rejected = _call(context, 'confirm_action', {'confirmation_id': preview['confirmation_id']})

    assert rejected['error']['code'] == 'STALE_VERSION'
    node.refresh_from_db()
    assert node.document_id == context.source.pk
    assert node.client_visible is False
    assert version(context) == 0
