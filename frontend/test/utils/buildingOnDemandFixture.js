const copy = {
  es: {
    seo: {
      title: 'Building on Demand | Tu célula Scrum disponible',
      description: 'Haz evolucionar tu producto con una célula Scrum y una bolsa mensual de horas que incluye servidor, mantenimiento y soporte.',
    },
    hero: {
      eyebrow: 'Building on Demand',
      title: 'Una célula Scrum para hacer evolucionar tu producto',
      subtitle: 'Alquila horas de una célula de siete personas y úsalas cada mes en lo que tu producto necesita.',
      positioning: 'Una suscripción de IA te da capacidad de producción. Una célula te da criterio.',
      note: 'Una bolsa mensual de horas disponibles, con el acompañamiento de una célula compartida.',
    },
    cell: {
      title: 'La célula que acompaña tu producto',
      summary: 'La célula reúne siete personas que trabajan juntas sobre tu producto. Cada rol aporta una mirada distinta para que los cambios lleguen bien pensados, construidos y probados.',
      note: 'La célula siempre es la misma. Cada nivel define cuántas horas compras y qué roles puedes usar.',
      roles: [
        { id: 'developers', title: 'Dos desarrolladores', summary: 'Construyen las mejoras que necesita tu producto.' },
        { id: 'project-lead', title: 'Líder de proyecto', summary: 'Ordena las prioridades y acompaña las entregas.' },
        { id: 'designer', title: 'Diseñador', summary: 'Da claridad a la experiencia y a las pantallas.' },
        { id: 'architect', title: 'Arquitecto de desarrollo', summary: 'Cuida la arquitectura y también cubre DevOps.' },
        { id: 'scrum-master', title: 'Scrum Master', summary: 'Ayuda a sostener el ritmo de trabajo.' },
        { id: 'qa', title: 'QA', summary: 'Verifica la calidad de cada entrega.' },
      ],
    },
    fit: {
      title: '¿Es para tu producto?',
      summary: 'Una forma de avanzar por tareas con criterio y acompañamiento.',
      good_for: [
        { id: 'existing-product', title: 'Evolucionar un producto', summary: 'Mejorar productos o herramientas que ya existen.' },
        { id: 'organize-tools', title: 'Poner orden', summary: 'Organizar herramientas que crecieron sin estructura.' },
        { id: 'discovery', title: 'Explorar antes de construir', summary: 'Levantar requerimientos, diseñar y revisar la arquitectura.' },
      ],
      not_for: [
        { id: 'new-product', title: 'Un producto desde cero', summary: 'Eso requiere un proyecto completo de desarrollo.' },
        { id: 'dedicated-team', title: 'Un equipo de planta', summary: 'La célula es compartida, con horas disponibles cada mes.' },
        { id: 'fixed-scope', title: 'Un alcance y fecha cerrados', summary: 'El trabajo se acuerda y estima tarea por tarea.' },
      ],
    },
    tiers: {
      title: 'Elige el ritmo de tu producto',
      summary: 'Cada nivel incluye una bolsa mensual de horas y acceso a los roles que necesitas.',
      items: [
        {
          id: 'starter', name: 'Starter', badge: 'Para empezar', pace_label: 'Medio tiempo',
          pace_summary: 'Avanza a un ritmo constante con tareas claras.',
          ideal_for: 'Ya sabes qué necesitas y quieres que se ejecute bien.',
          roles: ['Desarrollo', 'Líder de proyecto', 'QA en cada entrega'],
          highlights: ['Cadencia asíncrona con una ceremonia cada dos semanas', 'Una persona solicitante', 'Una tarea en curso', 'Tiempo de respuesta objetivo: 48 horas hábiles.'],
          cta_label: 'Quiero Starter',
        },
        {
          id: 'business', name: 'Business', badge: 'Recomendado', pace_label: 'Tiempo completo',
          pace_summary: 'Avanza con criterio para ordenar y mejorar tu producto.',
          ideal_for: 'Tus herramientas crecieron rápido y necesitas arquitecto y diseñador para poner orden.',
          roles: ['Todo lo de Starter', 'Diseñador', 'Arquitecto', 'Levantamiento de requerimientos', 'Deploy a producción'],
          highlights: ['Sprint semanal con demo', 'Hasta tres personas solicitantes', 'Dos tareas en curso', 'Tiempo de respuesta objetivo: 24 horas hábiles.'],
          cta_label: 'Quiero Business',
        },
        {
          id: 'enterprise', name: 'Enterprise', badge: 'Ritmo sostenido', pace_label: 'Sin pausa',
          pace_summary: 'Sostén el ritmo de evolución de tu producto.',
          ideal_for: 'Tu equipo necesita operar y mejorar con acompañamiento continuo.',
          roles: ['Todo lo de Business', 'Scrum Master dedicado', 'DevOps continuo', 'Prioridad de atención'],
          highlights: ['Sprint de dos semanas con canal dedicado', 'Todo tu equipo puede solicitar', 'Tres tareas en curso', 'Tiempo de respuesta objetivo: 4 horas, con prioridad.'],
          cta_label: 'Quiero Enterprise',
        },
      ],
    },
    terms: {
      title: 'Elige la duración', summary: 'Puedes anticipar varios meses para obtener un descuento.',
      note: 'Aunque anticipes varios meses, la bolsa se reanuda cada mes y no se acumula.',
      items: [{ id: 'monthly', label: 'Mensual' }, { id: 'quarterly', label: '3 meses' }, { id: 'semiannual', label: '6 meses' }, { id: 'nine-month', label: '9 meses' }],
    },
    bag: {
      title: 'Así funciona tu bolsa de horas', summary: 'Planeamos las tareas del mes contigo.',
      note: 'Cada tarea empieza con una estimación que tú apruebas.',
      rules: [
        { id: 'monthly-renewal', title: 'Se reanuda cada mes', summary: 'Cada ciclo trae una nueva bolsa de horas.' },
        { id: 'no-rollover', title: 'No se acumula', summary: 'Las horas que no uses vencen al terminar el mes.' },
        { id: 'no-transfer', title: 'No se transfiere', summary: 'La bolsa no se transfiere a otra empresa, persona o proyecto.' },
        { id: 'approved-estimate', title: 'Tú apruebas la estimación', summary: 'Se consume según la estimación aprobada antes de cada tarea.' },
        { id: 'shared-cell', title: 'Una célula compartida', summary: 'No es contratación de planta ni de tiempo completo.' },
        { id: 'work-in-progress', title: 'Un ritmo por nivel', summary: 'Cada nivel define cuántas tareas pueden avanzar a la vez.' },
        { id: 'task-by-task', title: 'Tarea por tarea', summary: 'Sin alcance fijo ni fecha de entrega comprometida.' },
      ],
    },
    estimator: {
      title: '¿Cabe en tu bolsa?', summary: 'Selecciona tareas para conocer un rango de referencia.',
      description_label: 'Cuéntanos qué necesitas', description_placeholder: 'Describe la mejora que quieres hacer en tu producto.',
      disclaimer: 'Estas horas son una referencia. Antes de empezar usamos la calculadora de requerimientos para hacer una estimación formal que tú apruebas. El trabajo XL se divide.',
      tasks: [
        { id: 'requirements-session', label: 'Sesión de requerimientos', hint: 'Aclarar objetivos y necesidades.' },
        { id: 'screen-design', label: 'Diseño de pantalla', hint: 'Definir una experiencia clara.' },
        { id: 'small-change', label: 'Cambio pequeño', hint: 'Ajustar algo que ya existe.' },
        { id: 'component', label: 'Componente', hint: 'Crear una pieza reutilizable.' },
        { id: 'feature', label: 'Funcionalidad', hint: 'Construir una mejora de alcance medio.' },
        { id: 'large-feature', label: 'Funcionalidad grande', hint: 'Abordar una mejora de mayor alcance.' },
        { id: 'architecture-review', label: 'Revisión de arquitectura', hint: 'Ordenar las bases técnicas del producto.' },
        { id: 'production-deploy', label: 'Deploy a producción', hint: 'Publicar una entrega con cuidado.' },
        { id: 'continuous-devops', label: 'DevOps continuo', hint: 'Acompañar la operación del producto.' },
      ],
    },
    hosting: {
      title: 'Servidor, mantenimiento y soporte incluidos',
      summary: 'Cada nivel incluye un servidor VPS, mantenimiento y soporte.',
      note: 'El mantenimiento preventivo y la atención de incidentes del servidor no consumen la bolsa.',
      features: [
        { id: 'processors', title: 'Procesadores AMD EPYC', summary: 'Capacidad para las necesidades de tu producto.' },
        { id: 'storage', title: 'Disco NVMe', summary: 'Almacenamiento rápido para tu aplicación.' },
        { id: 'backups', title: 'Copias semanales', summary: 'Respaldo periódico de los datos.' },
        { id: 'firewall', title: 'Firewall gestionado', summary: 'Protección del acceso al servidor.' },
        { id: 'network', title: 'Red de 1 Gbps', summary: 'Conectividad para la operación diaria.' },
        { id: 'dedicated-ip', title: 'IP dedicada', summary: 'Una dirección propia para tu servidor.' },
        { id: 'ddos', title: 'Protección contra DDoS', summary: 'Protección frente a ataques de tráfico.' },
      ],
    },
    faq: {
      title: 'Preguntas frecuentes',
      items: [
        { id: 'unused-hours', question: '¿Qué pasa si no uso mis horas?', answer: 'Vencen cada mes. Planeemos el mes, como cuando organizas tus visitas al gimnasio.' },
        { id: 'hiring', question: '¿Esto es contratación?', answer: 'No. Accedes a una célula compartida mediante una bolsa mensual de horas.' },
        { id: 'does-not-fit', question: '¿Qué pasa si una tarea no cabe?', answer: 'La dividimos, espera al mes siguiente o subes de nivel. No hay horas extra automáticas.' },
        { id: 'change-tier', question: '¿Puedo cambiar de nivel?', answer: 'Puedes subir desde el siguiente ciclo o bajar avisando con anticipación.' },
        { id: 'ownership', question: '¿De quién es lo entregado?', answer: 'Lo que se entrega y se paga es tuyo.' },
        { id: 'term-ending', question: '¿Qué pasa al terminar una duración?', answer: 'Continúa de forma mensual hasta que elijas otra duración.' },
        { id: 'delivery-date', question: '¿Hay un alcance o una fecha fija?', answer: 'No. Cada tarea tiene una estimación de referencia antes de comenzar.' },
      ],
    },
    cta: {
      title: 'Hablemos de tu producto', body: 'Cuéntanos qué necesitas y encontremos el nivel que te ayuda a avanzar.',
      button_label: 'Hablar por WhatsApp', whatsapp_url: 'https://wa.me/573238122373?text=Hola%2C%20quiero%20conocer%20Building%20on%20Demand',
    },
    legal: { disclaimer: 'Esta presentación es informativa. Aplican las condiciones acordadas y firmadas; los valores pueden cambiar.' },
  },
  en: {
    seo: {
      title: 'Building on Demand | Your available Scrum cell',
      description: 'Evolve your product with a Scrum cell and a monthly bag of hours that includes a server, maintenance and support.',
    },
    hero: {
      eyebrow: 'Building on Demand', title: 'A Scrum cell to help your product evolve',
      subtitle: 'Rent hours from a seven-person cell and use them each month on what your product needs.',
      positioning: 'An AI subscription gives you production capacity. A cell gives you judgment.',
      note: 'A monthly bag of available hours, supported by a shared cell.',
    },
    cell: {
      title: 'The cell supporting your product', summary: 'The cell brings together seven people who work together on your product. Each role adds a different perspective so changes arrive thoughtfully designed, built and tested.',
      note: 'The cell stays the same. Each tier defines how many hours you buy and which roles you can use.',
      roles: [
        { id: 'developers', title: 'Two developers', summary: 'Build the improvements your product needs.' },
        { id: 'project-lead', title: 'Project lead', summary: 'Organizes priorities and supports delivery.' },
        { id: 'designer', title: 'Designer', summary: 'Brings clarity to the experience and screens.' },
        { id: 'architect', title: 'Development architect', summary: 'Maintains the architecture and also covers DevOps.' },
        { id: 'scrum-master', title: 'Scrum Master', summary: 'Helps sustain the working pace.' },
        { id: 'qa', title: 'QA', summary: 'Checks the quality of each delivery.' },
      ],
    },
    fit: {
      title: 'Is this for your product?', summary: 'Move forward task by task with judgment and support.',
      good_for: [
        { id: 'existing-product', title: 'Evolve a product', summary: 'Improve products or tools that already exist.' },
        { id: 'organize-tools', title: 'Bring order', summary: 'Organize tools that grew without structure.' },
        { id: 'discovery', title: 'Explore before building', summary: 'Gather requirements, design and review architecture.' },
      ],
      not_for: [
        { id: 'new-product', title: 'A product from scratch', summary: 'That needs a complete development project.' },
        { id: 'dedicated-team', title: 'A permanent team', summary: 'The cell is shared, with hours available each month.' },
        { id: 'fixed-scope', title: 'A fixed scope and date', summary: 'Work is agreed and estimated task by task.' },
      ],
    },
    tiers: {
      title: 'Choose your product pace', summary: 'Each tier includes a monthly bag of hours and access to the roles you need.',
      items: [
        {
          id: 'starter', name: 'Starter', badge: 'Get started', pace_label: 'Part time',
          pace_summary: 'Move at a steady pace with clear tasks.', ideal_for: 'You know what you need and want it executed well.',
          roles: ['Development', 'Project lead', 'QA for each delivery'],
          highlights: ['Asynchronous cadence with a ceremony every two weeks', 'One requester', 'One task in progress', 'Target response time: 48 business hours.'], cta_label: 'I want Starter',
        },
        {
          id: 'business', name: 'Business', badge: 'Recommended', pace_label: 'Full time',
          pace_summary: 'Move with judgment to organize and improve your product.',
          ideal_for: 'Your tools grew quickly and need an architect and designer to bring order.',
          roles: ['Everything in Starter', 'Designer', 'Architect', 'Requirements sessions', 'Production deployment'],
          highlights: ['Weekly sprint with a demo', 'Up to three requesters', 'Two tasks in progress', 'Target response time: 24 business hours.'], cta_label: 'I want Business',
        },
        {
          id: 'enterprise', name: 'Enterprise', badge: 'Sustained pace', pace_label: 'Nonstop',
          pace_summary: 'Sustain the pace of your product evolution.', ideal_for: 'Your team needs ongoing support to operate and improve.',
          roles: ['Everything in Business', 'Dedicated Scrum Master', 'Continuous DevOps', 'Priority support'],
          highlights: ['Two-week sprint with a dedicated channel', 'Your whole team can request', 'Three tasks in progress', 'Target response time: 4 hours, with priority.'], cta_label: 'I want Enterprise',
        },
      ],
    },
    terms: {
      title: 'Choose the term', summary: 'Prepay several months to receive a discount.',
      note: 'Even when you prepay several months, the bag renews every month and does not roll over.',
      items: [{ id: 'monthly', label: 'Monthly' }, { id: 'quarterly', label: '3 months' }, { id: 'semiannual', label: '6 months' }, { id: 'nine-month', label: '9 months' }],
    },
    bag: {
      title: 'How your bag of hours works', summary: 'We plan the monthly tasks with you.', note: 'Every task starts with an estimate you approve.',
      rules: [
        { id: 'monthly-renewal', title: 'Renews each month', summary: 'Every cycle brings a new bag of hours.' },
        { id: 'no-rollover', title: 'No rollover', summary: 'Unused hours expire at the end of the month.' },
        { id: 'no-transfer', title: 'No transfers', summary: 'The bag cannot transfer to another company, person or project.' },
        { id: 'approved-estimate', title: 'You approve the estimate', summary: 'Hours are used according to the estimate approved before each task.' },
        { id: 'shared-cell', title: 'A shared cell', summary: 'This is not permanent or full-time hiring.' },
        { id: 'work-in-progress', title: 'A pace per tier', summary: 'Each tier defines how many tasks can progress at once.' },
        { id: 'task-by-task', title: 'Task by task', summary: 'There is no fixed scope or committed delivery date.' },
      ],
    },
    estimator: {
      title: 'Does it fit your bag?', summary: 'Choose tasks to get a reference range.',
      description_label: 'Tell us what you need', description_placeholder: 'Describe the improvement you want to make to your product.',
      disclaimer: 'These hours are a reference. Before starting, we use the requirements calculator for a formal estimate you approve. XL work is split.',
      tasks: [
        { id: 'requirements-session', label: 'Requirements session', hint: 'Clarify goals and needs.' },
        { id: 'screen-design', label: 'Screen design', hint: 'Define a clear experience.' },
        { id: 'small-change', label: 'Small change', hint: 'Adjust something that already exists.' },
        { id: 'component', label: 'Component', hint: 'Create a reusable piece.' },
        { id: 'feature', label: 'Feature', hint: 'Build a medium-scope improvement.' },
        { id: 'large-feature', label: 'Large feature', hint: 'Address a larger improvement.' },
        { id: 'architecture-review', label: 'Architecture review', hint: 'Organize the product technical foundations.' },
        { id: 'production-deploy', label: 'Production deployment', hint: 'Publish a delivery with care.' },
        { id: 'continuous-devops', label: 'Continuous DevOps', hint: 'Support your product operations.' },
      ],
    },
    hosting: {
      title: 'Server, maintenance and support included', summary: 'Every tier includes a VPS server, maintenance and support.',
      note: 'Preventive maintenance and server incident support do not consume your bag.',
      features: [
        { id: 'processors', title: 'AMD EPYC processors', summary: 'Capacity for your product needs.' },
        { id: 'storage', title: 'NVMe storage', summary: 'Fast storage for your application.' },
        { id: 'backups', title: 'Weekly backups', summary: 'Regular backups of your data.' },
        { id: 'firewall', title: 'Managed firewall', summary: 'Protection for access to the server.' },
        { id: 'network', title: '1 Gbps network', summary: 'Connectivity for daily operations.' },
        { id: 'dedicated-ip', title: 'Dedicated IP', summary: 'Your server has its own address.' },
        { id: 'ddos', title: 'DDoS protection', summary: 'Protection from traffic attacks.' },
      ],
    },
    faq: {
      title: 'Frequently asked questions',
      items: [
        { id: 'unused-hours', question: 'What happens if I do not use my hours?', answer: 'They expire each month. Plan your month, just as you plan visits to a gym.' },
        { id: 'hiring', question: 'Is this hiring?', answer: 'No. You access a shared cell through a monthly bag of hours.' },
        { id: 'does-not-fit', question: 'What if a task does not fit?', answer: 'We split it, wait until next month or move to a higher tier. There are no automatic extra hours.' },
        { id: 'change-tier', question: 'Can I change tiers?', answer: 'Move up from the next cycle or move down with advance notice.' },
        { id: 'ownership', question: 'Who owns the delivered work?', answer: 'Work that is delivered and paid for is yours.' },
        { id: 'term-ending', question: 'What happens when a term ends?', answer: 'It continues monthly until you choose another term.' },
        { id: 'delivery-date', question: 'Is there a fixed scope or date?', answer: 'No. Each task has a reference estimate before starting.' },
      ],
    },
    cta: {
      title: 'Let us talk about your product', body: 'Tell us what you need and find the tier that helps you move forward.',
      button_label: 'Talk on WhatsApp', whatsapp_url: 'https://wa.me/573238122373?text=Hello%2C%20I%20want%20to%20learn%20about%20Building%20on%20Demand',
    },
    legal: { disclaimer: 'This presentation is informative. Agreed and signed conditions apply; values may change.' },
  },
}

