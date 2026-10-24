import { withEditorialFormats } from '~/utils/editorialMetadata';
/**
 * JSON ↔ form conversion helpers for the 8 DiagnosticSection types.
 *
 * Each section type has a `buildForm(contentJson)` that hydrates a reactive
 * form object from the backend payload, and a `toJson(form)` that serializes
 * the form back into the persisted JSON. Arrays of strings are exposed as
 * newline-delimited textareas.
 */

import {
  arrToText,
  textToArr,
} from '~/components/BusinessProposal/admin/sectionEditorUtils';

export { VISIBILITY_OPTIONS } from '~/stores/diagnostics_constants';

export const SECTION_TYPES = [
  'purpose',
  'radiography',
  'categories',
  'delivery_structure',
  'executive_summary',
  'cost',
  'timeline',
  'scope',
];

export const SECTION_META = {
  purpose: { label: 'Propósito', icon: '🧭' },
  radiography: { label: 'Radiografía', icon: '📐' },
  categories: { label: 'Categorías', icon: '🗂️' },
  delivery_structure: { label: 'Estructura de la Entrega', icon: '📦' },
  executive_summary: { label: 'Resumen Ejecutivo', icon: '📊' },
  cost: { label: 'Costo y Pago', icon: '💰' },
  timeline: { label: 'Cronograma', icon: '📅' },
  scope: { label: 'Alcance', icon: '🎯' },
};

function cloneJson(value) {
  if (value === undefined || value === null) return value;
  return JSON.parse(JSON.stringify(value));
}

// ── purpose ────────────────────────────────────────────────────────────
function buildPurposeForm(content) {
  return {
    index: content.index || '',
    title: content.title || '',
    paragraphsText: arrToText(content.paragraphs),
    scopeNote: content.scopeNote || '',
    severityTitle: content.severityTitle || 'Escala de Severidad',
    severityIntro: content.severityIntro || '',
    severityLevels: (content.severityLevels || []).map((lvl) => ({
      level: lvl.level || '',
      meaning: lvl.meaning || '',
    })),
  };
}

function purposeToJson(form) {
  return {
    index: form.index,
    title: form.title,
    paragraphs: textToArr(form.paragraphsText),
    scopeNote: form.scopeNote,
    severityTitle: form.severityTitle,
    severityIntro: form.severityIntro,
    severityLevels: form.severityLevels.filter(
      (lvl) => lvl.level || lvl.meaning,
    ),
  };
}

// ── radiography ────────────────────────────────────────────────────────
function buildRadiographyForm(content) {
  return {
    index: content.index || '',
    title: content.title || '',
    intro: content.intro || '',
    includesTitle: content.includesTitle || '',
    includes: (content.includes || []).map((it) => ({
      title: it.title || '',
      description: it.description || '',
    })),
    classificationTitle: content.classificationTitle || '',
    classificationIntro: content.classificationIntro || '',
    classificationRows: (content.classificationRows || []).map((row) => ({
      dimension: row.dimension || '',
      small: row.small || '',
      medium: row.medium || '',
      large: row.large || '',
    })),
    classificationNote: content.classificationNote || '',
  };
}

function radiographyToJson(form) {
  return {
    index: form.index,
    title: form.title,
    intro: form.intro,
    includesTitle: form.includesTitle,
    includes: form.includes.filter((i) => i.title || i.description),
    classificationTitle: form.classificationTitle,
    classificationIntro: form.classificationIntro,
    classificationRows: form.classificationRows.filter(
      (r) => r.dimension || r.small || r.medium || r.large,
    ),
    classificationNote: form.classificationNote,
  };
}

// ── categories ─────────────────────────────────────────────────────────
function buildCategoriesForm(content) {
  return {
    index: content.index || '',
    title: content.title || '',
    intro: content.intro || '',
    categories: (content.categories || []).map((cat) => ({
      key: cat.key || '',
      title: cat.title || '',
      description: cat.description || '',
      strengthsText: arrToText(cat.strengths),
      findings: (cat.findings || []).map((f) => ({
        level: f.level || '',
        title: f.title || '',
        detail: f.detail || '',
      })),
      recommendations: (cat.recommendations || []).map((r) => ({
        level: r.level || '',
        title: r.title || '',
        detail: r.detail || '',
      })),
    })),
  };
}

function categoriesToJson(form) {
  return {
    index: form.index,
    title: form.title,
    intro: form.intro,
    categories: form.categories.map((cat) => ({
      key: cat.key,
      title: cat.title,
      description: cat.description,
      strengths: textToArr(cat.strengthsText),
      findings: cat.findings.filter((f) => f.level || f.title || f.detail),
      recommendations: cat.recommendations.filter(
        (r) => r.level || r.title || r.detail,
      ),
    })),
  };
}

