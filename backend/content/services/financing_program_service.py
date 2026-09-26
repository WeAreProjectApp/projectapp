"""Canonical bilingual content for Project App.'s financing program."""

import copy
from urllib.parse import quote

from content.models import HourPackage, Nationality
from content.services.financing_policy_service import (
    current_policy,
    minimum_initial_payment_percent,
)


WHATSAPP_NUMBER = '573238122373'
INCLUDED_PACKAGE_HOURS = 60


PROGRAM_CONTENT = {
    'es': {
        'hero': {
            'eyebrow': 'Programa de Alianza para productos con visión de largo plazo',
            'title': 'Construimos hoy. Crecemos contigo.',
            'subtitle': (
                'Project App. puede financiar el desarrollo e implementación de '
                'productos de software en los que identifica valor y potencial '
                'sostenible. Entregamos antes de recuperar la totalidad de la '
                'inversión y compartimos el riesgo operativo del proyecto.'
            ),
            'trust_note': (
                'Una alternativa para convertir una buena oportunidad en un producto '
                'real sin trasladar todo el esfuerzo financiero al inicio.'
            ),
        },
        'eligibility': {
            'title': 'Un programa sujeto a evaluación',
            'summary': (
                'Cada solicitud pasa por una revisión técnica, comercial y de riesgo. '
                'La propuesta aprobada define el aporte inicial —si aplica—, el saldo '
                'financiado, las fases incluidas y la fecha de entrada a producción.'
            ),
            'badge': 'Aprobación previa',
        },
        'options': [
            {
                'id': 'five-year',
                'name': 'Alianza a 5 años',
                'badge': 'Recomendada',
                'summary': (
                    'La opción de mayor continuidad: financiación, exclusividad, '
                    'custodia de código, calculadora de requerimientos y un paquete '
                    'mensual de 60 horas incluido sin costo adicional. Añade exclusividad '
                    'conceptual de Project App. para el mismo sector, nicho y tipo '
                    'de proyecto durante la alianza. Cuando el '
                    'primer ciclo se paga por completo, puede habilitar un segundo '
                    'ciclo de 12 meses sujeto a una nueva evaluación de riesgo.'
                ),
                'exclusivity_years': 5,
                'financing_cycles': 2,
                'recommended': True,
                'hour_package_included': True,
                'highlights': [
                    'Hasta dos ciclos separados de 12 meses al 0% de interés ordinario.',
                    'El segundo exige pago íntegro del primero y una nueva aprobación.',
                    '60 horas disponibles cada mes desde la salida a producción.',
                    'Exclusividad conceptual a cargo de Project App. durante los cinco años.',
                ],
            },
            {
                'id': 'three-year',
                'name': 'Alianza a 3 años',
                'badge': 'Alternativa',
                'summary': (
                    'Conserva la financiación, la exclusividad, la custodia del código '
                    'y la transparencia de la calculadora, pero no incluye el paquete '
                    'mensual de horas ni la exclusividad conceptual a cargo de Project App.'
                ),
                'exclusivity_years': 3,
                'financing_cycles': 1,
                'recommended': False,
                'hour_package_included': False,
                'highlights': [
                    '12 meses de financiación al 0% de interés ordinario.',
                    'Tres años de continuidad bajo el acuerdo de exclusividad.',
                    'Requerimientos futuros cotizados de forma independiente.',
                    'Sin el compromiso adicional de exclusividad conceptual de la opción a cinco años.',
                ],
            },
        ],
        'conditions': [
            {
                'id': 'financing',
                'number': '01',
                'icon': '↗',
                'title': '12 meses de financiación',
                'summary': (
                    'Financiamos el saldo aprobado del desarrollo e implementación de '
                    'un producto de software o de una o varias de sus fases.'
                ),
                'commercial_reason': (
                    'El 0% de interés ordinario permite dirigir el capital inicial a '
                    'validar, operar y hacer crecer el producto mientras el desarrollo '
                    'se paga en un plazo predecible.'
                ),
                'highlights': [
                    'Plazo de financiación: 12 meses.',
                    'Interés ordinario: 0%.',
                    'El saldo aprobado se define después del aporte inicial, si aplica.',
                ],
            },
            {
                'id': 'exclusivity',
                'number': '02',
                'icon': '◇',
                'title': 'Exclusividad y custodia responsable',
                'summary': (
                    'Al financiar y participar en la operación, Project App. asume '
                    'parte del riesgo de éxito del proyecto y se convierte en su casa '
                    'desarrolladora durante el periodo acordado.'
                ),
                'commercial_reason': (
                    'La continuidad con un solo equipo protege las decisiones técnicas, '
                    'reduce la pérdida de contexto y permite responder por la estabilidad '
                    'del producto que también estamos ayudando a financiar.'
                ),
                'highlights': [
                    'Cinco años en la opción recomendada o tres años en la alternativa.',
                    'Custodia segura de repositorios, versiones, respaldos y accesos.',
                    'La custodia no transfiere la propiedad intelectual a Project App.',
                ],
            },
            {
                'id': 'calculator',
                'number': '03',
                'icon': '◎',
                'title': 'Calculadora de requerimientos',
                'summary': (
                    'Una herramienta de transparencia para anticipar el esfuerzo, el '
                    'trabajo, el tiempo y el rango de precio de cambios futuros.'
                ),
                'commercial_reason': (
                    'Antes de comprometer presupuesto, el cliente obtiene una lectura '
                    'comparable del requerimiento y puede decidir con mayor claridad '
                    'qué priorizar y cuándo ejecutarlo.'
                ),
                'highlights': [
                    'Recibe una descripción clara y el contexto esencial del cambio.',
                    'Entrega nivel de esfuerzo, tiempo estimado y rango de inversión.',
                    'El resultado orienta; la cotización formal confirma el alcance.',
                ],
            },
            {
                'id': 'hour-package',
                'number': '04',
                'icon': '◷',
                'title': '60 horas disponibles cada mes',
                'summary': (
                    'La alianza a cinco años incluye el Paquete Pro para implementar '
                    'requerimientos aprobados después de la salida a producción.'
                ),
                'commercial_reason': (
                    'El producto puede seguir evolucionando sin abrir una negociación '
                    'desde cero por cada ajuste pequeño, manteniendo capacidad técnica '
                    'previsible durante la operación.'
                ),
                'highlights': [
                    '60 horas que se renuevan al iniciar cada mes.',
                    'Las horas no utilizadas no se acumulan.',
                    'Disponible únicamente en la opción de exclusividad a cinco años.',
                ],
            },
            {
                'id': 'payment-discipline',
                'number': '05',
                'icon': '%',
                'title': 'Pagos claros y cobertura del riesgo de impago',
                'summary': (
                    'Cada cuota se paga dentro de los primeros cinco días calendario '
                    'del mes. Una cuota en mora aumenta en 2% el costo vigente del Hosting.'
                ),
                'commercial_reason': (
                    'La regla hace visible desde el inicio el costo de incumplir y '
                    'compensa gradualmente el riesgo que Project App. asume al entregar '
                    'y operar antes de recuperar la totalidad de la inversión.'
                ),
                'highlights': [
                    'El aumento se aplica por cada cuota que entre en mora.',
                    'Los incrementos son acumulativos y permanentes.',
                    'Opera automáticamente desde el vencimiento y no sustituye la cuota pendiente.',
                ],
            },
            {
                'id': 'conceptual-exclusivity',
                'number': '08',
                'icon': '◇',
                'title': 'Exclusividad conceptual — sólo a 5 años',
                'summary': (
                    'Al elegir la alianza de cinco años, Project App. renuncia durante '
                    'esa vigencia a desarrollar para otros clientes proyectos '
                    'competidores del mismo sector y nicho que reproduzcan conceptos, '
                    'ideas o enfoques específicos del producto acordado.'
                ),
                'commercial_reason': (
                    'El compromiso protege la diferenciación del producto y alinea '
                    'nuestra participación con su crecimiento: las decisiones '
                    'conceptuales trabajadas contigo no se trasladan a un proyecto '
                    'equivalente para un competidor en el mismo mercado.'
                ),
                'highlights': [
                    'Beneficio exclusivo de la modalidad a cinco años; no aplica a la de tres.',
                    'Mismo sector, mismo nicho y proyecto equivalente con finalidad competidora.',
                    'Prohíbe reproducir o adaptar para terceros los conceptos, ideas y enfoques específicos acordados.',
                    'El alcance se delimita por escrito en la propuesta y el contrato.',
                ],
            },
        ],
        'calculator': {
            'eyebrow': 'Transparencia para decidir',
            'title': 'De una necesidad en palabras a un rango útil para planear',
            'summary': (
                'No necesitas conocer una metodología técnica. La herramienta toma el '
                'requerimiento en lenguaje natural y devuelve una referencia comercial '
                'consistente para conversar sobre prioridad, tiempo y presupuesto.'
            ),
            'input': {
                'title': 'Qué se ingresa',
                'items': [
                    'Descripción en lenguaje natural de lo que se necesita.',
                    'Objetivo o resultado esperado para el usuario o el negocio.',
                    'Contexto esencial del producto, restricciones e integraciones conocidas.',
                ],
            },
            'output': {
                'title': 'Qué se obtiene',
                'items': [
                    'Nivel relativo de esfuerzo, comunicado con una talla de referencia (XS–XL).',
                    'Trabajo y tiempo estimados para implementar el requerimiento.',
                    'Rango de precio, supuestos y aspectos que requieren definición.',
                ],
            },
            'disclaimer': (
                'El resultado es orientativo y no reemplaza la validación técnica ni la '
                'cotización formal que fija alcance, cronograma y precio definitivo.'
            ),
        },
        'package': {
            'title': 'Capacidad mensual para la evolución del producto',
            'summary': (
                'El paquete está pensado principalmente para cambios pequeños y '
                'acotados —por ejemplo, requerimientos XS o S—. Un requerimiento de '
                'mayor tamaño puede consumir más capacidad, requerir varios ciclos o '
                'cotizarse y programarse por separado.'
            ),
            'renewal_label': 'Se renueva cada mes',
            'rollover_label': 'No acumula horas',
            'availability_label': 'Desde producción',
            'included_label': 'Incluido sin costo adicional',
        },
        'legal_terms': [
            {
                'id': 'approval',
                'title': 'Evaluación, aporte inicial y saldo aprobado',
                'summary': 'La financiación no es automática ni constituye una oferta abierta.',
                'items': [
                    'Project App. evalúa la viabilidad técnica, comercial y de riesgo del proyecto.',
                    'La propuesta puede establecer un aporte inicial antes de calcular el saldo financiado.',
                    'Sólo se financian las fases y entregables expresamente aprobados en la propuesta.',
                ],
            },
            {
                'id': 'interest',
                'title': 'Qué significa interés ordinario del 0%',
                'summary': 'El saldo aprobado no genera intereses ordinarios durante el plazo pactado.',
                'items': [
                    'El acuerdo formal define el calendario de pagos y las fechas de exigibilidad.',
                    'Mora, incumplimiento y costos derivados se rigen por el contrato firmado.',
                    'Impuestos, licencias y servicios de terceros no se entienden incluidos salvo mención expresa.',
                ],
            },
            {
                'id': 'late-payment-hosting',
                'title': 'Mora y aumento del costo del Hosting',
                'summary': 'La fecha y la consecuencia se conocen antes de firmar.',
                'items': [
                    'Cada cuota debe pagarse dentro de los primeros cinco días calendario del mes correspondiente.',
                    'Por cada cuota en mora, el costo vigente del Hosting aumenta en 2%; los aumentos son acumulativos y permanentes.',
                    'El aumento opera automáticamente desde el vencimiento, sin requerimiento previo, y no extingue la cuota pendiente.',
                    'La aplicación operativa se documenta y audita; este módulo no modifica automáticamente registros de Hosting o contabilidad.',
                ],
            },
            {
                'id': 'second-cycle',
                'title': 'Segundo ciclo en la alianza de cinco años',
                'summary': 'La modalidad recomendada puede financiar una nueva etapa sin reiniciar la alianza.',
                'items': [
                    'La alianza de cinco años permite hasta dos ciclos separados de financiación de 12 meses.',
                    'El segundo requiere que el primer ciclo esté pagado íntegramente y una nueva aprobación manual de riesgo.',
                    'Una mora ya subsanada no impide por sí sola la evaluación del segundo ciclo.',
                    'El segundo calendario debe terminar dentro de la vigencia original y no reinicia ni extiende la exclusividad.',
                ],
            },
            {
                'id': 'exclusivity-scope',
                'title': 'Alcance y vigencia de la exclusividad',
                'summary': 'La exclusividad se limita al producto financiado y al periodo elegido.',
                'items': [
                    'Comprende desarrollo, mantenimiento, soporte, infraestructura, actualizaciones y continuidad técnica del producto.',
                    'No restringe otros productos o iniciativas del cliente que no formen parte del proyecto financiado.',
                    'La vigencia se cuenta desde la salida a producción definida en el acuerdo formal.',
                ],
            },
            {
                'id': 'conceptual-exclusivity-scope',
                'title': 'No competencia conceptual en la alianza a cinco años',
                'summary': 'Un compromiso de Project App. limitado al producto, su mercado y la vigencia pactada.',
                'items': [
                    'Aplica únicamente al elegir la modalidad de cinco años y durante su vigencia original; un segundo ciclo no reinicia ni extiende este plazo.',
                    'Project App. se obliga a no desarrollar, reproducir ni adaptar para otros clientes conceptos, ideas o enfoques específicos trabajados para el producto en proyectos iguales o sustancialmente similares que compitan en el mismo sector y nicho.',
                    'La propuesta y el contrato delimitan por escrito el sector, el nicho, el producto y los conceptos o enfoques comprendidos. La restricción requiere la coincidencia de ese ámbito y una finalidad competidora.',
                    'No supone una prohibición general de atender todo el sector ni impide usar conocimientos técnicos generales, herramientas o componentes reutilizables, siempre que no se reproduzca el planteamiento específico protegido ni se revele información confidencial.',
                    'Es un compromiso contractual entre las partes, sin atribuir propiedad sobre ideas generales. Las obligaciones de confidencialidad, propiedad intelectual y las normas de competencia desleal que resulten aplicables se respetan en ambas modalidades.',
                ],
            },
            {
                'id': 'code-custody',
                'title': 'Custodia de código no es cesión de propiedad',
                'summary': 'Project App. protege la continuidad técnica sin apropiarse del producto.',
                'items': [
                    'La custodia abarca repositorios, control de versiones, respaldos, accesos e integridad del código.',
                    'No implica transferencia de propiedad intelectual ni autorización de explotación comercial por Project App.',
                    'La cesión de derechos patrimoniales acordada opera cuando se completa el pago íntegro y se formaliza la entrega con el acta correspondiente, conforme al contrato; la custodia sólo difiere la entrega material.',
                    'La entrega del código y los repositorios ocurre al finalizar la custodia y cumplir las obligaciones pactadas, mediante acta de entrega.',
                ],
            },
            {
                'id': 'package-rules',
                'title': 'Uso y renovación del paquete mensual',
                'summary': 'La capacidad existe para mantener un ritmo sostenible de evolución.',
                'items': [
                    'Está disponible sólo en la alianza a cinco años, desde la salida a producción y mientras el acuerdo esté vigente y al día.',
                    'Las 60 horas se reinician cada mes; el saldo no utilizado expira y no se traslada al siguiente periodo.',
                    'Cada requerimiento debe validarse, priorizarse y programarse según la capacidad disponible.',
                ],
            },
            {
                'id': 'calculator-reference',
                'title': 'Resultado referencial de la calculadora',
                'summary': 'La herramienta mejora la visibilidad, pero no reemplaza una propuesta.',
                'items': [
                    'El cálculo depende de la información disponible al momento de describir el requerimiento.',
                    'Cambios de alcance, dependencias o integraciones pueden modificar el esfuerzo estimado.',
                    'La cotización formal aprobada por ambas partes es la que fija el compromiso final.',
                ],
            },
            {
                'id': 'formal-agreement',
                'title': 'El acuerdo formal prevalece',
                'summary': 'Este módulo es informativo y presenta las reglas comerciales principales.',
                'items': [
                    'La propuesta y el contrato definen valores, entregables, cronograma, garantías y consecuencias de incumplimiento.',
                    'Hosting, soporte recurrente, infraestructura, licencias, terceros e impuestos se excluyen salvo inclusión expresa.',
                    'Cualquier excepción debe constar por escrito y ser aceptada por ambas partes.',
                ],
            },
        ],
        'cta': {
            'eyebrow': 'Conversemos sobre el potencial del proyecto',
            'title': 'Solicita tu evaluación para el Programa de Alianza',
            'body': (
                'Cuéntanos qué producto quieres construir, qué etapa necesitas financiar '
                'y cuál es el resultado que esperas alcanzar.'
            ),
            'button': 'Hablar por WhatsApp',
            'message': (
                'Hola, quiero solicitar una evaluación de mi proyecto de software '
                'para el Programa de Alianza de Project App.'
            ),
        },
        'disclaimer': (
            'Información comercial de referencia. La aprobación y las condiciones '
            'definitivas dependen de la propuesta y del contrato suscrito por las partes.'
        ),
    },
    'en': {
        'hero': {
            'eyebrow': 'Partnership Program for products built with a long-term vision',
            'title': 'We build today. We grow with you.',
            'subtitle': (
                'Project App. may finance the development and implementation of '
                'software products where it identifies sustainable value and potential. '
                'We deliver before recovering the full investment and share the '
                'project’s operational risk.'
            ),
            'trust_note': (
                'An alternative for turning a strong opportunity into a real product '
                'without placing the entire financial effort at the beginning.'
            ),
        },
        'eligibility': {
            'title': 'A program subject to evaluation',
            'summary': (
                'Each request goes through technical, commercial, and risk review. The '
                'approved proposal defines the initial contribution—if applicable—the '
                'financed balance, included phases, and production date.'
            ),
            'badge': 'Prior approval',
        },
        'options': [
            {
                'id': 'five-year',
                'name': '5-year partnership',
                'badge': 'Recommended',
                'summary': (
                    'The highest-continuity option: financing, exclusivity, code '
                    'custody, the requirement calculator, and a monthly 60-hour package '
                    'included at no additional cost. It adds conceptual exclusivity '
                    'by Project App. for the same sector, niche, and type of project '
                    'during the partnership. Once the first cycle is fully '
                    'paid, a second 12-month cycle may be approved after a new risk review.'
                ),
                'exclusivity_years': 5,
                'financing_cycles': 2,
                'recommended': True,
                'hour_package_included': True,
                'highlights': [
                    'Up to two separate 12-month cycles at 0% ordinary interest.',
                    'The second requires full payment of the first and a new approval.',
                    '60 hours available each month after production starts.',
                    'Conceptual exclusivity by Project App. throughout the five-year term.',
                ],
            },
            {
                'id': 'three-year',
                'name': '3-year partnership',
                'badge': 'Alternative',
                'summary': (
                    'Keeps financing, exclusivity, code custody, and calculator '
                    'transparency, but does not include the monthly hour package '
                    'or conceptual exclusivity by Project App.'
                ),
                'exclusivity_years': 3,
                'financing_cycles': 1,
                'recommended': False,
                'hour_package_included': False,
                'highlights': [
                    '12-month financing at 0% ordinary interest.',
                    'Three years of continuity under the exclusivity agreement.',
                    'Future requirements quoted independently.',
                    'Excludes the additional conceptual exclusivity commitment of the five-year option.',
                ],
            },
        ],
        'conditions': [
            {
                'id': 'financing',
                'number': '01',
                'icon': '↗',
                'title': '12 months of financing',
                'summary': (
                    'We finance the approved balance for developing and implementing a '
                    'software product or one or more of its phases.'
                ),
                'commercial_reason': (
                    '0% ordinary interest lets the initial capital support validation, '
                    'operations, and growth while development is paid over a '
                    'predictable period.'
                ),
                'highlights': [
                    'Financing term: 12 months.',
                    'Ordinary interest: 0%.',
                    'The approved balance is defined after any applicable initial contribution.',
                ],
            },
            {
                'id': 'exclusivity',
                'number': '02',
                'icon': '◇',
                'title': 'Exclusivity and responsible custody',
                'summary': (
                    'By financing and joining the operation, Project App. assumes part '
                    'of the project’s success risk and becomes its software development '
                    'partner for the agreed period.'
                ),
                'commercial_reason': (
                    'Continuity with one team protects technical decisions, reduces '
                    'context loss, and lets us remain accountable for the stability of '
                    'the product we are helping finance.'
                ),
                'highlights': [
                    'Five years in the recommended option or three years in the alternative.',
                    'Secure custody of repositories, versions, backups, and access.',
                    'Custody does not transfer intellectual property to Project App.',
                ],
            },
            {
                'id': 'calculator',
                'number': '03',
                'icon': '◎',
                'title': 'Requirement calculator',
                'summary': (
                    'A transparency tool that anticipates the effort, work, time, and '
                    'price range of future changes.'
                ),
                'commercial_reason': (
                    'Before committing budget, the client gets a comparable view of the '
                    'requirement and can decide more clearly what to prioritize and when '
                    'to execute it.'
                ),
                'highlights': [
                    'Receives a clear description and the essential context of the change.',
                    'Returns effort level, estimated time, and investment range.',
                    'The result guides the conversation; a formal quote confirms scope.',
                ],
            },
            {
                'id': 'hour-package',
                'number': '04',
                'icon': '◷',
                'title': '60 hours available every month',
                'summary': (
                    'The five-year partnership includes the Pro Pack to implement '
                    'approved requirements after the product enters production.'
                ),
                'commercial_reason': (
                    'The product can keep evolving without reopening a negotiation for '
                    'every small adjustment, with predictable technical capacity '
                    'throughout operations.'
                ),
                'highlights': [
                    '60 hours renew at the beginning of every month.',
                    'Unused hours do not roll over.',
                    'Available only with the five-year exclusivity option.',
                ],
            },
            {
                'id': 'payment-discipline',
                'number': '05',
                'icon': '%',
                'title': 'Clear payments and non-payment risk coverage',
                'summary': (
                    'Each installment is due within the first five calendar days of '
                    'the month. A late installment increases the current Hosting cost by 2%.'
                ),
                'commercial_reason': (
                    'The rule makes the cost of default visible from the outset and '
                    'gradually offsets the risk Project App. assumes by delivering and '
                    'operating before recovering the full investment.'
                ),
                'highlights': [
                    'The increase applies for each installment that becomes overdue.',
                    'Increases are cumulative and permanent.',
                    'It applies automatically at default and does not replace the unpaid installment.',
                ],
            },
            {
                'id': 'conceptual-exclusivity',
                'number': '08',
                'icon': '◇',
                'title': 'Conceptual exclusivity — five-year option only',
                'summary': (
                    'By choosing the five-year partnership, Project App. agrees for '
                    'that term not to develop competing projects for other clients '
                    'in the same sector and niche that reproduce specific concepts, '
                    'ideas, or approaches from the agreed product.'
                ),
                'commercial_reason': (
                    'This commitment protects the product’s differentiation and aligns '
                    'our participation with its growth: conceptual decisions developed '
                    'with you are not transferred to an equivalent project for a '
                    'competitor in the same market.'
                ),
                'highlights': [
                    'Exclusive to the five-year option; it does not apply to the three-year option.',
                    'The same sector, the same niche, and an equivalent project with a competing purpose.',
                    'Prohibits reproducing or adapting the agreed specific concepts, ideas, and approaches for third parties.',
                    'The proposal and contract define the scope in writing.',
                ],
            },
        ],
        'calculator': {
            'eyebrow': 'Transparency for better decisions',
            'title': 'From a need in plain language to a useful planning range',
            'summary': (
                'You do not need to know a technical methodology. The tool takes a '
                'plain-language requirement and returns a consistent commercial '
                'reference for discussing priority, time, and budget.'
            ),
            'input': {
                'title': 'What goes in',
                'items': [
                    'A plain-language description of what is needed.',
                    'The intended result for the user or the business.',
                    'Essential product context, constraints, and known integrations.',
                ],
            },
            'output': {
                'title': 'What comes out',
                'items': [
                    'A relative effort level expressed through a reference size (XS–XL).',
                    'Estimated work and time needed to implement the requirement.',
                    'A price range, assumptions, and aspects that still need definition.',
                ],
            },
            'disclaimer': (
                'The result is indicative and does not replace technical validation or '
                'the formal quote that establishes final scope, schedule, and price.'
            ),
        },
        'package': {
            'title': 'Monthly capacity for product evolution',
            'summary': (
                'The package is intended mainly for small, bounded changes—for example, '
                'XS or S requirements. A larger requirement may use more capacity, '
                'require multiple cycles, or be quoted and scheduled separately.'
            ),
            'renewal_label': 'Renews every month',
            'rollover_label': 'Hours do not roll over',
            'availability_label': 'Available from production',
            'included_label': 'Included at no additional cost',
        },
        'legal_terms': [
            {
                'id': 'approval',
                'title': 'Evaluation, initial contribution, and approved balance',
                'summary': 'Financing is not automatic and is not an open offer.',
                'items': [
                    'Project App. evaluates the project’s technical, commercial, and risk viability.',
                    'The proposal may establish an initial contribution before calculating the financed balance.',
                    'Only phases and deliverables expressly approved in the proposal are financed.',
                ],
            },
            {
                'id': 'interest',
                'title': 'What 0% ordinary interest means',
                'summary': 'The approved balance generates no ordinary interest during the agreed term.',
                'items': [
                    'The formal agreement defines the payment schedule and due dates.',
                    'Late payment, default, and related costs are governed by the signed contract.',
                    'Taxes, licenses, and third-party services are excluded unless expressly included.',
                ],
            },
            {
                'id': 'late-payment-hosting',
                'title': 'Late payment and Hosting cost increase',
                'summary': 'The deadline and consequence are known before signing.',
                'items': [
                    'Each installment must be paid within the first five calendar days of its corresponding month.',
                    'For every overdue installment, the current Hosting cost increases by 2%; increases are cumulative and permanent.',
                    'The increase applies automatically from the due date, without prior notice, and does not extinguish the unpaid installment.',
                    'Operational application is documented and audited; this module does not automatically alter Hosting or accounting records.',
                ],
            },
            {
                'id': 'second-cycle',
                'title': 'Second cycle in the five-year partnership',
                'summary': 'The recommended option may finance a new stage without restarting the partnership.',
                'items': [
                    'The five-year partnership permits up to two separate 12-month financing cycles.',
                    'The second requires full payment of the first and a new manual risk approval.',
                    'A cured late payment does not by itself prevent the second-cycle review.',
                    'The second schedule must finish within the original term and does not restart or extend exclusivity.',
                ],
            },
            {
                'id': 'exclusivity-scope',
                'title': 'Scope and term of exclusivity',
                'summary': 'Exclusivity is limited to the financed product and selected period.',
                'items': [
                    'It covers development, maintenance, support, infrastructure, updates, and technical continuity for the product.',
                    'It does not restrict unrelated client products or initiatives outside the financed project.',
                    'The term begins on the production date defined in the formal agreement.',
                ],
            },
            {
                'id': 'conceptual-exclusivity-scope',
                'title': 'Conceptual non-compete in the five-year partnership',
                'summary': 'A commitment by Project App. limited to the product, its market, and the agreed term.',
                'items': [
                    'It applies only when the five-year option is chosen and during its original term; a second cycle does not restart or extend this period.',
                    'Project App. undertakes not to develop, reproduce, or adapt for other clients specific concepts, ideas, or approaches developed for the product in identical or substantially similar projects competing in the same sector and niche.',
                    'The proposal and contract define the sector, niche, product, and covered concepts or approaches in writing. The restriction requires both a matching scope and a competing purpose.',
                    'It is not a general ban on serving the entire sector and does not prevent the use of general technical knowledge, tools, or reusable components, provided the protected specific approach is not reproduced and confidential information is not disclosed.',
                    'This is a contractual commitment between the parties, without claiming ownership of general ideas. Confidentiality, intellectual property obligations, and applicable unfair competition rules are respected under both options.',
                ],
            },
            {
                'id': 'code-custody',
                'title': 'Code custody is not ownership transfer',
                'summary': 'Project App. protects technical continuity without taking ownership of the product.',
                'items': [
                    'Custody covers repositories, version control, backups, access, and code integrity.',
                    'It does not transfer intellectual property or authorize commercial exploitation by Project App.',
                    'The agreed assignment of economic rights takes effect once full payment is completed and delivery is formalized with the corresponding delivery record, as set out in the contract; custody only defers physical delivery.',
                    'Code and repositories are delivered through a delivery record after custody ends and the agreed obligations are fulfilled.',
                ],
            },
            {
                'id': 'package-rules',
                'title': 'Monthly package use and renewal',
                'summary': 'The capacity supports a sustainable pace of evolution.',
                'items': [
                    'It is available only in the five-year partnership, after production starts, while the agreement is active and current.',
                    'The 60 hours reset each month; unused capacity expires and does not move to the next period.',
                    'Each requirement must be validated, prioritized, and scheduled against available capacity.',
                ],
            },
            {
                'id': 'calculator-reference',
                'title': 'The calculator result is referential',
                'summary': 'The tool improves visibility but does not replace a proposal.',
                'items': [
                    'The calculation depends on the information available when the requirement is described.',
                    'Scope, dependency, or integration changes can modify the estimated effort.',
                    'The formal quote approved by both parties establishes the final commitment.',
                ],
            },
            {
                'id': 'formal-agreement',
                'title': 'The formal agreement prevails',
                'summary': 'This module is informational and presents the main commercial rules.',
                'items': [
                    'The proposal and contract define amounts, deliverables, schedule, warranties, and default consequences.',
                    'Hosting, recurring support, infrastructure, licenses, third parties, and taxes are excluded unless expressly included.',
                    'Any exception must be recorded in writing and accepted by both parties.',
                ],
            },
        ],
        'cta': {
            'eyebrow': 'Let’s discuss the project’s potential',
            'title': 'Request your Partnership Program evaluation',
            'body': (
                'Tell us what product you want to build, which stage you need to '
                'finance, and the outcome you expect to achieve.'
            ),
            'button': 'Talk on WhatsApp',
            'message': (
                'Hi, I would like to request a Partnership Program evaluation '
                'for my software project with Project App.'
            ),
        },
        'disclaimer': (
            'Commercial information for reference. Approval and final conditions '
            'depend on the proposal and contract signed by the parties.'
        ),
    },
}


