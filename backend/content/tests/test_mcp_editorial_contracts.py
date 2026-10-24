"""Published editorial MCP contracts and real writes through their handlers."""

from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Max

from accounts.models import UserProfile
from content.mcp.connectors import TOOLS_BY_SLUG
from content.mcp.protocol import handle_message
from content.models import (
    AdditionalModule, AdditionalModuleCategory, CommunicationMessage,
    CommunicationThread, Document, DocumentType, HourPackage, McpConnector,
)
from content.services.document_note_service import create_note
from content.tests.mcp_parity import call_tool_inprocess


SOURCE = '<p style="text-align: center"><strong>Nuevo contenido</strong></p>'
INITIAL = 'Contenido inicial'
SCHEMA_CASES = (
    ('documents', 'create_document', None),
    ('documents', 'update_document', None),
    ('documents', 'add_document_note', None),
    ('documents', 'update_document_note', None),
    ('communications', 'create_message', None),
    ('communications', 'update_message', None),
    ('commercial', 'create_proposal', None),
    ('commercial', 'update_proposal', None),
    ('content', 'create_blog_post', None),
    ('content', 'update_blog_post', None),
    ('offerings', 'create_hour_package', 'data'),
    ('offerings', 'update_hour_package', 'data'),
    ('offerings', 'create_additional_module', 'data'),
    ('offerings', 'update_additional_module', 'data'),
)
GRAMMAR_CASES = (
    ('commercial', 'preview_proposal_contract_template_update'),
    ('commercial', 'update_proposal_contract_template'),
    ('programs', 'preview_building_with_us_contract_update'),
    ('programs', 'update_building_with_us_contract'),
    ('programs', 'preview_building_on_demand_contract_update'),
    ('programs', 'update_building_on_demand_contract'),
)


def _published(slug, name):
    _, response = handle_message(
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
        TOOLS_BY_SLUG[slug],
    )
    return next(tool for tool in response['result']['tools'] if tool['name'] == name)


def _write_schema(tool, envelope):
    schema = tool['inputSchema']
    return schema['properties'][envelope] if envelope else schema


def _grammar_text(value):
    if isinstance(value, dict):
        return ' '.join(str(item) if key == 'description' else _grammar_text(item) for key, item in value.items())
    if isinstance(value, list):
        return ' '.join(_grammar_text(item) for item in value)
    return ''


def _format_maps(value):
    if isinstance(value, dict):
        own = [value['text_formats']] if 'text_formats' in value else []
        return own + [item for child in value.values() for item in _format_maps(child)]
    if isinstance(value, list):
        return [item for child in value for item in _format_maps(child)]
    return []


@pytest.mark.parametrize('slug,name,envelope', SCHEMA_CASES, ids=[f'{slug}/{name}' for slug, name, _ in SCHEMA_CASES])
def test_mcp_published_schema_exposes_bounded_metadata(slug, name, envelope):
    """Falla si tools/list publica un mapa editorial abierto o sin límites."""
    schema = _write_schema(_published(slug, name), envelope)
    metadata = schema['properties']['text_formats']

    assert metadata['type'] == 'object'
    assert metadata['maxProperties'] == 1000
    assert metadata['additionalProperties'] is False
    assert metadata['propertyNames']['pattern'] == '^/'
    assert metadata['propertyNames']['description']


@pytest.mark.parametrize('slug,name,envelope', SCHEMA_CASES, ids=[f'{slug}/{name}' for slug, name, _ in SCHEMA_CASES])
def test_mcp_published_schema_types_each_editorial_pointer(slug, name, envelope):
    """Falla si tools/list deja un valor de ruta sin formato declarado o vuelve obligatoria la metadata."""
    schema = _write_schema(_published(slug, name), envelope)
    metadata = schema['properties']['text_formats']
    format_value = metadata['patternProperties']['^/']

    assert format_value['type'] == 'string'
    assert format_value['enum'] == ['plain', 'markdown', 'markdown_html_v1', 'whatsapp_v1']
    assert format_value['description']
    assert 'text_formats' not in schema.get('required', [])


@pytest.mark.parametrize('slug,name', GRAMMAR_CASES, ids=[f'{slug}/{name}' for slug, name in GRAMMAR_CASES])
def test_mcp_native_contract_describes_versioned_grammar(slug, name):
    """Falla si una herramienta de contratos nativos sigue anunciando Markdown plano y oculta el HTML admitido."""
    text = _grammar_text(_published(slug, name)).lower()

    assert 'markdown_html_v1' in text
    assert 'html' in text


def _document():
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown'},
    )
    return Document.objects.create(
        title='Documento editorial', document_type=document_type,
        content_markdown=INITIAL,
    )


def _communication(actor):
    user = get_user_model().objects.create_user(username='editorial-client', email='editorial-client@example.com')
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': UserProfile.ROLE_CLIENT})
    thread = CommunicationThread.objects.create(client=profile, title='Hilo editorial', created_by=actor)
    return CommunicationMessage.objects.create(
        thread=thread, channel='email', direction='outgoing', status='draft',
        subject='Revisión editorial', content=INITIAL, created_by=actor,
        occurred_at=datetime(2026, 10, 23, 12, tzinfo=UTC),
    )


