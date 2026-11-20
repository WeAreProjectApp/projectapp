"""Seed JSON for a new WebAppDiagnostic.

Each entry builds the default ``content_json`` for a ``DiagnosticSection``.
The shape matches the props of the matching Vue component under
``frontend/components/WebAppDiagnostic/public/``.
"""

from __future__ import annotations


CATEGORIES = [
    {
        'key': 'architecture',
        'title': 'Arquitectura y Estructura Interna',
        'description': (
            'Cómo está organizada la aplicación por dentro. Si el código está '
            'ordenado y bien separado en capas lógicas, o si es un "plato de '
            'espagueti" donde todo está mezclado. Si los patrones de diseño que '
            'se usaron tienen sentido. Si un equipo nuevo podría entender cómo '
            'funciona sin depender de una sola persona.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'code_quality',
        'title': 'Calidad del Código',
        'description': (
            'Qué tan limpio, legible y consistente es lo que está escrito. Si '
            'se siguen convenciones, si hay código duplicado, si los nombres de '
            'las cosas tienen sentido, si hay complejidad innecesaria.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'ui_ux',
        'title': 'Interfaz de Usuario y Experiencia (Lo que el usuario ve)',
        'description': (
            'Si la aplicación tiene partes construidas con tecnologías distintas '
            '(algunas más viejas que otras) y qué tan sostenible es esa mezcla. '
            'La velocidad de carga y la fluidez de la experiencia. Que funcione '
            'bien tanto en celular como en computador. La coherencia visual y de '
            'interacción entre las distintas partes de la aplicación.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'database',
        'title': 'Base de Datos y Gestión de la Información',
        'description': (
            'Cómo se guardan, organizan y consultan los datos. Si la estructura '
            'tiene sentido, si hay datos duplicados o inconsistentes, si las '
            'consultas son eficientes, si se gestionan las migraciones '
            'correctamente.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'security',
        'title': 'Seguridad',
        'description': (
            'Qué tan protegida está la aplicación contra accesos no autorizados, '
            'robo de datos, ataques o mal uso. Esto se evalúa desde lo que se '
            'puede observar en el código: cómo se manejan contraseñas, permisos, '
            'validaciones y datos sensibles.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'performance',
        'title': 'Rendimiento',
        'description': (
            'Qué tan rápida es la aplicación en sus operaciones. Los cuellos de '
            'botella que se pueden identificar desde el código: consultas '
            'lentas, procesos que bloquean al usuario, carga innecesaria de '
            'recursos.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'scalability',
        'title': 'Escalabilidad',
        'description': (
            'No "¿qué tan rápida es hoy?" sino "¿está preparada para crecer?" '
            'Desde el código se evalúa si las decisiones de diseño permiten que '
            'la aplicación soporte más usuarios, más datos y más transacciones '
            'sin requerir reescribirla.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'testing',
        'title': 'Pruebas y Criterios de Calidad',
        'description': (
            'Qué tipos de pruebas existen y cuáles faltan. Cubre pruebas '
            'unitarias, de contrato, de integración con base de datos real y '
            'permisos, con mocking y casos extremos, E2E, de carga y '
            'rendimiento, y de seguridad y configuración. También evalúa qué '
            'tan automatizadas están y si se ejecutan como parte del proceso de '
            'desarrollo.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'maintainability',
        'title': 'Mantenibilidad y Evolución',
        'description': (
            'Qué tan fácil es hacerle cambios, corregir errores o agregar '
            'funcionalidades sin romper lo existente. Qué tan acopladas están '
            'las piezas entre sí.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'reliability',
        'title': 'Confiabilidad y Tolerancia a Fallos',
        'description': (
            'Qué tan estable es en el día a día, evaluado desde el código. Qué '
            'pasa cuando algo sale mal: ¿el código maneja los errores '
            'correctamente o se desploma todo? ¿Las operaciones críticas '
            'protegen los datos ante fallos?'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'integrations',
        'title': 'Integraciones y Comunicación entre Componentes',
        'description': (
            'Cómo se conectan las partes internas entre sí (frontend y backend) '
            'y con sistemas o servicios externos. Si esas conexiones están bien '
            'organizadas y manejan errores adecuadamente.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'tech_currency',
        'title': 'Vigencia Tecnológica',
        'description': (
            'Qué tan actualizadas están las herramientas, librerías y '
            'plataformas. Qué riesgo hay de obsolescencia. Si las tecnologías '
            'elegidas tienen futuro y si se puede encontrar talento capacitado.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'documentation',
        'title': 'Documentación y Gestión del Conocimiento',
        'description': (
            'Qué tanto está explicado y registrado. Si cualquier equipo nuevo '
            'podría entender la aplicación sin depender de la tradición oral de '
            'una o dos personas.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
    {
        'key': 'functional_capabilities',
        'title': 'Capacidades Funcionales (Qué necesidades resuelve y cómo)',
        'description': (
            'Desde el código y la estructura, qué funcionalidades ofrece la '
            'aplicación, qué problemas resuelve y de qué manera lo hace. Si hay '
            'módulos incompletos, lógica de negocio dispersa, soluciones '
            'improvisadas o funcionalidades abandonadas.'
        ),
        'findings': [],
        'strengths': [],
        'recommendations': [],
    },
]


SEVERITY_LEVELS = [
    {
        'level': 'Crítico',
        'meaning': (
            'Representa un riesgo inmediato. Puede causar caídas, pérdida de '
            'datos, brechas de seguridad o bloqueo total del equipo. Debe '
            'atenderse con urgencia.'
        ),
    },
    {
        'level': 'Alto',
        'meaning': (
            'Problema serio que impacta significativamente la calidad, el '
            'rendimiento o la capacidad de evolución. Debe planificarse a corto '
            'plazo.'
        ),
    },
    {
        'level': 'Medio',
        'meaning': (
            'Problema real pero manejable. Genera fricción, deuda técnica o '
            'ineficiencias. Se recomienda abordar a mediano plazo.'
        ),
    },
    {
        'level': 'Bajo',
        'meaning': (
            'Mejora deseable que aporta valor pero no representa un riesgo. Se '
            'puede abordar cuando haya espacio en la planificación.'
        ),
    },
]


RADIOGRAPHY_INCLUDES = [
    {
        'title': 'Tecnologías utilizadas',
        'description': (
            'Qué lenguajes, frameworks y herramientas principales se usan en el '
            'backend y en el frontend.'
        ),
    },
    {
        'title': 'Cantidad de pantallas o vistas',
        'description': 'Cuántas pantallas tiene la aplicación del lado del usuario.',
    },
    {
        'title': 'Cantidad de entidades o tablas',
        'description': (
            'Cuántas "cosas" maneja la aplicación (usuarios, productos, '
            'pedidos, etc.), reflejado en las tablas de la base de datos.'
        ),
    },
    {
        'title': 'Cantidad de endpoints o rutas del backend',
        'description': (
            'Cuántos puntos de comunicación ofrece el backend (cada acción que '
            'el frontend le puede pedir al servidor).'
        ),
    },
    {
        'title': 'Cantidad de componentes del frontend',
        'description': 'Cuántas piezas reutilizables tiene la interfaz.',
    },
    {
        'title': 'Integraciones externas',
        'description': (
            'Con cuántos servicios de terceros se conecta la aplicación '
            '(pasarelas de pago, envío de correos, APIs externas, etc.).'
        ),
    },
    {
        'title': 'Módulos o dominios funcionales',
        'description': (
            'Cuántas áreas de negocio distintas cubre la aplicación '
            '(autenticación, facturación, reportes, notificaciones, etc.).'
        ),
    },
]


SIZE_CLASSIFICATION_ROWS = [
    {
        'dimension': 'Entidades / tablas',
        'small': 'Menos de 15',
        'medium': 'Entre 15 y 50',
        'large': 'Más de 50',
    },
    {
        'dimension': 'Endpoints / rutas backend',
        'small': 'Menos de 30',
        'medium': 'Entre 30 y 100',
        'large': 'Más de 100',
    },
    {
        'dimension': 'Pantallas / vistas',
        'small': 'Menos de 15',
        'medium': 'Entre 15 y 50',
        'large': 'Más de 50',
    },
    {
        'dimension': 'Componentes frontend',
        'small': 'Menos de 20',
        'medium': 'Entre 20 y 80',
        'large': 'Más de 80',
    },
    {
        'dimension': 'Integraciones externas',
        'small': '0 a 2',
        'medium': '3 a 7',
        'large': 'Más de 7',
    },
    {
        'dimension': 'Módulos funcionales',
        'small': '1 a 3',
        'medium': '4 a 8',
        'large': 'Más de 8',
    },
]


TIMELINE_DISTRIBUTION = [
    {
        'dayRange': 'Día 1',
        'description': 'Levantamiento y lectura estructural de backend y frontend.',
    },
    {
        'dayRange': 'Días 2 a 4',
        'description': (
            'Evaluación por categorías, identificación de hallazgos y '
            'consolidación de evidencia.'
        ),
    },
    {
        'dayRange': 'Día 5',
        'description': (
            'Construcción del informe final, resumen ejecutivo y '
            'recomendaciones priorizadas.'
        ),
    },
]


SCOPE_CONSIDERATIONS = [
    (
        'El diagnóstico se realiza exclusivamente sobre los repositorios de '
        'código fuente (backend y frontend). No se evalúa infraestructura del '
        'servidor, procesos de despliegue ni sistemas de monitoreo.'
    ),
    (
        'La escala de severidad es una herramienta de priorización, no un '
        'juicio sobre el equipo que construyó la aplicación.'
    ),
    (
        'La clasificación de tamaño es orientativa y sirve como herramienta de '
        'dimensionamiento, no como un veredicto absoluto.'
    ),
    (
        'Esta propuesta describe qué se evaluará, cómo se estructurará la '
        'entrega y qué tipo de valor puede esperar la empresa al contratar el '
        'diagnóstico.'
    ),
]


DELIVERY_STRUCTURE_BLOCKS = [
    {
        'title': 'Lo que se encontró bien',
        'paragraphs': [
            (
                'Se documentan las prácticas, decisiones o implementaciones que '
                'hoy están funcionando correctamente. Esto permite reconocer '
                'fortalezas reales de la aplicación y señalar qué vale la pena '
                'conservar.'
            ),
        ],
        'example': (
            '"El modelo de datos está bien normalizado y las migraciones están '
            'versionadas con un historial limpio."'
        ),
    },
    {
        'title': 'Hallazgos y oportunidades de mejora',
        'paragraphs': [
            (
                'Se documentan los problemas, riesgos o debilidades encontradas. '
                'Cada hallazgo se presenta con su respectiva clasificación de '
                'severidad.'
            ),
        ],
        'example': '',
    },
    {
        'title': 'Recomendaciones',
        'paragraphs': [
            (
                'Se proponen acciones concretas para abordar los hallazgos '
                'identificados. Cada recomendación conserva el nivel de '
                'severidad del hallazgo que busca resolver.'
            ),
        ],
        'example': '',
    },
]


def _purpose_section(order):
    return {
        'section_type': 'purpose',
        'title': 'Propósito',
        'order': order,
        'visibility': 'both',
        'is_enabled': True,
        'content_json': {
            'index': '1',
            'title': 'Propósito',
            'paragraphs': [
                (
                    'Esta propuesta presenta el alcance, las categorías de '
                    'evaluación y la estructura de entrega de un diagnóstico '
                    'integral para una aplicación web, realizado a partir de la '
                    'revisión de sus repositorios de código (backend y '
                    'frontend). El objetivo es evaluar el estado actual de la '
                    'aplicación, identificar fortalezas, oportunidades de '
                    'mejora y entregar recomendaciones priorizadas que sirvan '
                    'como base para la toma de decisiones técnicas y de '
                    'negocio.'
                ),
            ],
            'scopeNote': (
                'Este diagnóstico se realiza exclusivamente sobre los '
                'repositorios de código fuente. No se evalúa la infraestructura '
                'del servidor, el proceso de despliegue ni los sistemas de '
                'monitoreo, ya que no se tiene acceso a esos entornos.'
            ),
            'severityTitle': 'Escala de Severidad',
            'severityIntro': (
                'Los hallazgos, oportunidades de mejora y recomendaciones '
                'resultantes del diagnóstico se clasifican usando la siguiente '
                'escala:'
            ),
            'severityLevels': SEVERITY_LEVELS,
        },
    }


def _radiography_section(order):
    return {
        'section_type': 'radiography',
        'title': 'Radiografía de la Aplicación',
        'order': order,
        'visibility': 'both',
        'is_enabled': True,
        'content_json': {
            'index': '2',
            'title': 'Radiografía de la Aplicación',
            'intro': (
                'Como parte del diagnóstico, se levanta un inventario general '
                'de la aplicación para dimensionar su tamaño, complejidad y '
                'nivel de madurez técnica. Esta radiografía permite '
                'contextualizar los hallazgos y establecer expectativas '
                'realistas sobre el esfuerzo de mejora.'
            ),
            'includesTitle': '¿Qué incluye esta radiografía?',
            'includes': RADIOGRAPHY_INCLUDES,
            'classificationTitle': 'Clasificación por Tamaño',
            'classificationIntro': (
                'Con base en este inventario, la aplicación se clasifica en una '
                'de las siguientes categorías de tamaño:'
            ),
            'classificationRows': SIZE_CLASSIFICATION_ROWS,
            'classificationNote': (
                'No es necesario que todas las dimensiones caigan en la misma '
                'columna. Se evalúa el panorama general. Si la mayoría de los '
                'indicadores apuntan a "mediana", la aplicación se clasifica '
                'como mediana, incluso si una dimensión cae en otra columna.'
            ),
        },
    }


def _categories_section(order):
    return {
        'section_type': 'categories',
        'title': 'Categorías Evaluadas',
        'order': order,
        'visibility': 'both',
        'is_enabled': True,
        'content_json': {
            'index': '3',
            'title': 'Categorías que se evalúan en el diagnóstico',
            'intro': (
                'Por cada categoría, la entrega del diagnóstico incluye lo que '
                'se encontró bien, los hallazgos con su nivel de severidad y '
                'las recomendaciones asociadas.'
            ),
            'categories': CATEGORIES,
        },
    }


def _delivery_structure_section(order):
    return {
        'section_type': 'delivery_structure',
        'title': 'Estructura de la Entrega',
        'order': order,
        'visibility': 'initial',
        'is_enabled': True,
        'content_json': {
            'index': '4',
            'title': 'Estructura de la Entrega',
            'intro': (
                'Para cada categoría evaluada, la entrega del diagnóstico '
                'incluirá las siguientes secciones:'
            ),
            'blocks': DELIVERY_STRUCTURE_BLOCKS,
        },
    }


def _executive_summary_section(order):
    return {
        'section_type': 'executive_summary',
        'title': 'Resumen Ejecutivo',
        'order': order,
        'visibility': 'final',
        'is_enabled': True,
        'content_json': {
            'index': '5',
            'title': 'Resumen Ejecutivo',
            'intro': (
                'La entrega incluye un resumen ejecutivo con el conteo de '
                'hallazgos por nivel y un párrafo que resume el estado general '
                'de la aplicación en lenguaje claro, sin tecnicismos '
                'innecesarios, orientado a que cualquier tomador de decisión '
                'pueda entender la situación.'
            ),
            'severityCounts': {
                'critico': 0,
                'alto': 0,
                'medio': 0,
                'bajo': 0,
            },
            'narrative': '',
            'highlights': [],
        },
    }


def _cost_section(order):
    return {
        'section_type': 'cost',
        'title': 'Costo y Formas de Pago',
        'order': order,
        'visibility': 'both',
        'is_enabled': True,
        'content_json': {
            'index': '6',
            'title': 'Costo y Formas de Pago',
            'intro': (
                'Antes de invertir en cambios, conviene invertir en claridad. '
                'El diagnóstico es un ejercicio acotado que convierte intuiciones '
                'en evidencia y te entrega una base concreta para decidir qué '
                'mover, qué sostener y en qué orden.'
            ),
            'valueBullets': [
                'Claridad técnica accionable: un mapa del estado real de la '
                'aplicación, sin tecnicismos vacíos, listo para tomar decisiones.',
                'Priorización de inversión: identificas qué cambios mueven la '
                'aguja del negocio y cuáles son ruido, evitando gastar en '
                'reescribir lo que ya funciona.',
                'Reducción de riesgo silencioso: detectas el sobrecosto técnico '
                'y los puntos frágiles antes de que se conviertan en incidentes '
                'o frenos al crecimiento.',
                'Conversación informada con el equipo: una referencia común — '
                'propia o con proveedores externos — para alinear alcance, '
                'tiempos y expectativas a partir de hechos, no de opiniones.',
            ],
            'paymentDescription': [
                {
                    'label': 'al inicio',
                    'detail': (
                        'para dar apertura formal al diagnóstico y reservar '
                        'la dedicación del equipo.'
                    ),
                },
                {
                    'label': 'al final',
                    'detail': (
                        'contra entrega del informe y socialización de '
                        'hallazgos con el equipo.'
                    ),
                },
            ],
            'note': '',
        },
    }


def _timeline_section(order):
    return {
        'section_type': 'timeline',
        'title': 'Cronograma',
        'order': order,
        'visibility': 'both',
        'is_enabled': True,
        'content_json': {
            'index': '7',
            'title': 'Cronograma',
            'intro': (
                'La duración estimada del diagnóstico se muestra a '
                'continuación.'
            ),
            'distributionTitle': 'Distribución general',
            'distribution': TIMELINE_DISTRIBUTION,
        },
    }


def _scope_section(order):
    return {
        'section_type': 'scope',
        'title': 'Alcance y Consideraciones',
        'order': order,
        'visibility': 'both',
        'is_enabled': True,
        'content_json': {
            'index': '8',
            'title': 'Alcance y Consideraciones',
            'considerations': list(SCOPE_CONSIDERATIONS),
        },
    }


_ENGLISH_SECTION_TITLES = {
    'purpose': 'Purpose',
    'radiography': 'Application Overview',
    'categories': 'Evaluation Categories',
    'delivery_structure': 'Deliverable Structure',
    'executive_summary': 'Executive Summary',
    'cost': 'Cost and Payment Terms',
    'timeline': 'Timeline',
    'scope': 'Scope and Considerations',
}


def default_sections(language: str = 'es') -> list[dict]:
    """Return the ordered seed payload for a newly created diagnostic."""
    sections = [
        _purpose_section(1),
        _radiography_section(2),
        _categories_section(3),
        _delivery_structure_section(4),
        _executive_summary_section(5),
        _cost_section(6),
        _timeline_section(7),
        _scope_section(8),
    ]
    if language == 'en':
        for section in sections:
            title = _ENGLISH_SECTION_TITLES[section['section_type']]
            section['title'] = title
            section['content_json']['title'] = title
    return sections
