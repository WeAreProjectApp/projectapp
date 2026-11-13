"""Plain-language descriptions shown when a connector is expanded in the Panel."""
from content.mcp.module_catalog import CANONICAL_FOR, INFRASTRUCTURE_TOOLS, SECTION_NOTES

NAMES = {
    'operations': 'Gestor de operaciones', 'commercial': 'Gestor de clientes y ventas',
    'offerings': 'Gestor de nuestra oferta', 'programs': 'Gestor de programas',
    'projects': 'Gestor de proyectos', 'data-integrity': 'Gestor de integridad de datos',
    'documents': 'Gestor de documentos', 'communications': 'Gestor de comunicaciones',
    'content': 'Gestor de contenido', 'accounting': 'Gestor de contabilidad',
    'tasks': 'Gestor de tareas', 'procurement': 'Gestor de contratación pública',
}

DESCRIPTIONS = {
    'procurement': 'Busca y revisa oportunidades de contratación pública de SECOP. Administra búsquedas guardadas, clasificaciones, alertas y su seguimiento; consulta sincronizaciones y exporta resultados. Las búsquedas y alertas conservan su propietario. No presenta ofertas ni modifica procesos en SECOP.',
    'data-integrity': 'Revisa inconsistencias entre clientes, proyectos, documentos, comunicaciones, contabilidad y propuestas. Consulta hallazgos, ejecuta revisiones, acepta casos intencionales y corrige por lotes con vista previa, motivo, historial y deshacer. No reescribe evidencia emitida.',
    'operations': 'Consulta indicadores, alertas y prioridades del dashboard. Gestiona el seguimiento operativo: casos, estados, notas, reportes y asociación de recursos observados a proyectos. Conserva evidencia e historial; no configura credenciales ni ingiere observaciones en nombre de una fuente. Las acciones de negocio se realizan en el gestor de su sección.',
    'commercial': 'Gestiona la relación con clientes y el proceso de venta: fichas, propuestas, diagnósticos, documentos contractuales, seguimiento, correos y valores predeterminados. Organiza sus funciones en Clientes, Propuestas y Diagnósticos, y Configuración. Para paquetes de requerimientos y módulos adicionales usa Nuestra oferta; para alianzas y células usa Programas.',
    'offerings': 'Administra lo que ofrecemos al cliente: paquetes de requerimientos, precios y configuración; y módulos adicionales, categorías, orden, enlaces compartidos, PDFs y videos. Las propuestas y los diagnósticos se gestionan en Comercial. Las condiciones, contratos y versiones de las alianzas y células se gestionan en Programas.',
    'programs': 'Administra nuestros programas y sus condiciones. Reúne las alianzas —Programa de Alianza y Building with Us— y las Células de Building on Demand, con sus acuerdos, contratos, economía interna, documentos y versiones. Para preparar una propuesta usa Comercial; para paquetes de requerimientos y módulos adicionales usa Nuestra oferta.',
    'projects': 'Gestiona los proyectos y su ejecución: etapas, entregables, requisitos, recursos, incidencias, accesos y seguimiento de entregas. Conserva la relación con el cliente y la documentación del proyecto. La eliminación irreversible exige permiso explícito, vista previa y confirmación. Los registros financieros, hosting y facturación se administran en Contabilidad.',
    'documents': 'Organiza carpetas, documentos, archivos, estados, notas e hilos documentales. Permite buscar, crear, revisar versiones y preparar movimientos con control de propiedad y audiencia. Los contratos que son espejos de otros módulos se consultan aquí y se editan desde su módulo de origen.',
    'communications': 'Gestiona conversaciones con clientes, mensajes, carpetas, correos independientes, adjuntos y enlaces seguros. Ayuda a consultar el historial y preparar envíos con sus destinatarios. Consultar secretos o sus URLs requiere los permisos explícitos de la credencial; las acciones sensibles solicitan confirmación.',
    'content': 'Administra el contenido y la presencia pública de ProjectApp: blog, calendario editorial, LinkedIn, portafolio, tarjetas QR y Linktrees. Permite preparar recursos y gestionar su publicación. Las propuestas, programas y módulos adicionales tienen sus propios conectores.',
    'accounting': 'Administra las finanzas: ingresos por cobrar o recibidos, gastos, bolsillo, participaciones, recurrentes, cuentas de cobro, tarjetas y extractos. Incluye hosting, suscripciones y conciliación. Los recurrentes representan gastos que pagamos; los cobros a clientes se registran como ingresos.',
    'tasks': 'Organiza el trabajo interno del equipo mediante el Kanban: tareas, responsables, prioridades, orden, comentarios y recordatorios. Permite consultar pendientes y archivados y mantener el seguimiento diario. Los entregables de clientes se gestionan desde Proyectos.',
}

