function uniqueStrings(items) {
  const seen = new Set();
  const out = [];
  for (const raw of items || []) {
    if (typeof raw !== 'string') continue;
    const value = raw.trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    out.push(value);
  }
  return out;
}

function buildOption(id, label, aliases = [], isAlwaysIncluded = false) {
  return {
    id,
    label,
    aliases: uniqueStrings([id, ...aliases]),
    isAlwaysIncluded,
  };
}

/**
 * Build the canonical commercial-module catalog used by technical_document links.
 * Canonical ids:
 * - functional_requirements groups      -> group-<id>
 * - functional_requirements calculator  -> module-<id>
 * - investment modules                  -> <id>
 *
 * @param {Array<{ section_type?: string, content_json?: object }>} sections
 * @returns {{ options: Array<{id: string, label: string, aliases: string[], isAlwaysIncluded: boolean}>, aliasMap: Record<string, string>, alwaysIncludedIds: string[] }}
 */
export function buildProposalModuleLinkCatalog(sections) {
  const options = [];
  const aliasMap = {};
  const alwaysIncludedIds = [];

  if (!Array.isArray(sections)) {
    return { options, aliasMap, alwaysIncludedIds };
  }

  const addOption = (option) => {
    options.push(option);
    for (const alias of option.aliases || []) {
      aliasMap[alias] = option.id;
    }
    if (option.isAlwaysIncluded) {
      alwaysIncludedIds.push(option.id);
    }
  };

  const fr = sections.find((s) => s.section_type === 'functional_requirements');
  const inv = sections.find((s) => s.section_type === 'investment');
  const cj = fr?.content_json || {};
  const groups = [...(cj.groups || []), ...(cj.additionalModules || [])];

  for (const g of groups) {
    if (!g || g.is_visible === false) continue;
    if (g.id == null || String(g.id).trim().length === 0) continue;
    if (!g.title && !(g.items || []).length) continue;

    const rawId = String(g.id).trim();
    const isCalc = g.is_calculator_module === true;
    const canonicalId = isCalc ? `module-${rawId}` : `group-${rawId}`;
    const label = `${g.icon || ''} ${g.title || rawId}`.trim();
    const isAlwaysIncluded = (g.is_always_included ?? !isCalc) === true;

    addOption(buildOption(canonicalId, label, [rawId], isAlwaysIncluded));
  }

  for (const m of inv?.content_json?.modules || []) {
    if (m == null || m.id == null || String(m.id).trim().length === 0) continue;
    const id = String(m.id).trim();
    const label = `${m.icon || ''} ${m.title || id}`.trim();
    const isAlwaysIncluded = m.is_required === true;
    addOption(buildOption(id, label, [], isAlwaysIncluded));
  }

  return {
    options,
    aliasMap,
    alwaysIncludedIds: uniqueStrings(alwaysIncludedIds),
  };
}

/**
 * Build selectable options for the admin technical-document editor.
 *
 * @param {Array<{ section_type?: string, content_json?: object }>} sections
 * @returns {Array<{ id: string, label: string, aliases: string[], isAlwaysIncluded: boolean }>}
 */
export function buildProposalModuleLinkOptions(sections) {
  return buildProposalModuleLinkCatalog(sections).options;
}

export function buildProposalModuleIdAliasMap(sections) {
  return buildProposalModuleLinkCatalog(sections).aliasMap;
}

/**
 * Build the grouped item options for the admin technical-document editor's
 * per-requirement "link to commercial items" picker. Items without an id
 * are skipped (they get one on the next functional-requirements save).
 *
 * @param {Array<{ section_type?: string, content_json?: object }>} sections
 * @returns {Array<{ groupId: string, groupLabel: string, items: Array<{ id: string, label: string }> }>}
 */
export function buildProposalItemLinkOptions(sections) {
  if (!Array.isArray(sections)) return [];
  const fr = sections.find((s) => s?.section_type === 'functional_requirements');
  const cj = fr?.content_json || {};
  const baseGroups = (cj.groups || []).map((group) => ({
    group,
    isRequiredForCoverage: true,
  }));
  const additionalGroups = (cj.additionalModules || []).map((group) => ({
    group,
    // Optional catalog modules only become contractual coverage when the
    // seller explicitly selected them (or a legacy proposal selected them by
    // default). Unselected modules remain auditable without blocking a save.
    isRequiredForCoverage: group?.selected === true
      || (group?.selected == null && group?.default_selected === true),
  }));
  const groups = [...baseGroups, ...additionalGroups];
  const out = [];

  for (const { group: g, isRequiredForCoverage } of groups) {
    if (!g || typeof g !== 'object') continue;
    if (g.is_visible === false) continue;
    const groupId = g.id == null ? '' : String(g.id).trim();
    if (!groupId) continue;
    const items = [];
    for (const item of Array.isArray(g.items) ? g.items : []) {
      if (!item || typeof item !== 'object') continue;
      const itemId = typeof item.id === 'string' ? item.id.trim() : '';
      if (!itemId) continue;
      items.push({
        id: itemId,
        label: `${item.icon || ''} ${item.name || itemId}`.trim(),
      });
    }
    if (!items.length) continue;
    out.push({
      groupId,
      groupLabel: `${g.icon || ''} ${g.title || groupId}`.trim(),
      isRequiredForCoverage,
      items,
    });
  }
  return out;
}

