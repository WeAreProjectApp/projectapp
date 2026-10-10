import json
import re
from copy import deepcopy
from urllib.parse import urlencode

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
        if key.endswith(('_id', '_ids')) or key in {'action', 'mode'}
    }
    return {
        'summary': operation['confirmation_message'],
        'operation': operation['name'],
        'resources': identifiers,
    }


def _path_properties(path_params, *, explicit=False):
    properties = {}
    for name in path_params:
        if name.endswith('_id'):
            properties[name] = (
                {'type': 'integer', 'minimum': 1}
                if explicit else {'type': ['integer', 'string']}
            )
        else:
            properties[name] = {'type': 'string'}
    return properties


def _validation_error(errors, *, message=None):
    if message is not None:
        errors = {**errors, 'detail': message}
    detail, code, fields = normalize_error(errors)
    raise ToolError(detail, code=code, details=fields)


def _field_error(field, message, *, code='invalid'):
    _validation_error({field: [serializers.ErrorDetail(message, code=code)]}, message=message)


def _check_unknown_fields(values, properties):
    unknown = set(values) - set(properties)
    if unknown:
        _validation_error({
            name: [serializers.ErrorDetail('Campo desconocido o de solo lectura.', code='unknown_field')]
            for name in sorted(unknown)
        })


def _merge_alias(values, arguments, alias):
    conflicts = sorted(key for key in arguments if key in values and arguments[key] != values[key])
    if conflicts:
        message = f'Campos contradictorios entre {alias} y argumentos.'
        _validation_error({
            name: [serializers.ErrorDetail(message, code='invalid')]
            for name in conflicts
        }, message=message)
    values.update(arguments)


def _allows_null(schema):
    field_type = schema.get('type', ())
    return (
        field_type == 'null'
        or isinstance(field_type, list) and 'null' in field_type
        or schema.get('nullable') is True
        or any(_allows_null(option) for key in ('anyOf', 'oneOf') for option in schema.get(key, []))
    )


