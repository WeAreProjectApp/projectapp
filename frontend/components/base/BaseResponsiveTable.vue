<template>
  <div
    ref="tableContainerRef"
    class="overflow-x-auto bg-surface rounded-xl border border-border-muted shadow-sm"
    :aria-busy="loading ? 'true' : undefined"
  >
    <p class="sr-only" aria-live="polite">
      {{ loading ? 'Cargando registros...' : `${rows.length} registros en la tabla` }}
    </p>
    <!-- Priority-aware tables collapse declared columns on narrow screens.
         Legacy tables without a responsive declaration keep horizontal scroll
         until their module adopts the explicit contract. -->
    <table
      class="w-full text-sm"
      :class="[
        hasResponsivePolicy ? 'base-responsive-table--priority' : '',
        hasColumnResize ? 'base-responsive-table--resizable' : '',
        hasFluidMenuStart ? 'base-responsive-table--fluid-menu' : '',
      ]"
      :style="tableStyle"
    >
      <caption v-if="caption" class="sr-only">{{ caption }}</caption>
      <!-- Data <col>s only where the headers keep their declared width: a <col>
           is a column even when every cell under it is hidden, so a fluid
           menu-start table would hand those tracks the width of the columns a
           narrow profile drops. -->
      <colgroup v-if="hasMenuStart">
        <col v-if="selectable" :style="{ width: SELECT_TRACK }">
        <col :style="{ width: ROW_ACTION_MENU_TRACK }">
        <template v-if="!hasFluidMenuStart">
          <col v-for="col in resolved" :key="col.key">
        </template>
      </colgroup>
      <thead>
        <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
          <th v-if="selectable" class="w-10 px-3 py-2">
            <input
              type="checkbox"
              class="align-middle accent-primary"
              aria-label="Seleccionar todas las filas de esta página"
              :data-testid="`${testIdPrefix}-select-page`"
              :checked="allPageSelected"
              :indeterminate.prop="somePageSelected && !allPageSelected"
              @change="togglePage($event.target.checked)"
            >
          </th>
          <th
            v-if="hasMenuStart"
            :style="actionsHeaderStyle"
            :class="actionsHeaderClass"
            :data-testid="`${testIdPrefix}-actions-header`"
            aria-label="Acciones"
          />
          <th
            v-for="col in resolved"
            :key="col.key"
            :style="columnHeaderStyle(col)"
            :class="[
              col.headerPadClass, col.alignClass, col.nowrapClass,
              responsiveCellClass(col), col.columnWidth?.resizable ? 'relative' : '',
              hasFluidMenuStart ? 'base-responsive-table__fluid-th' : '',
            ]"
            :aria-sort="ariaSort(col)"
          >
            <button
              v-if="col.sortable"
              type="button"
              class="inline-flex items-center gap-1 uppercase tracking-wider rounded hover:text-text-default transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/50"
              :class="sortKey === col.key ? 'text-text-default' : ''"
              :data-testid="`${testIdPrefix}-sort-${col.key}`"
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
            <BaseResizeHandle
              v-if="hasColumnResize && col.columnWidth?.resizable"
              :value="resize.preferredWidth(col.key)"
              :min="col.columnWidth.min"
              :max="col.columnWidth.max"
              :label="`Ajustar el ancho de la columna ${col.label}`"
              :test-id="`${testIdPrefix}-resize-${col.key}`"
              class="absolute -right-2 top-0 z-20 h-full w-4"
              indicator-class="h-7 w-0.5"
              @pointer-start="resize.onPointerStart(col.key, $event)"
              @pointer-move="resize.onPointerMove(col.key, $event)"
              @pointer-end="resize.onPointerEnd(col.key)"
              @resize="resize.resizeTo(col.key, $event)"
              @reset="resize.reset(col.key)"
            />
          </th>
          <th
            v-if="showActions && !hasMenuStart"
            :style="actionsHeaderStyle"
            :class="[DENSITY.headerCell, 'text-center']"
          >Acciones</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border-muted">
        <template v-if="showSkeleton">
          <tr
            v-for="n in skeletonRows"
            :key="`skeleton-${n}`"
            class="bg-surface"
            :data-testid="`${testIdPrefix}-skeleton-row`"
          >
            <td v-if="selectable" :class="DENSITY.cell" />
            <td v-if="hasMenuStart" :style="actionsHeaderStyle" :class="actionsCellClass" />
            <td
              v-for="(col, colIndex) in resolved"
              :key="col.key"
              :class="[col.padClass, col.alignClass, responsiveCellClass(col)]"
            >
              <div
                class="h-3 rounded bg-surface-raised motion-safe:animate-pulse inline-block"
                :class="skeletonWidthClass(n, colIndex)"
              />
            </td>
            <td v-if="showActions && !hasMenuStart" :class="DENSITY.cell" />
          </tr>
        </template>
        <tr v-else-if="rows.length === 0">
          <td :colspan="colspan" class="px-5 py-8 text-center text-sm text-text-subtle">
            <slot name="empty">Sin registros.</slot>
          </td>
        </tr>
        <tr
          v-for="row in showSkeleton ? [] : rows"
          :key="row[rowKey]"
          :data-testid="`${testIdPrefix}-row-${row[rowKey]}`"
          class="hover:bg-surface-raised transition-colors h-9"
          :class="[
            rowBgClass(row),
            rowClassValue(row),
            interactiveRows ? 'cursor-pointer' : '',
            row[rowKey] === highlightId ? 'accounting-row-flash' : '',
          ]"
          @click="interactiveRows && emit('row-click', row, $event)"
          @auxclick.middle="interactiveRows && emit('row-auxclick', row, $event)"
        >
          <td v-if="selectable" class="w-10 px-3" @click.stop @auxclick.stop>
            <input
              type="checkbox"
              class="align-middle accent-primary"
              :aria-label="rowSelectionLabel(row)"
              :data-testid="`${testIdPrefix}-select-${row[rowKey]}`"
              :checked="selectedSet.has(row[rowKey])"
              @change="toggleRow(row[rowKey], $event.target.checked)"
            >
          </td>
          <td
            v-if="hasMenuStart"
            :style="actionsHeaderStyle"
            :class="actionsCellClass"
            :data-testid="`${testIdPrefix}-actions-cell-${row[rowKey]}`"
            @click.stop
            @auxclick.stop
          >
            <slot name="row-actions" :row="row" />
            <BaseActionButton
              v-if="showDefaultActions"
              action="edit"
              label="Editar"
              :data-testid="`${testIdPrefix}-edit-${row[rowKey]}`"
              class="p-1.5 rounded-lg text-text-subtle hover:text-text-brand hover:bg-primary-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/50"
              @click.stop="emit('edit', row)"
            />
            <BaseActionButton
              v-if="showDefaultActions"
              action="delete"
              label="Eliminar"
              variant="danger-ghost"
              size="sm"
              :data-testid="`${testIdPrefix}-delete-${row[rowKey]}`"
              @click.stop="emit('delete', row)"
            />
          </td>
          <td
            v-for="col in resolved"
            :key="col.key"
            :class="cellClass(col)"
          >
            <!-- The wrapper is what caps the name column: a <td>'s own
                 max-width is ignored under auto layout. -->
            <div :class="col.contentClass" :data-text-policy="col.textPolicy">
              <slot
                :name="`cell-${col.key}`"
                :row="row"
                :value="row[col.key]"
                :responsive-profile="null"
              >
                <template v-if="col.format === 'money'">
                  {{ formatMoney(row[col.key], 'COP') }}
                </template>
                <template v-else-if="col.format === 'percent'">
                  {{ formatPercent(row[col.key]) }}
                </template>
                <template v-else-if="col.format === 'date'">
                  {{ formatDate(row[col.key]) }}
                </template>
                <span
                  v-else-if="col.format === 'badge'"
                  class="text-xs px-2.5 py-1 rounded-full font-medium"
                  :class="badgeClass(col, row[col.key])"
                >
                  {{ row[col.key] }}
                </span>
                <HighlightText
                  v-else-if="highlightQuery"
                  :text="row[col.key] ?? ''"
                  :query="highlightQuery"
                />
                <template v-else>
                  {{ row[col.key] }}
                </template>
              </slot>

              <!-- The label floor is the primary column's min-content on a phone:
                   at 5.5rem it alone pushed a three-value row past 412px. Longer
                   labels still grow the track through `auto`. -->
              <dl
                v-if="col.responsive?.primary && groupedColumns.compact.length"
                class="mt-2 space-y-1 panel-portrait:hidden"
                data-testid="responsive-group-compact"
              >
                <div
                  v-for="detail in groupedColumns.compact"
                  :key="detail.key"
                  class="grid grid-cols-[minmax(4.5rem,auto)_1fr] gap-2 text-left text-xs"
                >
                  <dt class="font-medium text-text-subtle">{{ detail.label }}</dt>
                  <dd
                    class="min-w-0 text-text-muted"
                    :class="[detail.contentClass, detail.link ? 'relative' : '']"
                    :data-text-policy="detail.textPolicy"
                  >
                    <slot
                      :name="`cell-${detail.key}`"
                      :row="row"
                      :value="row[detail.key]"
                      responsive-profile="compact"
                    >
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
                  <dd
                    class="min-w-0 text-text-muted"
                    :class="[detail.contentClass, detail.link ? 'relative' : '']"
                    :data-text-policy="detail.textPolicy"
                  >
                    <slot
                      :name="`cell-${detail.key}`"
                      :row="row"
                      :value="row[detail.key]"
                      responsive-profile="portrait"
                    >
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
                  <dd
                    class="min-w-0 text-text-muted"
                    :class="[detail.contentClass, detail.link ? 'relative' : '']"
                    :data-text-policy="detail.textPolicy"
                  >
                    <slot
                      :name="`cell-${detail.key}`"
                      :row="row"
                      :value="row[detail.key]"
                      responsive-profile="landscape"
                    >
                      {{ formatGroupedValue(detail, row[detail.key]) }}
                    </slot>
                  </dd>
                </div>
              </dl>
            </div>
          </td>
          <td
            v-if="showActions && !hasMenuStart"
            :class="[DENSITY.cell, 'text-center whitespace-nowrap']"
            @click.stop
            @auxclick.stop
          >
            <slot name="row-actions" :row="row" />
            <BaseActionButton
              v-if="showDefaultActions"
              action="edit"
              label="Editar"
              :data-testid="`${testIdPrefix}-edit-${row[rowKey]}`"
              class="p-1.5 rounded-lg text-text-subtle hover:text-text-brand hover:bg-primary-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/50"
              @click.stop="emit('edit', row)"
            />
            <BaseActionButton
              v-if="showDefaultActions"
              action="delete"
              label="Eliminar"
              variant="danger-ghost"
              size="sm"
              :data-testid="`${testIdPrefix}-delete-${row[rowKey]}`"
              @click.stop="emit('delete', row)"
            />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { computed, ref, watchEffect } from 'vue';
