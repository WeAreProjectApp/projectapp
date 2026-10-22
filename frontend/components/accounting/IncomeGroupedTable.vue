<template>
  <!--
    Same ARIA grid of divs as RecurringGroupedTable, kept as a sibling on
    purpose: that component owes its div markup (and its mutable group
    mirror) to vuedraggable, which incomes do not need — grafting income
    subtotals and row actions onto it would couple two tables that only
    share the shell. The subgrid CSS is duplicated with it.
  -->
  <div
    class="overflow-x-auto bg-surface rounded-xl border border-border-muted shadow-sm"
    role="table"
    :aria-busy="loading ? 'true' : undefined"
    :aria-label="ariaLabel"
  >
    <p class="sr-only" aria-live="polite">
      {{ loading ? 'Cargando registros...' : `${rowCount} ${rowNoun} en ${groups.length} ${groupNoun}` }}
    </p>

    <div class="accounting-grid-scroll" :style="{ ...containerVars, ...gridVars }">
      <!-- Header -->
      <div
        role="row"
        class="accounting-grid-row items-end bg-surface-raised text-xs text-text-muted uppercase tracking-wider leading-tight"
      >
        <!-- Must stay in flow to occupy the selection track; without the cell
             every label would shift one track left. The grouped view never
             paginates, so this covers the whole filtered set. -->
        <span v-if="selectable" role="columnheader" :class="SELECT_PAD">
          <input
            type="checkbox"
            class="align-middle accent-primary"
            :aria-label="`Seleccionar ${allSelectionArticle} ${rowNoun} ${filteredAdjective}`"
            data-testid="accounting-select-all"
            :checked="allSummary.all"
            :indeterminate.prop="allSummary.some && !allSummary.all"
            @change="toggleAll($event.target.checked)"
          >
        </span>
        <span
          v-if="hasMenuStart"
          role="columnheader"
          class="w-14 min-w-14 max-w-14 px-1.5 py-2 text-center"
          data-testid="accounting-actions-header"
          aria-label="Acciones"
        />
        <span
          v-for="col in resolved"
          :key="col.key"
          role="columnheader"
          :class="[col.headerPadClass, col.alignClass, responsiveGridCellClass(col)]"
          :aria-sort="ariaSort(col)"
        >
          <button
            v-if="col.sortable"
            type="button"
            class="inline-flex items-center gap-1 uppercase tracking-wider rounded hover:text-text-default transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/50"
            :class="sortKey === col.key ? 'text-text-default' : ''"
            :data-testid="`accounting-sort-${col.key}`"
            @click="emit('sort', col.key)"
          >
            <span>{{ col.label }}</span>
            <BaseActionIcon
              v-if="sortKey === col.key && sortDir === 'asc'"
              action="sort-ascending"
              class="h-3 w-3"
            />
            <BaseActionIcon
              v-else-if="sortKey === col.key && sortDir === 'desc'"
              action="sort-descending"
              class="h-3 w-3"
            />
            <span v-else data-testid="sortable-hint" aria-hidden="true">
              <BaseActionIcon action="sort" class="h-3 w-3 text-text-subtle" />
            </span>
          </button>
          <template v-else>{{ col.label }}</template>
        </span>
        <span v-if="showActions && !hasMenuStart" role="columnheader" :class="[DENSITY.headerCell, 'text-center']">Acciones</span>
      </div>

      <!-- Skeleton -->
      <div v-if="showSkeleton" class="accounting-grid-band divide-y divide-border-muted">
        <div
          v-for="n in skeletonRows"
          :key="`skeleton-${n}`"
          class="px-4 py-1.5 min-h-9 flex items-center bg-surface"
          data-testid="accounting-skeleton-row"
        >
          <div class="h-3 w-32 rounded bg-surface-raised motion-safe:animate-pulse" />
        </div>
      </div>

      <template v-else>
        <div v-for="group in groups" :key="group.id" role="rowgroup" class="accounting-grid-subgrid">
          <!-- Group header -->
          <!--
            This row IS the group's totals row, but its figures are facts about
            the client they follow, so they sit CONTIGUOUS to the name at the
            start of the band. Spreading them over the row's width was tried and
            rejected: on a wide table the amounts landed so far from the name
            that they read as columns of something else again. Below sm they
            drop together to a second line under the name rather than wrapping
            mid amount.
          -->
          <AccountingGroupSummaryBand
            class="accounting-grid-band bg-surface-raised border-y border-border-muted px-4 py-2"
            :data-testid="`${groupTestPrefix}-group-${group.id}`"
            :metrics="metricsForGroup(group)"
            :statuses="statusesFor(group)"
          >
            <div class="flex items-center gap-2 min-w-0">
              <!-- Sibling of the toggle, never inside it: a checkbox nested in
                   a <button> is invalid, and its click would collapse the
                   group instead of selecting it. -->
              <input
                v-if="selectable"
                type="checkbox"
                class="align-middle accent-primary flex-shrink-0"
                :aria-label="`Seleccionar ${selectionArticle} ${group.count} ${rowNoun} de ${group.name}`"
                :data-testid="`${groupTestPrefix}-group-select-${group.id}`"
                :checked="groupSummary(group.id).all"
                :indeterminate.prop="groupSummary(group.id).some && !groupSummary(group.id).all"
                @change="toggleGroupSelection(group, $event.target.checked)"
              >
              <button
                type="button"
                role="columnheader"
                class="inline-flex items-center gap-2 min-w-0 text-sm font-medium text-text-default rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/50"
                :aria-expanded="!isCollapsed(group.id)"
                :aria-controls="`${groupTestPrefix}-group-body-${group.id}`"
                :data-testid="`${groupTestPrefix}-group-toggle-${group.id}`"
                @click="emit('toggle-group', group.id)"
              >
                <BaseActionIcon
                  :action="isCollapsed(group.id) ? 'expand' : 'collapse'"
                  class="text-text-subtle"
                />
                <span class="min-w-0 max-w-full truncate" :title="group.name">{{ group.name }}</span>
                <span
                  v-if="group.id === unassignedKey"
                  class="text-[10px] px-1.5 py-0.5 rounded-full font-semibold uppercase tracking-wider bg-warning-soft text-warning-strong whitespace-nowrap"
                >
                  {{ unassignedBadge }}
                </span>
                <span class="text-xs text-text-subtle font-normal">({{ group.count }})</span>
              </button>
              <!-- A collapsed group still counts towards the bulk action, so
                   it has to say how much of it is selected — otherwise the
                   confirmation lists rows the operator cannot see. -->
              <span
                v-if="selectable && isCollapsed(group.id) && groupSummary(group.id).count > 0"
                class="text-[10px] px-1.5 py-0.5 rounded-full font-semibold uppercase tracking-wider bg-primary-soft text-text-brand whitespace-nowrap"
                :data-testid="`${groupTestPrefix}-group-selected-${group.id}`"
              >
                {{ groupSummary(group.id).count }}
                seleccionado{{ groupSummary(group.id).count === 1 ? '' : 's' }}
              </span>
            </div>
          </AccountingGroupSummaryBand>

          <!-- Rows -->
          <div
            v-show="!isCollapsed(group.id)"
            :id="`${groupTestPrefix}-group-body-${group.id}`"
            :data-testid="`${groupTestPrefix}-group-body-${group.id}`"
            class="accounting-grid-subgrid divide-y divide-border-muted"
          >
            <div
              v-for="row in group.rows"
              :key="row.id"
              role="row"
              :data-testid="`accounting-row-${row.id}`"
              class="accounting-grid-row items-center min-h-9 bg-surface hover:bg-surface-raised transition-colors text-sm"
              :class="row.id === highlightId ? 'accounting-row-flash' : ''"
            >
              <span v-if="selectable" role="cell" :class="SELECT_PAD">
                <input
                  type="checkbox"
                  class="align-middle accent-primary"
                  :aria-label="`Seleccionar fila ${row.id}`"
                  :data-testid="`accounting-select-${row.id}`"
                  :checked="selectedSet.has(row.id)"
                  @change="toggleRow(row.id, $event.target.checked)"
                >
              </span>
              <span
                v-if="hasMenuStart"
                role="cell"
                class="w-14 min-w-14 max-w-14 px-1.5 py-1.5 text-center whitespace-nowrap"
                :data-testid="`accounting-actions-cell-${row.id}`"
                @click.stop
                @auxclick.stop
              >
                <slot name="row-actions" :row="row" />
                <template v-if="showDefaultActions">
                  <BaseActionButton
                    action="edit"
                    variant="ghost"
                    size="sm"
                    label="Editar ingreso"
                    :data-testid="`accounting-edit-${row.id}`"
                    @click.stop="emit('edit', row)"
                  />
                  <BaseActionButton
                    action="delete"
                    variant="danger-ghost"
                    size="sm"
                    label="Eliminar ingreso"
                    :data-testid="`accounting-delete-${row.id}`"
                    @click.stop="emit('delete', row)"
                  />
                </template>
              </span>
              <span
                v-for="col in resolved"
                :key="col.key"
                role="cell"
                class="min-w-0"
                :class="cellClass(col)"
              >
                <!-- Caps the name column's content so one long value cannot
                     widen its track past the rest of the table. -->
                <div :class="col.contentClass">
                  <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
                    <template v-if="col.format === 'money'">
                      {{ formatMoney(row[col.key], 'COP') }}
                    </template>
                    <HighlightText
                      v-else-if="highlightQuery"
                      :text="row[col.key] ?? ''"
                      :query="highlightQuery"
                    />
                    <template v-else>{{ row[col.key] }}</template>
                  </slot>

                  <dl
                    v-if="col.responsive?.primary && groupedColumns.compact.length"
                    class="mt-2 space-y-1 panel-portrait:hidden"
                    data-testid="responsive-group-compact"
                  >
                    <div
                      v-for="detail in groupedColumns.compact"
                      :key="detail.key"
                      class="grid grid-cols-[minmax(5.5rem,auto)_1fr] gap-2 text-left text-xs"
                    >
                      <dt class="font-medium text-text-subtle">{{ detail.label }}</dt>
                      <dd class="min-w-0 text-text-muted">
                        <slot :name="`cell-${detail.key}`" :row="row" :value="row[detail.key]">
                          {{ formatGroupedValue(detail, row[detail.key]) }}
                        </slot>
                      </dd>
                    </div>
                  </dl>

                  <dl
                    v-if="col.responsive?.primary && groupedColumns.portrait.length"
                    class="mt-2 hidden space-y-1 panel-portrait:block panel-landscape:hidden"
                    data-testid="responsive-group-portrait"
                  >
                    <div
                      v-for="detail in groupedColumns.portrait"
                      :key="detail.key"
                      class="grid grid-cols-[minmax(6rem,auto)_1fr] gap-2 text-left text-xs"
                    >
                      <dt class="font-medium text-text-subtle">{{ detail.label }}</dt>
                      <dd class="min-w-0 text-text-muted">
                        <slot :name="`cell-${detail.key}`" :row="row" :value="row[detail.key]">
                          {{ formatGroupedValue(detail, row[detail.key]) }}
                        </slot>
                      </dd>
                    </div>
                  </dl>

                  <dl
                    v-if="col.responsive?.primary && groupedColumns.landscape.length"
                    class="mt-2 hidden space-y-1 panel-landscape:block panel-desktop:hidden"
                    data-testid="responsive-group-landscape"
                  >
                    <div
                      v-for="detail in groupedColumns.landscape"
                      :key="detail.key"
                      class="grid grid-cols-[minmax(6rem,auto)_1fr] gap-2 text-left text-xs"
                    >
                      <dt class="font-medium text-text-subtle">{{ detail.label }}</dt>
                      <dd class="min-w-0 text-text-muted">
                        <slot :name="`cell-${detail.key}`" :row="row" :value="row[detail.key]">
                          {{ formatGroupedValue(detail, row[detail.key]) }}
                        </slot>
                      </dd>
                    </div>
                  </dl>
                </div>
              </span>
              <span v-if="showActions && !hasMenuStart" role="cell" :class="[DENSITY.cell, 'text-center whitespace-nowrap']">
                <slot name="row-actions" :row="row" />
                <template v-if="showDefaultActions">
                  <BaseActionButton
                    action="edit"
                    variant="ghost"
                    size="sm"
                    label="Editar ingreso"
                    :data-testid="`accounting-edit-${row.id}`"
                    @click.stop="emit('edit', row)"
                  />
                  <BaseActionButton
                    action="delete"
                    variant="danger-ghost"
                    size="sm"
                    label="Eliminar ingreso"
                    :data-testid="`accounting-delete-${row.id}`"
                    @click.stop="emit('delete', row)"
                  />
                </template>
              </span>
            </div>
          </div>
        </div>

        <!-- Grand totals: billed vs collected are separate ledger rows, so
             they read side by side instead of summing into one number.

             Shares the group headers' layout, so the whole table reads the same
             way top to bottom: the label first and the figures grouped right
             after it. Pendiente keeps coming before Cobrado because those first
             two are the columns the groups also carry, and Cobrado — which has
             no group-level counterpart — closes the set. -->
        <AccountingGroupSummaryBand
          class="accounting-grid-band bg-surface-raised border-t-2 border-border-muted px-4 py-2"
          :metrics="metricsForFooter"
          :statuses="statusesFor(summaryTotals, true)"
        >
          <span role="cell" class="text-xs uppercase tracking-wider text-text-muted">
            {{ footerLabel }}
          </span>
        </AccountingGroupSummaryBand>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import AccountingGroupSummaryBand from '~/components/accounting/AccountingGroupSummaryBand.vue';
