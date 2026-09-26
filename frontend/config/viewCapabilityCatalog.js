import { viewCatalogSections } from './viewCatalog.js'

const feature = (id, label, summary, value, viewUrls, options = {}) => ({
  id,
  kind: 'feature',
  label,
  summary,
  value,
  viewUrls,
  icon: options.icon || 'file',
  actors: options.actors || ['team'],
  stage: options.stage || 'Operación',
  secondary: options.secondary === true,
})

const capability = (id, label, summary, value, children, options = {}) => ({
  id,
  kind: 'capability',
  label,
  summary,
  value,
  children,
  icon: options.icon || 'dashboard',
  actors: options.actors || ['team'],
  stage: options.stage || 'Operación',
  relations: options.relations || [],
  secondary: options.secondary === true,
})

const space = (
  id,
  label,
  summary,
  value,
  sectionIds,
  children,
  relations,
  options = {},
) => ({
  id,
  kind: 'space',
  label,
  summary,
  value,
  sectionIds,
  children,
  relations,
  icon: options.icon || 'sitemap',
  actors: options.actors || ['team'],
  stage: options.stage || 'Ecosistema',
})

const panelCapabilities = [
  capability(
    'panel-overview-work',
    'Panorama y tareas',
    'Dirección diaria, prioridades y trabajo interno reunidos en un mismo punto.',
    'Ayuda al equipo a decidir qué atender primero y convertirlo en acciones visibles.',
    [
      feature('panel-command-center', 'Leer el estado del negocio',
        'Resume pipeline, operación, alertas y señales financieras relevantes. El panel se puede instalar como ProjectApp desde la navegación, con ayuda por navegador y reintento sin conexión.',
        'Reduce el tiempo necesario para detectar riesgos y oportunidades.', ['/panel'],
        { icon: 'dashboard', stage: 'Dirección' }),
      feature('panel-team-tasks', 'Organizar el trabajo del equipo',
        'Permite priorizar y mover tareas internas en un tablero Kanban.',
        'Convierte decisiones operativas en responsabilidades trazables.', ['/panel/tasks'],
        { icon: 'board', stage: 'Ejecución' }),
    ],
    { icon: 'dashboard', stage: 'Dirección' },
  ),
  capability(
    'panel-commercial',
    'Comercial',
    'Clientes, propuestas, diagnósticos y configuración de la oferta comercial.',
    'Conecta la oportunidad inicial con una propuesta medible y lista para cerrar.',
    [
      feature('panel-proposals', 'Gestionar propuestas',
        'Crea, edita y sigue propuestas; formaliza con contrato final, anexos curados y correo por secciones. Copia documentos en Markdown, visualiza PDF/imágenes y contenido de DOCX/XLSX, y descarga adjuntos originales. Incluye historial por registro con fecha, autor y consulta de versiones.',
        'Conecta la venta con la documentación formal y conserva evidencia del correo y los archivos enviados.',
        ['/panel/proposals', '/panel/proposals/create', '/panel/proposals/:id/edit'],
        { icon: 'send', stage: 'Venta' }),
      feature('panel-diagnostics', 'Entregar diagnósticos',
        'Administra diagnósticos iniciales y finales con seguimiento de lectura.',
        'Permite demostrar oportunidades antes de definir la solución completa.',
        ['/panel/diagnostics', '/panel/diagnostics/create', '/panel/diagnostics/:id/edit'],
        { icon: 'file', stage: 'Diagnóstico' }),
      feature('panel-additional-modules', 'Administrar módulos adicionales',
        'Mantiene el catálogo bilingüe, sus tres vistas, PDF para clientes, enlaces seleccionados y seguimiento de lectura.',
        'Permite despertar interés con material comercial reutilizable sin recargar la propuesta.',
        ['/panel/additional-modules'],
        { icon: 'puzzle', stage: 'Venta' }),
      feature('panel-financing', 'Gestionar el Programa de Alianza y sus otrosíes',
        'Reúne las condiciones bilingües, la exclusividad conceptual sólo a cinco años, la vista pública, las políticas versionadas y la preparación, firma y seguimiento de otrosíes de financiación.',
        'Permite explicar la alianza y formalizar cada financiación con datos, calendario, documentos privados e historial trazable.',
        ['/panel/partnership-program', '/panel/partnership-program/new', '/panel/partnership-program/:id', '/panel/financing', '/panel/financing/new', '/panel/financing/:id'],
        { icon: 'credit-card', stage: 'Venta' }),
      feature('panel-clients-offers', 'Administrar clientes y paquetes',
        'Centraliza identidades comerciales y ofertas de horas reutilizables. Incluye historial por registro con fecha, autor y consulta de versiones.',
        'Evita duplicar contexto al preparar nuevas oportunidades.',
        ['/panel/clients', '/panel/hour-packages', '/panel/hour-packages/create', '/panel/hour-packages/:id/edit'],
        { icon: 'users', stage: 'Relación' }),
      feature('panel-commercial-settings', 'Configurar mensajes y valores base',
        'Reúne defaults, plantillas y señales de entregabilidad para los flujos comerciales.',
        'Mantiene una voz consistente y reduce errores antes de enviar.',
        ['/panel/defaults', '/panel/proposals/defaults', '/panel/diagnostics/defaults', '/panel/proposals/email-templates', '/panel/proposals/email-deliverability'],
        { icon: 'settings', stage: 'Configuración' }),
    ],
    { icon: 'send', stage: 'Venta' },
  ),
  capability(
    'panel-content',
    'Contenido',
    'Publicaciones, casos, recursos QR y canales de distribución de ProjectApp.',
    'Convierte el conocimiento del equipo en presencia digital y prueba social.',
    [
      feature('panel-editorial-content', 'Publicar blog y LinkedIn',
        'Gestiona artículos, calendario editorial y distribución en LinkedIn.',
        'Sostiene una presencia regular sin separar creación y publicación.',
        ['/panel/blog', '/panel/blog/create', '/panel/blog/:id/edit', '/panel/blog/calendar', '/panel/linkedin'],
        { icon: 'blog', stage: 'Publicación' }),
      feature('panel-portfolio-content', 'Mostrar resultados',
        'Administra los casos de portafolio y su contenido bilingüe.',
        'Transforma entregas reales en evidencia para nuevas oportunidades.',
        ['/panel/portfolio', '/panel/portfolio/create', '/panel/portfolio/:id/edit'],
        { icon: 'portfolio', stage: 'Prueba social' }),
      feature('panel-shareable-resources', 'Crear recursos compartibles',
        'Configura tarjetas QR y Linktrees con colores, logo, Google Fonts o plantillas HTML propias. Valida diseños, cambia imágenes, publica versiones y comparte plantillas entre proyectos del cliente.',
        'Facilita distribuir accesos y campañas con destinos administrables.',
        ['/panel/qr-cards', '/panel/linktrees', '/panel/linktrees/:id/edit'],
        { icon: 'qrcode', stage: 'Distribución' }),
    ],
    { icon: 'blog', stage: 'Contenido' },
  ),
  capability(
    'panel-documents-communications',
    'Documentos y comunicaciones',
    'Documentos, estados, conversaciones y envíos ligados al contexto del cliente.',
    'Conserva la evidencia comercial y operativa sin dispersarla en herramientas externas.',
    [
      feature('panel-documents', 'Crear y seguir documentos',
        'Administra documentos PDF, su contenido y sus estados operativos, con ID visible en listado y editor y búsqueda por ID. Incluye historial por registro con fecha, autor y consulta de versiones. El contrato vigente se consulta en solo lectura y se descarga en PDF o Markdown desde la misma fuente que ve el cliente.',
        'Mantiene entregables formales y su evolución en una sola fuente.',
        ['/panel/documents', '/panel/documents/create', '/panel/documents/:id/edit', '/panel/documents/statuses'],
        { icon: 'file', stage: 'Documentación' }),
      feature('panel-client-threads', 'Registrar conversaciones',
        'Organiza hilos completos en carpetas y subcarpetas por cliente o proyecto, con IDs visibles y búsqueda exacta. Permite recorrer el histórico, plegar la redacción y copiar mensajes directamente.',
        'Preserva decisiones, respuestas y referencias documentales.', ['/panel/communications'],
        { icon: 'mail', stage: 'Comunicación' }),
      feature('panel-email-center', 'Preparar y revisar emails',
        'Centraliza composición con varios destinatarios y copias, configuración e historial de correo.',
        'Da continuidad a los mensajes enviados desde distintos módulos.', ['/panel/emails'],
        { icon: 'send', stage: 'Comunicación' }),
    ],
    { icon: 'file', stage: 'Relación' },
  ),
  capability(
    'panel-projects',
    'Proyectos',
    'Portafolio operativo y ciclo de vida de los proyectos de clientes.',
    'Convierte una venta cerrada en una iniciativa gobernada y visible.',
    [
      feature('panel-project-portfolio', 'Administrar proyectos',
        'Relaciona cada proyecto con su cliente, accesos y Linktrees; organiza documentos y assets privados de branding y diseño. Incluye historial por registro con fecha, autor y consulta de versiones.',
        'Crea una referencia común entre el panel y la plataforma del cliente.', ['/panel/projects'],
        { icon: 'folder', stage: 'Ejecución' }),
      feature('panel-project-lifecycle', 'Gobernar el ciclo del proyecto',
        'Configura y aplica estados con consecuencias operativas trazables.',
        'Evita que una etiqueta visual sustituya decisiones reales de operación.', ['/panel/projects/statuses'],
        { icon: 'refresh', stage: 'Gobierno' }),
      feature('panel-monitoring', 'Seguir eventos técnicos',
        'Separa eventos de proyectos y servidores, muestra la salud de las fuentes y conserva reportes informativos.',
        'Permite revisar y resolver casos con notas e historial, sin depender del correo.', ['/panel/monitoring'],
        { icon: 'database', stage: 'Operación' }),
    ],
    { icon: 'folder', stage: 'Ejecución' },
  ),
  capability(
    'panel-finance',
    'Control financiero',
    'Ingresos, gastos, cobros, hosting, efectivo, tarjetas y controles contables.',
    'Hace visibles los compromisos financieros y su impacto en la operación.',
    [
      feature('panel-financial-flow', 'Leer ingresos y gastos',
        'Resume resultados, estima la cartera pendiente por cobrar y permite gestionar entradas y salidas de dinero. Incluye historial por registro con fecha, autor y consulta de versiones.',
        'Expone la utilidad y los movimientos que la explican.',
        ['/panel/accounting', '/panel/accounting/incomes', '/panel/accounting/expenses'],
        { icon: 'dashboard', stage: 'Resultados' }),
      feature('panel-service-revenue', 'Seguir servicios y cobros',
        'Relaciona hosting, recurrentes, publicidad y cuentas de cobro. Incluye historial por registro con fecha, autor y consulta de versiones.',
        'Anticipa obligaciones y mantiene trazabilidad sobre lo facturable.',
        ['/panel/accounting/hostings', '/panel/accounting/recurring', '/panel/accounting/ads', '/panel/accounting/collections'],
        { icon: 'refresh', stage: 'Proyección' }),
      feature('panel-cash-credit', 'Controlar caja y crédito',
        'Reúne bolsillo, tarjetas y extractos mensuales. Incluye historial por registro con fecha, autor y consulta de versiones.',
        'Permite entender liquidez, deuda y movimientos asociados.',
        ['/panel/accounting/pocket', '/panel/accounting/cards', '/panel/accounting/statements'],
        { icon: 'credit-card', stage: 'Tesorería' }),
      feature('panel-financial-governance', 'Auditar y configurar',
        'Expone historial y preferencias transversales del módulo contable. Incluye historial por registro con fecha, autor y consulta de versiones.',
        'Da contexto a los cambios y mantiene reglas operativas explícitas.',
        ['/panel/accounting/history', '/panel/accounting/settings'],
        { icon: 'settings', stage: 'Control' }),
    ],
    { icon: 'credit-card', stage: 'Finanzas' },
  ),
  capability(
    'panel-integrations',
    'Integraciones',
    'Conectores autorizados que exponen capacidades del panel a asistentes externos.',
    'Reduce trabajo repetitivo sin saltarse permisos ni reglas del producto.',
    [
      feature('panel-mcp-connectors', 'Administrar conectores MCP',
        'Permite activar, rotar y observar conectores especializados por dominio.',
        'Extiende la operación del panel con accesos controlados y auditables.', ['/panel/mcps'],
        { icon: 'database', stage: 'Automatización' }),
    ],
    { icon: 'database', stage: 'Automatización' },
  ),
  capability(
    'panel-governance',
    'Gobierno del sistema',
    'Referencia visual, administración de accesos y entrada segura al panel.',
    'Mantiene coherencia entre quienes operan, las vistas disponibles y el sistema de diseño.',
    [
      feature('panel-product-reference', 'Consultar mapa y sistema de diseño',
        'Expone la taxonomía de vistas y los componentes visuales compartidos.',
        'Facilita explicar el producto y mantener una interfaz consistente.',
        ['/panel/views', '/panel/styleguide'],
        { icon: 'sitemap', stage: 'Referencia' }),
      feature('panel-admin-access', 'Administrar operadores',
        'Permite gestionar las cuentas que acceden al panel interno.',
        'Conserva el acceso operativo dentro de un perímetro administrado.', ['/panel/admins'],
        { icon: 'shield', stage: 'Seguridad' }),
      feature('panel-secure-login', 'Entrar al panel',
        'Exige CAPTCHA en el login de Django Admin antes de abrir el panel.',
        'Bloquea el ingreso si la verificación falla y permite reintentar.', ['/panel/login'],
        { icon: 'key', stage: 'Ingreso', secondary: true }),
    ],
    { icon: 'shield', stage: 'Gobierno' },
  ),
]

