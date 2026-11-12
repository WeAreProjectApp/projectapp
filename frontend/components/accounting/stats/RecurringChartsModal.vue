<template>
  <StatsModal
    :open="open"
    title="Gráficos de pagos recurrentes"
    subtitle="Distribución del gasto recurrente, siempre en equivalente COP mensual."
    :tabs="TABS"
    :model-value="activeTab"
    size="full"
    @update:model-value="activeTab = $event"
    @close="emit('close')"
  >
    <template #default="{ activeTab: tab }">
      <div data-testid="recurring-charts-modal">
        <!-- One filter row above everything it scopes: every tab re-renders
             against the same slice, so the numbers always agree. -->
        <div
          class="flex flex-wrap items-center gap-2 pb-4 mb-4 border-b border-border-muted"
          data-testid="recurring-charts-filters"
        >
          <template v-if="inheritedChips.length">
            <span class="text-xs text-text-muted">Filtros de la tabla:</span>
            <span
              v-for="chip in inheritedChips"
              :key="chip"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-surface-raised text-xs text-text-default"
              data-testid="recurring-charts-chip"
            >{{ chip }}</span>
            <BaseButton
              variant="ghost"
              size="sm"
              data-testid="recurring-charts-clear-filters"
              @click="emit('clear-filters')"
            >
              Ver todo
            </BaseButton>
            <span class="w-px h-5 bg-border-muted mx-1" aria-hidden="true" />
          </template>

          <label class="flex items-center gap-2 text-xs text-text-muted">
            <span>Categoría</span>
            <BaseSelect
              :model-value="categoryFilter"
              :options="categoryOptions"
              size="sm"
              data-testid="recurring-charts-category"
              @update:model-value="categoryFilter = $event"
            />
          </label>

          <p class="ml-auto text-xs text-text-muted" data-testid="recurring-charts-budget-scope">
            Solo pagos activos; inactivos y archivados no cuentan en el presupuesto.
          </p>

          <BaseButton
            variant="secondary"
            size="sm"
            :disabled="!activeChartId"
            disabled-reason="Espera a que el gráfico activo termine de renderizarse."
            data-testid="recurring-charts-download"
            @click="downloadActiveChart"
          >
            <BaseActionIcon action="download" />
            <span>PNG</span>
          </BaseButton>
        </div>

        <!-- Above the tab panels, because the category scopes all four of them
             — and outside the empty state below, so a category with nothing
             left to show never strands the operator without a way back. -->
        <div
          v-if="drilledCategory"
          class="flex flex-wrap items-center gap-3 px-3 py-2 mb-4 rounded-xl bg-surface-raised"
          data-testid="recurring-charts-drill-header"
        >
          <span
            class="shrink-0 w-3 h-3 rounded-sm"
            :style="{ backgroundColor: drilledCategory.color }"
            aria-hidden="true"
          />
          <div class="min-w-0">
            <p class="text-sm text-text-default">
              <span class="font-semibold">{{ drilledCategory.name }}</span>
              <span class="text-text-muted">
                · {{ formatMonthlyCop(total) }}/mes
                · {{ formatPercent(shareOfAll(total)) }} del total general
              </span>
            </p>
            <p class="text-xs text-text-muted">
              Los porcentajes de abajo son sobre esta categoría.
            </p>
          </div>
          <BaseButton
            variant="ghost"
            size="sm"
            class="ml-auto"
            data-testid="recurring-charts-back"
            @click="clearDrill"
          >
            <BaseActionIcon action="back" />
            <span>Todas las categorías</span>
          </BaseButton>
        </div>

        <BaseEmptyState
          v-if="!chartRows.length"
          :title="emptyTitle"
          :description="emptyDescription"
        />

        <!-- Panels use v-if, never v-show: ApexCharts mounted inside a hidden
             panel measures width 0 and renders as a sliver. -->
        <template v-else>
          <div v-if="tab === 'category'" class="space-y-5">
            <div
              class="grid grid-cols-1 lg:grid-cols-2 gap-6"
              :class="isDrilled ? 'items-start' : 'items-center'"
            >
              <StatsDonutChart
                :labels="donutSlices.map((slice) => slice.name)"
                :values="donutSlices.map((slice) => slice.total)"
                :colors="donutSlices.map((slice) => slice.color)"
                :tooltip-value-formatter="donutTooltip"
                :total-label="isDrilled ? 'Total categoría' : 'Total'"
                :height="320"
                :show-legend="false"
                chart-id="recurring-chart-category"
                empty-title="Sin pagos que distribuir"
                @select="drillToDonutSlice"
              />
              <!-- Capped to the donut's own height: a category of fifteen
                   payments would otherwise scroll the chart out of view. -->
              <div class="lg:max-h-[320px] lg:overflow-y-auto">
                <RecurringChartLegend
                  :items="legendItems"
                  :clickable="!isDrilled"
                  @select="toggleCategory"
                />
              </div>
            </div>
            <p
              v-if="singleItemNote"
              class="text-xs text-text-muted"
              data-testid="recurring-charts-single-item"
            >
              {{ singleItemNote }}
            </p>
            <p class="text-xs text-text-muted">
              <template v-if="isDrilled">
                Estás viendo el reparto dentro de {{ drilledCategory.name }}. Volvé a
                todas las categorías para comparar entre ellas.
              </template>
              <template v-else>
                Clic en una porción o en una fila para ver sólo esa categoría.
              </template>
            </p>
          </div>

          <div v-else-if="tab === 'items'" class="space-y-4">
            <StatsBarChart
              :series="[{ name: 'Equiv. COP mensual', data: items.map((item) => item.total) }]"
              :categories="items.map((item) => item.name)"
              :colors="items.map((item) => colorFor(item.categoryId))"
              :tooltip-value-formatter="itemTooltip"
              :height="itemsChartHeight"
              horizontal
              distributed
              chart-id="recurring-chart-items"
              empty-title="Sin pagos que ordenar"
            />
            <p class="text-xs text-text-muted">
              Cada barra toma el color de su categoría. Ordenadas de mayor a menor
              costo mensual.
            </p>
          </div>

          <div v-else-if="tab === 'composition'" class="space-y-5">
            <StatsSummaryStrip :items="compositionStrip" />
            <StatsBarChart
              :series="compositionSeries"
              :categories="COMPOSITION_ROWS.map((row) => row.label)"
              :colors="[palette.categorical[0], palette.categorical[1]]"
              :tooltip-value-formatter="compositionTooltip"
              :height="220"
              horizontal
              stacked
              :show-legend="false"
              chart-id="recurring-chart-composition"
              empty-title="Sin pagos que componer"
            />
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div v-for="row in compositionRows" :key="row.field">
                <p class="text-xs text-text-muted uppercase tracking-wider mb-1">
                  {{ row.label }}
                </p>
                <RecurringChartLegend :items="row.legend" />
              </div>
            </div>
          </div>

          <div v-else-if="tab === 'calendar'" class="min-w-0 space-y-4" data-testid="recurring-calendar">
            <StatsBarChart
              :series="[{ name: 'Equiv. COP mensual', data: calendar.days.map((day) => day.total) }]"
              :categories="calendar.days.map((day) => String(day.day))"
              :colors="[palette.categorical[0]]"
              :tooltip-value-formatter="dayTooltip"
              :height="isCompactCalendar ? calendar.days.length * 32 + 80 : 280"
              :horizontal="isCompactCalendar"
              chart-id="recurring-chart-calendar"
              empty-title="Sin cobros con día definido"
            />

            <div
              v-if="calendar.withoutDay.total > 0"
              class="rounded-xl border border-warning-strong/30 bg-warning-soft px-4 py-3"
              data-testid="recurring-charts-no-day"
            >
              <p class="text-sm font-semibold text-text-default">
                Sin día definido: {{ formatMonthlyCop(calendar.withoutDay.total) }}
                ({{ formatPercent(calendar.withoutDay.pct) }} del total)
              </p>
              <p class="text-xs text-text-muted mt-1">
                {{ calendar.withoutDay.names.join(' · ') }} — no aparecen en el
                calendario porque no tienen día de cobro. Completá el campo Día
                para verlos aquí.
              </p>
            </div>

            <p class="text-xs text-text-muted">
              Los pagos que no son mensuales aparecen prorrateados: su cuota
              mensual, no el cobro real de ese día.
            </p>
          </div>
        </template>
      </div>
    </template>
  </StatsModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import StatsModal from '~/components/stats/StatsModal.vue';
