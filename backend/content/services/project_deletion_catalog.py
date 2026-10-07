"""Explicit user-facing categories; unknown models never authorize deletion."""
from content.services.project_deletion_service import DEPENDENCY_LABELS


# Model, Spanish label, English label. Keys already published by the panel
# stay stable; formerly unclassified rows keep their existing model-label key.
_LABELS = '''
accounts.projectadminaccess|Accesos administrativos|Administrative access
accounts.projectaccessnote|Notas del proyecto|Project notes
accounts.projectphase|Fases comerciales|Commercial phases
accounts.deliveryworkspace|Organización de las entregas|Delivery workspace
accounts.projectcontract|Contratos del proyecto|Project contracts
accounts.contractamendment|Otrosíes de contratos|Contract amendments
accounts.contractsignatureevidence|Firmas de contratos|Contract signatures
accounts.deliveryscope|Alcances de entrega|Delivery scopes
accounts.deliveryphase|Fases de entrega|Delivery phases
accounts.deliverystage|Etapas de entrega|Delivery stages
accounts.requirement|Requerimientos|Requirements
accounts.deliverypublication|Entregas publicadas|Published deliveries
accounts.requirementreview|Revisiones de requerimientos|Requirement reviews
accounts.deliverydocumentsnapshot|Copias de documentos de entrega|Delivery document copies
accounts.deliveryreviewdocumentevidence|Documentos de revisión|Review documents
accounts.deliverydocumentlink|Vínculos de documentos de entrega|Delivery document links
accounts.deliverymessage|Mensajes de seguimiento de entregas|Delivery follow-up messages
accounts.deliveryoperation|Historial de operaciones de entrega|Delivery operation history
accounts.changerequest|Solicitudes de cambio|Change requests
accounts.changerequestcomment|Comentarios de solicitudes de cambio|Change request comments
accounts.bugreport|Reportes de errores|Bug reports
accounts.bugcomment|Comentarios de reportes de errores|Bug report comments
accounts.issuecontext|Origen de reportes y solicitudes|Issue source context
accounts.issueresponse|Respuestas a reportes y solicitudes|Issue responses
accounts.issueevent|Historial de reportes y solicitudes|Issue history
accounts.issueattachment|Archivos de reportes y solicitudes|Issue attachments
accounts.deliverable|Entregables|Deliverables
accounts.datamodelentity|Definiciones de datos de los entregables|Deliverable data definitions
accounts.projectdatamodelentity|Definiciones de datos del proyecto|Project data definitions
accounts.deliverableversion|Versiones anteriores de entregables|Previous deliverable versions
accounts.deliverablefile|Archivos adjuntos de entregables|Deliverable attachments
accounts.deliverableclientfolder|Carpetas de archivos del cliente|Client upload folders
accounts.deliverableclientupload|Archivos aportados por el cliente|Client uploads
accounts.notification|Notificaciones|Notifications
accounts.deliverynotificationevent|Avisos de seguimiento de entregas|Delivery activity notices
accounts.deliverynotificationattempt|Intentos de avisos de entregas|Delivery notice attempts
accounts.hostingsubscription|Suscripciones de hosting|Hosting subscriptions
accounts.payment|Pagos de hosting|Hosting payments
accounts.paymenthistory|Historial de pagos|Payment history
accounts.projecthosting|Servicio de hosting del proyecto|Project hosting service
accounts.projecthostingaccountingsource|Vínculos de facturación del hosting|Hosting billing links
accounts.hostingevidencegroup|Grupos de comprobantes de hosting|Hosting evidence groups
accounts.hostingevidence|Comprobantes de hosting|Hosting evidence
accounts.collectionaccountcontext|Origen de cuentas de cobro|Collection account sources
accounts.projectclientaccesspolicy|Permisos de acceso del cliente|Client access permissions
accounts.projectclientaccessevent|Historial de accesos del cliente|Client access history
accounts.projectidea|Ideas y sugerencias|Ideas and suggestions
accounts.projectidearevision|Versiones de ideas|Idea revisions
accounts.projectideacollection|Grupos de ideas|Idea collections
accounts.projectideacollectionitem|Ideas incluidas en grupos|Collected ideas
content.hostingrecord|Registros de hosting|Hosting records
content.hostingcycle|Ciclos de hosting pagados|Paid hosting cycles
content.incomerecord|Ingresos|Income records
content.expenserecord|Gastos y deducciones|Expenses and deductions
content.pocketmovement|Movimientos del bolsillo|Pocket movements
content.document|Documentos|Documents
content.documentfolder|Carpetas de documentos|Document folders
content.documentthread|Hilos documentales|Document threads
content.documentthreaditem|Vínculos de documentos en hilos|Thread document links
content.documentitem|Conceptos de documentos|Document line items
content.documentpaymentmethod|Instrucciones de pago de documentos|Document payment instructions
content.documentcollectionaccount|Detalle de cuentas de cobro|Collection account details
content.documentnote|Notas privadas de documentos|Private document notes
content.documentnoteevent|Historial de notas de documentos|Document note history
content.documentstateepisode|Periodos de estado|State periods
content.documentstateepisodeevent|Cambios del historial de estados|State history events
content.financingagreement|Acuerdos de alianza|Partnership agreements
content.financingagreementevent|Historial de acuerdos de alianza|Partnership agreement history
content.projectbrandasset|Recursos de marca|Brand resources
content.communicationfolder|Carpetas de comunicaciones|Communication folders
content.communicationthread|Conversaciones|Conversations
content.communicationmessage|Mensajes|Messages
content.communicationattachment|Adjuntos de comunicaciones|Communication attachments
content.communicationmessagerevision|Versiones de mensajes|Message revisions
content.communicationmessagedatecorrection|Correcciones de fechas de mensajes|Message date corrections
content.linktree|Páginas de enlaces|Link pages
content.linktreebutton|Botones de páginas de enlaces|Link page buttons
content.linktreeasset|Imágenes de páginas de enlaces|Link page images
content.linktreetemplateversion|Versiones de páginas de enlaces|Link page versions
content.linktreetemplateclick|Estadísticas de páginas de enlaces|Link page statistics
content.qrcard|Tarjetas QR|QR cards
content.contracttemplatemirror|Copias de plantillas de contrato|Contract template copies
secure_links.securelink|Enlaces seguros|Secure links
secure_links.securelinkevent|Historial de enlaces seguros|Secure link history
monitoring.resource|Recursos de monitoreo|Monitoring resources
monitoring.source|Fuentes de monitoreo|Monitoring sources
monitoring.case|Casos de monitoreo|Monitoring cases
monitoring.caseactivity|Actividad de casos de monitoreo|Monitoring case activity
monitoring.report|Reportes de monitoreo|Monitoring reports
monitoring.delivery|Historial de avisos de monitoreo|Monitoring notification history
'''

