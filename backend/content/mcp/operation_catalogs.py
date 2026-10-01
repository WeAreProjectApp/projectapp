"""MCP parity adapters for Panel operations not covered by domain-native tools.

Every adapter resolves the existing DRF FBV and therefore keeps its serializer,
service, permissions, transaction and audit behavior. Domain-native tools remain
the preferred rich interface; these close the operational gaps without forking
business logic.
"""
from content.mcp.document_tools import _FOLDER_FIELDS
from content.mcp.delivery_tools import DELIVERY_TOOLS
from content.mcp.platform_billing_tools import PLATFORM_BILLING_TOOLS
from content.mcp.operation_builder import _op
from content.mcp.proposal_operations import PROPOSAL_PARITY_TOOLS
from content.services.document_write_service import DOCUMENT_WRITE_SCHEMA

OPERATIONS_TOOLS = [
    _op(
        'get_operations_dashboard',
        'Obtiene el dashboard transversal del Panel con indicadores y alertas.',
        'panel-dashboard',
    ),
]


PROJECT_TOOLS = [
    _op('list_projects', 'Lista proyectos y sus indicadores por estado.', 'panel-projects-list'),
    _op('create_project', 'Crea un proyecto con las validaciones del Panel.', 'panel-projects-create', 'POST', risk='write'),
    _op('update_project', 'Actualiza nombre y metadatos editables de un proyecto.', 'panel-projects-update', 'PATCH', ('project_id',), 'write'),
    _op('list_project_unlinked_records', 'Previsualiza registros del cliente todavía sin proyecto.', 'panel-projects-unlinked-records', path=('project_id',)),
    _op('assign_project_unlinked_records', 'Asigna al proyecto el conjunto explícito de registros previsualizados.', 'panel-projects-assign-unlinked', 'POST', ('project_id',), 'sensitive', True),
    _op('preview_project_client_change', 'Calcula el impacto de cambiar el cliente propietario del proyecto.', 'panel-projects-change-client-preview', path=('project_id',)),
    _op('change_project_client', 'Cambia el cliente y aplica la cascada previamente revisada.', 'panel-projects-change-client', 'POST', ('project_id',), 'sensitive', True),
    _op('list_project_state_groups', 'Lista grupos del catálogo de estados de proyecto.', 'project-state-groups'),
    _op('create_project_state_group', 'Crea un grupo de estados de proyecto.', 'project-state-groups', 'POST', risk='write'),
    _op('list_project_states', 'Lista el catálogo de estados de proyecto.', 'project-states'),
    _op('create_project_state', 'Crea un estado en el catálogo de proyectos.', 'project-states', 'POST', risk='write'),
    _op('suggest_project_states', 'Busca estados de proyecto similares antes de crear.', 'project-state-suggestions'),
    _op('update_project_state', 'Actualiza nombre, descripción, color y orden de un estado.', 'update-project-state', 'PATCH', ('state_id',), 'write'),
    _op('retire_project_state', 'Retira un estado administrable del catálogo.', 'retire-project-state', 'POST', ('state_id',), 'sensitive', True),
    _op('merge_project_state', 'Fusiona un estado de proyecto dentro de otro.', 'merge-project-state', 'POST', ('state_id',), 'sensitive', True),
    _op('preview_project_state_transition', 'Calcula consecuencias financieras y operativas de una transición.', 'panel-project-state-transition-preview', 'POST', ('project_id',)),
    _op('apply_project_state_transition', 'Aplica una transición con el impact_token vigente.', 'panel-project-state-transition', 'POST', ('project_id',), 'sensitive', True),
    _op('list_project_state_history', 'Lista episodios y eventos de estado de un proyecto.', 'panel-project-state-history', path=('project_id',)),
] + DELIVERY_TOOLS + PLATFORM_BILLING_TOOLS


_FOLDER_SCHEMA = {'type': 'object', 'properties': _FOLDER_FIELDS, 'additionalProperties': False}
_MOVE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'document_ids': {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}, 'minItems': 1, 'maxItems': 100, 'uniqueItems': True},
        'folder_id': {'type': ['integer', 'null'], 'minimum': 1},
        'include_content': {'type': 'boolean', 'default': False},
    },
    'required': ['document_ids', 'folder_id'],
}