def _included_package(language):
    package = HourPackage.objects.filter(
        nationality=Nationality.COL,
        hours=INCLUDED_PACKAGE_HOURS,
        is_active=True,
    ).order_by('order', 'id').first()
    suffix = 'en' if language == 'en' else 'es'
    return {
        'name': (
            getattr(package, f'name_{suffix}')
            if package
            else ('Pro Pack' if language == 'en' else 'Paquete Pro')
        ),
        'hours': INCLUDED_PACKAGE_HOURS,
        'renews_monthly': True,
        'rollover': False,
        'catalog_synced': package is not None,
    }


def _percent(value):
    return format(value, 'f').rstrip('0').rstrip('.')


def _cop(value, language):
    whole = int(value)
    grouped = f'{whole:,}'
    if language == 'es':
        return f'$ {grouped.replace(",", ".")} COP'
    return f'COP {grouped}'


def _apply_policy_content(payload, policy, language):
    months = policy.financing_months
    minimum = _cop(policy.minimum_project_value_cop, language)
    maximum = _cop(policy.maximum_project_value_cop, language)
    maximum_percent = _percent(policy.maximum_financed_percent)
    minimum_percent = _percent(minimum_initial_payment_percent(policy))
    late_percent = _percent(policy.late_hosting_increase_percent)
    due_start = policy.installment_due_day_start
    due_end = policy.installment_due_day_end
    five_year, three_year = payload['options']
    financing = payload['conditions'][0]
    payment = payload['conditions'][4]
    terms = {term['id']: term for term in payload['legal_terms']}

    if language == 'es':
        payload['eligibility']['summary'] = (
            f'Aplican proyectos, fases o conjuntos de fases con un valor total entre '
            f'{minimum} y {maximum}, ambos inclusive. Cada solicitud pasa por una '
            f'revisión técnica, comercial y de riesgo que define el aporte inicial '
            f'—mínimo {minimum_percent}%— y el saldo aprobado.'
        )
        five_year['summary'] = (
            'La opción de mayor continuidad: financiación, exclusividad, custodia '
            'de código, calculadora de requerimientos y un paquete mensual de 60 '
            'horas incluido. Añade exclusividad conceptual de Project App. para '
            'el mismo sector, nicho y tipo de proyecto durante la alianza. '
            f'Al pagar el primer ciclo, puede habilitarse un segundo '
            f'ciclo de {months} meses sujeto a una nueva evaluación de riesgo.'
        )
        five_year['highlights'][0] = (
            f'Hasta dos ciclos separados de {months} meses al 0% de interés ordinario.'
        )
        three_year['highlights'][0] = (
            f'{months} meses de financiación al 0% de interés ordinario.'
        )
        financing['title'] = f'{months} meses de financiación'
        financing['highlights'] = [
            f'Plazo de financiación: {months} meses.',
            'Interés ordinario: 0%.',
            f'Se financia hasta el {maximum_percent}% del valor aprobado.',
        ]
        payment['summary'] = (
            f'Cada cuota se paga entre los días {due_start} y {due_end} calendario '
            f'del mes. Una cuota en mora aumenta en {late_percent}% el costo vigente '
            'del Hosting.'
        )
        # Keep the policy conditions before the five-year-only condition (08).
        payload['conditions'][5:5] = [
            {
                'id': 'project-value-range',
                'number': '06',
                'icon': '◆',
                'title': 'Un rango claro para aplicar',
                'summary': (
                    f'El proyecto, una fase o el conjunto de fases a financiar debe '
                    f'tener un valor total entre {minimum} y {maximum}, ambos inclusive.'
                ),
                'commercial_reason': (
                    'El rango concentra el programa en iniciativas donde la financiación '
                    'puede crear capacidad real de ejecución y mantiene una exposición '
                    'responsable para ambas partes.'
                ),
                'highlights': [
                    f'Monto mínimo elegible: {minimum}.',
                    f'Monto máximo elegible: {maximum}.',
                    'En USD se valida el equivalente en COP con la tasa congelada en el acuerdo.',
                ],
            },
            {
                'id': 'risk-and-initial-payment',
                'number': '07',
                'icon': '◒',
                'title': f'Análisis de riesgo y aporte desde el {minimum_percent}%',
                'summary': (
                    f'El primer pago se define mediante el análisis de riesgo y nunca '
                    f'será inferior al {minimum_percent}% del valor total. El saldo '
                    f'financiado puede llegar hasta el {maximum_percent}%.'
                ),
                'commercial_reason': (
                    'El aporte alinea el compromiso inicial del cliente con el riesgo '
                    'que Project App. asume al desarrollar y operar antes de recuperar '
                    'la totalidad de la inversión.'
                ),
                'highlights': [
                    'El análisis de riesgo define el porcentaje final del primer pago.',
                    f'Abono mínimo: {minimum_percent}% del valor total.',
                    f'Financiación máxima: {maximum_percent}% del valor aprobado.',
                ],
            },
        ]
        terms['approval']['items'] = [
            'Project App. evalúa la viabilidad técnica, comercial y de riesgo del proyecto.',
            f'El alcance debe sumar entre {minimum} y {maximum}, ambos inclusive.',
            f'El aporte inicial es como mínimo del {minimum_percent}%; el análisis puede exigir uno mayor.',
            'Sólo se financian las fases y entregables expresamente aprobados en la propuesta.',
        ]
        terms['late-payment-hosting']['items'][0] = (
            f'Cada cuota debe pagarse entre los días {due_start} y {due_end} calendario '
            'del mes correspondiente.'
        )
        terms['late-payment-hosting']['items'][1] = (
            f'Por cada cuota en mora, el costo vigente del Hosting aumenta en '
            f'{late_percent}%; los aumentos son acumulativos y permanentes.'
        )
        terms['second-cycle']['items'][0] = (
            f'La alianza de cinco años permite hasta dos ciclos separados de '
            f'financiación de {months} meses.'
        )
    else:
        payload['eligibility']['summary'] = (
            f'Eligible projects, phases, or phase groups have a total value from '
            f'{minimum} through {maximum}, inclusive. Every request undergoes a '
            f'technical, commercial, and risk review that sets the initial '
            f'contribution—at least {minimum_percent}%—and approved balance.'
        )
        five_year['summary'] = (
            'The highest-continuity option: financing, exclusivity, code custody, '
            'the requirement calculator, and an included monthly 60-hour package. '
            'It adds conceptual exclusivity by Project App. for the same sector, '
            'niche, and type of project during the partnership. '
            f'After the first cycle is paid, a second {months}-month cycle may be '
            'approved following a new risk review.'
        )
        five_year['highlights'][0] = (
            f'Up to two separate {months}-month cycles at 0% ordinary interest.'
        )
        three_year['highlights'][0] = (
            f'{months}-month financing at 0% ordinary interest.'
        )
        financing['title'] = f'{months} months of financing'
        financing['highlights'] = [
            f'Financing term: {months} months.',
            'Ordinary interest: 0%.',
            f'Up to {maximum_percent}% of the approved value is financed.',
        ]
        payment['summary'] = (
            f'Each installment is due between calendar days {due_start} and {due_end} '
            f'of the month. A late installment increases the current Hosting cost '
            f'by {late_percent}%.'
        )
        payload['conditions'][5:5] = [
            {
                'id': 'project-value-range',
                'number': '06',
                'icon': '◆',
                'title': 'A clear eligibility range',
                'summary': (
                    f'The project, phase, or phase group to be financed must have a '
                    f'total value from {minimum} through {maximum}, inclusive.'
                ),
                'commercial_reason': (
                    'The range focuses the program on initiatives where financing can '
                    'create meaningful execution capacity while keeping responsible '
                    'exposure for both parties.'
                ),
                'highlights': [
                    f'Minimum eligible amount: {minimum}.',
                    f'Maximum eligible amount: {maximum}.',
                    'USD agreements use the COP equivalent at the rate frozen in the agreement.',
                ],
            },
            {
                'id': 'risk-and-initial-payment',
                'number': '07',
                'icon': '◒',
                'title': f'Risk review and contribution from {minimum_percent}%',
                'summary': (
                    f'The risk review determines the first payment, which cannot be '
                    f'less than {minimum_percent}% of total value. The financed '
                    f'balance may reach up to {maximum_percent}%.'
                ),
                'commercial_reason': (
                    'The contribution aligns the client’s initial commitment with the '
                    'risk Project App. takes by developing and operating before the '
                    'investment is fully recovered.'
                ),
                'highlights': [
                    'The risk review sets the final first-payment percentage.',
                    f'Minimum contribution: {minimum_percent}% of total value.',
                    f'Maximum financing: {maximum_percent}% of approved value.',
                ],
            },
        ]
        terms['approval']['items'] = [
            'Project App. evaluates the project’s technical, commercial, and risk viability.',
            f'The scope must total from {minimum} through {maximum}, inclusive.',
            f'The initial contribution is at least {minimum_percent}%; the review may require more.',
            'Only phases and deliverables expressly approved in the proposal are financed.',
        ]
        terms['late-payment-hosting']['items'][0] = (
            f'Each installment must be paid between calendar days {due_start} and '
            f'{due_end} of its corresponding month.'
        )
        terms['late-payment-hosting']['items'][1] = (
            f'For every overdue installment, the current Hosting cost increases by '
            f'{late_percent}%; increases are cumulative and permanent.'
        )
        terms['second-cycle']['items'][0] = (
            f'The five-year partnership permits up to two separate {months}-month '
            'financing cycles.'
        )


