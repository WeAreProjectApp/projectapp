"""Administrative delivery tools over the same services as Platform.

The connector never acts as the client. Contract attestations and historical
approvals explicitly record external evidence; ordinary client decisions stay
on the authenticated client API. Sensitive writes use the existing owned MCP
confirmation, including a workspace-version check at confirmation time.
"""
from copy import deepcopy

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from accounts.services import delivery_authoring as authoring
from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_access import is_admin
from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.errors import normalize_error
from content.mcp.protocol import ToolError
from content.mcp.upload_tools import consume_upload, store_artifact
from content.models import McpUpload


ID = {'type': 'integer', 'minimum': 1}
NULLABLE_ID = {'type': ['integer', 'null'], 'minimum': 1}
TEXT = {'type': 'string'}
CONTEXT_ID = {'type': 'string', 'format': 'uuid', 'minLength': 1}
CITATION_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'source_key': {**TEXT, 'minLength': 1, 'maxLength': 100},
        'locator': {**TEXT, 'minLength': 1, 'maxLength': 1000},
        'quote': {**TEXT, 'minLength': 1, 'maxLength': 20000},
    },
    'required': ['source_key', 'locator', 'quote'],
}
SOURCE_REFERENCES = {'type': 'array', 'items': CITATION_SCHEMA, 'maxItems': 100}
CLASSIFICATIONS = {
    'type': 'array', 'minItems': 1, 'maxItems': 100,
    'items': {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            'request': {**TEXT, 'minLength': 1, 'maxLength': 5000},
            'classification': {'type': 'string', 'enum': [
                'inside_scope', 'outside_scope', 'indeterminate',
            ]},
            'rationale': {**TEXT, 'minLength': 1, 'maxLength': 10000},
            'citations': SOURCE_REFERENCES,
        },
        'required': ['request', 'classification', 'rationale'],
    },
}
VERSION = {
    'type': 'integer', 'minimum': 0,
    'description': 'Versión del espacio obtenida con get_delivery_overview.',
}
REQUEST_ID = {
    'type': 'string', 'minLength': 1,
    'description': 'Identificador estable de la operación; reutilizarlo al reintentar.',
}
LEVELS = ('project', 'contract', 'amendment', 'scope', 'phase', 'stage', 'requirement')
NODE_NAMES = {
    'contracts': 'contract', 'amendments': 'amendment', 'scopes': 'scope',
    'phases': 'phase', 'stages': 'stage', 'requirements': 'requirement',
}
GUIDE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        **{name: TEXT for name in (
            'role', 'environment', 'preparation', 'data', 'expected_result',
            'failure_signals',
        )},
        'steps': {'type': 'array', 'items': TEXT},
    },
}
COMMON_FIELDS = {'key': TEXT, 'title': TEXT}
NODE_FIELDS = {
    'contracts': {
        **COMMON_FIELDS, 'document_id': NULLABLE_ID,
        'proposal_document_id': NULLABLE_ID, 'client_visible': {'type': 'boolean'},
    },
    'amendments': {
        **COMMON_FIELDS, 'contract_id': ID, 'document_id': NULLABLE_ID,
        'proposal_document_id': NULLABLE_ID, 'client_visible': {'type': 'boolean'},
    },
    'scopes': {
        **COMMON_FIELDS, 'description': TEXT, 'contract_id': ID,
        'amendment_id': NULLABLE_ID, 'is_current': {'type': 'boolean'},
    },
    'phases': {
        **COMMON_FIELDS, 'description': TEXT, 'scope_id': ID,
        'commercial_phase_id': NULLABLE_ID, 'order': {'type': 'integer', 'minimum': 0},
    },
    'stages': {
        **COMMON_FIELDS, 'description': TEXT, 'phase_id': ID,
        'order': {'type': 'integer', 'minimum': 0},
    },
    'requirements': {
        **COMMON_FIELDS, 'description': TEXT, 'stage_id': ID,
        'guide': GUIDE_SCHEMA, 'order': {'type': 'integer', 'minimum': 0},
        'context_id': {**CONTEXT_ID, 'type': ['string', 'null']},
        'source_references': SOURCE_REFERENCES,
    },
}


def _actor():
    actor = mcp_actor()
    if not is_admin(actor):
        raise ToolError('Solo los administradores pueden gestionar entregas.', code='FORBIDDEN')
    return actor


