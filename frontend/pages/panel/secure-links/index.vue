<template>
  <div data-testid="secure-links-page">
    <div class="mb-6 flex flex-col items-start gap-3 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
      <div class="min-w-0">
        <h1 class="text-2xl font-light text-text-default">Enlaces seguros</h1>
        <p class="mt-1 text-sm text-text-subtle">
          Enlaces de un solo uso para compartir contraseñas, llaves y datos confidenciales. El contenido queda guardado y cifrado; el enlace se puede reactivar.
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <BaseButton variant="secondary" size="sm" data-testid="secure-links-copy-public" @click="copyPublicUrl">
          <BaseActionIcon action="copy" />
          {{ publicFeedback.label || 'Enlace para clientes' }}
        </BaseButton>
        <BaseButton variant="primary" size="sm" data-testid="secure-links-new" @click="openCreate">
          Nuevo enlace
        </BaseButton>
      </div>
    </div>

    <div class="mb-4 flex flex-col gap-3 panel-landscape:flex-row panel-landscape:items-center panel-landscape:justify-between">
      <BaseSegmented
        v-model="filters.tab"
        :options="tabOptions"
        size="sm"
        :nowrap="false"
        data-testid="secure-links-tabs"
      />
      <BaseInput
        v-model="filters.search"
        class="w-full panel-landscape:w-72"
        placeholder="Buscar por título, cliente o proyecto"
        data-testid="secure-links-search"
      />
    </div>

    <BaseAlert v-if="store.error" variant="danger" class="mb-4">
      No se pudieron cargar los enlaces.
      <BaseButton variant="link" size="sm" @click="load">Reintentar</BaseButton>
    </BaseAlert>

    <div v-if="store.isLoading && store.links.length === 0" class="py-16 text-center text-sm text-text-subtle">
      Cargando enlaces...
    </div>

    <BaseEmptyState
      v-else-if="store.links.length === 0"
      title="Sin enlaces en esta vista"
      description="Crea un enlace seguro o comparte con tus clientes la página pública para que te envíen información sensible."
    />

    <BaseExploratoryList
      v-else
      :columns="columns"
      :rows="store.links"
      caption="Enlaces seguros de un solo uso"
      card-test-id-prefix="secure-link-row"
      table-min-width="60rem"
      interactive-rows
      @row-click="(row) => openDetail(row.id)"
    >
      <template #cell-title="{ row }">
        <span class="font-medium text-text-default [overflow-wrap:anywhere]">{{ row.title }}</span>
        <span class="block text-xs text-text-subtle">{{ row.type_label }}</span>
      </template>
      <template #cell-association="{ row }">
        <span class="[overflow-wrap:anywhere]">{{ [row.client_name, row.project_name].filter(Boolean).join(' · ') || '—' }}</span>
      </template>
      <template #cell-origin="{ row }">
        {{ row.team_only ? `Cliente: ${row.creator_name || 'sin nombre'}` : row.origin_label }}
      </template>
      <template #cell-status="{ row }">
        <SecureLinkStatusBadge :status="row.status" />
      </template>
      <template #cell-expires_at="{ row }">{{ formatDateTime(row.expires_at) }}</template>
      <template #cell-consumed_at="{ row }">{{ row.consumed_at ? formatDateTime(row.consumed_at) : '—' }}</template>
      <template #row-actions="{ row }">
        <BaseActionMenu :items="actionItems(row)" :testid="`secure-link-actions-${row.id}`" />
      </template>
    </BaseExploratoryList>

    <div v-if="store.count > store.pageSize" class="mt-4 flex items-center justify-end gap-2 text-sm text-text-muted">
      <BaseButton variant="ghost" size="sm" :disabled="filters.page <= 1" disabled-reason="Ya estás en la primera página" @click="filters.page -= 1">Anterior</BaseButton>
      <span>Página {{ filters.page }} de {{ totalPages }}</span>
      <BaseButton variant="ghost" size="sm" :disabled="filters.page >= totalPages" disabled-reason="Ya estás en la última página" @click="filters.page += 1">Siguiente</BaseButton>
    </div>

    <SecureLinkFormModal
      v-model="formModal.open"
      :link="formModal.link"
      :initial-fields="formModal.fields"
      @saved="onSaved"
    />

    <SecureLinkDetailModal
      v-model="detailModal.open"
      :link-id="detailModal.id"
      @edit="openEdit"
      @changed="load"
    />

    <BaseModal v-model="createdModal.open" kind="form" padding="md" :close-on-backdrop="false">
      <div class="space-y-4 px-6 py-5" data-testid="secure-link-created">
        <h3 class="text-lg font-bold text-text-default">Enlace listo para enviar</h3>
        <p class="text-sm text-text-muted">
          Se abre una sola vez y vence el {{ formatDateTime(createdModal.expiresAt) }}. Puedes volver a copiarlo desde el detalle del enlace.
        </p>
        <code class="block break-all rounded bg-surface-muted p-3 text-xs" data-testid="secure-link-created-url">{{ createdModal.url }}</code>
        <div class="flex flex-col-reverse items-stretch gap-2 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-end">
          <BaseButton variant="secondary" size="sm" data-testid="secure-link-copy-message" @click="copyCreated('message')">
            <BaseActionIcon action="copy" />
            {{ createdFeedback('message').label || 'Copiar mensaje sugerido' }}
          </BaseButton>
          <BaseButton variant="secondary" size="sm" data-testid="secure-link-copy-created" @click="copyCreated('url')">
            <BaseActionIcon action="copy" />
            {{ createdFeedback('url').label || 'Copiar enlace' }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" data-testid="secure-link-created-close" @click="createdModal.open = false">Listo</BaseButton>
        </div>
      </div>
    </BaseModal>

    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, watch } from 'vue';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import BaseActionMenu from '~/components/base/BaseActionMenu.vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import SecureLinkDetailModal from '~/components/secureLinks/SecureLinkDetailModal.vue';