DOCUMENT_PARITY_TOOLS = [
    _op('move_documents', 'Mueve documentos activos de forma atómica: todos o ninguno, con resultado por ID.', 'move-documents', 'POST', risk='write', payload_schema=_MOVE_SCHEMA),
    _op('browse_documents', 'Busca, filtra, ordena y pagina todo el inventario documental.', 'browse-documents'),
    _op('get_document_counts', 'Obtiene conteos documentales para filtros y navegación.', 'document-counts'),
    _op('get_document_navigation', 'Obtiene raíces, clientes y proyectos navegables.', 'document-navigation'),
    _op('get_document_communication_usage', 'Lista comunicaciones que referencian el documento.', 'document-communication-usage', path=('document_id',)),
    _op('get_document_email_usage', 'Lista correos que utilizaron el documento.', 'document-email-usage', path=('document_id',)),
    _op('render_document_pdf', 'Genera el PDF vigente como asset temporal descargable.', 'download-document-pdf', path=('document_id',)),
    _op('duplicate_document', 'Duplica un documento Markdown como borrador independiente.', 'duplicate-document', 'POST', ('document_id',), 'write'),
    _op('archive_document', 'Archiva un documento individual de forma reversible.', 'archive-document', 'PATCH', ('document_id',), 'write'),
    _op('unarchive_document', 'Restaura un documento archivado individualmente.', 'unarchive-document', 'PATCH', ('document_id',), 'write'),
    _op('list_document_folders', 'Lista carpetas activas o archivadas con filtros del Panel.', 'list-document-folders'),
    _op('get_project_folder_readiness', 'Revisa la disponibilidad de raíces documentales de proyectos.', 'project-folder-readiness'),
    _op('update_folder', 'Actualiza nombre, padre y metadatos permitidos de una carpeta.', 'update-document-folder', 'PATCH', ('folder_id',), 'write', payload_schema=_FOLDER_SCHEMA),
    _op('delete_folder', 'Elimina una carpeta vacía que el sistema permita eliminar.', 'delete-document-folder', 'DELETE', ('folder_id',), 'sensitive', True),
    _op('archive_folder', 'Archiva una carpeta y la cascada informada por el Panel.', 'archive-document-folder', 'PATCH', ('folder_id',), 'sensitive', True),
    _op('unarchive_folder', 'Restaura una carpeta y los elementos archivados por ella.', 'unarchive-document-folder', 'PATCH', ('folder_id',), 'write'),
    _op('reorder_folders', 'Reordena carpetas hermanas con una lista explícita de ids.', 'reorder-document-folders', 'POST', risk='write'),
    _op('preview_folder_client_change', 'Calcula la cascada de cambiar el cliente de una carpeta.', 'preview-document-folder-client-change', path=('folder_id',)),
    _op('change_folder_client', 'Aplica el cambio de cliente de carpeta previamente revisado.', 'change-document-folder-client', 'POST', ('folder_id',), 'sensitive', True),
    _op('list_document_tags', 'Lista el catálogo de etiquetas documentales.', 'list-document-tags'),
    _op('create_document_tag', 'Crea una etiqueta documental.', 'create-document-tag', 'POST', risk='write'),
    _op('update_document_tag', 'Actualiza una etiqueta documental.', 'update-document-tag', 'PATCH', ('tag_id',), 'write'),
    _op('delete_document_tag', 'Elimina una etiqueta documental no protegida.', 'delete-document-tag', 'DELETE', ('tag_id',), 'sensitive', True),
    _op('list_document_state_groups', 'Lista grupos del workflow documental.', 'document-state-groups'),
    _op('create_document_state_group', 'Crea un grupo de workflow documental.', 'document-state-groups', 'POST', risk='write'),
    _op('update_document_state_group', 'Actualiza un grupo de workflow documental.', 'document-state-group-detail', 'PATCH', ('group_id',), 'write'),
    _op('list_document_state_catalog', 'Lista estados activos o retirados del catálogo documental.', 'document-states'),
    _op('create_document_state', 'Crea un estado documental administrable.', 'document-states', 'POST', risk='write'),
    _op('suggest_document_states', 'Busca estados documentales similares.', 'document-state-suggestions'),
    _op('update_document_state_catalog_item', 'Actualiza un estado documental.', 'update-document-state', 'PATCH', ('state_id',), 'write'),
    _op('retire_document_state', 'Retira un estado documental.', 'retire-document-state', 'POST', ('state_id',), 'sensitive', True),
    _op('merge_document_state', 'Fusiona un estado documental dentro de otro.', 'merge-document-state', 'POST', ('state_id',), 'sensitive', True),
    _op('correct_document_state_opening', 'Corrige de forma auditada la fecha de apertura de un episodio.', 'correct-document-state-opening', 'PATCH', ('document_id', 'episode_id'), 'write'),
    _op('list_document_state_history', 'Lista el histórico completo de estados del documento.', 'document-state-history', path=('document_id',)),
    _op('update_document_note', 'Edita el contenido de una observación activa.', 'update-document-note', 'PATCH', ('document_id', 'note_id'), 'write'),
    _op('list_document_note_events', 'Lista eventos atribuidos de observaciones.', 'document-note-events', path=('document_id',)),
]


