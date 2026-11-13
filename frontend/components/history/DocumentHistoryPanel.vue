<script setup>
import { computed, nextTick, ref } from 'vue';
import { useMediaQuery } from '@vueuse/core';
import { useI18n } from '#imports';
import BaseDropdown from '~/components/base/BaseDropdown.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import { useDocumentHistory } from '~/composables/useDocumentHistory';
import DocumentHistoryResult from './DocumentHistoryResult.vue';
import { PANEL_MEDIA } from '~/config/responsive';

const props = defineProps({ objectId: { type: [String, Number], required: true } });
const { t, locale } = useI18n();
const {
  result, order, page, loading, listError, selected, active, detailOpen, busy, detailError, mode,
  focusVersion, pagination, load, consult, toggle, clearSelection, compareSelected, goToPage, retry,
} = useDocumentHistory(props);
const detailPanel = ref(null);
const listPanel = ref(null);
const isLandscape = useMediaQuery(PANEL_MEDIA.landscape);
let listScroll = 0;
const readingScroll = { changes: 0, full: 0 };
const readingWindowScroll = { changes: 0, full: 0 };
const date = (value) => value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota' }).format(new Date(value)) : '';
const orderItems = computed(() => ['recent', 'oldest'].map((value) => ({
  label: `${order.value === value ? '✓ ' : ''}${t(`documentHistory.${value}`)}`,
  onClick: () => { order.value = value; }, testid: `history-order-${value}`,
})));
const selectedLabel = computed(() => [...selected.value].sort((a, b) => a.number - b.number).map((row) => `v${row.number}`).join(' → '));
const versionLabel = (row) => row?.number ? t('documentHistory.version', { number: row.number }) : t('documentHistory.legacyEvent');
const actionLabel = (action) => t(`documentHistory.actions.${['created', 'updated', 'deleted', 'baseline', 'sent_version'].includes(action) ? action : 'other'}`);
const rowSummary = (entry) => [...new Set((entry.fields || []).map((field) => field.label))].slice(0, 3).join(' · ');

async function show(action) {
  listScroll = window.scrollY;
  readingScroll.changes = 0;
  readingScroll.full = 0;
  readingWindowScroll.changes = 0;
  readingWindowScroll.full = 0;
  action();
  await nextTick();
  detailPanel.value?.scrollTo?.({ top: 0 });
  detailPanel.value?.scrollIntoView?.({ block: 'start' });
  detailPanel.value?.focus({ preventScroll: true });
}
async function back() {
  detailOpen.value = false;
  await nextTick();
  window.scrollTo({ top: listScroll });
  listPanel.value?.focus({ preventScroll: true });
}
async function switchMode() {
  readingScroll[mode.value] = detailPanel.value?.scrollTop || 0;
  readingWindowScroll[mode.value] = window.scrollY;
  mode.value = mode.value === 'changes' ? 'full' : 'changes';
  await nextTick();
  detailPanel.value?.scrollTo?.({ top: readingScroll[mode.value] });
  if (!isLandscape.value) {
    if (readingWindowScroll[mode.value]) window.scrollTo({ top: readingWindowScroll[mode.value] });
    else detailPanel.value?.scrollIntoView?.({ block: 'start' });
  }
}
</script>

