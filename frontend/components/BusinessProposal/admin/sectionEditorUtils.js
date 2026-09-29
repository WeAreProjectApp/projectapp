/**
 * Pure utility functions for SectionEditor.vue.
 *
 * Extracted to enable unit testing of JSON serialization/deserialization
 * logic without mounting Vue components.
 */

import { DEFAULT_HOSTING_PERCENT, DEFAULT_BILLING_TIERS } from '~/stores/proposals_constants';
import { ensureFunctionalRequirementItemIds } from '~/utils/itemRequirementLinks';

/**
 * Join an array into newline-separated text.
 * @param {Array|string} arr
 * @returns {string}
 */
export function arrToText(arr) {
  return Array.isArray(arr) ? arr.join('\n') : (arr || '');
}

/**
 * Split newline-separated text into a trimmed, non-empty array.
 * @param {string} text
 * @returns {string[]}
 */
export function textToArr(text) {
  if (!text) return [];
  return text.split('\n').map(l => l.trim()).filter(Boolean);
}

/** Module ids highlighted in the value_added_modules section by default. */
export const VALUE_ADDED_DEFAULT_MODULE_IDS = [
  'admin_module', 'analytics_dashboard', 'kpi_dashboard_module', 'manual_module',
];

/**
 * Whether the hosting free-month gift block is shown to the client.
 *
 * Mirrors `normalize_hosting_plan` in the backend: the explicit flag wins, and
 * content written before it existed falls back to the old rule — a non-zero
 * count meant visible — so legacy proposals keep their current appearance.
 *
 * @param {object} hostingPlan
 * @returns {boolean}
 */
export function resolveFreeMonthsVisible(hostingPlan) {
  const hp = hostingPlan || {};
  if (hp.freeMonthsVisible !== undefined && hp.freeMonthsVisible !== null) {
    return Boolean(hp.freeMonthsVisible);
  }
  return Number(hp.freeMonths ?? 1) > 0;
}

/**
 * Build a reactive form object from a section's content_json.
 * @param {object} json - The content_json from the backend.
 * @param {string} type - The section_type.
 * @param {object} [proposalData] - Optional parent proposal data for defaults.
 * @returns {object}
 */