COMMUNICATION_EMAIL_TOOLS = [
    _op('get_email_defaults', 'Obtiene saludo, firma y defaults del centro de correos.', 'standalone-email-defaults'),
    _op('update_email_defaults', 'Actualiza los defaults del centro de correos.', 'standalone-email-defaults', 'PUT', risk='write'),
    _op('list_email_history', 'Lista el historial global de correos con filtros y paginación.', 'list-standalone-emails'),
    _op('read_email_body', 'Abre el cuerpo conservado de un correo del historial.', 'standalone-email-body', path=('log_id',)),
    _op('download_email_attachment', 'Conserva un adjunto histórico como asset temporal.', 'standalone-email-attachment', path=('log_id', 'attachment_id')),
    _op('preview_email', 'Renderiza un correo y sus adjuntos sin enviarlo.', 'preview-composed-email', 'POST'),
    _op('send_email', 'Envía el correo previsualizado a recipient_emails y cc_emails (máximo 10 direcciones únicas) y registra una evidencia agrupada.', 'send-standalone-email', 'POST', risk='sensitive', confirm=True, assets={
        'attachment_asset_id': {'field': 'attachments'},
    }),
    _op('resend_email', 'Reenvía un correo histórico usando su snapshot; sólo permite cambiar recipient_emails y cc_emails, con máximo 10 direcciones únicas.', 'resend-standalone-email', 'POST', ('log_id',), 'sensitive', True),
    _op('list_email_copy_recipients', 'Lista destinatarios de copia por familia de correo.', 'client-email-copy-recipients'),
    _op('create_email_copy_recipient', 'Crea un destinatario de copia administrable.', 'client-email-copy-recipients', 'POST', risk='write'),
    _op('update_email_copy_recipient', 'Actualiza un destinatario de copia.', 'client-email-copy-recipient-detail', 'PATCH', ('recipient_id',), 'write'),
    _op('delete_email_copy_recipient', 'Elimina un destinatario de copia.', 'client-email-copy-recipient-detail', 'DELETE', ('recipient_id',), 'sensitive', True),
]