const tierNumbers = [
  {
    id: 'starter', recommended: false, monthly_price: 1800000, daily_hours: 4, bag_hours: 96,
    server: { vcpu: 1, ram_gb: 4, disk_gb: 50, transfer_tb: 4 },
    prices: [
      { term: 'monthly', months: 1, discount_percent: 0, monthly_price: 1800000, total: 1800000, savings: 0 },
      { term: 'quarterly', months: 3, discount_percent: 5, monthly_price: 1710000, total: 5130000, savings: 270000 },
      { term: 'semiannual', months: 6, discount_percent: 10, monthly_price: 1620000, total: 9720000, savings: 1080000 },
      { term: 'nine-month', months: 9, discount_percent: 15, monthly_price: 1530000, total: 13770000, savings: 2430000 },
    ],
  },
  {
    id: 'business', recommended: true, monthly_price: 4200000, daily_hours: 8, bag_hours: 192,
    server: { vcpu: 4, ram_gb: 16, disk_gb: 200, transfer_tb: 16 },
    prices: [
      { term: 'monthly', months: 1, discount_percent: 0, monthly_price: 4200000, total: 4200000, savings: 0 },
      { term: 'quarterly', months: 3, discount_percent: 10, monthly_price: 3780000, total: 11340000, savings: 1260000 },
      { term: 'semiannual', months: 6, discount_percent: 15, monthly_price: 3570000, total: 21420000, savings: 3780000 },
      { term: 'nine-month', months: 9, discount_percent: 20, monthly_price: 3360000, total: 30240000, savings: 7560000 },
    ],
  },
  {
    id: 'enterprise', recommended: false, monthly_price: 9600000, daily_hours: 12, bag_hours: 288,
    server: { vcpu: 8, ram_gb: 32, disk_gb: 400, transfer_tb: 32 },
    prices: [
      { term: 'monthly', months: 1, discount_percent: 0, monthly_price: 9600000, total: 9600000, savings: 0 },
      { term: 'quarterly', months: 3, discount_percent: 15, monthly_price: 8160000, total: 24480000, savings: 4320000 },
      { term: 'semiannual', months: 6, discount_percent: 20, monthly_price: 7680000, total: 46080000, savings: 11520000 },
      { term: 'nine-month', months: 9, discount_percent: 25, monthly_price: 7200000, total: 64800000, savings: 21600000 },
    ],
  },
]

