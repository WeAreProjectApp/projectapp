import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import { useEntityHistoryStore } from '~/stores/entity_history';

/** Each mounted history owns its requests and active immutable snapshots. */
export function useDocumentHistory(props) {
  const store = useEntityHistoryStore();
  const result = shallowRef(null);
  const order = ref('recent');
  const page = ref(1);
  const loading = ref(false);
  const listError = ref(false);
  const selected = ref([]);
  const active = shallowRef(null);
  const detailOpen = ref(false);
  const busy = ref(false);
  const detailError = ref(false);
  const mode = ref('changes');
  const focusVersion = shallowRef(null);
  let listGeneration = 0;
  let detailGeneration = 0;
  let retryDetail = null;

  async function load() {
    const generation = ++listGeneration;
    loading.value = true;
    listError.value = false;
    // Hide rows from the previous page/order until the matching response arrives.
    result.value = null;
    try {
      const response = await store.list('document', props.objectId, page.value, order.value);
      if (generation === listGeneration) result.value = response;
    } catch {
      if (generation === listGeneration) listError.value = true;
    } finally {
      if (generation === listGeneration) loading.value = false;
    }
  }

  function invalidateDetail() {
    detailGeneration++;
    active.value = null;
    busy.value = false;
    detailError.value = false;
    retryDetail = null;
    mode.value = 'changes';
  }

  async function requestDetail(action, target) {
    invalidateDetail();
    const generation = detailGeneration;
    detailOpen.value = true;
    focusVersion.value = target;
    busy.value = true;
    retryDetail = () => requestDetail(action, target);
    try {
      const response = await action();
      if (generation === detailGeneration) active.value = response;
    } catch {
      if (generation === detailGeneration) detailError.value = true;
    } finally {
      if (generation === detailGeneration) busy.value = false;
    }
  }

  function consult(entry) {
    const objectId = props.objectId;
    return requestDetail(async () => {
      const to = await store.version('document', objectId, entry.id);
      if (!to.complete || !to.previous_id) return { from: null, to, comparison: null };
      const from = await store.version('document', objectId, to.previous_id);
      // Requests are tied to the object ID captured before any await.
      const comparison = await store.compare('document', objectId, from.id, to.id);
      return { from, to, comparison };
    }, entry);
  }

  function compareSelected() {
    if (selected.value.length !== 2) return;
    const ordered = [...selected.value].sort((a, b) => a.number - b.number);
    const objectId = props.objectId;
    return requestDetail(async () => {
      const [from, to] = await Promise.all(ordered.map((entry) => store.version('document', objectId, entry.id)));
      const comparison = await store.compare('document', objectId, from.id, to.id);
      return { from, to, comparison };
    }, ordered[1]);
  }

  function toggle(entry) {
    const existing = selected.value.some((row) => row.id === entry.id);
    if (!existing && selected.value.length === 2) return;
    selected.value = existing ? selected.value.filter((row) => row.id !== entry.id) : [...selected.value, entry];
    invalidateDetail();
    detailOpen.value = false;
    focusVersion.value = null;
  }

  function clearSelection() {
    selected.value = [];
    invalidateDetail();
    detailOpen.value = false;
    focusVersion.value = null;
  }

  function goToPage(value) {
    if (loading.value) return;
    const target = Math.max(1, Math.min(Number(value), result.value?.num_pages || page.value));
    if (target === page.value) return;
    page.value = target;
    load();
  }

  watch(order, () => { page.value = 1; load(); });
  watch(() => props.objectId, () => {
    page.value = 1;
    selected.value = [];
    invalidateDetail();
    detailOpen.value = false;
    focusVersion.value = null;
    load();
  }, { immediate: true });
  onBeforeUnmount(() => { listGeneration++; detailGeneration++; });

  const pagination = computed(() => ({
    currentPage: page.value, totalPages: result.value?.num_pages || 1,
    totalItems: result.value?.count || 0,
    rangeFrom: result.value?.count ? (page.value - 1) * 20 + 1 : 0,
    rangeTo: Math.min(page.value * 20, result.value?.count || 0),
  }));

  return { result, order, page, loading, listError, selected, active, detailOpen, busy, detailError, mode, focusVersion, pagination, load, consult, toggle, clearSelection, compareSelected, goToPage, retry: () => retryDetail?.() };
}
