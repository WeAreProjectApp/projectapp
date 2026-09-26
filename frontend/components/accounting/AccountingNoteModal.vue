<script setup>
import BaseButton from '~/components/base/BaseButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import HighlightText from '~/components/ui/HighlightText.vue';

// A note can run several paragraphs, so the table cell only offers a button and
// the text lives here. A modal and not a tooltip: the table wrapper is
// `overflow-x-auto`, which clips anything positioned absolutely inside a row.
defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: 'Nota' },
  subtitle: { type: String, default: '' },
  /** Who can read the note, when that matters (collection accounts' notes
   *  never reach the client). */
  hint: { type: String, default: '' },
  notes: { type: String, default: '' },
  /** The table search also matches notes; the hit is highlighted here because
   *  the cell no longer shows the text. */
  highlightQuery: { type: String, default: '' },
});

const emit = defineEmits(['close']);
</script>

<template>
  <BaseModal
    :model-value="open"
    kind="detail"
    title-id="accounting-note-title"
    @close="emit('close')"
  >
    <div class="space-y-3 p-6" data-testid="accounting-note-modal">
      <header>
        <h3 id="accounting-note-title" class="text-lg font-bold text-text-default">
          {{ title }}
        </h3>
        <p v-if="subtitle" class="mt-1 text-sm text-text-muted">{{ subtitle }}</p>
        <p v-if="hint" class="mt-2 text-xs text-text-subtle" data-testid="accounting-note-hint">
          {{ hint }}
        </p>
      </header>
      <p
        class="whitespace-pre-line break-words text-sm text-text-default"
        data-testid="accounting-note-body"
      >
        <HighlightText :text="notes" :query="highlightQuery" />
      </p>
      <div class="flex justify-end pt-2">
        <BaseButton variant="secondary" @click="emit('close')">Cerrar</BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