import HighlightText from '~/components/ui/HighlightText.vue';
import { formatMoney } from '~/utils/formatMoney';
import { formatPercent } from '~/utils/percent';
import { sumClientGroups } from '~/utils/incomeClients';
import { selectionSummary, toggleKeys } from '~/utils/rowSelection';
import {
  ROW_ACTION_LAYOUTS,
  SELECT_PAD,
  TABLE_DENSITY,
  minWidthFor,
  resolveColumns,
  trackListFor,
} from '~/utils/tableLayout';

const props = defineProps({
  /** Same column contract as AccountingTable, including the explicit
   * responsive priority for compact, portrait and landscape profiles. */
  columns: { type: Array, required: true },
  columnLayout: {
    type: String,
    default: 'proportional',
    validator: (value) => ['proportional', 'content'].includes(value),
  },
  /** withClientWeights(groupByClient(rows)) — ordered, subtotaled, "Sin cliente" last. */
  groups: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  skeletonRows: { type: Number, default: 5 },
  highlightId: { type: [String, Number], default: null },
  highlightQuery: { type: String, default: '' },
  /** Active sort state, controlled by the page through the `sort` event. */
  sortKey: { type: String, default: '' },
  sortDir: { type: String, default: 'asc' },
  /** Ids of the collapsed groups. */
  collapsedIds: { type: Array, default: () => [] },
  /** Mirrors AccountingTable: false lets the page own every row action. */
  showActions: { type: Boolean, default: true },
  showDefaultActions: { type: Boolean, default: true },
  rowActionsLayout: {
    type: String,
    default: ROW_ACTION_LAYOUTS.INLINE_END,
    validator: (value) => Object.values(ROW_ACTION_LAYOUTS).includes(value),
  },
  /** Opt-in checkbox column, same contract as AccountingTable. */
  selectable: { type: Boolean, default: false },
  /** Selected row ids (v-model:selected). */
  selected: { type: Array, default: () => [] },
  ariaLabel: { type: String, default: 'Ingresos por cliente' },
  rowNoun: { type: String, default: 'ingresos' },
  allSelectionArticle: { type: String, default: 'todos los' },
  selectionArticle: { type: String, default: 'los' },
  filteredAdjective: { type: String, default: 'filtrados' },
  groupNoun: { type: String, default: 'clientes' },
  groupTestPrefix: { type: String, default: 'income' },
  unassignedKey: { type: [String, Number], default: 'none' },
  unassignedBadge: { type: String, default: 'por completar' },
  groupMetrics: {
    type: Array,
    default: () => [
      { key: 'billed', label: 'Facturado', format: 'money', tone: 'muted' },
      { key: 'pending', label: 'Pendiente', format: 'money', tone: 'warning' },
      {
        key: 'weight',
        source: 'weightPct',
        label: 'Participación en lo facturado',
        format: 'percent',
        tone: 'muted',
      },
    ],
  },
  footerMetrics: {
    type: Array,
    default: () => [
      { key: 'billed', label: 'Facturado', format: 'money', tone: 'default' },
      { key: 'pending', label: 'Pendiente', format: 'money', tone: 'warning' },
      { key: 'collected', label: 'Cobrado', format: 'money', tone: 'success' },
    ],
  },
  statusDefinitions: { type: Array, default: () => [] },
  summaryTotals: { type: Object, default: null },
  footerLabel: { type: String, default: 'Total del conjunto filtrado' },
});