const platformCapabilities = [
  capability(
    'platform-access-account', 'Acceso y cuenta',
    'Entrada segura, verificación de identidad y administración del perfil.',
    'Acompaña al usuario desde su primer ingreso hasta una cuenta lista para operar.',
    [
      feature('platform-secure-entry', 'Ingresar de forma segura',
        'Exige CAPTCHA para entrar; conserva la verificación por código y el perfil inicial.',
        'Ofrece reintento ante fallas sin permitir el acceso sin verificación.',
        ['/platform', '/platform/login', '/platform/verify', '/platform/complete-profile'],
        { icon: 'key', actors: ['client', 'team'], stage: 'Ingreso' }),
      feature('platform-account-recovery', 'Recuperar el acceso',
        'Guía la recuperación de contraseña y la verificación de códigos.',
        'Ayuda al cliente a volver a operar sin depender de soporte manual.',
        ['/platform/admin-login', '/platform/forgot-password', '/platform/reset-password', '/platform/verify-code'],
        { icon: 'refresh', actors: ['client', 'team'], stage: 'Ingreso' }),
      feature('platform-profile-management', 'Mantener el perfil al día',
        'Centraliza los datos personales y la configuración de la cuenta.',
        'Mantiene la experiencia y las comunicaciones vinculadas a la persona correcta.', ['/platform/profile'],
        { icon: 'settings', actors: ['client', 'team'], stage: 'Cuenta' }),
    ],
    { icon: 'key', actors: ['client', 'team'], stage: 'Ingreso' },
  ),
  capability(
    'platform-client-projects', 'Clientes y proyectos',
    'Panorama de clientes, proyectos activos y contexto de cada iniciativa.',
    'Convierte cada proyecto en un espacio operativo con una visión compartida.',
    [
      feature('platform-project-portfolio', 'Consultar los proyectos',
        'Permite recorrer el portafolio y entrar al resumen de una iniciativa.',
        'Da una lectura clara de qué se está construyendo y dónde continuar.',
        ['/platform/projects', '/platform/projects/:id', '/platform/dashboard'],
        { icon: 'folder', actors: ['client', 'team'], stage: 'Proyecto' }),
      feature('platform-client-administration', 'Administrar clientes',
        'Permite al equipo consultar clientes y abrir su contexto operativo.',
        'Relaciona cada iniciativa con la persona y organización responsables.',
        ['/platform/clients', '/platform/clients/:id'],
        { icon: 'users', actors: ['team'], stage: 'Administración' }),
    ],
    { icon: 'folder', actors: ['client', 'team'], stage: 'Proyecto' },
  ),
  capability(
    'platform-work-tracking', 'Seguimiento del trabajo',
    'Tablero, solicitudes, bugs y estructura funcional reunidos por proyecto.',
    'Hace visible el avance y ordena las conversaciones sobre lo que falta por resolver.',
    [
      feature('platform-project-board', 'Seguir el avance',
        'Presenta el tablero de trabajo dentro del contexto del proyecto.',
        'Permite entender prioridades, estado y próximos movimientos.',
        ['/platform/projects/:id/board', '/platform/board'],
        { icon: 'board', actors: ['client', 'team'], stage: 'Seguimiento' }),
      feature('platform-bug-follow-up', 'Reportar y seguir bugs',
        'Concentra los problemas reportados y su evolución.',
        'Da trazabilidad a los incidentes sin dispersarlos en conversaciones externas.',
        ['/platform/projects/:id/bugs', '/platform/bugs'],
        { icon: 'bug', actors: ['client', 'team'], stage: 'Soporte' }),
      feature('platform-change-requests', 'Gestionar solicitudes de cambio',
        'Organiza nuevas solicitudes y decisiones fuera del alcance inicial.',
        'Separa los cambios del trabajo acordado y facilita priorizarlos.',
        ['/platform/projects/:id/changes', '/platform/changes'],
        { icon: 'refresh', actors: ['client', 'team'], stage: 'Seguimiento' }),
      feature('platform-data-model', 'Comprender la estructura funcional',
        'Expone el modelo de datos asociado al proyecto cuando está disponible.',
        'Ayuda a conversar sobre la información del producto en un mismo contexto.',
        ['/platform/projects/:id/data-model'],
        { icon: 'database', actors: ['client', 'team'], stage: 'Planeación' }),
    ],
    { icon: 'board', actors: ['client', 'team'], stage: 'Seguimiento' },
  ),
  capability(
    'platform-deliverables', 'Entregables y recursos',
    'Materiales, versiones y resultados compartidos durante el proyecto.',
    'Mantiene las entregas localizables y conectadas con el trabajo que las produjo.',
    [
      feature('platform-deliverable-library', 'Consultar entregables',
        'Permite revisar la biblioteca del proyecto y abrir el detalle de cada entrega.',
        'Ofrece un punto estable para encontrar y validar los recursos recibidos.',
        ['/platform/projects/:id/deliverables', '/platform/projects/:id/deliverables/:deliverableId', '/platform/deliverables'],
        { icon: 'file', actors: ['client', 'team'], stage: 'Entrega' }),
    ],
    { icon: 'file', actors: ['client', 'team'], stage: 'Entrega' },
  ),
  capability(
    'platform-documents', 'Documentos y aprobaciones',
    'Contratos y anexos disponibles para consulta, descarga y aceptación.',
    'Reduce pasos manuales en la entrega documental y deja una aprobación trazable.',
    [
      feature('platform-document-portal', 'Revisar y aprobar documentos',
        'Reúne documentos del cliente y el flujo de firma del documento principal.',
        'Facilita pasar de la lectura a una aprobación verificable en el mismo portal.',
        ['/platform/documents'],
        { icon: 'file', actors: ['client'], stage: 'Aprobación' }),
    ],
    { icon: 'file', actors: ['client', 'team'], stage: 'Aprobación' },
  ),
  capability(
    'platform-commercial-operations', 'Pagos, hosting y cobros',
    'Estado comercial del proyecto, pagos y documentos de cobro.',
    'Da transparencia sobre compromisos económicos y continuidad operativa.',
    [
      feature('platform-project-payments', 'Consultar pagos y hosting',
        'Presenta la operación de pagos asociada al proyecto.',
        'Ayuda al cliente a entender obligaciones, cobertura y continuidad del servicio.',
        ['/platform/projects/:id/payments', '/platform/payments'],
        { icon: 'credit-card', actors: ['client', 'team'], stage: 'Cobro' }),
      feature('platform-collection-accounts', 'Consultar cuentas de cobro',
        'Reúne las cuentas vinculadas al proyecto y sus accesos anteriores.',
        'Mantiene los soportes de cobro dentro del contexto comercial correcto.',
        ['/platform/projects/:id/collection-accounts', '/platform/collection-accounts', '/platform/collection-accounts/:id'],
        { icon: 'file', actors: ['client', 'team'], stage: 'Cobro' }),
    ],
    { icon: 'credit-card', actors: ['client', 'team'], stage: 'Cobro' },
  ),
  capability(
    'platform-notifications', 'Comunicación y notificaciones',
    'Novedades relevantes de la relación y de los proyectos.',
    'Mantiene al usuario enterado sin obligarlo a revisar cada espacio por separado.',
    [
      feature('platform-notification-center', 'Revisar novedades',
        'Agrupa las notificaciones que requieren atención del usuario.',
        'Funciona como bandeja operativa para regresar al contexto indicado.',
        ['/platform/notifications'],
        { icon: 'bell', actors: ['client', 'team'], stage: 'Comunicación' }),
    ],
    { icon: 'bell', actors: ['client', 'team'], stage: 'Comunicación' },
  ),
  capability(
    'platform-access-management', 'Administración de accesos',
    'URLs y credenciales operativas disponibles exclusivamente para el equipo autorizado.',
    'Acelera el soporte y la operación sin exponer información sensible a clientes.',
    [
      feature('platform-project-access', 'Abrir accesos operativos',
        'Centraliza por ambiente URLs, usuarios, contraseñas cifradas y notas sensibles del proyecto, editables también desde el panel, y conserva el enlace global anterior.',
        'Permite al equipo llegar rápidamente a los entornos necesarios para operar.',
        ['/platform/projects/:id/access', '/platform/access'],
        { icon: 'key', actors: ['team'], stage: 'Administración' }),
    ],
    { icon: 'key', actors: ['team'], stage: 'Administración' },
  ),
]

