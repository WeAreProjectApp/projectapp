"""Procurement MCP adapters. The external assistant supplies analysis, never executes inside ProjectApp."""
import base64

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import APIException

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError
from procurement.models import Alert, Delivery, SavedSearch, Settings
from procurement.serializers import AlertSerializer, DeliverySerializer, DeliverySummarySerializer, SavedSearchSerializer, SettingsSerializer, SyncRunSerializer, owner_for_mcp
from procurement.services import records

STRING = {'type': 'string'}
ID = {'type': 'integer', 'minimum': 1}
FILTER_PROPERTIES = {
    key: {'type': 'array', 'items': STRING, 'maxItems': 33}
    for key in ['keywords', 'unspsc_codes', 'entity_names', 'departments', 'methods', 'contract_types', 'statuses']
}
FILTER_PROPERTIES.update({key: STRING for key in ['search', 'published_from', 'published_to', 'closing_from', 'closing_to']})
FILTER_PROPERTIES.update({key: {'type': ['string', 'number']} for key in ['min_budget', 'max_budget']})
FILTER_PROPERTIES['is_open'] = {'type': 'boolean'}
FILTERS = {'type': 'object', 'properties': FILTER_PROPERTIES, 'additionalProperties': False}
QUERY = {'filters': FILTERS, 'page': ID, 'page_size': {'type': 'integer', 'minimum': 1, 'maximum': 100},
         'ordering': {'type': 'string', 'enum': ['-published_at', 'closing_at', '-budget', 'entity_name']},
         'classified': {'type': 'boolean'}, 'state': {'type': 'string', 'enum': ['interesting', 'reviewing', 'applied', 'discarded']}}
ALERT = {'name': STRING, 'filters': FILTERS, 'recipients': {'type': 'array', 'items': {'type': 'string', 'format': 'email'}, 'minItems': 1, 'maxItems': 10},
         'frequency': {'type': 'string', 'enum': ['immediate', 'daily', 'weekly']}, 'is_active': {'type': 'boolean'}}
SEARCH = {'name': STRING, 'filters': FILTERS, 'is_favorite': {'type': 'boolean'}}
CONFIG = {'sync_enabled': {'type': 'boolean'}, 'email_enabled': {'type': 'boolean'},
          'sync_time': STRING, 'daily_time': STRING, 'weekly_time': STRING,
          'weekly_day': {'type': 'integer', 'minimum': 0, 'maximum': 6},
          'lookback_days': {'type': 'integer', 'minimum': 1, 'maximum': 365}}


def owner(arguments):
    return owner_for_mcp(arguments['owner_id']) if 'owner_id' in arguments else mcp_actor()