import StatsSummaryStrip from '~/components/stats/StatsSummaryStrip.vue';
import StatsBarChart from '~/components/stats/charts/StatsBarChart.vue';
import StatsDonutChart from '~/components/stats/charts/StatsDonutChart.vue';
import RecurringChartLegend from '~/components/accounting/stats/RecurringChartLegend.vue';
import { useChartTheme } from '~/composables/useChartTheme';
import { formatMoney } from '~/utils/formatMoney';
import { formatPercent, percentOf } from '~/utils/percent';
import {
  UNCATEGORIZED_KEY,
  UNCATEGORIZED_LABEL,
  formatMonthlyCop,
  sumMonthlyCop,
} from '~/utils/recurring';
import {
  OTHER_ITEMS_KEY,
  OTHER_ITEMS_LABEL,
  byBillingDay,
  categoryColorMap,
  foldChartBuckets,
  itemsByMonthlyCost,
  splitBy,
  totalsByCategory,
  visibleRows,
} from '~/utils/recurringCharts';
import { toSlug } from '~/utils/slugify';
import { usePanelViewportProfile } from '~/composables/usePanelViewportProfile';

/**
 * The recurring spend, seen instead of read.
 *
 * Every figure is the monthly COP equivalent, so the four tabs always add up
 * to the same total and to the "Costo mensual (COP)" card on the page behind.
 * `rows` arrives already filtered by the table, which is why the inherited
 * filters are spelled out as chips: a donut opened from the USD tab is a
 * legitimate view, but only if the reader can see why it does not match the
 * monthly total they know.
 *
 * The category filter does not just narrow the charts, it changes the question
 * they answer. Unfiltered the reader asks how the spend splits BETWEEN
 * categories; once they pick one they are asking how it splits INSIDE it. So
 * the donut, its legend, its center total and its copy all switch to the
 * payments of that category — see `drilledCategory`.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  /** Rows as the table has them filtered. */
  rows: { type: Array, default: () => [] },
  categories: { type: Array, default: () => [] },
  /** Reference COP-per-USD rate, shown as context in the composition tab. */
  usdExchangeRate: { type: [Number, String], default: null },
  /** Human labels of the filters the table is applying, e.g. ['Moneda: USD']. */
  inheritedChips: { type: Array, default: () => [] },
});