def _call(function, *args, **kwargs):
    try:
        return _public_result(function(*args, **kwargs))
    except APIException as exc:
        message, code, details = normalize_error(exc.detail, exc.status_code)
        raise ToolError(message, code=code, details=details) from exc


def _public_result(value):
    """Keep internal portal-signature network evidence off the MCP surface."""
    if isinstance(value, dict):
        result = {name: _public_result(item) for name, item in value.items()}
        for evidence in result.get('signature_evidence', []):
            evidence.pop('source_snapshot', None)
        return result
    if isinstance(value, list):
        return [_public_result(item) for item in value]
    return value


def _validate(arguments, schema):
    """Check the transport envelope; domain payload validation stays shared."""
    unknown = set(arguments) - set(schema['properties'])
    if unknown:
        raise ToolError('Argumentos desconocidos.', details={'fields': sorted(unknown)})
    missing = [name for name in schema.get('required', ()) if name not in arguments]
    if missing:
        raise ToolError('Faltan argumentos obligatorios.', details={'fields': missing})
    for name, value in arguments.items():
        field = schema['properties'][name]
        field_type = field.get('type')
        if field_type == 'object' and not isinstance(value, dict):
            raise ToolError(f'{name} debe ser un objeto JSON.')
        if field_type == 'array' and not isinstance(value, list):
            raise ToolError(f'{name} debe ser una lista JSON.')
        if field_type == 'boolean' and not isinstance(value, bool):
            raise ToolError(f'{name} debe ser verdadero o falso.')
        if field_type == 'integer' and (
            isinstance(value, bool) or not isinstance(value, int)
            or value < field.get('minimum', 0)
        ):
            raise ToolError(f'{name} debe ser un entero válido.')
        if field_type == 'string' and (
            not isinstance(value, str) or len(value) < field.get('minLength', 0)
        ):
            raise ToolError(f'{name} debe ser un texto válido.')
        if 'enum' in field and value not in field['enum']:
            raise ToolError(f'{name} no es una opción válida.')


def _overview(arguments, actor):
    return _call(delivery.overview, arguments['project_id'], actor)


def _nodes(value, kind):
    """Traverse only the delivery hierarchy returned by the shared service."""
    for name in NODE_NAMES:
        for row in value.get(name, []):
            if name == kind:
                yield row
            yield from _nodes(row, kind)


def _read_node(arguments, actor, kind):
    for node in _nodes(_overview(arguments, actor), kind):
        if node['id'] == arguments['node_id']:
            return {'node': node}
    raise ToolError('El elemento no pertenece a este proyecto.', code='NOT_FOUND')


def _mutate_node(arguments, actor, kind, *, delete=False):
    data = deepcopy(arguments.get('data', {}))
    data['expected_version'] = arguments['expected_version']
    if 'request_id' in arguments:
        data['request_id'] = arguments['request_id']
    return _call(
        delivery.mutate_node, arguments['project_id'], actor, kind, data,
        node_id=arguments.get('node_id'), delete=delete,
    )


def _import(arguments, actor, *, apply):
    return _call(
        delivery.import_payload, arguments['project_id'], actor,
        arguments['payload'], arguments['expected_version'], apply=apply,
        request_id=arguments.get('request_id'),
    )


def _create_prompt(arguments, actor, mode):
    data = {name: deepcopy(value) for name, value in arguments.items()
            if name != 'project_id'}
    data['mode'] = mode
    return _call(authoring.create_prompt_context, arguments['project_id'], actor, data)


def _prompt_source(arguments, actor):
    body, filename, content_type = _call(
        authoring.prompt_source_file, arguments['project_id'], actor,
        arguments['context_id'], arguments['source_key'],
    )
    return _artifact(body, filename, filename, content_type=content_type)


def _publish(arguments, actor):
    return _call(delivery.publish_stage, arguments['project_id'], actor,
                 arguments['stage_id'], _lifecycle_data(arguments))


def _lifecycle_data(arguments):
    return {name: deepcopy(value) for name, value in arguments.items()
            if name not in {'project_id', 'stage_id', 'asset_id', 'kind', 'node_id'}}


def _historical_approval(arguments, actor):
    return _call(
        delivery.review_stage, arguments['project_id'], actor,
        arguments['stage_id'], _lifecycle_data(arguments), historical=True,
    )