// ── delivery_structure ─────────────────────────────────────────────────
function buildDeliveryStructureForm(content) {
  return {
    index: content.index || '',
    title: content.title || '',
    intro: content.intro || '',
    blocks: (content.blocks || []).map((block) => ({
      title: block.title || '',
      paragraphsText: arrToText(block.paragraphs),
      example: block.example || '',
    })),
  };
}

function deliveryStructureToJson(form) {
  return {
    index: form.index,
    title: form.title,
    intro: form.intro,
    blocks: form.blocks.map((b) => ({
      title: b.title,
      paragraphs: textToArr(b.paragraphsText),
      example: b.example,
    })),
  };
}

// ── executive_summary ──────────────────────────────────────────────────
function buildExecutiveSummaryForm(content) {
  const counts = content.severityCounts || {};
  return {
    index: content.index || '',
    title: content.title || '',
    intro: content.intro || '',
    severityCounts: {
      critico: counts.critico ?? 0,
      alto: counts.alto ?? 0,
      medio: counts.medio ?? 0,
      bajo: counts.bajo ?? 0,
    },
    narrative: content.narrative || '',
    highlightsText: arrToText(content.highlights),
  };
}

function executiveSummaryToJson(form) {
  return {
    index: form.index,
    title: form.title,
    intro: form.intro,
    severityCounts: {
      critico: Number(form.severityCounts.critico) || 0,
      alto: Number(form.severityCounts.alto) || 0,
      medio: Number(form.severityCounts.medio) || 0,
      bajo: Number(form.severityCounts.bajo) || 0,
    },
    narrative: form.narrative,
    highlights: textToArr(form.highlightsText),
  };
}

// ── cost ───────────────────────────────────────────────────────────────
function buildCostForm(content) {
  return {
    index: content.index || '',
    title: content.title || '',
    intro: content.intro || '',
    valueBulletsText: arrToText(content.valueBullets),
    paymentDescription: (content.paymentDescription || []).map((p) => ({
      label: p.label || '',
      detail: p.detail || '',
    })),
    note: content.note || '',
  };
}

function costToJson(form) {
  return {
    index: form.index,
    title: form.title,
    intro: form.intro,
    valueBullets: textToArr(form.valueBulletsText),
    paymentDescription: form.paymentDescription.filter(
      (p) => p.label || p.detail,
    ),
    note: form.note,
  };
}

// ── timeline ───────────────────────────────────────────────────────────
function buildTimelineForm(content) {
  return {
    index: content.index || '',
    title: content.title || '',
    intro: content.intro || '',
    distributionTitle: content.distributionTitle || '',
    distribution: (content.distribution || []).map((d) => ({
      dayRange: d.dayRange || '',
      description: d.description || '',
    })),
  };
}

function timelineToJson(form) {
  return {
    index: form.index,
    title: form.title,
    intro: form.intro,
    distributionTitle: form.distributionTitle,
    distribution: form.distribution.filter((d) => d.dayRange || d.description),
  };
}

// ── scope ──────────────────────────────────────────────────────────────
function buildScopeForm(content) {
  return {
    index: content.index || '',
    title: content.title || '',
    considerationsText: arrToText(content.considerations),
  };
}

function scopeToJson(form) {
  return {
    index: form.index,
    title: form.title,
    considerations: textToArr(form.considerationsText),
  };
}

// ── Dispatch table ─────────────────────────────────────────────────────
const BUILDERS = {
  purpose: buildPurposeForm,
  radiography: buildRadiographyForm,
  categories: buildCategoriesForm,
  delivery_structure: buildDeliveryStructureForm,
  executive_summary: buildExecutiveSummaryForm,
  cost: buildCostForm,
  timeline: buildTimelineForm,
  scope: buildScopeForm,
};

const SERIALIZERS = {
  purpose: purposeToJson,
  radiography: radiographyToJson,
  categories: categoriesToJson,
  delivery_structure: deliveryStructureToJson,
  executive_summary: executiveSummaryToJson,
  cost: costToJson,
  timeline: timelineToJson,
  scope: scopeToJson,
};

export function buildFormFromJson(sectionType, contentJson) {
  const builder = BUILDERS[sectionType];
  if (!builder) return cloneJson(contentJson || {});
  return withEditorialFormats(contentJson, builder(cloneJson(contentJson || {})));
}

export function formToJson(sectionType, form) {
  const serializer = SERIALIZERS[sectionType];
  if (!serializer) return cloneJson(form);
  return withEditorialFormats(form, serializer(form));
}
