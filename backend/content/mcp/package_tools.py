"""Administrative parity for examples, purchases, manual sizing and allowance history."""
from content.mcp.operation_builder import _op
from content.mcp.schema_policy import closed_object


def field(kind, description, **kwargs):
    return {'type': kind, 'description': description, **kwargs}


TOKEN = field('string', 'UUID estable para repetir esta operación sin duplicar efectos.', format='uuid')
VERSION = field('integer', 'Versión del registro obtenida en la consulta anterior.', minimum=0)
PAGE = {'offset': field('integer', 'Cantidad de registros anteriores que se omiten.', minimum=0)}
LANG = field('string', 'Idioma de los ejemplos o condiciones.', enum=['es', 'en'])
EXAMPLES = {
    'request_id': TOKEN, 'expected_revision': VERSION,
    'examples': field('object', 'Ejemplos completos del ámbito; omitir una talla del proyecto restaura su ejemplo genérico.',
        properties={size: {'type': 'array', 'items': {'type': 'string', 'minLength': 1, 'maxLength': 2000},
                    'minItems': 1, 'maxItems': 10} for size in ('XS', 'S', 'M', 'L', 'XL', 'PROJECT')}, additionalProperties=False),
    'note': field('string', 'Motivo de la revisión conservado en el historial.', minLength=1, maxLength=2000),
    'language': LANG,
}


def operation(name, description, route, *, path=(), fields=None, required=(), write=False, confirm=False):
    schema = closed_object(fields or {}, required=list(required))
    return _op(name, description, route, method='POST' if write else 'GET', path=path,
        risk='sensitive' if confirm else 'write' if write else 'read', confirm=confirm,
        envelope_aliases=False, **({'payload_schema': schema} if write else {'query_schema': schema}))


PACKAGE_GENERAL_TOOLS = [
    operation('get_package_generic_examples', 'Consulta los ejemplos genéricos por talla, sin horas ni parámetros económicos internos.',
              'package-examples-general', fields={'language': LANG}),
    operation('publish_package_generic_examples', 'Publica ejemplos genéricos versionados sin cambiar precios ni calculadoras aprobadas.',
              'package-examples-general', fields=EXAMPLES, required=tuple(EXAMPLES), write=True, confirm=True),
    operation('list_package_generic_example_history', 'Consulta las revisiones y autoría de los ejemplos genéricos de requerimientos.',
              'package-examples-general-history', fields={**PAGE, 'language': LANG}),
]

PACKAGE_PROJECT_TOOLS = [
    operation('get_project_requirement_packages', 'Consulta catálogo público, compras, saldos, movimientos y solicitudes del proyecto.',
              'package-overview', path=('project_id',), fields={'language': LANG,
                **{key: field('integer', 'Desplazamiento de esta colección paginada.', minimum=0)
                   for key in ('order_offset', 'request_offset', 'movement_offset')}}),
    operation('get_project_package_examples', 'Consulta ejemplos particulares y genéricos; los particulares prevalecen por talla.',
              'package-examples', path=('project_id',), fields={'language': LANG}),
    operation('publish_project_package_examples', 'Publica ejemplos particulares del proyecto sin alterar parámetros ni acuerdos congelados.',
              'package-examples', path=('project_id',), fields=EXAMPLES, required=tuple(EXAMPLES), write=True, confirm=True),
    operation('list_project_package_example_history', 'Consulta revisiones completas de los ejemplos del proyecto con autor y motivo.',
              'package-examples-history', path=('project_id',), fields={**PAGE, 'language': LANG}),
    operation('get_package_request', 'Consulta la solicitud y sus propuestas de talla conservadas, incluidas las decisiones del cliente.',
              'package-request-detail', path=('project_id', 'package_request_id')),
    operation('get_package_evaluation_context', 'Consulta la definición interna aplicable para que el equipo evalúe manualmente una solicitud.',
              'package-evaluation-context', path=('project_id',)),
    operation('create_package_purchase', 'Registra una orden por proyecto con condiciones aceptadas. No acredita pago ni activa cupos.',
              'package-order-create', path=('project_id',), write=True,
              fields={'request_id': TOKEN, 'package_id': field('integer', 'Paquete del catálogo vigente.', minimum=1),
                      'method': field('string', 'Método de pago que se utilizará.', enum=['online', 'external']),
                      'language': LANG, 'conditions_accepted': field('boolean', 'Confirma que se revisaron y aceptaron las condiciones.'),
                      'quote_digest': field('string', 'Huella de la oferta obtenida en el catálogo del proyecto.', minLength=64, maxLength=64)},
              required=('request_id', 'package_id', 'method', 'conditions_accepted', 'quote_digest')),
    operation('create_package_request', 'Registra una solicitud general para evaluación manual sin consumir cupos ni asignar talla automáticamente.',
              'package-request-create', path=('project_id',), write=True,
              fields={'request_id': TOKEN, 'title': field('string', 'Título del resultado solicitado.', minLength=1, maxLength=300),
                      'description': field('string', 'Descripción y contexto del cambio solicitado.', minLength=1, maxLength=15000)},
              required=('request_id', 'title', 'description')),
    operation('update_project_package_settings', 'Configura mercado e impuesto del catálogo del proyecto para nuevas compras; las órdenes previas no cambian.',
              'package-settings', path=('project_id',), write=True,
              fields={'request_id': TOKEN, 'expected_version': VERSION,
                      'nationality': field('string', 'Mercado autorizado para el proyecto.', enum=['COL', 'EXT', 'USA']),
                      'tax_rate': field('number', 'Porcentaje de impuesto aplicable a nuevas compras.', minimum=0, maximum=100)},
              required=('request_id', 'expected_version', 'nationality', 'tax_rate'), confirm=True),
    operation('reverse_package_consumption', 'Revierte un consumo administrativo con motivo. No devuelve dinero ni amplía el vencimiento original.',
              'package-reverse', path=('project_id', 'movement_id'), write=True, confirm=True,
              fields={'request_id': TOKEN, 'reason': field('string', 'Motivo obligatorio de la corrección.', minLength=1, maxLength=2000)},
              required=('request_id', 'reason')),
]