def _additional_module():
    next_order = (AdditionalModuleCategory.objects.aggregate(value=Max('order'))['value'] or 0) + 1
    category = AdditionalModuleCategory.objects.create(
        slug='editorial-test', name_es='Editorial', name_en='Editorial', order=next_order,
    )
    return AdditionalModule.objects.create(
        category=category, slug='editorial-module', name_es='Editor', name_en='Editor', summary_es=INITIAL,
    )


@pytest.fixture(params=['document', 'document_note', 'communication', 'proposal', 'blog', 'hour_package', 'additional_module'])
def mcp_write_case(request, superuser):
    factories = {
        'document': lambda: (_document(), 'documents', 'update_document', 'content_markdown', 'document_id', None, 'read_document'),
        'document_note': lambda: (create_note(_document(), content=INITIAL, actor=superuser), 'documents', 'update_document_note', 'content', 'note_id', None, 'read_document'),
        'communication': lambda: (_communication(superuser), 'communications', 'update_message', 'content', 'message_id', None, 'get_thread'),
        'proposal': lambda: (request.getfixturevalue('proposal'), 'commercial', 'update_proposal', 'email_intro', 'proposal_id', None, 'get_proposal'),
        'blog': lambda: (request.getfixturevalue('draft_blog_post'), 'content', 'update_blog_post', 'excerpt_es', 'post_id', None, 'get_blog_post'),
        'hour_package': lambda: (HourPackage.objects.create(name_es='Paquete', name_en='Package', pricing_model='requirements', xs_count=1, note_es=INITIAL), 'offerings', 'update_hour_package', 'note_es', 'package_id', 'data', 'get_hour_package'),
        'additional_module': lambda: (_additional_module(), 'offerings', 'update_additional_module', 'summary_es', 'module_id', 'data', 'get_additional_modules_catalog'),
    }
    instance, slug, tool, field, identity, envelope, read_tool = factories[request.param]()
    setattr(instance, field, INITIAL)
    instance.save(update_fields=[field])
    arguments = {identity: instance.pk}
    read_arguments = dict(arguments)
    if request.param == 'document_note':
        arguments['document_id'] = instance.document_id
        read_arguments = {'document_id': instance.document_id}
    elif request.param == 'communication':
        read_arguments = {'thread_id': instance.thread_id}
    elif request.param == 'additional_module':
        read_arguments = {}
    elif request.param == 'proposal':
        arguments.update({'title': instance.title, 'client_name': instance.client_name,
                          'sections': {'general': {'clientName': instance.client_name}}})
    connector, _ = McpConnector.objects.get_or_create(slug=slug, defaults={'name': slug})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    credential = connector.credential_for_token(connector.generate_token())
    credential.actor = superuser
    credential.save(update_fields=['actor'])
    return {
        'instance': instance, 'slug': slug, 'tool': tool, 'field': field,
        'arguments': arguments, 'envelope': envelope, 'credential': credential,
        'read_tool': read_tool, 'read_arguments': read_arguments,
    }


def _write_arguments(case, source):
    payload = {case['field']: source, 'text_formats': {'/' + case['field']: 'markdown_html_v1'}}
    return {**case['arguments'], case['envelope']: payload} if case['envelope'] else {**case['arguments'], **payload}


def _write_tool(case, source):
    result = call_tool_inprocess(case['slug'], case['tool'], _write_arguments(case, source), credential=case['credential'])
    if result.get('confirmation_required'):
        result = call_tool_inprocess(case['slug'], 'confirm_action', {'confirmation_id': result['confirmation_id']}, credential=case['credential'])
    return result


@pytest.mark.django_db
def test_mcp_write_persists_format_metadata(mcp_write_case):
    """Falla si el handler acepta text_formats pero lo descarta antes de guardar o leer por MCP."""
    case = mcp_write_case

    result = _write_tool(case, SOURCE)
    case['instance'].refresh_from_db()
    read = call_tool_inprocess(case['slug'], case['read_tool'], case['read_arguments'], credential=case['credential'])

    assert 'error' not in result, result
    assert getattr(case['instance'], case['field']) == SOURCE
    assert case['instance'].text_formats == {'/' + case['field']: 'markdown_html_v1'}
    assert {'/' + case['field']: 'markdown_html_v1'} in _format_maps(read)


@pytest.mark.django_db
def test_mcp_unsafe_format_preserves_existing_content(mcp_write_case):
    """Falla si MCP guarda una presentación prohibida o cambia la metadata pese a rechazar el contenido."""
    case = mcp_write_case

    result = _write_tool(case, '<p style="position: fixed">Texto prohibido</p>')
    case['instance'].refresh_from_db()

    assert result['ok'] is False
    assert getattr(case['instance'], case['field']) == INITIAL
    assert case['instance'].text_formats == {}