const emit = defineEmits(['edit', 'delete', 'sort', 'toggle-group', 'update:selected']);

const DENSITY = TABLE_DENSITY;
const hasMenuStart = computed(() => (
  props.showActions && props.rowActionsLayout === ROW_ACTION_LAYOUTS.MENU_START
));

/** Widths by content, slack shared in proportion — see utils/tableLayout. */
const resolved = computed(() => resolveColumns(props.columns, {
  hasActions: props.showActions,
  rowActionsLayout: props.rowActionsLayout,
  columnLayout: props.columnLayout,
}));

function ariaSort(column) {
  if (!column.sortable) return undefined;
  if (props.sortKey !== column.key) return 'none';
  return props.sortDir === 'desc' ? 'descending' : 'ascending';
}

const PROFILE_ORDER = ['compact', 'portrait', 'landscape'];
const POLICY_CLASSES = {
  compact: { keep: 'block', group: 'hidden', hide: 'hidden' },
  portrait: { keep: 'panel-portrait:block', group: 'panel-portrait:hidden', hide: 'panel-portrait:hidden' },
  landscape: { keep: 'panel-landscape:block', group: 'panel-landscape:hidden', hide: 'panel-landscape:hidden' },
};

function policyFor(column, profile) {
  if (!column.responsive) return 'keep';
  if (column.responsive[profile]) return column.responsive[profile];
  if (profile === 'portrait') return column.responsive.compact || 'keep';
  return 'keep';
}

