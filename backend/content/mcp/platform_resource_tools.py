"""Administrative resource adapters over the shared Platform services."""
import hashlib
import json
from copy import deepcopy

from accounts.models import Deliverable, DeliveryOperation
from accounts.services import platform_data_model as data_model
from accounts.services import platform_resources as resources
from accounts.services.delivery_access import project_for_actor
from accounts.services.platform_resource_operations import workspace_version
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from content.mcp.context import current_mcp_context
from content.mcp.delivery_tools import ID, REQUEST_ID, TEXT, VERSION, _call
from content.mcp.delivery_tools import _tool as delivery_tool
from content.mcp.issue_tools import _validate as validate_schema
from content.mcp.protocol import ToolError
from content.mcp.upload_tools import _upload_or_error, store_artifact
from content.models import McpUpload

PROJECT_ID = {**ID, 'description': 'Identificador entero positivo del proyecto autorizado.'}
RESOURCE_ID = {**ID, 'description': 'Identificador entero positivo del recurso dentro del proyecto.'}
FOLDER_ID = {**ID, 'description': 'Identificador entero positivo de la carpeta dentro del recurso.'}
ASSET_ID = {'type': 'string', 'format': 'uuid', 'description': (
    'UUID de un archivo completado por esta credencial; hasta 25 MB. '
    'Los archivos del cliente deben ser PDF de hasta 15 MB.'
)}
CATEGORY = {'type': 'string', 'enum': [value for value, _label in Deliverable.CATEGORY_CHOICES],
            'description': 'Categoría del recurso o adjunto; other por defecto al crear.'}
META = {'type': 'object', 'additionalProperties': False,
        'properties': {
            'title': {**TEXT, 'minLength': 1, 'maxLength': 300,
                      'description': 'Título del recurso, de 1 a 300 caracteres.'},
            'description': {**TEXT, 'description': 'Descripción del recurso; vacía por defecto al crearlo.'},
            'category': CATEGORY,
        }}
ATTACHMENT = {'type': 'object', 'additionalProperties': False,
              'properties': {'title': {**TEXT, 'description': 'Título del adjunto; vacío por defecto.'},
                             'category': CATEGORY}}
CLIENT_FILE = {'type': 'object', 'additionalProperties': False,
               'properties': {'title': {**TEXT, 'description': 'Título del PDF del cliente; vacío por defecto.'},
                              'folder_id': {'type': ['integer', 'null'], 'minimum': 1,
                                            'description': 'Identificador de carpeta del recurso; nulo o ausente deja el PDF sin carpeta.'}}}
FOLDER = {'type': 'object', 'additionalProperties': False,
          'properties': {'name': {**TEXT, 'minLength': 1, 'maxLength': 200,
                                 'description': 'Nombre de la carpeta, de 1 a 200 caracteres.'},
                         'order': {'type': 'integer', 'minimum': 0,
                                   'description': 'Orden de la carpeta, entero desde 0; al crearla, 0 por defecto.'}}}
ENTITY = {'type': 'object', 'additionalProperties': False,
          'properties': {'name': {**TEXT, 'minLength': 1, 'maxLength': 300},
                         **{name: TEXT for name in ('description', 'keyFields', 'relationship')}},
          'required': ['name']}
MODEL = {'type': 'object', 'additionalProperties': False,
         'properties': {'entities': {'type': 'array', 'items': ENTITY, 'maxItems': 1000,
                                    'description': 'Lista de hasta 1000 entidades; cada una requiere name. Una lista vacía elimina las entidades al importar.'}},
         'required': ['entities']}
RESOURCE_VERSION = {**VERSION, 'description': 'Versión vigente del espacio del proyecto, entero desde 0, obtenida al consultar recursos.'}
WRITE = {'expected_version': RESOURCE_VERSION, 'request_id': REQUEST_ID}


def _tool(name, description, handler, properties=None, required=(), *, risk='read'):
    return delivery_tool(name, description, handler,
                         {'project_id': PROJECT_ID, **(properties or {})}, required, risk=risk)


