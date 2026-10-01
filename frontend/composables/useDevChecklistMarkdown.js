import { computed } from 'vue';

const LABELS = {
  es: {
    objective: '🎯 Objetivo',
    opportunity: 'Oportunidad',
    includes: 'Incluye',
    components: '🧩 Componentes y funcionalidades',
    additionalModules: '➕ Módulos adicionales',
    includedFree: '🎁 Incluidos sin costo extra',
    dataModel: '🗄️ Modelos de datos',
    epics: '🏗️ Épicas y requerimientos',
    apis: '🔌 API endpoints',
    integrations: '🔗 Integraciones (incluidas)',
    growth: '🌱 Preparación para el crecimiento (visión v2)',
    keyFields: 'campos clave',
    configuration: 'Configuración',
    flow: 'Flujo',
    preparation: 'Preparación',
    evolution: 'Evolución',
    client: 'Cliente',
    status: 'Estado',
    language: 'Idioma',
    untitled: '(sin título)',
  },
  en: {
    objective: '🎯 Objective',
    opportunity: 'Opportunity',
    includes: 'Includes',
    components: '🧩 Components and features',
    additionalModules: '➕ Additional modules',
    includedFree: '🎁 Included at no extra cost',
    dataModel: '🗄️ Data models',
    epics: '🏗️ Epics and requirements',
    apis: '🔌 API endpoints',
    integrations: '🔗 Integrations (included)',
    growth: '🌱 Growth readiness (v2 vision)',
    keyFields: 'key fields',
    configuration: 'Configuration',
    flow: 'Flow',
    preparation: 'Preparation',
    evolution: 'Evolution',
    client: 'Client',
    status: 'Status',
    language: 'Language',
    untitled: '(untitled)',
  },
};

function pickLabels(language) {
  return LABELS[language] || LABELS.es;
}

function findSection(sections, type) {
  if (!Array.isArray(sections)) return null;
  return sections.find((s) => s && s.section_type === type) || null;
}

