/** Seed copy from migration 0291; prices and economics are pinned to contract.md, not calculated by the browser. */
export const BUILDING_ON_DEMAND_GUIDE_SEEN_KEY = 'projectapp-building-on-demand-guide-seen';
const updatedAt = '2026-10-10T15:00:00Z';
const author = 'Equipo ProjectApp';
const contractTitle = 'Contrato de alquiler de célula — Building on Demand';

const content = {
  "es": {
    "seo": {"title": "Building on Demand | ProjectApp", "description": "Haz evolucionar tu producto con una célula Scrum compartida. Elige tu bolsa mensual de horas y úsala en desarrollo, diseño, arquitectura y operación."},
    "hero": {
      "eyebrow": "Building on Demand",
      "title": "Una célula Scrum completa para hacer evolucionar tu producto",
      "subtitle": "Alquilas horas de una célula de siete personas y las usas cada mes en lo que tu producto necesita. Tú decides las prioridades; nosotros aportamos el equipo y el criterio para avanzar.",
      "positioning": "Una suscripción de IA te da capacidad de producción. Una célula te da criterio.",
      "note": "Es una bolsa mensual de horas disponibles de una célula compartida. No es contratación de planta ni un equipo dedicado de tiempo completo.",
    },
    "cell": {
      "title": "Un equipo completo, sin tener que contratarlo",
      "summary": "La célula reúne siete personas que trabajan juntas sobre tu producto. Cada rol aporta una mirada distinta para que los cambios lleguen bien pensados, construidos y probados.",
      "note": "La célula siempre es la misma. El nivel que eliges define cuántas horas compras y qué roles puedes usar.",
      "roles": [
        {"id": "developers", "title": "Dos desarrolladores", "summary": "Construyen y ajustan las funciones que tu producto necesita, con código que pueda seguir creciendo."},
        {"id": "project-lead", "title": "Líder de proyecto", "summary": "Organiza las prioridades, resuelve dudas contigo y mantiene visible el avance de cada tarea."},
        {"id": "designer", "title": "Diseñador", "summary": "Hace que las pantallas y los recorridos tengan sentido para las personas que los usan."},
        {"id": "architect", "title": "Arquitecto de desarrollo y DevOps", "summary": "Da estructura a la solución y cuida cómo se despliega y opera en producción."},
        {"id": "scrum-master", "title": "Scrum Master", "summary": "Cuida el ritmo del equipo, facilita las conversaciones y ayuda a quitar obstáculos."},
        {"id": "qa", "title": "QA", "summary": "Prueba cada entrega con criterios claros para detectar problemas antes de que lleguen a tus usuarios."},
      ],
    },
    "fit": {
      "title": "Para productos que necesitan seguir avanzando",
      "summary": "Si ya tienes un producto o herramientas en uso, puedes dedicar la bolsa a lo que más valor aporte cada mes. También puedes usarla para aclarar lo que necesitas antes de empezar un proyecto.",
      "good_for": [
        {"id": "existing-product", "title": "Evolucionar lo que ya existe", "summary": "Mejora tu producto o tus herramientas con cambios, funciones e integraciones según tus prioridades."},
        {"id": "product-structure", "title": "Poner orden y traer el estado del arte", "summary": "Dale estructura, diseño y criterio técnico a herramientas que crecieron rápido y hoy son difíciles de mantener."},
        {"id": "discovery", "title": "Entender antes de construir", "summary": "Levanta requerimientos, diseña los recorridos y define la arquitectura antes de iniciar un proyecto."},
      ],
      "not_for": [
        {"id": "new-product", "title": "Un producto nuevo desde cero", "summary": "Construir un producto completo desde cero corresponde a un proyecto de desarrollo con su propio alcance."},
        {"id": "dedicated-team", "title": "Contratar un equipo exclusivo", "summary": "La célula es compartida. Este programa no reemplaza una contratación de tiempo completo para tu empresa."},
        {"id": "fixed-delivery", "title": "Un alcance cerrado con fecha comprometida", "summary": "Avanzas por tareas priorizadas y estimadas. La bolsa no promete un alcance fijo ni una fecha de entrega comprometida."},
      ],
    },
    "tiers": {
      "title": "Elige el ritmo al que quieres avanzar",
      "summary": "La misma célula acompaña tu producto. Cada nivel amplía tu bolsa y los roles a los que puedes acudir para resolver lo que viene.",
      "items": [
        {
          "id": "starter",
          "name": "Starter",
          "badge": "Para avanzar con foco",
          "pace_label": "Medio tiempo",
          "pace_summary": "Avanzas a un ritmo tranquilo y constante, con una prioridad clara a la vez.",
          "ideal_for": "Ya sabes qué necesitas y quieres que se ejecute bien. Ideal para ajustes y funciones de un producto que ya está en marcha.",
          "roles": ["Desarrollo.", "Líder de proyecto.", "QA en cada entrega."],
          "highlights": ["Trabajo asíncrono con una ceremonia cada dos semanas.", "Una persona solicita y prioriza el trabajo.", "Una tarea en curso a la vez.", "Tiempo de respuesta objetivo: 48 horas hábiles."],
          "cta_label": "Hablemos de Starter",
        },
        {
          "id": "business",
          "name": "Business",
          "badge": "Recomendado",
          "pace_label": "Tiempo completo",
          "pace_summary": "Avanzas cada semana con espacio para definir, diseñar y construir los siguientes pasos de tu producto.",
          "ideal_for": "Construiste herramientas rápido, incluso con IA, y ahora están desordenadas y lejos del estado del arte. Necesitas un arquitecto y un diseñador para darles estructura y una buena experiencia.",
          "roles": ["Todo lo de Starter.", "Diseñador.", "Arquitecto de desarrollo.", "Sesiones de levantamiento de requerimientos.", "Deploy a producción."],
          "highlights": ["Sprint semanal con demo de los avances.", "Hasta tres personas pueden solicitar trabajo.", "Dos tareas en curso a la vez.", "Tiempo de respuesta objetivo: 24 horas hábiles."],
          "cta_label": "Hablemos de Business",
        },
        {
          "id": "enterprise",
          "name": "Enterprise",
          "badge": "Para un ritmo sostenido",
          "pace_label": "Sin pausa",
          "pace_summary": "Avanzas de forma sostenida con tu equipo, mientras evolucionas el producto y cuidas su operación.",
          "ideal_for": "Tu producto está en movimiento continuo y necesitas coordinar a más personas, mantener la operación y dar respuesta a prioridades frecuentes.",
          "roles": ["Todo lo de Business.", "Scrum Master dedicado.", "DevOps continuo.", "Prioridad de atención."],
          "highlights": ["Sprint de dos semanas con canal dedicado.", "Todo tu equipo puede solicitar trabajo.", "Tres tareas en curso a la vez.", "Tiempo de respuesta objetivo: 4 horas, con prioridad."],
          "cta_label": "Hablemos de Enterprise",
        },
      ],
    },
    "terms": {
      "title": "Elige cómo quieres darle continuidad",
      "summary": "Puedes empezar mes a mes o pagar por anticipado un plazo mayor. Cada nivel tiene sus condiciones para el plazo que elijas.",
      "note": "Aunque pagues varios meses por anticipado, la bolsa se renueva cada mes y las horas no se acumulan.",
      "items": [
        {"id": "monthly", "label": "Mensual"},
        {"id": "quarterly", "label": "3 meses"},
        {"id": "semiannual", "label": "6 meses"},
        {"id": "nine-month", "label": "9 meses"},
      ],
    },
    "bag": {
      "title": "Una bolsa mensual con reglas claras",
      "summary": "Planeamos contigo el mes y usamos las horas en tareas que hayas aprobado. Así sabes qué se va a hacer y cómo se consume la bolsa.",
      "note": "La bolsa define capacidad disponible. No compromete un alcance fijo ni una fecha de entrega.",
      "rules": [
        {"id": "monthly-reset", "title": "Se renueva cada mes", "summary": "Cada ciclo comienza con la bolsa de horas de tu nivel, incluso si pagaste varios meses por anticipado."},
        {"id": "no-rollover", "title": "Las horas no se acumulan", "summary": "Las horas que no uses vencen al terminar el mes. Planea tus prioridades para aprovecharlas."},
        {"id": "no-transfer", "title": "La bolsa no se transfiere", "summary": "Las horas corresponden al proyecto acordado. No pasan a otra empresa, persona o proyecto."},
        {"id": "approved-estimate", "title": "Apruebas antes de empezar", "summary": "Cada tarea consume las horas de la estimación que revisas y apruebas antes de que comencemos."},
        {"id": "shared-cell", "title": "Acceso a una célula compartida", "summary": "Compras horas disponibles y acceso a los roles de tu nivel. No es contratación de planta ni tiempo completo."},
        {"id": "work-in-progress", "title": "Un ritmo que podamos sostener", "summary": "Cada nivel define cuántas tareas pueden estar en curso a la vez. Las demás esperan en la lista de prioridades."},
        {"id": "flexible-scope", "title": "Prioridades que pueden cambiar", "summary": "No hay un alcance fijo ni una fecha de entrega comprometida. Revisamos las siguientes tareas contigo según la bolsa disponible."},
      ],
    },
    "estimator": {
      "title": "¿Cabe en tu bolsa?",
      "summary": "Explora las tareas que tu producto necesita y sus rangos de referencia. Te ayuda a preparar la conversación y a escoger un nivel.",
      "description_label": "Cuéntanos qué quieres hacer",
      "description_placeholder": "Por ejemplo: ordenar mis herramientas, mejorar una pantalla o integrar un servicio.",
      "disclaimer": "Las horas son una referencia. Antes de empezar cada tarea hacemos la estimación formal con la calculadora de requerimientos y tú la apruebas. El trabajo XL se divide en tareas más pequeñas.",
      "tasks": [
        {"id": "requirements-session", "label": "Sesión de requerimientos", "hint": "Aclara el problema, las personas que lo usan y lo que la tarea debe resolver."},
        {"id": "screen-design", "label": "Diseño de una pantalla", "hint": "Define el recorrido y la presentación de una pantalla antes de construirla."},
        {"id": "small-change", "label": "Cambio pequeño", "hint": "Ajusta un texto, una regla o un detalle de una función que ya existe."},
        {"id": "component", "label": "Componente", "hint": "Construye una pieza concreta que puedas usar dentro de tu producto."},
        {"id": "feature", "label": "Funcionalidad", "hint": "Agrega un recorrido o una capacidad definida a tu producto."},
        {"id": "large-feature", "label": "Funcionalidad grande", "hint": "Resuelve una capacidad más amplia que necesita varias piezas conectadas."},
        {"id": "architecture-review", "label": "Revisión de arquitectura", "hint": "Evalúa la estructura de tu solución y define cómo darle orden para crecer."},
        {"id": "production-deploy", "label": "Deploy a producción", "hint": "Prepara y publica un cambio aprobado en el entorno de producción."},
        {"id": "continuous-devops", "label": "DevOps continuo", "hint": "Acompaña la operación y mejora de forma sostenida los despliegues de tu producto."},
      ],
    },
    "hosting": {
      "title": "Tu producto también tiene dónde vivir",
      "summary": "Cada nivel incluye un servidor VPS, mantenimiento y soporte para que tu producto pueda operar en producción.",
      "note": "El mantenimiento preventivo y la atención de incidentes del servidor no consumen tu bolsa de horas.",
      "features": [
        {"id": "amd-epyc", "title": "Procesadores AMD EPYC", "summary": "Capacidad de procesamiento para acompañar la operación de tu producto."},
        {"id": "nvme-storage", "title": "Disco NVMe", "summary": "Almacenamiento rápido para los archivos y datos de tu aplicación."},
        {"id": "weekly-backups", "title": "Copias de seguridad semanales", "summary": "Respaldo periódico para apoyar la recuperación ante un incidente."},
        {"id": "managed-firewall", "title": "Firewall gestionado", "summary": "Reglas de acceso administradas para proteger el servidor."},
        {"id": "network", "title": "Red de 1 Gbps", "summary": "Conectividad para el tráfico de tu producto."},
        {"id": "dedicated-ip", "title": "IP dedicada", "summary": "Una dirección propia para el servidor de tu aplicación."},
        {"id": "ddos-protection", "title": "Protección contra DDoS", "summary": "Protección de red frente a ataques que intentan saturar el servicio."},
      ],
    },
    "faq": {
      "title": "Preguntas frecuentes",
      "items": [
        {"id": "unused-hours", "question": "¿Qué pasa si no uso mis horas?", "answer": "Vencen al terminar el mes y no se acumulan. Como en un gimnasio, tienes la capacidad disponible para usarla durante el ciclo. Planeamos el mes contigo para aprovecharla."},
        {"id": "hiring", "question": "¿Esto es una contratación de personal?", "answer": "No. Accedes a una célula compartida por medio de una bolsa mensual de horas. No contratas empleados de planta ni un equipo exclusivo de tiempo completo."},
        {"id": "task-fit", "question": "¿Qué pasa si una tarea no cabe en mi bolsa?", "answer": "Podemos dividirla, dejar una parte para el siguiente mes o conversar sobre subir de nivel. No se agregan horas extra automáticamente; tú apruebas la estimación antes de comenzar."},
        {"id": "tier-change", "question": "¿Puedo cambiar de nivel?", "answer": "Puedes subir desde el siguiente ciclo. Para bajar de nivel debes avisar con anticipación, según las condiciones acordadas."},
        {"id": "ownership", "question": "¿De quién es lo que entregan?", "answer": "Lo que te entregamos y has pagado es tuyo, según las condiciones acordadas para el proyecto."},
        {"id": "term-end", "question": "¿Qué pasa cuando termina el plazo que elegí?", "answer": "El servicio continúa mes a mes hasta que elijas otro plazo, según las condiciones acordadas."},
        {"id": "scope", "question": "¿Hay un alcance fijo o una fecha de entrega comprometida?", "answer": "No. Priorizamos tareas contigo y cada una tiene una estimación de referencia que se formaliza antes de empezar. El avance depende de la bolsa disponible y de las decisiones que tomemos juntos."},
      ],
    },
    "cta": {"title": "Hablemos de lo que tu producto necesita", "body": "Cuéntanos qué tienes hoy, qué te está frenando y cómo quieres avanzar. Te ayudamos a elegir el nivel que tenga sentido para ti.", "button_label": "Hablemos por WhatsApp", "whatsapp_message": "Hola, ProjectApp. Quiero conocer Building on Demand y conversar sobre cómo hacer evolucionar mi producto con una célula Scrum."},
    "legal": {"disclaimer": "Esta presentación es informativa. Las condiciones aplicables son las firmadas en el contrato. Los valores y las condiciones pueden cambiar; confirma la oferta vigente antes de contratar."},
  },
  "en": {
    "seo": {"title": "Building on Demand | ProjectApp", "description": "Grow your product with a shared Scrum cell. Choose your monthly bag of hours for development, design, architecture and operations."},
    "hero": {
      "eyebrow": "Building on Demand",
      "title": "A complete Scrum cell to help your product evolve",
      "subtitle": "You rent hours from a seven-person cell and use them each month on what your product needs. You set the priorities; we bring the team and the judgment to move forward.",
      "positioning": "An AI subscription gives you production capacity. A cell gives you judgment.",
      "note": "This is a monthly bag of available hours from a shared cell. It is not staff hiring or a dedicated full-time team.",
    },
    "cell": {
      "title": "A complete team, without having to hire it",
      "summary": "The cell brings together seven people who work together on your product. Each role adds a different perspective so changes arrive thoughtfully designed, built and tested.",
      "note": "The cell is always the same. Your tier defines how many hours you buy and which roles you can use.",
      "roles": [
        {"id": "developers", "title": "Two developers", "summary": "Build and refine the features your product needs, with code that can keep growing."},
        {"id": "project-lead", "title": "Project lead", "summary": "Organizes priorities, resolves questions with you and keeps each task’s progress visible."},
        {"id": "designer", "title": "Designer", "summary": "Makes screens and journeys work well for the people who use them."},
        {"id": "architect", "title": "Development architect and DevOps", "summary": "Gives the solution structure and looks after how it is deployed and operated in production."},
        {"id": "scrum-master", "title": "Scrum Master", "summary": "Looks after the team’s pace, facilitates conversations and helps remove obstacles."},
        {"id": "qa", "title": "QA", "summary": "Tests each delivery against clear criteria to catch problems before they reach your users."},
      ],
    },
    "fit": {
      "title": "For products that need to keep moving forward",
      "summary": "If you already have a product or tools in use, you can spend the bag on what adds the most value each month. You can also use it to clarify what you need before starting a project.",
      "good_for": [
        {"id": "existing-product", "title": "Evolve what already exists", "summary": "Improve your product or tools with changes, features and integrations based on your priorities."},
        {"id": "product-structure", "title": "Bring order and the state of the art", "summary": "Add structure, design and technical judgment to tools that grew quickly and are now difficult to maintain."},
        {"id": "discovery", "title": "Understand before you build", "summary": "Gather requirements, design journeys and define the architecture before starting a project."},
      ],
      "not_for": [
        {"id": "new-product", "title": "A new product from scratch", "summary": "Building a complete product from scratch belongs in a development project with its own scope."},
        {"id": "dedicated-team", "title": "Hiring an exclusive team", "summary": "The cell is shared. This program does not replace full-time hiring for your company."},
        {"id": "fixed-delivery", "title": "A fixed scope with a committed date", "summary": "You move through prioritized, estimated tasks. The bag does not promise a fixed scope or a committed delivery date."},
      ],
    },
    "tiers": {
      "title": "Choose the pace you want to move at",
      "summary": "The same cell supports your product. Each tier expands your bag and the roles you can turn to for what comes next.",
      "items": [
        {
          "id": "starter",
          "name": "Starter",
          "badge": "Focused progress",
          "pace_label": "Part-time",
          "pace_summary": "You move at a calm, steady pace, with one clear priority at a time.",
          "ideal_for": "You already know what you need and want it executed well. Ideal for changes and features in a product that is already running.",
          "roles": ["Development.", "Project lead.", "QA with every delivery."],
          "highlights": ["Asynchronous work with a ceremony every two weeks.", "One person requests and prioritizes work.", "One task in progress at a time.", "Target response time: 48 business hours."],
          "cta_label": "Let’s talk about Starter",
        },
        {
          "id": "business",
          "name": "Business",
          "badge": "Recommended",
          "pace_label": "Full-time",
          "pace_summary": "You move forward each week with room to define, design and build the next steps for your product.",
          "ideal_for": "You built tools quickly, even with AI, and they are now disorganized and behind the state of the art. You need an architect and a designer to give them structure and a good experience.",
          "roles": ["Everything in Starter.", "Designer.", "Development architect.", "Requirements discovery sessions.", "Production deploy."],
          "highlights": ["Weekly sprint with a progress demo.", "Up to three people can request work.", "Two tasks in progress at a time.", "Target response time: 24 business hours."],
          "cta_label": "Let’s talk about Business",
        },
        {
          "id": "enterprise",
          "name": "Enterprise",
          "badge": "A sustained pace",
          "pace_label": "Nonstop",
          "pace_summary": "You move at a sustained pace with your team, evolving the product while looking after its operation.",
          "ideal_for": "Your product is always moving and you need to coordinate more people, maintain operations and respond to frequent priorities.",
          "roles": ["Everything in Business.", "Dedicated Scrum Master.", "Continuous DevOps.", "Priority attention."],
          "highlights": ["Two-week sprint with a dedicated channel.", "Your entire team can request work.", "Three tasks in progress at a time.", "Target response time: 4 hours, with priority."],
          "cta_label": "Let’s talk about Enterprise",
        },
      ],
    },
    "terms": {
      "title": "Choose how to keep the work going",
      "summary": "You can start month to month or prepay a longer term. Each tier has its own conditions for the term you choose.",
      "note": "Even when you prepay several months, the bag renews every month and hours do not roll over.",
      "items": [
        {"id": "monthly", "label": "Monthly"},
        {"id": "quarterly", "label": "3 months"},
        {"id": "semiannual", "label": "6 months"},
        {"id": "nine-month", "label": "9 months"},
      ],
    },
    "bag": {
      "title": "A monthly bag with clear rules",
      "summary": "We plan the month with you and use the hours on tasks you have approved. You know what will be done and how the bag is used.",
      "note": "The bag defines available capacity. It does not commit to a fixed scope or a delivery date.",
      "rules": [
        {"id": "monthly-reset", "title": "It renews every month", "summary": "Each cycle starts with your tier’s bag of hours, even when you prepay several months."},
        {"id": "no-rollover", "title": "Hours do not roll over", "summary": "Unused hours expire at the end of the month. Plan your priorities to make the most of them."},
        {"id": "no-transfer", "title": "The bag cannot be transferred", "summary": "Hours belong to the agreed project. They cannot move to another company, person or project."},
        {"id": "approved-estimate", "title": "You approve before we start", "summary": "Each task uses the hours from the estimate you review and approve before we begin."},
        {"id": "shared-cell", "title": "Access to a shared cell", "summary": "You buy available hours and access to your tier’s roles. This is not permanent or full-time hiring."},
        {"id": "work-in-progress", "title": "A pace we can sustain", "summary": "Each tier defines how many tasks can be in progress at once. The others wait in the priority list."},
        {"id": "flexible-scope", "title": "Priorities can change", "summary": "There is no fixed scope or committed delivery date. We review the next tasks with you based on the available bag."},
      ],
    },
    "estimator": {
      "title": "Does it fit in your bag?",
      "summary": "Explore the tasks your product needs and their reference ranges. This helps you prepare the conversation and choose a tier.",
      "description_label": "Tell us what you want to do",
      "description_placeholder": "For example: organize my tools, improve a screen or integrate a service.",
      "disclaimer": "Hours are a reference. Before starting each task, we prepare the formal estimate with the requirements calculator and you approve it. XL work is split into smaller tasks.",
      "tasks": [
        {"id": "requirements-session", "label": "Requirements session", "hint": "Clarify the problem, the people who use it and what the task must solve."},
        {"id": "screen-design", "label": "Screen design", "hint": "Define a screen’s journey and presentation before building it."},
        {"id": "small-change", "label": "Small change", "hint": "Adjust text, a rule or a detail in an existing feature."},
        {"id": "component", "label": "Component", "hint": "Build a specific piece you can use within your product."},
        {"id": "feature", "label": "Feature", "hint": "Add a defined journey or capability to your product."},
        {"id": "large-feature", "label": "Large feature", "hint": "Solve a broader capability that needs several connected pieces."},
        {"id": "architecture-review", "label": "Architecture review", "hint": "Evaluate your solution’s structure and decide how to organize it for growth."},
        {"id": "production-deploy", "label": "Production deploy", "hint": "Prepare and publish an approved change in the production environment."},
        {"id": "continuous-devops", "label": "Continuous DevOps", "hint": "Support operations and steadily improve your product’s deployments."},
      ],
    },
    "hosting": {
      "title": "Your product also has a place to live",
      "summary": "Every tier includes a VPS server, maintenance and support so your product can operate in production.",
      "note": "Preventive maintenance and server incident support do not consume your bag of hours.",
      "features": [
        {"id": "amd-epyc", "title": "AMD EPYC processors", "summary": "Processing capacity to support your product’s operation."},
        {"id": "nvme-storage", "title": "NVMe storage", "summary": "Fast storage for your application’s files and data."},
        {"id": "weekly-backups", "title": "Weekly backups", "summary": "Regular backups to support recovery after an incident."},
        {"id": "managed-firewall", "title": "Managed firewall", "summary": "Managed access rules to protect the server."},
        {"id": "network", "title": "1 Gbps network", "summary": "Connectivity for your product’s traffic."},
        {"id": "dedicated-ip", "title": "Dedicated IP", "summary": "A dedicated address for your application’s server."},
        {"id": "ddos-protection", "title": "DDoS protection", "summary": "Network protection against attacks that attempt to overwhelm the service."},
      ],
    },
    "faq": {
      "title": "Frequently asked questions",
      "items": [
        {"id": "unused-hours", "question": "What happens if I do not use my hours?", "answer": "They expire at the end of the month and do not roll over. Like a gym, you have capacity available to use during the cycle. We plan the month with you to make the most of it."},
        {"id": "hiring", "question": "Is this staff hiring?", "answer": "No. You access a shared cell through a monthly bag of hours. You do not hire permanent employees or an exclusive full-time team."},
        {"id": "task-fit", "question": "What happens if a task does not fit in my bag?", "answer": "We can split it, leave part for the next month or discuss moving up a tier. Extra hours are never added automatically; you approve the estimate before we begin."},
        {"id": "tier-change", "question": "Can I change tiers?", "answer": "You can move up from the next cycle. To move down, you need to give advance notice under the agreed conditions."},
        {"id": "ownership", "question": "Who owns what you deliver?", "answer": "What we deliver and you have paid for is yours, under the conditions agreed for the project."},
        {"id": "term-end", "question": "What happens when my chosen term ends?", "answer": "The service continues month to month until you choose another term, under the agreed conditions."},
        {"id": "scope", "question": "Is there a fixed scope or a committed delivery date?", "answer": "No. We prioritize tasks with you and each has a reference estimate that is formalized before we start. Progress depends on the available bag and the decisions we make together."},
      ],
    },
    "cta": {"title": "Let’s talk about what your product needs", "body": "Tell us what you have today, what is holding you back and how you want to move forward. We help you choose a tier that makes sense for you.", "button_label": "Chat on WhatsApp", "whatsapp_message": "Hi, ProjectApp. I would like to learn about Building on Demand and discuss how to help my product evolve with a Scrum cell."},
    "legal": {"disclaimer": "This presentation is for information only. The applicable conditions are those signed in the contract. Values and conditions may change; confirm the current offer before subscribing."},
  },
};