const emit = defineEmits(['close', 'clear-filters']);
const { profile } = usePanelViewportProfile();
const isCompactCalendar = computed(() => profile.value === 'compact');

const TABS = [
  { id: 'category', label: 'Categoría' },
  { id: 'items', label: 'Ítems' },
  { id: 'composition', label: 'Composición' },
  { id: 'calendar', label: 'Calendario' },
];

const CHART_IDS = {
  category: 'recurring-chart-category',
  items: 'recurring-chart-items',
  composition: 'recurring-chart-composition',
  calendar: 'recurring-chart-calendar',
};

const COMPOSITION_ROWS = [
  { field: 'currency', label: 'Moneda' },
  { field: 'payment_method', label: 'Método' },
  { field: 'cost_type', label: 'Tipo' },
];

const activeTab = ref('category');
const categoryFilter = ref('');

const { palette } = useChartTheme();

// Reopening starts from the tab's own view again; a category drilled into
// three sessions ago is not a filter the reader remembers setting.
watch(() => props.open, (open) => {
  if (!open) return;
  activeTab.value = 'category';
  categoryFilter.value = '';
});

const colors = computed(() =>
  categoryColorMap(props.categories, palette.value.categorical, palette.value.text),
);

function colorFor(key) {
  return colors.value.get(key) || palette.value.text;
}

const activeRows = computed(() =>
  visibleRows(props.rows),
);

/**
 * A row the category catalog cannot place — no category, or one the catalog no
 * longer carries. Same rule totalsByCategory() uses to build its trailing
 * bucket, so drilling into "Sin categoría" adds up to what the legend showed.
 */
function isUncategorized(row) {
  return !props.categories.some((category) => String(category.id) === String(row.category));
}

function matchesCategoryFilter(row) {
  if (categoryFilter.value === UNCATEGORIZED_KEY) return isUncategorized(row);
  return String(row.category) === categoryFilter.value;
}

