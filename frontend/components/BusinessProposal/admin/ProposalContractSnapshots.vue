<script setup>
import { ref } from 'vue';
import { useProposalStore } from '~/stores/proposals';
import ProposalContractChangeModal from './ProposalContractChangeModal.vue';
import DocumentMarkdownBody from '~/components/panel/documents/DocumentMarkdownBody.vue';
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';

const props = defineProps({ proposal: { type: Object, required: true } });
const emit = defineEmits(['refresh']);
const store = useProposalStore();
const rows = ref([]);
const total = ref(0);
const loading = ref(false);
const opened = ref(false);
const error = ref('');
const selected = ref(null);
const restoring = ref(null);

async function load(more = false) {
  if (loading.value) return;
  loading.value = true;
  error.value = '';
  try {
    const data = await store.fetchContractSnapshots(props.proposal.id, more ? rows.value.length : 0);
    rows.value = more ? [...rows.value, ...data.snapshots] : data.snapshots;
    total.value = data.total;
    opened.value = true;
  } catch { error.value = 'No se pudieron cargar las instantáneas. Intenta de nuevo.'; }
  finally { loading.value = false; }
}
async function read(row) {
  if (loading.value) return;
  loading.value = true;
  error.value = '';
  try { selected.value = await store.fetchContractSnapshot(props.proposal.id, row.snapshot_id); }
  catch { error.value = 'No se pudo leer la instantánea. Intenta de nuevo.'; }
  finally { loading.value = false; }
}
function restored() {
  restoring.value = null;
  selected.value = null;
  emit('refresh');
  load();
}
</script>

<template>
  <section class="mt-6 space-y-4 rounded-xl border border-border-muted p-4" data-testid="contract-snapshots">
    <h3 class="font-semibold text-text-default">Instantáneas de contratos</h3>
    <p class="text-sm text-text-muted">Copias permanentes del contenido anterior a cada cambio. Restaurar conserva primero los contratos actuales.</p>
    <BaseButton variant="secondary" :disabled="loading" disabled-reason="Cargando instantáneas…" data-testid="contract-snapshots-load" @click="load()">{{ opened ? 'Actualizar instantáneas' : 'Ver instantáneas' }}</BaseButton>
    <p v-if="error" class="text-sm text-danger-strong" role="alert">{{ error }}</p>
    <p v-if="opened && !rows.length" class="text-sm text-text-muted">Todavía no hay instantáneas de contratos.</p>
    <ul v-if="opened" class="space-y-3">
      <li v-for="row in rows" :key="row.snapshot_id" class="flex flex-wrap items-start justify-between gap-3 border-b border-border-muted pb-3">
        <div class="min-w-0 text-sm text-text-default">
          <p>{{ row.from_modality === 'split' ? 'Producto y servicio' : 'Contrato único' }} → {{ row.to_modality === 'split' ? 'Producto y servicio' : 'Contrato único' }}</p>
          <p>{{ row.actor }} · {{ new Date(row.created_at).toLocaleString('es-CO') }}</p>
          <p class="break-words">{{ row.change_note }}</p>
        </div>
        <div class="flex gap-2">
          <BaseButton variant="secondary" size="sm" :disabled="loading" disabled-reason="Cargando instantánea…" :data-testid="`contract-snapshot-read-${row.snapshot_id}`" @click="read(row)">Consultar</BaseButton>
          <BaseButton variant="secondary" size="sm" :data-testid="`contract-snapshot-restore-${row.snapshot_id}`" @click="restoring = row.snapshot_id">Restaurar</BaseButton>
        </div>
      </li>
    </ul>
    <BaseButton v-if="rows.length < total" variant="secondary" :disabled="loading" disabled-reason="Cargando instantáneas…" @click="load(true)">Ver más</BaseButton>
    <BaseModal v-if="selected" :model-value="true" kind="detail" @close="selected = null">
      <div class="space-y-4 p-5">
        <h2 class="text-lg font-semibold text-text-default">Instantánea de contratos {{ selected.snapshot_id }}</h2>
        <div v-for="doc in selected.payload.documents" :key="doc.document_id" class="space-y-2">
          <h3 class="font-semibold text-text-default">{{ doc.title }} · {{ doc.source === 'custom' ? 'Personalizado' : 'Plantilla' }}</h3>
          <PanelDownloadLink :url="`/api/proposals/${proposal.id}/contract/snapshots/${selected.snapshot_id}/files/${doc.document_id}/`" filename="contrato-anterior.pdf" />
          <DocumentMarkdownBody :markdown="doc.markdown" />
        </div>
      </div>
    </BaseModal>
    <ProposalContractChangeModal v-if="restoring" :proposal="proposal" :snapshot-id="restoring" @close="restoring = null" @changed="restored" />
  </section>
</template>
