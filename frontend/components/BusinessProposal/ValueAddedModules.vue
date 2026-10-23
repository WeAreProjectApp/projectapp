<template>
  <section v-if="resolvedCards.length > 0" ref="sectionRef" class="value-added-modules min-h-screen w-full bg-surface py-16">
    <div class="w-full px-6 md:px-12 lg:px-24">
      <div class="max-w-5xl mx-auto">
        <!-- Header -->
        <div data-animate="fade-up" class="flex items-baseline gap-4 mb-8">
          <span class="text-text-muted font-light tracking-[0.25em] text-xs md:text-sm">
            {{ content.index || '' }}
          </span>
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-xl flex items-center justify-center bg-primary-soft">
              <span class="text-2xl">🎁</span>
            </div>
            <h2 class="text-text-brand font-light leading-tight text-3xl md:text-5xl">
              {{ content.title || defaultTitle }}
            </h2>
          </div>
        </div>

        <!-- Free badge + intro -->
        <div data-animate="fade-up" class="mb-10">
          <span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary-soft text-text-brand text-xs font-semibold uppercase tracking-wider mb-5">
            <span>✨</span>
            <span>{{ noCostLabel }}</span>
          </span>
          <div
            v-if="content.intro"
            class="text-text-default/80 font-light leading-relaxed text-lg md:text-xl"
            v-html="linkify(content.intro, content.text_formats?.['/intro'])"
          />
        </div>

        <!-- Cards grid -->
        <div data-animate="fade-up-stagger" class="grid md:grid-cols-2 gap-5 mb-8">
          <article
            v-for="card in resolvedCards"
            :key="card.id"
            class="value-card group bg-esmerald/5 p-6 rounded-2xl border border-esmerald/10 hover:border-esmerald/30 transition-colors cursor-pointer"
            :data-testid="`value-added-card-${card.id}`"
            role="button"
            tabindex="0"
            @click="openModal(card)"
            @keydown.enter.prevent="openModal(card)"
            @keydown.space.prevent="openModal(card)"
          >
            <div class="flex items-start gap-4">
              <div class="w-11 h-11 rounded-xl bg-primary-soft border border-esmerald/10 flex items-center justify-center flex-shrink-0">
                <span class="text-2xl">{{ card.icon || '🧩' }}</span>
              </div>
              <div class="flex-1">
                <div class="flex items-start justify-between gap-3 mb-2">
                  <h3 class="font-bold text-text-brand text-lg leading-snug">{{ card.title }}</h3>
                  <span class="text-xs font-semibold text-text-brand bg-primary-soft px-2 py-0.5 rounded-full whitespace-nowrap">
                    {{ freeBadge }}
                  </span>
                </div>
                <p class="text-sm text-text-default/75 font-light leading-relaxed mb-3">
                  {{ card.justification }}
                </p>
                <BaseRichTextContent v-if="card.description" class="text-xs text-text-default/60 italic leading-relaxed mb-3" :source="card.description" :format="card.text_formats?.['/description'] || 'plain'" />

                <!-- Condition badges (duration + minimum gate "condicionado") -->
                <div v-if="card.durationLabel || card.minimumNote" class="flex flex-wrap gap-2 mb-2">
                  <span v-if="card.durationLabel" class="inline-flex items-center gap-1 text-[11px] font-semibold text-text-brand bg-primary-soft px-2 py-0.5 rounded-full">
                    ⏳ {{ card.durationLabel }}
                  </span>
                  <span
                    v-if="card.minimumNote"
                    class="inline-flex items-center gap-1 text-[11px] font-semibold text-text-muted bg-surface-raised border border-border-default px-2 py-0.5 rounded-full"
                    :data-testid="`value-added-minimum-${card.id}`"
                  >
                    🔒 {{ card.minimumNote }}
                  </span>
                </div>
                <!-- eslint-disable-next-line vue/no-v-html — renderInlineBold escapes all HTML first -->
                <p
                  v-if="card.discretionaryNote"
                  class="text-[11px] text-text-default/55 italic leading-relaxed mb-3 [&_strong]:font-semibold [&_strong]:not-italic"
                  v-html="renderInlineBold(card.discretionaryNote)"
                />

                <!-- Bottom row: "Ver detalle" (left) · "Términos y condiciones" (right) -->
                <div class="flex items-center justify-between gap-3 mt-1">
                  <span class="inline-flex items-center gap-1 text-xs font-semibold text-green-light group-hover:text-text-brand transition-colors">
                    {{ viewDetailLabel }}
                    <svg class="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                  </span>
                  <button
                    v-if="card.termsClauses.length || card.terms || card.minimumNote || card.durationLabel"
                    type="button"
                    class="inline-flex items-center gap-1 text-xs font-medium text-text-subtle hover:text-text-brand transition-colors"
                    :data-testid="`value-added-terms-${card.id}`"
                    @click.stop="openTerms(card)"
                    @keydown.enter.stop.prevent="openTerms(card)"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h7l5 5v11a2 2 0 01-2 2z" />
                    </svg>
                    {{ termsLabel }}
                  </button>
                </div>
              </div>
            </div>
          </article>
        </div>

        <!-- General legal provisions — same block, same order as the PDF annex.
             Collapsed by default so the section stays readable. -->
        <details
          v-if="generalClauses.length"
          data-animate="fade-up"
          class="group border border-border-default rounded-xl bg-surface-raised"
          data-testid="value-added-general-terms"
        >
          <summary class="flex items-center justify-between gap-3 px-5 py-4 cursor-pointer list-none">
            <span class="text-sm font-medium text-text-brand">{{ generalTermsTitle }}</span>
            <svg class="w-4 h-4 text-text-subtle transition-transform group-open:rotate-180 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </summary>
          <ol class="px-5 pb-5 space-y-4 border-t border-border-muted pt-4">
            <li
              v-for="(clause, idx) in generalClauses"
              :key="idx"
              class="border-l-2 border-border-default pl-4"
            >
              <p
                v-if="clause.label"
                class="text-[11px] font-semibold uppercase tracking-wider text-text-subtle mb-1"
                data-testid="value-added-general-label"
              >
                {{ clause.label }}
              </p>
              <!-- eslint-disable-next-line vue/no-v-html — renderInlineBold escapes all HTML first -->
              <p
                class="text-sm text-text-default/75 font-light leading-relaxed [&_strong]:font-semibold [&_strong]:text-text-default"
                v-html="renderInlineBold(clause.text)"
              />
            </li>
          </ol>
        </details>

        <!-- Footer note -->
        <div v-if="content.footer_note" data-animate="fade-up" class="bg-primary-soft border border-primary/20 rounded-xl px-5 py-4 text-center">
          <p class="text-text-brand text-sm md:text-base font-medium">
            {{ content.footer_note }}
          </p>
        </div>
      </div>
    </div>

    <FunctionalRequirementsModal
      :visible="modalVisible"
      :group="selectedGroup"
      :item-requirements-map="itemRequirementsMap"
      :language="language"
      @close="modalVisible = false"
    />

    <ModuleTermsModal
      :visible="termsModalVisible"
      :title="termsCard.title"
      :icon="termsCard.icon"
      :terms="termsCard.terms"
      :clauses="termsCard.clauses"
      :general-terms-title="generalClauses.length ? generalTermsTitle : ''"
      :notes="termsCard.notes"
      :language="language"
      @close="termsModalVisible = false"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useSectionAnimations } from '~/composables/useSectionAnimations';