COMMERCIAL_PARITY_TOOLS = [
    # Client lifecycle and evidence.
    _op('get_client_status_counts', 'Obtiene conteos de clientes por estado.', 'proposal-client-status-counts'),
    _op('preview_client_archive', 'Calcula el impacto de archivar un cliente.', 'preview-client-archive', path=('client_id',)),
    _op('archive_client', 'Archiva el cliente y aplica la cascada confirmada.', 'archive-proposal-client', 'POST', ('client_id',), 'sensitive', True),
    _op('unarchive_client', 'Restaura un cliente archivado.', 'unarchive-proposal-client', 'POST', ('client_id',), 'write'),
    _op('list_client_emails', 'Lista el historial de correos de un cliente.', 'list-client-emails', path=('client_id',)),
    _op('read_client_email_body', 'Abre el cuerpo de un correo autorizado por cliente.', 'client-email-body', path=('client_id', 'log_id')),
    _op('retry_client_email', 'Reintenta un correo fallido del cliente.', 'retry-client-email', 'POST', ('client_id', 'log_id'), 'sensitive', True),
] + PROPOSAL_PARITY_TOOLS + [
    # Diagnostics administration.
    _op('bulk_action_diagnostics', 'Aplica una acción masiva a diagnósticos.', 'bulk-diagnostic-action', 'POST', risk='sensitive', confirm=True),
    _op('get_diagnostic_scorecard', 'Obtiene el scorecard del diagnóstico.', 'diagnostic-scorecard', path=('diagnostic_id',)),
    _op('list_diagnostic_activity', 'Lista actividad atribuida del diagnóstico.', 'list-diagnostic-activity', path=('diagnostic_id',)),
    _op('create_diagnostic_activity', 'Registra una actividad en el diagnóstico.', 'create-diagnostic-activity', 'POST', ('diagnostic_id',), 'write'),
    _op('get_diagnostic_analytics', 'Obtiene analítica del diagnóstico.', 'diagnostic-analytics', path=('diagnostic_id',)),
    _op('reset_diagnostic_section', 'Restaura una sección diagnóstica.', 'reset-diagnostic-section', 'POST', ('diagnostic_id', 'section_id'), 'sensitive', True),
    _op('list_diagnostic_attachments', 'Lista adjuntos del diagnóstico.', 'list-diagnostic-attachments', path=('diagnostic_id',)),
    _op('upload_diagnostic_attachment', 'Adjunta un asset validado al diagnóstico.', 'upload-diagnostic-attachment', 'POST', ('diagnostic_id',), 'write', assets={
        'asset_id': {'field': 'file'},
    }),
    _op('delete_diagnostic_attachment', 'Elimina un adjunto diagnóstico.', 'delete-diagnostic-attachment', 'DELETE', ('diagnostic_id', 'attachment_id'), 'sensitive', True),
    _op('send_diagnostic_attachments', 'Envía adjuntos del diagnóstico.', 'send-diagnostic-attachments', 'POST', ('diagnostic_id',), 'sensitive', True),
    _op('update_diagnostic_confidentiality', 'Actualiza parámetros de confidencialidad.', 'diagnostic-update-confidentiality-params', 'PATCH', ('diagnostic_id',), 'write'),
    _op('generate_diagnostic_confidentiality', 'Genera el documento de confidencialidad.', 'diagnostic-generate-confidentiality', 'POST', ('diagnostic_id',), 'write'),
    _op('render_diagnostic_confidentiality_pdf', 'Genera el acuerdo vigente como asset temporal.', 'diagnostic-download-confidentiality', path=('diagnostic_id',)),
    _op('render_diagnostic_draft_confidentiality_pdf', 'Genera el borrador de confidencialidad como asset temporal.', 'diagnostic-download-draft-confidentiality', path=('diagnostic_id',)),
    _op('get_diagnostic_email_defaults', 'Obtiene defaults del correo diagnóstico.', 'diagnostic-email-defaults', path=('diagnostic_id',)),
    _op('list_diagnostic_emails', 'Lista correos enviados para el diagnóstico.', 'list-diagnostic-emails', path=('diagnostic_id',)),
    _op('send_diagnostic_email', 'Envía un correo manual del diagnóstico con recipient_emails y cc_emails visibles (máximo 10 direcciones únicas).', 'send-diagnostic-email', 'POST', ('diagnostic_id',), 'sensitive', True),
    _op('get_diagnostic_defaults', 'Obtiene defaults de diagnósticos.', 'diagnostic-defaults'),
    _op('update_diagnostic_defaults', 'Actualiza defaults de diagnósticos.', 'diagnostic-defaults', 'PUT', risk='write'),
    _op('reset_diagnostic_defaults', 'Restaura defaults de diagnósticos.', 'reset-diagnostic-defaults', 'POST', risk='sensitive', confirm=True),
    # Additional modules, hour packages and financing.
    _op('get_additional_modules_catalog', 'Obtiene categorías, módulos y configuración comercial.', 'admin-additional-module-catalog'),
    _op('create_additional_module_category', 'Crea una categoría de módulos.', 'create-additional-module-category', 'POST', risk='write'),
    _op('update_additional_module_category', 'Actualiza una categoría de módulos.', 'update-additional-module-category', 'PATCH', ('category_id',), 'write'),
    _op('set_additional_module_category_status', 'Activa, archiva o restaura una categoría.', 'set-additional-module-category-status', 'POST', ('category_id', 'action'), 'write'),
    _op('create_additional_module', 'Crea un módulo adicional bilingüe.', 'create-additional-module', 'POST', risk='write'),
    _op('update_additional_module', 'Actualiza un módulo adicional.', 'update-additional-module', 'PATCH', ('module_id',), 'write'),
    _op('set_additional_module_status', 'Activa, archiva o restaura un módulo.', 'set-additional-module-status', 'POST', ('module_id', 'action'), 'write'),
    _op('reorder_additional_modules', 'Reordena categorías y módulos.', 'reorder-additional-module-catalog', 'POST', risk='write'),
    _op('list_additional_module_shares', 'Lista enlaces compartidos del catálogo.', 'admin-additional-module-shares'),
    _op('create_additional_module_share', 'Crea un enlace compartido del catálogo.', 'admin-additional-module-shares', 'POST', risk='write'),
    _op('set_additional_module_share_status', 'Activa, archiva o restaura un enlace compartido.', 'set-additional-module-share-status', 'POST', ('share_uuid', 'action'), 'write'),
    _op('update_additional_module_share', 'Muestra u oculta el video explicativo en un enlace compartido del catálogo (show_explainer_video).', 'update-additional-module-share', 'PATCH', ('share_uuid',), 'write'),
    _op('get_explainer_video_settings', 'Obtiene si el catálogo y el Programa de Alianza muestran su video explicativo a los clientes.', 'explainer-video-settings'),
    _op('update_explainer_video_settings', 'Muestra u oculta el video explicativo del catálogo o del Programa de Alianza en la vista pública.', 'update-explainer-video-settings', 'PATCH', risk='write'),
    _op('render_additional_modules_pdf', 'Genera el catálogo de módulos como asset temporal.', 'admin-additional-module-catalog-pdf', 'POST'),
    _op('list_hour_packages', 'Lista paquetes de horas y sus precios.', 'list-admin-hour-packages'),
    _op('get_hour_package', 'Abre un paquete de horas.', 'retrieve-admin-hour-package', path=('package_id',)),
    _op('create_hour_package', 'Crea un paquete de horas.', 'create-hour-package', 'POST', risk='write'),
    _op('update_hour_package', 'Actualiza un paquete de horas.', 'update-hour-package', 'PATCH', ('package_id',), 'write'),
    _op('delete_hour_package', 'Elimina un paquete de horas permitido.', 'delete-hour-package', 'DELETE', ('package_id',), 'sensitive', True),
    _op('get_hour_package_settings', 'Obtiene ajustes de paquetes de horas.', 'hour-package-settings'),
    _op('update_hour_package_settings', 'Actualiza ajustes de paquetes de horas.', 'update-hour-package-settings', 'PATCH', risk='write'),
    _op('restore_default_hour_packages', 'Restaura el catálogo inicial de paquetes.', 'restore-default-hour-packages', 'POST', risk='sensitive', confirm=True),
    _op('get_financing_program', 'Obtiene el Programa de Alianza: financiación, custodia, paquete mensual y exclusividad conceptual de Project App. sólo en la modalidad de cinco años.', 'public-financing-program'),
    _op('render_financing_program_pdf', 'Genera el PDF del Programa de Alianza como asset temporal.', 'public-financing-program-pdf'),
]


