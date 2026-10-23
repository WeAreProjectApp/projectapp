<template>
  <section>
    <SectionHeader :index="content.index" :title="content.title" fallback="Costo y Formas de Pago" />
    <BaseRichTextContent v-if="content.intro" class="text-text-brand/80 dark:text-text-brand/80 leading-relaxed" :source="content.intro" :format="content.text_formats?.['/intro'] || 'plain'" />

    <div
      v-if="parsedBullets.length"
      class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4"
      data-testid="cost-value-cards"
    >
      <div
        v-for="(item, idx) in parsedBullets"
        :key="idx"
        class="bg-surface dark:bg-primary-soft border border-input-border rounded-2xl p-5 shadow-sm"
      >
        <div class="flex items-start gap-3">
          <span class="mt-1 shrink-0 size-2 rounded-full bg-accent-soft" aria-hidden="true" />
          <div>
            <p class="font-semibold text-text-brand dark:text-text-brand leading-snug">{{ item.title }}</p>
            <BaseRichTextContent v-if="item.body" class="text-sm text-text-brand/70 dark:text-text-brand/70 leading-relaxed mt-1" :source="item.body" :format="item.format || 'plain'" />
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="hasInvestmentCard"
      class="my-6 relative overflow-hidden bg-surface dark:bg-primary-soft text-text-brand dark:text-text-brand rounded-2xl p-6 shadow-sm border border-input-border"
      data-testid="cost-investment-card"
    >
      <div class="absolute inset-0 bg-gradient-to-br from-lemon/0 via-lemon/5 to-lemon/10 pointer-events-none" />

      <div class="relative space-y-6">
        <header
          v-if="investmentFormatted || durationLabel"
          class="flex flex-wrap items-end justify-between gap-3"
        >
          <div>
            <div class="text-xs font-medium text-text-brand/60 dark:text-text-brand/60 uppercase tracking-[0.2em]">Inversión</div>
            <div v-if="investmentFormatted" class="mt-1 text-4xl font-semibold text-text-brand dark:text-text-brand tabular-nums leading-none">
              {{ investmentFormatted }}
              <span class="text-2xl text-text-brand/60 dark:text-text-brand/60 ml-1">{{ currencyCode }}</span>
            </div>
          </div>
          <div
            v-if="durationLabel"
            class="inline-flex items-center gap-1.5 text-xs text-text-brand/70 dark:text-text-brand/70 bg-primary/5 dark:bg-primary-soft ring-1 ring-esmerald/10 dark:ring-esmerald-light/15 rounded-full px-3 py-1"
          >
            <span class="size-1.5 rounded-full bg-accent-soft" aria-hidden="true" />
            <span>{{ durationLabel }}</span>
          </div>
        </header>

        <div
          v-if="paymentSegments.length === 2"
          class="flex flex-col sm:flex-row w-full overflow-hidden rounded-xl ring-1 ring-esmerald/10 dark:ring-esmerald-light/15"
          role="presentation"
          data-testid="cost-segmented-bar"
        >
          <div
            v-for="seg in paymentSegments"
            :key="seg.key"
            :style="{ flexGrow: seg.pct }"
            :class="['flex flex-col gap-2 px-5 py-5 min-w-0 text-text-brand', seg.barClass]"
            :data-testid="`cost-bar-${seg.key}`"
          >
            <div class="flex items-baseline justify-between gap-3">
              <span class="text-3xl font-semibold tabular-nums leading-none">{{ seg.pct }}%</span>
              <span class="text-[11px] font-semibold uppercase tracking-[0.18em] opacity-75">{{ seg.label }}</span>
            </div>
            <div
              v-if="seg.amountFormatted"
              class="text-sm font-medium tabular-nums opacity-90"
              :data-testid="`cost-segment-amount-${seg.key}`"
            >{{ seg.amountFormatted }} {{ currencyCode }}</div>
            <BaseRichTextContent
              v-if="seg.detail"
              class="text-xs leading-relaxed opacity-80"
              :data-testid="`cost-segment-detail-${seg.key}`"
             :source="seg.detail" :format="seg.text_formats?.['/detail'] || 'plain'" />
          </div>
        </div>

        <ul
          v-if="!paymentSegments.length && fallbackPaymentItems.length"
          class="space-y-2 text-text-brand/80 dark:text-text-brand/80"
          data-testid="cost-fallback-list"
        >
          <li
            v-for="(item, idx) in fallbackPaymentItems"
            :key="idx"
            class="flex gap-3 items-baseline"
          >
            <span class="mt-2 shrink-0 size-1.5 rounded-full bg-accent-soft" aria-hidden="true" />
            <span class="font-semibold text-text-brand dark:text-text-brand">{{ item.label }}</span>
            <BaseRichTextContent class="text-text-brand/70 dark:text-text-brand/70" :source="item.detail" :format="item.text_formats?.['/detail'] || 'plain'" />
          </li>
        </ul>
      </div>
    </div>

    <aside
      v-if="content.note"
      class="mt-6 flex gap-3 border-l-4 border-lemon/70 bg-primary/5 dark:bg-primary-soft text-text-brand/80 dark:text-text-brand/80 px-4 py-3 rounded-r-lg text-sm"
    >
      <span class="shrink-0 inline-flex items-center text-[10px] font-semibold uppercase tracking-wider text-text-brand dark:text-accent bg-accent-soft/30 dark:bg-accent-soft/15 rounded px-1.5 py-0.5 h-fit">Nota</span>
      <BaseRichTextContent class="leading-relaxed" :source="content.note" :format="content.text_formats?.['/note'] || 'plain'" />
    </aside>
  </section>
