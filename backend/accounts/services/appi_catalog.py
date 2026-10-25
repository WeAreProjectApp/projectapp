"""Finite client guide vocabulary. Editors change prose, never routes or permissions."""
GUIDES = {
    'projects': ('projects', 'Find my projects', 'Abre Proyectos y selecciona el proyecto que quieres consultar.', 'Open Proyectos (Projects) and select the project you want to check.'),
    'documents': ('documents', 'Find client documents', 'Abre Documentos. Selecciona el documento para consultarlo o descargarlo.', 'Open Documentos (Documents). Select a document to read or download it.'),
    'sign_document': ('documents', 'Sign a document', '1. Abre Documentos.\n2. Selecciona el documento que requiere firma.\n3. Lee su contenido.\n4. Usa la opción de firma disponible y confirma únicamente si estás de acuerdo.', '1. Open Documentos (Documents).\n2. Select the document requiring your signature.\n3. Read it.\n4. Use the available signature option and confirm only if you agree.'),
    'collection_accounts': ('collection-accounts', 'Find collection accounts', 'Abre Cuentas de cobro. Selecciona una cuenta para consultar sus datos y las opciones disponibles.', 'Open Cuentas de cobro (Collection accounts). Select an account to view its details and available options.'),
    'hosting_payments': ('hosting', 'View hosting and payments', 'Abre Hosting en el menú de la plataforma. Consulta el servicio y sus opciones de pago disponibles. Appi no realiza pagos.', 'Open Hosting in the platform menu. Check your service and the available payment options. Appi does not make payments.'),
    'notifications': ('notifications', 'Read notifications', 'Abre Notificaciones. Selecciona la novedad que quieres revisar para acceder a su detalle.', 'Open Notificaciones (Notifications). Select the update you want to review.'),
    'profile': ('profile', 'Edit my profile', '1. Abre Configuración en el menú de tu cuenta.\n2. Edita los datos de tu perfil.\n3. Pulsa Guardar cambios.', '1. Open Configuración (Settings) in your account menu.\n2. Edit your profile details.\n3. Click Guardar cambios (Save changes).'),
    'help': ('help', 'Find platform help', 'Abre Ayuda en el menú lateral o móvil. Consulta los recursos, videos o recorridos que tengas disponibles.', 'Open Ayuda (Help) in the sidebar or mobile menu. Choose an available resource, video or tour.'),
    'project_overview': ('project-summary', 'Find project overview', 'En {scope_label}:\n1. Abre Proyectos y selecciona tu proyecto.\n2. Revisa el resumen, avance y estado publicados.', 'For {scope_label}:\n1. Open Proyectos (Projects) and select your project.\n2. Check its published summary, progress and status.'),
    'delivery_review': ('project-delivery', 'Review a published stage or requirement', 'En {scope_label}:\n1. Abre el seguimiento de entrega del proyecto.\n2. Selecciona una fase y etapa publicadas.\n3. Revisa la guía y los requerimientos.\n4. Registra tu revisión con las opciones disponibles. Appi no aprueba ni rechaza por ti.', 'For {scope_label}:\n1. Open the project delivery workspace.\n2. Select a published phase and stage.\n3. Read the guide and requirements.\n4. Submit your review using the available options. Appi does not approve or reject on your behalf.'),
    'find_contract': ('project-delivery', 'Find project contract', 'En {scope_label}:\n1. Abre el seguimiento de entrega.\n2. Busca el contrato y sus modificaciones compartidas.\n3. Abre la copia disponible para consultarla. Si no aparece, solicita al equipo que comparta el documento.', 'For {scope_label}:\n1. Open the delivery workspace.\n2. Find the shared contract and amendments.\n3. Open the available copy. If it is missing, ask the team to share it.'),
    'ideas': ('project-ideas', 'Record a project idea', 'En {scope_label}:\n1. Abre Ideas.\n2. Utiliza la opción para añadir una idea.\n3. Describe tu propuesta y guárdala. Una idea no equivale a una ampliación contractual aprobada.', 'For {scope_label}:\n1. Open Ideas.\n2. Choose the option to add an idea.\n3. Describe it and save. An idea does not constitute an approved contract change.'),
    'change_request': ('project-changes', 'Request a change', 'En {scope_label}:\n1. Abre Solicitudes.\n2. Selecciona la opción para crear una solicitud.\n3. Indica el requerimiento afectado y describe el cambio.\n4. Revisa y envía la solicitud para evaluación.', 'For {scope_label}:\n1. Open Solicitudes (Change requests).\n2. Choose the option to create a request.\n3. Select the affected requirement and describe the change.\n4. Review and submit it for evaluation.'),
    'report_bug': ('project-bugs', 'Report a bug', 'En {scope_label}:\n1. Abre Proyectos y selecciona tu proyecto.\n2. Entra en Reporte de bugs.\n3. Pulsa Reportar bug.\n4. Escribe el título y describe qué sucede, los pasos para reproducirlo y qué esperabas. Añade una captura si ayuda.\n5. Revisa la información y pulsa Reportar bug para enviarlo.', 'For {scope_label}:\n1. Open Proyectos (Projects) and select your project.\n2. Open Reporte de bugs (Bug reports).\n3. Click Reportar bug (Report bug).\n4. Enter a title, what happens, reproduction steps and the expected result. Add a screenshot if useful.\n5. Review your information and click Reportar bug to submit.'),
    'track_bug': ('project-bugs', 'Track a reported bug', 'En {scope_label}:\n1. Abre Reporte de bugs.\n2. Busca el reporte y revisa su estado.\n3. Abre el detalle para consultar la respuesta del equipo y los comentarios.', 'For {scope_label}:\n1. Open Reporte de bugs (Bug reports).\n2. Find the report and check its status.\n3. Open its details to read the team response and comments.'),
    'deliverables': ('project-resources', 'Find deliverables and downloads', 'En {scope_label}:\n1. Abre Recursos del proyecto.\n2. Selecciona el recurso compartido.\n3. Usa las opciones de consulta o descarga disponibles.', 'For {scope_label}:\n1. Open the project resources.\n2. Select a shared resource.\n3. Use its available view or download options.'),
    'resources': ('project-resources', 'Find project resources', 'En {scope_label}, abre Recursos para consultar los archivos y materiales que el equipo haya compartido contigo.', 'For {scope_label}, open Resources to see the files and materials the team has shared with you.'),
    'access': ('project-access', 'Find permitted project accesses', 'En {scope_label}, abre Accesos y consulta únicamente los accesos habilitados para tu cuenta. No compartas contraseñas en el chat.', 'For {scope_label}, open Access and view only the accesses enabled for your account. Do not share passwords in chat.'),
    'secure_links': ('project-secure-links', 'Find secure links', 'En {scope_label}, abre Enlaces y consulta los enlaces seguros disponibles. Respeta su vencimiento y condiciones de uso; no compartas sus secretos en el chat.', 'For {scope_label}, open Links and check the available secure links. Follow their expiration and use conditions; do not share their secrets in chat.'),
    'comment_issue': ('project-bugs', 'Comment on a report', 'En {scope_label}:\n1. Abre el reporte de bug que quieras comentar.\n2. Escribe el comentario en el detalle.\n3. Revisa lo escrito y pulsa Enviar. Si el reporte está archivado, consulta las opciones que muestre la plataforma.', 'For {scope_label}:\n1. Open the bug report you want to comment on.\n2. Write your comment in its details.\n3. Review it and click Enviar (Send). If the report is archived, use the options offered by the platform.'),
    'voice_report': ('project-bugs', 'Dictate a report', 'En {scope_label}:\n1. Abre el formulario de reporte.\n2. Usa el control de nota de voz disponible.\n3. Graba tu explicación (30 segundos recomendados, máximo 60).\n4. Revisa y edita la transcripción y el borrador.\n5. Confirma el envío desde el formulario; grabar no envía el reporte.', 'For {scope_label}:\n1. Open the report form.\n2. Use the available voice-note control.\n3. Record your explanation (30 seconds recommended, 60 seconds maximum).\n4. Review and edit the transcript and draft.\n5. Submit using the form; recording alone does not submit a report.'),
}