const chartRows = computed(() => {
  if (!categoryFilter.value) return activeRows.value;
  return activeRows.value.filter(matchesCategoryFilter);
});

const total = computed(() => sumMonthlyCop(chartRows.value));

/**
 * The whole visible set, before the category drill — the base of every "del
 * total general" figure. Keeping it separate from `total` is what lets a
 * drilled item state both of its shares: 90,9% of its category AND 87,6% of
 * everything, two answers to two different questions.
 */
const overallTotal = computed(() => sumMonthlyCop(activeRows.value));

function shareOfAll(value) {
  return percentOf(value, overallTotal.value);
}

/**
 * The category the charts are drilled into, or null for the general view.
 *
 * This is the mode switch: drilled, the donut splits by the payments inside
 * one category instead of by the categories themselves, because that is the
 * question the reader is asking once they picked one.
 */
const drilledCategory = computed(() => {
  const key = categoryFilter.value;
  if (!key) return null;
  if (key === UNCATEGORIZED_KEY) {
    return { key: UNCATEGORIZED_KEY, name: UNCATEGORIZED_LABEL, color: palette.value.text };
  }
  const category = props.categories.find((item) => String(item.id) === key);
  return category
    ? { key: category.id, name: category.name, color: colorFor(category.id) }
    : null;
});

const isDrilled = computed(() => drilledCategory.value !== null);

/** What the percentages on screen are a share OF. */
const scopeLabel = computed(() => (isDrilled.value ? 'de la categoría' : 'del total'));

// Both the drilled donut and the Ítems tab rank the same payments over the same
// filtered set, so they share one computation and one denominator.
const items = computed(() => itemsByMonthlyCost(chartRows.value));

/**
 * Item hues: the categorical ramp rotated to start at the drilled category's
 * own slot, so the biggest item inherits the color that category wore in the
 * general view and the drill reads as a zoom into that same slice. Past the
 * ramp's slots items share the neutral ink, exactly as categories do.
 */
const itemRamp = computed(() => {
  const ramp = palette.value.categorical;
  const start = props.categories.findIndex(
    (category) => String(category.id) === categoryFilter.value,
  );
  if (start <= 0 || start >= ramp.length) return ramp;
  return [...ramp.slice(start), ...ramp.slice(0, start)];
});

function itemColor(index) {
  return itemRamp.value[index] || palette.value.text;
}

// -------------------------------------------------------------------
// Filters
// -------------------------------------------------------------------

const categoryOptions = computed(() => {
  const options = [
    { value: '', label: 'Todas' },
    ...props.categories.map((category) => ({
      value: String(category.id),
      label: category.name,
    })),
  ];
  // The legend can drill into the uncategorized bucket, so the select has to be
  // able to express it too — a native select on a value it has no option for
  // renders blank, stranding the operator on a filter they cannot see.
  if (categoryFilter.value === UNCATEGORIZED_KEY || activeRows.value.some(isUncategorized)) {
    options.push({ value: UNCATEGORIZED_KEY, label: UNCATEGORIZED_LABEL });
  }
  return options;
});

function toggleCategory(key) {
  const next = String(key);
  categoryFilter.value = categoryFilter.value === next ? '' : next;
}

function clearDrill() {
  categoryFilter.value = '';
}

function drillToDonutSlice(index) {
  // Drilled, the slices are payments — and payment ids collide with category
  // ids, so without this guard clicking "Claude" (id 1) would toggle whatever
  // category happens to be id 1. Items do not drill; the way back is the
  // header's button.
  if (isDrilled.value) return;
  const bucket = donutSlices.value[index];
  if (!bucket) return;
  // The folded bucket is the one slice that cannot drill: it is several
  // categories at once, not a value the filter can express.
  const drillable =
    bucket.id === UNCATEGORIZED_KEY
    || props.categories.some((category) => category.id === bucket.id);
  if (drillable) toggleCategory(bucket.id);
}

const emptyTitle = computed(() =>
  props.rows.length ? 'Nada que graficar con estos filtros' : 'Sin pagos recurrentes',
);