export function buildFormFromJson(json, type, proposalData) {
  const j = json || {};
  switch (type) {
    case 'greeting':
      return { proposalTitle: j.proposalTitle || proposalData?.title || '', clientName: j.clientName || proposalData?.client_name || '', inspirationalQuote: j.inspirationalQuote || '' };
    case 'executive_summary':
      return { index: j.index || '', title: j.title || '', paragraphs: arrToText(j.paragraphs), highlightsTitle: j.highlightsTitle || '', highlights: arrToText(j.highlights) };
    case 'context_diagnostic':
      return { index: j.index || '', title: j.title || '', paragraphs: arrToText(j.paragraphs), issuesTitle: j.issuesTitle || '', issues: arrToText(j.issues), opportunityTitle: j.opportunityTitle || '', opportunity: j.opportunity || '' };
    case 'conversion_strategy':
      return { index: j.index || '', title: j.title || '', intro: j.intro || '', steps: (j.steps || []).map(s => ({ title: s.title || '', bullets: arrToText(s.bullets) })), resultTitle: j.resultTitle || '', result: j.result || '' };
    case 'design_ux':
      return { index: j.index || '', title: j.title || '', paragraphs: arrToText(j.paragraphs), focusTitle: j.focusTitle || '', focusItems: arrToText(j.focusItems), objectiveTitle: j.objectiveTitle || '', objective: j.objective || '' };
    case 'creative_support':
      return { index: j.index || '', title: j.title || '', paragraphs: arrToText(j.paragraphs), includesTitle: j.includesTitle || '', includes: arrToText(j.includes), closing: j.closing || '' };
    case 'development_stages':
      return { index: j.index || '', title: j.title || '', intro: j.intro || '', currentLabel: j.currentLabel || '', stages: (j.stages || []).map(s => ({ icon: s.icon || '', title: s.title || '', description: s.description || '', current: !!s.current })) };
    case 'functional_requirements':
      return {
        index: j.index || '', title: j.title || '', intro: j.intro || '',
        groups: (j.groups || []).map(g => ({
          id: g.id || '', icon: g.icon || '', title: g.title || '',
          description: g.description || '',
          is_visible: g.is_visible !== undefined ? g.is_visible : true,
          selected: g.selected ?? (g.default_selected ?? false),
          is_calculator_module: g.is_calculator_module || false,
          default_selected: g.default_selected ?? false,
          is_always_included: g.is_always_included ?? !g.is_calculator_module,
          is_invite: g.is_invite || false,
          invite_note: g.invite_note || '',
          items: (g.items || []).map(i => ({ id: i.id || '', icon: i.icon || '', name: i.name || '', description: i.description || '', price: i.price ?? null, is_required: i.is_required !== false })),
          _pasteMode: g._editMode === 'paste', _pasteText: g.rawText || '', _collapsed: true,
        })),
        additionalModules: (j.additionalModules || []).map(m => ({
          id: m.id || `module_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`, icon: m.icon || '', title: m.title || '', description: m.description || '',
          is_visible: m.is_visible !== undefined ? m.is_visible : true,
          selected: m.selected ?? (m.default_selected ?? false),
          is_calculator_module: m.is_calculator_module || false,
          default_selected: m.default_selected ?? false,
          is_always_included: m.is_always_included ?? false,
          is_invite: m.is_invite || false,
          invite_note: m.invite_note || '',
          items: (m.items || []).map(i => ({ id: i.id || '', icon: i.icon || '', name: i.name || '', description: i.description || '', price: i.price ?? null, is_required: i.is_required !== false })),
          _pasteMode: m._editMode === 'paste', _pasteText: m.rawText || '', _collapsed: true,
        })),
      };
    case 'timeline':
      return { index: j.index || '', title: j.title || '', introText: j.introText || '', totalDuration: j.totalDuration || '', phases: (j.phases || []).map(p => ({ title: p.title || '', duration: p.duration || '', description: p.description || '', tasks: arrToText(p.tasks), milestone: p.milestone || '' })) };
    case 'investment': {
      const hp = j.hostingPlan || {};
      const defaultTiers = DEFAULT_BILLING_TIERS;
      return {
        index: j.index || '', title: j.title || '', introText: j.introText || '',
        totalInvestment: j.totalInvestment || '', currency: j.currency || 'COP',
        whatsIncluded: (j.whatsIncluded || []).map(i => ({ ...i })),
        paymentOptions: (j.paymentOptions || []).map(o => ({ ...o })),
        hostingPlan: {
          title: hp.title || '', description: hp.description || '',
          specs: (hp.specs || []).map(s => ({ icon: s.icon || '', label: s.label || '', value: s.value || '' })),
          hostingPercent: hp.hostingPercent ?? DEFAULT_HOSTING_PERCENT,
          billingTiers: (hp.billingTiers || defaultTiers).map(t => ({
            frequency: t.frequency || '', months: t.months ?? 1,
            discountPercent: t.discountPercent ?? 0, label: t.label || '', badge: t.badge || '',
          })),
          renewalNote: hp.renewalNote || '', coverageNote: hp.coverageNote || '',
          freeMonths: hp.freeMonths ?? 1, freeMonthNote: hp.freeMonthNote || '',
          freeMonthsVisible: resolveFreeMonthsVisible(hp),
        },
        modules: (j.modules || []).map(m => ({ id: m.id || '', name: m.name || '', price: m.price ?? 0, included: m.included !== false, is_required: m.is_required !== false })),
        paymentMethods: arrToText(j.paymentMethods), valueReasons: arrToText(j.valueReasons),
      };
    }
    case 'final_note':
      return { index: j.index || '', title: j.title || '', message: j.message || '', personalNote: j.personalNote || '', teamName: j.teamName || '', teamRole: j.teamRole || '', contactEmail: j.contactEmail || '', signature: j.signature || '', commitmentBadges: (j.commitmentBadges || []).map(b => ({ ...b })), validityMessage: j.validityMessage || '', thankYouMessage: j.thankYouMessage || '' };
    case 'proposal_summary':
      return { index: j.index || '', title: j.title || '', subtitle: j.subtitle || '', kpis: (j.kpis || []).map(k => ({ value: k.value || '', label: k.label || '', source: k.source || '' })), cards: (j.cards || []).map(c => ({ icon: c.icon || '', title: c.title || '', description: c.description || '', source: c.source || 'static' })) };
    case 'next_steps':
      return { index: j.index || '', title: j.title || '', introMessage: j.introMessage || '', steps: (j.steps || []).map(s => ({ ...s })), ctaMessage: j.ctaMessage || '', primaryCTA: { text: j.primaryCTA?.text || '', link: j.primaryCTA?.link || '' }, secondaryCTA: { text: j.secondaryCTA?.text || '', link: j.secondaryCTA?.link || '' }, contactMethods: (j.contactMethods || []).map(m => ({ ...m })), validityMessage: j.validityMessage || '', thankYouMessage: j.thankYouMessage || '' };
    case 'process_methodology':
      return { index: j.index || '', title: j.title || '', intro: j.intro || '', steps: (j.steps || []).map(s => ({ icon: s.icon || '', title: s.title || '', description: s.description || '', clientAction: s.clientAction || '' })) };
    case 'value_added_modules': {
      const ids = Array.isArray(j.module_ids) && j.module_ids.length
        ? j.module_ids
        : [...VALUE_ADDED_DEFAULT_MODULE_IDS];
      const justifications = j.justifications || {};
      const conditions = j.conditions || {};
      return {
        index: j.index || '',
        title: j.title || '',
        intro: j.intro || '',
        module_ids: [...ids],
        justifications: ids.reduce((acc, id) => {
          acc[id] = justifications[id] || '';
          return acc;
        }, {}),
        conditions: ids.reduce((acc, id) => {
          if (conditions[id]) {
            const cond = { ...conditions[id] };
            // Deep-copy the clause list so the editor never mutates the section.
            cond.terms_clauses = Array.isArray(cond.terms_clauses)
              ? cond.terms_clauses.map((c) => ({ label: c?.label || '', text: c?.text || '' }))
              : [];
            acc[id] = cond;
          }
          return acc;
        }, {}),
        general_terms: {
          title: j.general_terms?.title || '',
          clauses: Array.isArray(j.general_terms?.clauses)
            ? j.general_terms.clauses.map((c) => ({ label: c?.label || '', text: c?.text || '' }))
            : [],
        },
        footer_note: j.footer_note || '',
      };
    }
    case 'commercial_conditions': {
      const packages = Array.isArray(j.packages) ? j.packages : [];
      return {
        index: j.index || '',
        title: j.title || '',
        packagesTitle: j.packagesTitle || '',
        packagesIntro: j.packagesIntro || '',
        // Hour rates and packages are owned by the «Tarifa por hora» tab and
        // by the catalog; this form no longer renders them. They stay on the
        // form purely so formToJson can hand them back untouched — dropping
        // them here would wipe the proposal's packages on the next save.
        hourPackagesMode: j.hourPackagesMode === 'manual' ? 'manual' : 'auto',
        hourlyRate: j.hourlyRate ?? '',
        currency: j.currency || proposalData?.currency || 'COP',
        manualHourlyRate: j.manualHourlyRate ?? '',
        manualCurrency: j.manualCurrency || '',
        manualPackageRates: Array.isArray(j.manualPackageRates)
          ? j.manualPackageRates.map((e) => ({
            packageId: e?.packageId,
            hourlyRate: e?.hourlyRate,
          }))
          : [],
        packages: packages.map((p) => ({
          id: p.id,
          name: p.name || '',
          hours: p.hours ?? '',
          discountPercent: p.discountPercent ?? 0,
          note: p.note || '',
          hourlyRate: p.hourlyRate ?? '',
        })),
        effortBadge: j.effortBadge || '',
        scopeTitle: j.scopeTitle || '',
        scopeParagraphs: arrToText(j.scopeParagraphs || []),
      };
    }
    case 'roi_projection':
      return {
        index: j.index || '',
        title: j.title || '',
        subtitle: j.subtitle || '',
        methodology: j.methodology || '',
        kpis: (j.kpis || []).map(k => ({
          icon: k.icon || '',
          value: k.value || '',
          label: k.label || '',
          sublabel: k.sublabel || '',
          source: k.source || '',
        })),
        scenariosTitle: j.scenariosTitle || '',
        scenarios: (j.scenarios || []).map(s => ({
          name: s.name || '',
          label: s.label || '',
          icon: s.icon || '',
          assumptions: Array.isArray(s.assumptions) ? s.assumptions.map(a => String(a ?? '')) : [],
          metrics: (s.metrics || []).map(m => ({
            label: m.label || '',
            value: m.value || '',
            basis: m.basis || '',
            emphasis: !!m.emphasis,
          })),
        })),
        ctaNote: j.ctaNote || '',
      };
    default:
      return {};
  }
}

