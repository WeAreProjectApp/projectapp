export function json(body, status = 200) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

export function calculatorDefinition(title = 'Definición comercial vigente') {
  return {
    schema_version: 1,
    title,
    methodology: 'Clasifica el alcance por señales observables.',
    project_rules: ['Lo que supera XL se trata como proyecto.'],
    sizes: [
      ['XS', 1], ['S', 2], ['M', 3], ['L', 5], ['XL', 8],
    ].map(([id, points]) => ({
      id, label: `Talla ${id}`, definition: `Definición ${id}`, examples: [`Ejemplo ${id}`],
      points, hours_min: 2, hours_max: 7, standard_value_cop: id === 'XS' ? 50000 : 125000,
    })),
    signals: [{ id: 'signal-form', label: 'Formulario', description: 'Captura y valida datos.', size: 'S', surcharge_percent: 0 }],
    modifiers: [{ id: 'modifier-risk', label: 'Riesgo', kind: 'percentage', minimum: 0, maximum: 10, applies_to: ['S'], exclusive_group: '' }],
    families: [{ label: 'Formularios', small: 'Campo único', medium: 'Formulario validado', large: 'Flujo con auditoría', extra_large: 'Módulo transversal' }],
    calibration: { minimum_samples: 3, deviation_percent: 30, hourly_cost_cop: 60000 },
  };
}

export function generalCalculator(definition = calculatorDefinition()) {
  return {
    initialized: true, revision_id: 11, if_match: 'general-v11', definition,
    document_url: '/panel/documents/800/edit', document_candidates: [],
  };
}

export function projectVersion({ id = 301, status = 'draft', definition = calculatorDefinition('Parámetros Proyecto Aurora') } = {}) {
  return {
    id, status, document_id: 900, document_url: '/panel/documents/900/edit', if_match: `project-v${id}`,
    definition, base_revision_id: 11, created_at: '2026-11-05T09:00:00Z',
    changes: [{ id: 1, status: 'draft', note: 'Condiciones acordadas', created_at: '2026-11-05T09:00:00Z' }],
  };
}

export function projectCalculator({ versions = [], calculatorDocumentId = null } = {}) {
  return {
    project_id: 20, project_name: 'Proyecto Aurora', calculator_document_id: calculatorDocumentId,
    if_match: 'project-20-v1', versions: versions.map(({ definition, changes, ...summary }) => summary),
  };
}

export const calibration = {
  consistency: { reviewed: 2, disagreements: 0 },
  cohorts: [{ definition_digest: 'digest-11', size: 'M', revision_id: 11, samples: 1, minimum_samples: 3, median_hours: 24, deviation_percent: 0, status: 'insufficient_data', median_cost_cop: null, standard_value_cop: 360000, cost_samples: 0, covers_median_cost: null, propose_review: false }],
};

export const estimates = {
  count: 1,
  results: [{ id: 44, size: 'M', project_name: 'Proyecto Aurora', requirement: 'Alta de clientes', explanation: 'Formulario con validación', actuals: [{ id: 77, actual_hours: '22.00', hourly_cost_cop: '60000.00', evidence: 'Bitácora', cause: 'Ajuste inicial' }] }],
};