import SecureLinkFormModal from '~/components/secureLinks/SecureLinkFormModal.vue';
import SecureLinkStatusBadge from '~/components/secureLinks/SecureLinkStatusBadge.vue';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useSecureLinksStore } from '~/stores/secure_links';
import { formatDateTime } from '~/utils/formatDate';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const store = useSecureLinksStore();
const route = useRoute();
const router = useRouter();
const notify = usePanelNotify();
const clipboard = useClipboardFeedback();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();

const filters = reactive({ tab: 'all', search: '', page: 1 });
const formModal = reactive({ open: false, link: null, fields: null });
const detailModal = reactive({ open: false, id: null });
const createdModal = reactive({ open: false, url: '', expiresAt: null });

const columns = [
  { key: 'title', label: 'Enlace', mobile: 'primary' },
  { key: 'association', label: 'Cliente / proyecto', mobile: 'secondary' },
  { key: 'origin', label: 'Origen', mobile: 'meta' },
  { key: 'status', label: 'Estado', mobile: 'secondary' },
  { key: 'expires_at', label: 'Vence', mobile: 'meta' },
  { key: 'consumed_at', label: 'Abierto', mobile: 'meta' },
];

const TABS = [
  ['all', 'Todos'], ['active', 'Activos'], ['consumed', 'Usados'],
  ['expired', 'Vencidos'], ['revoked', 'Revocados'],
];
const tabOptions = computed(() => [
  ...TABS.map(([value, label]) => ({ value, label: `${label} (${store.counts[value] ?? 0})` })),
  { value: 'received', label: `Recibidos · ${store.unopenedReceived} sin abrir` },
]);
const totalPages = computed(() => Math.max(1, Math.ceil(store.count / store.pageSize)));
const publicFeedback = computed(() => clipboard.feedbackFor('secure-links-public'));

function currentFilters() {
  const tab = filters.tab;
  return {
    status: ['all', 'received'].includes(tab) ? '' : tab,
    received: tab === 'received' ? 'true' : '',
    search: filters.search.trim(),
    page: filters.page,
  };
}

let searchTimer = null;
async function load() {
  const result = await store.fetchLinks(currentFilters());
  if (!result.success && result.error) notify.error({ title: result.error.message });
}