def _credential():
    context = current_mcp_context()
    if (context is None or context.credential is None or not context.credential.is_usable
            or context.actor is None or context.credential.actor_id != context.actor.pk):
        raise ToolError('Se requiere una credencial MCP activa.', code='FORBIDDEN')
    return context.credential


def _operation(arguments):
    return {'expected_version': arguments['expected_version'], 'request_id': arguments['request_id'],
            'credential': _credential(), 'expected_client_id': arguments.get('expected_client_id')}


def _safe(value):
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()
                if key not in {'file_url', 'file', 'download_url'}}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    return value


def _result(arguments, actor, function, *args, **kwargs):
    _credential()
    result = _safe(_call(function, arguments['project_id'], actor, *args, **kwargs))
    project = _call(project_for_actor, arguments['project_id'], actor)
    return {'project_id': project.pk, 'version': workspace_version(project), 'result': result}


def _data(arguments, schema):
    return {key: deepcopy(arguments[key]) for key in schema['properties'] if key in arguments}


def _upload(arguments, actor, function, schema=None):
    upload = _upload_or_error(arguments['asset_id'], lock=True)
    if upload.status == McpUpload.STATUS_CONSUMED:
        # A completed request may be replayed; a consumed file is never a new upload.
        if not DeliveryOperation.objects.filter(project_id=arguments['project_id'],
                actor=actor, request_id=arguments['request_id']).exists():
            raise ToolError('El archivo ya fue consumido.', code='CONFLICT')
    elif upload.status != McpUpload.STATUS_COMPLETE:
        raise ToolError('Completa el archivo antes de asociarlo.', code='CONFLICT')
    with upload.file.open('rb') as source:
        body = source.read(25 * 1024 * 1024 + 1)
    if len(body) > 25 * 1024 * 1024:
        raise ToolError('El archivo supera 25 MB.')
    file = SimpleUploadedFile(upload.filename, body, content_type=upload.content_type)
    values = {**(_data(arguments, schema) if schema else {}), 'file': file}
    ids = [arguments['resource_id']] if 'resource_id' in arguments else []
    result = _result(arguments, actor, function, *ids, values, **_operation(arguments))
    upload.status = McpUpload.STATUS_CONSUMED
    upload.consumed_at = upload.consumed_at or timezone.now()
    upload.save(update_fields=['status', 'consumed_at', 'updated_at'])
    return result


def _download(arguments, actor):
    credential = _credential()
    body, filename, mime = _call(resources.read_file, arguments['project_id'], actor,
        arguments['resource_id'], kind=arguments.get('kind', 'current'), file_id=arguments.get('file_id'))
    context = current_mcp_context()
    return store_artifact(connector=context.connector, credential=credential, filename=filename,
                          content_type=mime, content=body, request=context.request)


def _resource_update(arguments, actor, *, archived=None):
    data = _data(arguments, META) if archived is None else {'is_archived': archived}
    return _result(arguments, actor, resources.update_resource, arguments['resource_id'], data, **_operation(arguments))