function responsiveGridCellClass(column) {
  return [
    ...PROFILE_ORDER.map((profile) => POLICY_CLASSES[profile][policyFor(column, profile)]),
    'panel-desktop:block',
  ];
}

const groupedColumns = computed(() => Object.fromEntries(
  PROFILE_ORDER.map((profile) => [
    profile,
    resolved.value.filter((column) => policyFor(column, profile) === 'group'),
  ]),
));

function visibleColumns(profile) {
  return resolved.value
    .filter((column) => policyFor(column, profile) === 'keep')
    .map((column) => (
      column.responsive?.primary
        ? { ...column, track: 'minmax(0, 1fr)' }
        : column
    ));
}

/**
 * Header and rows must line up, so every row shares one track list. CSS
 * cannot drop a track from grid-template-columns, so each breakpoint gets
 * its own list as a custom property and a media query picks between them.
 */
const gridVars = computed(() => {
  const opts = {
    hasSelect: props.selectable,
    hasActions: props.showActions,
    rowActionsLayout: props.rowActionsLayout,
    breakpoint: 'lg',
  };
  return {
    '--cols-compact': trackListFor(visibleColumns('compact'), opts),
    '--cols-portrait': trackListFor(visibleColumns('portrait'), opts),
    '--cols-landscape': trackListFor(visibleColumns('landscape'), opts),
    '--cols-desktop': trackListFor(resolved.value, opts),
  };
});

