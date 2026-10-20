<script setup>
import { ref, watch, computed } from 'vue';
import { get_request } from '~/stores/services/request_http';
import ProposalApprovalModal from '~/components/BusinessProposal/admin/ProposalApprovalModal.vue';
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
const props = defineProps({ refreshKey: { type: [String, Number], default: '' }, proposalId: { type: [Number, String], required: true } });
const localePath = useLocalePath();
const { locale } = useI18n();
const data = ref(null);
const error = ref('');
const revisionOpen = ref(false);
const en = computed(() => locale.value.startsWith('en'));
const pending = computed(() => data.value?.shared_documents?.some(item => item.has_pending_changes));
let generation = 0;
async function load() {
  const ticket = ++generation;
  error.value = '';
  try {
    const result = await get_request(`proposals/${props.proposalId}/approval/`);
    if (ticket === generation) data.value = result.data;
  }
  catch { if (ticket !== generation) return; error.value = en.value ? 'Could not load the approved documents.' : 'No se pudieron cargar los documentos aprobados.'; }
}
watch(() => [props.proposalId, props.refreshKey], (value, old) => {
  if (value[0] !== old?.[0]) data.value = null;
  load();
}, { immediate: true });
</script>

<template>
  <section v-if="data?.package_number || error" class="mb-5 space-y-3 rounded-xl border border-border-default bg-surface p-4" data-testid="proposal-shared-documents">
    <h3 class="font-semibold text-text-default">{{ en ? 'Shared approved documents' : 'Documentos aprobados compartidos' }}</h3>
    <p v-if="error" role="alert" class="text-sm text-danger-strong">{{ error }}</p>
    <template v-if="data?.package_number">
      <p class="text-sm text-text-muted">{{ en ? 'Current package' : 'Paquete vigente' }} {{ data.package_number }} · {{ pending ? (en ? 'Pending draft' : 'Borrador pendiente') : (en ? 'Up to date' : 'Al día') }}</p>
      <p class="text-sm text-text-muted">{{ en ? 'Approved downloads stay unchanged until you confirm a new package.' : 'Las descargas aprobadas se conservan hasta confirmar un nuevo paquete.' }}</p>
      <ul class="space-y-3">
        <li v-for="item in data.shared_documents" :key="item.document_id" class="space-y-1 break-words">
          <NuxtLink :to="localePath(`/panel/documents/${item.document_id}/edit`)" class="text-sm text-text-brand underline">{{ data.confirmed_files.find(file => file.id === item.current_file_id)?.title || item.source_key }}</NuxtLink>
          <span v-if="!item.is_current" class="ml-2 text-xs text-text-muted">{{ en ? 'Historical' : 'Histórico' }}</span>
          <details class="text-sm text-text-default">
            <summary class="cursor-pointer">{{ en ? 'Revisions' : 'Revisiones' }}</summary>
            <ul class="space-y-2 pt-2"><li v-for="revision in item.history" :key="revision.id"><PanelDownloadLink :url="revision.download_url" :filename="revision.filename" :label="`${revision.title} · v${revision.package_number}`" expected-type="" /></li></ul>
          </details>
        </li>
      </ul>
      <BaseButton type="button" variant="primary" size="sm" data-testid="proposal-revision-open" @click="revisionOpen = true">{{ en ? 'Review new package' : 'Revisar nuevo paquete' }}</BaseButton>
      <ProposalApprovalModal :visible="revisionOpen" :proposal="{ id: proposalId }" :accept-proposal="false" revision @close="revisionOpen = false" @completed="load" />
    </template>
  </section>
</template>