# First matching resource wins. Every remaining domain tool is still represented
# by its module group; infrastructure is described separately from business work.
CAPABILITY_GROUPS = {
    'operations': (('Casos, reportes y recursos observados', ('monitoring',)), ('Indicadores y Radar de atención', ())),
    'commercial': (
        ('Clientes y contactos', ('client',)), ('Propuestas y documentos comerciales', ('proposal', 'create_share_link')),
        ('Diagnósticos', ('diagnostic', 'send_initial', 'send_final', 'mark_in_analysis')),
        ('Consultoría y asesoría', ('consulting',)),
        ('Calculadora de requerimientos', ('calculator', 'requirement_estimate', 'requirement_actual', 'requirement_calibration')),
        ('Correos y configuración comercial', ()),
    ),
    'offerings': (('Paquetes de requerimientos', ('hour_package',)), ('Módulos adicionales y recursos', ())),
    'programs': (('Programa de Alianza', ('partnership', 'financing')),
                 ('Building with Us', ('building_with_us',)), ('Células de Building on Demand', ())),
    'projects': (
        ('Acceso autorizado', ('access',)), ('Ayuda y tutoriales', ('help', 'guided_tour', 'tour_progress')),
        ('IA de Plataforma', ('platform_ai',)), ('Entregas, etapas y requisitos', ('delivery',)),
        ('Recursos de Plataforma', ('resource',)), ('Incidencias y solicitudes', ('issue', 'bug', 'change_request')),
        ('Proyectos, estados y seguimiento', ()),
    ),
    'data-integrity': (('Hallazgos, revisiones y correcciones de integridad', ()),),
    'documents': (('Carpetas y organización', ('folder',)), ('Hilos documentales', ('thread',)),
                  ('Documentos, versiones y archivos', ())),
    'communications': (('Enlaces seguros', ('secure_link',)), ('Carpetas de comunicaciones', ('folder',)),
                       ('Conversaciones, mensajes y correos', ())),
    'content': (('Blog y calendario editorial', ('blog',)), ('LinkedIn', ('post', 'linkedin', 'get_connection_status')),
                ('Portafolio', ('portfolio',)), ('Tarjetas QR y Linktrees', ())),
    'accounting': (('Ingresos y liquidaciones', ('income', 'settlement', 'abono')),
                   ('Gastos y recurrentes', ('expense', 'recurring')),
                   ('Hosting y suscripciones', ('hosting', 'subscription')),
                   ('Cuentas de cobro', ('collection_account', 'billing')),
                   ('Tarjetas y extractos', ('card', 'statement', 'transaction')),
                   ('Bolsillo, participaciones y configuración', ())),
    'tasks': (('Tareas, responsables y seguimiento', ()),),
    'procurement': (('Oportunidades y clasificación', ('opportunit', 'classification', 'filters')),
                    ('Búsquedas guardadas', ('search',)), ('Alertas, envíos y sincronización', ())),
}

ACTION_LABELS = (
    ('Consultar', ('get_', 'list_', 'describe_', 'search_', 'read_', 'browse_', 'compare_', 'reveal_')),
    ('Previsualizar', ('preview_',)),
    ('Sugerir', ('suggest_',)),
    ('Crear', ('create_', 'add_', 'duplicate_', 'prepare_')),
    ('Registrar', ('append_', 'comment_', 'log_', 'record_', 'learn_', 'attest_')),
    ('Actualizar', ('update_', 'change_', 'correct_', 'override_', 'save_', 'mark_', 'toggle_',
                    'transition_', 'invalidate_', 'mute_', 'bulk_update_')),
    ('Configurar', ('set_', 'configure_', 'initialize_')),
    ('Renombrar', ('rename_',)),
    ('Asignar', ('assign_', 'reassign_', 'bulk_assign_')),
    ('Vincular', ('link_', 'associate_', 'adopt_')),
    ('Desvincular', ('unlink_', 'dissolve_')),
    ('Ordenar', ('reorder_',)),
    ('Mover', ('move_',)),
    ('Archivar', ('archive_',)),
    ('Restaurar', ('unarchive_', 'restore_', 'reset_')),
    ('Reabrir', ('reopen_', 'reactivate_')),
    ('Enviar', ('send_', 'resend_')),
    ('Reintentar', ('retry_',)),
    ('Publicar', ('publish_',)),
    ('Compartir', ('share_',)),
    ('Descargar', ('download_',)),
    ('Exportar', ('export_',)),
    ('Cargar archivos', ('upload_',)),
    ('Sustituir archivos', ('replace_',)),
    ('Eliminar según las reglas', ('delete_', 'remove_', 'force_delete_')),
    ('Retirar', ('retire_',)),
    ('Cancelar', ('cancel_', 'abort_')),
    ('Anular', ('void_',)),
    ('Revocar', ('revoke_',)),
    ('Descartar', ('dismiss_',)),
    ('Revertir', ('undo_', 'reverse_')),
    ('Cerrar', ('close_', 'complete_', 'finish_', 'finalize_')),
    ('Aprobar', ('approve_',)),
    ('Confirmar', ('confirm_',)),
    ('Revisar', ('review_',)),
    ('Evaluar', ('evaluate_', 'bulk_evaluate_', 'begin_package_request_evaluation')),
    ('Validar', ('validate_', 'check_', 'test_', 'verify_package_payment')),
    ('Resolver', ('resolve_',)),
    ('Fusionar', ('merge_',)),
    ('Conciliar', ('reconcile_',)),
    ('Sincronizar', ('sync_',)),
    ('Solicitar sincronización', ('request_procurement_sync',)),
    ('Escanear', ('start_integrity_scan',)),
    ('Aplicar cambios', ('apply_', 'convert_')),
    ('Liquidar', ('settle_', 'bulk_settle_')),
    ('Generar', ('generate_', 'render_')),
    ('Importar', ('import_',)),
    ('Gestionar por lote', ('bulk_action_',)),
    ('Otras acciones del módulo', ()),
)


