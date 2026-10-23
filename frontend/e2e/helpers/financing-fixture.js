const content = {
  es: {
    hero: {
      eyebrow: 'Programa de Alianza para productos con visión de largo plazo',
      title: 'Construimos hoy. Crecemos contigo.',
      subtitle: 'Financiamos productos con potencial y compartimos el riesgo operativo.',
      trust_note: 'Una oportunidad puede convertirse en un producto real.',
    },
    eligibility: {
      title: 'Un programa sujeto a evaluación',
      summary: 'La propuesta define el aporte inicial y el saldo aprobado.',
      badge: 'Aprobación previa',
    },
    options: [
      ['five-year', 'Alianza a 5 años', 'Recomendada', true, 5],
      ['three-year', 'Alianza a 3 años', 'Alternativa', false, 3],
    ],
    conditionTitles: ['12 meses de financiación', 'Exclusividad y custodia responsable', 'Calculadora de requerimientos', '4 XS, 2 S y 1 M disponibles cada mes', 'Pagos claros y cobertura del riesgo de impago', 'Un rango claro para aplicar', 'Análisis de riesgo y aporte desde el 20%', 'Exclusividad conceptual — sólo a 5 años'],
    conceptualExclusivity: {
      summary: 'Project App. renuncia durante los cinco años a reproducir conceptos, ideas o enfoques específicos del producto para proyectos competidores del mismo sector y nicho.',
      included: 'Exclusividad conceptual a cargo de Project App. durante los cinco años.',
      excluded: 'Sin el compromiso adicional de exclusividad conceptual de la opción a cinco años.',
      scope: 'La propuesta y el contrato delimitan por escrito el sector, el nicho, el producto y los conceptos o enfoques comprendidos.',
      termTitle: 'No competencia conceptual en la alianza a cinco años',
      term: 'Aplica únicamente al elegir la modalidad de cinco años y durante su vigencia original; un segundo ciclo no reinicia ni extiende este plazo.',
    },
    calculator: {
      eyebrow: 'Transparencia para decidir',
      title: 'De una necesidad en palabras a un rango útil para planear',
      summary: 'La herramienta recibe lenguaje natural y entrega una referencia comercial.',
      input: { title: 'Qué se ingresa', items: ['Descripción en lenguaje natural del cambio.'] },
      output: { title: 'Qué se obtiene', items: ['Esfuerzo, tiempo y rango de precio.'] },
      disclaimer: 'La cotización formal confirma el alcance.',
    },
    package: {
      title: 'Capacidad mensual para la evolución del producto',
      summary: 'Pensado principalmente para requerimientos pequeños y acotados.',
      renewal_label: 'Se renueva cada mes', rollover_label: 'No acumula cupos',
      availability_label: 'Desde producción', included_label: 'Incluido sin costo adicional',
    },
    term: {
      title: 'Custodia de código no es cesión de propiedad',
      summary: 'Project App. protege la continuidad técnica.',
      item: 'La custodia no transfiere la propiedad intelectual.',
    },
    cta: {
      eyebrow: 'Conversemos sobre el potencial del proyecto',
      title: 'Solicita tu evaluación para el Programa de Alianza',
      body: 'Cuéntanos qué producto quieres construir.',
      button: 'Hablar por WhatsApp',
    },
    disclaimer: 'Información comercial de referencia.',
  },
  en: {
    hero: {
      eyebrow: 'Partnership Program for products built with a long-term vision',
      title: 'We build today. We grow with you.',
      subtitle: 'We finance products with potential and share operational risk.',
      trust_note: 'An opportunity can become a real product.',
    },
    eligibility: {
      title: 'A program subject to evaluation',
      summary: 'The proposal defines the initial contribution and approved balance.',
      badge: 'Prior approval',
    },
    options: [
      ['five-year', '5-year partnership', 'Recommended', true, 5],
      ['three-year', '3-year partnership', 'Alternative', false, 3],
    ],
    conditionTitles: ['12 months of financing', 'Exclusivity and responsible custody', 'Requirement calculator', '4 XS, 2 S and 1 M available every month', 'Clear payments and default-risk coverage', 'A clear eligibility range', 'Risk review and contribution from 20%', 'Conceptual exclusivity — five-year option only'],
    conceptualExclusivity: {
      summary: 'During the five-year term, Project App. agrees not to reproduce specific product concepts, ideas, or approaches for competing projects in the same sector and niche.',
      included: 'Conceptual exclusivity by Project App. throughout the five-year term.',
      excluded: 'Excludes the additional conceptual exclusivity commitment of the five-year option.',
      scope: 'The proposal and contract define the sector, niche, product, and covered concepts or approaches in writing.',
      termTitle: 'Conceptual non-compete in the five-year partnership',
      term: 'It applies only when the five-year option is chosen and during its original term; a second cycle does not restart or extend this period.',
    },
    calculator: {
      eyebrow: 'Transparency for better decisions',
      title: 'From a need in plain language to a useful planning range',
      summary: 'The tool receives plain language and returns a commercial reference.',
      input: { title: 'What goes in', items: ['A plain-language description of the change.'] },
      output: { title: 'What comes out', items: ['Effort, time, and a price range.'] },
      disclaimer: 'The formal quote confirms the scope.',
    },
    package: {
      title: 'Monthly capacity for product evolution',
      summary: 'Intended mainly for small, bounded requirements.',
      renewal_label: 'Renews every month', rollover_label: 'Requirements do not roll over',
      availability_label: 'Available from production', included_label: 'Included at no additional cost',
    },
    term: {
      title: 'Code custody is not ownership transfer',
      summary: 'Project App. protects technical continuity.',
      item: 'Custody does not transfer intellectual property.',
    },
    cta: {
      eyebrow: 'Let’s discuss the project’s potential',
      title: 'Request your Partnership Program evaluation',
      body: 'Tell us what product you want to build.',
      button: 'Talk on WhatsApp',
    },
    disclaimer: 'Commercial information for reference.',
  },
}