const publicCapabilities = [
  capability(
    'public-brand-acquisition', 'Marca y captación',
    'Páginas que presentan la empresa, sus servicios y los caminos para iniciar una conversación.',
    'Convierte una primera visita en confianza y en una oportunidad comercial.',
    [
      feature('public-brand-entry', 'Descubrir ProjectApp',
        'Reúne la portada, landings especializadas y la historia de la empresa.',
        'Permite que cada necesidad encuentre una explicación relevante.',
        ['/', '/landing-apps', '/landing-software', '/landing-web-design', '/about-us'],
        { icon: 'dashboard', actors: ['visitor'], stage: 'Descubrimiento' }),
      feature('public-contact', 'Iniciar una conversación',
        'Presenta el formulario de contacto y confirma la recepción de la solicitud.',
        'Reduce la distancia entre interés y una conversación comercial.',
        ['/contact', '/contact-success'],
        { icon: 'mail', actors: ['visitor'], stage: 'Conversión' }),
      feature('public-trust-pages', 'Consultar información institucional',
        'Incluye políticas, términos y el manejo de rutas no encontradas.',
        'Sostiene transparencia y una salida clara ante enlaces incorrectos.',
        ['/privacy-policy', '/terms-and-conditions', '/:slug*'],
        { icon: 'shield', actors: ['visitor'], stage: 'Confianza', secondary: true }),
    ],
    { icon: 'dashboard', actors: ['visitor'], stage: 'Descubrimiento' },
  ),
  capability(
    'public-content-proof', 'Contenido y prueba social',
    'Casos, artículos y recursos públicos que muestran conocimiento y resultados.',
    'Permite evaluar la experiencia de ProjectApp antes de iniciar una relación.',
    [
      feature('public-portfolio', 'Explorar casos de trabajo',
        'Presenta el portafolio y el detalle de cada proyecto destacado.',
        'Convierte entregas anteriores en evidencia concreta.',
        ['/portfolio-works', '/portfolio-works/:slug'],
        { icon: 'portfolio', actors: ['visitor'], stage: 'Evaluación' }),
      feature('public-blog', 'Leer conocimiento aplicado',
        'Organiza artículos y sus páginas de lectura completas.',
        'Demuestra criterio y mantiene conversaciones más allá de una venta puntual.',
        ['/blog', '/blog/:slug'],
        { icon: 'blog', actors: ['visitor'], stage: 'Evaluación' }),
      feature('public-linktree', 'Abrir recursos compartidos',
        'Ofrece páginas de enlaces con tema básico o plantillas HTML validadas, imágenes propias, acciones de contacto y analítica de clics.',
        'Concentra destinos relevantes en un acceso fácil de compartir.', ['/lk/:handle'],
        { icon: 'link', actors: ['visitor'], stage: 'Distribución' }),
      feature('public-linkedin-callback', 'Completar conexión editorial',
        'Recibe el retorno técnico de LinkedIn durante su autorización.',
        'Sostiene la distribución editorial sin convertirse en una experiencia principal.',
        ['/auth/linkedin/callback'],
        { icon: 'linkedin', actors: ['team'], stage: 'Integración', secondary: true }),
    ],
    { icon: 'portfolio', actors: ['visitor'], stage: 'Evaluación' },
  ),
  capability(
    'public-additional-modules-experience', 'Módulos adicionales',
    'Catálogo interactivo y selecciones privadas de capacidades opcionales para una plataforma.',
    'Ayuda al prospecto a descubrir posibilidades relevantes y retomarlas en la conversación comercial.',
    [
      feature('public-additional-modules', 'Explorar módulos adicionales',
        'Presenta selector ES/EN, tarjetas, lista, acordeón, tema local, guía, video de 45 segundos con voz y subtítulos y controles flotantes para PDF sin precios y compartir la selección.',
        'Permite entender qué resuelve cada módulo sin depender de una explicación previa.',
        ['/additional-modules', '/additional-modules/share/:uuid'],
        { icon: 'puzzle', actors: ['prospect'], stage: 'Evaluación' }),
    ],
    { icon: 'puzzle', actors: ['visitor', 'prospect'], stage: 'Evaluación' },
  ),
  capability(
    'public-financing-experience', 'Programa de Alianza',
    'Programa informativo que explica financiación, exclusividad, transparencia de requerimientos y continuidad mensual.',
    'Ayuda al prospecto a evaluar una alianza de largo plazo antes de formalizar una propuesta.',
    [
      feature('public-financing', 'Comprender el Programa de Alianza',
        'Presenta dos opciones de alianza, ocho condiciones con exclusividad conceptual sólo a cinco años, reglas expandibles, tema local, guía, video de 45 segundos con voz y subtítulos, PDF y un diálogo para compartir el programa.',
        'Convierte condiciones técnicas y legales en una explicación comercial clara y compartible.',
        ['/partnership-program'],
        { icon: 'credit-card', actors: ['prospect'], stage: 'Evaluación' }),
    ],
    { icon: 'credit-card', actors: ['visitor', 'prospect'], stage: 'Evaluación' },
  ),
  capability(
    'public-proposal-experience', 'Propuesta comercial',
    'Experiencia interactiva para comprender, comparar y responder una propuesta.',
    'Convierte un documento estático en una conversación comercial medible.',
    [
      feature('public-proposal', 'Revisar una propuesta',
        'Presenta alcance, inversión, condiciones y acciones de respuesta.',
        'Ayuda al prospecto a decidir con contexto y permite medir su interés.', ['/proposal/:uuid'],
        { icon: 'send', actors: ['prospect'], stage: 'Decisión' }),
    ],
    { icon: 'send', actors: ['prospect'], stage: 'Decisión' },
  ),
  capability(
    'public-diagnostic-experience', 'Diagnóstico',
    'Lectura ejecutiva y técnica del estado actual de una iniciativa.',
    'Hace visibles prioridades y oportunidades antes de comprometer una solución.',
    [
      feature('public-diagnostic', 'Revisar un diagnóstico',
        'Presenta hallazgos, alcance y recomendaciones en una experiencia compartible.',
        'Prepara una conversación comercial basada en evidencia.', ['/diagnostic/:uuid'],
        { icon: 'file', actors: ['prospect'], stage: 'Diagnóstico' }),
    ],
    { icon: 'file', actors: ['prospect'], stage: 'Diagnóstico' },
  ),
]