def _message(arguments, actor):
    return _call(delivery.add_message, arguments['project_id'], actor,
                 _lifecycle_data(arguments))


def _link(arguments, actor):
    return _call(delivery.link_document, arguments['project_id'], actor,
                 _lifecycle_data(arguments))


def _unlink(arguments, actor):
    data = {'expected_version': arguments['expected_version']}
    if 'request_id' in arguments:
        data['request_id'] = arguments['request_id']
    return _call(delivery.unlink_document, arguments['project_id'], actor,
                 arguments['link_id'], data)


def _documents(arguments, actor):
    if 'target_id' in arguments and 'level' not in arguments:
        raise ToolError('Indica level junto con target_id.')
    return _call(delivery.list_documents, arguments['project_id'], actor,
                 level=arguments.get('level'), target_id=arguments.get('target_id'))


def _read_document(arguments, actor):
    for document in _documents({'project_id': arguments['project_id']}, actor)['documents']:
        if document['id'] == arguments['link_id']:
            return {'document': document}
    raise ToolError('Documento no disponible en este proyecto.', code='NOT_FOUND')


def _artifact(body, title, filename, *, content_type='application/pdf'):
    context = current_mcp_context()
    if context is None or context.credential is None:
        raise ToolError('La descarga requiere una credencial MCP.', code='FORBIDDEN')
    return {
        'title': title,
        **store_artifact(
            connector=context.connector, credential=context.credential,
            filename=filename, content_type=content_type, content=body,
            request=context.request,
        ),
    }


def _document_pdf(arguments, actor):
    linked = 'link_id' in arguments
    evidence = 'review_id' in arguments or 'evidence_id' in arguments
    if linked and not evidence:
        body, title = _call(delivery.document_pdf, arguments['project_id'], actor,
                            arguments['link_id'])
        filename = f'entrega-{arguments["link_id"]}.pdf'
    elif not linked and 'review_id' in arguments and 'evidence_id' in arguments:
        from accounts.services.delivery_review_evidence import review_evidence_pdf
        body, title = _call(review_evidence_pdf, arguments['project_id'], actor,
                            arguments['review_id'], arguments['evidence_id'])
        filename = f'revision-{arguments["review_id"]}-evidencia-{arguments["evidence_id"]}.pdf'
    else:
        raise ToolError('Indica solo link_id, o review_id y evidence_id juntos.')
    return _artifact(body, title, filename)


def _contract_pdf(arguments, actor):
    body, title = _call(delivery.contract_pdf, arguments['project_id'], actor,
                        arguments['kind'], arguments['node_id'])
    return _artifact(body, title, f'contrato-{arguments["node_id"]}.pdf')


def _attest(arguments, actor):
    upload = consume_upload(arguments['asset_id'], allowed_content_types={'application/pdf'})
    if upload.received_size > 10 * 1024 * 1024:
        raise ToolError('El PDF firmado no puede superar 10 MB.')
    with upload.file.open('rb') as source:
        body = source.read(10 * 1024 * 1024 + 1)
    file = SimpleUploadedFile(upload.filename, body, content_type='application/pdf')
    result = _call(
        delivery.attest_signature, arguments['project_id'], actor,
        arguments['kind'], arguments['node_id'], _lifecycle_data(arguments), file,
    )
    upload.status = McpUpload.STATUS_CONSUMED
    upload.consumed_at = timezone.now()
    upload.save(update_fields=['status', 'consumed_at', 'updated_at'])
    return result


def _workspace_etag(arguments):
    result = _overview(arguments, _actor())
    return {f'project:{arguments["project_id"]}:delivery': str(result['version'])}


def _tool(name, description, handler, properties=None, required=(), *, risk='read', one_of=None):
    schema = {
        'type': 'object', 'additionalProperties': False,
        'properties': {'project_id': ID, **(properties or {})},
        'required': ['project_id', *required],
    }
    if one_of is not None:
        schema['oneOf'] = one_of

    def execute(arguments):
        _validate(arguments, schema)
        actor = _actor()
        with transaction.atomic():
            return handler(arguments, actor)

    tool = {
        'name': name, 'description': description, 'risk': risk,
        'input_schema': schema, 'handler': execute,
    }
    if risk == 'sensitive':
        def prepare(arguments):
            _validate(arguments, schema)
            _overview(arguments, _actor())
            return deepcopy(arguments)

        tool.update({
            'requires_confirmation': True,
            'prepare_arguments': prepare,
            'etag_resolver': _workspace_etag,
            'impact_builder': lambda arguments: {
                'summary': description, 'operation': name,
                'project_id': arguments['project_id'],
                'expected_version': arguments['expected_version'],
                **{key: arguments[key] for key in ('node_id', 'stage_id', 'link_id', 'kind')
                   if key in arguments},
            },
        })
    return tool


