"""Complete internal filing administration, sharing the panel's services."""
from functools import partial
from django.db import connection
from secure_links import folder_services as filing
from secure_links.folder_serializers import FolderSerializer, FolderWriteSerializer, ReorderSerializer
from secure_links.models import SecureLinkFolder
from secure_links.services import SecureLinkError
from .actor import mcp_actor
from .protocol import ToolError
from .secure_link_tools import _int, _link_or_error, _reject_unknown, _summary


def _service(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc


def _folder(arguments):
    return _service(filing.folder_for, _int(arguments.get('folder_id'), 'folder_id'))


def _data(serializer_class, arguments):
    serializer = serializer_class(data=arguments)
    if not serializer.is_valid():
        raise ToolError('Revisa el nombre, destino y contexto de la carpeta.', code='INVALID_ARGUMENTS')
    return dict(serializer.validated_data)


def list_secure_link_folders(arguments):
    from secure_links.queries import folder_index
    _reject_unknown(arguments or {}, set())
    return folder_index()


def get_secure_link_folder(arguments):
    _reject_unknown(arguments, {'folder_id'})
    row = _folder(arguments)
    from secure_links.queries import counts_for, filter_links
    return {**FolderSerializer(row).data, 'descendant_ids': sorted(filing.subtree(row) - {row.pk}),
            **_service(lambda: counts_for(filter_links({'folder': str(row.pk)})))}


def create_secure_link_folder(arguments):
    _reject_unknown(arguments, {'name', 'parent', 'client', 'project'})
    if not arguments.get('name'):
        raise ToolError('El nombre es obligatorio.')
    data = _data(FolderWriteSerializer, arguments)
    return FolderSerializer(_service(filing.save_folder, data=data, actor=mcp_actor())).data


def update_secure_link_folder(arguments):
    _reject_unknown(arguments, {'folder_id', 'name', 'expected_updated_at'})
    data = _data(FolderWriteSerializer, {k: v for k, v in arguments.items() if k != 'folder_id'})
    expected = data.pop('expected_updated_at', None)
    return FolderSerializer(_service(filing.save_folder, folder=_folder(arguments), data=data,
                                    actor=mcp_actor(), expected_updated_at=expected)).data


def move_secure_link_folder(arguments):
    _reject_unknown(arguments, {'folder_id', 'parent', 'expected_updated_at'})
    if 'parent' not in arguments:
        raise ToolError('Indica parent; null mueve a la raíz.')
    data = _data(FolderWriteSerializer, {k: v for k, v in arguments.items() if k != 'folder_id'})
    expected = data.pop('expected_updated_at', None)
    return FolderSerializer(_service(filing.save_folder, folder=_folder(arguments), data=data,
                                    actor=mcp_actor(), expected_updated_at=expected)).data


def reorder_secure_link_folders(arguments):
    _reject_unknown(arguments, {'ids', 'parent'})
    _service(filing.reorder_folders, **_data(ReorderSerializer, arguments))
    return {'success': True}


def archive_secure_link_folder(arguments, *, restore=False):
    _reject_unknown(arguments, {'folder_id', 'expected_updated_at'})
    return _service(filing.archive_folder, _folder(arguments), restore=restore, actor=mcp_actor(),
                    expected_updated_at=arguments.get('expected_updated_at'))


def delete_secure_link_folder(arguments):
    _reject_unknown(arguments, {'folder_id'})
    row = _folder(arguments)
    pk = row.pk
    _service(filing.delete_folder, row)
    return {'deleted': True, 'folder_id': pk}


def folder_etags(arguments):
    if connection.in_atomic_block:
        filing.lock_tree()
    row = _folder(arguments)
    return {f'secure-folder:{row.pk}': row.updated_at.isoformat()}


def prepare_delete(arguments):
    _reject_unknown(arguments, {'folder_id'})
    return {'folder_id': _folder(arguments).pk}


def move_secure_link(arguments):
    _reject_unknown(arguments, {'link_id', 'folder_id', 'expected_updated_at'})
    if 'folder_id' not in arguments:
        raise ToolError('Indica folder_id; null mueve a la raíz.')
    target = None if arguments['folder_id'] is None else _service(filing.folder_for, _int(arguments['folder_id'], 'folder_id'))
    return _summary(_service(filing.move_link, _link_or_error(arguments), target, actor=mcp_actor(),
                            expected_updated_at=arguments.get('expected_updated_at')))


ID = {'type': 'integer', 'minimum': 1}
NULL_ID = {'type': ['integer', 'null'], 'minimum': 1}
REVISION = {'expected_updated_at': {'type': 'string', 'format': 'date-time'}}
FOLDER_ID = {'folder_id': ID}


def tool(name, description, handler, properties, required=(), *, risk='write'):
    return {'name': name, 'description': description, 'handler': handler, 'risk': risk,
            'input_schema': {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}}


SECURE_LINK_FOLDER_TOOLS = [
    tool('list_secure_link_folders', 'Lista el árbol completo propio de Enlaces seguros, con conteos directos activos/archivados y navegación por cliente/proyecto. No son las carpetas de hilos ni de documentos.', list_secure_link_folders, {}, risk='read'),
    tool('get_secure_link_folder', 'Consulta una carpeta de Enlaces seguros, sus descendientes y conteos del subárbol sin secretos ni URL.', get_secure_link_folder, FOLDER_ID, ('folder_id',), risk='read'),
    tool('create_secure_link_folder', 'Crea una carpeta propia o subcarpeta. parent=null crea una raíz; hereda contexto inicial del padre.', create_secure_link_folder, {'name': {'type': 'string', 'minLength': 1, 'maxLength': 120}, 'parent': NULL_ID, 'client': NULL_ID, 'project': NULL_ID}, ('name',)),
    tool('update_secure_link_folder', 'Renombra una carpeta manual; las raíces de proyecto se mantienen desde el proyecto.', update_secure_link_folder, {**FOLDER_ID, 'name': {'type': 'string', 'minLength': 1, 'maxLength': 120}, **REVISION}, ('folder_id', 'name')),
    tool('move_secure_link_folder', 'Mueve una carpeta con su subárbol. Rechaza ciclos y destinos archivados. Conserva las asociaciones de su contenido.', move_secure_link_folder, {**FOLDER_ID, 'parent': NULL_ID, **REVISION}, ('folder_id', 'parent')),
    tool('reorder_secure_link_folders', 'Ordena todas las carpetas manuales hermanas; ids debe contenerlas exactamente una vez.', reorder_secure_link_folders, {'ids': {'type': 'array', 'items': ID, 'uniqueItems': True}, 'parent': NULL_ID}, ('ids',)),
    tool('archive_secure_link_folder', 'Archiva la carpeta manual y su contenido, incluidos descendientes. Solo oculta: los enlaces vigentes siguen funcionando.', archive_secure_link_folder, {**FOLDER_ID, **REVISION}, ('folder_id',)),
    tool('restore_secure_link_folder', 'Restaura la carpeta y únicamente el contenido archivado por ella, sin reactivar enlaces.', partial(archive_secure_link_folder, restore=True), {**FOLDER_ID, **REVISION}, ('folder_id',)),
    {**tool('delete_secure_link_folder', 'Elimina tras confirmación una carpeta manual vacía. Contenido archivado y subcarpetas también bloquean.', delete_secure_link_folder, FOLDER_ID, ('folder_id',), risk='sensitive'),
     'confirmation_message': 'Eliminar definitivamente esta carpeta vacía de Enlaces seguros.', 'prepare_arguments': prepare_delete, 'etag_resolver': folder_etags},
    tool('move_secure_link', 'Cambia solo la ubicación interna de un enlace: conserva cliente, proyecto, propietario, audiencia, URL y estado. folder_id=null lo deja en raíz.', move_secure_link, {'link_id': ID, 'folder_id': NULL_ID, **REVISION}, ('link_id', 'folder_id')),
]