_KEYS = {
    **{model: key for model, (key, _) in DEPENDENCY_LABELS.items()},
    'accounts.projectcontract': 'contracts', 'accounts.contractamendment': 'contract_amendments',
    'accounts.contractsignatureevidence': 'contract_signatures',
    'accounts.deliveryscope': 'delivery_scopes', 'accounts.deliveryphase': 'delivery_phases',
    'accounts.deliverystage': 'delivery_stages', 'accounts.requirement': 'requirements',
    'accounts.deliverypublication': 'delivery_publications',
    'accounts.requirementreview': 'requirement_reviews',
    'accounts.deliverydocumentsnapshot': 'delivery_documents',
    'accounts.deliveryreviewdocumentevidence': 'delivery_evidence',
    'accounts.payment': 'payments', 'accounts.paymenthistory': 'payment_history',
    'accounts.projecthosting': 'project_hostings',
    'accounts.projecthostingaccountingsource': 'hosting_sources',
    'content.expenserecord': 'expenses', 'content.pocketmovement': 'pocket_movements',
    'content.documentfolder': 'document_folders', 'content.documentthread': 'document_threads',
    'content.documentthreaditem': 'document_thread_items',
    'content.documentstateepisode': 'state_episodes', 'content.documentstateepisodeevent': 'state_events',
    'content.communicationthread': 'communication_threads', 'content.communicationmessage': 'messages',
    'content.communicationattachment': 'communication_attachments',
    'content.linktreeasset': 'linktree_assets', 'content.linktreetemplateversion': 'linktree_versions',
    'content.linktreetemplateclick': 'linktree_clicks',
}

_HELP = {
    'accounts.projectphase': ('Fases creadas desde propuestas. Las propuestas comerciales se conservan.', 'Phases created from proposals. Commercial proposals are retained.'),
    'accounts.datamodelentity': ('Describe la información prevista en una entrega, como clientes o pedidos; no contiene sus registros reales.', 'Describes planned information, such as customers or orders; it does not contain their actual records.'),
    'accounts.projectdatamodelentity': ('Describe cómo se organiza la información del sistema; no son los datos reales de sus usuarios.', 'Describes how system information is organized, not actual user records.'),
    'accounts.deliverable': ('Fichas de entregas y su archivo principal. Los adjuntos y versiones se eligen por separado.', 'Delivery records and their main file. Attachments and versions are selected separately.'),
    'accounts.deliverablefile': ('Archivos adicionales de una entrega, como contratos y anexos.', 'Additional delivery files, such as contracts and annexes.'),
    'accounts.deliverableversion': ('Archivos guardados de versiones anteriores de una entrega.', 'Saved files from previous delivery versions.'),
    'accounts.projectadminaccess': ('Usuarios y contraseñas administrativos guardados para cada ambiente.', 'Saved administrative usernames and passwords for each environment.'),
    'accounts.projectaccessnote': ('Notas y credenciales adicionales guardadas en el detalle del proyecto.', 'Additional notes and credentials saved in the project detail.'),
    'content.incomerecord': ('Registros de ingresos esperados o recibidos; no implica un reembolso.', 'Expected or received income records; deletion does not issue a refund.'),
    'content.pocketmovement': ('Entradas y salidas registradas que determinan el saldo del bolsillo.', 'Recorded money movements used to calculate the pocket balance.'),
    'content.documentstateepisode': ('Periodos durante los que el proyecto o un documento tuvo un estado.', 'Periods during which the project or a document had a particular state.'),
    'content.documentstateepisodeevent': ('Hechos registrados durante esos periodos de estado.', 'Events recorded during those state periods.'),
}

CATEGORIES = {}
for _line in _LABELS.strip().splitlines():
    _model, _es, _en = _line.split('|')
    _description, _description_en = _HELP.get(_model, (
        f'{_es} guardados en este proyecto. Se conservan cuando el interruptor está apagado.',
        f'{_en} saved for this project. They are retained when the switch is off.',
    ))
    CATEGORIES[_model] = {
        'key': _KEYS.get(_model, _model), 'label': _es, 'label_en': _en,
        'description': _description, 'description_en': _description_en,
    }
