"""Platform availability has the same service, versions and permissions as Panel."""
from accounts.feature_catalog import FEATURES
from content.mcp.operation_builder import _op


VERSION = {'type': 'integer', 'minimum': 0, 'description': 'Versión vigente de este ámbito; evita sobrescribir cambios ajenos.'}
KEY = {'type': 'string', 'enum': list(FEATURES)}
STRING_LIST = {'type': 'array', 'items': {'type': 'string'}}
FEATURE = {'type': 'object', 'properties': {
    'key': KEY, 'label_es': {'type': 'string'}, 'label_en': {'type': 'string'},
    'module': {'type': 'string'}, 'default_enabled': {'type': 'boolean'},
    **{field: STRING_LIST for field in ('routes', 'capabilities', 'targets', 'api_routes', 'surfaces')},
    'global_value': {'type': 'boolean'}, 'override': {'type': ['boolean', 'null']},
    'effective': {'type': 'boolean'}, 'source': {'type': 'string', 'enum': ['global', 'client']},
}}
SETTINGS = {'type': 'object', 'properties': {
    'catalog_version': VERSION, 'version': VERSION, 'global_version': VERSION,
    'user_id': {'type': ['integer', 'null']}, 'name': {'type': ['string', 'null']},
    'features': {'type': 'array', 'items': FEATURE},
}}
QUERY = {'type': 'object', 'properties': {
    'page': {'type': 'integer', 'minimum': 1, 'description': 'Página desde 1; hasta 20 registros.'},
    'search': {'type': 'string', 'maxLength': 200, 'description': 'Buscar por nombre, correo o empresa.'},
}, 'additionalProperties': False}


def write_schema(client=False):
    return {'type': 'object', 'properties': {
        'expected_version': VERSION,
        'values': {'type': 'object', 'minProperties': 1, 'additionalProperties': False,
                   'description': 'Valores por clave estable; null retira una excepción de cliente.' if client else 'Valores globales por clave estable.',
                   'properties': {key: {'type': ['boolean', 'null'] if client else 'boolean',
                                        'description': item['label_es']} for key, item in FEATURES.items()}},
    }, 'required': ['expected_version', 'values'], 'additionalProperties': False}


def operation(name, description, route, method='GET', **options):
    output = options.pop('output_schema')
    if method == 'GET':
        options.setdefault('query_schema', {'type': 'object', 'properties': {}, 'additionalProperties': False})
    tool = _op(name, description, route, method, envelope_aliases=False, **options)
    tool['output_schema'] = output
    return tool


PLATFORM_FEATURE_TOOLS = [
    operation('get_platform_feature_flags', 'Consulta catálogo, globales y valores iniciales. IA y audio comienzan apagados. No concede permisos.',
              'platform-feature-settings', output_schema=SETTINGS),
    operation('update_platform_feature_flags', 'Configura globales con versión vigente. Las excepciones explícitas del cliente prevalecen.',
              'platform-feature-settings', 'PATCH', risk='sensitive', confirm=True,
              payload_schema=write_schema(), output_schema=SETTINGS),
    operation('list_platform_feature_clients', 'Busca clientes paginados para gestionar disponibilidad; no revela datos de otros módulos.',
              'platform-feature-clients', query_schema=QUERY, output_schema={'type': 'object', 'properties': {
                  'results': {'type': 'array', 'items': {'type': 'object', 'properties': {'user_id': {'type': 'integer'}, 'name': {'type': 'string'}}}},
                  'page': VERSION, 'count': VERSION}}),
    operation('get_platform_client_feature_flags', 'Consulta global, excepción, valor efectivo y procedencia de cada flag del cliente.',
              'platform-feature-client', path=('user_id',), output_schema=SETTINGS),
    operation('update_platform_client_feature_flags', 'Configura excepciones por cliente: true habilita, false deshabilita, null retira para heredar. No concede permisos.',
              'platform-feature-client', 'PATCH', path=('user_id',), risk='sensitive', confirm=True,
              payload_schema=write_schema(True), output_schema=SETTINGS),
    operation('list_platform_feature_events', 'Consulta auditoría paginada: actor, cliente, cambios y versión; no modifica datos.',
              'platform-feature-events', query_schema={'type': 'object', 'properties': {
                  'page': QUERY['properties']['page'],
                  'user_id': {'type': 'integer', 'minimum': 1, 'description': 'Filtrar por cliente; omitir devuelve todos los ámbitos.'}}, 'additionalProperties': False},
              output_schema={'type': 'object', 'properties': {'count': VERSION, 'page': VERSION,
                  'results': {'type': 'array', 'items': {'type': 'object', 'properties': {
                      'id': VERSION, 'actor_id': {'type': ['integer', 'null']}, 'client_id': {'type': ['integer', 'null']},
                      'scope': {'type': 'string', 'enum': ['global', 'client']}, 'version': VERSION, 'created_at': {'type': 'string'},
                      'changes': {'type': 'object', 'properties': {key: {'type': 'object', 'properties': {
                          'before': {'type': ['boolean', 'null']}, 'after': {'type': ['boolean', 'null']}}} for key in FEATURES}},
                  }}}}}),
]