const tierNumbers = [
  {
    "id": "starter",
    "recommended": false,
    "monthly_price": 1800000,
    "daily_hours": 4,
    "server": {"vcpu": 1, "ram_gb": 4, "disk_gb": 50, "transfer_tb": 4},
    "bag_hours": 96,
    "prices": [
      {"term": "monthly", "months": 1, "discount_percent": 0, "monthly_price": 1800000, "total": 1800000, "savings": 0},
      {"term": "quarterly", "months": 3, "discount_percent": 5, "monthly_price": 1710000, "total": 5130000, "savings": 270000},
      {"term": "semiannual", "months": 6, "discount_percent": 10, "monthly_price": 1620000, "total": 9720000, "savings": 1080000},
      {"term": "nine-month", "months": 9, "discount_percent": 15, "monthly_price": 1530000, "total": 13770000, "savings": 2430000},
    ],
  },
  {
    "id": "business",
    "recommended": true,
    "monthly_price": 4200000,
    "daily_hours": 8,
    "server": {"vcpu": 4, "ram_gb": 16, "disk_gb": 200, "transfer_tb": 16},
    "bag_hours": 192,
    "prices": [
      {"term": "monthly", "months": 1, "discount_percent": 0, "monthly_price": 4200000, "total": 4200000, "savings": 0},
      {"term": "quarterly", "months": 3, "discount_percent": 10, "monthly_price": 3780000, "total": 11340000, "savings": 1260000},
      {"term": "semiannual", "months": 6, "discount_percent": 15, "monthly_price": 3570000, "total": 21420000, "savings": 3780000},
      {"term": "nine-month", "months": 9, "discount_percent": 20, "monthly_price": 3360000, "total": 30240000, "savings": 7560000},
    ],
  },
  {
    "id": "enterprise",
    "recommended": false,
    "monthly_price": 9600000,
    "daily_hours": 12,
    "server": {"vcpu": 8, "ram_gb": 32, "disk_gb": 400, "transfer_tb": 32},
    "bag_hours": 288,
    "prices": [
      {"term": "monthly", "months": 1, "discount_percent": 0, "monthly_price": 9600000, "total": 9600000, "savings": 0},
      {"term": "quarterly", "months": 3, "discount_percent": 15, "monthly_price": 8160000, "total": 24480000, "savings": 4320000},
      {"term": "semiannual", "months": 6, "discount_percent": 20, "monthly_price": 7680000, "total": 46080000, "savings": 11520000},
      {"term": "nine-month", "months": 9, "discount_percent": 25, "monthly_price": 7200000, "total": 64800000, "savings": 21600000},
    ],
  },
];

