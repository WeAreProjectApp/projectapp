"""Proposal Panel operations shared by Proposals and Commercial."""
from content.mcp.operation_builder import _op as panel_op
from content.mcp.proposal_approval_tools import PROPOSAL_APPROVAL_TOOLS
from content.mcp.proposal_schemas import PAYLOAD_SCHEMAS, VARIANT, guarded_arguments


def _op(*args, **kwargs):
    schema = PAYLOAD_SCHEMAS.get(args[0])
    if args[0] in {'send_branded_email', 'send_custom_proposal_email'}:
        kwargs['assets'] = {'attachment_asset_ids': {'field': 'attachments', 'many': True}}
    tool = panel_op(*args, payload_schema=schema, **kwargs)
    if schema:
        tool['input_schema']['properties']['query'] = {'type': 'object', 'additionalProperties': True}
        handler = tool['handler']
        tool['handler'] = lambda arguments: handler(guarded_arguments(arguments, tool))
        if tool['requires_confirmation']:
            tool['prepare_arguments'] = lambda arguments: guarded_arguments(arguments, tool)
    return tool


PROPOSAL_PARITY_TOOLS = [
    # Proposal editing, analytics and delivery.
    _op('export_proposal_json', 'Obtiene el JSON completo editable de una propuesta.', 'export-proposal-json', path=('proposal_id',)),
    _op('update_proposal_from_json', 'Reemplaza el contenido editable usando el contrato JSON.', 'update-proposal-from-json', 'PUT', ('proposal_id',), 'write'),
    _op('preview_proposal_email', 'Previsualiza el correo inicial de la propuesta.', 'preview-proposal-email', 'POST', ('proposal_id',)),
    _op('toggle_proposal_active', 'Activa o pausa automatizaciones de la propuesta.', 'toggle-proposal-active', 'POST', ('proposal_id',), 'write'),
    _op('get_proposal_scorecard', 'Obtiene el scorecard comercial de una propuesta.', 'proposal-scorecard', path=('proposal_id',)),
    _op('get_proposal_analytics', 'Obtiene visitas e interacciones de una propuesta.', 'proposal-analytics', path=('proposal_id',)),
    _op('get_proposal_dashboard', 'Obtiene indicadores del módulo de propuestas.', 'proposal-dashboard'),
    _op('retry_proposal_first_view_notification', 'Reintenta la alerta fallida de primera vista.', 'retry-first-view-notification', 'POST', ('proposal_id',), 'sensitive', True),
    _op('create_proposal_section', 'Crea una sección en una propuesta.', 'create-proposal-section', 'POST', ('proposal_id',), 'write'),
    _op('update_proposal_section', 'Actualiza contenido y configuración de una sección.', 'update-proposal-section', 'PATCH', ('section_id',), 'write'),
    _op('delete_proposal_section', 'Elimina una sección de la propuesta.', 'delete-proposal-section', 'DELETE', ('section_id',), 'sensitive', True),
    _op('reorder_proposal_sections', 'Reordena todas las secciones de una propuesta.', 'reorder-sections', 'POST', ('proposal_id',), 'write'),
    _op('preview_proposal_section_sync', 'Previsualiza cambios de sincronización de una sección.', 'section-sync-preview', 'POST', ('section_id',)),
    _op('apply_proposal_section_sync', 'Aplica exactamente la sincronización previsualizada.', 'section-apply-sync', 'POST', ('section_id',), 'sensitive', True),
    _op('list_proposal_alerts', 'Lista alertas comerciales de propuestas.', 'proposal-alerts'),
    _op('create_proposal_alert', 'Crea una alerta comercial.', 'create-proposal-alert', 'POST', risk='write'),
    _op('dismiss_proposal_alert', 'Descarta una alerta comercial.', 'dismiss-proposal-alert', 'PATCH', ('alert_id',), 'write'),
    _op('log_proposal_activity', 'Registra una actividad atribuida en la propuesta.', 'log-activity', 'POST', ('proposal_id',), 'write'),
    _op('bulk_action_proposals', 'Aplica una acción masiva explícita sobre propuestas.', 'bulk-action', 'POST', risk='sensitive', confirm=True),
    _op('get_proposal_defaults', 'Obtiene contenido y ajustes predeterminados por idioma; usa lang=es o en y conserva updated_at para editar.', 'proposal-defaults'),
    _op('update_proposal_defaults', 'Actualiza el contenido base por idioma.', 'proposal-defaults', 'PUT', risk='write'),
    _op('reset_proposal_defaults', 'Restaura defaults de propuesta del sistema.', 'reset-proposal-defaults', 'POST', risk='sensitive', confirm=True),
    _op('list_email_templates', 'Lista templates administrables de correo.', 'email-template-list'),
    _op('get_email_template', 'Abre un template de correo.', 'email-template-detail', path=('template_key',)),
    _op('update_email_template', 'Actualiza un template de correo.', 'email-template-detail', 'PUT', ('template_key',), 'write'),
    _op('preview_email_template', 'Renderiza un template sin enviarlo.', 'email-template-preview', path=('template_key',)),
    _op('reset_email_template', 'Restaura un template de correo.', 'email-template-reset', 'POST', ('template_key',), 'sensitive', True),
    _op('get_email_deliverability', 'Obtiene salud y métricas de entregabilidad.', 'email-deliverability-dashboard'),
    _op('update_proposal_contract', 'Actualiza parámetros contractuales editables; variant (combined, product o service) indica el contrato que se genera o edita.', 'update-contract-params', 'PATCH', ('proposal_id',), 'write'),
    _op('update_proposal_contract_modality', 'Elige, sólo en negociación, si el negocio cierra con contrato único (single) o con contrato de producto y de servicio (split).', 'update-contract-modality', 'PATCH', ('proposal_id',), 'write'),
    _op('render_proposal_contract_pdf', 'Genera el contrato vigente como asset temporal; en cierre separado exige variant=product o variant=service.', 'download-contract-pdf', path=('proposal_id',)),
    _op('render_proposal_draft_contract_pdf', 'Genera el borrador contractual como asset temporal; en cierre separado exige variant=product o variant=service.', 'download-draft-contract-pdf', path=('proposal_id',)),
    _op('save_proposal_contract_negotiation', 'Guarda condiciones y pasa la propuesta a negociación.', 'save-contract-and-negotiate', 'POST', ('proposal_id',), 'sensitive', True),
    _op('list_proposal_documents', 'Lista documentos adjuntos a una propuesta.', 'list-proposal-documents', path=('proposal_id',)),
    _op('upload_proposal_document', 'Adjunta un asset validado a una propuesta.', 'upload-proposal-document', 'POST', ('proposal_id',), 'write', assets={
        'asset_id': {'field': 'file'},
    }),
    _op('delete_proposal_document', 'Elimina un adjunto de propuesta.', 'delete-proposal-document', 'DELETE', ('proposal_id', 'doc_id'), 'sensitive', True),
    _op('send_proposal_documents', 'Envía al cliente los documentos seleccionados.', 'send-documents-to-client', 'POST', ('proposal_id',), 'sensitive', True),
    _op('send_proposal_discount_offer', 'Envía una oferta manual de descuento.', 'send-discount-offer', 'POST', ('proposal_id',), 'sensitive', True),
    _op('get_branded_email_defaults', 'Obtiene defaults del correo de marca.', 'branded-email-defaults', path=('proposal_id',)),
    _op('list_branded_emails', 'Lista correos de marca enviados para la propuesta.', 'list-branded-emails', path=('proposal_id',)),
    _op('send_branded_email', 'Envía un correo de marca asociado a la propuesta con recipient_emails y cc_emails visibles (máximo 10 direcciones únicas).', 'send-branded-email', 'POST', ('proposal_id',), 'sensitive', True),
    _op('get_proposal_email_defaults', 'Obtiene defaults del compositor de propuesta.', 'proposal-email-defaults', path=('proposal_id',)),
    _op('list_proposal_emails', 'Lista correos manuales de la propuesta.', 'list-proposal-emails', path=('proposal_id',)),
    _op('send_custom_proposal_email', 'Envía un correo manual de propuesta con recipient_emails y cc_emails visibles (máximo 10 direcciones únicas).', 'send-proposal-email', 'POST', ('proposal_id',), 'sensitive', True),
    _op('update_proposal_stage', 'Actualiza una etapa del cronograma.', 'update-project-stage', 'PUT', ('proposal_id', 'stage_key'), 'write'),
    _op('complete_proposal_stage', 'Marca una etapa del cronograma como completada.', 'complete-project-stage', 'POST', ('proposal_id', 'stage_key'), 'write'),
]

