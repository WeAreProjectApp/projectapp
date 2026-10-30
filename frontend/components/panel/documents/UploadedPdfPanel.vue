<script setup>
import { computed, ref, watch } from 'vue';
import { useI18n } from '#imports';
import PdfPreviewPane from '~/components/base/PdfPreviewPane.vue';
import { useDocumentStore } from '~/stores/documents';
import { usePanelNotify } from '~/composables/usePanelNotify';

const props = defineProps({ document: { type: Object, required: true } });
const { t } = useI18n();
const emit = defineEmits(['pending']);
const store = useDocumentStore();
const notify = usePanelNotify();
const file = ref(null);
const error = ref('');
const saving = ref(false);
// Keep the version seen when choosing the file: a refresh must not silently
// authorize replacement of a PDF the operator never reviewed.
const expectedVersion = ref(null);
watch(file, (value) => emit('pending', value ? `${value.name}:${value.size}:${value.lastModified}` : null));
const src = computed(() => `/api/documents/${props.document.id}/pdf/?inline=1&v=${props.document.pdf.version}`);
const textStatus = computed(() => {
  const status = props.document.pdf.text_status;
  return t(`documentPdf.${['indexed', 'partial', 'empty'].includes(status) ? status : 'unindexed'}`);
});

function selectFile(event) {
  error.value = '';
  file.value = null;
  const selected = event.target.files?.[0];
  if (!selected) return;
  if (!selected.name.toLowerCase().endsWith('.pdf')) {
    error.value = t('documentPdf.invalidFormat');
    return;
  }
  if (!selected.size || selected.size > 25 * 1024 * 1024) {
    error.value = t('documentPdf.invalidSize');
    return;
  }
  file.value = selected;
  expectedVersion.value = props.document.pdf.version;
}

async function replace() {
  if (saving.value || !file.value) return;
  saving.value = true;
  const result = await store.replacePdf(props.document.id, file.value, expectedVersion.value);
  saving.value = false;
  if (result.success) {
    file.value = null;
    error.value = '';
    notify.success({ title: t('documentPdf.replaced') });
  } else {
    error.value = result.message;
    notify.error({ title: t('documentPdf.failed'), detail: result.message });
  }
}
</script>

<template>
  <section class="flex min-w-0 flex-col gap-4 rounded-xl border border-border-muted bg-surface p-5 sm:p-6" data-testid="doc-uploaded-pdf-panel">
    <div>
      <h2 class="font-semibold text-text-default">{{ t('documentPdf.heading') }}</h2>
      <p class="mt-1 text-sm text-text-muted">{{ t('documentPdf.original') }}</p>
      <p class="mt-2 break-words text-sm text-text-default" data-testid="doc-pdf-version">{{ t('documentPdf.version', { version: document.pdf.version, filename: document.pdf.filename }) }}</p>
      <p class="mt-1 text-xs text-text-subtle" data-testid="doc-pdf-text-status">{{ textStatus }}</p>
    </div>
    <BaseButton as="a" :to="`/api/documents/${document.id}/pdf/`" target="_blank" rel="noopener noreferrer" variant="secondary" data-testid="doc-pdf-original-download">{{ t('documentPdf.download') }}</BaseButton>
    <PdfPreviewPane :src="src" class="h-[clamp(20rem,52vh,34rem)]" :error-message="t('documentPdf.unavailable')" :loading-label="t('documentPdf.loading')" test-id-prefix="doc-uploaded-pdf" />
    <div v-if="document.pdf_replaceable" class="space-y-3 border-t border-border-muted pt-4">
      <label class="block text-sm font-medium text-text-default" for="doc-pdf-replace-file">{{ t('documentPdf.replace') }}</label>
      <p id="doc-pdf-replace-hint" class="text-xs text-text-subtle">{{ t('documentPdf.sizeHint') }}</p>
      <input :key="document.pdf.version" id="doc-pdf-replace-file" type="file" accept=".pdf,application/pdf" class="w-full text-sm text-text-default" :disabled="saving" :title="saving ? t('documentPdf.saving') : undefined" :aria-invalid="Boolean(error)" aria-describedby="doc-pdf-replace-hint doc-pdf-replace-error" data-testid="doc-pdf-replace-file" @change="selectFile">
      <p v-if="error" id="doc-pdf-replace-error" role="alert" class="text-sm text-danger-strong">{{ error }}</p>
      <BaseButton v-if="file" type="button" variant="primary" :loading="saving" data-testid="doc-pdf-replace-save" @click="replace">{{ t('documentPdf.upload') }}</BaseButton>
    </div>
  </section>
</template>
