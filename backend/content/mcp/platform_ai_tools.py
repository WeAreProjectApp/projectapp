"""Platform AI administration belongs to projects; secrets are encrypted before intents."""
from accounts.serializers_ai import SettingsSerializer, ClientFlagsSerializer, TemplateSerializer, TemplateRestoreSerializer, CredentialSerializer, validated
from accounts.services import platform_ai as service
from accounts.services.platform_ai_cipher import encrypt
from content.mcp.actor import mcp_actor
from content.mcp.operation_builder import _op as _panel_op
from content.mcp.proposal_schemas import writable_schema


def _schema(serializer):
    return writable_schema(serializer, partial=False)


def _op(name, description, route, method='GET', **options):
    # Even reads and body-free actions have a finite argument contract.
    options.setdefault('query_schema' if method == 'GET' else 'payload_schema',
                       {'type': 'object', 'properties': {}, 'additionalProperties': False})
    return _panel_op(name, description, route, method, **options)


def _prepare_key(arguments):
    service.require_admin(mcp_actor())
    values = validated(CredentialSerializer, {key: value for key, value in arguments.items() if key != 'provider'})
    return {'provider': arguments['provider'], 'expected_version': values['expected_version'], '_encrypted_value': encrypt(values['api_key'])}


def _set_key(arguments):
    return service.set_credential(mcp_actor(), arguments['provider'], expected_version=arguments['expected_version'], encrypted_value=arguments['_encrypted_value'])


PROVIDER = {'type': 'string', 'enum': ['anthropic', 'openai', 'jev']}
VERSION = {'type': 'integer', 'minimum': 0}