/**
 * Convert form state back to content_json for saving.
 * @param {object} formData - The reactive form object.
 * @param {string} type - The section_type.
 * @returns {object}
 */
export function formToJson(formData, type) {
  const f = formData;
  switch (type) {
    case 'greeting':
      return { proposalTitle: f.proposalTitle, clientName: f.clientName, inspirationalQuote: f.inspirationalQuote };
    case 'executive_summary':
      return { index: f.index, title: f.title, paragraphs: textToArr(f.paragraphs), highlightsTitle: f.highlightsTitle, highlights: textToArr(f.highlights) };
    case 'context_diagnostic':
      return { index: f.index, title: f.title, paragraphs: textToArr(f.paragraphs), issuesTitle: f.issuesTitle, issues: textToArr(f.issues), opportunityTitle: f.opportunityTitle, opportunity: f.opportunity };
    case 'conversion_strategy':
      return { index: f.index, title: f.title, intro: f.intro, steps: f.steps.map(s => ({ title: s.title, bullets: textToArr(s.bullets) })), resultTitle: f.resultTitle, result: f.result };
    case 'design_ux':
      return { index: f.index, title: f.title, paragraphs: textToArr(f.paragraphs), focusTitle: f.focusTitle, focusItems: textToArr(f.focusItems), objectiveTitle: f.objectiveTitle, objective: f.objective };
    case 'creative_support':
      return { index: f.index, title: f.title, paragraphs: textToArr(f.paragraphs), includesTitle: f.includesTitle, includes: textToArr(f.includes), closing: f.closing };
    case 'development_stages':
      return { index: f.index, title: f.title, intro: f.intro, currentLabel: f.currentLabel, stages: f.stages.map(s => ({ icon: s.icon, title: s.title, description: s.description, ...(s.current ? { current: true } : {}) })) };
    case 'functional_requirements': {
      const cleanGroup = (g) => {
        const out = {
          id: g.id, icon: g.icon, title: g.title, description: g.description,
          is_visible: g.is_visible !== undefined ? g.is_visible : true,
          selected: g.selected ?? false,
          items: (g.items || []).map(i => ({ ...(i.id ? { id: i.id } : {}), icon: i.icon, name: i.name, description: i.description, ...(i.price != null ? { price: i.price } : {}), is_required: i.is_required !== false })),
        };
        if (g.is_calculator_module) out.is_calculator_module = true;
        if (g.default_selected != null) out.default_selected = g.default_selected;
        if (g.is_always_included != null) out.is_always_included = g.is_always_included;
        if (g.is_invite) out.is_invite = true;
        if (g.invite_note) out.invite_note = g.invite_note;
        if (g._pasteMode) {
          out._editMode = 'paste';
          out.rawText = g._pasteText || '';
        } else {
          out._editMode = 'form';
        }
        return out;
      };
      return ensureFunctionalRequirementItemIds({
        index: f.index, title: f.title, intro: f.intro,
        groups: (f.groups || []).map(cleanGroup),
        additionalModules: (f.additionalModules || []).map(cleanGroup),
      });
    }
    case 'timeline':
      return { index: f.index, title: f.title, introText: f.introText, totalDuration: f.totalDuration, phases: f.phases.map(p => ({ title: p.title, duration: p.duration, description: p.description, tasks: textToArr(p.tasks), milestone: p.milestone })) };
    case 'investment': {
      const hp = f.hostingPlan || {};
      return {
        index: f.index, title: f.title, introText: f.introText,
        totalInvestment: f.totalInvestment, currency: f.currency,
        whatsIncluded: f.whatsIncluded, paymentOptions: f.paymentOptions,
        hostingPlan: {
          title: hp.title, description: hp.description,
          specs: (hp.specs || []).map(s => ({ icon: s.icon, label: s.label, value: s.value })),
          hostingPercent: hp.hostingPercent ?? DEFAULT_HOSTING_PERCENT,
          billingTiers: (hp.billingTiers || []).map(t => ({
            frequency: t.frequency, months: t.months, discountPercent: t.discountPercent,
            label: t.label, badge: t.badge || '',
          })),
          renewalNote: hp.renewalNote || '', coverageNote: hp.coverageNote || '',
          freeMonths: hp.freeMonths ?? 1, freeMonthNote: hp.freeMonthNote || '',
          freeMonthsVisible: resolveFreeMonthsVisible(hp),
        },
        modules: (f.modules || []).map(m => ({ id: m.id, name: m.name, price: m.price ?? 0, included: m.included !== false, is_required: m.is_required !== false })),
        paymentMethods: textToArr(f.paymentMethods), valueReasons: textToArr(f.valueReasons),
      };
    }
    case 'final_note':
      return { index: f.index, title: f.title, message: f.message, personalNote: f.personalNote, teamName: f.teamName, teamRole: f.teamRole, contactEmail: f.contactEmail, signature: f.signature, commitmentBadges: f.commitmentBadges, validityMessage: f.validityMessage, thankYouMessage: f.thankYouMessage };
    case 'proposal_summary':
      return { index: f.index, title: f.title, subtitle: f.subtitle, kpis: (f.kpis || []).filter(k => k.value || k.label).map(k => ({ value: k.value, label: k.label, source: k.source })), cards: (f.cards || []).map(c => ({ icon: c.icon, title: c.title, description: c.description, source: c.source })) };
    case 'next_steps':
      return { index: f.index, title: f.title, introMessage: f.introMessage, steps: f.steps, ctaMessage: f.ctaMessage, primaryCTA: f.primaryCTA, secondaryCTA: f.secondaryCTA, contactMethods: f.contactMethods, validityMessage: f.validityMessage, thankYouMessage: f.thankYouMessage };
    case 'process_methodology':
      return { index: f.index, title: f.title, intro: f.intro, steps: f.steps.map(s => ({ icon: s.icon, title: s.title, description: s.description, clientAction: s.clientAction })) };
    case 'value_added_modules': {
      const ids = Array.isArray(f.module_ids) ? f.module_ids : [];
      const justifications = {};
      const conditions = {};
      for (const id of ids) {
        justifications[id] = (f.justifications && f.justifications[id]) || '';
        const cond = f.conditions && f.conditions[id];
        if (cond && Object.values(cond).some((v) => v !== '' && v != null)) {
          conditions[id] = { ...cond };
        }
      }
      const generalClauses = Array.isArray(f.general_terms?.clauses)
        ? f.general_terms.clauses.filter((c) => String(c?.text || '').trim())
        : [];
      const payload = {
        index: f.index,
        title: f.title,
        intro: f.intro,
        module_ids: ids,
        justifications,
        conditions,
        footer_note: f.footer_note || '',
      };
      // Only persist general_terms when it carries content, so an empty editor
      // state never wipes a block the section already had.
      if (generalClauses.length || String(f.general_terms?.title || '').trim()) {
        payload.general_terms = {
          title: f.general_terms?.title || '',
          clauses: generalClauses,
        };
      }
      return payload;
    }
    case 'commercial_conditions': {
      const packages = Array.isArray(f.packages) ? f.packages : [];
      return {
        index: f.index,
        title: f.title,
        packagesTitle: f.packagesTitle || '',
        packagesIntro: f.packagesIntro || '',
        // Carried through untouched — owned by the «Tarifa por hora» tab, not
        // by this form. Emitting them back is what keeps a save here from
        // resetting the proposal's rates and packages.
        hourPackagesMode: f.hourPackagesMode === 'manual' ? 'manual' : 'auto',
        hourlyRate: f.hourlyRate === '' || f.hourlyRate == null
          ? 0 : Number(f.hourlyRate),
        currency: f.currency || 'COP',
        // Omitted when empty rather than coerced to 0: a 0 manual rate would
        // print $0 packages in the PDF instead of falling back to the catalog.
        ...(f.manualHourlyRate === '' || f.manualHourlyRate == null
          ? {} : { manualHourlyRate: Number(f.manualHourlyRate) }),
        ...(f.manualCurrency ? { manualCurrency: f.manualCurrency } : {}),
        ...(Array.isArray(f.manualPackageRates) && f.manualPackageRates.length
          ? {
            manualPackageRates: f.manualPackageRates.map((e) => ({
              packageId: e.packageId,
              hourlyRate: Number(e.hourlyRate),
            })),
          }
          : {}),
        packages: packages.map((p) => ({
          ...(p.id == null ? {} : { id: p.id }),
          name: p.name || '',
          hours: p.hours === '' || p.hours == null ? 0 : Number(p.hours),
          discountPercent: p.discountPercent === '' || p.discountPercent == null
            ? 0 : Number(p.discountPercent),
          note: p.note || '',
          // Per-package rate is optional: omit the key when empty so old
          // proposals keep using the section-level hourlyRate.
          ...(p.hourlyRate === '' || p.hourlyRate == null
            ? {} : { hourlyRate: Number(p.hourlyRate) }),
        })),
        effortBadge: f.effortBadge || '',
        scopeTitle: f.scopeTitle || '',
        scopeParagraphs: textToArr(f.scopeParagraphs || ''),
      };
    }
    case 'roi_projection':
      return {
        index: f.index,
        title: f.title,
        subtitle: f.subtitle,
        methodology: f.methodology || '',
        kpis: (f.kpis || [])
          .filter(k => k.value || k.label)
          .map(k => ({
            icon: k.icon || '',
            value: k.value || '',
            label: k.label || '',
            sublabel: k.sublabel || '',
            source: k.source || '',
          })),
        scenariosTitle: f.scenariosTitle || '',
        scenarios: (f.scenarios || [])
          .filter(s => s.label || s.name || (s.metrics || []).length)
          .map(s => ({
            name: s.name || '',
            label: s.label || '',
            icon: s.icon || '',
            assumptions: (s.assumptions || []).map(a => (a || '').trim()).filter(Boolean),
            metrics: (s.metrics || [])
              .filter(m => m.label || m.value)
              .map(m => ({
                label: m.label || '',
                value: m.value || '',
                ...(m.basis && m.basis.trim() ? { basis: m.basis.trim() } : {}),
                ...(m.emphasis ? { emphasis: true } : {}),
              })),
          })),
        ctaNote: f.ctaNote || '',
      };
    default:
      return {};
  }
}

