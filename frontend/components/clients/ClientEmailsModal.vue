<template>
  <BaseModal
    :model-value="open"
    kind="detail"
    full-height
    :close-on-esc="!previewOpen && !rowMenuOpen"
    :close-on-backdrop="!previewOpen && !rowMenuOpen"
    @update:model-value="emit('close')"
  >
    <div class="flex flex-col h-full" data-testid="client-emails-modal">
      <header class="px-5 py-4 border-b border-border-muted space-y-3">
        <div>
          <h2 class="text-lg font-bold text-text-default">Correos de {{ clientName }}</h2>
          <p class="text-sm text-text-muted mt-1">
            Todo lo que salió por este cliente, de lo más reciente a lo más viejo.
          </p>
        </div>

        <!-- The two groups the operator asked to keep visibly apart: what
             reached the client, and the internal notices about their records.
             Server-side because the list paginates — counting one loaded page
             would misreport the totals. -->
        <BaseSegmented
          :model-value="audience"
          :options="audienceOptions"
          data-testid="client-emails-audience"
          @update:model-value="selectAudience"
        />
      </header>

      <div class="flex-1 overflow-auto p-5 space-y-4">
        <p v-if="isLoading" class="text-sm text-text-subtle text-center py-10">
          Cargando los correos...
        </p>
        <p
          v-else-if="error"
          class="text-sm text-danger-strong text-center py-10"
          data-testid="client-emails-error"
        >
          {{ error }}
        </p>
        <template v-else>
          <EmailLogTable
            :entries="entries"
            :retrying-id="retryingId"
            nested
            @view-body="emit('view-body', $event)"
            @retry="retrySend"
            @menu-open-change="rowMenuOpen = $event"
          />
          <div v-if="numPages > 1" class="flex items-center justify-between text-sm">
            <BaseButton
              variant="secondary"
              size="sm"
              :disabled="page <= 1"
              disabled-reason="Ya estás en la primera página."
              data-testid="client-emails-prev"
              @click="goToPage(page - 1)"
            >
              Anterior
            </BaseButton>
            <span class="text-text-muted">Página {{ page }} de {{ numPages }}</span>
            <BaseButton
              variant="secondary"
              size="sm"
              :disabled="page >= numPages"
              disabled-reason="Ya estás en la última página."
              data-testid="client-emails-next"
              @click="goToPage(page + 1)"
            >
              Siguiente
            </BaseButton>
          </div>
        </template>
      </div>

      <footer class="px-5 py-3 border-t border-border-muted flex justify-end">
        <BaseButton variant="secondary" size="sm" @click="emit('close')">
          Cerrar
        </BaseButton>
      </footer>
    </div>
  </BaseModal>
</template>

<script setup>
/**
 * A client's email history: what we sent them and how it looked.
 *
 * Read-only except for the retry, exactly like the accounting Historial it
 * borrows its table from — no email is written or edited from here.
 *
 * The preview is not rendered inside this modal: BaseModal has no stacking
 * manager (every instance is fixed z-[9999]), so the page owns both and
 * paints the viewer after this one. While it is open this modal stops
 * answering Esc and backdrop clicks, since BaseModal's keydown listener is
 * global and both would otherwise close at once.
 */
import { computed, ref, watch } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import EmailLogTable from '~/components/accounting/EmailLogTable.vue';
import { useProposalClientsStore } from '~/stores/proposal_clients';
import { usePanelNotify } from '~/composables/usePanelNotify';

const props = defineProps({
  open: { type: Boolean, default: false },
  client: { type: Object, default: null },
  /** True while the page shows the body preview above this modal. */
  previewOpen: { type: Boolean, default: false },
});

const emit = defineEmits(['close', 'view-body']);

const store = useProposalClientsStore();
const notify = usePanelNotify();

const entries = ref([]);
const isLoading = ref(false);
const error = ref('');
const page = ref(1);
const numPages = ref(1);
const counts = ref({ client: 0, internal: 0 });
const audience = ref('client');
const retryingId = ref(null);
// A row's actions menu opens above this modal; like the preview, it must be
// the only dialog answering Esc and backdrop clicks while it is open.
const rowMenuOpen = ref(false);

const clientName = computed(() => props.client?.name || 'este cliente');

const audienceOptions = computed(() => [
  { value: 'client', label: `Al cliente (${counts.value.client})` },
  { value: 'internal', label: `Internos (${counts.value.internal})` },
]);

async function load() {
  if (!props.client?.id) return;
  isLoading.value = true;
  error.value = '';
  const result = await store.fetchClientEmails(props.client.id, {
    audience: audience.value,
    page: page.value,
  });
  if (result.success) {
    entries.value = result.data.results || [];
    numPages.value = result.data.num_pages || 1;
    counts.value = { ...counts.value, [audience.value]: result.data.count || 0 };
  } else {
    entries.value = [];
    error.value = result.message || 'No se pudieron cargar los correos.';
  }
  isLoading.value = false;
}

/** Both totals, so the segmented labels are right before either tab is opened. */
async function loadCounts() {
  if (!props.client?.id) return;
  const [toClient, internal] = await Promise.all([
    store.fetchClientEmails(props.client.id, { audience: 'client' }),
    store.fetchClientEmails(props.client.id, { audience: 'internal' }),
  ]);
  counts.value = {
    client: toClient.success ? toClient.data.count || 0 : 0,
    internal: internal.success ? internal.data.count || 0 : 0,
  };
}

function selectAudience(value) {
  if (value === audience.value) return;
  audience.value = value;
  page.value = 1;
  load();
}

function goToPage(next) {
  if (next < 1 || next > numPages.value) return;
  page.value = next;
  load();
}

async function retrySend(entry) {
  if (retryingId.value) return;
  retryingId.value = entry.id;
  const result = await store.retryClientEmail(props.client.id, entry.id);
  retryingId.value = null;
  if (result.success) {
    notify.success({
      title: 'Reenviado',
      detail: `Salió de nuevo a ${entry.recipient}.`,
    });
    // The retry is a new row and it lands first: reload rather than patch, so
    // the list and its counts tell the same story.
    page.value = 1;
    await Promise.all([load(), loadCounts()]);
  } else {
    notify.error({ title: result.message || 'No se pudo reenviar el correo.' });
  }
}

watch(
  () => [props.open, props.client?.id],
  ([isOpen, id]) => {
    if (!isOpen || !id) return;
    audience.value = 'client';
    page.value = 1;
    load();
    loadCounts();
  },
  { immediate: true },
);

defineExpose({ load });
</script>
