import { onScopeDispose, ref, watch } from 'vue';
import { get_request } from '~/stores/services/request_http';

/** Fetch a single record independently of list filters; ignore superseded reads. */
export function useAccountingRecordDetail(path, recordId, open) {
  const record = ref(null);
  const loading = ref(false);
  const error = ref('');
  let generation = 0;

  async function reload() {
    const current = ++generation;
    record.value = null;
    error.value = '';
    loading.value = false;
    if (!open.value || !recordId.value) return;
    loading.value = true;
    try {
      const response = await get_request(`${path}${recordId.value}/`);
      if (current === generation) record.value = response.data;
    } catch (failure) {
      if (current === generation) error.value = failure.response?.status === 404 ? 'missing' : 'failed';
    } finally {
      if (current === generation) loading.value = false;
    }
  }

  watch([recordId, open], reload, { immediate: true });
  onScopeDispose(() => { generation += 1; });
  return { record, loading, error, reload };
}
