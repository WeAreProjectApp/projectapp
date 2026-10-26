<template>
  <div data-testid="secure-links-page">
    <div class="mb-6 flex flex-col items-start gap-3 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between" data-testid="secure-links-header">
      <div class="min-w-0">
        <h1 class="text-2xl font-light text-text-default">Enlaces seguros</h1>
        <p class="mt-1 text-sm text-text-subtle" data-testid="secure-links-description">
          Enlaces de un solo uso para compartir contraseñas, llaves y datos confidenciales. El contenido queda guardado y cifrado; el enlace se puede reactivar.
        </p>
      </div>
      <div class="flex shrink-0 flex-wrap gap-2">
        <BaseTooltip
          :text="publicFeedback.label"
          :disabled="!publicFeedback.label"
          :force-open="Boolean(publicFeedback.label)"
          :toggle-on-click="false"
          :background-color="publicFeedback.tone === 'success' ? 'bg-success-soft' : 'bg-danger-soft'"
          :textColor="publicFeedback.tone === 'success' ? 'text-success-strong' : 'text-danger-strong'"
          root-class="inline-flex min-w-0"
          trigger-class=""
          width="w-max max-w-xs"
          min-width="min-w-0"
          floating
        >
          <template #trigger="{ tooltipId }">
            <BaseButton
              variant="secondary"
              size="sm"
              :aria-describedby="publicFeedback.label ? tooltipId : undefined"
              :data-displayed-action="publicCopyAction"
              data-testid="secure-links-copy-public"
              @click="copyPublicUrl"
            >
              <BaseActionIcon :action="publicCopyAction" />
              {{ t('secureLinks.panel.publicLink') }}
            </BaseButton>
          </template>
        </BaseTooltip>
        <span class="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="secure-links-copy-status">{{ publicFeedback.label }}</span>
        <BaseButton variant="primary" size="sm" data-testid="secure-links-new" @click="openCreate">
          Nuevo enlace
        </BaseButton>
      </div>
    </div>

    <div class="flex min-w-0 flex-col gap-4 panel-landscape:flex-row">
      <BaseButton class="panel-landscape:hidden" variant="secondary" data-testid="secure-folders-open" @click="folderDrawerOpen = true"><BaseActionIcon action="folders" />Carpetas</BaseButton>
      <div class="hidden w-64 shrink-0 panel-landscape:block" data-testid="secure-folders-sidebar">
        <FolderSidebar v-bind="sidebarProps" v-on="sidebarEvents" />
      </div>
      <BaseDrawer v-model="folderDrawerOpen" title="Carpetas de enlaces seguros">
        <FolderSidebar v-bind="sidebarProps" touch-mode v-on="sidebarEvents" />
      </BaseDrawer>
      <section class="min-w-0 flex-1" aria-label="Contenido de enlaces seguros">
        <FolderBreadcrumb :adapter="folders" :active-id="selectedFolderId" root-label="Todos los enlaces" @select="selectFolder" />
        <div class="mb-4 flex flex-wrap gap-2">
          <BaseButton variant="secondary" size="sm" data-testid="secure-folder-create" :disabled="Boolean(currentFolder?.is_archived || currentFolder?.is_read_only)" disabled-reason="Restaura primero la carpeta" @click="openFolderForm()"><BaseActionIcon action="create" />Nueva carpeta</BaseButton>
          <BaseButton v-if="currentFolder && !currentFolder.managed_project && !currentFolder.is_read_only" variant="secondary" size="sm" data-testid="secure-folder-edit" @click="openFolderForm(currentFolder)"><BaseActionIcon action="edit" />Editar carpeta</BaseButton>
          <BaseButton v-if="currentFolder && !currentFolder.managed_project && !currentFolder.is_read_only" variant="secondary" size="sm" data-testid="secure-folder-move" @click="openFolderForm(currentFolder, true)"><BaseActionIcon action="move" />Mover carpeta</BaseButton>
          <BaseButton v-if="currentFolder && !currentFolder.managed_project && !currentFolder.is_read_only" variant="secondary" size="sm" data-testid="secure-folder-archive" @click="archiveFolder(currentFolder)"><BaseActionIcon :action="currentFolder.is_archived ? 'restore' : 'archive'" />{{ currentFolder.is_archived ? 'Restaurar carpeta' : 'Archivar carpeta' }}</BaseButton>
          <BaseButton v-if="currentFolder && !currentFolder.managed_project && !currentFolder.is_read_only" variant="danger-ghost" size="sm" :disabled="folders.totalContentCount(currentFolder) > 0" disabled-reason="Mueve antes los enlaces y subcarpetas, incluidos los archivados" data-testid="secure-folder-delete" @click="deleteFolder(currentFolder)"><BaseActionIcon action="delete" />Eliminar carpeta</BaseButton>
        </div>
        <div v-if="childFolders.length" class="mb-4 flex flex-wrap gap-2" data-testid="secure-folder-children">
          <div v-for="folder in childFolders" :key="folder.id" class="flex items-center gap-1">
            <BaseButton variant="secondary" size="sm" :data-testid="`secure-folder-child-${folder.id}`" @click="selectFolder(folder.id)"><BaseActionIcon action="folders" />{{ folder.name }} · {{ folders.recursiveDocumentCount(folder, filters.archive) }}</BaseButton>
            <BaseActionButton action="move-up" :label="`Subir carpeta ${folder.name}`" :disabled="childFolders[0]?.id === folder.id || folders.isUpdating" disabled-reason="La carpeta ya está primera o se está guardando el orden" @click="reorderFolder(folder)" />
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
      row-actions-layout="menu-start"
      interactive-rows
      @row-click="(row, event) => openRow(detailHref(row.id), event)"
      @row-auxclick="(row, event) => openRow(detailHref(row.id), event)"
    >
      <template #cell-title="{ row }">
        <BaseRowLink :to="detailHref(row.id)" class="font-medium text-text-default [overflow-wrap:anywhere]">{{ row.title }}</BaseRowLink>
        <span class="block text-xs text-text-subtle">{{ row.type_label }}</span>
        <span class="block text-xs text-text-subtle" :data-testid="`secure-link-location-${row.id}`">{{ folderPathLabel(folders.folders, row.folder) || 'Sin carpeta' }}</span>
      </template>
      <template #cell-association="{ row }">
        <span class="[overflow-wrap:anywhere]">{{ [row.client_name, row.project_name].filter(Boolean).join(' · ') || '—' }}</span>
      </template>
      <template #cell-origin="{ row }">
        {{ row.team_only ? `Cliente: ${row.creator_name || 'sin nombre'}` : row.origin_label }}
      </template>
      <template #cell-status="{ row }">
        <SecureLinkStatusBadge :status="row.lifecycle_status || row.status" :team-only="row.team_only" />
      </template>
      <template #cell-expires_at="{ row }">{{ formatDateTime(row.expires_at) }}</template>
      <template #cell-consumed_at="{ row }">{{ row.consumed_at ? formatDateTime(row.consumed_at) : '—' }}</template>
      <template #row-actions="{ row }">
        <BaseActionButton
          action="more"
          class="h-11 w-11 shrink-0"
          :label="`Acciones de ${row.title}`"
          :loading="openingContentId === row.id"
          :data-testid="`secure-link-actions-${row.id}`"
          @click.stop="actionsRow = row"
        />
      </template>
    </BaseExploratoryList>

    <BaseRowActionsModal
      :open="actionsRow !== null"
      :title="actionsRow?.title || ''"
      :subtitle="actionsRow?.type_label || ''"
      :items="actionsRow ? actionItems(actionsRow) : []"
      testid="secure-link-actions-modal"
      @close="actionsRow = null"
    />

    <div v-if="store.count > store.pageSize" class="mt-4 flex items-center justify-end gap-2 text-sm text-text-muted">
      <BaseButton variant="ghost" size="sm" :disabled="filters.page <= 1" disabled-reason="Ya estás en la primera página" @click="filters.page -= 1">Anterior</BaseButton>
      <span>Página {{ filters.page }} de {{ totalPages }}</span>
      <BaseButton variant="ghost" size="sm" :disabled="filters.page >= totalPages" disabled-reason="Ya estás en la última página" @click="filters.page += 1">Siguiente</BaseButton>
    </div>

      </section>
    </div>
    <SecureLinkFolderManager :open="folderForm.open" :folder="folderForm.folder" :parent-id="numericFolderId" :move-link="folderForm.link" :move-folder="folderForm.moving" :busy="store.isUpdating" @close="folderForm.open = false" @saved="folderSaved" @move-link="moveLink" />
    <SecureLinkFormModal
      v-model="formModal.open"
      :link="formModal.link"
      :initial-fields="formModal.fields"
      :folder="creationFolder"
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
      </div>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="secondary" size="sm" data-testid="secure-link-copy-message" @click="copyCreated('message')">
            <BaseActionIcon action="copy" />
            {{ createdFeedback('message').label || 'Copiar mensaje sugerido' }}
          </BaseButton>
          <BaseButton variant="secondary" size="sm" data-testid="secure-link-copy-created" @click="copyCreated('url')">
            <BaseActionIcon action="copy" />
            {{ createdFeedback('url').label || 'Copiar enlace' }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" data-testid="secure-link-created-close" @click="createdModal.open = false">Listo</BaseButton>
        </BaseModalActions>
      </template>
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
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import FolderSidebar from '~/components/panel/FolderSidebar.vue';
import FolderBreadcrumb from '~/components/panel/FolderBreadcrumb.vue';
import SecureLinkFolderManager from '~/components/secureLinks/SecureLinkFolderManager.vue';
import { useSecureLinkFoldersStore } from '~/stores/secure_link_folders';
import { folderPathLabel } from '~/utils/folderOptions';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseRowActionsModal from '~/components/base/BaseRowActionsModal.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseTooltip from '~/components/base/BaseTooltip.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import SecureLinkDetailModal from '~/components/secureLinks/SecureLinkDetailModal.vue';
import SecureLinkFormModal from '~/components/secureLinks/SecureLinkFormModal.vue';
import SecureLinkStatusBadge from '~/components/secureLinks/SecureLinkStatusBadge.vue';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useRowNavigation } from '~/composables/useRowNavigation';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { contentFieldValues } from '~/composables/useSecureLinkForm';
import { useSecureLinksStore } from '~/stores/secure_links';
import { formatDateTime } from '~/utils/formatDate';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const store = useSecureLinksStore();
const folders = useSecureLinkFoldersStore();
const folderDrawerOpen = ref(false);
const showInactive = ref(false);
const folderForm = reactive({ open: false, folder: null, link: null, moving: false });
const route = useRoute();
const router = useRouter();
const { openRow } = useRowNavigation();
const detailHref = id => router.resolve({ path: route.path, query: { ...route.query, link: id } }).href;
const notify = usePanelNotify();
const clipboard = useClipboardFeedback();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();