def guide_slots():
    return {f'guide_{name}': ({'scope_label'} if '{scope_label}' in row[2] else set()) for name, row in GUIDES.items()}


def guide_defaults():
    return [{'family': 'chatbot', 'scenario': f'guide_{name}', 'language': language, 'content': row[index]}
            for name, row in GUIDES.items() for language, index in (('es', 2), ('en', 3))]


DATA_SCENARIOS = {
    'project_status': 'Current project status and progress',
    'phase_status': 'Published phase/stage status and pending reviews',
    'deliverables': 'Shared project deliverables and their current versions',
    'bugs': 'Reported bugs, their status and severity',
    'project_health': 'Evidence-based project health: progress, dates, open bugs and reviews',
    'contract_clause': 'Read the relevant clause in the client-visible contractual copy',
}
CONTRACT_TOPICS = {
    'intellectual_property': ('propiedad intelectual', 'intellectual property', 'derechos de autor', 'copyright'),
    'deliverables': ('entregable', 'deliverable', 'alcance', 'scope'),
    'payments': ('pago', 'payment', 'precio', 'price', 'honorarios'),
    'deadlines': ('plazo', 'deadline', 'cronograma', 'schedule', 'vigencia'),
    'confidentiality': ('confidencial', 'confidential'),
    'warranty': ('garantía', 'warranty', 'soporte', 'support'),
    'termination': ('terminación', 'termination', 'cancelación', 'cancellation'),
    'general': (),
}


def routing_options():
    return {**DATA_SCENARIOS, **{f'guide_{name}': 'HOW TO use the platform: ' + row[1] for name, row in GUIDES.items()},
            'out_of_scope': 'Outside the client platform/project universe, including weather, general time, personal conversation, admin operations or unrelated requests',
            'clarification': 'Ambiguous, mixed unrelated/in-scope requests, historical state not recorded, or insufficient information'}