def encode_query_value(value, *, encoding='csv', field='query'):
    """Encode JSON query values consistently for GET and body-bearing requests."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float, str)):
        return str(value)
    if isinstance(value, list):
        if any(isinstance(item, (dict, list)) for item in value):
            _field_error(field, 'La lista de consulta debe contener valores simples.')
        items = [encode_query_value(item, field=field) for item in value if item is not None]
        if encoding == 'repeat':
            return items
        if encoding == 'csv':
            return ','.join(items)
        _field_error(field, 'La codificación de consulta no es válida.')
    _field_error(field, 'El valor de consulta debe ser un valor simple o una lista.')


def _encode_query(query, schema):
    properties = schema.get('properties', {}) if schema is not None else {}
    default_encoding = 'repeat' if schema is None else 'csv'
    encoded = {}
    for name, value in query.items():
        field_schema = properties.get(name, {})
        if value is None and name in properties and not _allows_null(field_schema):
            _field_error(name, 'Este campo no puede ser nulo.', code='null')
        item = encode_query_value(value, encoding=field_schema.get('x-query-encoding', default_encoding), field=name)
        if item is not None:
            encoded[name] = item
    return encoded


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
    if query:
        url = f'{url}?{urlencode(query, doseq=True)}'
    # Multipart cannot encode nested objects; the Panel parsers accept JSON strings.
    encoded = {key: json.dumps(value) if isinstance(value, (dict, list)) else value
               for key, value in data.items()} if files else data
    payload = {**encoded, **files}
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
    payload_schema = operation.get('payload_schema')
    query_schema = operation.get('query_schema')
    explicit = payload_schema is not None or query_schema is not None
    is_get = operation['method'] == 'GET'
    if explicit:
        permitted = (set(operation['path_params']) | set(operation['asset_fields'])
                     | {'if_match'})
        if not is_get and payload_schema is not None:
            permitted.add('data')
        if payload_schema is not None:
            permitted.update(payload_schema.get('properties', {}))
        if query_schema is not None:
            permitted.update(query_schema.get('properties', {}))
            permitted.add('query')
        if operation.get('envelope_aliases', True):
            permitted.update({'data', 'query'})
        _check_unknown_fields(args, permitted)
    route_kwargs = {}
    for name in operation['path_params']:
        value = args.pop(name, None)
        if value in (None, ''):
            _field_error(name, f'{name} es obligatorio.', code='required')
        if explicit and name.endswith('_id'):
            if isinstance(value, str) and re.fullmatch(r'[0-9]+', value):
                try:
                    value = int(value)
                except ValueError:
                    _field_error(name, f'{name} debe ser un identificador positivo.')
            if type(value) is not int or value < 1:
                _field_error(name, f'{name} debe ser un identificador positivo.')
        route_kwargs[name] = value
    query = args.pop('query', {})
    data = args.pop('data', {})
    query = {} if query is None and query_schema is None else query
    data = {} if data is None else data
    if not isinstance(query, dict):
        _field_error('query', 'query y data deben ser objetos JSON.')
    if not isinstance(data, dict):
        _field_error('data', 'query y data deben ser objetos JSON.')
    if query_schema is not None:
        query_fields = query_schema.get('properties', {})
        _check_unknown_fields(query, query_fields)
        declared = {name: args.pop(name) for name in query_fields if name in args}
        _merge_alias(query, declared, 'query')
        missing = [name for name in query_schema.get('required', []) if name not in query]
        if missing:
            _validation_error({
                name: [serializers.ErrorDetail(f'{name} es obligatorio.', code='required')]
                for name in missing
            }, message=f'{missing[0]} es obligatorio.' if len(missing) == 1 else None)
    if_match = args.pop('if_match', '') or ''
    files = {}
    uploads = []
    for argument_name, config in operation['asset_fields'].items():
        asset_id = args.pop(argument_name, None)
        if not asset_id:
            continue
        asset_ids = asset_id if config.get('many') else [asset_id]
        if not isinstance(asset_ids, list) or not asset_ids or any(not isinstance(item, str) for item in asset_ids):
            _field_error(argument_name, f'{argument_name} debe contener identificadores de archivo.')
        if len(set(asset_ids)) != len(asset_ids):
            _field_error(argument_name, 'No repitas archivos adjuntos.', code='duplicate')
        attachments = []
        for selected_asset_id in asset_ids:
            upload = consume_upload(
                selected_asset_id,
                allowed_content_types=set(config.get('content_types') or []),
            )
            with upload.file.open('rb') as source:
                attachments.append(SimpleUploadedFile(
                    upload.filename, source.read(), content_type=upload.content_type,
                ))
            uploads.append(upload)
        files[config['field']] = attachments if config.get('many') else attachments[0]
    if is_get:
        query.update(args)
    else:
        if payload_schema is not None:
            _check_unknown_fields(data, payload_schema.get('properties', {}))
            _merge_alias(data, args, 'data')
        else:
            data.update(args)
    query = _encode_query(query, query_schema)
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
    query_schema=None,
    envelope_aliases=True,
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
        'query_schema': query_schema,
        'envelope_aliases': envelope_aliases,
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
    explicit = payload_schema is not None or query_schema is not None
    if explicit and (not envelope_aliases or query_schema is not None):
        properties = {
            **(payload_schema.get('properties', {}) if payload_schema is not None else {}),
            **(query_schema.get('properties', {}) if query_schema is not None else {}),
            **_path_properties(path_params, explicit=True),
            'if_match': properties['if_match'],
        }
    elif payload_schema is not None:
        # Keep existing published envelopes for connectors that retain aliases.
        properties = {**_path_properties(path_params), **payload_schema['properties'],
                      'data': payload_schema, 'if_match': properties['if_match']}
    for argument_name, config in operation['asset_fields'].items():
        asset_schema = {'type': 'string', 'format': 'uuid'}
        properties[argument_name] = (
            {'type': 'array', 'items': asset_schema, 'minItems': 1, 'uniqueItems': True}
            if config.get('many') else asset_schema
        )
    tool = {
        'name': name,
        'description': description,
        'risk': risk,
        'requires_confirmation': requires_confirmation,
        'confirmation_message': operation['confirmation_message'],
        'input_schema': {
            'type': 'object',
            'properties': properties,
            'required': (list(path_params) if envelope_aliases and query_schema is None else
                         list(dict.fromkeys([
                             *path_params,
                             *(payload_schema.get('required', []) if payload_schema is not None else []),
                             *(query_schema.get('required', []) if query_schema is not None else []),
                         ]))),
            'additionalProperties': not explicit,
        },
        'handler': lambda arguments: _execute(operation, arguments),
        '_panel_operation': operation,
    }
    if explicit:
        accepted_properties = deepcopy(properties)
        if operation['method'] != 'GET' and payload_schema is not None:
            accepted_properties['data'] = deepcopy(payload_schema)
        if query_schema is not None:
            accepted_properties['query'] = deepcopy(query_schema)
        tool['accepted_arguments_schema'] = {
            'type': 'object',
            'properties': accepted_properties,
            'required': list(dict.fromkeys(path_params)),
            'additionalProperties': False,
        }
    if requires_confirmation:
        tool['impact_builder'] = lambda arguments: _impact_for(operation, arguments)
    return tool
