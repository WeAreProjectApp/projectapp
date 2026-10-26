<template>
  <section aria-labelledby="attention-radar-title" data-testid="attention-radar">
    <h2
      id="attention-radar-title"
      class="mb-3 text-xs font-semibold uppercase tracking-widest text-text-muted"
    >
      Radar de atención
    </h2>

    <div
      v-if="!items.length"
      class="flex items-center gap-3 rounded-xl border border-success-soft bg-success-soft px-5 py-4"
      data-testid="attention-radar-empty"
    >
      <CheckCircleIcon class="w-6 h-6 shrink-0 text-success-strong" aria-hidden="true" />
      <p class="text-sm text-success-strong font-medium">
        Nada requiere tu atención. Todo al día.
      </p>
    </div>

    <ul v-else class="space-y-2" data-testid="attention-radar-list">
      <li v-for="item in items" :key="item.type">
        <!-- design-tokens: allow-raw-button (accordion header, not a command action) -->
        <button
          type="button"
          :aria-expanded="Boolean(groups[item.type]?.open)"
          :aria-controls="`radar-records-${item.type}`"
          @click="toggle(item.type)"
          class="group flex w-full text-left items-center gap-3 rounded-xl border-l-4 bg-surface border border-border-muted px-4 py-3 shadow-card
                 transition-shadow duration-base motion-reduce:transition-none hover:shadow-raised
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          :class="severityBorder(item.severity)"
          :data-testid="`attention-item-${item.type}`"
        >
          <span
            class="flex w-9 h-9 shrink-0 items-center justify-center rounded-full"
            :class="severityBadge(item.severity)"
          >
            <component :is="config(item).icon" class="w-5 h-5" aria-hidden="true" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-medium text-text-default">
              {{ config(item).text(item) }}
            </span>
            <span class="block text-xs text-text-subtle mt-0.5">
              {{ config(item).module }}
            </span>
          </span>
          <span
            class="shrink-0 text-text-muted"
            aria-hidden="true"
          >
          <BaseActionIcon :action="groups[item.type]?.open ? 'collapse' : 'expand'" />
          </span>
        </button>
        <div v-if="groups[item.type]?.open" :id="`radar-records-${item.type}`" class="mt-2 rounded-xl border border-border-muted bg-surface p-3" :data-testid="`radar-records-${item.type}`" :aria-busy="groups[item.type].loading">
          <ul class="space-y-2">
            <li v-for="record in groups[item.type].records" :key="record.id">
              <!-- design-tokens: allow-raw-button (selectable record opens its preview) -->
              <button type="button" class="w-full min-w-0 rounded-lg border border-border-muted p-3 text-left hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring" :data-testid="`radar-record-${item.type}-${record.id}`" @click="openDetail(record)">
                <span class="mb-2 block break-words text-sm font-medium text-text-default">{{ record.title }}</span>
                <DashboardAttentionFields :record="record" compact />
              </button>
            </li>
          </ul>
          <p v-if="groups[item.type].loading" class="mt-3 text-sm text-text-muted" role="status">{{ text.loading }}</p>
          <div v-else-if="groups[item.type].error" class="mt-3" role="alert">
            <p class="text-sm text-danger-strong">{{ text.loadError }}</p>
            <BaseButton variant="secondary" size="sm" @click="loadPage(item.type)">{{ text.retry }}</BaseButton>
          </div>
          <p v-else-if="!groups[item.type].records.length" class="text-sm text-text-muted">{{ text.empty }}</p>
          <BaseButton v-else-if="groups[item.type].hasNext" class="mt-3" variant="secondary" size="sm" :data-testid="`radar-more-${item.type}`" @click="loadPage(item.type)">{{ text.more }}</BaseButton>
        </div>
      </li>
    </ul>
    <BaseModal :model-value="detailOpen" kind="detail" @update:model-value="closeDetail">
      <div class="p-5 panel-portrait:p-6" data-testid="radar-detail-modal">
        <h2 class="mb-4 break-words text-lg font-medium text-text-default">{{ selected?.title || text.loading }}</h2>
        <p v-if="detailLoading" class="text-sm text-text-muted" role="status">{{ text.loading }}</p>
        <div v-else-if="detailError" role="alert">
          <p class="text-sm text-danger-strong">{{ detailError }}</p>
          <BaseButton v-if="canRetryDetail" variant="secondary" @click="openDetail(selected)">{{ text.retry }}</BaseButton>
        </div>
        <template v-else-if="selected">
          <p v-if="!selected.eligible" class="mb-4 text-sm text-warning-strong" role="status">{{ text.changed }}</p>
          <DashboardAttentionFields :record="selected" />
          <p v-if="selected.type === 'emails_failed'" class="mt-4 text-sm text-text-muted">{{ selected.can_resend ? text.resend : text.noResend }}</p>
        </template>
      </div>
      <BaseModalActions>
        <BaseButton variant="secondary" @click="closeDetail">{{ text.close }}</BaseButton>
        <BaseButton v-if="selected?.destination && !detailLoading && !detailError" as="NuxtLink" :to="localePath(selected.destination)" data-testid="radar-detail-destination">{{ text.destination[selected.type] }}</BaseButton>
      </BaseModalActions>
    </BaseModal>
  </section>
</template>

