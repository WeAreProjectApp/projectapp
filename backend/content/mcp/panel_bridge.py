import json
import re
from copy import deepcopy

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.http import HttpResponseBase, StreamingHttpResponse
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.errors import normalize_error
from content.mcp.protocol import ToolError
from content.mcp.upload_tools import consume_upload, store_artifact
from content.models import McpUpload

factory = APIRequestFactory()


def _json_safe(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _error_message(payload, status_code):
    return normalize_error(payload, status_code)


def _response_filename(response, fallback):
    disposition = response.headers.get('Content-Disposition', '')
    match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)', disposition)
    return match.group(1) if match else fallback


def _artifact_payload(response, operation):
    context = current_mcp_context()
    if context is None or context.credential is None:
        raise ToolError('No existe contexto para conservar el artefacto.', code='FORBIDDEN')
    if isinstance(response, StreamingHttpResponse):
        content = b''.join(response.streaming_content)
    else:
        content = response.content
    content_type = response.headers.get('Content-Type', 'application/octet-stream')
    extension = {
        'application/pdf': 'pdf',
        'text/csv': 'csv',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    }.get(content_type.split(';', 1)[0], 'bin')
    filename = _response_filename(response, f'{operation["name"]}.{extension}')
    try:
        return store_artifact(
            connector=context.connector,
            credential=context.credential,
            filename=filename,
            content_type=content_type,
            content=content,
            request=context.request,
        )
    finally:
        response.close()


def _impact_for(operation, arguments):
    identifiers = {
        key: value for key, value in arguments.items()
        if key.endswith('_id') or key.endswith('_ids') or key in {'action', 'mode'}
    }
    return {
        'summary': operation['confirmation_message'],
        'operation': operation['name'],
        'resources': identifiers,
    }


def _path_properties(path_params):
    properties = {}
    for name in path_params:
        if name.endswith('_id'):
            properties[name] = {'type': ['integer', 'string']}
        else:
            properties[name] = {'type': 'string'}
    return properties


def _request_for(method, url, *, query, data, files, if_match):
    headers = {'HTTP_IF_MATCH': if_match} if if_match else {}
    context = current_mcp_context()
    source_request = context.request if context is not None else None
    if source_request is not None:
        headers['HTTP_HOST'] = source_request.get_host()
    secure = bool(source_request and source_request.is_secure())
    method = method.lower()
    if method == 'get':
        return factory.get(url, data=query, secure=secure, **headers)
    payload = {**data, **files}
    request_factory = getattr(factory, method)
    return request_factory(
        url,
        data=payload,
        format='multipart' if files else 'json',
        secure=secure,
        **headers,
    )


@transaction.atomic
def _execute(operation, arguments):
    args = deepcopy(arguments)
    if operation.get('payload_schema'):
        permitted = set(operation['path_params']) | {'data', 'if_match'} | set(operation['payload_schema']['properties'])
        unexpected = set(args) - permitted
        if unexpected:
            message, code, details = normalize_error({name: [serializers.ErrorDetail('Campo desconocido o de solo lectura.', code='unknown_field')] for name in sorted(unexpected)})
            raise ToolError(message, code=code, details=details)
    route_kwargs = {}
    for name in operation['path_params']:
        value = args.pop(name, None)
        if value in (None, ''):
            raise ToolError(f'{name} es obligatorio.')
        route_kwargs[name] = value
    query = args.pop('query', {})
    data = args.pop('data', {})
    query = {} if query is None else query
    data = {} if data is None else data
    if not isinstance(query, dict) or not isinstance(data, dict):
        raise ToolError('query y data deben ser objetos JSON.')
    if_match = args.pop('if_match', '') or ''
    files = {}
    uploads = []
    for argument_name, config in operation['asset_fields'].items():
        asset_id = args.pop(argument_name, None)
        if not asset_id:
            continue
        upload = consume_upload(
            asset_id,
            allowed_content_types=set(config.get('content_types') or []),
        )
        with upload.file.open('rb') as source:
            files[config['field']] = SimpleUploadedFile(
                upload.filename,
                source.read(),
                content_type=upload.content_type,
            )
        uploads.append(upload)
    if operation['method'] == 'GET':
        query.update(args)
    else:
        if operation.get('payload_schema'):
            conflicts = [key for key in args if key in data and args[key] != data[key]]
            if conflicts:
                raise ToolError('Campos contradictorios entre data y argumentos.', details={'fields': conflicts})
        data.update(args)
    url = reverse(operation['route_name'], kwargs=route_kwargs)
    request = _request_for(
        operation['method'],
        url,
        query=query,
        data=data,
        files=files,
        if_match=if_match,
    )
    force_authenticate(request, user=mcp_actor())
    match = resolve(url)
    response = match.func(request, *match.args, **match.kwargs)
    if not isinstance(response, Response):
        if isinstance(response, HttpResponseBase) and response.status_code < 400:
            return _artifact_payload(response, operation)
        raise ToolError('La operación devolvió una respuesta no compatible.')
    if response.status_code >= 400:
        message, code, details = _error_message(response.data, response.status_code)
        raise ToolError(message, code=code, details=details)
    payload = _json_safe(response.data)
    for upload in uploads:
        upload.status = McpUpload.STATUS_CONSUMED
        upload.consumed_at = upload.consumed_at or timezone.now()
        upload.save(update_fields=['status', 'consumed_at', 'updated_at'])
    return payload


def panel_operation(
    name,
    description,
    route_name,
    *,
    method='GET',
    path_params=(),
    risk='read',
    requires_confirmation=False,
    confirmation_message='',
    asset_fields=None,
    payload_schema=None,
):
    if len(description.strip()) < 40:
        description = (
            f'{description.rstrip(".")} usando las validaciones vigentes del Panel.'
        )
    operation = {
        'name': name,
        'route_name': route_name,
        'method': method.upper(),
        'path_params': tuple(path_params),
        'risk': risk,
        'requires_confirmation': requires_confirmation,
        'confirmation_message': confirmation_message or description,
        'asset_fields': asset_fields or {},
        'payload_schema': payload_schema,
    }
    properties = {
        **_path_properties(path_params),
        'query': {
            'type': 'object',
            'description': 'Parámetros de consulta del endpoint del Panel.',
            'additionalProperties': True,
        },
        'data': {
            'type': 'object',
            'description': 'Payload validado por el serializer del Panel.',
            'additionalProperties': True,
        },
        'if_match': {
            'type': 'string',
            'description': 'ETag leído previamente, cuando el recurso lo ofrece.',
        },
    }
    if payload_schema:
        properties = {**_path_properties(path_params), **payload_schema['properties'],
                      'data': payload_schema, 'if_match': properties['if_match']}
    for argument_name in operation['asset_fields']:
        properties[argument_name] = {'type': 'string', 'format': 'uuid'}
    tool = {
        'name': name,
        'description': description,
        'risk': risk,
        'requires_confirmation': requires_confirmation,
        'confirmation_message': operation['confirmation_message'],
        'input_schema': {
            'type': 'object',
            'properties': properties,
            'required': list(path_params),
            'additionalProperties': not bool(payload_schema),
        },
        'handler': lambda arguments: _execute(operation, arguments),
        '_panel_operation': operation,
    }
    if requires_confirmation:
        tool['impact_builder'] = lambda arguments: _impact_for(operation, arguments)
    return tool
