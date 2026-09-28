"""Dedicated connectors share the existing Panel operations and domain rules."""
from content.mcp.operation_catalogs import COMMERCIAL_PARITY_TOOLS, _op
from content.mcp.video_tools import video_tools

ADDITIONAL_MODULE_TOOLS = [
    tool for tool in COMMERCIAL_PARITY_TOOLS
    if 'additional_module' in tool['name']
] + video_tools('additional-modules')

PARTNERSHIP_PROGRAM_TOOLS = [
    tool for tool in COMMERCIAL_PARITY_TOOLS
    if tool['name'] in ('get_financing_program', 'render_financing_program_pdf')
] + [
    _op('get_partnership_settings', 'Consulta la política vigente, revisiones y condiciones del Programa de Alianza.', 'financing-settings'),
    _op('publish_partnership_policy', 'Publica una nueva revisión de política sin cambiar acuerdos históricos.', 'financing-settings', 'POST', risk='sensitive', confirm=True),
    _op('list_partnership_agreements', 'Lista acuerdos con búsqueda, filtros, paginación e historial de archivados.', 'financing-agreement-list'),
    _op('create_partnership_agreement', 'Crea un acuerdo borrador usando la política vigente.', 'financing-agreement-list', 'POST', risk='write'),
    _op('get_partnership_agreement', 'Consulta el acuerdo, su calendario, documentos e historial.', 'financing-agreement-detail', path=('agreement_id',)),
    _op('update_partnership_agreement', 'Edita un acuerdo borrador con las validaciones del Panel.', 'financing-agreement-detail', 'PATCH', ('agreement_id',), 'write'),
    _op('list_partnership_templates', 'Consulta las plantillas versionadas disponibles para acuerdos.', 'financing-agreement-templates'),
    _op('get_partnership_client_context', 'Consulta datos del cliente necesarios para preparar un acuerdo.', 'financing-client-context'),
    _op('render_partnership_agreement_pdf', 'Genera el borrador del acuerdo como PDF temporal descargable.', 'financing-agreement-draft-pdf', path=('agreement_id',)),
    _op('download_partnership_signed_pdf', 'Descarga el documento firmado del acuerdo como archivo temporal.', 'financing-agreement-signed-pdf', path=('agreement_id',)),
    _op('transition_partnership_agreement', 'Ejecuta mark-ready, reopen, complete, cancel, archive, restore, create-second-cycle o apply-current-policy; conserva las reglas e historial del Panel.', 'financing-agreement-action', 'POST', ('agreement_id', 'action'), 'sensitive', True),
    _op('upload_partnership_signed_pdf', 'Registra el PDF firmado mediante un asset_id previamente completado; usa action=upload-signed.', 'financing-agreement-action', 'POST', ('agreement_id', 'action'), 'sensitive', True, assets={'asset_id': {'field': 'signed_document', 'content_types': ['application/pdf']}}),
] + video_tools('financing')

for tool in PARTNERSHIP_PROGRAM_TOOLS:
    if tool['name'] == 'transition_partnership_agreement':
        tool['input_schema']['properties']['action'] = {'type': 'string', 'enum': [
            'mark-ready', 'reopen', 'complete', 'cancel', 'archive', 'restore',
            'create-second-cycle', 'apply-current-policy',
        ]}
    elif tool['name'] == 'upload_partnership_signed_pdf':
        tool['input_schema']['properties']['action'] = {'type': 'string', 'enum': ['upload-signed']}
        tool['input_schema']['required'].append('asset_id')