/**
 * Compare commercial items with the requirement links in a technical document.
 * Required items block saves; optional catalog items are reported as guidance.
 *
 * @param {Array<{ groupId: string, groupLabel: string, isRequiredForCoverage?: boolean, items: Array<{ id: string, label: string }> }>} itemLinkOptions
 * @param {{ epics?: Array<{ requirements?: Array<{ linked_item_ids?: string[] }> }> }} technicalDocument
 * @returns {{ missingRequired: Array<object>, missingOptional: Array<object>, requiredCount: number, coveredRequiredCount: number }}
 */
export function buildTechnicalItemCoverage(itemLinkOptions, technicalDocument) {
  const linkedIds = new Set();
  for (const epic of technicalDocument?.epics || []) {
    for (const requirement of epic?.requirements || []) {
      for (const itemId of requirement?.linked_item_ids || requirement?.linkedItemIds || []) {
        if (typeof itemId === 'string' && itemId.trim()) linkedIds.add(itemId.trim());
      }
    }
  }

  const missingRequired = [];
  const missingOptional = [];
  let requiredCount = 0;
  let coveredRequiredCount = 0;

  for (const group of itemLinkOptions || []) {
    const isRequired = group?.isRequiredForCoverage === true;
    for (const item of group?.items || []) {
      if (!item?.id) continue;
      const entry = {
        id: item.id,
        label: item.label || item.id,
        groupId: group.groupId || '',
        groupLabel: group.groupLabel || group.groupId || '',
      };
      if (isRequired) {
        requiredCount += 1;
        if (linkedIds.has(item.id)) coveredRequiredCount += 1;
        else missingRequired.push(entry);
      } else if (!linkedIds.has(item.id)) {
        missingOptional.push(entry);
      }
    }
  }

  return { missingRequired, missingOptional, requiredCount, coveredRequiredCount };
}

export function buildProposalModuleIdAliasMapFromOptions(options) {
  const aliasMap = {};
  for (const option of options || []) {
    if (!option || typeof option.id !== 'string') continue;
    const aliases = Array.isArray(option.aliases) ? option.aliases : [option.id];
    for (const alias of aliases) {
      if (typeof alias !== 'string' || !alias.trim()) continue;
      aliasMap[alias.trim()] = option.id;
    }
  }
  return aliasMap;
}

export function normalizeLinkedModuleIds(raw, aliasMap = {}) {
  const values = Array.isArray(raw)
    ? raw
    : typeof raw === 'string'
      ? [raw]
      : [];
  return uniqueStrings(values.map((value) => {
    if (typeof value !== 'string') return '';
    const trimmed = value.trim();
    return aliasMap[trimmed] || trimmed;
  }));
}

export function normalizeTechnicalDocumentModuleLinks(contentJson, aliasMap = {}) {
  if (!contentJson || typeof contentJson !== 'object') return {};
  const out = JSON.parse(JSON.stringify(contentJson));
  const epics = Array.isArray(out.epics) ? out.epics : [];

  out.epics = epics.map((epic) => {
    if (!epic || typeof epic !== 'object') return epic;
    const normalizedEpic = { ...epic };
    delete normalizedEpic.linkedModuleIds;
    normalizedEpic.linked_module_ids = normalizeLinkedModuleIds(
      epic.linked_module_ids || epic.linkedModuleIds,
      aliasMap,
    );
    const requirements = Array.isArray(epic.requirements) ? epic.requirements : [];
    normalizedEpic.requirements = requirements.map((requirement) => {
      if (!requirement || typeof requirement !== 'object') return requirement;
      const normalizedRequirement = { ...requirement };
      delete normalizedRequirement.linkedModuleIds;
      normalizedRequirement.linked_module_ids = normalizeLinkedModuleIds(
        requirement.linked_module_ids || requirement.linkedModuleIds,
        aliasMap,
      );
      delete normalizedRequirement.linkedItemIds;
      normalizedRequirement.linked_item_ids = normalizeLinkedModuleIds(
        requirement.linked_item_ids || requirement.linkedItemIds,
      );
      return normalizedRequirement;
    });
    return normalizedEpic;
  });

  return out;
}