CONTENT_PARITY_TOOLS = [
    _op('duplicate_blog_post', 'Duplica un blog post como borrador.', 'duplicate-blog-post', 'POST', ('post_id',), 'write'),
    _op('publish_blog_to_linkedin', 'Publica el resumen del blog en LinkedIn.', 'publish-to-linkedin', 'POST', ('post_id',), 'sensitive', True),
    _op('upload_blog_cover', 'Asigna un asset de portada al blog.', 'upload-blog-cover-image', 'POST', ('post_id',), 'write', assets={
        'asset_id': {'field': 'cover_image'},
    }),
    _op('list_portfolio_works', 'Lista trabajos administrables de portafolio.', 'list-admin-portfolio-works'),
    _op('get_portfolio_work', 'Abre el contenido editable de un trabajo.', 'retrieve-admin-portfolio-work', path=('work_id',)),
    _op('get_portfolio_template', 'Obtiene el template JSON de portafolio.', 'portfolio-json-template'),
    _op('create_portfolio_work', 'Crea un trabajo de portafolio.', 'create-portfolio-work', 'POST', risk='write'),
    _op('create_portfolio_from_json', 'Crea un trabajo desde el contrato JSON.', 'create-portfolio-work-from-json', 'POST', risk='write'),
    _op('update_portfolio_work', 'Actualiza un trabajo de portafolio.', 'update-portfolio-work', 'PATCH', ('work_id',), 'write'),
    _op('duplicate_portfolio_work', 'Duplica un trabajo como borrador.', 'duplicate-portfolio-work', 'POST', ('work_id',), 'write'),
    _op('delete_portfolio_work', 'Elimina un trabajo permitido.', 'delete-portfolio-work', 'DELETE', ('work_id',), 'sensitive', True),
    _op('upload_portfolio_cover', 'Asigna un asset de portada al trabajo.', 'upload-portfolio-cover-image', 'POST', ('work_id',), 'write', assets={
        'asset_id': {'field': 'cover_image'},
    }),
    _op('list_qr_cards', 'Lista tarjetas QR.', 'list-admin-qr-cards'),
    _op('create_qr_card', 'Crea una tarjeta QR.', 'create-qr-card', 'POST', risk='write'),
    _op('update_qr_card', 'Actualiza una tarjeta QR.', 'update-qr-card', 'PATCH', ('card_id',), 'write'),
    _op('delete_qr_card', 'Elimina una tarjeta QR.', 'delete-qr-card', 'DELETE', ('card_id',), 'sensitive', True),
    _op('list_linktrees', 'Lista Linktrees administrables.', 'list-admin-linktrees'),
    _op('get_linktree', 'Abre un Linktree completo.', 'retrieve-admin-linktree', path=('linktree_id',)),
    _op('create_linktree', 'Crea un Linktree y sus botones; project permite asociarlo a un proyecto.', 'create-linktree', 'POST', risk='write'),
    _op('update_linktree', 'Actualiza un Linktree y sus botones; project asigna un proyecto y null lo desvincula.', 'update-linktree', 'PATCH', ('linktree_id',), 'write'),
    _op('delete_linktree', 'Elimina un Linktree.', 'delete-linktree', 'DELETE', ('linktree_id',), 'sensitive', True),
    _op('upload_linktree_logo', 'Asigna un logo JPG, PNG o WebP (máximo 5 MB) al Linktree.', 'upload-linktree-logo', 'POST', ('linktree_id',), 'write', assets={'asset_id': {'field': 'logo'}}),
    _op('remove_linktree_logo', 'Elimina el logo personalizado del Linktree.', 'upload-linktree-logo', 'DELETE', ('linktree_id',), 'write'),
    _op('upload_linktree_avatar', 'Asigna un asset de avatar al Linktree.', 'upload-linktree-avatar', 'POST', ('linktree_id',), 'write', assets={
        'asset_id': {'field': 'avatar'},
    }),
]