const { t } = useI18n();
const readFilters = query => ({
  tab: ['all', 'received', 'ready', 'sent', 'opened', 'expired', 'revoked'].includes(query.tab) ? query.tab : 'all',
  search: typeof query.search === 'string' ? query.search : '', page: Math.max(1, Number(query.page) || 1),
  folder: /^\d+$/.test(String(query.folder)) || query.folder === 'none' ? String(query.folder) : 'all',
  mode: query.mode === 'client' ? 'client' : 'project', entity: /^\d+$/.test(String(query.entity)) || query.entity === 'none' ? String(query.entity) : 'all',
  archive: ['active', 'archived', 'all'].includes(query.archive) ? query.archive : 'active',
});
const filters = reactive(readFilters(route.query));
const selectedFolderId = computed(() => /^\d+$/.test(filters.folder) ? Number(filters.folder) : filters.folder);
const numericFolderId = computed(() => typeof selectedFolderId.value === 'number' ? selectedFolderId.value : null);
const currentFolder = computed(() => folders.folderById(numericFolderId.value));
const creationFolder = computed(() => filters.folder === 'all' ? undefined : currentFolder.value || null);
const childFolders = computed(() => folders.folders.filter(f => filters.folder !== 'none' && f.parent === numericFolderId.value && !f.managed_project && (filters.archive === 'all' || (filters.archive === 'active' ? !f.is_archived : f.is_archived || folders.archivedContentCount(f) > 0))));
const sidebarProps = computed(() => ({
  adapter: folders, testIdPrefix: 'secure-links', unassignedManualOnly: false, itemLabel: 'enlaces', itemShortLabel: 'enlaces', storageKey: 'projectapp-secure-links-sidebar-sections',
  folders: folders.folders, activeId: selectedFolderId.value, archiveScope: filters.archive,
  navigationMode: filters.mode, navigationSelection: ['all', 'none'].includes(filters.entity) ? filters.entity : Number(filters.entity), navigationFacets: folders.navigationFacets,
  navigationLoading: folders.isLoading, navigationError: folders.error, showInactiveProjects: showInactive.value,
  archivedCount: folders.navigation.totals?.archived?.documents || 0,
  unfiledCount: filters.archive === 'all' ? (folders.navigation.unfiled?.active?.documents || 0) + (folders.navigation.unfiled?.archived?.documents || 0) : folders.navigation.unfiled?.[filters.archive]?.documents || 0,
}));
const sidebarEvents = {
  select: selectFolder, manage: () => openFolderForm(), edit: f => openFolderForm(f), delete: deleteFolder, archive: archiveFolder,
  'update:navigation-mode': mode => { filters.mode = mode; filters.entity = 'all'; filters.folder = 'all'; filters.page = 1; },
  'select-entity': id => { filters.entity = String(id); filters.folder = filters.mode === 'project' ? String(folders.navigation.projects.find(p => p.id === Number(id))?.managed_root_id || 'all') : 'all'; filters.page = 1; folderDrawerOpen.value = false; },
  'toggle-inactive-projects': value => { showInactive.value = value; },
  'toggle-archived': () => { filters.archive = filters.archive === 'archived' ? 'active' : 'archived'; filters.page = 1; },
  'view-archived': () => { filters.archive = 'archived'; }, 'retry-navigation': () => folders.fetchFolders(),
};
const formModal = reactive({ open: false, link: null, fields: null });
const detailModal = reactive({ open: false, id: null });
const createdModal = reactive({ open: false, url: '', expiresAt: null });
const actionsRow = ref(null);
const openingContentId = ref(null);