import HighlightText from '~/components/ui/HighlightText.vue';
import BaseResizeHandle from '~/components/base/BaseResizeHandle.vue';
import { usePanelViewportProfile } from '~/composables/usePanelViewportProfile';
import { useResizableTableColumns } from '~/composables/useResizableTableColumns';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';
import { formatPercent } from '~/utils/percent';
import { selectionSummary, toggleKeys } from '~/utils/rowSelection';
import {
  ROW_ACTION_LAYOUTS,
  ROW_ACTION_MENU_TRACK,
  SELECT_TRACK,
  TABLE_DENSITY,
  actionsWidthFor,
  minWidthFor,
  profileWidthVars,
  resolveColumns,
  responsivePolicyFor,
} from '~/utils/tableLayout';

const props = defineProps({
  /**
   * Column config: { key, label, format ('money'|'percent'|'date'|'text'|'badge'),
   * align ('left'|'right'|'center'), badgeTones ({ value: tone }),
   * textPolicy ('wrap'|'truncate'|'atomic'),
   * sortable (Boolean), size (see utils/tableLayout SIZE_NAMES),
   * group (String — adjacent columns sharing one draw closer together),
   * hideBelow ('md'|'lg' — legacy collapse rule), responsive: {
   * primary?: Boolean, compact: 'keep'|'group'|'hide',
   * portrait: 'keep'|'group'|'hide', landscape?: 'keep'|'group'|'hide' } }.
   */
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  rowKey: { type: String, default: 'id' },
  caption: { type: String, default: '' },
  testIdPrefix: { type: String, default: 'accounting' },
  showActions: { type: Boolean, default: true },
  showDefaultActions: { type: Boolean, default: true },
  /**
   * `menu-start` is the compact kebab contract: selection, actions, data.
   * `inline-end` preserves the wider legacy column used by loose icon rows.
   */
  rowActionsLayout: {
    type: String,
    default: ROW_ACTION_LAYOUTS.INLINE_END,
    validator: (value) => Object.values(ROW_ACTION_LAYOUTS).includes(value),
  },
  /** Search text to highlight inside default text cells. */
  highlightQuery: { type: String, default: '' },
  /** Active sort state (controlled by the page via @sort). */
  sortKey: { type: String, default: '' },
  sortDir: { type: String, default: 'asc' },
  /** When true, renders skeleton placeholder rows instead of data. */
  loading: { type: Boolean, default: false },
  skeletonRows: { type: Number, default: 5 },
  /** Row key of the last created/edited record: flashes that row. */
  highlightId: { type: [String, Number], default: null },
  /**
   * Optional (row) => 'success'|'warning'|null, tinting the row background.
   * The tone REPLACES `bg-surface` rather than stacking on it: two
   * background utilities of equal specificity would be decided by
   * stylesheet order, not by this binding.
   */
  rowTone: { type: Function, default: null },
  /** Extra row classes, either static or resolved from the current row. */
  rowClass: { type: [String, Array, Object, Function], default: '' },
  /** Emit pointer gestures from non-interactive row cells as a convenience. */
  interactiveRows: { type: Boolean, default: false },
  /** Opt-in checkbox column; every other tab keeps its current layout. */
  selectable: { type: Boolean, default: false },
  /** Accessible label for each row checkbox. */
  selectionLabel: { type: Function, default: null },
  /** Selected row keys (v-model:selected). */
  selected: { type: Array, default: () => [] },
  /** localStorage namespace for opt-in resizable column preferences. */
  columnWidthsKey: { type: String, default: '' },
});