export const viewCapabilityCatalog = {
  id: 'projectapp',
  kind: 'root',
  label: 'Ecosistema ProjectApp',
  summary: 'Tres experiencias conectan la operación interna, la colaboración con clientes y la presencia pública.',
  value: 'Permite explicar el producto desde su recorrido y sus resultados, sin exponer datos sensibles.',
  icon: 'sitemap',
  children: [
    space('panel-internal', 'Panel interno',
      'El espacio donde el equipo dirige ventas, contenido, proyectos, comunicaciones y finanzas.',
      'Concentra la operación que sostiene cada relación comercial y cada entrega.',
      ['admin-panel', 'panel-accounting', 'panel-mcps'], panelCapabilities,
      [
        { from: 'panel-overview-work', to: 'panel-commercial', label: 'prioriza oportunidades' },
        { from: 'panel-commercial', to: 'panel-content', label: 'activa contenido' },
        { from: 'panel-commercial', to: 'panel-documents-communications', label: 'formaliza y conversa' },
        { from: 'panel-commercial', to: 'panel-projects', label: 'convierte ventas en ejecución' },
        { from: 'panel-projects', to: 'panel-documents-communications', label: 'conecta evidencia' },
        { from: 'panel-projects', to: 'panel-finance', label: 'conecta compromisos' },
        { from: 'panel-finance', to: 'panel-overview-work', label: 'alimenta decisiones' },
        { from: 'panel-documents-communications', to: 'panel-integrations', label: 'habilita automatización' },
        { from: 'panel-governance', to: 'panel-overview-work', label: 'sostiene la operación' },
      ],
      { icon: 'dashboard', stage: 'Operación' }),
    space('client-platform', 'Plataforma de clientes',
      'El espacio donde clientes y equipo siguen la ejecución, sus entregas y compromisos.',
      'Conecta el proyecto, la comunicación y la operación comercial en una sola experiencia.',
      ['client-platform'], platformCapabilities,
      [
        { from: 'platform-access-account', to: 'platform-client-projects', label: 'habilita la operación' },
        { from: 'platform-client-projects', to: 'platform-work-tracking', label: 'organiza el trabajo' },
        { from: 'platform-work-tracking', to: 'platform-deliverables', label: 'conduce a entregas' },
        { from: 'platform-client-projects', to: 'platform-documents', label: 'da contexto documental' },
        { from: 'platform-client-projects', to: 'platform-commercial-operations', label: 'conecta compromisos' },
        { from: 'platform-documents', to: 'platform-access-account', label: 'requiere identidad' },
        { from: 'platform-work-tracking', to: 'platform-notifications', label: 'genera novedades' },
        { from: 'platform-commercial-operations', to: 'platform-notifications', label: 'comunica vencimientos' },
        { from: 'platform-client-projects', to: 'platform-access-management', label: 'habilita soporte interno' },
      ],
      { icon: 'folder', actors: ['client', 'team'], stage: 'Colaboración' }),
    space('public-experiences', 'Experiencias públicas',
      'Presencia digital, contenido y experiencias comerciales compartidas con visitantes y prospectos.',
      'Atrae oportunidades, demuestra experiencia y acompaña la decisión antes del proyecto.',
      ['public-site', 'public-additional-modules', 'public-financing', 'public-proposals', 'public-diagnostics'], publicCapabilities,
      [
        { from: 'public-brand-acquisition', to: 'public-content-proof', label: 'construye confianza' },
        { from: 'public-brand-acquisition', to: 'public-additional-modules-experience', label: 'descubre posibilidades' },
        { from: 'public-additional-modules-experience', to: 'public-financing-experience', label: 'abre opciones de inversión' },
        { from: 'public-financing-experience', to: 'public-proposal-experience', label: 'formaliza condiciones' },
        { from: 'public-brand-acquisition', to: 'public-diagnostic-experience', label: 'convierte interés en diagnóstico' },
        { from: 'public-diagnostic-experience', to: 'public-proposal-experience', label: 'prepara la propuesta' },
        { from: 'public-content-proof', to: 'public-proposal-experience', label: 'respalda la decisión' },
      ],
      { icon: 'portfolio', actors: ['visitor', 'prospect'], stage: 'Atracción' }),
  ],
}