import { linkify } from '~/composables/useLinkify';
import { trackRequirementClick } from '~/utils/trackRequirementClick';
import { renderInlineBold } from '~/utils/renderInlineBold';
import FunctionalRequirementsModal from './FunctionalRequirementsModal.vue';
import ModuleTermsModal from './ModuleTermsModal.vue';

const props = defineProps({
  text_formats: { type: Object, default: () => ({}) },
  section: {
    type: Object,
    default: () => ({ content_json: {} }),
  },
  proposal: {
    type: Object,
    default: () => ({ sections: [] }),
  },
  proposalUuid: {
    type: String,
    default: '',
  },
  itemRequirementsMap: {
    type: Object,
    default: () => ({}),
  },
  // Client-facing effective total (base + selected modules) used to gate the
  // per-module minimums ("condicionado"). Compared in the proposal currency.
  effectiveTotal: {
    type: [Number, String],
    default: 0,
  },
});

const sectionRef = ref(null);
useSectionAnimations(sectionRef);

const content = computed(() => props.section?.content_json || {});

const language = computed(() => props.proposal?.language || 'es');

const i18n = {
  es: {
    defaultTitle: 'Incluido sin costo adicional',
    noCost: 'Sin costo adicional',
    free: 'Gratis',
    viewDetail: 'Ver detalle',
    terms: 'Términos y condiciones',
    from: 'Disponible en proyectos desde',
    months: (n) => `Disponible por ${n} ${n === 1 ? 'mes' : 'meses'}`,
  },
  en: {
    defaultTitle: 'Included at no extra cost',
    noCost: 'No extra cost',
    free: 'Free',
    viewDetail: 'View details',
    terms: 'Terms & conditions',
    from: 'Available for projects from',
    months: (n) => `Available for ${n} ${n === 1 ? 'month' : 'months'}`,
  },
};
const t = computed(() => i18n[language.value] || i18n.es);