const DENSITY = TABLE_DENSITY;

/**
 * Widths come from what each column shows, and the slack is shared out in
 * proportion to that — no single column absorbs it, which is what used to open
 * one wide gap next to the name.
 */
const hasMenuStart = computed(() => (
  props.showActions && props.rowActionsLayout === ROW_ACTION_LAYOUTS.MENU_START
));

const resolved = computed(() => resolveColumns(props.columns, {
  hasActions: props.showActions,
  rowActionsLayout: props.rowActionsLayout,
}));

const tableContainerRef = ref(null);
const { profile: viewportProfile } = usePanelViewportProfile();

const hasColumnResize = computed(() =>
  props.columns.some((column) => Boolean(column.columnWidth?.resizable)),
);

const resizeColumns = computed(() => {
  const dataColumns = resolved.value.map((column) => ({
    ...column,
    columnWidth: column.columnWidth || {
      min: column.minRem * 16,
      default: column.minRem * 16,
      max: column.minRem * 16,
      fixed: true,
    },
  }));
  const leadingControls = [];
  if (props.selectable) {
    leadingControls.push({
      key: '__select',
      columnWidth: { min: 40, default: 40, max: 40, fixed: true },
    });
  }
  if (hasMenuStart.value) {
    leadingControls.push({
      key: '__actions',
      columnWidth: { min: 56, default: 56, max: 56, fixed: true },
    });
  }
  const trailingControls = [];
  if (props.showActions && !hasMenuStart.value) {
    trailingControls.push({
      key: '__actions',
      columnWidth: { min: 80, default: 80, max: 80, fixed: true },
    });
  }
  return [...leadingControls, ...dataColumns, ...trailingControls];
});

