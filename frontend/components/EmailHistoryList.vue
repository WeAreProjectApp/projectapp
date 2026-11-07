<script setup>
import { ref } from 'vue';
import { formatDateTime } from '~/utils/formatDate';
import BaseCollapse from '~/components/base/BaseCollapse.vue';
import { recipientSummary } from '~/utils/emailRecipients';
import { emailStatusLabel as statusLabel } from '~/utils/emailStatus';

/**
 * Sent-email history panel — shared by the Proposals and Diagnostics email
 * composers. Self-contained expand/collapse (animated via BaseCollapse). The
 * consumer owns pagination and emits nothing but `load-more`.
 *
 * The `#entry-meta` slot receives each entry so a module can append extra
 * metadata (e.g. the diagnostics template label) after the date.
 */
defineProps({
  history: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  hasNextPage: { type: Boolean, default: false },
  emptyLabel: { type: String, default: 'No se han enviado correos.' },
})

defineEmits(['load-more'])

function copyStatusClass(status) {
  if (status === 'failed' || status === 'bounced') return 'text-danger-strong'
  if (status === 'skipped') return 'text-warning-strong'
  return 'text-success-strong'
}

function historyRecipientSummary(recipients, fallback = '') {
  return recipientSummary(recipients?.length ? recipients : [fallback]);
}

function deliveryRecipients(entry) {
  return [
    ...(entry.to_recipients || []).map(recipient => ({ ...recipient, kindLabel: 'Para' })),
    ...(entry.cc_recipients || []).map(recipient => ({ ...recipient, kindLabel: 'CC' })),
  ];
}

function formatDate(isoString) {
  return formatDateTime(isoString, { fallback: '' })
}

// metadata.sections stores legacy plain strings and new {text, markdown} dicts.
function sectionText(section) {
  return typeof section === 'string' ? section : (section?.text || '')
}
function sectionIsMarkdown(section) {
  return typeof section === 'object' && !!section?.markdown
}

const expandedIds = ref({})
function toggleExpand(id) {
  if (expandedIds.value[id]) delete expandedIds.value[id]
  else expandedIds.value[id] = true
}
</script>

