<script setup>
import { computed } from 'vue'
import { useIsMobile } from '~/composables/useIsMobile'
import { ROW_ACTION_LAYOUTS, ROW_ACTION_MENU_TRACK, textPolicyClass } from '~/utils/tableLayout'

const props = defineProps({
  /**
   * Exploratory columns declare `mobile`: primary | secondary | meta | hidden.
   * The declaration is a business decision owned by the consuming table; this
   * component never guesses which information is safe to remove.
   */
  columns: {
    type: Array,
    required: true,
    validator: (columns) => columns.every((column) => (
      ['primary', 'secondary', 'meta', 'hidden'].includes(column.mobile)
    )),
  },
  rows: { type: Array, default: () => [] },
  rowKey: { type: String, default: 'id' },
  caption: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  tableMinWidth: { type: String, default: '48rem' },
  sortKey: { type: String, default: '' },
  sortDir: { type: String, default: 'asc' },
  showActions: { type: Boolean, default: true },
  showSelection: { type: Boolean, default: false },
  /**
   * `inline-end` keeps the labeled trailing column. `menu-start` is for a
   * single three-dot button: a header-less 56 px track after the checkbox and
   * before the data, and the first control of each mobile card.
   */
  rowActionsLayout: {
    type: String,
    default: ROW_ACTION_LAYOUTS.INLINE_END,
    validator: (value) => Object.values(ROW_ACTION_LAYOUTS).includes(value),
  },
  interactiveRows: { type: Boolean, default: false },
  rowClass: { type: [String, Array, Object, Function], default: '' },
  cardTestIdPrefix: { type: String, default: 'responsive-row' },
})

const emit = defineEmits(['sort', 'row-click', 'row-auxclick'])
const { isMobile } = useIsMobile()

const hasMenuStart = computed(() => (
  props.showActions && props.rowActionsLayout === ROW_ACTION_LAYOUTS.MENU_START
))
const hasTrailingActions = computed(() => props.showActions && !hasMenuStart.value)
const menuTrackStyle = {
  width: ROW_ACTION_MENU_TRACK,
  minWidth: ROW_ACTION_MENU_TRACK,
  maxWidth: ROW_ACTION_MENU_TRACK,
}

const primaryColumns = computed(() => props.columns.filter((column) => column.mobile === 'primary'))
const detailColumns = computed(() => props.columns.filter((column) => ['secondary', 'meta'].includes(column.mobile)))
const tableColspan = computed(() => props.columns.length
  + (props.showActions ? 1 : 0)
  + (props.showSelection ? 1 : 0))

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

function contentClass(column) {
  return [textPolicyClass(column), column.cellContentClass]
}

function ariaSort(column) {
  if (!column.sortable) return undefined
  if (props.sortKey !== column.key) return 'none'
  return props.sortDir === 'desc' ? 'descending' : 'ascending'
}

function classesForRow(row) {
  return typeof props.rowClass === 'function' ? props.rowClass(row) : props.rowClass
}

function activateCard(row, event) {
  if (!props.interactiveRows) return
  emit('row-click', row, event)
}
</script>