const resizeVisibleKeys = computed(() => {
  const dataKeys = resolved.value
    .filter((column) => ['desktop', 'wide'].includes(viewportProfile.value)
      || policyFor(column, viewportProfile.value) === 'keep')
    .map((column) => column.key);
  const leadingKeys = [];
  if (props.selectable) leadingKeys.push('__select');
  if (hasMenuStart.value) leadingKeys.push('__actions');
  const trailingKeys = props.showActions && !hasMenuStart.value ? ['__actions'] : [];
  return [...leadingKeys, ...dataKeys, ...trailingKeys];
});

const resize = useResizableTableColumns({
  columns: resizeColumns,
  containerRef: tableContainerRef,
  storageKey: props.columnWidthsKey,
  visibleKeys: resizeVisibleKeys,
});

// Same scale as the data columns, so the actions column is one more share of
// the total instead of a hardcoded width that disagreed with minWidthFor().
const actionsWidth = computed(() => actionsWidthFor(resolved.value));

const tableMinWidth = computed(
  () => minWidthFor(resolved.value, {
    hasActions: props.showActions,
    rowActionsLayout: props.rowActionsLayout,
  }),
);

const hasResponsivePolicy = computed(() =>
  props.columns.some((column) => Boolean(column.responsive)),
);

/**
 * A menu-start table with a responsive policy switches layout per profile (see
 * FIXED_LAYOUT_PROFILES): auto with content-sized data columns below landscape,
 * fixed with re-shared percentages from landscape up. Either way no hidden
 * column keeps a share. Resizable tables already own their widths.
 */