LEDGER_PARITY_TOOLS = [
    _op('get_accounting_stats', 'Obtiene indicadores contables del año.', 'accounting-stats'),
    _op('duplicate_income_draft', 'Obtiene un borrador duplicado de un ingreso.', 'duplicate-income-draft', path=('record_id',)),
    _op('suggest_income_period', 'Sugiere el siguiente período para un ingreso.', 'suggest-income-period'),
    _op('bulk_assign_income_client', 'Asigna cliente a una selección de ingresos.', 'bulk-assign-income-client', 'POST', risk='sensitive', confirm=True),
    _op('bulk_assign_income_project', 'Asigna proyecto a una selección de ingresos.', 'bulk-assign-income-project', 'POST', risk='sensitive', confirm=True),
    _op('reorder_recurring_payments', 'Reordena pagos recurrentes.', 'reorder-recurring-payments', 'POST', risk='write'),
    _op('list_recurring_categories', 'Lista categorías de pagos recurrentes.', 'list-recurring-categories'),
    _op('create_recurring_category', 'Crea una categoría recurrente.', 'create-recurring-category', 'POST', risk='write'),
    _op('update_recurring_category', 'Actualiza una categoría recurrente.', 'update-recurring-category', 'PATCH', ('category_id',), 'write'),
    _op('delete_recurring_category', 'Elimina una categoría recurrente permitida.', 'delete-recurring-category', 'DELETE', ('category_id',), 'sensitive', True),
    _op('reorder_recurring_categories', 'Reordena categorías recurrentes.', 'reorder-recurring-categories', 'POST', risk='write'),
    _op('list_accounting_change_logs', 'Lista la auditoría contable.', 'list-accounting-change-logs'),
    _op('get_accounting_history_counts', 'Obtiene conteos de tabs del historial contable.', 'accounting-history-tab-counts', 'POST'),
    _op('export_accounting_records', 'Genera una exportación filtrada como asset temporal.', 'export-accounting-records'),
    _op('export_accounting_workbook', 'Genera el workbook contable como asset temporal.', 'export-accounting-workbook'),
]