export const EXPLORER_SPACE_IDS = Object.freeze(viewCapabilityCatalog.children.map((node) => node.id))

export function flattenCapabilityCatalog(root = viewCapabilityCatalog) {
  const result = []
  const visit = (node, parentId = null) => {
    result.push({ ...node, parentId })
    for (const child of node.children || []) visit(child, node.id)
  }
  visit(root)
  return result
}

export function findCapabilityNode(nodeId, root = viewCapabilityCatalog) {
  if (!nodeId || nodeId === root.id) return root
  return flattenCapabilityCatalog(root).find((node) => node.id === nodeId) || null
}

export function capabilityNodePath(nodeId, root = viewCapabilityCatalog) {
  const nodes = flattenCapabilityCatalog(root)
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const path = []
  let current = byId.get(nodeId || root.id)
  while (current) {
    path.unshift(current)
    current = current.parentId ? byId.get(current.parentId) : null
  }
  return path.length > 0 ? path : [root]
}

export function descendantCapabilityViewUrls(node) {
  return [
    ...(node?.viewUrls || []),
    ...(node?.children || []).flatMap((child) => descendantCapabilityViewUrls(child)),
  ]
}

export function capabilityViewRecords(node, sections = viewCatalogSections, { recursive = false } = {}) {
  const entriesByUrl = new Map(
    sections.flatMap((section) => section.views.map((view) => [view.url, view])),
  )
  const urls = recursive ? descendantCapabilityViewUrls(node) : (node?.viewUrls || [])
  return [...new Set(urls)].map((url) => entriesByUrl.get(url)).filter(Boolean)
}

