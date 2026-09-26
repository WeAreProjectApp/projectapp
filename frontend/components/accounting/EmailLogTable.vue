<template>
  <div class="overflow-x-auto bg-surface rounded-xl border border-border-muted shadow-sm">
    <table class="accounting-history-table w-full text-sm" :style="{ '--table-min-width': tableMinWidth }">
      <thead>
        <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
          <th
            class="px-1.5 py-2 panel-landscape:w-14"
            aria-label="Acciones"
            data-testid="email-log-actions-header"
          />
          <th
            v-for="col in resolved"
            :key="col.key"
            :style="{ width: col.width }"
            :class="[col.headerPadClass, col.alignClass, col.nowrapClass, visibilityClass(col.key)]"
          >{{ col.label }}</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border-muted">
        <tr v-if="entries.length === 0">
          <td :colspan="resolved.length + 1" class="px-5 py-8 text-center text-sm text-text-subtle">
            Sin envíos.
          </td>
        </tr>
        <template v-for="entry in entries" :key="entry.id">
          <tr
            :data-testid="`email-log-row-${entry.id}`"
            class="accounting-history-row hover:bg-surface-raised transition-colors bg-surface h-9"
            :class="canExpand(entry) ? 'cursor-pointer' : ''"
            @click="toggleEntry(entry)"
          >
            <!-- Stops the click: opening the menu must not also expand the row. -->
            <td
              data-field="actions"
              class="px-1.5 py-1 text-center panel-landscape:w-14"
              @click.stop
            >
              <AccountingRowActionsButton
                v-if="entryActions(entry).length"
                :label="`Acciones del envío a ${entry.recipient}`"
                :test-id="`email-log-actions-${entry.id}`"
                :busy="retryingId === entry.id"
                busy-label="Reintentando el envío"
                @open="actionsEntry = entry"
              />
            </td>
            <td data-field="date" :class="[cell(0), 'text-text-muted text-xs tabular-nums']">
              <span class="history-mobile-label panel-landscape:hidden">Fecha</span>
              {{ formatDateTime(entry.sent_at) }}
            </td>
            <td data-field="notice" :class="[cell(1), 'text-text-muted']">
              <span class="history-mobile-label panel-landscape:hidden">Aviso</span>
              <span :class="resolved[1].contentClass">{{ entry.template_label }}</span>
            </td>
            <td data-field="recipient" :class="[cell(2), 'min-w-0 text-text-default font-medium']">
              <span :class="resolved[2].contentClass">{{ entry.recipient }}</span>
            </td>
            <td data-field="subject" :class="[cell(3), 'text-text-muted']">
              <span class="history-mobile-label panel-landscape:hidden">Asunto</span>
              <span :class="resolved[3].contentClass">{{ entry.subject || '—' }}</span>
            </td>
            <td data-field="status" :class="cell(4)">
              <span
                class="inline-flex min-w-0 max-w-full flex-wrap rounded-full px-2.5 py-1 text-xs font-medium [overflow-wrap:anywhere]"
                :class="statusClass(entry.status)"
              >
                {{ entry.status_label }}
              </span>
            </td>
          </tr>
          <!-- What turns "no me llegó" into a diagnosis: why it failed, what
               it was about, and whether somebody already retried it. -->
          <tr
            v-if="expandedIds.has(entry.id)"
            :data-testid="`email-log-detail-${entry.id}`"
            class="bg-surface-raised"
          >
            <td :colspan="resolved.length + 1" class="px-5 py-3 space-y-1.5">
              <p v-if="entry.error_message" class="text-xs text-danger-strong [overflow-wrap:anywhere]">
                {{ entry.error_message }}
              </p>
              <p v-if="entry.targets && entry.targets.length" class="text-xs text-text-muted">
                <span class="font-medium text-text-default">Salió por:</span>
                {{ targetsLabel(entry) }}
              </p>
              <p v-if="entry.retry_of" class="text-xs text-text-muted">
                Reintento del envío #{{ entry.retry_of }}.
              </p>
              <div v-if="entry.copies?.length" :data-testid="`email-log-copies-${entry.id}`" class="space-y-1.5 pt-1">
                <p class="text-xs font-medium text-text-default">Copias internas (BCC)</p>
                <div
                  v-for="copy in entry.copies"
                  :key="copy.id"
                  class="flex flex-col gap-1 rounded-lg border border-border-muted bg-surface px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                >
                  <span class="break-all text-xs text-text-muted">{{ copy.recipient }}</span>
                  <span
                    class="min-w-0 max-w-full text-xs [overflow-wrap:anywhere]"
                    :class="copy.status === 'failed' ? 'text-danger-strong' : 'text-success-strong'"
                  >
                    {{ copy.status_label }}<span v-if="copy.error_message"> · {{ copy.error_message }}</span>
                  </span>
                </div>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <AccountingRowActionsModal
      :open="actionsEntry !== null"
      :record="actionsEntry"
      :title="actionsEntry ? (actionsEntry.subject || actionsEntry.template_label) : ''"
      :subtitle="actionsEntry ? `${actionsEntry.recipient} · ${formatDateTime(actionsEntry.sent_at)}` : ''"
      :actions="actionsEntry ? entryActions(actionsEntry) : []"
      test-id-prefix="email-log"
      :lock-scroll="!nested"
      @close="actionsEntry = null"
      @select="runEntryAction"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import AccountingRowActionsButton from '~/components/accounting/AccountingRowActionsButton.vue';