<template>
  <div v-if="loading && !history.length" class="text-xs text-text-subtle py-4 text-center">
    Cargando historial…
  </div>
  <div v-else-if="!history.length" class="text-xs text-text-subtle py-4 text-center">
    {{ emptyLabel }}
  </div>
  <div v-else class="space-y-2">
    <div v-for="entry in history" :key="entry.id"
      class="border border-border-muted rounded-lg overflow-hidden">
      <button type="button" @click="toggleExpand(entry.id)"
        class="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-muted motion-safe:transition-colors motion-safe:duration-fast focus:outline-none focus:ring-2 focus:ring-focus-ring/40">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium text-text-default truncate">{{ entry.subject }}</span>
            <span class="px-1.5 py-0.5 rounded text-2xs font-medium"
              :class="{
                'bg-primary-soft text-text-brand': entry.status === 'sent' || entry.status === 'delivered',
                'bg-danger-soft text-danger-strong': entry.status === 'failed' || entry.status === 'bounced',
              }">{{ statusLabel(entry.status) }}</span>
          </div>
          <div class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span class="break-all text-2xs text-text-muted">Para: {{ historyRecipientSummary(entry.to_recipients, entry.recipient) }}</span>
            <span v-if="entry.cc_recipients?.length" class="break-all text-2xs text-text-muted">CC: {{ historyRecipientSummary(entry.cc_recipients) }}</span>
            <span class="text-2xs text-text-subtle">{{ formatDate(entry.sent_at) }}</span>
            <slot name="entry-meta" :entry="entry" />
          </div>
        </div>
        <BaseActionIcon
          :action="expandedIds[entry.id] ? 'collapse' : 'expand'"
          class="text-text-subtle motion-safe:transition-transform motion-safe:duration-fast"
        />
      </button>

      <BaseCollapse :open="Boolean(expandedIds[entry.id])">
        <div class="border-t border-border-muted px-4 py-3 bg-surface-muted space-y-3">
          <div v-if="deliveryRecipients(entry).length">
            <p class="mb-1 text-2xs uppercase tracking-wide text-text-subtle">Destinatarios</p>
            <div class="space-y-1.5">
              <div
                v-for="recipient in deliveryRecipients(entry)"
                :key="`${recipient.kindLabel}-${recipient.email}`"
                class="rounded-lg border border-border-muted bg-surface px-3 py-2"
              >
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <span class="break-all text-xs text-text-default">{{ recipient.kindLabel }} · {{ recipient.email }}</span>
                  <span class="text-2xs font-medium" :class="copyStatusClass(recipient.status)">
                    {{ statusLabel(recipient.status) }}
                  </span>
                </div>
                <p v-if="recipient.error_message" class="mt-1 text-2xs text-danger-strong">{{ recipient.error_message }}</p>
              </div>
            </div>
          </div>
          <div v-if="entry.metadata?.greeting">
            <p class="text-2xs text-text-subtle uppercase tracking-wide mb-0.5">Saludo</p>
            <p class="text-xs text-text-default">{{ entry.metadata.greeting }}</p>
          </div>
          <div v-if="entry.metadata?.sections?.length">
            <p class="text-2xs text-text-subtle uppercase tracking-wide mb-1">Secciones</p>
            <div v-for="(section, idx) in entry.metadata.sections" :key="idx"
              class="bg-surface rounded-lg px-3 py-2 mb-1.5 border border-border-muted">
              <span v-if="sectionIsMarkdown(section)"
                class="inline-block mb-1 px-1.5 py-0.5 bg-primary-soft text-text-brand rounded text-[9px] font-medium uppercase tracking-wide">MD</span>
              <p class="text-xs text-text-default whitespace-pre-wrap">{{ sectionText(section) }}</p>
            </div>
          </div>
          <div v-if="entry.metadata?.footer">
            <p class="text-2xs text-text-subtle uppercase tracking-wide mb-0.5">Pie de correo</p>
            <p class="text-xs text-text-default">{{ entry.metadata.footer }}</p>
          </div>
          <div v-if="entry.metadata?.attachment_names?.length">
            <p class="text-2xs text-text-subtle uppercase tracking-wide mb-0.5">Adjuntos</p>
            <div class="flex flex-wrap gap-1">
              <span v-for="(name, idx) in entry.metadata.attachment_names" :key="idx"
                class="inline-flex items-center gap-1 px-2 py-0.5 bg-surface border border-border-default rounded text-2xs text-text-muted">
                <BaseActionIcon action="attach" />
                {{ name }}
              </span>
            </div>
          </div>
          <div v-if="entry.copies?.length" :data-testid="`email-copy-list-${entry.id}`">
            <p class="text-2xs text-text-subtle uppercase tracking-wide mb-1">Copias internas (BCC)</p>
            <div class="space-y-1.5">
              <div
                v-for="copy in entry.copies"
                :key="copy.id"
                class="rounded-lg border border-border-muted bg-surface px-3 py-2"
              >
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <span class="break-all text-xs text-text-default">{{ copy.recipient }}</span>
                  <span class="text-2xs font-medium" :class="copyStatusClass(copy.status)">
                    {{ statusLabel(copy.status) }}
                  </span>
                </div>
                <p
                  v-if="copy.error_message"
                  class="mt-1 text-2xs"
                  :class="copy.status === 'skipped' ? 'text-warning-strong' : 'text-danger-strong'"
                >{{ copy.error_message }}</p>
              </div>
            </div>
          </div>
        </div>
      </BaseCollapse>
    </div>

    <div v-if="hasNextPage" class="pt-3 text-center">
      <BaseButton variant="secondary" size="sm" :disabled="loading" @click="$emit('load-more')">
        {{ loading ? 'Cargando…' : 'Cargar más' }}
      </BaseButton>
    </div>
  </div>
</template>