PLATFORM_AI_TOOLS = [
    _op('get_platform_ai_settings', 'Consulta configuración IA, modelos por función, límites y estado de claves; nunca revela secretos.', 'platform-ai-settings', envelope_aliases=False),
    _op('update_platform_ai_settings', 'Actualiza activación global, redactor por función y políticas de consumo/caché con versión vigente.', 'platform-ai-settings', 'PATCH', risk='sensitive', confirm=True, payload_schema=_schema(SettingsSerializer), envelope_aliases=False),
    _op('list_platform_ai_clients', 'Lista clientes paginados con interruptores independientes de chatbot y reporte por voz.', 'platform-ai-clients', query_schema={'type': 'object', 'properties': {'page': {'type': 'integer', 'minimum': 1}, 'search': {'type': 'string', 'maxLength': 200}}, 'additionalProperties': False}, envelope_aliases=False),
    _op('get_platform_ai_client', 'Consulta controles IA de un cliente y su versión.', 'platform-ai-client', path=('user_id',), envelope_aliases=False),
    _op('update_platform_ai_client', 'Activa o apaga IA por cliente; el apagado global prevalece.', 'platform-ai-client', 'PATCH', path=('user_id',), risk='sensitive', confirm=True, payload_schema=_schema(ClientFlagsSerializer), envelope_aliases=False),
    _op('list_platform_ai_templates', 'Lista plantillas ES/EN de Reportes y Chatbot con sus marcadores permitidos.', 'platform-ai-templates', envelope_aliases=False),
    _op('get_platform_ai_template', 'Lee una plantilla vigente sin fuentes ni conversaciones privadas.', 'platform-ai-template', path=('template_id',), envelope_aliases=False),
    _op('update_platform_ai_template', 'Crea una versión de plantilla conservando los marcadores requeridos; no modifica reportes anteriores.', 'platform-ai-template', 'PATCH', path=('template_id',), risk='sensitive', confirm=True, payload_schema=_schema(TemplateSerializer), envelope_aliases=False),
    _op('preview_platform_ai_template', 'Valida una plantilla y muestra un ejemplo local sin llamar proveedores.', 'platform-ai-template-preview', 'POST', path=('template_id',), payload_schema=_schema(TemplateSerializer), envelope_aliases=False),
    _op('list_platform_ai_template_versions', 'Lista las últimas versiones de una plantilla.', 'platform-ai-template-versions', path=('template_id',), envelope_aliases=False),
    _op('restore_platform_ai_template', 'Restaura una versión anterior creando una versión nueva, con control de concurrencia.', 'platform-ai-template-restore', 'POST', path=('template_id',), risk='sensitive', confirm=True, payload_schema=_schema(TemplateRestoreSerializer), envelope_aliases=False),
    _op('get_platform_ai_usage', 'Consulta consumo mensual agregado, tokens/caché y costo estimado, sin mensajes ni audio.', 'platform-ai-usage', envelope_aliases=False),
    _op('list_platform_ai_events', 'Consulta auditoría de configuración sin claves ni conversaciones.', 'platform-ai-events', envelope_aliases=False),
    _op('invalidate_platform_ai_cache', 'Invalida la caché de IA sin borrar el historial oficial.', 'platform-ai-cache-invalidate', 'POST', risk='sensitive', confirm=True, payload_schema={'type': 'object', 'properties': {'function': {'type': 'string', 'enum': ['chatbot', 'voice_report', 'all']}}, 'required': ['function'], 'additionalProperties': False}, envelope_aliases=False),
    _op('test_platform_ai_credential', 'Comprueba la conexión con el proveedor; Jev realiza una petición mínima sin datos del cliente.', 'platform-ai-credential-test', 'POST', path=('provider',), risk='sensitive', confirm=True, envelope_aliases=False),
    _op('delete_platform_ai_credential', 'Elimina la clave guardada de un proveedor con versión vigente.', 'platform-ai-credential', 'DELETE', path=('provider',), risk='sensitive', confirm=True, payload_schema={'type': 'object', 'properties': {'expected_version': VERSION}, 'required': ['expected_version'], 'additionalProperties': False}, envelope_aliases=False),
    {'name': 'set_platform_ai_credential', 'description': 'Guarda o reemplaza una API key cifrada de Anthropic, OpenAI o Jev; jamás permite leerla. No inventes claves. El preview y la confirmación no contienen el secreto en claro.',
     'risk': 'sensitive', 'requires_confirmation': True,
     'input_schema': {'type': 'object', 'properties': {'provider': PROVIDER, 'api_key': {'type': 'string', 'minLength': 10, 'maxLength': 4096, 'writeOnly': True}, 'expected_version': VERSION}, 'required': ['provider', 'api_key', 'expected_version'], 'additionalProperties': False},
     'prepare_arguments': _prepare_key, 'handler': _set_key,
     'impact_builder': lambda values: {'summary': 'Reemplaza una credencial de IA cifrada.', 'provider': values['provider'], 'expected_version': values['expected_version']},
     'output_schema': {'type': 'object', 'properties': {'configured': {'type': 'boolean'}, 'version': VERSION}}},
]

# Publish finite, described input contracts rather than generic Panel envelopes.
_DESCRIPTIONS = {
    'page': 'Página de clientes, desde 1; se devuelven hasta 20 por página.',
    'search': 'Filtro por correo, nombre o empresa del cliente, hasta 200 caracteres.',
    'provider': 'Proveedor: anthropic, openai o jev.',
    'api_key': 'Clave privada nueva. Solo escritura; nunca se devuelve ni se incluye en el preview.',
    'expected_version': 'Versión vigente leída antes de cambiar el recurso; evita sobrescribir cambios ajenos.',
    'content': 'Texto plano de la plantilla; conserva exactamente los marcadores admitidos del escenario.',
    'version': 'Número de la versión histórica que se restaurará como una versión nueva.',
    'function': 'Función cuya caché se desea invalidar; all invalida ambas.',
    'chatbot_enabled': 'Habilita el chatbot; el apagado global prevalece sobre el cliente.',
    'voice_reporting_enabled': 'Habilita los reportes por voz; independiente del chatbot.',
    'chatbot_model': 'Redactor del chatbot: claude-haiku-5-5 o gpt-6-luna.',
    'voice_report_model': 'Redactor de reportes por voz; no modifica el transcriptor gpt-transcribe.',
    'monthly_audio_limit': 'Máximo mensual de notas de voz compartido entre ambas funciones.',
    'daily_user_audio_limit': 'Máximo diario de notas de voz por usuario.',
    'ai_request_limit': 'Cupo compartido por cliente para chatbot y reportes por voz; null en cliente hereda el global.',
    'ai_window_minutes': 'Ventana móvil del cupo compartido en minutos; null en cliente hereda el global.',
    'max_output_tokens': 'Límite de salida de los redactores por petición, de 256 a 2000 tokens.',
    'report_cache_enabled': 'Permite reutilizar resultados idénticos y autorizados de reportes.',
    'chatbot_cache_enabled': 'Permite reutilizar respuestas del chatbot tras validar fuentes y permisos.',
    'report_cache_hours': 'Vigencia de caché de reportes, entre 1 y 24 horas.',
    'chatbot_cache_hours': 'Vigencia de caché caliente del chatbot, entre 1 y 24 horas.',
}
for _tool in PLATFORM_AI_TOOLS:
    for _field, _property in _tool['input_schema'].get('properties', {}).items():
        if _field in _DESCRIPTIONS:
            _property['description'] = _DESCRIPTIONS[_field]

