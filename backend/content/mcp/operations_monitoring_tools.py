"""Operations owns monitoring follow-up; source ingestion is not delegated."""
from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import writable_schema
from monitoring.serializers import FilterSerializer, NoteSerializer, ResourceLinkSerializer, StateSerializer

DESCRIPTIONS = {
    'page': 'Página positiva; se devuelven 25 registros por página.',
    'resource': 'ID positivo del recurso observado.', 'source': 'ID positivo de la fuente observada.',
    'kind': 'Tipo de recurso: proyecto o servidor.', 'state': 'Estado admitido del caso.',
    'severity': 'Gravedad admitida del caso.', 'search': 'Texto del título, hasta 200 caracteres.',
    'since': 'Fecha inicial inclusiva en formato YYYY-MM-DD.',
    'until': 'Fecha final inclusiva en formato YYYY-MM-DD.',
    'version': 'Versión leída del caso; impide sobrescribir un cambio posterior.',
    'note': 'Nota opcional del cambio de estado, hasta 4000 caracteres.',
    'text': 'Nota interna no vacía, hasta 4000 caracteres; queda atribuida al actor técnico.',
    'project': 'ID del proyecto asociado al recurso; null retira la asociación.',
    'condition': 'Condición técnica activa o recuperada, independiente del seguimiento.',
    'followup': 'Limita a casos pendientes o en revisión, incluso recuperados.',
    'snapshot': 'new inicia una consulta estable; el token recibido permite continuarla.',
    'activities_page': 'Página positiva de notas e historial.',
    'deliveries_page': 'Página positiva de entregas.',
    'history_snapshot': 'Congela el límite superior del historial al iniciar la consulta.',
    'activities_before': 'Límite superior de actividades recibido al consultar el historial.',
    'deliveries_before': 'Límite superior de entregas recibido al consultar el historial.',
    'changes_before': 'Límite superior de cambios de capacidad recibido al consultar su historial.',
}


def _schema(serializer):
    schema = writable_schema(serializer)
    for name, field in schema['properties'].items():
        field['description'] = DESCRIPTIONS[name]
    return schema


def _tool(name, description, route, method='GET', *, detail=False, serializer=None, confirm=False,
          query_fields=None):
    kwargs = {'payload_schema': _schema(serializer)} if serializer and method != 'GET' else {
        'query_schema': _schema(serializer) if serializer else
        {'type': 'object', 'properties': {}, 'additionalProperties': False},
    }
    if query_fields is not None:
        query = kwargs['query_schema']
        query['properties'] = {field: query['properties'][field] for field in query_fields}
    tool = _op(name, description, route, method, ('pk',) if detail else (),
               'sensitive' if confirm else 'read' if method == 'GET' else 'write', confirm,
               envelope_aliases=False, **kwargs)
    if detail:
        tool['input_schema']['properties']['pk'] = {
            'type': 'integer', 'minimum': 1, 'description': 'ID positivo del caso, reporte o recurso indicado por la herramienta.',
        }
    if confirm:
        def impact(arguments):
            resource = 'monitoring_case_id' if 'case' in name else 'monitoring_resource_id'
            return {'summary': description, 'resources': {resource: arguments['pk']},
                    'changes': {key: arguments[key] for key in ('state', 'version', 'project') if key in arguments}}
        tool['impact_builder'] = impact
    return tool


OPERATIONS_MONITORING_TOOLS = [
    _tool('get_monitoring_catalog', 'Consulta recursos y fuentes observadas, su salud y asociación a proyectos; no revela credenciales de ingestión.', 'monitoring-catalog'),
    _tool('list_monitoring_cases', 'Lista casos operativos con filtros y paginación; la evidencia extensa se consulta en el detalle.', 'monitoring-cases', serializer=FilterSerializer),
    _tool('get_monitoring_case', 'Consulta un caso operativo con su evidencia, historial y entregas paginadas; conserva el alcance administrativo.', 'monitoring-case', detail=True, serializer=FilterSerializer, query_fields=('page',)),
    _tool('update_monitoring_case_state', 'Cambia el estado de un caso con su versión vigente y nota; exige confirmación y registra el actor técnico.', 'monitoring-case-state', 'POST', detail=True, serializer=StateSerializer, confirm=True),
    _tool('create_monitoring_case_note', 'Añade una nota interna al caso operativo y la atribuye al actor de la credencial; no modifica evidencia recibida.', 'monitoring-case-note', 'POST', detail=True, serializer=NoteSerializer),
    _tool('list_monitoring_reports', 'Lista reportes operativos con filtros y paginación; el texto completo se consulta en el detalle.', 'monitoring-reports', serializer=FilterSerializer,
          query_fields=('page', 'resource', 'source', 'kind', 'search', 'since', 'until')),
    _tool('get_monitoring_report', 'Consulta el texto y contexto de un reporte operativo recibido, sin modificar su evidencia ni origen.', 'monitoring-report', detail=True),
    _tool('link_monitoring_resource_project', 'Asocia o desvincula el proyecto de un recurso observado con confirmación; conserva las observaciones y su evidencia histórica.', 'monitoring-resource-link', 'PATCH', detail=True, serializer=ResourceLinkSerializer, confirm=True),
]
