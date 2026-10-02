import { computed, reactive, ref, watch } from 'vue';
import {
  availableProposalGroups,
  proposalGroupForSection,
  proposalSectionQuery,
  resolveProposalSection,
} from '~/utils/proposalNavigation';

export function useProposalNavigation({ query, status }) {
  const activeTab = ref(resolveProposalSection(query, status.value));
  let hasLoadedStatus = Boolean(status.value);
  const rememberedSections = reactive({});
  const groups = computed(() => availableProposalGroups(status.value));
  const visitedTabs = ref(new Set());
  const activeGroup = computed({
    get: () => proposalGroupForSection(activeTab.value)?.id || 'general',
    set: (id) => {
      const group = groups.value.find((entry) => entry.id === id);
      if (!group) return;
      const remembered = rememberedSections[id];
      activeTab.value = group.sections.some((section) => section.id === remembered)
        ? remembered : group.sections[0].id;
    },
  });
  const tabs = computed(() => groups.value.map(({ id, label }) => ({ id, label })));
  const subTabs = computed(() => groups.value.find((group) => group.id === activeGroup.value)?.sections || []);

  watch([activeTab, status], ([section, value]) => {
    if (!value || !groups.value.some((group) => group.sections.some((entry) => entry.id === section))) return;
    visitedTabs.value.add(section);
    rememberedSections[proposalGroupForSection(section)?.id || 'general'] = section;
  }, { immediate: true, flush: 'sync' });

  watch(status, (value) => {
    if (!value) return;
    if (!hasLoadedStatus) {
      hasLoadedStatus = true;
      activeTab.value = resolveProposalSection(query, value);
      return;
    }
    const group = groups.value.find((entry) => entry.id === activeGroup.value);
    if (!group?.sections.some((section) => section.id === activeTab.value)) {
      activeTab.value = group?.sections[0].id || 'general';
    }
  }, { immediate: true, flush: 'sync' });

  // Only replace the browser URL: a router navigation would rerun admin-auth.
  // Preserve unrelated query parameters and the fragment of shared links.
  watch([activeTab, status], () => {
    if (!status.value || typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    const destination = proposalSectionQuery(activeTab.value);
    for (const key of ['tab', 'section']) {
      if (destination[key]) url.searchParams.set(key, destination[key]);
      else url.searchParams.delete(key);
    }
    if (url.href !== window.location.href) window.history.replaceState(window.history.state, '', url);
  }, { immediate: true, flush: 'post' });

  return { activeTab, activeGroup, tabs, subTabs, visitedTabs };
}
