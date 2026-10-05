"""Versioned default-contract operations with the server's durable confirmation."""
from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError
from content.services import contract_template_service as service
from content.services.contract_template_consistency import check_consistency
from content.services.contract_template_validation import ContractTemplateError

VARIANT = {'type': 'string', 'enum': ['combined', 'product', 'service']}
PATCH = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'operation': {'type': 'string', 'enum': ['replace', 'insert_before', 'insert_after']},
        'heading': {'type': 'string'}, 'clause_heading': {'type': 'string'},
        'text': {'type': 'string'}, 'markdown': {'type': 'string'},
    }, 'required': ['operation', 'markdown'],
    'oneOf': [{'required': ['heading'], 'not': {'required': ['text']}}, {'required': ['text'], 'not': {'required': ['heading']}}],
}
EDIT_FIELDS = {
    'variant': VARIANT, 'markdown': {'type': 'string', 'maxLength': 250000},
    'patches': {'type': 'array', 'minItems': 1, 'maxItems': 50, 'items': PATCH},
    'if_match': {'type': 'string', 'minLength': 1},
}


def _run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ContractTemplateError as exc:
        raise ToolError(str(exc), code=exc.code, details=exc.details) from exc


def _known(arguments, names):
    if not isinstance(arguments, dict) or set(arguments) - set(names):
        raise ToolError('Argumentos desconocidos.')
    return arguments


def _read(arguments):
    _known(arguments, ['variant', 'query'])
    query = arguments.get('query', {})
    _known(query, ['variant'])
    if 'variant' in arguments and 'variant' in query and arguments['variant'] != query['variant']:
        raise ToolError('variant y query.variant deben coincidir.')
    return _run(service.read_template, arguments.get('variant', query.get('variant', 'combined')))


def _versions(arguments):
    _known(arguments, ['variant', 'limit', 'offset'])
    return _run(service.list_versions, arguments.get('variant'), limit=arguments.get('limit', 20), offset=arguments.get('offset', 0))


def _preview(arguments):
    return _run(service.prepare_update, arguments)


def _prepare_sensitive(arguments, *, restore=False):
    prepared = _run(service.prepare_update, arguments, restore=restore, require_match=True)
    if not prepared['consistency']['consistent']:
        raise ToolError('Las variantes no son coherentes; revisa el preview.', code='TEMPLATES_INCONSISTENT', details=prepared['consistency'])
    frozen = dict(arguments)
    # Freeze the entire dependency set. The confirmation validates it again under lock.
    frozen['_expected_etags'] = prepared['resource_etags']
    return frozen


def _impact(arguments, *, restore=False):
    public = {key: value for key, value in arguments.items() if not key.startswith('_')}
    prepared = _run(service.prepare_update, public, restore=restore, require_match=True)
    return {'summary': 'Actualiza plantillas predeterminadas y sus espejos; no cambia contratos guardados en propuestas.', **prepared}


def _apply(arguments, *, restore=False):
    context = current_mcp_context()
    if context is None or not context.confirmation_bypass:
        raise ToolError('La operación requiere confirm_action.', code='CONFIRMATION_REQUIRED')
    arguments = dict(arguments)
    expected = arguments.pop('_expected_etags', None)
    if expected is None:
        raise ToolError('La confirmación no conserva la versión previsualizada.', code='STALE_VERSION')
    return _run(service.apply_update, arguments, actor=mcp_actor(), credential=context.credential,
                restore=restore, expected_etags=expected)


def _schema(*, sensitive=False, restore=False):
    sources = ['markdown', 'patches', 'version_id'] if restore else ['markdown', 'patches']
    fields = dict(EDIT_FIELDS)
    if restore:
        fields['version_id'] = {'type': 'integer', 'minimum': 1}
    related = {
        'type': 'object', 'additionalProperties': False, 'properties': fields,
        'required': ['variant', *(['if_match'] if sensitive else [])],
        'oneOf': [{'required': [source], 'not': {'anyOf': [{'required': [other]} for other in sources if other != source]}} for source in sources],
    }
    return {
        **related,
        'properties': {**fields, 'change_note': {'type': 'string', 'minLength': 1, 'maxLength': 4000},
            'related_updates': {'type': 'array', 'maxItems': 2, 'items': related}},
        'required': ['variant', *(['if_match', 'change_note'] if sensitive else []), *(['version_id'] if restore else [])],
    }