const termMonths = {"monthly": 1, "quarterly": 3, "semiannual": 6, "nine-month": 9};

const estimatorSizes = [
  {"id": "xs", "hours_min": 2, "hours_max": 7},
  {"id": "s", "hours_min": 7, "hours_max": 20},
  {"id": "m", "hours_min": 20, "hours_max": 50},
  {"id": "l", "hours_min": 55, "hours_max": 90},
];

const estimatorTasks = [
  {"id": "requirements-session", "size": "s", "min_tier": "business"},
  {"id": "screen-design", "size": "s", "min_tier": "business"},
  {"id": "small-change", "size": "xs", "min_tier": "starter"},
  {"id": "component", "size": "s", "min_tier": "starter"},
  {"id": "feature", "size": "m", "min_tier": "starter"},
  {"id": "large-feature", "size": "l", "min_tier": "starter"},
  {"id": "architecture-review", "size": "m", "min_tier": "business"},
  {"id": "production-deploy", "size": "xs", "min_tier": "business"},
  {"id": "continuous-devops", "size": "m", "min_tier": "enterprise"},
];

const economics = {
  "currency": "COP",
  "hour_cost": 55000,
  "vat_percent": 19,
  "provider": "Hostinger",
  "reference_url": "https://www.hostinger.com/co/vps-servidor-web",
  "consulted_on": "2026-10-10",
  "tiers": [
    {"id": "starter", "name": "Starter", "bag_hours": 96, "plan": "KVM 1", "promo_monthly": 19900, "renewal_monthly": 38900, "hosting_cost_monthly": 46291},
    {"id": "business", "name": "Business", "bag_hours": 192, "plan": "KVM 4", "promo_monthly": 38900, "renewal_monthly": 97900, "hosting_cost_monthly": 116501},
    {"id": "enterprise", "name": "Enterprise", "bag_hours": 288, "plan": "KVM 8", "promo_monthly": 77900, "renewal_monthly": 168900, "hosting_cost_monthly": 200991},
  ],
  "rows": [
    {"tier": "starter", "term": "monthly", "months": 1, "monthly_price": 1800000, "hosting_cost_monthly": 46291, "net_monthly": 1753709, "breakeven_hours": 31.9, "breakeven_hours_rounded": 32, "bag_hours": 96, "bag_share_percent": 33, "breakeven_hours_without_hosting": 32.7},
    {"tier": "starter", "term": "quarterly", "months": 3, "monthly_price": 1710000, "hosting_cost_monthly": 46291, "net_monthly": 1663709, "breakeven_hours": 30.2, "breakeven_hours_rounded": 30, "bag_hours": 96, "bag_share_percent": 32, "breakeven_hours_without_hosting": 31.1},
    {"tier": "starter", "term": "semiannual", "months": 6, "monthly_price": 1620000, "hosting_cost_monthly": 46291, "net_monthly": 1573709, "breakeven_hours": 28.6, "breakeven_hours_rounded": 29, "bag_hours": 96, "bag_share_percent": 30, "breakeven_hours_without_hosting": 29.5},
    {"tier": "starter", "term": "nine-month", "months": 9, "monthly_price": 1530000, "hosting_cost_monthly": 46291, "net_monthly": 1483709, "breakeven_hours": 27.0, "breakeven_hours_rounded": 27, "bag_hours": 96, "bag_share_percent": 28, "breakeven_hours_without_hosting": 27.8},
    {"tier": "business", "term": "monthly", "months": 1, "monthly_price": 4200000, "hosting_cost_monthly": 116501, "net_monthly": 4083499, "breakeven_hours": 74.2, "breakeven_hours_rounded": 74, "bag_hours": 192, "bag_share_percent": 39, "breakeven_hours_without_hosting": 76.4},
    {"tier": "business", "term": "quarterly", "months": 3, "monthly_price": 3780000, "hosting_cost_monthly": 116501, "net_monthly": 3663499, "breakeven_hours": 66.6, "breakeven_hours_rounded": 67, "bag_hours": 192, "bag_share_percent": 35, "breakeven_hours_without_hosting": 68.7},
    {"tier": "business", "term": "semiannual", "months": 6, "monthly_price": 3570000, "hosting_cost_monthly": 116501, "net_monthly": 3453499, "breakeven_hours": 62.8, "breakeven_hours_rounded": 63, "bag_hours": 192, "bag_share_percent": 33, "breakeven_hours_without_hosting": 64.9},
    {"tier": "business", "term": "nine-month", "months": 9, "monthly_price": 3360000, "hosting_cost_monthly": 116501, "net_monthly": 3243499, "breakeven_hours": 59.0, "breakeven_hours_rounded": 59, "bag_hours": 192, "bag_share_percent": 31, "breakeven_hours_without_hosting": 61.1},
    {"tier": "enterprise", "term": "monthly", "months": 1, "monthly_price": 9600000, "hosting_cost_monthly": 200991, "net_monthly": 9399009, "breakeven_hours": 170.9, "breakeven_hours_rounded": 171, "bag_hours": 288, "bag_share_percent": 59, "breakeven_hours_without_hosting": 174.5},
    {"tier": "enterprise", "term": "quarterly", "months": 3, "monthly_price": 8160000, "hosting_cost_monthly": 200991, "net_monthly": 7959009, "breakeven_hours": 144.7, "breakeven_hours_rounded": 145, "bag_hours": 288, "bag_share_percent": 50, "breakeven_hours_without_hosting": 148.4},
    {"tier": "enterprise", "term": "semiannual", "months": 6, "monthly_price": 7680000, "hosting_cost_monthly": 200991, "net_monthly": 7479009, "breakeven_hours": 136.0, "breakeven_hours_rounded": 136, "bag_hours": 288, "bag_share_percent": 47, "breakeven_hours_without_hosting": 139.6},
    {"tier": "enterprise", "term": "nine-month", "months": 9, "monthly_price": 7200000, "hosting_cost_monthly": 200991, "net_monthly": 6999009, "breakeven_hours": 127.3, "breakeven_hours_rounded": 127, "bag_hours": 288, "bag_share_percent": 44, "breakeven_hours_without_hosting": 130.9},
  ],
};

