"""Monitoring management shares the Panel's authorization and write services."""
from content.mcp.operation_builder import _op
from content.mcp.schema_policy import closed_object


def field(kind, description, **kwargs):
    return {'type': kind, 'description': description, **kwargs}


PAGE = field('integer', 'Página de 25 registros.', minimum=1)
FILTERS = {
    'page': PAGE,
    'resource': field('integer', 'ID del recurso técnico: proyecto o servidor.', minimum=1),
    'source': field('integer', 'ID de la fuente dentro del recurso.', minimum=1),
    'kind': field('string', 'Tipo del recurso técnico.', enum=['project', 'server']),
    'state': field('string', 'Estado humano del seguimiento.', enum=['pending', 'reviewing', 'resolved']),
    'severity': field('string', 'Gravedad de la observación.', enum=['info', 'warning', 'critical']),
    'condition': field('string', 'Condición técnica, independiente del seguimiento humano.', enum=['active', 'recovered']),
    'followup': field('boolean', 'true limita a seguimientos pending o reviewing, incluso recuperados.'),
    'search': field('string', 'Texto del título, sin buscar dentro de evidencia técnica.', maxLength=200),
    'since': field('string', 'Fecha inicial incluida en la zona horaria del proyecto.', format='date'),
    'until': field('string', 'Fecha final incluida, igual o posterior a since.', format='date'),
    'snapshot': field('string', 'new crea una consulta estable de 15 minutos; el token recibido permite paginarla.', maxLength=64),
}
CAPACITY = {
    'version': field('integer', 'Versión leída; 0 para la primera asignación. Un conflicto exige volver a consultar.', minimum=0),
    **{f'{dimension}_mode': field('string', f'Modalidad de {dimension}: sin configurar, compartida o asignada.', enum=['unknown', 'shared', 'assigned']) for dimension in ['cpu', 'ram', 'storage']},
    'cpu_vcpu': field(['number', 'string', 'null'], 'CPU en vCPU; positiva en modo assigned, null en los demás.'),
    'ram_bytes': field(['integer', 'null'], 'RAM en bytes; positiva en modo assigned, null en los demás.'),
    'storage_bytes': field(['integer', 'null'], 'Almacenamiento en bytes; positivo en modo assigned, null en los demás.'),
}


def operation(name, description, route, *, path=False, query=None, payload=None, method='GET'):
    parameter = 'case_id' if route.startswith('monitoring-case-') else 'report_id' if route == 'monitoring-report-detail' else 'server_id' if route == 'monitoring-series' else 'resource_id'
    tool = _op(name, description, route, method, (parameter,) if path else (),
               'read' if method == 'GET' else 'write', envelope_aliases=False,
               query_schema=closed_object(query or {}) if method == 'GET' else None, payload_schema=payload)
    if path:
        tool['input_schema']['properties'][parameter] = field('integer', 'ID positivo del caso, reporte o recurso técnico indicado por la operación.', minimum=1)
    return tool


MONITORING_TOOLS = [
    operation('get_monitoring_catalog', 'Consulta proyectos, servidores y fuentes, salud y última observación.', 'monitoring-catalog'),
    operation('get_monitoring_status', 'Consulta revisión y presión medida actual de servidores; distingue ausencia de datos.', 'monitoring-status', query={key: value for key, value in FILTERS.items() if key in {'resource', 'source', 'kind'}}),
    operation('list_monitoring_cases', 'Consulta casos de 25 en 25; snapshot=new incluye indicadores y atención del conjunto filtrado completo.', 'monitoring-cases', query=FILTERS),
    operation('get_monitoring_case', 'Consulta evidencia original, estado y páginas independientes de notas y entregas.', 'monitoring-case-detail', path=True, query={'page': PAGE, 'activities_page': PAGE, 'deliveries_page': PAGE,
        'history_snapshot': field('boolean', 'Congela el límite superior del historial para paginar sin incorporar entradas nuevas.'),
        'activities_before': field('integer', 'Límite de notas recibido en history_bounds.activities.', minimum=0),
        'deliveries_before': field('integer', 'Límite de entregas recibido en history_bounds.deliveries.', minimum=0)}),
    operation('set_monitoring_case_state', 'Cambia el seguimiento sin confundirlo con recuperación técnica; exige versión vigente.', 'monitoring-case-state', path=True, method='POST', payload=closed_object({
        'state': FILTERS['state'], 'version': field('integer', 'Versión actual del caso.', minimum=1),
        'note': field('string', 'Nota opcional del cambio.', maxLength=4000),
    }, ['state', 'version'])),
    operation('add_monitoring_case_note', 'Añade una nota con autor y fecha conservando el historial.', 'monitoring-case-note', path=True, method='POST', payload=closed_object({'text': field('string', 'Nota no vacía.', minLength=1, maxLength=4000)}, ['text'])),
    operation('list_monitoring_reports', 'Consulta reportes informativos paginados; retención de 90 días.', 'monitoring-reports', query={key: value for key, value in FILTERS.items() if key not in {'state', 'severity', 'condition', 'followup'}}),
    operation('get_monitoring_report', 'Consulta el texto original saneado de un reporte informativo.', 'monitoring-report-detail', path=True),
    operation('get_monitoring_server_series', 'Consulta muestras reales, huecos y capacidad de RAM, disco, CPU y carga.', 'monitoring-series', path=True, query={'period': field('string', 'Periodo histórico; 24h por defecto.', enum=['24h', '7d', '30d', '90d'])}),
    operation('get_monitoring_capacity', 'Consulta asignación informativa, servidor y disponibilidad de consumo por proyecto.', 'monitoring-capacity', path=True),
    operation('update_monitoring_capacity', 'Registra capacidad informativa sin aplicar límites al servidor; conserva auditoría y versión.', 'monitoring-capacity', path=True, method='PUT', payload=closed_object(CAPACITY, ['version', 'cpu_mode', 'ram_mode', 'storage_mode'])),
    operation('list_monitoring_capacity_history', 'Consulta cambios de capacidad con autor y valores anteriores y posteriores.', 'monitoring-capacity-history', path=True, query={'page': PAGE}),
    operation('link_monitoring_project', 'Vincula un recurso técnico de proyecto con un proyecto comercial; null desvincula.', 'monitoring-resource-link', path=True, method='PATCH', payload=closed_object({'project': field(['integer', 'null'], 'ID de accounts.Project, o null para desvincular.')}, ['project'])),
]