# Fixed action wrappers keep routes unambiguous in the public catalog and never
# expose the client's consent endpoint through an administrative credential.
def action_tool(name, description, action, *, order=False, fields=None, required=(), confirm=False):
    tool = operation(name, description, 'package-order-action' if order else 'package-request-action',
        path=('project_id', 'order_key' if order else 'package_request_id', 'action'),
        fields=fields, required=required, write=True, confirm=confirm)
    tool['input_schema']['properties']['action']['enum'] = [action]
    if order:
        tool['input_schema']['properties']['order_key'] = field('string', 'UUID de la orden del proyecto.', format='uuid')
    return tool


PACKAGE_PROJECT_TOOLS += [
    action_tool('prepare_package_checkout', 'Prepara o recupera el enlace COP de la compra sin acreditar cupos ni crear una suscripción de hosting.',
        'checkout', order=True, fields={'request_id': TOKEN}, required=('request_id',)),
    action_tool('verify_package_payment', 'Verifica la transacción canónica de la pasarela y acredita la compra únicamente cuando coincide y está aprobada.',
        'verify', order=True,
        fields={'request_id': TOKEN, 'transaction_id': field('string', 'Id de transacción obtenido al regresar de la pasarela.', maxLength=100)},
        required=('request_id', 'transaction_id')),
    action_tool('confirm_external_package_payment', 'Confirma un pago externo con fecha y referencia y acredita cupos una sola vez.',
        'confirm-external', order=True, confirm=True,
        fields={'request_id': TOKEN, 'paid_at': field('string', 'Fecha real del pago con zona horaria.', format='date-time'),
                'payment_reference': field('string', 'Referencia del pago recibido; nunca credenciales.', minLength=1, maxLength=200)},
        required=('request_id', 'paid_at', 'payment_reference')),
    action_tool('begin_package_request_evaluation', 'Marca el inicio de la evaluación manual y avisa al cliente sin consumir cupos.', 'evaluate',
        fields={'request_id': TOKEN, 'expected_version': VERSION}, required=('request_id', 'expected_version')),
    action_tool('publish_package_size_proposal', 'Publica una talla explicada y agenda orientativa; requiere aceptación posterior del cliente y no descuenta cupos.', 'offer', confirm=True,
        fields={'request_id': TOKEN, 'expected_version': VERSION,
                'size': field('string', 'Talla evaluada por el equipo.', enum=['XS', 'S', 'M', 'L', 'XL', 'PROJECT']),
                **{key: field('string', 'Texto público de la propuesta: ' + key + '.', maxLength=limit)
                   for key, limit in [('scope', 15000), ('explanation', 8000), ('assumptions', 8000), ('schedule_conditions', 4000)]},
                'delivery_from': field('string', 'Inicio del rango orientativo de entrega.', format='date'),
                'delivery_until': field('string', 'Final del rango orientativo de entrega.', format='date'),
                'signal_ids': field('array', 'Señales de la definición aplicable que justifican la talla.', items={'type': 'string'}, maxItems=100),
                'warranty': field('boolean', 'Indica corrección cubierta por garantía, sin consumo.'), 'language': LANG},
        required=('request_id', 'expected_version', 'size', 'scope', 'explanation', 'delivery_from', 'delivery_until', 'signal_ids')),
]