export function buildingOnDemandProgramFixture(language = 'es') {
  const lang = language === 'en' ? 'en' : 'es';
  const payload = structuredClone(content[lang]);
  payload.tiers.items = payload.tiers.items.map((tier) => ({
    ...tier, ...structuredClone(tierNumbers.find((numbers) => numbers.id === tier.id)),
  }));
  payload.terms.items = payload.terms.items.map((term) => ({
    ...term, months: termMonths[term.id],
  }));
  payload.estimator.sizes = structuredClone(estimatorSizes);
  payload.estimator.tasks = payload.estimator.tasks.map((task) => ({
    ...task, ...estimatorTasks.find((numbers) => numbers.id === task.id),
  }));
  const whatsappBaseUrl = 'https://wa.me/573238122373';
  payload.cta.whatsapp_url = `${whatsappBaseUrl}?text=${encodeURIComponent(payload.cta.whatsapp_message)}`;
  delete payload.cta.whatsapp_message;
  return {
    language: lang, version: 21, updated_at: updatedAt,
    canonical_path: `/${lang === 'en' ? 'en-us' : 'es-co'}/building-on-demand`,
    alternate_path: `/${lang === 'en' ? 'es-co' : 'en-us'}/building-on-demand`,
    pdf_path: `/api/building-on-demand/public/pdf/?lang=${lang}`,
    ...payload,
    offer: { currency: 'COP', prices_include_vat: false, days_per_week: 6, weeks_per_month: 4, recommended_tier: 'business' },
    contact: { whatsapp_base_url: whatsappBaseUrl },
  };
}