watch(() => [filters.tab, filters.page], load);
watch(() => filters.tab, () => { filters.page = 1; });
watch(() => filters.search, () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    filters.page = 1;
    load();
  }, 300);
});

watch(() => route.query.link, (value) => {
  const id = Number(value);
  if (id) {
    detailModal.id = id;
    detailModal.open = true;
  }
}, { immediate: true });

watch(() => detailModal.open, (open) => {
  if (!open && route.query.link) router.replace({ query: { ...route.query, link: undefined } });
});

onMounted(() => {
  store.fetchTypes();
  load();
});

function actionItems(row) {
  return [
    { action: 'view', label: 'Ver detalle', testid: `secure-link-open-${row.id}`, onClick: () => openDetail(row.id) },
    { action: 'copy', label: 'Copiar enlace', testid: `secure-link-copy-${row.id}`, onClick: () => copyRowUrl(row) },
    ...(row.status === 'active'
      ? [{ action: 'deactivate', label: 'Revocar', testid: `secure-link-revoke-${row.id}`, onClick: () => revoke(row) }]
      : [{ action: 'activate', label: 'Reactivar', testid: `secure-link-reactivate-${row.id}`, onClick: () => openDetail(row.id) }]),
    { divider: true },
    { action: 'delete', label: 'Eliminar', danger: true, testid: `secure-link-delete-${row.id}`, onClick: () => remove(row) },
  ];
}

function openCreate() {
  formModal.link = null;
  formModal.fields = null;
  formModal.open = true;
}

function openEdit({ link, fields }) {
  detailModal.open = false;
  formModal.link = link;
  formModal.fields = fields;
  formModal.open = true;
}

function openDetail(id) {
  detailModal.id = id;
  detailModal.open = true;
}

function onSaved(data) {
  formModal.fields = null;
  if (data?.url) {
    createdModal.url = data.url;
    createdModal.expiresAt = data.expires_at;
    createdModal.open = true;
  }
  load();
}

async function copyTo(key, text, successLabel) {
  await clipboard.copyText({
    key,
    text,
    successLabel,
    errorLabel: 'No se pudo copiar',
    onError: () => notify.error({ title: 'No se pudo copiar', detail: 'Selecciónalo y cópialo manualmente.' }),
  });
}

function copyPublicUrl() {
  return copyTo('secure-links-public', store.publicCreateUrl, 'Copiado: página para clientes');
}

async function copyRowUrl(row) {
  const result = await store.fetchLinkUrl(row.id);
  if (!result.success) {
    notify.error({ title: result.error.message });
    return;
  }
  await copyTo(`secure-link-row-${row.id}`, result.url, 'Enlace copiado');
  notify.success({ title: 'Enlace copiado' });
}

function createdFeedback(kind) {
  return clipboard.feedbackFor(`secure-link-created-${kind}`);
}

function copyCreated(kind) {
  const text = kind === 'url'
    ? createdModal.url
    : `Te compartimos la información por un enlace seguro de un solo uso: ${createdModal.url}\n`
      + `Sólo se puede abrir una vez y vence el ${formatDateTime(createdModal.expiresAt)}. `
      + 'Copia la información apenas la abras; si lo abres por error, avísanos y lo reactivamos.';
  return copyTo(`secure-link-created-${kind}`, text, kind === 'url' ? 'Enlace copiado' : 'Mensaje copiado');
}

async function revoke(row) {
  const result = await store.revokeLink(row.id);
  if (!result.success) notify.error({ title: result.error.message });
  else load();
}

async function remove(row) {
  const confirmed = await requestConfirm({
    title: 'Eliminar enlace seguro',
    message: `"${row.title}" y su contenido cifrado se eliminarán de forma permanente. El enlace dejará de funcionar. Esta acción no se puede deshacer.`,
    confirmText: 'Eliminar',
    variant: 'danger',
  });
  if (!confirmed) return;
  const result = await store.deleteLink(row.id);
  if (!result.success) notify.error({ title: result.error.message });
  else load();
}
</script>