</template>

<script setup>
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import { computed } from 'vue';
import SectionHeader from './SectionHeader.vue';

const SIDES = [
  {
    key: 'initial',
    pctKey: 'payment_initial_pct',
    termKey: 'initial_pct',
    defaultLabel: 'al inicio',
    barClass: 'bg-accent-soft/80',
  },
  {
    key: 'final',
    pctKey: 'payment_final_pct',
    termKey: 'final_pct',
    defaultLabel: 'al final',
    barClass: 'bg-accent-soft/15',
  },
];

const CURRENCY_FMT = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });

function formatCurrency(n) {
  const value = Number(n);
  if (!Number.isFinite(value) || value === 0) return '';
  return CURRENCY_FMT.format(value);
}

function normalizePct(raw) {
  if (raw === undefined || raw === null || raw === '') return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

const props = defineProps({
  content: { type: Object, required: true },
  diagnostic: { type: Object, required: true },
  renderContext: { type: Object, default: () => ({}) },
});

const investmentAmount = computed(() => {
  const n = Number(props.diagnostic?.investment_amount);
  return Number.isFinite(n) && n > 0 ? n : 0;
});

const investmentFormatted = computed(() => formatCurrency(investmentAmount.value));

const currencyCode = computed(() => props.diagnostic?.currency || props.renderContext?.currency || '');

const durationLabel = computed(
  () => props.diagnostic?.duration_label || props.renderContext?.duration_label || '',
);

const valueBullets = computed(() => {
  const arr = props.content?.valueBullets;
  if (!Array.isArray(arr)) return [];
  return arr.map((s) => (typeof s === 'string' ? s.trim() : '')).filter(Boolean);
});

const parsedBullets = computed(() =>
  valueBullets.value.map((s, index) => {
    const format = props.content.text_formats?.['/valueBullets/' + index];
    if (format && format !== 'plain') return { title: '', body: s, format };
    const sep = s.indexOf(': ');
    if (sep === -1) return { title: s, body: '' };
    return { title: s.slice(0, sep), body: s.slice(sep + 2) };
  }),
);

const paymentDescription = computed(() => {
  const desc = props.content?.paymentDescription;
  return Array.isArray(desc) ? desc : [];
});

const paymentSegments = computed(() => {
  // renderContext wins over diagnostic.payment_terms — public view receives
  // pcts via render_context; admin preview falls back to the raw model field.
  const ctx = props.renderContext || {};
  const terms = props.diagnostic?.payment_terms || {};
  const segments = SIDES
    .map((side, idx) => ({
      side,
      pct: normalizePct(ctx[side.pctKey] ?? terms[side.termKey]),
      desc: paymentDescription.value[idx] || {},
    }))
    .filter((s) => s.pct !== null);
  return segments.map(({ side, pct, desc }) => {
    const amount = investmentAmount.value
      ? Math.round((investmentAmount.value * pct) / 100)
      : 0;
    return {
      key: side.key,
      pct,
      label: desc.label || side.defaultLabel,
      detail: desc.detail || '',
      barClass: side.barClass,
      amount,
      amountFormatted: formatCurrency(amount),
    };
  });
});

const fallbackPaymentItems = computed(() =>
  paymentDescription.value
    .map((item) => ({
      label: item?.label || '',
      detail: item?.detail || '',
    }))
    .filter((item) => item.label || item.detail),
);

const hasInvestmentCard = computed(
  () =>
    !!investmentFormatted.value
    || paymentSegments.value.length > 0
    || fallbackPaymentItems.value.length > 0
    || !!durationLabel.value,
);
</script>