def _node_tools(kind, singular):
    data_schema = {'type': 'object', 'properties': NODE_FIELDS[kind], 'additionalProperties': False}
    # Binding kind in the closure prevents generated tools from sharing the
    # final loop value and exposing a different entity than their schema.
    return [
        _tool(
            f'get_delivery_{singular}',
            f'Consulta {singular} y su evidencia dentro del proyecto autorizado de Platform.',
            lambda args, actor: _read_node(args, actor, kind),
            {'node_id': ID}, ('node_id',),
        ),
        _tool(
            f'create_delivery_{singular}',
            f'Crea {singular} en borrador con las reglas contractuales vigentes de Platform.',
            lambda args, actor: _mutate_node(args, actor, kind),
            {'expected_version': VERSION, 'request_id': REQUEST_ID, 'data': data_schema}, ('expected_version', 'data'),
            risk='write',
        ),
        _tool(
            f'update_delivery_{singular}',
            f'Edita {singular} sin modificar evidencia aprobada ni omitir las reglas de Platform.',
            lambda args, actor: _mutate_node(args, actor, kind),
            {'node_id': ID, 'expected_version': VERSION, 'request_id': REQUEST_ID, 'data': data_schema},
            ('node_id', 'expected_version', 'data'), risk='write',
        ),
        _tool(
            f'delete_delivery_{singular}',
            f'Elimina {singular} permitido por Platform tras confirmación; conserva evidencia aprobada.',
            lambda args, actor: _mutate_node(args, actor, kind, delete=True),
            {'node_id': ID, 'expected_version': VERSION, 'request_id': REQUEST_ID}, ('node_id', 'expected_version'),
            risk='sensitive',
        ),
    ]