const emptyDescription = computed(() => {
  if (!props.rows.length) return 'Creá un pago recurrente para ver su distribución.';
  if (!activeRows.value.length) {
    return 'Los pagos que quedan están inactivos. Activá "Incluir inactivos" para verlos.';
  }
  // Drilled into a category that does have payments here: they are all
  // inactive, which is a different problem from an empty category.
  if (isDrilled.value && props.rows.some(matchesCategoryFilter)) {
    return 'Los pagos de esta categoría están inactivos. Activá "Incluir inactivos" para verlos.';
  }
  return 'Esa categoría no tiene pagos en el conjunto filtrado.';
});

// -------------------------------------------------------------------
// Tab: categoría
// -------------------------------------------------------------------

// The general legend is built off the unfiltered-by-category set, so the reader
// sees every category weighed against the same whole.
const categoryBuckets = computed(() => totalsByCategory(activeRows.value, props.categories));

const categoryLegend = computed(() =>
  categoryBuckets.value.map((bucket) => ({
    key: bucket.key,
    label: bucket.name,
    total: bucket.total,
    pct: bucket.pct,
    color: colorFor(bucket.key),
  })),
);

/**
 * The drilled legend lists EVERY payment of the category, unfolded and
 * including the ones worth nothing: it doubles as the table view, so what the
 * chart cannot draw still has to be readable here. Each row carries both
 * shares — its weight inside the category, and, in the muted column, its
 * weight over everything.
 */
const itemLegend = computed(() =>
  items.value.map((item, index) => ({
    key: item.key,
    label: item.name,
    total: item.total,
    pct: item.pct,
    sub: `${formatPercent(shareOfAll(item.total))} del total general`,
    color: itemColor(index),
  })),
);

const legendItems = computed(() => (isDrilled.value ? itemLegend.value : categoryLegend.value));

const donutSlices = computed(() => {
  if (!isDrilled.value) {
    return foldChartBuckets(
      totalsByCategory(chartRows.value, props.categories),
      palette.value.categorical.length,
    ).map((bucket) => ({ ...bucket, color: colorFor(bucket.key) }));
  }

  return foldChartBuckets(
    // A payment worth nothing is an invisible arc that would still claim a
    // palette slot — and a fold position ahead of an item that has weight.
    items.value.filter((item) => item.total > 0),
    palette.value.categorical.length,
    { key: OTHER_ITEMS_KEY, label: OTHER_ITEMS_LABEL },
  // Item hues come from the slice's rank, never from colorFor(): that map is
  // keyed by category id, and payment ids collide with it.
  ).map((slice, index) => ({ ...slice, color: itemColor(index) }));
});

const singleItemNote = computed(() => {
  if (!isDrilled.value || items.value.length !== 1) return '';
  return `${drilledCategory.value.name} tiene un solo ítem, ${items.value[0].name}: `
    + 'la dona marca 100% porque no hay nada más que dividir.';
});

function donutTooltip(value, { seriesIndex } = {}) {
  const slice = donutSlices.value[seriesIndex];
  if (!slice) return formatMonthlyCop(value);
  const shares = isDrilled.value
    ? `${formatPercent(slice.pct)} de la categoría · ${formatPercent(shareOfAll(slice.total))} del total general`
    : `${formatPercent(slice.pct)} del total`;
  return `${formatMonthlyCop(slice.total)}/mes · ${shares}`;
}

// -------------------------------------------------------------------
// Tab: ítems
// -------------------------------------------------------------------

// A fixed height would give a lone item a 100px-thick bar. Growing with the
// count keeps every bar in the same band whether there is one or twenty.
const itemsChartHeight = computed(() => Math.max(120, items.value.length * 44 + 60));

function itemTooltip(value, { dataPointIndex } = {}) {
  const item = items.value[dataPointIndex];
  if (!item) return formatMonthlyCop(value);
  const original = formatMoney(item.price, item.currency, {
    decimals: item.currency === 'COP' ? 0 : 2,
  });
  const periodicity = item.frequencyLabel ? ` ${item.frequencyLabel.toLowerCase()}` : '';
  // `pct` is a share of whatever set is on screen, so the label has to follow
  // the drill — filtered, this is the weight inside the category, not the total.
  return `${formatMonthlyCop(item.total)}/mes · ${original}${periodicity} · ${formatPercent(item.pct)} ${scopeLabel.value}`;
}