const columns = [
  { key: 'title', label: 'Enlace', mobile: 'primary' },
  { key: 'association', label: 'Cliente / proyecto', mobile: 'secondary' },
  { key: 'origin', label: 'Origen', mobile: 'meta' },
  { key: 'status', label: 'Estado', mobile: 'secondary' },
  { key: 'expires_at', label: 'Vence', mobile: 'meta' },
  { key: 'consumed_at', label: 'Abierto', mobile: 'meta' },
];

const TABS = ['ready', 'sent', 'opened', 'expired', 'revoked'];
const tabOptions = computed(() => [
  { value: 'all', label: `${t('secureLinks.panel.all')} (${store.lifecycleCounts.all ?? store.counts.all ?? 0})` },
  ...TABS.map(value => ({ value, label: `${t(`secureLinks.states.${value}`)} (${store.lifecycleCounts[value] ?? 0})` })),
  { value: 'received', label: `${t('secureLinks.panel.received')} · ${store.unopenedReceived} ${t('secureLinks.panel.unopened')}` },
]);
const totalPages = computed(() => Math.max(1, Math.ceil(store.count / store.pageSize)));
const publicFeedback = computed(() => clipboard.feedbackFor('secure-links-public'));
const publicCopyAction = computed(() => publicFeedback.value.tone === 'success' ? 'complete' : 'copy');

