"""Platform help administration stays in the existing projects connector."""
from accounts.serializers_platform_help import HelpFlagsSerializer, TourWriteSerializer, TourVersionSerializer
from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import writable_schema

DESCRIPTIONS = {
    'expected_version': 'Versión vigente obtenida al consultar este registro; impide sobrescribir cambios ajenos.',
    'tour_enabled': 'Habilita los recorridos; el apagado global prevalece sobre cada cliente.',
    'video_enabled': 'Habilita los videos disponibles; nunca inicia su reproducción automáticamente.',
    'slug': 'Identificador estable del recorrido. Otra novedad necesita un identificador diferente.',
    'context': 'Lugar de la interfaz cuyos destinos puede señalar el recorrido.',
    'kind': 'Onboarding para orientación inicial; novelty para una novedad independiente.',
    'priority': 'Orden ascendente de elegibilidad de los recorridos.',
    'is_active': 'Permite mostrar este recorrido publicado; apagar conserva historial y vistos.',
    'content': 'Borrador bilingüe con textos y pasos; no se muestra al cliente hasta publicarlo.',
    'title_es': 'Título visible en español, como texto sin código ejecutable.',
    'title_en': 'Título visible en inglés, como texto sin código ejecutable.',
    'description_es': 'Explicación del paso en español.',
    'description_en': 'Explicación del paso en inglés.',
    'steps': 'Pasos en el orden de presentación, usando destinos del mismo contexto.',
    'target': 'Clave de un control conocido de la plataforma; no admite selectores ni URLs libres.',
    'page': 'Número de página, empezando en uno; hasta veinte registros por página.',
    'search': 'Texto para buscar un cliente por nombre o correo.',
    'user_id': 'Identificador del usuario cliente cuyo estado se consulta.',
}


def _describe(schema):
    if 'properties' in schema:
        schema['additionalProperties'] = False
        for key, value in schema['properties'].items():
            value.setdefault('description', DESCRIPTIONS[key])
            _describe(value)
    if 'items' in schema:
        _describe(schema['items'])
    return schema


def _help_op(*args, **kwargs):
    method = args[3] if len(args) > 3 else kwargs.get('method', 'GET')
    if method == 'GET':
        kwargs.setdefault('query_schema', {'type': 'object', 'properties': {}, 'additionalProperties': False})
    for key in ('payload_schema', 'query_schema'):
        if key in kwargs:
            kwargs[key] = _describe(kwargs[key])
    return _op(*args, **kwargs)

QUERY = {'type': 'object', 'properties': {'page': {'type': 'integer', 'minimum': 1},
         'search': {'type': 'string', 'maxLength': 200}}, 'additionalProperties': False}
PROGRESS_QUERY = {'type': 'object', 'properties': {'page': {'type': 'integer', 'minimum': 1},
                  'user_id': {'type': 'integer', 'minimum': 1}}, 'additionalProperties': False}

PLATFORM_HELP_TOOLS = [
    _help_op('get_platform_help_settings', 'Consulta interruptores globales de recorridos y videos y su versión.', 'platform-help-settings', envelope_aliases=False),
    _help_op('update_platform_help_settings', 'Cambia los interruptores globales; el apagado prevalece sobre cualquier cliente.', 'platform-help-settings', 'PATCH', risk='sensitive', confirm=True, payload_schema=writable_schema(HelpFlagsSerializer), envelope_aliases=False),
    _help_op('list_platform_help_clients', 'Lista clientes y sus controles de ayuda con búsqueda y paginación.', 'platform-help-clients', query_schema=QUERY, envelope_aliases=False),
    _help_op('get_platform_help_client', 'Consulta los controles de ayuda de un cliente sin modificar sus vistos.', 'platform-help-client', path=('user_id',), envelope_aliases=False),
    _help_op('update_platform_help_client', 'Cambia la disponibilidad de recorridos y videos de un cliente con versión vigente.', 'platform-help-client', 'PATCH', path=('user_id',), risk='sensitive', confirm=True, payload_schema=writable_schema(HelpFlagsSerializer), envelope_aliases=False),
    _help_op('list_platform_guided_tours', 'Lista borradores, revisiones publicadas y destinos permitidos para recorridos.', 'platform-help-tours', envelope_aliases=False),
    _help_op('get_platform_guided_tour', 'Consulta un recorrido editable bilingüe con su versión vigente.', 'platform-help-tour', path=('tour_id',), envelope_aliases=False),
    _help_op('create_platform_guided_tour', 'Crea una novedad en borrador usando destinos conocidos; no la muestra todavía a clientes.', 'platform-help-tours', 'POST', risk='write', payload_schema=writable_schema(TourWriteSerializer), envelope_aliases=False),
    _help_op('update_platform_guided_tour', 'Edita textos bilingües, orden de pasos y prioridad con control de versión. No publica los textos.', 'platform-help-tour', 'PATCH', path=('tour_id',), risk='write', payload_schema=writable_schema(TourWriteSerializer), envelope_aliases=False),
    _help_op('preview_platform_guided_tour', 'Valida y previsualiza el borrador sin alterar el progreso de ningún cliente.', 'platform-help-tour-preview', path=('tour_id',), envelope_aliases=False),
    _help_op('publish_platform_guided_tour', 'Publica una revisión bilingüe validada. Editar un recorrido existente no reinicia los vistos; para otra novedad crea otra identidad.', 'platform-help-tour-publish', 'POST', path=('tour_id',), risk='sensitive', confirm=True, payload_schema=writable_schema(TourVersionSerializer), envelope_aliases=False),
    _help_op('archive_platform_guided_tour', 'Oculta un recorrido conservando sus revisiones y los vistos de cada usuario.', 'platform-help-tour-archive', 'POST', path=('tour_id',), risk='sensitive', confirm=True, payload_schema=writable_schema(TourVersionSerializer), envelope_aliases=False),
    _help_op('list_platform_guided_tour_revisions', 'Consulta las revisiones inmutables de un recorrido.', 'platform-help-tour-revisions', path=('tour_id',), envelope_aliases=False),
    _help_op('list_platform_tour_progress', 'Consulta estados por usuario paginados; no permite marcar recorridos como vistos por otra persona.', 'platform-help-progress', query_schema=PROGRESS_QUERY, envelope_aliases=False),
]