const hasFluidMenuStart = computed(() => (
  hasMenuStart.value && hasResponsivePolicy.value && !hasColumnResize.value
));

const headerWidthVars = computed(() => (
  hasFluidMenuStart.value ? profileWidthVars(resolved.value) : {}
));

// Landscape still hides columns, so its scroll floor counts only the ones it keeps.
const tableMinWidthLandscape = computed(() => (
  hasFluidMenuStart.value
    ? minWidthFor(
      resolved.value.filter((column) => responsivePolicyFor(column, 'landscape') === 'keep'),
      { hasActions: props.showActions, rowActionsLayout: props.rowActionsLayout },
    )
    : null
));

const tableStyle = computed(() => {
  if (hasColumnResize.value) return resize.tableStyle.value;
  const widthStyle = hasResponsivePolicy.value
    ? {
      '--table-min-width': tableMinWidth.value,
      ...(tableMinWidthLandscape.value
        ? { '--table-min-width-landscape': tableMinWidthLandscape.value }
        : {}),
    }
    : { minWidth: tableMinWidth.value };
  // A fluid menu-start table sets its layout from CSS: an inline value would
  // beat the media query that keeps small screens on auto layout.
  return hasMenuStart.value && !hasFluidMenuStart.value
    ? { ...widthStyle, tableLayout: 'fixed' }
    : widthStyle;
});

function columnHeaderStyle(column) {
  if (hasColumnResize.value) return resize.columnStyle(column.key);
  // Custom properties only: an inline width would beat the profile media queries.
  if (hasFluidMenuStart.value) return headerWidthVars.value[column.key];
  return { width: column.width };
}

const actionsHeaderStyle = computed(() => (
  hasColumnResize.value
    ? resize.columnStyle('__actions')
    : hasMenuStart.value
      ? {
        width: ROW_ACTION_MENU_TRACK,
        minWidth: ROW_ACTION_MENU_TRACK,
        maxWidth: ROW_ACTION_MENU_TRACK,
      }
      : { width: actionsWidth.value }
));

const actionsHeaderClass = computed(() => [
  'w-14 min-w-14 max-w-14 px-1.5 py-2 text-center',
]);