<script setup>
import { ref, reactive, onBeforeUnmount } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseModalActions from '~/components/base/BaseModalActions.vue';
import DashboardAttentionFields from './DashboardAttentionFields.vue';
import { usePanelDashboardStore } from '~/stores/panel_dashboard';
import { useDashboardAttentionText } from '~/composables/useDashboardAttentionText';
import {
  CheckCircleIcon,
  ClipboardDocumentListIcon,
  CreditCardIcon,
  DocumentTextIcon,
  EnvelopeIcon,
  PaperAirplaneIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/vue/24/outline';

/**
 * Cross-module actionable list: each backend attention item maps to
 * Spanish copy, a module label, an icon and a deep-link. Severity only
 * changes the visual accent (danger/warning/info status tokens).
 */
defineProps({
  /** Backend items: [{ type, severity, count, meta }] sorted by severity. */
  items: { type: Array, default: () => [] },
});

const localePath = useLocalePath();
const store = usePanelDashboardStore();
const text = useDashboardAttentionText();
const groups = reactive({});
const detailOpen = ref(false);
const detailLoading = ref(false);
const selected = ref(null);
const detailError = ref('');
const canRetryDetail = ref(false);
let requestId = 0;
let disposed = false;
onBeforeUnmount(() => { disposed = true; requestId += 1; });

async function loadPage(type) {
  const group = groups[type];
  if (group.loading) return;
  group.loading = true;
  group.error = false;
  try {
    const data = await store.fetchAttentionPage(type, group.page + 1);
    if (disposed) return;
    const known = new Set(group.records.map((row) => row.id));
    group.records.push(...data.results.filter((row) => !known.has(row.id)));
    group.page = data.page;
    group.hasNext = data.has_next;
  } catch {
    if (!disposed) group.error = true;
  } finally {
    if (!disposed) group.loading = false;
  }
}
function toggle(type) {
  groups[type] ||= { open: false, loading: false, error: false, records: [], page: 0, hasNext: false };
  groups[type].open = !groups[type].open;
  if (groups[type].open && groups[type].page === 0) loadPage(type);
}
function closeDetail() {
  detailOpen.value = false;
  requestId += 1;
}
async function openDetail(record) {
  selected.value = record;
  detailOpen.value = true;
  detailLoading.value = true;
  detailError.value = '';
  const token = ++requestId;
  try {
    const data = await store.fetchAttentionDetail(record.type, record.id);
    if (token !== requestId) return;
    selected.value = data;
    if (!data.eligible) refreshGroup(record.type);
  } catch (error) {
    if (token !== requestId) return;
    const status = error.response?.status;
    canRetryDetail.value = status !== 404 && status !== 403;
    detailError.value = status === 404 ? text.value.missing : status === 403 ? text.value.forbidden : text.value.detailError;
    if (status === 404) refreshGroup(record.type);
  } finally {
    if (token === requestId) detailLoading.value = false;
  }
}
function refreshGroup(type) {
  const group = groups[type];
  if (!group || group.loading) return;
  group.records = [];
  group.page = 0;
  loadPage(type);
}

function plural(count, singular, plural_) {
  return count === 1 ? singular : plural_;
}

const TYPE_CONFIG = {
  documents_overdue: {
    icon: DocumentTextIcon,
    module: 'Documentos',
    route: '/panel/documents',
    text: ({ count }) =>
      `${count} ${plural(count, 'cuenta de cobro vencida', 'cuentas de cobro vencidas')}`,
  },
  emails_failed: {
    icon: EnvelopeIcon,
    module: 'Emails',
    route: '/panel/emails',
    text: ({ count }) =>
      `${count} ${plural(count, 'email fallido', 'emails fallidos')} en los últimos 7 días`,
  },
  tasks_overdue: {
    icon: ClipboardDocumentListIcon,
    module: 'Tareas',
    route: '/panel/tasks',
    text: ({ count, meta }) => {
      const base = `${count} ${plural(count, 'tarea vencida', 'tareas vencidas')}`;
      return meta?.high_priority
        ? `${base} · ${meta.high_priority} de alta prioridad`
        : base;
    },
  },
  proposals_stale: {
    icon: PaperAirplaneIcon,
    module: 'Propuestas',
    route: '/panel/proposals',
    text: ({ count, meta }) =>
      `${count} ${plural(count, 'propuesta enviada', 'propuestas enviadas')} sin abrir hace más de ${meta?.days ?? 7} días`,
  },
  recurring_due: {
    icon: CreditCardIcon,
    module: 'Contabilidad',
    route: '/panel/accounting/recurring',
    text: ({ count, meta }) => {
      const base = `${count} ${plural(count, 'pago recurrente', 'pagos recurrentes')}`;
      if (meta?.next_days === 0) return `${base} — el próximo vence hoy`;
      if (meta?.next_days === 1) return `${base} — el próximo vence mañana`;
      return `${base} en los próximos 7 días`;
    },
  },
};

const FALLBACK_CONFIG = {
  icon: QuestionMarkCircleIcon,
  module: 'Panel',
  route: '/panel',
  text: ({ count }) => `${count} pendientes`,
};

function config(item) {
  return TYPE_CONFIG[item.type] || FALLBACK_CONFIG;
}

const SEVERITY_BORDER = {
  danger: 'border-l-danger-strong',
  warning: 'border-l-warning-strong',
  info: 'border-l-info-strong',
};

const SEVERITY_BADGE = {
  danger: 'bg-danger-soft text-danger-strong',
  warning: 'bg-warning-soft text-warning-strong',
  info: 'bg-info-soft text-info-strong',
};

function severityBorder(severity) {
  return SEVERITY_BORDER[severity] || SEVERITY_BORDER.info;
}

function severityBadge(severity) {
  return SEVERITY_BADGE[severity] || SEVERITY_BADGE.info;
}
</script>