PROPOSAL_PARITY_TOOLS += PROPOSAL_APPROVAL_TOOLS + [
    _op('update_proposal_settings', 'Edita parcialmente los ajustes del panel sin reenviar secciones; para cambiar estado usa update_proposal_status.', 'update-proposal', 'PATCH', ('proposal_id',), 'write'),
    _op('get_proposal_company_settings', 'Consulta los datos de empresa y opciones vigentes del contrato de servicio.', 'get-company-settings'),
    _op('update_proposal_service_settings', 'Actualiza las opciones numéricas y valores predeterminados del contrato de servicio.', 'get-company-settings', 'PATCH', risk='write'),
    _op('get_proposal_contract_template', 'Consulta el Markdown de la plantilla contractual predeterminada, de sólo lectura.', 'get-default-contract-template'),
    _op('read_proposal_contract_markdown', 'Lee el Markdown guardado del contrato; en modalidad split indica variant=product o service.', 'contract-markdown', path=('proposal_id',)),
    _op('read_proposal_document_markdown', 'Extrae el Markdown de un documento adjunto perteneciente a la propuesta.', 'proposal-attachment-markdown', path=('proposal_id', 'doc_id')),
    _op('download_proposal_document', 'Descarga un adjunto de la propuesta como archivo temporal de esta credencial.', 'proposal-attachment-download', path=('proposal_id', 'doc_id')),
    _op('export_proposal_analytics_csv', 'Exporta la analítica de la propuesta como archivo CSV temporal descargable.', 'proposal-analytics-csv', path=('proposal_id',)),
    _op('send_multi_proposal', 'Envía juntas las propuestas seleccionadas del mismo cliente, previa confirmación.', 'send-multi-proposal', 'POST', ('proposal_id',), 'sensitive', True),
    _op('render_proposal_email_markdown_pdf', 'Convierte Markdown en un PDF temporal para adjuntar al correo de la propuesta.', 'generate-email-markdown-attachment', 'POST', ('proposal_id',), 'read'),
]

for _tool in PROPOSAL_PARITY_TOOLS:
    if _tool['name'] in {'read_proposal_contract_markdown', 'render_proposal_contract_pdf', 'render_proposal_draft_contract_pdf'}:
        _tool['input_schema']['properties']['variant'] = VARIANT
        _tool['input_schema']['properties']['query']['properties'] = {'variant': VARIANT}

    if _tool['name'] == 'get_proposal_defaults':
        _tool['input_schema']['properties']['lang'] = {'type': 'string', 'enum': ['es', 'en']}