export function financingProgramFixture(language = 'es', overrides = {}) {
  const copy = content[language]
  return {
    language,
    financing_months: 12,
    minimum_project_value_cop: '20000000.00',
    maximum_project_value_cop: '140000000.00',
    maximum_financed_percent: '80%',
    minimum_initial_payment_percent: '20%',
    ordinary_interest_rate: '0%',
    late_hosting_increase_percent: '2%',
    installment_due_day_range: [1, 5],
    canonical_path: language === 'en' ? '/en-us/partnership-program' : '/es-co/partnership-program',
    show_explainer_video: overrides.showExplainerVideo ?? true,
    hero: copy.hero,
    eligibility: copy.eligibility,
    options: copy.options.map(([id, name, badge, included, years]) => ({
      id, name, badge, exclusivity_years: years, recommended: included,
      financing_cycles: included ? 2 : 1,
      hour_package_included: included,
      summary: language === 'en'
        ? (included ? 'Financing with monthly continuity.' : 'Financing without the monthly package.')
        : (included ? 'Financiación con continuidad mensual.' : 'Financiación sin paquete mensual.'),
      highlights: language === 'en'
        ? (included
            ? ['Up to two separate 12-month cycles at 0% ordinary interest.', copy.conceptualExclusivity.included]
            : ['One 12-month cycle at 0% ordinary interest.', copy.conceptualExclusivity.excluded])
        : (included
            ? ['Hasta dos ciclos separados de 12 meses con interés ordinario del 0%.', copy.conceptualExclusivity.included]
            : ['Un ciclo de 12 meses con interés ordinario del 0%.', copy.conceptualExclusivity.excluded]),
    })),
    conditions: copy.conditionTitles.map((title, index) => {
      const isPaymentCondition = index === 4
      const isConceptualCondition = index === 7
      return {
        id: ['financing', 'exclusivity', 'calculator', 'hour-package', 'payment-discipline', 'project-value-range', 'risk-and-initial-payment', 'conceptual-exclusivity'][index],
        number: String(index + 1).padStart(2, '0'),
        icon: ['↗', '◇', '◎', '◷', '%', '◆', '◒', '◇'][index],
        title,
        summary: isPaymentCondition
          ? (language === 'en'
              ? 'An overdue installment increases current Hosting by 2%.'
              : 'Una cuota en mora aumenta en 2% el costo vigente del Hosting.')
          : (isConceptualCondition ? copy.conceptualExclusivity.summary : 'A clear commercial condition for the partnership.'),
        commercial_reason: 'It protects continuity and makes decisions predictable.',
        highlights: isPaymentCondition
          ? [language === 'en' ? 'Increases are cumulative and permanent.' : 'Los aumentos son acumulativos y permanentes.']
          : (isConceptualCondition ? [copy.conceptualExclusivity.scope] : ['The formal agreement defines its exact scope.']),
      }
    }),
    calculator: copy.calculator,
    package: {
      ...copy.package,
      name: language === 'en' ? 'Pro Pack' : 'Paquete Pro',
      xs_count: 4,
      s_count: 2,
      m_count: 1,
      renews_monthly: true,
      rollover: false,
      catalog_synced: overrides.catalogSynced ?? true,
    },
    legal_terms: [
      {
        id: 'conceptual-exclusivity-scope',
        title: copy.conceptualExclusivity.termTitle,
        summary: copy.conceptualExclusivity.summary,
        items: [copy.conceptualExclusivity.term, copy.conceptualExclusivity.scope],
      },
      {
        id: 'late-payment-hosting',
        title: language === 'en' ? 'Late payment and Hosting increase' : 'Mora y aumento del costo del Hosting',
        summary: language === 'en' ? 'The deadline and consequence are known before signing.' : 'La fecha y la consecuencia se conocen antes de firmar.',
        items: [language === 'en'
          ? 'Each overdue installment permanently and cumulatively increases current Hosting by 2%.'
          : 'Cada cuota en mora aumenta 2% el Hosting vigente de forma acumulativa y permanente.'],
      },
      {
        id: 'second-cycle',
        title: language === 'en' ? 'Second cycle in the five-year partnership' : 'Segundo ciclo en la alianza de cinco años',
        summary: language === 'en' ? 'A new stage without restarting the partnership.' : 'Una nueva etapa sin reiniciar la alianza.',
        items: [language === 'en'
          ? 'It requires full payment of cycle one and a new manual risk approval.'
          : 'Exige pago íntegro del primer ciclo y una nueva aprobación manual de riesgo.'],
      },
      {
        id: 'code-custody',
        title: copy.term.title,
        summary: copy.term.summary,
        items: [copy.term.item],
      },
    ],
    cta: {
      ...copy.cta,
      whatsapp_url: 'https://wa.me/573238122373?text=financing',
    },
    disclaimer: copy.disclaimer,
  }
}