DECISION_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'requirement_id': ID, 'version': {'type': 'integer', 'minimum': 1},
        'decision': {'type': 'string', 'enum': ['approved']},
        'message': TEXT, 'environment': TEXT,
    },
    'required': ['requirement_id', 'version', 'decision'],
}
CONTRACT_KIND = {'type': 'string', 'enum': ['contracts', 'amendments']}
DOCUMENT_IDS = {'type': 'array', 'items': ID, 'uniqueItems': True}
PROMPT_SELECTION = {
    'expected_version': VERSION, 'request_id': REQUEST_ID,
    'contract_id': ID, 'amendment_ids': {**DOCUMENT_IDS, 'maxItems': 30},
    'scope_id': NULLABLE_ID,
    'sources': {
        'type': 'array', 'maxItems': 30,
        'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'document_id': ID, 'proposal_document_id': ID,
                'role': {'type': 'string', 'enum': ['contractual_annex', 'reference']},
                'applicability_note': {**TEXT, 'minLength': 1, 'maxLength': 5000},
            },
            'required': ['role', 'applicability_note'],
            'oneOf': [
                {'required': ['document_id'], 'not': {'required': ['proposal_document_id']}},
                {'required': ['proposal_document_id'], 'not': {'required': ['document_id']}},
            ],
        },
    },
    'missing_sources': {'type': 'array', 'maxItems': 30,
                        'items': {**TEXT, 'maxLength': 1000}},
    'uncertainties': {'type': 'array', 'maxItems': 30,
                      'items': {**TEXT, 'maxLength': 2000}},
    'instructions': {**TEXT, 'maxLength': 10000},
}
REPLY_PAYLOAD = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'schema_version': {'type': 'integer', 'const': 2}, 'context_id': CONTEXT_ID,
        'response_text': {**TEXT, 'minLength': 1, 'maxLength': 20000},
        'classifications': CLASSIFICATIONS,
    },
    'required': ['schema_version', 'context_id', 'response_text', 'classifications'],
}
DELIVERY_TOOLS = [
    _tool('get_delivery_overview',
          'Consulta contratos, otrosíes, alcances, fases, etapas, guías y versiones de Platform.',
          _overview),
    _tool('get_delivery_authoring_contract',
          'Consulta opciones y esquemas de autoría sin leer textos ni seleccionar automáticamente un contrato.',
          lambda args, actor: _call(authoring.prompt_options, args['project_id'], actor)),
    _tool('create_delivery_guide_prompt',
          'Captura las fuentes elegidas y prepara un prompt con JSON v2 citado para guías; conserva copias privadas e inmutables.',
          lambda args, actor: _create_prompt(args, actor, 'guides'),
          PROMPT_SELECTION, ('expected_version', 'request_id', 'contract_id'), risk='write'),
    _tool('create_delivery_reply_prompt',
          'Prepara un borrador de respuesta para una etapa publicada con fuentes seleccionadas y conversación pública capturada.',
          lambda args, actor: _create_prompt(args, actor, 'reply'),
          {**PROMPT_SELECTION, 'stage_id': ID},
          ('expected_version', 'request_id', 'stage_id'), risk='write'),
    _tool('list_delivery_prompt_contexts',
          'Lista hasta cincuenta capturas de autoría del proyecto con su selección y estado, sin cargar textos de fuentes.',
          lambda args, actor: _call(authoring.list_prompt_contexts, args['project_id'], actor)),
    _tool('get_delivery_prompt_context',
          'Reabre una captura inmutable con prompt, plantilla, esquema, citas y fuentes elegidas para el proyecto autorizado.',
          lambda args, actor: _call(authoring.get_prompt_context, args['project_id'], actor,
                                   args['context_id']),
          {'context_id': CONTEXT_ID}, ('context_id',)),
    _tool('download_delivery_prompt_source',
          'Descarga la copia exacta capturada de una fuente como artefacto privado temporal ligado a la credencial MCP.',
          _prompt_source, {'context_id': CONTEXT_ID, 'source_key': {**TEXT, 'minLength': 1}},
          ('context_id', 'source_key')),
    _tool('preview_delivery_reply',
          'Valida JSON v2, citas y clasificación contractual sin compartir mensajes; exige aclaración si las fuentes están incompletas.',
          lambda args, actor: _call(authoring.preview_reply, args['project_id'], actor,
                                   args['payload'], expected_version=args.get('expected_version')),
          {'payload': REPLY_PAYLOAD, 'expected_version': VERSION}, ('payload',)),
    *[tool for kind, singular in NODE_NAMES.items() for tool in _node_tools(kind, singular)],
    _tool('preview_delivery_import',
          'Valida JSON v1 manual o v2 con contexto y citas; previsualiza borradores sin guardar ni omitir su trazabilidad.',
          lambda args, actor: _import(args, actor, apply=False),
          {'payload': {'type': 'object'}, 'expected_version': VERSION},
          ('payload', 'expected_version')),
    _tool('apply_delivery_import',
          'Aplica el JSON previsualizado sobre borradores de Platform tras confirmación; no declara firmas ni aprobaciones.',
          lambda args, actor: _import(args, actor, apply=True),
          {'payload': {'type': 'object'}, 'expected_version': VERSION, 'request_id': REQUEST_ID},
          ('payload', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('publish_delivery_stage',
          'Publica o republica los pendientes de una etapa firmada tras confirmación; conserva las conformidades previas.',
          _publish, {'stage_id': ID, 'expected_version': VERSION, 'request_id': REQUEST_ID},
          ('stage_id', 'expected_version', 'request_id'), risk='sensitive'),
    _tool('record_external_delivery_approval',
          'Registra una aprobación histórica explícita del cliente con evidencia entrante tras confirmación; no suplanta su revisión.',
          _historical_approval, {
              'stage_id': ID, 'expected_version': VERSION, 'request_id': REQUEST_ID,
              'decisions': {'type': 'array', 'items': DECISION_SCHEMA, 'minItems': 1},
              'evidence_message': TEXT, 'evidence_document_ids': DOCUMENT_IDS,
              'message': TEXT, 'document_ids': DOCUMENT_IDS,
              'client_statement': {'type': 'boolean', 'enum': [True]},
              'source_message_id': {**ID, 'description': 'Mensaje entrante recibido del mismo cliente/proyecto; la cita debe pertenecer a su contenido.'},
              'original_reviewer': TEXT,
              'occurred_at': {'type': 'string', 'format': 'date-time'},
              'evidence_channel': {'type': 'string', 'enum': ['email', 'whatsapp', 'document']},
              'external_reference': {**TEXT, 'description': 'Referencia externa explícita; sin source_message_id también se requieren revisor, fecha, canal y documento de evidencia.'},
          }, ('stage_id', 'expected_version', 'request_id', 'decisions',
              'evidence_message', 'client_statement'), risk='sensitive'),
    _tool('list_delivery_approval_evidence',
          'Consulta mensajes entrantes recibidos del cliente y proyecto para citar una aprobación externa verificable.',
          lambda args, actor: _call(delivery.evidence_options, args['project_id'], actor)),
    _tool('add_delivery_message',
          'Comparte manualmente un mensaje en Platform; un borrador citado exige contexto, clasificaciones y revisión humana explícita.',
          _message, {
              'expected_version': VERSION, 'request_id': REQUEST_ID,
              'level': {'type': 'string', 'enum': list(LEVELS)}, 'target_id': ID,
              'requirement_ids': DOCUMENT_IDS, 'message': TEXT,
              'document_ids': DOCUMENT_IDS, 'is_internal': {'type': 'boolean', 'default': False},
              'context_id': CONTEXT_ID, 'source_references': SOURCE_REFERENCES,
              'classifications': CLASSIFICATIONS, 'human_reviewed': {'type': 'boolean'},
          }, ('expected_version', 'request_id', 'level', 'target_id', 'message'), risk='write'),
    _tool('list_delivery_document_options',
          'Lista documentos del proyecto autorizados para vincular a contratos, alcances, etapas o requerimientos.',
          lambda args, actor: _call(delivery.document_options, args['project_id'], actor)),
    _tool('list_delivery_documents',
          'Lista documentos asociados a un nivel de entrega con las mismas reglas de publicación y propiedad de Platform.',
          _documents, {'level': {'type': 'string', 'enum': list(LEVELS)}, 'target_id': ID}),
    _tool('get_delivery_document',
          'Consulta la referencia y evidencia de un documento de entrega autorizado en el proyecto indicado.',
          _read_document, {'link_id': ID}, ('link_id',)),
    _tool('link_delivery_document',
          'Asocia un documento del mismo cliente y proyecto al nivel autorizado; su visibilidad hereda la publicación de Platform.',
          _link, {'expected_version': VERSION, 'request_id': REQUEST_ID,
                  'level': {'type': 'string', 'enum': list(LEVELS)},
                  'target_id': ID, 'document_id': ID},
          ('expected_version', 'level', 'target_id', 'document_id'), risk='write'),
    _tool('unlink_delivery_document',
          'Retira una asociación documental editable sin cambiar evidencia publicada o aprobada de Platform.',
          _unlink, {'expected_version': VERSION, 'request_id': REQUEST_ID, 'link_id': ID},
          ('expected_version', 'link_id'), risk='write'),
    _tool('download_delivery_document_pdf',
          'Obtiene un PDF documental o el respaldo congelado de una revisión como artefacto temporal ligado a la credencial MCP.',
          _document_pdf, {'link_id': ID, 'review_id': ID, 'evidence_id': ID}, one_of=[
              {'required': ['link_id'], 'not': {'anyOf': [
                  {'required': ['review_id']}, {'required': ['evidence_id']},
              ]}},
              {'required': ['review_id', 'evidence_id'], 'not': {'required': ['link_id']}},
          ]),
    _tool('download_delivery_contract_pdf',
          'Obtiene el contrato u otrosí consultable antes de publicar etapas; devuelve un PDF temporal autorizado.',
          _contract_pdf, {'kind': CONTRACT_KIND, 'node_id': ID}, ('kind', 'node_id')),
    _tool('attest_external_delivery_signature',
          'Constata la firma externa de contrato u otrosí con PDF, firmante, fecha y declaración administrativa tras confirmación.',
          _attest, {
              'kind': CONTRACT_KIND, 'node_id': ID, 'expected_version': VERSION,
              'request_id': REQUEST_ID,
              'asset_id': {'type': 'string', 'format': 'uuid',
                           'description': 'PDF completo de begin_upload/upload_asset_chunk/complete_upload; máximo 10 MB.'},
              'signer_name': TEXT, 'signed_at': {'type': 'string', 'format': 'date-time'},
              'attestation': TEXT,
          }, ('kind', 'node_id', 'expected_version', 'request_id', 'asset_id',
              'signer_name', 'signed_at', 'attestation'), risk='sensitive'),
]