const containerVars = computed(() => {
  const opts = {
    hasSelect: props.selectable,
    hasActions: props.showActions,
    rowActionsLayout: props.rowActionsLayout,
    breakpoint: 'lg',
  };
  return {
    '--minw-landscape': minWidthFor(visibleColumns('landscape'), opts),
    '--minw-desktop': minWidthFor(resolved.value, opts),
  };
});

const rowCount = computed(
  () => props.groups.reduce((total, group) => total + group.rows.length, 0),
);

/**
 * Skeleton only when there is nothing to show yet. Every mutation refetches,
 * so binding it to `loading` alone blanked the whole grid — groups, counters
 * and the totals row — and brought it back after a delete. `aria-busy` still
 * announces the fetch.
 */
const showSkeleton = computed(() => props.loading && props.groups.length === 0);

const summaryTotals = computed(() => props.summaryTotals || sumClientGroups(props.groups));

function formatMetricValue(definition, source) {
  const value = source?.[definition.source || definition.key];
  if (definition.format === 'money') return money(value);
  if (definition.format === 'percent') return formatPercent(value);
  return value ?? '—';
}

function metricTestId(definition, groupId = null) {
  if (groupId == null) return `${props.groupTestPrefix}-grouped-${definition.key}-total`;
  return `${props.groupTestPrefix}-group-${definition.key}-${groupId}`;
}