function versionSummary(kind, version = 21) {
  return {
    version, version_id: (kind === 'program' ? 100 : 200) + version,
    updated_at: updatedAt, author,
    change_note: kind === 'program' ? 'Programa actualizado con bolsas mensuales de horas.' : 'Contrato de la célula publicado.',
    etag: `building-on-demand-${kind}-${version}`,
  };
}

export function buildingOnDemandMirrorFixture(status = 'synchronized') {
  return {
    status, document_id: status === 'not_initialized' ? null : 731,
    title: contractTitle, folder_id: status === 'not_initialized' ? null : 730,
    folder_path: status === 'not_initialized' ? null : 'ProjectApp › Contratos',
    version: status === 'not_initialized' ? null : status === 'out_of_sync' ? 20 : 21,
    last_synced_at: status === 'not_initialized' ? null : updatedAt,
  };
}

export function buildingOnDemandOverviewFixture({ withContract = true, mirrorStatus = 'synchronized' } = {}) {
  const contractSummary = versionSummary('contract');
  delete contractSummary.etag;
  return {
    program: versionSummary('program'),
    contract: withContract ? { ...contractSummary, mirror: buildingOnDemandMirrorFixture(mirrorStatus) } : null,
    connector: { slug: 'programs', is_active: false },
    public_paths: { es: '/es-co/building-on-demand', en: '/en-us/building-on-demand' },
    pdf_paths: { es: '/api/building-on-demand/public/pdf/?lang=es', en: '/api/building-on-demand/public/pdf/?lang=en' },
  };
}