<template>
  <section class="min-w-0 text-text-default" data-testid="entity-history">
    <div class="grid min-w-0 items-start gap-4 panel-landscape:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <div ref="listPanel" tabindex="-1" class="min-w-0 space-y-3 focus:outline-none" :class="{ 'hidden panel-landscape:block': detailOpen }" data-testid="history-list">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-base font-semibold">{{ t('documentHistory.title') }}</h2>
          <BaseDropdown :items="orderItems" width="w-64">
            <template #trigger>
              <BaseButton variant="secondary" size="sm" data-testid="history-order">{{ t(`documentHistory.${order}`) }} <span aria-hidden="true">⌄</span></BaseButton>
            </template>
          </BaseDropdown>
        </div>
        <p v-if="result?.latest_change" class="text-xs text-text-muted" data-testid="history-latest">{{ t('documentHistory.latest') }} {{ date(result.latest_change.occurred_at) }} · {{ result.latest_change.actor }}</p>
        <div v-if="selected.length" class="space-y-2 rounded-lg border border-border-default bg-surface-raised p-3 text-sm" data-testid="history-selection">
          <p>{{ t('documentHistory.selected') }} <strong>{{ selectedLabel }}</strong></p>
          <div class="flex flex-wrap items-center gap-2">
            <BaseButton variant="secondary" size="sm" :disabled="selected.length !== 2" :disabled-reason="t('documentHistory.selectTwo')" data-testid="history-compare" @click="show(compareSelected)">{{ t('documentHistory.compare') }}</BaseButton>
            <BaseButton variant="ghost" size="sm" @click="clearSelection">{{ t('documentHistory.clear') }}</BaseButton>
          </div>
          <p v-if="selected.length === 2" class="text-xs text-text-muted">{{ t('documentHistory.selectionLimit') }}</p>
        </div>
        <div v-if="listError" role="alert" class="space-y-2 rounded-lg bg-danger-soft p-3 text-sm text-danger-strong">
          <p>{{ t('documentHistory.listError') }}</p>
          <BaseButton variant="secondary" size="sm" @click="load">{{ t('documentHistory.retry') }}</BaseButton>
        </div>
        <p v-if="loading" role="status" class="p-3 text-sm text-text-muted">{{ t('documentHistory.loading') }}</p>
        <p v-else-if="result && !result.count" class="text-sm text-text-muted">{{ t('documentHistory.empty') }}</p>
        <ol v-else-if="result" class="divide-y divide-border-muted rounded-lg border border-border-muted bg-surface">
          <li v-for="entry in result.results" :key="entry.id" class="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 px-3 py-2" :class="{ 'bg-primary-soft ring-1 ring-inset ring-focus-ring': focusVersion?.id === entry.id, 'bg-surface-raised': selected.some(row => row.id === entry.id) }" :data-testid="`history-entry-${entry.id}`" :aria-current="focusVersion?.id === entry.id ? 'true' : undefined">
            <input v-if="entry.complete" type="checkbox" class="h-4 w-4 accent-primary" :checked="selected.some(row => row.id === entry.id)" :aria-label="t('documentHistory.selectVersion', { number: entry.number })" :disabled="selected.length === 2 && !selected.some(row => row.id === entry.id)" :title="selected.length === 2 && !selected.some(row => row.id === entry.id) ? t('documentHistory.selectionLimit') : undefined" @change="toggle(entry)">
            <span v-else aria-hidden="true" class="w-4" />
            <div class="min-w-0 text-xs">
              <p class="break-words text-sm font-medium">{{ entry.complete ? `v${entry.number}` : t('documentHistory.legacyEvent') }} · {{ actionLabel(entry.action) }}</p>
              <p class="text-text-muted"><time :datetime="entry.occurred_at">{{ date(entry.occurred_at) }}</time> · {{ entry.actor }}</p>
              <p class="truncate text-text-muted" :title="(entry.fields || []).map(field => field.label).join(', ')">{{ rowSummary(entry) }}</p>
              <p v-if="!entry.complete" class="text-text-muted">{{ t('documentHistory.legacySummary') }}</p>
            </div>
            <BaseButton variant="ghost" size="sm" :aria-pressed="focusVersion?.id === entry.id" @click="show(() => consult(entry))">{{ t('documentHistory.consult') }}</BaseButton>
          </li>
        </ol>
        <BasePagination v-if="result && !loading" v-bind="pagination" :aria-label="t('documentHistory.pagination')" @prev="goToPage(page - 1)" @next="goToPage(page + 1)" @go="goToPage" />
      </div>
      <aside ref="detailPanel" tabindex="-1" class="history-consultation min-w-0 space-y-4 rounded-xl border border-border-muted bg-surface p-4 focus:outline-none panel-landscape:sticky panel-landscape:top-4 panel-landscape:overflow-y-auto" :class="{ 'hidden panel-landscape:block': !detailOpen }" :aria-label="t('documentHistory.consultation')" :aria-busy="busy" data-testid="history-version-detail">
        <template v-if="detailOpen">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h3 class="text-base font-semibold">{{ versionLabel(active?.to || focusVersion) }}</h3>
            <BaseButton variant="ghost" size="sm" @click="back">{{ t('documentHistory.back') }}</BaseButton>
          </div>
          <p v-if="busy" role="status" class="text-sm text-text-muted">{{ t('documentHistory.consulting') }}</p>
          <div v-else-if="detailError" role="alert" class="space-y-3 rounded-lg bg-danger-soft p-3 text-sm text-danger-strong">
            <p>{{ t('documentHistory.consultError') }}</p>
            <BaseButton variant="secondary" size="sm" @click="retry">{{ t('documentHistory.retry') }}</BaseButton>
          </div>
          <template v-else-if="active">
            <div class="space-y-2 border-b border-border-muted pb-3 text-sm" data-testid="history-comparison-heading">
              <template v-if="active.from">
                <p class="font-semibold">{{ t('documentHistory.direction', { from: active.from.number, to: active.to.number }) }}</p>
                <p class="text-xs text-text-muted">{{ t('documentHistory.origin') }}: v{{ active.from.number }} · {{ date(active.from.occurred_at) }} · {{ active.from.actor }}</p>
              </template>
              <p class="text-xs text-text-muted">{{ active.from ? t('documentHistory.destination') : t('documentHistory.revision') }}: {{ versionLabel(active.to) }} · {{ date(active.to.occurred_at) }} · {{ active.to.actor }}</p>
              <BaseButton v-if="active.to.complete && active.from" variant="secondary" size="sm" data-testid="history-full-version" @click="switchMode">{{ t(mode === 'changes' ? 'documentHistory.fullVersion' : 'documentHistory.backToComparison') }}</BaseButton>
            </div>
            <DocumentHistoryResult :active="active" :full="mode === 'full'" :object-id="objectId" />
          </template>
        </template>
        <p v-else class="text-sm text-text-muted">{{ t('documentHistory.prompt') }}</p>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.history-consultation { overflow-wrap: anywhere; }
@media (min-width: 1024px) {
  .history-consultation { max-height: calc(100dvh - 3rem); }
}
</style>