function nonEmpty(value) {
  if (value == null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

function checklistItem(name, description) {
  if (!nonEmpty(name)) return null;
  const desc = nonEmpty(description) ? ` — ${description}` : '';
  return `- [ ] **${name}**${desc}`;
}

function humanizeId(id) {
  if (!id) return '';
  return id
    .split(/[_-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function resolveModuleLabel(moduleId, additionalModules) {
  if (!moduleId) return '';
  if (Array.isArray(additionalModules)) {
    const match = additionalModules.find((m) => m && m.id === moduleId);
    if (match && nonEmpty(match.title)) return match.title;
  }
  return humanizeId(moduleId);
}

function joinParagraphs(paragraphs) {
  if (!Array.isArray(paragraphs)) return '';
  return paragraphs.filter(nonEmpty).join('\n\n');
}

function buildHeader(proposal, L) {
  const title = nonEmpty(proposal.title) ? proposal.title : L.untitled;
  const meta = [
    nonEmpty(proposal.client_name) ? `${L.client}: ${proposal.client_name}` : null,
    `${L.status}: ${proposal.status || ''}`,
    `${L.language}: ${proposal.language || 'es'}`,
  ].filter(Boolean).join(' · ');
  const lines = [`# ${title}`];
  if (meta) lines.push(`> ${meta}`);
  return lines.join('\n');
}

function buildObjective(sections, L) {
  const summary = findSection(sections, 'executive_summary');
  const context = findSection(sections, 'context_diagnostic');
  const summaryParagraphs = joinParagraphs(summary?.content_json?.paragraphs);
  const contextParagraphs = joinParagraphs(context?.content_json?.paragraphs);
  const opportunity = context?.content_json?.opportunity;
  const highlights = Array.isArray(summary?.content_json?.highlights)
    ? summary.content_json.highlights.filter(nonEmpty)
    : [];

  if (!summaryParagraphs && !contextParagraphs && !nonEmpty(opportunity) && !highlights.length) {
    return '';
  }

  const lines = [`## ${L.objective}`];
  if (summaryParagraphs) lines.push(summaryParagraphs);
  if (contextParagraphs) lines.push(contextParagraphs);
  if (nonEmpty(opportunity)) lines.push(`**${L.opportunity}:** ${opportunity}`);
  if (highlights.length) {
    lines.push(`**${L.includes}:**`);
    for (const h of highlights) lines.push(`- ${h}`);
  }
  return lines.join('\n\n');
}

function buildComponents(sections, L) {
  const fr = findSection(sections, 'functional_requirements');
  const groups = Array.isArray(fr?.content_json?.groups) ? fr.content_json.groups : [];
  if (!groups.length) return '';
  const lines = [`## ${L.components}`];
  for (const group of groups) {
    if (!group) continue;
    if (nonEmpty(group.title)) lines.push(`### ${group.title}`);
    if (nonEmpty(group.description)) lines.push(group.description);
    const items = Array.isArray(group.items) ? group.items : [];
    for (const item of items) {
      const line = checklistItem(item?.name, item?.description);
      if (line) lines.push(line);
    }
  }
  return lines.join('\n\n');
}

function buildAdditionalModules(sections, L) {
  const fr = findSection(sections, 'functional_requirements');
  const modules = Array.isArray(fr?.content_json?.additionalModules)
    ? fr.content_json.additionalModules
    : [];
  const included = modules.filter((m) => m && m.is_visible !== false && (m.selected ?? m.default_selected ?? false));
  if (!included.length) return '';
  const lines = [`## ${L.additionalModules}`];
  for (const mod of included) {
    if (nonEmpty(mod.title)) lines.push(`### ${mod.title}`);
    if (nonEmpty(mod.description)) lines.push(mod.description);
    const items = Array.isArray(mod.items) ? mod.items : [];
    for (const item of items) {
      const line = checklistItem(item?.name, item?.description);
      if (line) lines.push(line);
    }
  }
  return lines.join('\n\n');
}

function buildIncludedFree(sections, L) {
  const vam = findSection(sections, 'value_added_modules');
  const moduleIds = Array.isArray(vam?.content_json?.module_ids)
    ? vam.content_json.module_ids
    : [];
  if (!moduleIds.length) return '';
  const justifications = vam?.content_json?.justifications || {};
  const fr = findSection(sections, 'functional_requirements');
  const additionalModules = fr?.content_json?.additionalModules;
  const lines = [`## ${L.includedFree}`];
  for (const id of moduleIds) {
    const label = resolveModuleLabel(id, additionalModules);
    const justification = justifications[id];
    const line = checklistItem(label, justification);
    if (line) lines.push(line);
  }
  return lines.join('\n');
}

function buildDataModel(technical, L) {
  const entities = Array.isArray(technical?.dataModel?.entities)
    ? technical.dataModel.entities
    : [];
  if (!entities.length) return '';
  const lines = [`## ${L.dataModel}`];
  for (const entity of entities) {
    if (!nonEmpty(entity?.name)) continue;
    const parts = [`- [ ] **${entity.name}**`];
    if (nonEmpty(entity.description)) parts.push(` — ${entity.description}`);
    if (nonEmpty(entity.keyFields)) parts.push(` _(${L.keyFields}: ${entity.keyFields})_`);
    lines.push(parts.join(''));
  }
  return lines.join('\n');
}

function buildEpics(technical, L) {
  const epics = Array.isArray(technical?.epics) ? technical.epics : [];
  if (!epics.length) return '';
  const lines = [`## ${L.epics}`];
  for (const epic of epics) {
    if (!epic) continue;
    if (nonEmpty(epic.title)) lines.push(`### ${epic.title}`);
    if (nonEmpty(epic.description)) lines.push(epic.description);
    const requirements = Array.isArray(epic.requirements) ? epic.requirements : [];
    for (const req of requirements) {
      if (!nonEmpty(req?.title)) continue;
      const desc = nonEmpty(req.description) ? ` — ${req.description}` : '';
      lines.push(`- [ ] **${req.title}**${desc}`);
      if (nonEmpty(req.configuration)) lines.push(`  - ${L.configuration}: ${req.configuration}`);
      if (nonEmpty(req.usageFlow)) lines.push(`  - ${L.flow}: ${req.usageFlow}`);
    }
  }
  return lines.join('\n\n');
}

function buildApiEndpoints(technical, L) {
  const domains = Array.isArray(technical?.apiDomains) ? technical.apiDomains : [];
  if (!domains.length) return '';
  const lines = [`## ${L.apis}`];
  for (const domain of domains) {
    if (!domain) continue;
    if (nonEmpty(domain.domain)) lines.push(`### ${domain.domain}`);
    if (nonEmpty(domain.summary)) lines.push(`- [ ] ${domain.summary}`);
  }
  return lines.join('\n');
}

function buildIntegrations(technical, L) {
  const included = Array.isArray(technical?.integrations?.included)
    ? technical.integrations.included
    : [];
  if (!included.length) return '';
  const lines = [`## ${L.integrations}`];
  for (const integ of included) {
    if (!integ) continue;
    const name = [integ.service, integ.provider].filter(nonEmpty).join(' — ');
    if (!name) continue;
    const meta = [
      nonEmpty(integ.connection) ? integ.connection : null,
      nonEmpty(integ.dataExchange) ? `Datos: ${integ.dataExchange}` : null,
      nonEmpty(integ.accountOwner) ? `Cuenta: ${integ.accountOwner}` : null,
    ].filter(Boolean).join(' · ');
    lines.push(meta ? `- [ ] **${name}** · ${meta}` : `- [ ] **${name}**`);
  }
  return lines.join('\n');
}

function buildGrowthReadiness(technical, L) {
  const strategies = Array.isArray(technical?.growthReadiness?.strategies)
    ? technical.growthReadiness.strategies
    : [];
  if (!strategies.length) return '';
  const lines = [`## ${L.growth}`];
  for (const strat of strategies) {
    if (!strat) continue;
    if (nonEmpty(strat.dimension)) lines.push(`### ${strat.dimension}`);
    if (nonEmpty(strat.preparation)) lines.push(`- [ ] ${L.preparation}: ${strat.preparation}`);
    if (nonEmpty(strat.evolution)) lines.push(`- [ ] ${L.evolution}: ${strat.evolution}`);
  }
  return lines.join('\n');
}

export function buildDevChecklistMarkdown(proposal) {
  if (!proposal || typeof proposal !== 'object') return '';
  const L = pickLabels(proposal.language);
  const sections = Array.isArray(proposal.sections) ? proposal.sections : [];
  const technical = findSection(sections, 'technical_document')?.content_json || null;

  const blocks = [
    buildHeader(proposal, L),
    buildObjective(sections, L),
    buildComponents(sections, L),
    buildAdditionalModules(sections, L),
    buildIncludedFree(sections, L),
    buildDataModel(technical, L),
    buildEpics(technical, L),
    buildApiEndpoints(technical, L),
    buildIntegrations(technical, L),
    buildGrowthReadiness(technical, L),
  ].filter((b) => nonEmpty(b));

  return blocks.join('\n\n---\n\n') + '\n';
}

export function buildDevChecklistFilename(proposal) {
  const id = proposal?.uuid || proposal?.id || 'proposal';
  return `dev-checklist-${id}.md`;
}

export function useDevChecklistMarkdown(proposalRef) {
  const markdown = computed(() => buildDevChecklistMarkdown(proposalRef.value));
  const filename = computed(() => buildDevChecklistFilename(proposalRef.value));
  return { markdown, filename };
}
