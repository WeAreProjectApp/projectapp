"""Platform help administration stays in the existing projects connector."""
from accounts.serializers_platform_help import HelpFlagsSerializer, TourWriteSerializer, TourVersionSerializer
from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import writable_schema

QUERY = {'type': 'object', 'properties': {'page': {'type': 'integer', 'minimum': 1},
         'search': {'type': 'string', 'maxLength': 200}}, 'additionalProperties': False}
PROGRESS_QUERY = {'type': 'object', 'properties': {'page': {'type': 'integer', 'minimum': 1},
                  'user_id': {'type': 'integer', 'minimum': 1}}, 'additionalProperties': False}

PLATFORM_HELP_TOOLS = [
    _op('get_platform_help_settings', 'Consulta interruptores globales de recorridos y videos y su versión.', 'platform-help-settings', envelope_aliases=False),
    _op('update_platform_help_settings', 'Cambia los interruptores globales; el apagado prevalece sobre cualquier cliente.', 'platform-help-settings', 'PATCH', risk='sensitive', confirm=True, payload_schema=writable_schema(HelpFlagsSerializer), envelope_aliases=False),
    _op('list_platform_help_clients', 'Lista clientes y sus controles de ayuda con búsqueda y paginación.', 'platform-help-clients', query_schema=QUERY, envelope_aliases=False),
    _op('get_platform_help_client', 'Consulta los controles de ayuda de un cliente sin modificar sus vistos.', 'platform-help-client', path=('user_id',), envelope_aliases=False),
    _op('update_platform_help_client', 'Cambia la disponibilidad de recorridos y videos de un cliente con versión vigente.', 'platform-help-client', 'PATCH', path=('user_id',), risk='sensitive', confirm=True, payload_schema=writable_schema(HelpFlagsSerializer), envelope_aliases=False),
    _op('list_platform_guided_tours', 'Lista borradores, revisiones publicadas y destinos permitidos para recorridos.', 'platform-help-tours', envelope_aliases=False),
    _op('get_platform_guided_tour', 'Consulta un recorrido editable bilingüe con su versión vigente.', 'platform-help-tour', path=('tour_id',), envelope_aliases=False),
    _op('create_platform_guided_tour', 'Crea una novedad en borrador usando destinos conocidos; no la muestra todavía a clientes.', 'platform-help-tours', 'POST', risk='write', payload_schema=writable_schema(TourWriteSerializer), envelope_aliases=False),
    _op('update_platform_guided_tour', 'Edita textos bilingües, orden de pasos y prioridad con control de versión. No publica los textos.', 'platform-help-tour', 'PATCH', path=('tour_id',), risk='write', payload_schema=writable_schema(TourWriteSerializer), envelope_aliases=False),
    _op('preview_platform_guided_tour', 'Valida y previsualiza el borrador sin alterar el progreso de ningún cliente.', 'platform-help-tour-preview', path=('tour_id',), envelope_aliases=False),
    _op('publish_platform_guided_tour', 'Publica una revisión bilingüe validada. Editar un recorrido existente no reinicia los vistos; para otra novedad crea otra identidad.', 'platform-help-tour-publish', 'POST', path=('tour_id',), risk='sensitive', confirm=True, payload_schema=writable_schema(TourVersionSerializer), envelope_aliases=False),
    _op('archive_platform_guided_tour', 'Oculta un recorrido conservando sus revisiones y los vistos de cada usuario.', 'platform-help-tour-archive', 'POST', path=('tour_id',), risk='sensitive', confirm=True, payload_schema=writable_schema(TourVersionSerializer), envelope_aliases=False),
    _op('list_platform_guided_tour_revisions', 'Consulta las revisiones inmutables de un recorrido.', 'platform-help-tour-revisions', path=('tour_id',), envelope_aliases=False),
    _op('list_platform_tour_progress', 'Consulta estados por usuario paginados; no permite marcar recorridos como vistos por otra persona.', 'platform-help-progress', query_schema=PROGRESS_QUERY, envelope_aliases=False),
]