const defaultTitle = computed(() => t.value.defaultTitle);
const noCostLabel = computed(() => t.value.noCost);
const freeBadge = computed(() => t.value.free);
const viewDetailLabel = computed(() => t.value.viewDetail);
const termsLabel = computed(() => t.value.terms);

const currency = computed(() => props.proposal?.currency || 'COP');
const effectiveTotalNum = computed(() => Number(props.effectiveTotal) || 0);

function formatMoney(value) {
  const num = Number(value) || 0;
  return `$${num.toLocaleString('es-CO')} ${currency.value}`;
}

const moduleCatalog = computed(() => {
  const sections = props.proposal?.sections || [];
  const fr = sections.find((s) => s.section_type === 'functional_requirements');
  const groups = fr?.content_json?.groups || [];
  const lookup = {};
  for (const group of groups) {
    if (group && group.id) {
      lookup[group.id] = group;
    }
  }
  return lookup;
});

const resolvedCards = computed(() => {
  const ids = Array.isArray(content.value.module_ids) ? content.value.module_ids : [];
  const justifications = content.value.justifications || {};
  const conditions = content.value.conditions || {};
  const catalog = moduleCatalog.value;
  return ids
    .map((id) => {
      const group = catalog[id];
      if (!group) return null;
      const cond = conditions[id] || {};
      const minimum = currency.value === 'USD'
        ? cond.min_price_usd
        : cond.min_price_cop;
      const meetsMinimum = !minimum || effectiveTotalNum.value >= Number(minimum);
      // "Condicionado": show the minimum note only when the effective total
      // does not reach it. The module is never hidden.
      const minimumNote = (minimum && !meetsMinimum)
        ? `${t.value.from} ${formatMoney(minimum)}`
        : '';
      const durationLabel = cond.duration_months
        ? t.value.months(Number(cond.duration_months))
        : '';
      const discretionaryNote = cond.discretionary_note || '';
      const terms = cond.terms || '';
      const termsClauses = Array.isArray(cond.terms_clauses) ? cond.terms_clauses : [];
      const notes = [durationLabel, minimumNote].filter(Boolean);
      return {
        id,
        icon: group.icon,
        title: group.title,
        description: group.description,
        items: Array.isArray(group.items) ? group.items : [],
        justification: justifications[id] || '',
        minimumNote,
        durationLabel,
        discretionaryNote,
        terms,
        termsClauses,
        notes,
      };
    })
    .filter(Boolean);
});

const modalVisible = ref(false);
const selectedGroup = ref({});

function openModal(card) {
  selectedGroup.value = card;
  modalVisible.value = true;
  trackRequirementClick(props.proposalUuid, card);
}

const termsModalVisible = ref(false);
const termsCard = ref({ title: '', icon: '', terms: '', clauses: [], notes: [] });

// Cross-cutting legal provisions; same source the PDF annex reads.
const generalTerms = computed(() => content.value.general_terms || {});

const generalClauses = computed(() => {
  const list = generalTerms.value?.clauses;
  if (!Array.isArray(list)) return [];
  return list
    .filter((c) => c && typeof c === 'object' && String(c.text || '').trim())
    .map((c) => ({ label: String(c.label || '').trim(), text: String(c.text) }));
});

const generalTermsTitle = computed(() => (
  String(generalTerms.value?.title || '').trim()
  || (language.value === 'en'
    ? 'General provisions applicable to the included modules'
    : 'Disposiciones generales aplicables a los módulos incluidos')
));

function openTerms(card) {
  termsCard.value = {
    title: card.title,
    icon: card.icon,
    terms: card.terms,
    clauses: card.termsClauses,
    notes: card.notes,
  };
  termsModalVisible.value = true;
}
</script>

<style scoped>
.value-card {
  transition: all 0.3s ease;
}

.value-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(7, 89, 73, 0.06);
}

.value-card:focus-visible {
  outline: 2px solid rgba(16, 185, 129, 0.6);
  outline-offset: 2px;
}
</style>