_STATUS = {'type': 'object', 'properties': {'configured': {'type': 'boolean'}, 'version': {'type': 'integer'}, 'last_test_status': {'type': 'string'}, 'tested_at': {'type': ['string', 'null']}}}
_TEMPLATE = {'type': 'object', 'properties': {'id': {'type': 'integer'}, 'family': {'type': 'string'}, 'scenario': {'type': 'string'}, 'language': {'type': 'string'}, 'content': {'type': 'string'}, 'version': {'type': 'integer'}, 'updated_at': {'type': 'string'}, 'placeholders': {'type': 'array', 'items': {'type': 'string'}}}}
_CLIENT = {'type': 'object', 'properties': {'user_id': {'type': 'integer'}, 'name': {'type': 'string'}, 'chatbot_enabled': {'type': 'boolean'}, 'voice_reporting_enabled': {'type': 'boolean'}, 'ai_request_limit': {'type': ['integer', 'null']}, 'ai_window_minutes': {'type': ['integer', 'null']}, 'version': {'type': 'string'}}}
_SETTINGS = {'type': 'object', 'properties': {**{name: schema for name, schema in _schema(SettingsSerializer)['properties'].items() if name != 'expected_version'}, 'version': {'type': 'integer'}, 'updated_at': {'type': 'string'}, 'credentials': {'type': 'object', 'properties': {provider: _STATUS for provider in ('anthropic', 'openai', 'jev')}}}}
for _tool in PLATFORM_AI_TOOLS:
    _name = _tool['name']
    if _name in ('get_platform_ai_settings', 'update_platform_ai_settings'):
        _tool['output_schema'] = _SETTINGS
    elif _name in ('get_platform_ai_client', 'update_platform_ai_client'):
        _tool['output_schema'] = _CLIENT
    elif _name == 'list_platform_ai_clients':
        _tool['output_schema'] = {'type': 'object', 'properties': {'results': {'type': 'array', 'items': _CLIENT}, 'count': {'type': 'integer'}, 'page': {'type': 'integer'}}}
    elif _name in ('get_platform_ai_template', 'update_platform_ai_template', 'restore_platform_ai_template'):
        _tool['output_schema'] = _TEMPLATE
    elif _name == 'list_platform_ai_templates':
        _tool['output_schema'] = {'type': 'object', 'properties': {'items': {'type': 'array', 'items': _TEMPLATE}}}
    elif _name in ('set_platform_ai_credential', 'test_platform_ai_credential', 'delete_platform_ai_credential'):
        _tool['output_schema'] = _STATUS
    elif _name == 'preview_platform_ai_template':
        _tool['output_schema'] = {'type': 'object', 'properties': {'preview': {'type': 'string'}, 'provider_called': {'type': 'boolean'}}}
    elif _name == 'invalidate_platform_ai_cache':
        _tool['output_schema'] = {'type': 'object', 'properties': {'invalidated': {'type': 'boolean'}, 'cache_epoch': {'type': 'integer'}}}