export function explorerTourSteps(spaceId, root = viewCapabilityCatalog) {
  const selectedSpace = root.children.find((node) => node.id === spaceId)
  return (selectedSpace?.children || []).filter((node) => !node.secondary)
}

export function capabilityCatalogFindings(root = viewCapabilityCatalog, sections = viewCatalogSections) {
  const findings = []
  const nodes = flattenCapabilityCatalog(root)
  const sectionById = new Map(sections.map((section) => [section.id, section]))
  const nodeCounts = new Map()

  for (const node of nodes) {
    nodeCounts.set(node.id, (nodeCounts.get(node.id) || 0) + 1)
    if (!node.label?.trim() || !node.summary?.trim() || !node.value?.trim()) {
      findings.push(`Nodo operativo incompleto: ${node.id}`)
    }
    if (!node.icon?.trim()) findings.push(`Nodo operativo sin icono: ${node.id}`)
    for (const sectionId of node.sectionIds || []) {
      if (!sectionById.has(sectionId)) findings.push(`Sección inexistente en nodo operativo: ${node.id}:${sectionId}`)
    }
    if (node.kind === 'feature' && !(node.viewUrls || []).length) {
      findings.push(`Submódulo sin vistas: ${node.id}`)
    }
  }

  for (const [nodeId, count] of nodeCounts) {
    if (count > 1) findings.push(`ID operativo duplicado: ${nodeId}`)
  }

  const allCatalogUrls = sections.flatMap((section) => section.views.map((view) => view.url))
  const allCatalogUrlSet = new Set(allCatalogUrls)
  const taxonomyUrls = nodes.flatMap((node) => node.viewUrls || [])
  const taxonomyCounts = new Map()
  for (const url of taxonomyUrls) {
    taxonomyCounts.set(url, (taxonomyCounts.get(url) || 0) + 1)
    if (!allCatalogUrlSet.has(url)) findings.push(`Vista operativa inexistente: ${url}`)
  }
  for (const url of allCatalogUrls) {
    const count = taxonomyCounts.get(url) || 0
    if (count === 0) findings.push(`Vista sin espacio operativo: ${url}`)
    if (count > 1) findings.push(`Vista repetida entre submódulos: ${url}`)
  }

  const coveredSectionIds = root.children.flatMap((node) => node.sectionIds || [])
  for (const section of sections) {
    const count = coveredSectionIds.filter((sectionId) => sectionId === section.id).length
    if (count === 0) findings.push(`Sección sin espacio operativo: ${section.id}`)
    if (count > 1) findings.push(`Sección repetida entre espacios: ${section.id}`)
  }

  for (const node of nodes) {
    const childIds = new Set((node.children || []).map((child) => child.id))
    for (const relation of node.relations || []) {
      if (!childIds.has(relation.from) || !childIds.has(relation.to)) {
        findings.push(`Relación funcional rota en ${node.id}: ${relation.from} -> ${relation.to}`)
      }
    }
  }

  return findings
}
