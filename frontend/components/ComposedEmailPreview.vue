<script setup>
/**
 * Server-rendered branded email preview.
 *
 * Fetches the real HTML from POST /api/emails/preview/ — the exact same
 * render path the send funnel uses (emails/branded_email.html) — and shows
 * it inside a sandboxed iframe, so the preview can never drift from the
 * email the client actually receives. Shared by the Emails module and the
 * Proposals/Diagnostics composers.
 */
import { onMounted, ref } from 'vue';
import { useEmailStore } from '~/stores/emails';

const props = defineProps({
  subject: { type: String, default: '' },
  greeting: { type: String, default: '' },
  // [{ id, text, markdown }]
  sections: { type: Array, default: () => [] },
  footer: { type: String, default: '' },
  textFormats: { type: Object, default: () => ({}) },
  // Plain names of files/documents to list in the attachments block.
  attachmentNames: { type: Array, default: () => [] },
  // Resolves the proposal's email signature; omit for standalone/diagnostic.
  proposalId: { type: [Number, String], default: null },
});

const emailStore = useEmailStore();
const previewHtml = ref('');
const previewError = ref('');
let requestSeq = 0;

async function fetchPreview() {
  const seq = ++requestSeq;
  previewError.value = '';
  const payload = {
    subject: props.subject,
    greeting: props.greeting,
    sections: props.sections
      .filter(s => (s.text || '').trim())
      .map(s => ({ text: s.text, markdown: !!s.markdown })),
    footer: props.footer,
    text_formats: props.textFormats,
    attachment_names: props.attachmentNames,
  };
  if (props.proposalId) payload.proposal_id = props.proposalId;

  const result = await emailStore.previewEmail(payload);
  if (seq !== requestSeq) return; // a newer request superseded this one
  if (result.success) {
    previewHtml.value = result.data?.html_preview || '';
  } else {
    previewError.value = 'No se pudo generar la vista previa. Intenta de nuevo.';
  }
}

onMounted(fetchPreview);
defineExpose({ fetchPreview });
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-end">
      <BaseButton
        size="sm"
        variant="secondary"
        :loading="emailStore.isLoadingPreview"
        :disabled="emailStore.isLoadingPreview"
        @click="fetchPreview"
      >
        Actualizar vista previa
      </BaseButton>
    </div>

    <div
      v-if="previewError"
      class="rounded-lg bg-danger-soft px-4 py-3 text-xs text-danger-strong"
    >
      {{ previewError }}
    </div>
    <div
      v-else-if="emailStore.isLoadingPreview && !previewHtml"
      class="py-10 text-center text-xs text-text-subtle"
    >
      Generando vista previa...
    </div>
    <iframe
      v-if="previewHtml"
      :srcdoc="previewHtml"
      sandbox="allow-same-origin"
      class="w-full min-h-[600px] border-0 rounded-xl bg-surface"
      title="Vista previa del correo"
    />
  </div>
</template>