const actionsCellClass = computed(() => [
  'w-14 min-w-14 max-w-14 px-1.5 py-1.5 text-center whitespace-nowrap',
]);

const PROFILE_ORDER = ['compact', 'portrait', 'landscape'];
const POLICY_CLASSES = {
  compact: {
    keep: 'table-cell',
    group: 'hidden',
    hide: 'hidden',
  },
  portrait: {
    keep: 'panel-portrait:table-cell',
    group: 'panel-portrait:hidden',
    hide: 'panel-portrait:hidden',
  },
  landscape: {
    keep: 'panel-landscape:table-cell',
    group: 'panel-landscape:hidden',
    hide: 'panel-landscape:hidden',
  },
};

function policyFor(column, profile) {
  return responsivePolicyFor(column, profile);
}

function responsiveCellClass(column) {
  if (!hasResponsivePolicy.value) return column.hideTableClass;
  return [
    ...PROFILE_ORDER.map((profile) => POLICY_CLASSES[profile][policyFor(column, profile)]),
    'panel-desktop:table-cell',
  ];
}

const groupedColumns = computed(() => Object.fromEntries(
  PROFILE_ORDER.map((profile) => [
    profile,
    resolved.value.filter((column) => policyFor(column, profile) === 'group'),
  ]),
));

if (process.env.NODE_ENV !== 'production') {
  watchEffect(() => {
    if (hasColumnResize.value) {
      const missingWidths = props.columns
        .filter((column) => !column.columnWidth)
        .map((column) => column.key);
      if (missingWidths.length) {
        console.warn(`[BaseResponsiveTable] Resizable tables need a columnWidth policy for every column. Missing: ${missingWidths.join(', ')}`);
      }
      if (!props.columnWidthsKey) {
        console.warn('[BaseResponsiveTable] Resizable tables need columnWidthsKey for persistence.');
      }
    }
    if (!hasResponsivePolicy.value) return;
    const missing = props.columns.filter((column) => !column.responsive).map((column) => column.key);
    const primaries = props.columns.filter((column) => column.responsive?.primary);
    if (missing.length) {
      console.warn(`[BaseResponsiveTable] Every column needs a responsive policy. Missing: ${missing.join(', ')}`);
    }
    if (primaries.length !== 1) {
      console.warn('[BaseResponsiveTable] Declare exactly one responsive.primary column.');
    } else if (policyFor(primaries[0], 'compact') !== 'keep' || policyFor(primaries[0], 'portrait') !== 'keep') {
      console.warn('[BaseResponsiveTable] The primary column must stay visible in compact and portrait profiles.');
    }
  });
}

/**
 * Skeleton only when there is nothing to show yet.
 *
 * Every accounting mutation refetches, so binding the placeholders to
 * `loading` alone made the whole table blank and come back after a delete or
 * an edit — a refresh that read as a reload. With rows already on screen the
 * update now happens in place; `aria-busy` still announces the fetch.
 */
const showSkeleton = computed(() => props.loading && props.rows.length === 0);

const ROW_TONE_CLASSES = {
  success: 'bg-success-soft',
  warning: 'bg-warning-soft',
};

function rowBgClass(row) {
  if (selectedSet.value.has(row[props.rowKey])) return 'bg-primary-soft';
  return ROW_TONE_CLASSES[props.rowTone?.(row)] || 'bg-surface';
}

function rowClassValue(row) {
  return typeof props.rowClass === 'function' ? props.rowClass(row) : props.rowClass;
}

const emit = defineEmits([
  'edit',
  'delete',
  'sort',
  'update:selected',
  'row-click',
  'row-auxclick',
]);

// ── Row selection (opt-in via `selectable`) ──

const selectedSet = computed(() => new Set(props.selected));

const pageKeys = computed(() => props.rows.map((row) => row[props.rowKey]));

const pageSummary = computed(() => selectionSummary(pageKeys.value, selectedSet.value));

const allPageSelected = computed(() => pageSummary.value.all);