BILLING_PARITY_TOOLS = [
    _op('send_hosting_collection_account', 'Emite el cobro del hosting con su contexto explícito y conserva el PDF.', 'send-hosting-collection-account', 'POST', ('record_id',), 'sensitive', True, payload_schema={'type': 'object', 'additionalProperties': False, 'properties': {'hosting_payment_id': {'type': ['integer', 'null'], 'minimum': 1}}}),
    _op('bulk_assign_hosting_client', 'Asigna cliente a una selección de hostings.', 'bulk-assign-hosting-client', 'POST', risk='sensitive', confirm=True),
    _op('bulk_assign_hosting_project', 'Asigna proyecto a una selección de hostings.', 'bulk-assign-hosting-project', 'POST', risk='sensitive', confirm=True),
    _op('list_hosting_cycles', 'Lista ciclos facturados de un hosting.', 'list-hosting-cycles', path=('record_id',)),
    _op('create_hosting_cycle', 'Registra un ciclo de hosting.', 'create-hosting-cycle', 'POST', ('record_id',), 'sensitive', True),
    _op('delete_hosting_cycle', 'Elimina un ciclo de hosting permitido.', 'delete-hosting-cycle', 'DELETE', ('record_id', 'cycle_id'), 'sensitive', True),
    _op('list_collection_accounts', 'Lista cuentas de cobro con filtros del Panel.', 'list-collection-accounts'),
    _op('get_collection_account', 'Abre una cuenta de cobro con su snapshot.', 'retrieve-collection-account', path=('doc_id',)),
    _op('download_collection_account_pdf', 'Conserva el PDF inmutable como asset temporal.', 'collection-account-pdf', path=('doc_id',)),
    _op('get_collection_account_next_number', 'Obtiene el siguiente consecutivo disponible.', 'collection-account-next-number'),
    _op('preview_collection_account', 'Valida y previsualiza una cuenta sin emitirla.', 'preview-collection-account', 'POST'),
    _op('create_collection_account', 'Emite una cuenta de cobro y conserva su PDF inmutable.', 'create-collection-account', 'POST', risk='sensitive', confirm=True),
    _op('resend_collection_account', 'Reenvía una cuenta emitida usando el snapshot.', 'resend-collection-account', 'POST', ('doc_id',), 'sensitive', True),
    _op('mark_collection_account_paid', 'Marca una cuenta emitida como pagada.', 'mark-collection-account-paid', 'POST', ('doc_id',), 'sensitive', True),
    _op('cancel_collection_account', 'Anula una cuenta de cobro.', 'cancel-collection-account', 'POST', ('doc_id',), 'sensitive', True),
    _op('delete_collection_account_draft', 'Elimina una cuenta que aún sea borrador.', 'delete-collection-account', 'DELETE', ('doc_id',), 'sensitive', True),
    _op('list_accounting_email_logs', 'Lista correos contables y sus resultados.', 'list-accounting-email-log'),
    _op('read_accounting_email_body', 'Abre el cuerpo de un correo contable.', 'accounting-email-log-body', path=('log_id',)),
    _op('retry_accounting_email', 'Reintenta un correo contable fallido.', 'retry-accounting-email-log', 'POST', ('log_id',), 'sensitive', True),
    _op('get_accounting_settings_full', 'Obtiene configuración de recordatorios y agrupación.', 'get-accounting-settings'),
    _op('update_accounting_settings_full', 'Actualiza configuración contable.', 'update-accounting-settings', 'PATCH', risk='write'),
]