const taskNumbers = [
  { id: 'requirements-session', size: 's', min_tier: 'business' },
  { id: 'screen-design', size: 's', min_tier: 'business' },
  { id: 'small-change', size: 'xs', min_tier: 'starter' },
  { id: 'component', size: 's', min_tier: 'starter' },
  { id: 'feature', size: 'm', min_tier: 'starter' },
  { id: 'large-feature', size: 'l', min_tier: 'starter' },
  { id: 'architecture-review', size: 'm', min_tier: 'business' },
  { id: 'production-deploy', size: 'xs', min_tier: 'business' },
  { id: 'continuous-devops', size: 'm', min_tier: 'enterprise' },
]

export function createBuildingOnDemandProgram(language = 'es') {
  const lang = String(language).startsWith('en') ? 'en' : 'es'
  const localized = copy[lang]
  const payload = {
    language: lang,
    version: 1,
    updated_at: '2026-10-10T00:00:00Z',
    canonical_path: `/${lang === 'en' ? 'en-us' : 'es-co'}/building-on-demand`,
    alternate_path: `/${lang === 'en' ? 'es-co' : 'en-us'}/building-on-demand`,
    pdf_path: `/api/building-on-demand/public/pdf/?lang=${lang}`,
    ...localized,
    tiers: {
      ...localized.tiers,
      items: localized.tiers.items.map((tier, index) => ({ ...tier, ...tierNumbers[index] })),
    },
    terms: {
      ...localized.terms,
      items: localized.terms.items.map((term, index) => ({ ...term, months: [1, 3, 6, 9][index] })),
    },
    estimator: {
      ...localized.estimator,
      sizes: [
        { id: 'xs', hours_min: 2, hours_max: 7 },
        { id: 's', hours_min: 7, hours_max: 20 },
        { id: 'm', hours_min: 20, hours_max: 50 },
        { id: 'l', hours_min: 55, hours_max: 90 },
      ],
      tasks: localized.estimator.tasks.map((task, index) => ({ ...task, ...taskNumbers[index] })),
    },
    offer: { currency: 'COP', prices_include_vat: false, days_per_week: 6, weeks_per_month: 4, recommended_tier: 'business' },
    contact: { whatsapp_base_url: 'https://wa.me/573238122373' },
  }

  return JSON.parse(JSON.stringify(payload))
}