const somePageSelected = computed(() => pageSummary.value.some);

function toggleRow(key, checked) {
  emit('update:selected', toggleKeys(props.selected, [key], checked));
}

function rowSelectionLabel(row) {
  return props.selectionLabel?.(row) || `Seleccionar fila ${row[props.rowKey]}`;
}

/** The header checkbox works on the CURRENT page; the page owns any
 *  "select every filtered row" affordance, which knows the full set. */
function togglePage(checked) {
  emit('update:selected', toggleKeys(props.selected, pageKeys.value, checked));
}

function ariaSort(col) {
  if (!col.sortable) return undefined;
  if (props.sortKey !== col.key) return 'none';
  return props.sortDir === 'desc' ? 'descending' : 'ascending';
}

const TONE_CLASSES = {
  success: 'bg-success-soft text-success-strong',
  warning: 'bg-warning-soft text-warning-strong',
  danger: 'bg-danger-soft text-danger-strong',
  info: 'bg-primary-soft text-text-brand',
  neutral: 'bg-surface-raised text-text-muted',
};

const colspan = computed(
  () => props.columns.length
    + (props.showActions ? 1 : 0)
    + (props.selectable ? 1 : 0),
);

// Deterministic width variety for skeleton cells (no randomness so SSR
// markup and snapshots stay stable).
const SKELETON_WIDTHS = ['w-24', 'w-16', 'w-32', 'w-20'];

function skeletonWidthClass(rowIndex, colIndex) {
  return SKELETON_WIDTHS[(rowIndex + colIndex) % SKELETON_WIDTHS.length];
}

/** `col` here is already resolved, so alignment and padding come precomputed. */
function cellClass(col) {
  const classes = [col.padClass, col.alignClass, col.nowrapClass, responsiveCellClass(col)];
  // `link: true` en la columna = acá va el enlace de la fila, y `relative` es
  // el marco contra el que BaseRowLink se estira para cubrir toda la celda.
  if (col.link) classes.push('relative');
  if (col.format === 'money') classes.push('tabular-nums text-text-muted');
  else if (col.format === 'percent') classes.push('tabular-nums text-text-subtle text-xs');
  else if (col.format === 'date') classes.push('text-text-muted text-xs');
  else classes.push('text-text-default');
  return classes;
}

function badgeClass(col, value) {
  const tone = col.badgeTones?.[value] || 'neutral';
  return TONE_CLASSES[tone] || TONE_CLASSES.neutral;
}

function formatGroupedValue(col, value) {
  if (col.format === 'money') return formatMoney(value, 'COP');
  if (col.format === 'percent') return formatPercent(value);
  if (col.format === 'date') return formatDate(value);
  return value ?? '—';
}
</script>

<style scoped>
/* Feedback flash for the row that was just created or edited. The color
 * holds briefly and then decays; with reduced motion it stays solid until
 * the page clears highlightId (the information is kept, not the motion). */
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

@media (min-width: 1024px) {
  .base-responsive-table--priority {
    min-width: var(--table-min-width-landscape, var(--table-min-width));
  }
}
@media (min-width: 1280px) {
  .base-responsive-table--priority {
    min-width: var(--table-min-width);
  }
}

/* Fluid menu-start tables. Below panel-landscape (1024) the layout is auto and
 * the data headers carry no width, so atomic values keep their content width,
 * the wrapping primary column takes the rest and the fixed control tracks get
 * no slack. From panel-landscape up the layout is fixed and the columns each
 * profile shows share 100% of what the tracks leave (panel-desktop at 1280). */
.base-responsive-table--fluid-menu {
  table-layout: auto;
}
.base-responsive-table__fluid-th {
  width: auto;
}
@media (min-width: 1024px) {
  .base-responsive-table--fluid-menu {
    table-layout: fixed;
  }
  .base-responsive-table__fluid-th {
    width: var(--col-w-landscape);
  }
}
@media (min-width: 1280px) {
  .base-responsive-table__fluid-th {
    width: var(--col-w-desktop);
  }
}
</style>