def _consistency(arguments):
    _known(arguments, [])
    return _run(check_consistency)


def _mirrors(arguments):
    _known(arguments, [])
    return _run(service.list_mirrors)


CONTRACT_TEMPLATE_TOOLS = [
    {'name': 'get_proposal_contract_template', 'risk': 'read',
     'description': 'Lee la plantilla predeterminada combined (default), product o service: markdown, placeholders, version, updated_at y etag. El gestor muestra su espejo de solo lectura.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {'variant': {**VARIANT, 'default': 'combined'}, 'query': {'type': 'object', 'additionalProperties': False, 'properties': {'variant': VARIANT}}}}, 'handler': _read},
    {'name': 'preview_proposal_contract_template_update', 'risk': 'read',
     'description': 'Valida markdown o patches literales, campos obligatorios y coherencia; devuelve diff y documentos afectados. related_updates permite coordinar variantes. No guarda cambios.',
     'input_schema': _schema(), 'handler': _preview},
    {'name': 'update_proposal_contract_template', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': 'Previsualiza una actualización con if_match y change_note. Sólo confirm_action guarda versiones, PDFs y notas en una transacción; un fallo revierte todo. related_updates permite un lote coherente. Sólo afecta contratos nuevos o regenerados.',
     'input_schema': _schema(sensitive=True), 'handler': _apply,
     'prepare_arguments': _prepare_sensitive, 'impact_builder': _impact, 'etag_resolver': service.resource_etags},
    {'name': 'list_proposal_contract_template_versions', 'risk': 'read',
     'description': 'Lista las versiones inmutables de una variante con autor, fecha, motivo y markdown; limit 1–50 y offset.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {'variant': VARIANT, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50}, 'offset': {'type': 'integer', 'minimum': 0}}, 'required': ['variant']}, 'handler': _versions},
    {'name': 'restore_proposal_contract_template_version', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': 'Previsualiza la restauración como nueva versión. Exige variant, version_id, if_match y change_note; confirm_action valida coherencia y sincroniza espejos atómicamente. related_updates puede restaurar las variantes dependientes.',
     'input_schema': _schema(sensitive=True, restore=True), 'handler': lambda args: _apply(args, restore=True),
     'prepare_arguments': lambda args: _prepare_sensitive(args, restore=True), 'impact_builder': lambda args: _impact(args, restore=True), 'etag_resolver': service.resource_etags},
    {'name': 'check_proposal_contract_templates_consistency', 'risk': 'read',
     'description': 'Compara cláusulas de producto y servicio con el combinado conservando cifras y obligaciones; ignora formato, numeración y referencias. Reporta cláusulas ausentes o diferentes y bloquea guardados incoherentes.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {}}, 'handler': _consistency},
]

CONTRACT_MIRROR_TOOLS = [
    {'name': 'list_contract_mirrors', 'risk': 'read',
     'description': 'Lista los tres espejos en Contratos, con document_id, variant, version, last_synced_at y synchronized. Son de solo lectura; las plantillas se editan desde el MCP de propuestas.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {}},
     'handler': _mirrors},
]

# Public output contracts are also returned by describe_capabilities.
READ_OUTPUT = {
    'type': 'object',
    'properties': {
        'variant': VARIANT, 'markdown': {'type': 'string'}, 'content_markdown': {'type': 'string'},
        'placeholders': {'type': 'array', 'items': {'type': 'string'}},
        'version': {'type': 'integer'}, 'version_id': {'type': ['integer', 'null']},
        'updated_at': {'type': 'string'}, 'etag': {'type': 'string'},
    },
    'required': ['variant', 'markdown', 'placeholders', 'version', 'updated_at', 'etag'],
}
CONTRACT_TEMPLATE_TOOLS[0]['output_schema'] = READ_OUTPUT
CONTRACT_MIRROR_TOOLS[0]['output_schema'] = {
    'type': 'object', 'required': ['mirrors'],
    'properties': {'mirrors': {'type': 'array', 'items': {
        'type': 'object', 'properties': {
            'variant': VARIANT, 'document_id': {'type': ['integer', 'null']},
            'title': {'type': 'string'}, 'folder_id': {'type': ['integer', 'null']},
            'version': {'type': ['integer', 'null']}, 'last_synced_at': {'type': ['string', 'null']},
            'synchronized': {'type': 'boolean'},
        }, 'required': ['variant', 'document_id', 'version', 'last_synced_at', 'synchronized'],
    }}},
}