/**
 * Convert form state to human-readable text for paste mode pre-fill.
 * @param {object} form - The reactive form object.
 * @param {string} type - The section_type.
 * @returns {string}
 */
export function formToReadableText(form, type) {
  const parts = [];
  const bullet = (items) => items.split('\n').filter(Boolean).map(l => `- ${l}`).join('\n');
  if (type === 'greeting') {
    if (form.clientName) parts.push(`Nombre del cliente: ${form.clientName}`);
    if (form.inspirationalQuote) parts.push(`\n"${form.inspirationalQuote}"`);
  } else if (type === 'executive_summary') {
    if (form.paragraphs) parts.push(form.paragraphs);
    if (form.highlightsTitle) parts.push(`\n${form.highlightsTitle}`);
    if (form.highlights) parts.push(bullet(form.highlights));
  } else if (type === 'context_diagnostic') {
    if (form.paragraphs) parts.push(form.paragraphs);
    if (form.issuesTitle) parts.push(`\n${form.issuesTitle}`);
    if (form.issues) parts.push(bullet(form.issues));
    if (form.opportunityTitle) parts.push(`\n${form.opportunityTitle}`);
    if (form.opportunity) parts.push(form.opportunity);
  } else if (type === 'conversion_strategy') {
    if (form.intro) parts.push(form.intro);
    for (const step of (form.steps || [])) {
      if (step.title) parts.push(`\n${step.title}`);
      if (step.bullets) parts.push(bullet(step.bullets));
    }
    if (form.resultTitle) parts.push(`\n${form.resultTitle}`);
    if (form.result) parts.push(form.result);
  } else if (type === 'design_ux') {
    if (form.paragraphs) parts.push(form.paragraphs);
    if (form.focusTitle) parts.push(`\n${form.focusTitle}`);
    if (form.focusItems) parts.push(bullet(form.focusItems));
    if (form.objectiveTitle) parts.push(`\n${form.objectiveTitle}`);
    if (form.objective) parts.push(form.objective);
  } else if (type === 'creative_support') {
    if (form.paragraphs) parts.push(form.paragraphs);
    if (form.includesTitle) parts.push(`\n${form.includesTitle}`);
    if (form.includes) parts.push(bullet(form.includes));
    if (form.closing) parts.push(`\n${form.closing}`);
  } else if (type === 'functional_requirements') {
    if (form.title) parts.push(form.title);
    if (form.intro) parts.push(form.intro);
    for (const g of (form.groups || [])) {
      parts.push(`\n${g.icon || ''} ${g.title || ''}`);
      if (g.description) parts.push(g.description);
    }
    for (const m of (form.additionalModules || [])) {
      parts.push(`\n${m.icon || ''} ${m.title || ''}`);
      if (m.description) parts.push(m.description);
    }
  } else if (type === 'development_stages') {
    for (const s of (form.stages || [])) {
      parts.push(`${s.icon || ''} ${s.title}${s.current ? ' (actual)' : ''}`);
      if (s.description) parts.push(`  ${s.description}`);
    }
  } else if (type === 'timeline') {
    if (form.introText) parts.push(form.introText);
    if (form.totalDuration) parts.push(`Duración total: ${form.totalDuration}`);
    for (const p of (form.phases || [])) {
      parts.push(`\n${p.title} — ${p.duration || ''}`);
      if (p.description) parts.push(p.description);
      if (p.tasks) parts.push(bullet(p.tasks));
      if (p.milestone) parts.push(`Hito: ${p.milestone}`);
    }
  } else if (type === 'investment') {
    if (form.introText) parts.push(form.introText);
    if (form.totalInvestment) parts.push(`Inversión total: ${form.totalInvestment} ${form.currency || 'COP'}`);
    if (form.whatsIncluded?.length) {
      parts.push('\nQué incluye:');
      for (const i of form.whatsIncluded) parts.push(`${i.icon || ''} ${i.title}: ${i.description || ''}`);
    }
    if (form.paymentOptions?.length) {
      parts.push('\nOpciones de pago:');
      for (const o of form.paymentOptions) parts.push(`- ${o.label}: ${o.description || ''}`);
    }
    if (form.valueReasons) parts.push(`\nRazones de valor:\n${bullet(form.valueReasons)}`);
    const hp = form.hostingPlan;
    if (hp?.title) {
      parts.push(`\n${hp.title}`);
      if (hp.description) parts.push(hp.description);
      if (hp.specs?.length) {
        for (const s of hp.specs) parts.push(`- ${s.icon || ''} ${s.label}: ${s.value}`);
      }
      if (hp.hostingPercent) parts.push(`Hosting: ${hp.hostingPercent}% de la inversión total`);
      if (resolveFreeMonthsVisible(hp)) {
        parts.push(`Meses gratis: ${Number(hp.freeMonths ?? 1)}`);
        if (hp.freeMonthNote) parts.push(hp.freeMonthNote);
      }
      if (hp.renewalNote) parts.push(`\n${hp.renewalNote}`);
    }
  } else if (type === 'final_note') {
    if (form.message) parts.push(form.message);
    if (form.personalNote) parts.push(`\n${form.personalNote}`);
    if (form.teamName) parts.push(`\n${form.teamName} — ${form.teamRole || ''}`);
    if (form.contactEmail) parts.push(form.contactEmail);
    if (form.validityMessage) parts.push(`\nValidez: ${form.validityMessage}`);
    if (form.thankYouMessage) parts.push(`\n${form.thankYouMessage}`);
    if (form.commitmentBadges?.length) {
      parts.push('\nBadges:');
      for (const b of form.commitmentBadges) parts.push(`${b.icon || ''} ${b.title}: ${b.description || ''}`);
    }
  } else if (type === 'proposal_summary') {
    if (form.subtitle) parts.push(form.subtitle);
    if (form.kpis?.length) {
      parts.push('\nKPIs:');
      for (const k of form.kpis) parts.push(`${k.value} — ${k.label}${k.source ? ` (${k.source})` : ''}`);
    }
    for (const c of (form.cards || [])) {
      parts.push(`${c.icon || ''} ${c.title}: ${c.description || ''}`);
    }
  } else if (type === 'next_steps') {
    if (form.introMessage) parts.push(form.introMessage);
    if (form.steps?.length) {
      parts.push('\nPasos:');
      for (const s of form.steps) parts.push(`- ${s.title}: ${s.description || ''}`);
    }
    if (form.ctaMessage) parts.push(`\n${form.ctaMessage}`);
    if (form.contactMethods?.length) {
      parts.push('\nContacto:');
      for (const m of form.contactMethods) parts.push(`${m.icon || ''} ${m.title}: ${m.value || ''}`);
    }
    if (form.validityMessage) parts.push(`\nValidez: ${form.validityMessage}`);
    if (form.thankYouMessage) parts.push(`\n${form.thankYouMessage}`);
  } else if (type === 'process_methodology') {
    if (form.intro) parts.push(form.intro);
    for (const s of (form.steps || [])) {
      parts.push(`\n${s.icon || ''} ${s.title || ''}`);
      if (s.description) parts.push(`  ${s.description}`);
      if (s.clientAction) parts.push(`  Acción del cliente: ${s.clientAction}`);
    }
  } else if (type === 'roi_projection') {
    if (form.subtitle) parts.push(form.subtitle);
    if (form.methodology) parts.push(`\nCómo calculamos esto: ${form.methodology}`);
    if (form.kpis?.length) {
      parts.push('\nKPIs:');
      for (const k of form.kpis) {
        parts.push(`${k.icon || ''} ${k.value} — ${k.label}${k.sublabel ? ` (${k.sublabel})` : ''}${k.source ? ` · ${k.source}` : ''}`);
      }
    }
    if (form.scenariosTitle) parts.push(`\n${form.scenariosTitle}`);
    for (const s of (form.scenarios || [])) {
      parts.push(`\n${s.icon || ''} ${s.label || s.name}`);
      for (const a of (s.assumptions || [])) {
        if (a) parts.push(`  - ${a}`);
      }
      for (const m of (s.metrics || [])) {
        parts.push(`  ${m.label}: ${m.value}${m.basis ? ` (${m.basis})` : ''}${m.emphasis ? ' ★' : ''}`);
      }
    }
    if (form.ctaNote) parts.push(`\n${form.ctaNote}`);
  }
  return parts.join('\n').trim();
}