def connector_name(slug, fallback=''):
    return NAMES.get(slug, fallback)


def connector_capabilities(slug, tools):
    """Derive actions only from tools actually published by this connector."""
    groups = CAPABILITY_GROUPS.get(CANONICAL_FOR.get(slug, slug), ())
    result = []
    remaining = [tool for tool in tools if tool['name'] not in INFRASTRUCTURE_TOOLS and not tool.get('_hidden')]
    for label, fragments in groups:
        selected = [tool for tool in remaining if not fragments or any(part in tool['name'] for part in fragments)]
        if not selected:
            continue
        names = {tool['name'] for tool in selected}
        remaining = [tool for tool in remaining if tool['name'] not in names]
        actions = []
        for tool in selected:
            action = next(label for label, prefixes in ACTION_LABELS if not prefixes or tool['name'].startswith(prefixes))
            if action not in actions:
                actions.append(action)
        result.append({'label': label, 'actions': actions, 'tools': sorted(names),
                       'requires_confirmation': any(tool.get('requires_confirmation') for tool in selected)})
    return result
LEGACY_DESCRIPTIONS = {
    'clients': 'Conserva la consulta y edición de fichas de clientes del catálogo anterior.',
    'proposals': 'Conserva las herramientas anteriores de propuestas, contratos, documentos, seguimiento y envíos.',
    'diagnostics': 'Conserva las herramientas anteriores para crear, editar y enviar diagnósticos iniciales y finales.',
    'additional-modules': 'Conserva las herramientas anteriores de categorías, módulos adicionales, enlaces, PDFs y videos.',
    'partnership-program': 'Conserva las herramientas anteriores del Programa de Alianza, acuerdos de financiación, políticas, documentos y videos.',
    'building-with-us': 'Conserva las herramientas anteriores del programa Building with Us y de su contrato versionado.',
    'building-on-demand': 'Conserva las herramientas anteriores de Células: programa, niveles, precios, economía, estimador y contrato.',
    'blog': 'Conserva las herramientas anteriores de artículos y calendario del blog.',
    'linkedin-personal': 'Conserva las herramientas anteriores de publicaciones y conexión de LinkedIn.',
    'accounting-ledger': 'Conserva las herramientas anteriores de ingresos, gastos, bolsillo, recurrentes y movimientos contables.',
    'accounting-billing': 'Conserva las herramientas anteriores de cuentas de cobro, hosting y facturación.',
    'accounting-cards': 'Conserva las herramientas anteriores de tarjetas, extractos, transacciones y conciliación.',
}
LABELS = {'data-integrity': 'Integridad de datos', 'commercial': 'Comercial', 'offerings': 'Nuestra oferta', 'programs': 'Programas',
          'content': 'Contenido ProjectApp', 'accounting': 'Contabilidad'}


def connector_description(slug, fallback=''):
    if slug in DESCRIPTIONS:
        return DESCRIPTIONS[slug]
    if slug in LEGACY_DESCRIPTIONS:
        target = CANONICAL_FOR[slug]
        return (f'{LEGACY_DESCRIPTIONS[slug]} Está en retirada: su reemplazo es '
                f'{LABELS.get(target, target)}. Los accesos existentes se conservan '
                'durante la transición; las nuevas conexiones deben usar el reemplazo.')
    return fallback


def section_note(slug):
    return SECTION_NOTES.get(CANONICAL_FOR.get(slug, slug), '')