PLATFORM_RESOURCE_TOOLS = [
    _tool('list_project_resources', 'Lista recursos del proyecto por categoría; conserva el archivo y sus versiones históricas.',
          lambda args, actor: _result(args, actor, resources.list_resources,
              include_archived=args.get('include_archived', False), category=args.get('category')),
          {'category': {**CATEGORY, 'description': 'Categoría por la que filtrar; si se omite, incluye todas.'},
           'include_archived': {'type': 'boolean', 'description': 'Incluye recursos archivados; false por defecto.'}}),
    _tool('get_project_resource', 'Consulta un recurso con versiones, adjuntos, carpetas, archivos del cliente y entidades.',
          lambda args, actor: _result(args, actor, resources.get_resource, args['resource_id']),
          {'resource_id': RESOURCE_ID}, ('resource_id',)),
    _tool('create_project_resource', 'Previsualiza la creación de un recurso compartido con el cliente, usando un asset validado de esta credencial.',
          lambda args, actor: _upload(args, actor, resources.create_resource, META),
          {**WRITE, 'asset_id': ASSET_ID, **META['properties']},
          ('asset_id', 'title', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('update_project_resource', 'Actualiza metadatos del recurso tras confirmación; conserva el archivo y el número de versión.',
          _resource_update, {**WRITE, 'resource_id': RESOURCE_ID, **META['properties']},
          ('resource_id', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('archive_project_resource', 'Archiva un recurso tras confirmación sin borrar archivos ni historia.',
          lambda args, actor: _resource_update(args, actor, archived=True), {**WRITE, 'resource_id': RESOURCE_ID},
          ('resource_id', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('restore_project_resource', 'Restaura un recurso archivado tras confirmación y recupera su consulta para el cliente.',
          lambda args, actor: _resource_update(args, actor, archived=False), {**WRITE, 'resource_id': RESOURCE_ID},
          ('resource_id', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('upload_project_resource_version', 'Agrega una versión desde un asset propio tras confirmación, conservando las versiones anteriores.',
          lambda args, actor: _upload(args, actor, resources.upload_version), {**WRITE, 'resource_id': RESOURCE_ID, 'asset_id': ASSET_ID},
          ('resource_id', 'asset_id', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('list_project_resource_attachments', 'Consulta metadatos de adjuntos de un recurso del proyecto sin revelar rutas privadas.',
          lambda args, actor: _result(args, actor, resources.list_attachments, args['resource_id']),
          {'resource_id': RESOURCE_ID}, ('resource_id',)),
    _tool('upload_project_resource_attachment', 'Asocia un adjunto validado de esta credencial al recurso tras confirmación.',
          lambda args, actor: _upload(args, actor, resources.upload_attachment, ATTACHMENT),
          {**WRITE, 'resource_id': RESOURCE_ID, 'asset_id': ASSET_ID, **ATTACHMENT['properties']},
          ('resource_id', 'asset_id', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('list_project_resource_folders', 'Lista las carpetas de archivos del cliente de un recurso del proyecto.',
          lambda args, actor: _result(args, actor, resources.list_folders, args['resource_id']),
          {'resource_id': RESOURCE_ID}, ('resource_id',)),
    _tool('create_project_resource_folder', 'Crea una carpeta de archivos del cliente tras confirmación administrativa.',
          lambda args, actor: _result(args, actor, resources.create_folder, args['resource_id'], _data(args, FOLDER), **_operation(args)),
          {**WRITE, 'resource_id': RESOURCE_ID, **FOLDER['properties']},
          ('resource_id', 'name', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('update_project_resource_folder', 'Actualiza nombre y orden de una carpeta del recurso tras confirmación.',
          lambda args, actor: _result(args, actor, resources.change_folder, args['resource_id'], args['folder_id'], _data(args, FOLDER), **_operation(args)),
          {**WRITE, 'resource_id': RESOURCE_ID, 'folder_id': FOLDER_ID, **FOLDER['properties']},
          ('resource_id', 'folder_id', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('delete_project_resource_folder', 'Elimina una carpeta y sus registros de archivos según la operación existente de Platform, tras confirmación.',
          lambda args, actor: _result(args, actor, resources.change_folder, args['resource_id'], args['folder_id'], {}, delete=True, **_operation(args)),
          {**WRITE, 'resource_id': RESOURCE_ID, 'folder_id': FOLDER_ID},
          ('resource_id', 'folder_id', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('list_project_resource_client_files', 'Consulta archivos del cliente asociados al recurso; las descargas requieren la operación autorizada.',
          lambda args, actor: _result(args, actor, resources.list_client_files, args['resource_id']),
          {'resource_id': RESOURCE_ID}, ('resource_id',)),
    _tool('upload_project_resource_client_file', 'Adjunta un PDF de hasta 15 MB a una carpeta del recurso con actor administrativo real, tras confirmación.',
          lambda args, actor: _upload(args, actor, resources.upload_client_file, CLIENT_FILE),
          {**WRITE, 'resource_id': RESOURCE_ID, 'asset_id': ASSET_ID, **CLIENT_FILE['properties']},
          ('resource_id', 'asset_id', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('download_project_resource_file', 'Descarga los bytes autorizados del archivo actual, una versión, adjunto o archivo del cliente como artefacto temporal propio.',
          _download, {'resource_id': RESOURCE_ID,
                      'kind': {'type': 'string', 'enum': ['current', 'version', 'attachment', 'client_upload'],
                               'description': 'Archivo actual, versión, adjunto o PDF del cliente; current por defecto.'},
                      'file_id': {**ID, 'description': 'Identificador entero positivo del archivo hijo; se omite para current.'}},
          ('resource_id',)),
    _tool('get_project_data_model', 'Consulta las entidades actuales del modelo de datos compartido con el cliente.',
          lambda args, actor: _result(args, actor, data_model.list_entities)),
    _tool('get_project_data_model_template', 'Obtiene la plantilla JSON real para importar entidades del modelo de datos.',
          lambda args, actor: _result(args, actor, data_model.template)),
    _tool('preview_project_data_model', 'Valida y muestra las entidades actuales y propuestas sin guardar ni compartir cambios.',
          lambda args, actor: _call(data_model.preview, args['project_id'], actor, _data(args, MODEL), args['expected_version']),
          {'expected_version': RESOURCE_VERSION, **MODEL['properties']}, ('expected_version', 'entities')),
    _tool('import_project_data_model', 'Reemplaza el modelo de datos revisado tras confirmación, con versión vigente y reintento idempotente.',
          lambda args, actor: _result(args, actor, data_model.import_entities, _data(args, MODEL), **_operation(args)),
          {**WRITE, **MODEL['properties']}, ('entities', 'expected_version', 'request_id'), risk='sensitive'),
]


def _guard(tool):
    handler = tool['handler']

    def execute(arguments):
        _credential()
        validate_schema(arguments, tool['input_schema'])
        if tool.get('requires_confirmation') and not current_mcp_context().confirmation_bypass:
            raise ToolError('Confirma la operación pública antes de ejecutarla.', code='FORBIDDEN')
        return handler(arguments)

    tool['handler'] = execute
    if tool.get('requires_confirmation'):
        prepare = tool['prepare_arguments']
        tool['input_schema']['properties']['expected_client_id'] = {
            **ID, 'description': 'Propietario capturado por la vista previa; se revalida al confirmar.'}

        def prepare_arguments(arguments):
            _credential()
            validate_schema(arguments, tool['input_schema'])
            values = prepare(arguments)
            from content.mcp.actor import mcp_actor
            project = _call(project_for_actor, arguments['project_id'], mcp_actor())
            if values.get('expected_client_id', project.client_id) != project.client_id:
                raise ToolError('El destinatario cambió.', code='STALE_VERSION')
            values['expected_client_id'] = project.client_id
            return values

        tool['prepare_arguments'] = prepare_arguments
        original_etag = tool['etag_resolver']

        def etags(arguments):
            from content.mcp.actor import mcp_actor
            project = _call(project_for_actor, arguments['project_id'], mcp_actor())
            result = original_etag(arguments)
            result['recipient'] = hashlib.sha256(json.dumps(
                [project.client_id, project.client.email], sort_keys=True).encode()).hexdigest()
            if 'asset_id' in arguments:
                upload = _upload_or_error(arguments['asset_id'], lock=True)
                with upload.file.open('rb') as source:
                    digest = hashlib.sha256(source.read()).hexdigest()
                if digest != upload.expected_sha256:
                    raise ToolError('El archivo cambió desde su carga.', code='STALE_VERSION')
                result['asset'] = [str(upload.pk), digest, upload.received_size, upload.content_type]
            return result

        def impact(arguments):
            from content.mcp.actor import mcp_actor
            project = _call(project_for_actor, arguments['project_id'], mcp_actor())
            result = {'summary': tool['description'], 'operation': tool['name'],
                      'project_id': project.pk, 'recipient': {'user_id': project.client_id,
                      'name': project.client.get_full_name() or project.client.email},
                      'selection': deepcopy(arguments)}
            if 'asset_id' in arguments:
                upload = _upload_or_error(arguments['asset_id'], lock=True)
                result['file'] = {'filename': upload.filename, 'content_type': upload.content_type,
                                  'size': upload.received_size, 'sha256': upload.expected_sha256}
            return result

        tool['etag_resolver'] = etags
        tool['impact_builder'] = impact


for _resource_tool in PLATFORM_RESOURCE_TOOLS:
    _guard(_resource_tool)
