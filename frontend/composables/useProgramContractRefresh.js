import { onBeforeUnmount, onMounted } from 'vue';

/** Refresh saved contract data when returning from its document editor. */
export function useProgramContractRefresh(store, activeSection) {
  let pending = null;
  const refresh = () => {
    if (pending) return pending;
    pending = (async () => {
      await store.fetchContract();
      if (!store.contractUnavailable) await store.fetchVersions('contract');
    })().finally(() => { pending = null; });
    return pending;
  };
  const onFocus = () => {
    if (activeSection.value === 'contract') void refresh();
  };
  onMounted(() => window.addEventListener('focus', onFocus));
  onBeforeUnmount(() => window.removeEventListener('focus', onFocus));
  return refresh;
}
