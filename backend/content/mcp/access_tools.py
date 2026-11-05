"""Access controls share panel authority and the MCP confirmation pipeline."""
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from rest_framework.exceptions import APIException
from accounts.services import access
from accounts.views_access import AccessChangeInput, ClientAccessInput, create_access_client
from accounts.access_models import AccessEvent
from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError


def _run(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except APIException as exc:
        raise ToolError(str(exc.detail), code='ACCESS_REJECTED') from None
    except get_user_model().DoesNotExist:
        raise ToolError('Cuenta no encontrada.', code='NOT_FOUND') from None


def list_accesses(arguments):
    return _run(access.list_accesses, mcp_actor(), arguments)


def get_access(arguments):
    user = _run(get_user_model().objects.select_related('profile', 'google_identity').get, pk=arguments['user_id'])
    _run(access.require_manager, mcp_actor(), user)
    data = access.access_payload(user)
    page = Paginator(AccessEvent.objects.filter(user=user), 20).get_page(arguments.get('page', 1))
    data['events'] = [{'action': item.action, 'method': item.method, 'surface': item.surface, 'at': item.created_at.isoformat(), 'ip': item.ip, 'device': item.device} for item in page]
    data['event_page'] = page.number
    data['event_pages'] = page.paginator.num_pages
    return data


def create_client_access(arguments):
    serializer = ClientAccessInput(data=arguments)
    if not serializer.is_valid():
        raise ToolError('Revisa nombre y correo del cliente.', code='INVALID_INPUT')
    return _run(create_access_client, mcp_actor(), serializer.validated_data)


def change_access(arguments):
    serializer = AccessChangeInput(data={key: value for key, value in arguments.items() if key != 'user_id'})
    if not serializer.is_valid():
        raise ToolError('Selecciona un cambio de acceso.', code='INVALID_INPUT')
    return access.access_payload(_run(access.change_access, arguments['user_id'], actor=mcp_actor(), **serializer.validated_data))


def _schema(properties, required=()):
    return {'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': list(required)}


_USER = {'type': 'integer', 'minimum': 1, 'description': 'Identificador de la cuenta existente que se consulta o modifica.'}
_PAGE = {'type': 'integer', 'minimum': 1, 'description': 'Página de resultados, desde 1; cada página contiene hasta 20 registros.'}
ACCESS_TOOLS = [
    {'name': 'list_accesses', 'description': 'Lista cuentas autorizadas y estados; clientes o equipo con búsqueda y filtros, sin secretos.', 'input_schema': _schema({
        'group': {'type': 'string', 'enum': ['clients', 'team'], 'description': 'Grupo de cuentas: clientes por defecto; equipo requiere ser superusuario.'},
        'search': {'type': 'string', 'maxLength': 200, 'description': 'Busca por correo, nombre, apellido o empresa.'},
        'enabled': {'type': 'string', 'enum': ['true', 'false', ''], 'description': 'Filtra acceso habilitado (true), deshabilitado (false) o cualquier estado (vacío).'},
        'onboarded': {'type': 'string', 'enum': ['true', 'false', ''], 'description': 'Filtra perfil completado (true), pendiente (false) o cualquier estado (vacío).'},
        'verified': {'type': 'string', 'enum': ['true', 'false', ''], 'description': 'Filtra correo verificado (true), sin verificar (false) o cualquier estado (vacío).'},
        'google': {'type': 'string', 'enum': ['true', 'false', ''], 'description': 'Filtra identidad Google vinculada (true), sin vincular (false) o cualquier estado (vacío).'},
        'last_access': {'type': 'string', 'enum': ['never', '7', '30', ''], 'description': 'Filtra cuentas sin accesos (never), con acceso en los últimos 7 o 30 días, o sin filtro (vacío).'},
        'page': _PAGE,
        'order': {'type': 'string', 'enum': ['email', 'name', 'recent'], 'description': 'Ordena por correo (predeterminado), nombre o acceso más reciente.'},
    }), 'handler': list_accesses},
    {'name': 'get_access', 'description': 'Consulta cuenta y actividad paginada. Equipo sólo para superusuarios.', 'input_schema': _schema({'user_id': _USER, 'page': _PAGE}, ['user_id']), 'handler': get_access},
    {'name': 'create_client_access', 'risk': 'write', 'description': 'Registra un cliente sin acceso ni proyecto. No habilita ni envía credenciales.', 'input_schema': _schema({'email': {'type': 'string', 'format': 'email', 'description': 'Correo único del cliente que se registra; no habilita su acceso automáticamente.'}, 'name': {'type': 'string', 'maxLength': 150, 'description': 'Nombre del cliente que se registra.'}, 'company': {'type': 'string', 'maxLength': 200, 'description': 'Nombre opcional de la empresa del cliente.'}}, ['name', 'email']), 'handler': create_client_access},
    {'name': 'change_access', 'risk': 'sensitive', 'description': 'Habilita/deshabilita o desvincula Google. Revoca sesiones anteriores. Equipo sólo para superusuarios; protege autobloqueo y último superusuario.', 'confirmation_message': 'Modificar el acceso de esta cuenta y revocar sus sesiones cuando corresponda.', 'input_schema': _schema({'user_id': _USER, 'enabled': {'type': 'boolean', 'description': 'Habilita el acceso (true) o lo deshabilita y revoca las sesiones (false).'}, 'unlink_google': {'type': 'boolean', 'description': 'Si es true, desvincula la identidad Google y revoca las sesiones; false no la modifica.'}}, ['user_id']), 'handler': change_access},
]
