<script setup>
import { computed } from 'vue'
import DocumentMarkdownBody from '~/components/panel/documents/DocumentMarkdownBody.vue'
import DocumentStateList from '~/components/panel/documents/DocumentStateList.vue'
import {
  formatDocumentDate, archivedAgeLabel,
} from '~/utils/documentStatus'
import { makeSafeExcerpt } from '~/utils/markdownExcerpt'
import BaseActionButton from '~/components/base/BaseActionButton.vue'
import BaseOverflowText from '~/components/base/BaseOverflowText.vue'

const props = defineProps({
  document: { type: Object, required: true },
  editTo: { type: [String, Object], default: null },
  newlyCreated: { type: Boolean, default: false },
  dragging: { type: Boolean, default: false },
  archived: { type: Boolean, default: false },
})

const emit = defineEmits(['open', 'action', 'thread', 'dragstart', 'dragend'])

const excerpt = computed(() => makeSafeExcerpt(props.document.content_excerpt || ''))

const isReadOnlyDocument = computed(() => (
  props.document.is_generated_snapshot
  || props.document.is_contract_mirror
  || props.document.movable === false
  || (
    props.document.document_type_code === 'collection_account'
    && props.document.commercial_status !== 'draft'
  )
))

const meta = computed(() => {
  const parts = []
  if (props.archived) {
    const archivedDate = props.document.archived_at || props.document.created_at
    parts.push(`Archivado · ${archivedAgeLabel(archivedDate) || '—'}`)
  } else {
    parts.push(formatDocumentDate(props.document.created_at))
  }
  const clientLabel = props.document.client_display_name || props.document.client_name
  if (clientLabel) parts.push(clientLabel)
  if (props.document.project_name) parts.push(props.document.project_name)
  return parts.join(' · ')
})
</script>

<template>
  <article
    class="group bg-surface border border-border-muted rounded-xl shadow-card overflow-hidden
           cursor-pointer select-none [content-visibility:auto]
           focus-within:ring-2 focus-within:ring-focus-ring/40
           hover:shadow-raised motion-safe:transition-[transform,box-shadow]
           motion-safe:duration-fast motion-safe:ease-out-soft motion-safe:hover:-translate-y-0.5"
    :class="[
      { 'opacity-50': dragging },
      { 'ring-2 ring-focus-ring/40 bg-primary-soft': newlyCreated },
    ]"
    :draggable="!archived && !isReadOnlyDocument"
    :data-testid="`document-card-${document.id}`"
    @click="emit('open', $event)"
    @auxclick.middle="emit('open', $event)"
    @dragstart="emit('dragstart', $event)"
    @dragend="emit('dragend', $event)"
  >
    <!-- Mini-preview -->
    <div class="relative h-36 overflow-hidden border-b border-border-muted" aria-hidden="true">
      <DocumentMarkdownBody
        v-if="excerpt"
        :markdown="excerpt"
        variant="mini"
        class="px-4 py-3 pointer-events-none select-none"
      />
      <div
        v-else
        class="flex h-full flex-col items-center justify-center gap-2 text-text-subtle"
        data-testid="document-empty-preview"
      >
        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span
          v-if="document.is_generated_snapshot"
          class="text-xs font-semibold uppercase tracking-wide"
          data-testid="document-pdf-preview-label"
        >
          {{ document.document_type_code === 'collection_account'
            ? 'Cuenta de cobro · PDF'
            : 'PDF inmutable' }}
        </span>
      </div>
      <div class="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-surface to-transparent"></div>
      <span
        v-if="archived"
        class="absolute top-2 right-2 inline-flex items-center rounded-full bg-surface-raised px-2 py-0.5 text-2xs font-semibold uppercase text-text-muted shadow-sm dark:text-text-subtle"
      >
        Archivado
      </span>
      <div v-else class="absolute right-2 top-2 max-w-[80%]">
        <BaseBadge
          v-if="document.display_state"
          :variant="document.display_state.variant"
          size="sm"
          :data-testid="`document-card-derived-state-${document.id}`"
        >
          {{ document.display_state.label }}
        </BaseBadge>
        <DocumentStateList v-else :episodes="document.active_states" :max-visible="1" />
      </div>
    </div>

    <!-- Info -->
    <div class="p-4">
      <!-- Sin `stretch`: el kebab vive en esta misma tarjeta y quedaría
           tapado. La tarjeta entera ya responde al clic simple. -->
<div class="flex min-w-0 items-center gap-2">
            <span class="shrink-0 text-xs tabular-nums text-text-muted" data-testid="document-visible-id">#{{ document.id }}</span>
      <BaseOverflowText
        :to="editTo"
        :text="document.title"
        :lines="1"
        :test-id="`document-card-open-${document.id}`"
        content-classes="text-sm font-semibold leading-snug text-text-default"
      />
            </div>
      <div
        v-if="document.folder_name || document.thread_summary"
        class="mt-2 flex min-w-0 max-w-full flex-wrap items-center gap-1"
        :data-testid="`document-card-title-meta-${document.id}`"
      >
        <!-- design-tokens: allow-raw-button — el badge es la puerta al hilo -->
        <button
          v-if="document.thread_summary"
          type="button"
          class="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/40"
          :aria-label="`Abrir el hilo ${document.thread_summary.title}`"
          :data-testid="`document-card-thread-open-${document.id}`"
          @click.stop="emit('thread', document)"
          @auxclick.stop
        >
          <BaseBadge
            variant="info"
            size="sm"
            :title="document.thread_summary.title"
            :data-testid="`document-card-thread-badge-${document.id}`"
          >
            Hilo · {{ document.thread_summary.document_count }}
          </BaseBadge>
        </button>
        <span
          v-if="document.folder_name"
          class="inline-flex min-w-0 max-w-full flex-wrap items-center gap-1 rounded bg-surface-raised px-2 py-0.5 text-2xs font-medium text-text-muted [overflow-wrap:anywhere]"
          :title="`Carpeta: ${document.folder_name}`"
          :data-testid="`document-card-folder-badge-${document.id}`"
        >
          <span aria-hidden="true">📁</span>
          <span class="min-w-0 max-w-full [overflow-wrap:anywhere]">{{ document.folder_name }}</span>
        </span>
      </div>
      <div
        class="flex items-center justify-between gap-2 mt-2 min-h-11"
        :data-testid="`document-card-priority-row-${document.id}`"
      >
        <BaseBadge
          v-if="document.display_state"
          :variant="document.display_state.variant"
          size="sm"
        >
          {{ document.display_state.label }}
        </BaseBadge>
        <DocumentStateList v-else class="min-w-0" :episodes="document.active_states" :max-visible="2" />
        <BaseActionButton
          action="more"
          :label="`Acciones de ${document.title}`"
          class="flex-shrink-0 flex items-center justify-center min-w-11 min-h-11 -mr-2 rounded-lg
                 text-text-subtle hover:text-text-default hover:bg-surface-raised transition-colors
                 outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/40"
          @click.stop="emit('action')"
        />
      </div>
      <p
        class="mt-1 min-w-0 max-w-full whitespace-normal text-xs text-text-muted tabular-nums [overflow-wrap:anywhere]"
        :data-testid="`document-card-secondary-meta-${document.id}`"
      >{{ meta }}</p>
    </div>
  </article>
</template>
