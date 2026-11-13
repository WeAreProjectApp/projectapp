/**
 * Item ↔ technical requirement traceability helpers.
 *
 * Functional-requirements items carry a stable `id`
 * (`item-<group_id>-<slug(name)>`); technical requirements reference
 * those ids via `linked_item_ids`. These helpers mirror the backend
 * canonical implementation in
 * `backend/content/services/proposal_module_links.py` — the backend
 * remains authoritative (it re-ensures ids on every save/import).
 */
import { toSlug } from '~/utils/slugify';
import { normalizeLinkedModuleIds } from '~/utils/proposalModuleLinkOptions';

export function buildItemId(groupId, name) {
  const groupSlug = String(groupId ?? '').trim() || 'group';
  const nameSlug = toSlug(name);
  if (!nameSlug) return '';
  return `item-${groupSlug}-${nameSlug}`;
}

function iterGroups(contentJson) {
  if (!contentJson || typeof contentJson !== 'object') return [];
  const groups = Array.isArray(contentJson.groups) ? contentJson.groups : [];
  const modules = Array.isArray(contentJson.additionalModules) ? contentJson.additionalModules : [];
  return [...groups, ...modules].filter((g) => g && typeof g === 'object');
}

/**
 * Client mirror of the backend `ensure_functional_requirements_item_ids`:
 * assigns `item-<group_id>-<slug(name)>` to items missing an id, deduping
 * across the whole section with a numeric suffix. Existing ids are kept
 * verbatim; items whose name produces an empty slug stay id-less.
 * Returns a deep copy — the input is not mutated.
 */
export function ensureFunctionalRequirementItemIds(contentJson) {
  if (!contentJson || typeof contentJson !== 'object') return {};
  const out = JSON.parse(JSON.stringify(contentJson));
  const seen = new Set();

  for (const group of iterGroups(out)) {
    for (const item of Array.isArray(group.items) ? group.items : []) {
      if (!item || typeof item !== 'object') continue;
      const existing = String(item.id ?? '').trim();
      if (existing) seen.add(existing);
    }
  }

  for (const group of iterGroups(out)) {
    for (const item of Array.isArray(group.items) ? group.items : []) {
      if (!item || typeof item !== 'object') continue;
      const existing = String(item.id ?? '').trim();
      if (existing) {
        item.id = existing;
        continue;
      }
      const base = buildItemId(group.id, item.name);
      if (!base) continue;
      let candidate = base;
      let suffix = 2;
      while (seen.has(candidate)) {
        candidate = `${base}-${suffix}`;
        suffix += 1;
      }
      item.id = candidate;
      seen.add(candidate);
    }
  }
  return out;
}

/**
 * Build `{ [itemId]: [{ title, description, priority, epicKey, flowKey }] }`
 * from a technical document's epics. Ids referencing no live item are
 * simply keys nobody looks up — callers match against their own catalog.
 */
export function buildItemRequirementsMap(technicalContentJson) {
  const result = {};
  const epics = technicalContentJson?.epics;
  if (!Array.isArray(epics)) return result;

  for (const epic of epics) {
    if (!epic || typeof epic !== 'object') continue;
    const requirements = Array.isArray(epic.requirements) ? epic.requirements : [];
    for (const req of requirements) {
      if (!req || typeof req !== 'object') continue;
      const linked = normalizeLinkedModuleIds(req.linked_item_ids ?? req.linkedItemIds);
      for (const itemId of linked) {
        if (!result[itemId]) result[itemId] = [];
        result[itemId].push({
          title: req.title || '',
          description: req.description || '',
          priority: req.priority || '',
          epicKey: epic.epicKey || '',
          flowKey: req.flowKey || '',
          ...(req.configuration ? { configuration: req.configuration } : {}),
          ...(req.usageFlow ? { usageFlow: req.usageFlow } : {}),
          ...(req.text_formats ? { text_formats: JSON.parse(JSON.stringify(req.text_formats)) } : {}),
        });
      }
    }
  }
  return result;
}
