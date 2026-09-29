import { computed, ref, toValue, watch } from 'vue';

/** Shared public download behavior for the floating control and closing link. */
export function useProposalPdfDownload({ proposal, url, filename, isLegal = false }) {
  const isGenerating = ref(false);
  const expiredResponse = ref(false);
  const errorMessage = ref('');
  const language = computed(() => toValue(proposal)?.language || 'es');
  const expiredMessage = computed(() => language.value === 'en'
    ? 'This proposal has expired. Request an updated version to download the PDF.'
    : 'Esta propuesta está vencida. Solicita una versión actualizada para descargar el PDF.');
  const isExpired = computed(() => {
    if (toValue(isLegal)) return false;
    const current = toValue(proposal);
    return expiredResponse.value || Boolean(current?.expired_meta)
      || current?.status === 'expired'
      || Boolean(current?.expires_at && Date.parse(current.expires_at) < Date.now());
  });
  const message = computed(() => isExpired.value ? expiredMessage.value : errorMessage.value);

  watch([() => toValue(proposal)?.uuid, () => toValue(url)], () => {
    expiredResponse.value = false;
    errorMessage.value = '';
  });

  async function downloadPdf() {
    if (isGenerating.value || isExpired.value || !toValue(proposal)?.uuid) return;
    isGenerating.value = true;
    errorMessage.value = '';
    try {
      const response = await fetch(toValue(url));
      if (response.status === 410 && !toValue(isLegal)) {
        expiredResponse.value = true;
        return;
      }
      if (!response.ok) throw new Error(`PDF request failed: ${response.status}`);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      try {
        link.href = objectUrl;
        link.download = toValue(filename);
        document.body.appendChild(link);
        link.click();
      } finally {
        link.remove();
        URL.revokeObjectURL(objectUrl);
      }
    } catch {
      errorMessage.value = language.value === 'en'
        ? 'The PDF could not be downloaded. Please try again.'
        : 'No se pudo descargar el PDF. Inténtalo nuevamente.';
    } finally {
      isGenerating.value = false;
    }
  }

  return { isGenerating, isExpired, message, downloadPdf };
}