export function buildingOnDemandVersionsFixture(kind = 'program', offset = 0, limit = 20) {
  const versions = Array.from({ length: 21 }, (_, index) => {
    const summary = versionSummary(kind, 21 - index);
    return {
      version_id: summary.version_id, version: summary.version, author: summary.author,
      created_at: updatedAt, change_note: summary.change_note,
      restored_from_version_id: null, restored_from_version: null,
    };
  });
  return { total: versions.length, versions: versions.slice(offset, offset + limit) };
}

export function buildingOnDemandEconomicsFixture() {
  return structuredClone(economics);
}

export function buildingOnDemandContractFixture(status = 'synchronized') {
  return {
    ...versionSummary('contract'), mirror: buildingOnDemandMirrorFixture(status),
    markdown: `# ${contractTitle}\n\n## Objeto\n\nAcceso a una célula Scrum compartida mediante una bolsa mensual de horas.\n\n## Bolsa mensual\n\n| Nivel | Horas disponibles |\n| --- | --- |\n| Starter | 96 |\n| Business | 192 |\n| Enterprise | 288 |\n\nLas horas se renuevan cada mes, no se acumulan y cada tarea se estima antes de comenzar.\n`,
  };
}

export function buildingOnDemandPdfFixture(filename = 'building-on-demand-es.pdf', inline = false) {
  return {
    status: 200, contentType: 'application/pdf',
    headers: { 'Content-Disposition': `${inline ? 'inline' : 'attachment'}; filename="${filename}"`, 'Cache-Control': 'private, no-store' },
    body: '%PDF-1.4 Building on Demand\n%%EOF',
  };
}

