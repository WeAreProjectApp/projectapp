"""Plain-language descriptions shown when a connector is expanded in the Panel."""
from content.mcp.module_catalog import CANONICAL_FOR, SECTION_NOTES

DESCRIPTIONS = {
    'operations': 'Consulta el panorama general del negocio: indicadores, alertas y prioridades del dashboard. Sirve para decidir qué atender; las acciones sobre un registro se realizan en el conector de su sección.',
    'commercial': 'Gestiona la relación con clientes y el proceso de venta: fichas, propuestas, diagnósticos, documentos contractuales, seguimiento, correos y valores predeterminados. Organiza sus funciones en Clientes, Propuestas y Diagnósticos, y Configuración. Para paquetes de requerimientos y módulos adicionales usa Nuestra oferta; para alianzas y células usa Programas.',
    'offerings': 'Administra lo que ofrecemos al cliente: paquetes de requerimientos, precios y configuración; y módulos adicionales, categorías, orden, enlaces compartidos, PDFs y videos. Las propuestas y los diagnósticos se gestionan en Comercial. Las condiciones, contratos y versiones de las alianzas y células se gestionan en Programas.',
    'programs': 'Administra nuestros programas y sus condiciones. Reúne las alianzas —Programa de Alianza y Building with Us— y las Células de Building on Demand, con sus acuerdos, contratos, economía interna, documentos y versiones. Para preparar una propuesta usa Comercial; para paquetes de requerimientos y módulos adicionales usa Nuestra oferta.',
    'projects': 'Gestiona los proyectos y su ejecución: etapas, entregables, requisitos, recursos, incidencias, accesos y seguimiento de entregas. Conserva la relación con el cliente y la documentación del proyecto. Los registros financieros, hosting y facturación se administran en Contabilidad.',
    'documents': 'Organiza el Gestor Documental: carpetas, documentos, archivos, estados, notas e hilos documentales. Permite buscar, crear, revisar versiones y preparar movimientos con control de propiedad y audiencia. Los contratos que son espejos de otros módulos se consultan aquí y se editan desde su módulo de origen.',
    'communications': 'Gestiona conversaciones con clientes, mensajes, carpetas, correos independientes, adjuntos y enlaces seguros. Ayuda a consultar el historial y preparar envíos con sus destinatarios. Las lecturas de secretos requieren un permiso explícito; las acciones sensibles solicitan confirmación.',
    'content': 'Administra el contenido y la presencia pública de ProjectApp: blog, calendario editorial, LinkedIn, portafolio, tarjetas QR y Linktrees. Permite preparar recursos y gestionar su publicación. Las propuestas, programas y módulos adicionales tienen sus propios conectores.',
    'accounting': 'Administra las finanzas: ingresos por cobrar o recibidos, gastos, bolsillo, participaciones, recurrentes, cuentas de cobro, tarjetas y extractos. Incluye hosting, suscripciones y conciliación. Los recurrentes representan gastos que pagamos; los cobros a clientes se registran como ingresos.',
    'tasks': 'Organiza el trabajo interno del equipo mediante el Kanban: tareas, responsables, prioridades, orden, comentarios y recordatorios. Permite consultar pendientes y archivados y mantener el seguimiento diario. Los entregables de clientes se gestionan desde Proyectos.',
}
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
LABELS = {'commercial': 'Comercial', 'offerings': 'Nuestra oferta', 'programs': 'Programas',
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