function metricItems(definitions, source, groupId = null) {
  return definitions
    .filter((definition) => !definition.optional || source?.[definition.source || definition.key] != null)
    .map((definition) => ({
      ...definition,
      value: formatMetricValue(definition, source),
      testId: metricTestId(definition, groupId),
    }));
}

function metricsForGroup(group) {
  return metricItems(props.groupMetrics, group, group.id);
}

const metricsForFooter = computed(
  () => metricItems(props.footerMetrics, summaryTotals.value),
);

function statusesFor(source, isFooter = false) {
  return props.statusDefinitions.map((definition) => ({
    ...definition,
    value: source?.statusCounts?.[definition.key] || 0,
    testId: isFooter
      ? `${props.groupTestPrefix}-grouped-status-${definition.key}-total`
      : `${props.groupTestPrefix}-group-status-${definition.key}-${source?.id}`,
  }));
}

function money(value) {
  return formatMoney(Number(value) || 0, 'COP');
}

function isCollapsed(id) {
  return props.collapsedIds.includes(id);
}

// ── Row selection (opt-in via `selectable`) ──
//
// The scope of a group checkbox is its own rows and the scope of the header
// one is every group — collapsed included, because a collapsed group keeps
// counting towards the bulk action. `groups` is built from the FILTERED rows
// and this view never paginates, so "all" here means the filtered set.

const selectedSet = computed(() => new Set(props.selected));

const groupSummaries = computed(() => new Map(
  props.groups.map((group) => [
    group.id,
    selectionSummary(group.rows.map((row) => row.id), selectedSet.value),
  ]),
));

const EMPTY_SUMMARY = { count: 0, all: false, some: false };

