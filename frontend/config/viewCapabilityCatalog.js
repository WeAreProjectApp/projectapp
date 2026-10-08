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
        'Acepta sin aprovisionar automáticamente. El equipo confirma cliente y proyecto existentes o nuevos, puede posponer y retomar la revisión y elige contratos de la propuesta o varios personalizados conservando detalles comercial y técnico, originales y firmas. El paquete confirmado admite descargas privadas y reintentos sobre el mismo vínculo. Consulta los intereses del cliente con fecha en General y decide manualmente el alcance y la inversión, sin recargos automáticos. Crea, edita y sigue propuestas en seis áreas con subpestañas: General, Propuesta, Comunicación, Documentos, Proyecto y Seguimiento, disponibles según el estado; conserva enlaces previos y cambios pendientes al navegar; permite descargar desde General los PDFs originales comercial y técnico aun vencidos; carga o sustituye videos genéricos y personalizados desde Configuraciones y Propuesta > Recursos; previsualiza el video de bienvenida y controla su visibilidad global desde Configuraciones e individual desde General; cambia la modalidad de contrato en cualquier estado, con nota y revisión confirmada fuera de negociación, conservación literal de personalizados y consulta o restauración de instantáneas permanentes; formaliza con contrato único o con contratos de producto y de servicio, anexos con el contenido original: diez capítulos comerciales y tres técnicos (stack, modelo de datos y módulos), con orden y numeración propios y correo por secciones. En modalidad separada, las condiciones completas de hosting se incorporan al contrato de servicio y el anexo comercial queda centrado en el producto; avisa si el servicio requiere regeneración antes de formalizar. Crea y edita contratos en formularios compactos con campos adaptados a móvil. Configura las opciones y preselecciones de duración y preavisos del servicio. En el contrato, elige desde desplegables visuales accesibles con opciones numéricas convertidas a letras y texto personalizado editable que se conserva al reabrir; los errores de guardado mantienen el borrador para corregir o reintentar. Copia documentos en Markdown, visualiza PDF/imágenes y contenido de DOCX/XLSX, y descarga adjuntos originales, contratos, PDF formales y CSV sin abrir ventanas; informa errores para reintentar. Incluye historial por registro con fecha, autor y consulta de versiones. Proyecto > Datos reúne cliente, contactos y proyecto en cualquier estado, con revisión confirmada de reasignaciones al mismo cliente, también desde un proyecto eliminado. Correos concentra los ajustes de email; ambos guardan sin sobrescribir borradores de General. Actividad carga veinte entradas por vez y permite reintentar; Historial muestra rango, total y controles de página.',
        'Conecta la venta con la documentación formal y conserva evidencia del correo y los archivos enviados.',
        ['/panel/proposals', '/panel/proposals/create', '/panel/proposals/:id/edit'],
        { icon: 'writing', stage: 'Venta' }),
      feature('panel-diagnostics', 'Entregar diagnósticos',
        'Administra diagnósticos iniciales y finales con seguimiento de lectura. Descarga acuerdos, borradores, adjuntos y CSV sin abandonar el panel; conserva la vista previa interna y permite reintentar errores.',
        'Permite demostrar oportunidades antes de definir la solución completa.',
        ['/panel/diagnostics', '/panel/diagnostics/create', '/panel/diagnostics/:id/edit'],
        { icon: 'file', stage: 'Diagnóstico' }),
      feature('panel-additional-modules', 'Administrar módulos adicionales',
        'Mantiene el catálogo bilingüe, sus tres vistas, PDF para clientes, enlaces seleccionados, seguimiento de lectura y recursos de video cargables por idioma.',
        'Permite despertar interés con material comercial reutilizable sin recargar la propuesta.',
        ['/panel/additional-modules'],
        { icon: 'puzzle', stage: 'Venta' }),
      feature('panel-financing', 'Gestionar el Programa de Alianza y sus otrosíes',
        'Reúne las condiciones bilingües, la exclusividad conceptual sólo a cinco años, la vista pública, las políticas versionadas y la preparación, firma y seguimiento de otrosíes de financiación. Configuración administra el archivo de video explicativo.',
        'Permite explicar la alianza y formalizar cada financiación con datos, calendario, documentos privados e historial trazable.',
        ['/panel/partnership-program', '/panel/partnership-program/new', '/panel/partnership-program/:id', '/panel/financing', '/panel/financing/new', '/panel/financing/:id'],
        { icon: 'credit-card', stage: 'Venta' }),
      feature('panel-clients-offers', 'Administrar clientes y paquetes',
        'Centraliza identidades comerciales y ofertas de horas reutilizables. La ficha conserva dirección y distingue NIT de C.C.; las cuentas de cobro reutilizan sus datos y permiten editar la ficha durante la preparación. Incluye historial por registro con fecha, autor y consulta de versiones; aprobar desde la ficha de un cliente abre la misma revisión de cliente, proyecto y documentos. Incluye consulta y descarga de datos conservados sin proyecto; su traslado se hace desde Asignar registros sin proyecto del proyecto de destino.',
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
        'Administra documentos PDF, su contenido y sus estados operativos, con ID visible en listado y editor y búsqueda por ID. Incluye historial por registro con fecha, autor y consulta de versiones. Las tres plantillas de contrato (unificado, producto y servicio) permanecen en Contratos como espejos de solo lectura, con versión y fecha de sincronización; se consultan y descargan en PDF o Markdown. Las carpetas rechazan nombres repetidos en el mismo nivel, incluidos los archivados.',
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
      feature('panel-secure-links', 'Compartir información sensible',
        'Genera la URL con un formulario de campos esenciales, dropdown de tipos y opciones plegables. Permite marcar el envío manual y distinguir enlaces listos, enviados, abiertos, vencidos y revocados; conserva edición, eliminación confirmada, reactivación e historial.',
        'Evita pegar secretos en correos o WhatsApp sin perder el control de quién los abrió.', ['/panel/secure-links'],
        { icon: 'key', stage: 'Comunicación' }),
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
        'Relaciona cada proyecto con su cliente, accesos y Linktrees; organiza documentos y assets privados de branding y diseño. Reúne las acciones en tres puntos y permite eliminar proyectos vacíos con confirmación. Desde Eliminar → Cambiar estado, un superusuario elige categorías con interruptores apagados por defecto y confirma DELETE; las dependencias requieren elección manual. Lo conservado queda bajo el cliente sin proyecto; las evidencias protegidas siguen bloqueando. Asignar registros sin proyecto traslada, con auditoría y opción de deshacer, los ingresos, documentos e hilos conservados que el equipo elija. Incluye historial por registro con fecha, autor y consulta de versiones.',
        'Crea una referencia común entre el panel y la plataforma del cliente.', ['/panel/projects'],
        { icon: 'folder', stage: 'Ejecución' }),
      feature('panel-project-ideas', 'Recopilar ideas para el futuro',
        'Conserva autoría, versiones y archivo reversible; congela copias de una selección explícita por proyecto y cliente.',
        'Prepara conversaciones de un contrato futuro sin cambiar alcance, entregas ni aprobaciones.', ['/panel/projects/:id/ideas'],
        { icon: 'file', stage: 'Proyecto' }),
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
        'Resume resultados, estima la cartera pendiente por cobrar y permite gestionar entradas y salidas de dinero con captura base/total incluido y desglose de IVA, propuesto al 19 % en nuevos registros. Editar conserva la tasa guardada. Los ingresos con cliente requieren una cuenta de cobro emitida antes de liquidar o abonar; Liquidar muestra icono atenuado, cursor de indisponibilidad y el motivo; los ingresos internos conservan su flujo. Incluye historial por registro con fecha, autor y consulta de versiones.',
        'Expone la utilidad y los movimientos que la explican.',
        ['/panel/accounting', '/panel/accounting/incomes', '/panel/accounting/expenses'],
        { icon: 'dashboard', stage: 'Resultados' }),
      feature('panel-service-revenue', 'Seguir servicios y cobros',
        'Relaciona hosting, recurrentes, publicidad y cuentas de cobro. La preparación de cuentas reutiliza nombre, identificación, correo, contacto y dirección del cliente y permite guardar cambios en su ficha. Los cobros de proyecto muestran las selecciones de contrato u hosting también desde Ingresos y explican el dato faltante. Permiten registrar un contrato existente desde el cobro sin copiarlo. Requieren contrato con otrosí opcional u hosting exclusivo y conservan sus snapshots y PDF; los históricos esperan asociación administrativa. Muestra base, IVA y total coherentes en el PDF y el correo, e incluye historial por registro con fecha, autor y consulta de versiones.',
        'Anticipa obligaciones y mantiene trazabilidad sobre lo facturable.',
        ['/panel/accounting/hostings', '/panel/accounting/recurring', '/panel/accounting/ads', '/panel/accounting/collections'],
        { icon: 'refresh', stage: 'Proyección' }),
      feature('panel-billing-context', 'Asociar y conciliar cobros de proyecto',
        'Asocia cada cuenta a un contrato con otrosí opcional o al único hosting; inventaría fuentes y vincula evidencias con preview, motivo y versión.',
        'Preserva historia financiera, PDF y automatismos sin elegir equivalencias por texto o importe.',
        ['/panel/accounting/collection-context/:id', '/panel/accounting/project-hosting/:id'],
        { icon: 'file', stage: 'Control' }),
      feature('panel-cash-credit', 'Controlar caja y crédito',
        'Reúne bolsillo, tarjetas y extractos mensuales. El saldo total del bolsillo se puede copiar con su formato visible aun con filtros, con confirmación o error local. Incluye historial por registro con fecha, autor y consulta de versiones.',
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
        'Permite activar, rotar y observar conectores especializados por dominio, incluidos Programa de Alianza y Módulos adicionales, con contratos personalizados, ajustes, documentos y Formalización privada con envío confirmado desde Propuestas, además de carga y sustitución de videos, y permisos explícitos para consultar secretos con confirmación por lectura.',
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
      feature('platform-project-ideas', 'Conservar ideas del cliente',
        'Registra texto con autor y fecha, corrige ideas propias conservando versiones y mantiene sugerencias archivadas.',
        'Permite recordar necesidades futuras sin incorporarlas al contrato vigente.', ['/platform/projects/:id/ideas'],
        { icon: 'file', actors: ['client', 'team'], stage: 'Proyecto' }),
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
    'Alcances contractuales, guías de validación, solicitudes y bugs reunidos por proyecto.',
    'Distingue lo aprobado y lo pendiente de revisión sin mezclarlo con la facturación.',
    [
      feature('platform-project-board', 'Validar las entregas del alcance',
        'Organiza contratos y otrosíes con fuentes documentales o archivos del paquete confirmado de aprobación, incluidos los personalizados. Seleccionar una copia privada no acredita firma y los archivos sin PDF conservan su formato original. Incluye alcances, fases, etapas y requerimientos con documentos y rondas de revisión. Las guías explican accesos y casos permitidos o bloqueados para roles acreditados por las fuentes. Una etapa totalmente aprobada habilita un correo con el registro público completo de conversaciones y decisiones, vista previa, constancia PDF y documentos opcionales e historial privado.',
        'El equipo revisa las fuentes y sus citas antes de aplicar borradores o enviar respuestas. El cliente conserva sus conformidades. El administrador decide cuándo enviar la constancia de cierre y debe revisar otra preparación para reenviarla; las guías y los correos conservan el alcance contractual. El administrador consulta los avisos persistidos de entrega y sólo reintenta un fallo confirmado después de revisar la copia exacta; los resultados en curso o desconocidos requieren revisión humana.',
        ['/platform/projects/:id/delivery', '/platform/projects/:id/board', '/platform/board'],
        { icon: 'board', actors: ['client', 'team'], stage: 'Seguimiento' }),
      feature('platform-bug-follow-up', 'Reportar y seguir bugs',
        'Permite reportar un bug general sin guías o conservar la publicación original de una entrega.',
        'El equipo prepara respuestas con fuentes y citas verificadas, confirma su revisión humana y conserva la procedencia privada. Sin contrato el alcance queda indeterminado; el cliente puede indicar que sigue fallando sin modificar aprobaciones.',
        ['/platform/projects/:id/bugs', '/platform/bugs'],
        { icon: 'bug', actors: ['client', 'team'], stage: 'Soporte' }),
      feature('platform-change-requests', 'Gestionar solicitudes de cambio',
        'Conserva el contexto contractual original y prepara respuestas con fuentes seleccionadas, citas verificadas y revisión humana. El cliente sólo recibe la respuesta y la conclusión de alcance, sin fuentes privadas.',
        'Permite crear una guía nueva y pendiente en una etapa editable del contrato aplicable, sin ampliar el alcance por comentarios.',
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
      feature('platform-client-secure-links', 'Compartir información confidencial con el equipo',
        'El cliente crea enlaces propios de texto o credenciales ligados a su proyecto; gestiona estados e historial sin leer el secreto guardado.',
        'Conserva el cifrado, el uso único y la auditoría. Reactivar rota la URL; corregir crea una sustitución tras revocar el anterior. Sin archivos, terceros ni accesos internos.',
        ['/platform/projects/:id/secure-links'],
        { icon: 'file', actors: ['client'], stage: 'Entrega' }),
      feature('platform-deliverable-library', 'Consultar entregables',
        'Permite revisar la biblioteca del proyecto y abrir el detalle de cada entrega. Muestra el paquete documental confirmado al aprobar la propuesta, con descargas autenticadas de copias privadas, separado de los adjuntos editables.',
        'Ofrece un punto estable para encontrar y validar los recursos recibidos, incluidos contratos, otrosíes y anexos legales. Las descargas autenticadas conservan el archivo actual o la versión elegida y explican los fallos sin cerrar su detalle.',
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
        'Lista los proyectos con hosting y muestra su único contexto, suscripción, pagos, ciclos y fuentes explícitamente reconciliadas.',
        'Ayuda al cliente a entender obligaciones, cobertura y continuidad del servicio.',
        ['/platform/projects/:id/payments', '/platform/payments'],
        { icon: 'credit-card', actors: ['client', 'team'], stage: 'Cobro' }),
      feature('platform-collection-accounts', 'Consultar cuentas de cobro',
        'Lista las cuentas emitidas del cliente y de cada proyecto, agrupadas y filtrables por contrato, otrosí, hosting o pendiente de asociar; abre detalle, estado e instrucciones de pago.',
        'Conserva el soporte financiero y permite descargar el PDF emitido con aislamiento del cliente en servidor.',
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
    'Editor interno y exposición explícita de URLs y accesos al cliente por proyecto y campo.',
    'Comparte únicamente los datos habilitados y revoca permisos cuando cambian sus fuentes o el propietario.',
    [
      feature('platform-project-access', 'Abrir accesos operativos',
        'El equipo administra datos y una matriz de visibilidad por ambiente; el cliente recibe URLs autorizadas y revelación puntual de credenciales, sin notas internas ni repositorio. Conserva el enlace global anterior.',
        'Permite llegar a entornos autorizados sin divulgar otros campos ni ocultar hosting, cobros o entregas.',
        ['/platform/projects/:id/access', '/platform/access'],
        { icon: 'key', actors: ['client', 'team'], stage: 'Administración' }),
    ],
    { icon: 'key', actors: ['client', 'team'], stage: 'Administración' },
  ),
]

const publicCapabilities = [
  capability(
    'public-brand-acquisition', 'Marca y captación',
    'Páginas que presentan la empresa, sus servicios y los caminos para iniciar una conversación.',
    'Convierte una primera visita en confianza y en una oportunidad comercial.',
    [
      feature('public-brand-entry', 'Descubrir ProjectApp',
        'Reúne la portada, landings especializadas, la historia de la empresa y la página del producto Waiter.',
        'Permite que cada necesidad encuentre una explicación relevante.',
        ['/', '/landing-apps', '/landing-software', '/landing-web-design', '/about-us', '/waiter'],
        { icon: 'dashboard', actors: ['visitor'], stage: 'Descubrimiento' }),
      feature('public-contact', 'Iniciar una conversación',
        'Presenta el formulario de contacto con los datos de la empresa y confirma la recepción de la solicitud.',
        'Reduce la distancia entre interés y una conversación comercial.',
        ['/contact', '/contact-success'],
        { icon: 'mail', actors: ['visitor'], stage: 'Conversión' }),
      feature('public-trust-pages', 'Consultar información institucional',
        'Incluye políticas, términos, las páginas legales de Waiter (privacidad, condiciones y eliminación de datos) y el manejo de rutas no encontradas.',
        'Sostiene transparencia, la verificación de Meta para WhatsApp y una salida clara ante enlaces incorrectos.',
        ['/privacy-policy', '/terms-and-conditions', '/waiter/privacy', '/waiter/terms', '/waiter/data-deletion', '/:slug*'],
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
        'Presenta selector ES/EN, tarjetas, lista, acordeón, tema local, guía, video de 60 segundos con voz latinoamericana y subtítulos y controles flotantes para PDF sin precios y compartir la selección. El video inicia manualmente, se pausa al salir y no se reanuda al volver.',
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
        'Presenta dos opciones de alianza, ocho condiciones con exclusividad conceptual y paquete mensual de horas sólo a cinco años, reglas expandibles, tema local, guía, video de 60 segundos con voz latinoamericana y subtítulos, PDF y un diálogo para compartir el programa. El video inicia manualmente, se pausa al salir y no se reanuda al volver.',
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
        'Presenta alcance, inversión, condiciones y acciones de respuesta. Aceptar deja la vinculación al proyecto pendiente de revisión interna, sin crear proyectos o clientes automáticamente. La portada incluye una guía y accesos al catálogo y al Programa de alianza en otra pestaña; desde Inversión el cliente explora módulos con video y guarda intereses pendientes, sin cambiar las condiciones. Los PDFs comercial y técnico se descargan mientras la propuesta está vigente; si venció, explica el bloqueo, y permite reintentar ante fallos de descarga. Cuando existe, incorpora el video personalizado después de la bienvenida en Vista Ejecutiva y Propuesta Completa. Un video general en español explica las cuatro opciones cuando todas están disponibles y los controles global e individual lo permiten; admite el predeterminado o un archivo cargado, inicia manualmente y se pausa al salir sin reanudarse al volver.',
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
  capability(
    'public-secure-link-experience', 'Enlaces seguros',
    'Intercambio de información sensible entre clientes y equipo mediante enlaces de un solo uso.',
    'Protege credenciales y datos confidenciales fuera del correo y del chat.',
    [
      feature('public-secure-links', 'Enviar y abrir información sensible',
        'El cliente empieza con Mensaje confidencial o elige otra plantilla desde un dropdown; Personalizado muestra su nombre y Más detalles agrupa campos opcionales. La URL se genera automáticamente y sólo el equipo puede abrirla. También abre una sola vez los enlaces que recibe de ProjectApp.',
        'Da un canal seguro y simple para compartir accesos durante el proyecto.',
        ['/secure-link', '/secure-link/view'],
        { icon: 'key', actors: ['client'], stage: 'Colaboración' }),
    ],
    { icon: 'key', actors: ['client'], stage: 'Colaboración' },
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
      ['public-site', 'public-additional-modules', 'public-financing', 'public-proposals', 'public-diagnostics', 'public-secure-links'], publicCapabilities,
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