CARD_PARITY_TOOLS = [
    _op('list_credit_cards', 'Lista el catálogo de tarjetas de crédito.', 'list-credit-cards'),
    _op('get_credit_card', 'Abre una tarjeta de crédito.', 'retrieve-credit-card', path=('record_id',)),
    _op('create_credit_card', 'Crea una tarjeta sin almacenar credenciales bancarias.', 'create-credit-card', 'POST', risk='write'),
    _op('update_credit_card', 'Actualiza metadatos y cupo de una tarjeta.', 'update-credit-card', 'PATCH', ('record_id',), 'write'),
    _op('delete_credit_card', 'Elimina una tarjeta permitida.', 'delete-credit-card', 'DELETE', ('record_id',), 'sensitive', True),
    _op('create_statement_transaction_batch', 'Crea un lote de transacciones del extracto.', 'batch-create-statement-transactions', 'POST', ('record_id',), 'write'),
    _op('delete_statement_transaction', 'Elimina una transacción de un extracto abierto.', 'delete-statement-transaction', 'DELETE', ('record_id', 'tx_id'), 'sensitive', True),
    _op('upload_statement_pdf', 'Adjunta un PDF validado al extracto.', 'upload-statement-pdf', 'POST', ('record_id',), 'write', assets={
        'asset_id': {'field': 'file', 'content_types': ['application/pdf']},
    }),
    _op('delete_statement_pdf', 'Elimina el PDF adjunto de un extracto abierto.', 'delete-statement-pdf', 'DELETE', ('record_id',), 'sensitive', True),
    _op('create_merchant_alias', 'Crea un alias de comercio.', 'create-merchant-alias', 'POST', risk='write'),
    _op('learn_merchant_alias', 'Aprende un alias desde una transacción revisada.', 'learn-merchant-alias', 'POST', risk='write'),
    _op('resolve_merchant_aliases', 'Resuelve descriptores contra el catálogo de alias.', 'resolve-merchant-aliases', 'POST'),
]


for _tool in DOCUMENT_PARITY_TOOLS:
    if _tool['name'] == 'move_documents':
        _tool['input_schema'] = _MOVE_SCHEMA
        _tool['output_schema'] = {
            'type': 'object',
            'properties': {
                'ok': {'type': 'boolean'},
                'results': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'status': {'type': 'string', 'enum': ['moved', 'unchanged', 'failed', 'aborted']},
                        'moved': {'type': 'boolean'},
                        'reason': {'type': ['string', 'object']},
                        'code': {'type': 'string'},
                        'message': {'type': 'string'},
                        'move_blockers': {'type': 'array', 'items': {'type': 'string'}},
                        'document': DOCUMENT_WRITE_SCHEMA,
                    },
                    'required': ['id', 'status', 'moved'],
                }},
            },
            'required': ['ok', 'results'],
        }
        _tool['annotations'] = {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}
    if _tool['name'] in ('duplicate_document', 'archive_document', 'unarchive_document'):
        _tool['output_schema'] = DOCUMENT_WRITE_SCHEMA
        _tool['input_schema']['properties']['include_content'] = {'type': 'boolean', 'default': False}
        _tool['description'] += ' Resumen por defecto; include_content=true añade markdown.'