function groupSummary(id) {
  return groupSummaries.value.get(id) || EMPTY_SUMMARY;
}

const allKeys = computed(
  () => props.groups.flatMap((group) => group.rows.map((row) => row.id)),
);

const allSummary = computed(() => selectionSummary(allKeys.value, selectedSet.value));

function toggleRow(id, checked) {
  emit('update:selected', toggleKeys(props.selected, [id], checked));
}

function toggleGroupSelection(group, checked) {
  const keys = group.rows.map((row) => row.id);
  emit('update:selected', toggleKeys(props.selected, keys, checked));
}

function toggleAll(checked) {
  emit('update:selected', toggleKeys(props.selected, allKeys.value, checked));
}

/** `col` is already resolved, so alignment, padding and visibility come precomputed. */
function cellClass(col) {
  const classes = [col.padClass, col.alignClass, responsiveGridCellClass(col)];
  // Amounts must never wrap or clip; free text may truncate.
  if (col.format === 'money' || col.align === 'right') {
    classes.push('tabular-nums whitespace-nowrap');
    classes.push(col.format === 'money' ? 'text-text-muted' : 'text-text-default');
  } else {
    classes.push('truncate text-text-default');
  }
  return classes;
}

function formatGroupedValue(col, value) {
  if (col.format === 'money') return formatMoney(value, 'COP');
  if (col.format === 'percent') return formatPercent(value);
  return value ?? '—';
}
</script>

<style scoped>
/* ONE grid for the whole table: the container owns the tracks and every band,
 * group and row is a subgrid of it, so a column is measured once across all
 * the rows — header included — and an outlier only fills its own cell.
 *
 * The variants come in as custom properties because a media query can switch
 * between values but cannot compute a track list from the column config;
 * --cols is the indirection that keeps that switch in one place. */
.accounting-grid-scroll {
  --cols: var(--cols-compact);
  min-width: 100%;
}
@media (min-width: 640px) {
  .accounting-grid-scroll {
    --cols: var(--cols-portrait);
    min-width: 100%;
  }
}
@media (min-width: 1024px) {
  .accounting-grid-scroll {
    --cols: var(--cols-landscape);
    min-width: var(--minw-landscape);
  }
}
@media (min-width: 1280px) {
  .accounting-grid-scroll {
    --cols: var(--cols-desktop);
    min-width: var(--minw-desktop);
  }
}

/* The width ceiling lives on the page root (PAGE_MAX_WIDTH), so the grid fills
 * its card and the fr tracks share the slack; min-width still makes a narrow
 * screen scroll instead of squeezing a column past its content. */
.accounting-grid-scroll {
  display: grid;
  grid-template-columns: var(--cols);
}

/* Rowgroups are transparent for track sizing: without them in the chain the
 * rows stop seeing the container's columns. Rows keep their box (unlike
 * display:contents) because the hover, flash and divider need something to
 * paint on. */
.accounting-grid-subgrid,
.accounting-grid-row {
  display: grid;
  grid-column: 1 / -1;
  /* Fallback first: where subgrid is missing the declaration is dropped and
   * the inherited track list stands — a degraded alignment beats every cell
   * collapsing into a single column. */
  grid-template-columns: var(--cols);
  grid-template-columns: subgrid;
}

/* Bands are not column-structured: they span the grid instead of pushing any
 * single column (client header, totals, loading skeleton). */
.accounting-grid-band {
  grid-column: 1 / -1;
}

/* Same feedback flash as AccountingTable for the row just created or edited. */
@keyframes accounting-row-flash {
  0%,
  55% {
    background-color: var(--color-primary-soft);
  }
  100% {
    background-color: transparent;
  }
}
.accounting-row-flash {
  animation: accounting-row-flash 2.5s ease-out;
}
@media (prefers-reduced-motion: reduce) {
  .accounting-row-flash {
    animation: none;
    background-color: var(--color-primary-soft);
  }
}
</style>