<template>
  <div :aria-busy="loading ? 'true' : undefined">
    <p class="sr-only" aria-live="polite">
      {{ loading ? 'Cargando registros...' : `${rows.length} registros` }}
    </p>

    <div v-if="!isMobile" class="overflow-x-auto rounded-xl border border-border-default bg-surface shadow-card">
      <table class="w-full text-sm" :style="{ minWidth: tableMinWidth }">
        <caption v-if="caption" class="sr-only">{{ caption }}</caption>
        <thead class="bg-surface-raised text-left text-xs uppercase tracking-wider text-text-muted">
          <tr>
            <th v-if="showSelection" class="w-12 px-3 py-3">
              <div @click.stop>
                <slot name="select-all" />
              </div>
            </th>
            <th
              v-if="hasMenuStart"
              :style="menuTrackStyle"
              class="w-14 min-w-14 max-w-14 px-1.5 py-2 text-center"
              :data-testid="`${cardTestIdPrefix}-actions-header`"
              aria-label="Acciones"
            />
            <th
              v-for="column in columns"
              :key="column.key"
              class="px-4 py-3"
              :class="column.headerClass"
              :aria-sort="ariaSort(column)"
            >
              <button
                v-if="column.sortable"
                type="button"
                class="rounded uppercase tracking-wider hover:text-text-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/50"
                @click="emit('sort', column.key)"
              >
                {{ column.label }}
                <span v-if="sortKey === column.key" aria-hidden="true">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
              </button>
              <template v-else>{{ column.label }}</template>
            </th>
            <th v-if="hasTrailingActions" class="px-4 py-3 text-right">Acciones</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border-muted">
          <tr v-if="!loading && rows.length === 0">
            <td :colspan="tableColspan" class="px-4 py-10 text-center text-text-muted">
              <slot name="empty">Sin registros.</slot>
            </td>
          </tr>
          <tr
            v-for="row in rows"
            :key="row[rowKey]"
            :data-testid="`${cardTestIdPrefix}-${row[rowKey]}`"
            class="transition-colors hover:bg-surface-raised"
            :class="[classesForRow(row), interactiveRows ? 'cursor-pointer' : '']"
            @click="interactiveRows && emit('row-click', row, $event)"
            @auxclick.middle="interactiveRows && emit('row-auxclick', row, $event)"
          >
            <td v-if="showSelection" class="w-12 px-3 py-3" @click.stop>
              <slot name="row-select" :row="row" />
            </td>
            <td
              v-if="hasMenuStart"
              :style="menuTrackStyle"
              class="w-14 min-w-14 max-w-14 px-1.5 py-1.5 text-center whitespace-nowrap"
              :data-testid="`${cardTestIdPrefix}-actions-cell-${row[rowKey]}`"
              @click.stop
              @auxclick.stop
            >
              <slot name="row-actions" :row="row" />
            </td>
            <td
              v-for="column in columns"
              :key="column.key"
              class="px-4 py-3 text-text-default"
              :class="column.cellClass"
            >
              <div :class="contentClass(column)">
                <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                  {{ displayValue(row[column.key]) }}
                </slot>
              </div>
            </td>
            <td v-if="hasTrailingActions" class="px-4 py-3 text-right" @click.stop>
              <div class="flex flex-wrap items-center justify-end gap-1" @click.stop>
                <slot name="row-actions" :row="row" />
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="grid gap-3">
      <div
        v-if="loading && rows.length === 0"
        class="h-32 rounded-xl border border-border-default bg-surface-raised motion-safe:animate-pulse"
        data-testid="exploratory-list-skeleton"
      />
      <div
        v-else-if="rows.length === 0"
        class="rounded-xl border border-border-default bg-surface px-4 py-10 text-center text-sm text-text-muted"
      >
        <slot name="empty">Sin registros.</slot>
      </div>
      <article
        v-for="row in rows"
        :key="row[rowKey]"
        :data-testid="`${cardTestIdPrefix}-${row[rowKey]}`"
        class="min-w-0 rounded-xl border border-border-default bg-surface p-4 shadow-card"
        :class="[classesForRow(row), interactiveRows ? 'cursor-pointer' : '']"
        :role="interactiveRows ? 'link' : undefined"
        :tabindex="interactiveRows ? 0 : undefined"
        @click="activateCard(row, $event)"
        @auxclick.middle="interactiveRows && emit('row-auxclick', row, $event)"
        @keydown.enter.prevent="activateCard(row, $event)"
      >
        <div class="flex min-w-0 items-start gap-3">
          <div v-if="showSelection" class="shrink-0 pt-0.5" @click.stop @keydown.stop>
            <slot name="row-select" :row="row" />
          </div>
          <div
            v-if="hasMenuStart"
            class="-my-1.5 -ml-1.5 shrink-0"
            :data-testid="`${cardTestIdPrefix}-actions-cell-${row[rowKey]}`"
            @click.stop
            @auxclick.stop
            @keydown.stop
          >
            <slot name="row-actions" :row="row" />
          </div>
          <div class="min-w-0 flex-1 space-y-1">
            <div v-for="column in primaryColumns" :key="column.key" class="min-w-0">
              <p v-if="primaryColumns.length > 1" class="text-2xs font-semibold uppercase tracking-wider text-text-subtle">
                {{ column.label }}
              </p>
              <div
                class="min-w-0 font-medium text-text-default"
                :class="[contentClass(column), column.cardClass]"
              >
                <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                  {{ displayValue(row[column.key]) }}
                </slot>
              </div>
            </div>
          </div>
        </div>

        <dl v-if="detailColumns.length" class="mt-3 grid grid-cols-1 gap-x-4 gap-y-2 border-t border-border-muted pt-3 panel-portrait:grid-cols-2">
          <div
            v-for="column in detailColumns"
            :key="column.key"
            class="min-w-0"
            :class="column.mobile === 'meta' ? 'text-xs' : 'text-sm'"
          >
            <dt class="text-2xs font-semibold uppercase tracking-wider text-text-subtle">{{ column.label }}</dt>
            <dd
              class="mt-0.5 min-w-0 text-text-default"
              :class="[contentClass(column), column.cardClass]"
            >
              <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                {{ displayValue(row[column.key]) }}
              </slot>
            </dd>
          </div>
        </dl>

        <div v-if="hasTrailingActions" class="mt-3 flex flex-wrap items-center justify-end gap-1 border-t border-border-muted pt-3" @click.stop @keydown.stop>
          <slot name="row-actions" :row="row" />
        </div>
      </article>
    </div>
  </div>
</template>