// -------------------------------------------------------------------
// Tab: composición
// -------------------------------------------------------------------

const compositionRows = computed(() =>
  COMPOSITION_ROWS.map((row) => {
    const buckets = splitBy(chartRows.value, row.field);
    return {
      ...row,
      buckets,
      legend: buckets.map((bucket, index) => ({
        key: `${row.field}-${bucket.key}`,
        label: bucket.label,
        total: bucket.total,
        pct: bucket.pct,
        color: palette.value.categorical[index] || palette.value.text,
      })),
    };
  }),
);

// One stacked bar per row, two layers deep. The series carry no meaning of
// their own — "first value / second value" — which is why the chart's own
// legend is off and the three legends below name the actual buckets.
const compositionSeries = computed(() => {
  const depth = Math.max(1, ...compositionRows.value.map((row) => row.buckets.length));
  return Array.from({ length: depth }, (_, layer) => ({
    name: `Parte ${layer + 1}`,
    data: compositionRows.value.map((row) => row.buckets[layer]?.total || 0),
  }));
});

function compositionTooltip(value, { seriesIndex, dataPointIndex } = {}) {
  const bucket = compositionRows.value[dataPointIndex]?.buckets[seriesIndex];
  if (!bucket) return formatMonthlyCop(value);
  return `${bucket.label}: ${formatMonthlyCop(bucket.total)}/mes · ${formatPercent(bucket.pct)}`;
}

const usdRows = computed(() => chartRows.value.filter((row) => row.currency === 'USD'));

const compositionStrip = computed(() => {
  const usdMonthlyCop = sumMonthlyCop(usdRows.value);
  const nativeUsd = usdRows.value.reduce(
    (sum, row) => sum + (Number(row.monthly_price) || 0),
    0,
  );
  const stats = [
    { label: 'Total mensual', value: formatMonthlyCop(total.value) },
    {
      label: 'Expuesto al dólar',
      value: formatMonthlyCop(usdMonthlyCop),
      sub: `${formatPercent(percentOfTotal(usdMonthlyCop))} del gasto`,
      tone: 'brand',
    },
    // Monthly, not the sum of raw prices the page's KPI shows: adding a $200
    // monthly subscription to a $10,98 yearly domain is the apples-to-oranges
    // total this whole modal exists to avoid.
    { label: 'Nativos USD / mes', value: formatMoney(nativeUsd, 'USD', { decimals: 2 }) },
  ];
  if (props.usdExchangeRate != null) {
    stats.push({
      label: 'Tasa de referencia',
      value: `${formatMoney(Number(props.usdExchangeRate), 'COP')}/USD`,
    });
  }
  return stats;
});

function percentOfTotal(value) {
  return total.value > 0 ? (value / total.value) * 100 : 0;
}

// -------------------------------------------------------------------
// Tab: calendario
// -------------------------------------------------------------------

const calendar = computed(() => byBillingDay(chartRows.value));

function dayTooltip(value, { dataPointIndex } = {}) {
  const day = calendar.value.days[dataPointIndex];
  if (!day || !day.total) return formatMonthlyCop(value);
  const suffix = day.prorated ? ' · incluye cuotas prorrateadas' : '';
  return `${formatMonthlyCop(day.total)}/mes · ${day.names.join(', ')}${suffix}`;
}

// -------------------------------------------------------------------
// Image export
// -------------------------------------------------------------------

const activeChartId = computed(() =>
  chartRows.value.length ? CHART_IDS[activeTab.value] : '',
);

async function downloadActiveChart() {
  const apex = typeof window !== 'undefined' ? window.ApexCharts : null;
  if (!apex || !activeChartId.value) return;
  // exec() resolves to undefined when no chart is mounted under that id, which
  // is what happens whenever the chart rendered its own empty state.
  const exported = await apex.exec(activeChartId.value, 'dataURI');
  if (!exported?.imgURI) return;
  // Without the category the general donut and every drilled one would all
  // land as recurrentes-category.png and overwrite each other.
  const scope = drilledCategory.value ? `-${toSlug(drilledCategory.value.name)}` : '';
  const link = document.createElement('a');
  link.download = `recurrentes-${activeTab.value}${scope}.png`;
  link.href = exported.imgURI;
  link.click();
}
</script>
