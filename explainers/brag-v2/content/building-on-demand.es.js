window.EXPLAINER_CONTENT = {
  "language": "es",
  "version": 1,
  "hero": {
    "eyebrow": "Building on Demand",
    "title": "Una célula Scrum completa para hacer evolucionar tu producto",
    "subtitle": "Alquilas horas de una célula de siete personas y las usas cada mes en lo que tu producto necesita. Tú decides las prioridades; nosotros aportamos el equipo y el criterio para avanzar.",
    "positioning": "Una suscripción de IA te da capacidad de producción. Una célula te da criterio.",
    "note": "Es una bolsa mensual de horas disponibles de una célula compartida. No es contratación de planta ni un equipo dedicado de tiempo completo."
  },
  "cell": {
    "title": "Un equipo completo, sin tener que contratarlo",
    "summary": "La célula reúne siete personas que trabajan juntas sobre tu producto. Cada rol aporta una mirada distinta para que los cambios lleguen bien pensados, construidos y probados.",
    "note": "La célula siempre es la misma. El nivel que eliges define cuántas horas compras y qué roles puedes usar.",
    "roles": [
      {
        "id": "developers",
        "title": "Dos desarrolladores",
        "summary": "Construyen y ajustan las funciones que tu producto necesita, con código que pueda seguir creciendo."
      },
      {
        "id": "project-lead",
        "title": "Líder de proyecto",
        "summary": "Organiza las prioridades, resuelve dudas contigo y mantiene visible el avance de cada tarea."
      },
      {
        "id": "designer",
        "title": "Diseñador",
        "summary": "Hace que las pantallas y los recorridos tengan sentido para las personas que los usan."
      },
      {
        "id": "architect",
        "title": "Arquitecto de desarrollo y DevOps",
        "summary": "Da estructura a la solución y cuida cómo se despliega y opera en producción."
      },
      {
        "id": "scrum-master",
        "title": "Scrum Master",
        "summary": "Cuida el ritmo del equipo, facilita las conversaciones y ayuda a quitar obstáculos."
      },
      {
        "id": "qa",
        "title": "QA",
        "summary": "Prueba cada entrega con criterios claros para detectar problemas antes de que lleguen a tus usuarios."
      }
    ]
  },
  "bag": {
    "title": "Una bolsa mensual con reglas claras",
    "summary": "Planeamos contigo el mes y usamos las horas en tareas que hayas aprobado. Así sabes qué se va a hacer y cómo se consume la bolsa.",
    "note": "La bolsa define capacidad disponible. No compromete un alcance fijo ni una fecha de entrega.",
    "rules": [
      {
        "id": "monthly-reset",
        "title": "Se renueva cada mes",
        "summary": "Cada ciclo comienza con la bolsa de horas de tu nivel, incluso si pagaste varios meses por anticipado."
      },
      {
        "id": "no-rollover",
        "title": "Las horas no se acumulan",
        "summary": "Las horas que no uses vencen al terminar el mes. Planea tus prioridades para aprovecharlas."
      },
      {
        "id": "no-transfer",
        "title": "La bolsa no se transfiere",
        "summary": "Las horas corresponden al proyecto acordado. No pasan a otra empresa, persona o proyecto."
      },
      {
        "id": "approved-estimate",
        "title": "Apruebas antes de empezar",
        "summary": "Cada tarea consume las horas de la estimación que revisas y apruebas antes de que comencemos."
      },
      {
        "id": "shared-cell",
        "title": "Acceso a una célula compartida",
        "summary": "Compras horas disponibles y acceso a los roles de tu nivel. No es contratación de planta ni tiempo completo."
      },
      {
        "id": "work-in-progress",
        "title": "Un ritmo que podamos sostener",
        "summary": "Cada nivel define cuántas tareas pueden estar en curso a la vez. Las demás esperan en la lista de prioridades."
      },
      {
        "id": "flexible-scope",
        "title": "Prioridades que pueden cambiar",
        "summary": "No hay un alcance fijo ni una fecha de entrega comprometida. Revisamos las siguientes tareas contigo según la bolsa disponible."
      }
    ]
  },
  "hosting": {
    "title": "Tu producto también tiene dónde vivir",
    "summary": "Cada nivel incluye un servidor VPS, mantenimiento y soporte para que tu producto pueda operar en producción.",
    "note": "El mantenimiento preventivo y la atención de incidentes del servidor no consumen tu bolsa de horas.",
    "features": [
      {
        "id": "amd-epyc",
        "title": "Procesadores AMD EPYC",
        "summary": "Capacidad de procesamiento para acompañar la operación de tu producto."
      },
      {
        "id": "nvme-storage",
        "title": "Disco NVMe",
        "summary": "Almacenamiento rápido para los archivos y datos de tu aplicación."
      },
      {
        "id": "weekly-backups",
        "title": "Copias de seguridad semanales",
        "summary": "Respaldo periódico para apoyar la recuperación ante un incidente."
      },
      {
        "id": "managed-firewall",
        "title": "Firewall gestionado",
        "summary": "Reglas de acceso administradas para proteger el servidor."
      },
      {
        "id": "network",
        "title": "Red de 1 Gbps",
        "summary": "Conectividad para el tráfico de tu producto."
      },
      {
        "id": "dedicated-ip",
        "title": "IP dedicada",
        "summary": "Una dirección propia para el servidor de tu aplicación."
      },
      {
        "id": "ddos-protection",
        "title": "Protección contra DDoS",
        "summary": "Protección de red frente a ataques que intentan saturar el servicio."
      }
    ]
  },
  "tiers": {
    "title": "Elige el ritmo al que quieres avanzar",
    "items": [
      {
        "id": "starter",
        "name": "Starter",
        "bag_hours": 96,
        "recommended": false,
        "roles": [
          "Desarrollo.",
          "Líder de proyecto.",
          "QA en cada entrega."
        ]
      },
      {
        "id": "business",
        "name": "Business",
        "bag_hours": 192,
        "recommended": true,
        "roles": [
          "Todo lo de Starter.",
          "Diseñador.",
          "Arquitecto de desarrollo.",
          "Sesiones de levantamiento de requerimientos.",
          "Deploy a producción."
        ]
      },
      {
        "id": "enterprise",
        "name": "Enterprise",
        "bag_hours": 288,
        "recommended": false,
        "roles": [
          "Todo lo de Business.",
          "Scrum Master dedicado.",
          "DevOps continuo.",
          "Prioridad de atención."
        ]
      }
    ]
  }
};