function currentFilters() {
  const tab = filters.tab;
  return {
    lifecycle_status: ['all', 'received'].includes(tab) ? '' : tab,
    received: tab === 'received' ? 'true' : '',
    search: filters.search.trim(),
    page: filters.page,
    folder: filters.folder, archive_scope: filters.archive,
    ...(filters.entity !== 'all' && (filters.mode === 'client' || filters.entity === 'none') ? { [filters.mode]: filters.entity } : {}),
  };
}

let searchTimer = null;
async function load() {
  persistFilters();
  const result = await store.fetchLinks(currentFilters());
  if (result.success && result.page !== filters.page) filters.page = result.page;
  if (!result.success && result.error) notify.error({ title: result.error.message });
}

watch(() => [filters.tab, filters.page, filters.folder, filters.mode, filters.entity, filters.archive], () => { persistFilters(); load(); });
watch(() => filters.tab, () => { filters.page = 1; });
watch(() => filters.search, () => {
  store.invalidateLists();
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

watch(() => formModal.open, (open) => {
  if (!open) { formModal.fields = null; formModal.link = null; }
}, { flush: 'sync' });
watch(() => createdModal.open, (open) => {
  if (!open) { createdModal.url = ''; createdModal.expiresAt = null; }
}, { flush: 'sync' });
onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  store.invalidateLists();
  formModal.fields = null;
  createdModal.url = '';
});