import AccountingRowActionsModal from '~/components/accounting/AccountingRowActionsModal.vue';
import { formatDateTime } from '~/utils/formatDate';
import { ROW_ACTION_LAYOUTS, minWidthFor, resolveColumns } from '~/utils/tableLayout';

// Destinatario is the identifying column here — the whole point of the view
// is answering who a notice reached — so it gets the widest floor.
const COLUMNS = [
  { key: 'sent_at', label: 'Fecha', format: 'date' },
  { key: 'template_label', label: 'Aviso' },
  { key: 'recipient', label: 'Destinatario', size: 'name' },
  { key: 'subject', label: 'Asunto' },
  { key: 'status_label', label: 'Estado', size: 'badge' },
];

// The actions track leads the row and holds one kebab, outside the data split.
const LAYOUT = { hasActions: true, rowActionsLayout: ROW_ACTION_LAYOUTS.MENU_START };
const resolved = resolveColumns(COLUMNS, LAYOUT);
const tableMinWidth = minWidthFor(resolved, LAYOUT);

function visibilityClass() {
  return '';
}

/** Padding + alignment for the nth column. */
function cell(index) {
  const col = resolved[index];
  return [col.padClass, col.alignClass, col.nowrapClass];
}

const props = defineProps({
  /**
   * Rows: { id, template_key, template_label, recipient, subject, status,
   * status_label, error_message, sent_at, targets, has_body, is_retryable,
   * retry_blocked_reason, retry_of }.
   */
  entries: { type: Array, default: () => [] },
  /** Row whose retry is in flight, so its button cannot be double-fired. */
  retryingId: { type: [Number, String], default: null },
  /** Rendered inside another modal (the client's emails): the row menu then
   *  leaves the page scroll lock to that modal. */
  nested: { type: Boolean, default: false },
});

const emit = defineEmits(['view-body', 'retry', 'menu-open-change']);

// ── Row menu ──
// A send offers at most two actions (see it as it left, retry a failure), so
// the kebab only appears on a row that has one.
const actionsEntry = ref(null);

function entryActions(entry) {
  const list = [];
  if (entry.has_body) {
    list.push({
      id: 'view-body',
      action: 'view',
      label: 'Ver el correo como salió',
      testId: `email-log-view-body-${entry.id}`,
    });
  }
  if (entry.status === 'failed') {
    const retrying = props.retryingId === entry.id;
    let description = `Reenviar solo a ${entry.recipient}.`;
    if (!entry.is_retryable) {
      description = entry.retry_blocked_reason || 'Este envío no admite reintento.';
    } else if (retrying) {
      description = 'El reintento ya está en curso. Espera a que termine.';
    }
    list.push({
      id: 'retry',
      action: 'retry',
      label: 'Reintentar el envío',
      testId: `email-log-retry-${entry.id}`,
      disabled: !entry.is_retryable || retrying,
      description,
    });
  }
  return list;
}

// The entry ids are the events the hosts already listen to.
function runEntryAction(id, entry) {
  emit(id, entry);
}

// A host modal must stop answering Esc and backdrop clicks while this menu is
// open above it: BaseModal's keydown listener is global.
watch(() => actionsEntry.value !== null, (open) => emit('menu-open-change', open));

const STATUS_CLASSES = {
  sent: 'bg-primary-soft text-text-brand',
  delivered: 'bg-success-soft text-success-strong',
  bounced: 'bg-warning-soft text-warning-strong',
  failed: 'bg-danger-soft text-danger-strong',
};

const expandedIds = ref(new Set());

function canExpand(entry) {
  return Boolean(
    entry.error_message || entry.retry_of || (entry.targets || []).length
      || (entry.copies || []).length,
  );
}

function targetsLabel(entry) {
  return (entry.targets || [])
    .map((target) => (
      target.object_repr
        ? `${target.entity_type_label}: ${target.object_repr}`
        : `${target.entity_type_label} #${target.object_id}`
    ))
    .join(' · ');
}

function toggleEntry(entry) {
  if (!canExpand(entry)) return;
  if (expandedIds.value.has(entry.id)) expandedIds.value.delete(entry.id);
  else expandedIds.value.add(entry.id);
  expandedIds.value = new Set(expandedIds.value);
}

function statusClass(status) {
  return STATUS_CLASSES[status] || 'bg-surface-raised text-text-muted';
}
</script>

<style scoped>
@media (max-width: 1023px) {
  .accounting-history-table thead {
    display: none;
  }

  /* The kebab leads the card, as in every accounting row; a send without
   * actions keeps the empty track so the cards stay aligned. */
  .accounting-history-row {
    display: grid;
    grid-template-columns: 2.75rem minmax(0, 1fr) auto;
    gap: 0.35rem 0.75rem;
    height: auto;
    padding: 0.85rem 1rem;
  }

  .accounting-history-row > td {
    padding: 0;
    white-space: normal;
  }

  .accounting-history-row > [data-field="actions"] {
    grid-column: 1;
    grid-row: 1;
    align-self: start;
  }

  .accounting-history-row > [data-field="recipient"] {
    grid-column: 2;
    grid-row: 1;
  }

  .accounting-history-row > [data-field="status"] {
    grid-column: 3;
    grid-row: 1;
  }

  .accounting-history-row > [data-field="date"],
  .accounting-history-row > [data-field="notice"],
  .accounting-history-row > [data-field="subject"] {
    grid-column: 2 / -1;
  }

  .history-mobile-label {
    display: inline-block;
    min-width: 4.5rem;
    color: var(--color-text-subtle);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
}

@media (min-width: 1024px) {
  .accounting-history-table {
    min-width: var(--table-min-width);
  }
}
</style>