def serialize_financing_program(*, language):
    """Return the localized public contract without internal prices or identifiers."""

    if language not in PROGRAM_CONTENT:
        raise ValueError('language must be es or en')

    policy = current_policy()
    payload = copy.deepcopy(PROGRAM_CONTENT[language])
    _apply_policy_content(payload, policy, language)
    payload.update({
        'language': language,
        'financing_months': policy.financing_months,
        'minimum_project_value_cop': policy.minimum_project_value_cop,
        'maximum_project_value_cop': policy.maximum_project_value_cop,
        'maximum_financed_percent': f'{_percent(policy.maximum_financed_percent)}%',
        'minimum_initial_payment_percent': (
            f'{_percent(minimum_initial_payment_percent(policy))}%'
        ),
        'ordinary_interest_rate': '0%',
        'late_hosting_increase_percent': (
            f'{_percent(policy.late_hosting_increase_percent)}%'
        ),
        'installment_due_day_range': [
            policy.installment_due_day_start,
            policy.installment_due_day_end,
        ],
        'canonical_path': (
            '/en-us/partnership-program'
            if language == 'en'
            else '/es-co/partnership-program'
        ),
    })
    payload['package'].update(_included_package(language))
    payload['cta']['whatsapp_url'] = (
        f'https://wa.me/{WHATSAPP_NUMBER}?text={quote(payload["cta"]["message"])}'
    )
    payload['cta'].pop('message')
    return payload