/** Fulfill only this module's GET endpoints; return null for the next mockApi handler. */
export function buildingOnDemandApiFixture({ apiPath, method, route }) {
  if (method !== 'GET') return null;
  const params = new URL(route.request().url()).searchParams;
  const lang = params.get('lang') === 'en' ? 'en' : 'es';
  if (apiPath === 'building-on-demand/public/pdf/') return buildingOnDemandPdfFixture(`building-on-demand-${lang}.pdf`);
  if (apiPath === 'building-on-demand/admin/contract/pdf/') return buildingOnDemandPdfFixture('building-on-demand-contract.pdf', params.get('inline') === '1');
  const offset = Number(params.get('offset') || 0);
  const limit = Number(params.get('limit') || 20);
  const payloads = {
    'building-on-demand/public/': () => buildingOnDemandProgramFixture(lang),
    'building-on-demand/admin/': buildingOnDemandOverviewFixture,
    'building-on-demand/admin/program/versions/': () => buildingOnDemandVersionsFixture('program', offset, limit),
    'building-on-demand/admin/economics/': buildingOnDemandEconomicsFixture,
    'building-on-demand/admin/contract/': buildingOnDemandContractFixture,
    'building-on-demand/admin/contract/versions/': () => buildingOnDemandVersionsFixture('contract', offset, limit),
  };
  const payload = payloads[apiPath]?.();
  return payload ? { status: 200, contentType: 'application/json', headers: { 'Cache-Control': 'no-store' }, body: JSON.stringify(payload) } : null;
}
