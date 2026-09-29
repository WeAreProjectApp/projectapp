import { onBeforeUnmount, ref } from 'vue';
import { useI18n } from '#imports';
import { get_request } from '~/stores/services/request_http';
import { normalizeBlobApiError } from '~/stores/services/normalize_api_error';
import { downloadBlob, filenameFromDisposition } from '~/utils/downloadFile';
import { usePanelNotify } from '~/composables/usePanelNotify';

/** Session-authenticated panel downloads. Never navigate or open a window. */
export function usePanelDownload() {
  const loading = ref(false);
  const { t } = useI18n();
  const notify = usePanelNotify();
  let controller = null;

  function cancel() {
    controller?.abort();
    controller = null;
    loading.value = false;
  }

  async function download(url, filename = '', expectedType = '') {
    if (loading.value) return;
    loading.value = true;
    const request = new AbortController();
    controller = request;
    try {
      const target = new URL(url, window.location.origin);
      // Only our panel API or same-origin attachments: never send credentials
      // or CSRF headers to a URL supplied by a third-party document.
      if (!url || target.origin !== window.location.origin || !/^https?:$/.test(target.protocol)) {
        throw new Error('Unsupported download URL');
      }
      let response;
      if (target.pathname.startsWith('/api/')) {
        response = await get_request(`${target.pathname.slice(5)}${target.search}`, {
          responseType: 'blob', signal: request.signal,
        });
      } else {
        const result = await fetch(target.href, { credentials: 'same-origin', signal: request.signal });
        response = {
          data: await result.blob(), status: result.status,
          headers: Object.fromEntries(result.headers.entries()),
        };
        if (!result.ok) throw Object.assign(new Error('Download request failed'), { response });
      }
      if (request.signal.aborted) return;
      const type = (response.headers?.['content-type'] || response.data?.type || '').split(';')[0].trim().toLowerCase();
      // A login redirect can be HTTP 200. Refuse HTML/JSON error pages even
      // when the transport succeeded, rather than saving them as a PDF.
      if (!(response.data instanceof Blob) || !response.data.size
        || /^(text\/html|application\/(xhtml\+xml|(?:[\w.-]+\+)?json))$/.test(type)
        || (expectedType && type !== expectedType)) {
        throw Object.assign(new Error('Invalid download response'), { response });
      }
      let fallback = filename;
      if (!fallback) {
        try { fallback = decodeURIComponent(target.pathname.split('/').pop()); } catch { /* use translated default */ }
      }
      downloadBlob(response.data, filenameFromDisposition(response.headers?.['content-disposition']) || fallback || t('pwa.download.file'));
    } catch (error) {
      if (request.signal.aborted) return;
      const status = error?.response?.status;
      const key = status === 401 ? 'sessionExpired' : status === 403 ? 'forbidden' : 'error';
      const normalized = await normalizeBlobApiError(error, t(`pwa.download.${key}`));
      if (!request.signal.aborted) notify.error(normalized.message);
    } finally {
      if (controller === request) {
        loading.value = false;
        controller = null;
      }
    }
  }

  onBeforeUnmount(cancel);
  return { loading, download, cancel };
}