onMounted(() => {
  store.fetchTypes();
  folders.fetchFolders();
  load();
});

// The admin layout's bottom "Actualizar datos" button reloads this list.
usePanelRefresh(async () => { await folders.fetchFolders(); await load(); });

function actionItems(row) {
  return [
    { action: 'view', label: 'Detalle e historial', testid: `secure-link-open-${row.id}`, onClick: () => openDetail(row.id) },
    { action: 'move', label: 'Mover de carpeta', testid: `secure-link-move-${row.id}`, onClick: () => { folderForm.folder = null; folderForm.link = row; folderForm.moving = false; folderForm.open = true; } },
    { action: 'edit', label: t('secureLinks.panel.editContent'), testid: `secure-link-edit-content-${row.id}`, onClick: () => editRowContent(row) },
    { action: 'copy', label: 'Copiar enlace', testid: `secure-link-copy-${row.id}`, onClick: () => copyRowUrl(row) },
    ...(!row.team_only && row.status === 'active' && !row.sent_at
      ? [{ action: 'complete', label: t('secureLinks.panel.markSent'), testid: `secure-link-mark-sent-${row.id}`, onClick: () => markSent(row) }] : []),
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

/** Same audited content read as the detail's "Editar contenido". */
async function editRowContent(row) {
  if (openingContentId.value) return;
  openingContentId.value = row.id;
  const result = await store.viewContent(row.id);
  openingContentId.value = null;
  if (!result.success) {
    notify.error({ title: result.error.message });
    return;
  }
  openEdit({ link: row, fields: contentFieldValues(result.data.fields) });
}

function onSaved(data) {
  folders.fetchFolders();
  formModal.fields = null;
  if (data?.url) {
    createdModal.url = data.url;
    createdModal.expiresAt = data.expires_at;
    createdModal.open = true;
  }
  load();
}

async function copyTo(key, text, successLabel) {
  return clipboard.copyText({
    key,
    text,
    successLabel,
    errorLabel: 'No se pudo copiar',
    onError: () => notify.error({ title: 'No se pudo copiar', detail: 'Selecciónalo y cópialo manualmente.' }),
  });
}

function copyPublicUrl() {
  return clipboard.copyText({
    key: 'secure-links-public',
    text: store.publicCreateUrl,
    successLabel: t('secureLinks.panel.publicLinkCopied'),
    errorLabel: t('secureLinks.panel.publicLinkCopyFailed'),
    onError: () => notify.error({
      title: t('secureLinks.panel.publicLinkCopyFailed'),
      detail: t('secureLinks.panel.publicLinkCopyRetry'),
    }),
  });
}

async function copyRowUrl(row) {
  const result = await store.fetchLinkUrl(row.id);
  if (!result.success) {
    notify.error({ title: result.error.message });
    return;
  }
  const copied = await copyTo(`secure-link-row-${row.id}`, result.url, 'Enlace copiado');
  if (copied) notify.success({ title: 'Enlace copiado' });
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
  if (store.isUpdating) return;
  const result = await store.revokeLink(row.id);
  if (!result.success) notify.error({ title: result.error.message });
  else load();
}

async function markSent(row) {
  if (store.isUpdating) return;
  const result = await store.markSent(row.id);
  if (!result.success) notify.error({ title: result.error.message });
  else { notify.success({ title: t('secureLinks.panel.markedSent') }); load(); }
}

async function remove(row) {
  if (store.isUpdating) return;
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

function persistFilters() {
  const query = { ...route.query, tab: filters.tab === 'all' ? undefined : filters.tab, search: filters.search || undefined,
    page: filters.page === 1 ? undefined : String(filters.page), folder: filters.folder === 'all' ? undefined : filters.folder,
    mode: filters.mode === 'project' ? undefined : filters.mode, entity: filters.entity === 'all' ? undefined : filters.entity,
    archive: filters.archive === 'active' ? undefined : filters.archive };
  router.replace({ query });
}
watch(() => route.query, query => {
  const next = readFilters(query);
  if (Object.keys(next).some(key => next[key] !== filters[key])) Object.assign(filters, next);
});
function selectFolder(id) { filters.folder = String(id); filters.entity = 'all'; filters.page = 1; folderDrawerOpen.value = false; }
function openFolderForm(folder = null, moving = false) { Object.assign(folderForm, { open: true, folder, link: null, moving }); }
async function reorderFolder(folder) {
  const siblings = folders.folders.filter(f => f.parent === folder.parent && !f.managed_project);
  const index = siblings.findIndex(f => f.id === folder.id);
  if (index < 1) return;
  [siblings[index - 1], siblings[index]] = [siblings[index], siblings[index - 1]];
  const result = await folders.reorderFolders(siblings.map(f => f.id), folder.parent);
  if (!result.success) notify.error({ title: result.error?.message || 'No se pudo guardar el orden.' });
}
async function folderSaved() { folderForm.open = false; await folders.fetchFolders(); await load(); }
async function moveLink({ link, folder }) {
  const result = await store.moveLink(link.id, folder, link.updated_at);
  if (!result.success) { notify.error({ title: result.error?.message || 'No se pudo mover el enlace.' }); return; }
  await folderSaved();
}
async function archiveFolder(folder) {
  const confirmed = await requestConfirm({ title: folder.is_archived ? 'Restaurar carpeta' : 'Archivar carpeta', message: folder.is_archived ? 'Se restaurará lo archivado por esta carpeta.' : 'Se ocultarán esta carpeta y su contenido. Los enlaces vigentes seguirán funcionando.' });
  if (!confirmed) return;
  const result = await folders.archiveFolder(folder, folder.is_archived);
  if (!result.success) { notify.error({ title: result.error?.message }); return; }
  filters.archive = folder.is_archived ? 'active' : 'archived';
  await load();
}
async function deleteFolder(folder) {
  const confirmed = await requestConfirm({ title: 'Eliminar carpeta', message: 'Solo se eliminará si está vacía, incluido su contenido archivado.' });
  if (!confirmed) return;
  const result = await folders.deleteFolder(folder);
  if (!result.success) { notify.error({ title: result.error?.message }); return; }
  if (numericFolderId.value === folder.id) selectFolder(folder.parent || 'all');
  await load();
}
</script>