/**
 * Convert a group's form data to human-readable text.
 * @param {object} group - A functional_requirements group object.
 * @returns {string}
 */
export function groupToReadableText(group) {
  const parts = [];
  if (group.title) parts.push(`${group.icon || ''} ${group.title}`.trim());
  if (group.description) parts.push(group.description);
  for (const item of (group.items || [])) {
    parts.push(`- ${item.icon || ''} **${item.name}**: ${item.description || ''}`);
  }
  return parts.join('\n').trim();
}

/**
 * Build the save payload from form state, applying paste mode metadata.
 * @param {object} form - The reactive form object.
 * @param {string} sectionType - The section_type.
 * @param {boolean} pasteMode - Whether paste mode is active.
 * @param {string} pasteText - The raw paste text.
 * @param {string} sectionTitle - The section title.
 * @param {boolean} isWidePanel - The is_wide_panel flag.
 * @param {number} sectionId - The section ID.
 * @returns {{ sectionId: number, payload: object }}
 */
export function buildSavePayload(form, sectionType, pasteMode, pasteText, sectionTitle, isWidePanel, sectionId) {
  const contentJson = formToJson(form, sectionType);
  if (pasteMode) {
    contentJson._editMode = 'paste';
    contentJson.rawText = pasteText;
  } else {
    contentJson._editMode = 'form';
    delete contentJson.rawText;
  }
  return {
    sectionId,
    payload: {
      title: sectionTitle,
      is_wide_panel: isWidePanel,
      content_json: contentJson,
    },
  };
}