def operation(name, arguments):
    args = dict(arguments)
    actor = mcp_actor()
    selected_owner = owner(args)
    pk = args.pop('id', None)
    args.pop('owner_id', None)
    if name == 'list_procurement_opportunities':
        return records.list_opportunities(args, selected_owner)
    if name == 'get_procurement_opportunity':
        return records.detail(pk)
    if name == 'get_procurement_filters':
        return records.filter_catalog()
    if name == 'export_procurement_opportunities':
        return {'filename': 'oportunidades-secop.xlsx', 'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'base64': base64.b64encode(records.export_opportunities(args, selected_owner)).decode()}
    if name in ('set_procurement_classification', 'restore_procurement_classification'):
        context = current_mcp_context()
        return records.classify(pk, args, selected_owner, actor, restore=name.startswith('restore'),
                                credential=context.credential if context else None)
    if name == 'list_procurement_searches':
        return {'results': SavedSearchSerializer(SavedSearch.objects.filter(owner=selected_owner), many=True).data}
    if name in ('create_procurement_search', 'update_procurement_search'):
        return records.save_search(args, selected_owner, pk)
    if name == 'delete_procurement_search':
        records.found(SavedSearch, pk, owner=selected_owner).delete()
        return {'deleted': True}
    if name == 'list_procurement_alerts':
        return {'results': AlertSerializer(Alert.objects.all()[:500], many=True).data}
    if name in ('create_procurement_alert', 'update_procurement_alert'):
        return records.save_alert(args, actor, pk)
    if name == 'preview_procurement_alert':
        alert = records.found(Alert, pk)
        return records.list_opportunities({'filters': {**alert.filters, 'is_open': True}}, selected_owner)
    if name == 'get_procurement_settings':
        return SettingsSerializer(Settings.current()).data
    if name == 'update_procurement_settings':
        return records.save_settings(args)
    if name == 'get_procurement_sync_status':
        return records.sync_status()
    if name == 'request_procurement_sync':
        from procurement.services.sync import request_sync
        return SyncRunSerializer(request_sync(actor)).data
    if name == 'list_procurement_deliveries':
        return records.page(Delivery.objects.defer('snapshot'), DeliverySummarySerializer, args.get('page', 1))
    if name == 'get_procurement_delivery':
        return DeliverySerializer(records.found(Delivery, pk)).data
    if name == 'retry_procurement_delivery':
        from procurement.services.notifications import retry_delivery
        return retry_delivery(pk)
    raise ToolError('Operación de contratación no disponible.')


def tool(name, description, properties=None, required=()):
    allowed = set(properties or {})
    def handler(arguments):
        if not isinstance(arguments, dict) or set(arguments) - allowed or any(key not in arguments for key in required):
            raise ToolError('Argumentos incompletos o no permitidos; consulta el esquema de la herramienta.')
        # Direct invocations must meet the same primitive schema as HTTP MCP calls.
        from content.mcp.issue_tools import _validate
        try:
            _validate(arguments, schema)
            return operation(name, arguments)
        except (APIException, ObjectDoesNotExist) as exc:
            detail = getattr(exc, 'detail', 'Datos inválidos o registro no disponible.')
            raise ToolError(str(detail)) from exc
    schema = {'type': 'object', 'properties': properties or {}, 'required': list(required), 'additionalProperties': False}
    return {'name': name, 'description': description, 'input_schema': schema, 'handler': handler,
            'strict_arguments': True, 'output_schema': {'type': 'object'},
            'risk': 'sensitive' if name in {'create_procurement_alert', 'update_procurement_alert', 'update_procurement_settings', 'retry_procurement_delivery', 'delete_procurement_search'} else ('read' if name.startswith(('list_', 'get_', 'export_', 'preview_')) else 'write')}


PROCUREMENT_TOOLS = [
    tool('list_procurement_opportunities', 'Consulta SECOP II con los mismos filtros del panel. owner_id permite ver clasificaciones del administrador indicado.', {**QUERY, 'owner_id': ID}),
    tool('get_procurement_opportunity', 'Lee detalle, notas del equipo e historial de decisiones.', {'id': ID}, ['id']),
    tool('get_procurement_filters', 'Obtiene entidades, departamentos de entidad y modalidades disponibles.'),
    tool('export_procurement_opportunities', 'Exporta hasta 5.000 coincidencias a Excel en base64.', {**QUERY, 'owner_id': ID}),
    tool('set_procurement_classification', 'Registra el análisis externo en notes y su estado para owner_id. Descartar exige motivo; nunca borra el proceso.',
         {'id': ID, 'owner_id': ID, 'state': QUERY['state'], 'notes': STRING}, ['id', 'owner_id', 'state', 'notes']),
    tool('restore_procurement_classification', 'Restaura un descarte al estado anterior y conserva la evidencia.', {'id': ID, 'owner_id': ID}, ['id', 'owner_id']),
    tool('list_procurement_searches', 'Lista las búsquedas del administrador owner_id.', {'owner_id': ID}, ['owner_id']),
    tool('create_procurement_search', 'Guarda una búsqueda y, opcionalmente, la marca como favorita.', {**SEARCH, 'owner_id': ID}, ['owner_id', 'name', 'filters']),
    tool('update_procurement_search', 'Edita nombre, filtros o favorito sin modificar alertas creadas previamente.', {**SEARCH, 'id': ID, 'owner_id': ID}, ['id', 'owner_id']),
    tool('delete_procurement_search', 'Elimina sólo una búsqueda guardada; no elimina sus alertas.', {'id': ID, 'owner_id': ID}, ['id', 'owner_id']),
    tool('list_procurement_alerts', 'Lista alertas compartidas, destinatarios, frecuencia y activación.'),
    tool('create_procurement_alert', 'Crea una alerta con filtros independientes y uno a diez destinatarios. Inactiva por defecto.', ALERT, ['name', 'filters', 'recipients']),
    tool('update_procurement_alert', 'Edita o desactiva una alerta. is_active=true habilita la evaluación y futuros envíos si el correo global está activo.', {**ALERT, 'id': ID}, ['id']),
    tool('preview_procurement_alert', 'Previsualiza coincidencias vigentes sin enviar correos.', {'id': ID}, ['id']),
    tool('get_procurement_settings', 'Lee horarios Bogotá, ventanas de consulta y activación global.'),
    tool('update_procurement_settings', 'Configura horarios y activación. email_enabled=true autoriza los envíos de alertas activas.', CONFIG),
    tool('get_procurement_sync_status', 'Lee historial y última sincronización exitosa.'),
    tool('request_procurement_sync', 'Solicita una sincronización pública; reutiliza una ejecución ya en curso.'),
    tool('list_procurement_deliveries', 'Consulta entregas, filtros enviados, fallos y resultados inciertos.', {'page': ID}),
    tool('get_procurement_delivery', 'Lee el contenido y filtros exactos de una entrega, sin volver a enviarla.', {'id': ID}, ['id']),
    tool('retry_procurement_delivery', 'Reintenta una entrega fallida o incierta. Verifica el buzón antes de repetir una incierta porque podría haberse enviado.', {'id': ID}, ['id']),
]
