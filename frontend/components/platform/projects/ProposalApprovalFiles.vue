<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { usePlatformApi } from '~/composables/usePlatformApi';
import { downloadBlob, filenameFromDisposition } from '~/utils/downloadFile';
import { normalizeBlobApiError } from '~/stores/services/normalize_api_error';
import es from '~/locales/proposalApproval/es';
import en from '~/locales/proposalApproval/en';

const props = defineProps({ projectId: { type: [String, Number], required: true }, files: { type: Array, default: () => [] } });
const { locale } = useI18n();
const text = computed(() => locale.value.startsWith('en') ? en : es);
const { get } = usePlatformApi();
const activeId = ref(null);
const error = ref('');
let controller = null;
function cancel() { controller?.abort(); controller = null; activeId.value = null; }
watch(() => props.projectId, cancel);
onBeforeUnmount(cancel);
async function download(file) {
  if (activeId.value !== null) return;
  error.value = '';
  const request = new AbortController();
  controller = request;
  activeId.value = file.id;
  try {
    const response = await get(`projects/${props.projectId}/approval-files/${file.id}/`, { responseType: 'blob', signal: request.signal });
    if (request.signal.aborted) return;
    const mime = String(response.headers?.['content-type'] || response.data?.type || '').split(';')[0].trim().toLowerCase();
    if (!(response.data instanceof Blob) || !response.data.size || /^(text\/html|application\/(xhtml\+xml|(?:[\w.-]+\+)?json))$/.test(mime)) {
      throw Object.assign(new Error('Invalid approval file response'), { response: { ...response, data: null } });
    }
    downloadBlob(response.data, filenameFromDisposition(response.headers?.['content-disposition']) || file.filename);
  } catch (failure) {
    if (request.signal.aborted) return;
    const normalized = await normalizeBlobApiError(failure, text.value.downloadError);
    if (!request.signal.aborted) error.value = normalized.message;
  } finally {
    if (controller === request) { activeId.value = null; controller = null; }
  }
}
</script>

<template>
  <section v-if="files.length" class="mb-5 space-y-3 rounded-xl border border-border-default p-4" data-testid="project-approval-files">
    <h3 class="text-sm font-semibold text-text-default">{{ text.confirmedPacket }}</h3>
    <p class="text-xs text-text-muted">{{ text.packetPreserved }}</p>
    <p v-if="error" role="alert" class="text-sm text-danger-strong">{{ error }}</p>
    <ul class="space-y-3">
      <li v-for="file in files" :key="file.id" class="space-y-1" :data-testid="`project-approval-file-${file.id}`">
        <p class="break-words text-sm font-medium text-text-default">{{ file.title }}</p>
        <p class="break-all text-xs text-text-muted">{{ file.filename }} · {{ (file.size / 1024).toFixed(1) }} KB</p>
        <BaseButton type="button" variant="secondary" size="sm" :loading="activeId === file.id" :disabled="activeId !== null && activeId !== file.id" :disabled-reason="text.processing" :aria-label="`${text.download} ${file.filename}`" @click="download(file)">
          {{ text.download }}
        </BaseButton>
      </li>
    </ul>
  </section>
</template>
