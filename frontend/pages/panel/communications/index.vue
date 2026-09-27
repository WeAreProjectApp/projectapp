<template>
  <div :class="[PAGE_MAX_WIDTH, 'flex min-h-full flex-col']" data-testid="communications-page">
    <header class="mb-4 flex flex-col gap-3 panel-portrait:flex-row panel-portrait:items-start panel-portrait:justify-between">
      <div>
        <h1 class="text-2xl font-light text-text-default">Comunicaciones</h1>
        <p class="mt-1 max-w-3xl text-sm text-text-subtle">
          Registro por cliente de lo enviado y recibido, organizado por proyecto o por cliente.
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <BaseButton
          :variant="isConfigOpen ? 'primary' : 'secondary'"
          size="md"
          data-testid="communications-settings"
          :aria-pressed="isConfigOpen"
          @click="toggleSettings"
        >
          <BaseActionIcon action="settings" />
          Configuraciones
        </BaseButton>
        <BaseButton
          variant="primary"
          size="md"
          data-testid="communications-new-thread"
          :disabled="isConfigOpen"
          disabled-reason="Vuelve a los hilos antes de crear uno nuevo."
          @click="openThreadForm"
        >
          <BaseActionIcon action="create" />
          Nuevo hilo
        </BaseButton>
      </div>
    </header>

    <CommunicationSettingsPanel
      v-if="isConfigOpen"
      ref="settingsPanelRef"
      @close="isConfigOpen = false"
      @reset-tabs="handleResetTabs"
    />

    <template v-else>
    <BaseAlert
      v-if="noticeReady && showNotice"
      variant="info"
      dismissible
      class="mb-4"
      data-testid="communications-channel-scope"
      @dismiss="dismissNotice"
    >
      Este módulo conserva el registro manual de las conversaciones. Copia el texto a WhatsApp o a tu correo y registra aquí lo enviado o recibido.
    </BaseAlert>
    <div v-else-if="noticeReady" class="mb-3">
      <BaseButton variant="link" size="sm" data-testid="communications-show-help" @click="showManualHelp">
        Cómo funciona el registro manual
      </BaseButton>
    </div>

    <BaseFilterTabs
      :tabs="displayTabs"
      :active-tab-id="activeTabId"
      :counts="tabCounts"
      :is-tab-limit-reached="isTabLimitReached"
      count-title="Hilos que cumplen este filtro"
      @select="handleSelectTab"
      @create="handleCreateTab"
      @rename="renameTab"
      @delete="deleteTab"
      @restore="restoreTab"
      @rebase="rebaseTab"
      @reorder="reorderTabs"
    />
    <div class="mb-4 flex flex-col gap-3 rounded-xl border border-border-muted bg-surface p-3 panel-portrait:flex-row panel-portrait:items-center">
      <BaseInput
        v-model="searchInput"
        class="min-w-0 flex-1"
        :placeholder="t('communicationFiling.search')"
        aria-label="Buscar comunicaciones"
        data-testid="communications-search"
      />
      <div class="flex min-w-0 flex-wrap items-center gap-2">
        <BaseButton
          :variant="isFilterPanelOpen || activeFilterCount ? 'primary' : 'secondary'"
          size="md"
          data-testid="communications-filter-toggle"
          :aria-expanded="isFilterPanelOpen"
          @click="isFilterPanelOpen = !isFilterPanelOpen"
        >
          <BaseActionIcon action="filter" />
          Filtros<span v-if="activeFilterCount"> ({{ activeFilterCount }})</span>
        </BaseButton>
        <div class="flex min-w-0 flex-wrap items-center gap-2" data-testid="communications-order-control">
          <span class="hidden text-xs font-medium text-text-subtle panel-portrait:inline">Orden:</span>
          <BaseSegmented
            :model-value="currentFilters.order"
            :options="ORDER_OPTIONS"
            size="sm"
            aria-label="Orden de los hilos"
            @update:model-value="handleSetOrder"
          />
        </div>
        <BaseActionButton
          action="refresh"
          label="Actualizar hilos"
          size="md"
          :loading="store.isLoading"
          @click="reloadThreadsAndCounts"
        />
      </div>
    </div>

    <CommunicationFilterPanel
      :model-value="currentFilters"
      :facets="store.facets"
      :is-open="isFilterPanelOpen"
      :results-count="store.count"
      :search-value="currentFilters.q.trim()"
      @update:model-value="updateFilters"
      @clear-search="searchInput = ''"
      @reset="clearFilters"
    />

    <BaseAlert v-if="store.error" variant="danger" class="mb-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>No se pudieron cargar las comunicaciones. {{ store.error }}</span>
        <BaseButton variant="secondary" size="sm" @click="loadThreads">Reintentar</BaseButton>
      </div>
    </BaseAlert>

    <BaseButton
      v-if="isPanelStacked"
      variant="secondary"
      size="md"
      class="mb-4 w-full justify-between"
      data-testid="communications-navigation-drawer-trigger"
      aria-haspopup="dialog"
      :aria-expanded="navigationDrawerOpen"
      @click="navigationDrawerOpen = true"
    >
      <span class="flex min-w-0 items-center gap-2">
        <BaseActionIcon action="folders" />
        <span class="truncate">{{ compactNavigationLabel }}</span>
      </span>
      <span class="shrink-0 text-xs font-medium text-text-brand">Cambiar</span>
    </BaseButton>

    <div
      ref="navigationGridRef"
      class="grid min-h-[32rem] flex-1 grid-cols-1 items-stretch gap-6 panel-landscape:grid-cols-[var(--communications-panel-w,18rem)_1.5rem_minmax(0,1fr)] panel-landscape:gap-0"
      :class="panelDragging ? 'select-none' : ''"
      :style="panelGridStyle"
    >
      <CommunicationNavigation
        v-if="!isPanelStacked"
        :mode="currentFilters.by"
        :selection="navigationSelection"
        :facets="store.facets"
        :archived-mode="currentFilters.scope === 'archived'"
        :scope-locked="Boolean(currentFilters.q.trim())"
        :show-inactive-projects="showInactiveProjects"
        data-testid="communications-navigation-panel"
        @update:mode="handleSetMode"
        @select="selectNavigation"
        @toggle-archived="handleToggleArchived"
        @toggle-inactive-projects="handleToggleInactiveProjects"
      >
        <CommunicationFolderPanel :client-id="folderClientId" :project-id="folderProjectId" :selected="currentFilters.folder" :searching="Boolean(currentFilters.q.trim())" @select="selectFolder" @loaded="visibleFolders = $event" @changed="reloadThreadsAndCounts" />
      </CommunicationNavigation>

      <BaseResizeHandle
        v-if="!isPanelStacked"
        :value="panelWidth"
        :min="COMMUNICATION_PANEL_MIN"
        :max="COMMUNICATION_PANEL_MAX"
        label="Ajustar el ancho de la navegación de comunicaciones"
        test-id="communications-navigation-resize-handle"
        @pointer-start="onHandleDown"
        @pointer-move="onHandleMove"
        @pointer-end="onHandleUp"
        @resize="resizePanelWidth"
        @reset="resetPanelWidth"
      />

      <section class="min-w-0">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="text-sm font-semibold text-text-default">Hilos</h2>
            <p class="text-xs text-text-subtle">{{ store.count }} en este recorte</p>
          </div>
        </div>

        <div v-if="childFolders.length && !currentFilters.q.trim()" class="mb-3 flex flex-wrap gap-2" data-testid="communication-subfolders">
          <BaseButton v-for="folder in childFolders" :key="folder.id" variant="secondary" @click="selectFolder(String(folder.id))"><BaseActionIcon action="folders" />{{ folder.name }}</BaseButton>
        </div>
        <BaseEmptyState
          v-if="!store.isLoading && store.threads.length === 0"
          title="No hay hilos con este recorte"
          description="Cambia la navegación o los filtros, o registra una conversación."
          class="rounded-xl border border-border-muted bg-surface"
        >
          <template #actions>
            <BaseButton variant="primary" size="sm" @click="openThreadForm">Crear hilo</BaseButton>
          </template>
        </BaseEmptyState>
        <CommunicationThreadTable
          v-else
          :threads="store.threads"
          :loading="store.isLoading"
          :search-query="currentFilters.q"
          :href-for="threadHref"
          :compact="isPanelStacked"
          @open="openThreadFromRow"
          @link-activate="markLinkActivation"
        />

        <BasePagination
          v-if="store.numPages > 1"
          class="mt-4"
          :current-page="store.page"
          :total-pages="store.numPages"
          :total-items="store.count"
          :range-from="(store.page - 1) * store.preferences.page_size + 1"
          :range-to="Math.min(store.page * store.preferences.page_size, store.count)"
          @prev="page = Math.max(1, page - 1)"
          @next="page = Math.min(store.numPages, page + 1)"
          @go="page = $event"
        />
      </section>
    </div>

    <BaseDrawer
      v-model="navigationDrawerOpen"
      placement="left"
      :title="currentFilters.by === 'project' ? 'Proyectos' : 'Clientes'"
      test-id="communications-navigation-drawer"
    >
      <div class="h-full p-3">
        <CommunicationNavigation
          :mode="currentFilters.by"
          :selection="navigationSelection"
          :facets="store.facets"
          :archived-mode="currentFilters.scope === 'archived'"
          :scope-locked="Boolean(currentFilters.q.trim())"
          :show-inactive-projects="showInactiveProjects"
          touch-mode
          @update:mode="handleDrawerMode"
          @select="handleDrawerSelection"
          @toggle-archived="handleToggleArchived"
          @toggle-inactive-projects="handleToggleInactiveProjects"
        >
          <CommunicationFolderPanel :client-id="folderClientId" :project-id="folderProjectId" :selected="currentFilters.folder" :searching="Boolean(currentFilters.q.trim())" @select="selectFolder" @loaded="visibleFolders = $event" @changed="reloadThreadsAndCounts" />
        </CommunicationNavigation>
      </div>
    </BaseDrawer>
    </template>

    <CommunicationWorkspaceModal
      :model-value="workspaceOpen"
      :thread-id="requestedThreadId"
      :default-channel="store.preferences.default_channel"
      @update:model-value="handleWorkspaceOpenChange"
      @changed="reloadThreadsAndCounts"
    />

    <BaseModal v-model="threadFormOpen" kind="form" padding="none">
      <form :id="modalFormId" novalidate @submit.prevent="createThread">
        <div class="border-b border-border-muted px-5 py-4 panel-portrait:px-6">
          <h2 class="text-lg font-semibold text-text-default">Nuevo hilo de comunicación</h2>
          <p class="mt-1 text-sm text-text-subtle">Un cliente puede mantener varios hilos abiertos a la vez.</p>
        </div>
        <div class="space-y-4 px-5 py-5 panel-portrait:px-6">
          <BaseFormField
            v-slot="{ invalid, errorId }"
            label="Cliente"
            required
            :error="threadFormErrors.client"
          >
            <ClientAutocomplete
              v-model="threadForm.client"
              :initial-label="threadForm.clientLabel"
              placeholder="Buscar cliente..."
              test-id="communication-thread-client"
              :error="invalid"
              :error-described-by="errorId"
              @select="onThreadClientSelect"
            />
          </BaseFormField>
          <ProjectSelect
            v-model="threadForm.project"
            :client-profile-id="threadForm.client"
            :client-label="threadForm.clientLabel"
            :allow-create="false"
            label="Proyecto"
            testid="communication-thread-project"
          />
          <CommunicationFolderPicker v-model="threadForm.folder" :client-id="threadForm.client" :project-id="threadForm.project" />
          <BaseAlert v-if="threadFormErrors.folder" variant="danger">{{ threadFormErrors.folder }}</BaseAlert>
          <BaseFormField
            v-slot="{ invalid, errorId }"
            label="Título"
            required
            :error="threadFormErrors.title"
          >
            <BaseInput
              v-model="threadForm.title"
              placeholder="Ej. Aprobación del alcance de la fase 2"
              data-testid="communication-thread-title"
              :error="invalid"
              :aria-describedby="errorId"
              @update:model-value="clearThreadFormError('title')"
            />
          </BaseFormField>
        </div>
      </form>
      <template #footer>
        <BaseModalActions>
          <BaseButton type="button" variant="secondary" size="md" @click="threadFormOpen = false">Cancelar</BaseButton>
          <BaseButton
            type="submit" :form="modalFormId"
            variant="primary"
            size="md"
            :loading="store.isMutating"
            data-testid="communication-thread-create-submit"
          >
            Crear hilo
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { useId, computed, reactive, ref, watch } from 'vue';
import CommunicationFolderPanel from '~/components/communications/CommunicationFolderPanel.vue';
import CommunicationFolderPicker from '~/components/communications/CommunicationFolderPicker.vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import ProjectSelect from '~/components/accounting/ProjectSelect.vue';
import CommunicationFilterPanel from '~/components/communications/CommunicationFilterPanel.vue';
import CommunicationNavigation from '~/components/communications/CommunicationNavigation.vue';
import CommunicationSettingsPanel from '~/components/communications/CommunicationSettingsPanel.vue';
import CommunicationThreadTable from '~/components/communications/CommunicationThreadTable.vue';
import CommunicationWorkspaceModal from '~/components/communications/CommunicationWorkspaceModal.vue';
import { useCommunicationFilters } from '~/composables/useCommunicationFilters';
import { useDetailQueryParam } from '~/composables/useDetailQueryParam';
import {
  COMMUNICATION_PANEL_MAX,
  COMMUNICATION_PANEL_MIN,
  useCommunicationPanelWidth,
} from '~/composables/useCommunicationPanelWidth';
import { useIsMobile } from '~/composables/useIsMobile';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useRowNavigation } from '~/composables/useRowNavigation';
import { PANEL_BREAKPOINTS } from '~/config/responsive';
import { useCommunicationsStore } from '~/stores/communications';
import { isPlainActivation } from '~/utils/rowNavigation';
import { PAGE_MAX_WIDTH } from '~/utils/tableLayout';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const ORDER_OPTIONS = [
  { value: 'recent', label: 'Recientes', testId: 'communications-order-recent' },
  { value: 'oldest', label: 'Antiguos', testId: 'communications-order-oldest' },
  { value: 'title', label: 'A–Z', testId: 'communications-order-title' },
];

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const visibleFolders = ref([]);
const store = useCommunicationsStore();
const notify = usePanelNotify();
const { openRow } = useRowNavigation();
const {
  currentFilters,
  page,
  activeTabId,
  isFilterPanelOpen,
  searchInput,
  displayTabs,
  tabCountSpecs,
  navigationSelection,
  activeFilterCount,
  isTabLimitReached,
  setMode,
  selectNavigation,
  setScope,
  updateFilters,
  setOrder,
  clearFilters,
  selectTab,
  saveTab,
  deleteTab,
  renameTab,
  restoreTab,
  rebaseTab,
  reorderTabs,
  reloadTabs,
  filtersReady,
  requestFilters,
} = useCommunicationFilters();

const { isMobile: isPanelStacked } = useIsMobile(PANEL_BREAKPOINTS.landscape - 1);
const navigationGridRef = ref(null);
const {
  width: panelWidth,
  dragging: panelDragging,
  gridStyle: panelGridStyle,
  onHandleDown,
  onHandleMove,
  onHandleUp,
  resizeWidth: resizePanelWidth,
  resetWidth: resetPanelWidth,
  hydrateWidth: hydratePanelWidth,
} = useCommunicationPanelWidth(navigationGridRef, {
  initialWidth: store.preferences.navigation_width,
  onPersist: persistNavigationWidth,
});

const noticeReady = ref(false);
const showNotice = ref(false);
const isConfigOpen = ref(false);
const settingsPanelRef = ref(null);
const tabCounts = ref({});
let tabCountsRequestId = 0;
const navigationDrawerOpen = ref(false);
const threadFormOpen = ref(false);
const workspaceOpenedLocally = ref(false);
const {
  openId: requestedThreadId,
  isOpen: workspaceOpen,
  toFor: threadLocation,
  close: removeThreadFromUrl,
} = useDetailQueryParam('thread');

const threadForm = reactive({
  client: null,
  clientLabel: '',
  project: null,
  title: '',
});
const threadFormErrors = ref({});

function clearThreadFormError(field) {
  const nextErrors = { ...threadFormErrors.value };
  delete nextErrors[field];
  threadFormErrors.value = nextErrors;
}

const compactNavigationLabel = computed(() => {
  if (navigationSelection.value === 'all') {
    return currentFilters.by === 'project' ? 'Todos los proyectos' : 'Todos los clientes';
  }
  if (navigationSelection.value === 'none') return 'Sin proyecto';
  const entries = currentFilters.by === 'project' ? store.facets.projects : store.facets.clients;
  return entries.find((entry) => String(entry.id) === String(navigationSelection.value))?.name
    || (currentFilters.by === 'project' ? 'Proyecto seleccionado' : 'Cliente seleccionado');
});

const requestSignature = computed(() => (
  filtersReady.value ? JSON.stringify(requestFilters()) : ''
));
watch(requestSignature, (signature) => {
  if (signature) loadThreads();
}, { immediate: true });
const tabCountSignature = computed(() => JSON.stringify(
  [...tabCountSpecs.value].sort((left, right) => String(left.id).localeCompare(String(right.id))),
));
watch(tabCountSignature, refreshTabCounts, { immediate: true });
watch(requestedThreadId, (threadId) => {
  if (!threadId) store.clearCurrentThread();
});

watch(
  () => store.preferences.show_manual_help,
  (showHelp) => {
    if (!store.preferenceReady) return;
    noticeReady.value = true;
    showNotice.value = showHelp;
  },
  { immediate: true },
);
watch(
  () => store.preferenceReady,
  (ready) => {
    if (!ready) return;
    noticeReady.value = true;
    showNotice.value = store.preferences.show_manual_help;
  },
  { immediate: true },
);
watch(
  () => store.preferences.navigation_width,
  (width) => hydratePanelWidth(width),
);
watch(
  () => store.preferences.page_size,
  (pageSize, previousPageSize) => {
    if (!store.preferenceReady || pageSize === previousPageSize) return;
    page.value = 1;
  },
);

async function dismissNotice() {
  showNotice.value = false;
  const result = await store.updatePreferences({ show_manual_help: false });
  if (!result.success) {
    notify.warning({
      title: 'La ayuda se ocultó sólo por esta visita',
      detail: result.message,
    });
  }
}

function showManualHelp() {
  showNotice.value = true;
}

function toggleSettings() {
  if (isConfigOpen.value) {
    settingsPanelRef.value?.requestClose();
    return;
  }
  isConfigOpen.value = true;
}

async function loadThreads() {
  await store.fetchThreads(requestFilters());
}

async function refreshTabCounts() {
  const requestId = ++tabCountsRequestId;
  const result = await store.fetchTabCounts(tabCountSpecs.value);
  if (requestId === tabCountsRequestId && result.success) tabCounts.value = result.counts;
}

async function reloadThreadsAndCounts() {
  await Promise.all([loadThreads(), refreshTabCounts()]);
}

function handleSelectTab(tabId) {
  selectTab(tabId);
}

async function handleResetTabs() {
  await reloadTabs();
  await refreshTabCounts();
}

async function handleCreateTab(name) {
  const tab = await saveTab(name);
  if (tab) notify.success({ title: 'Vista guardada' });
  else notify.error({ title: 'No se pudo guardar la vista' });
}

function handleDrawerMode(mode) {
  handleSetMode(mode);
}

async function persistPreference(payload, failureTitle) {
  const result = await store.updatePreferences(payload);
  if (!result.success) notify.warning({ title: failureTitle, detail: result.message });
}

function handleSetMode(mode) {
  const normalized = mode === 'client' ? 'client' : 'project';
  setMode(normalized);
  persistPreference(
    { navigation_mode: normalized },
    'El modo cambió sólo por esta visita',
  );
}

// El interruptor de archivados es un eje de la VISITA, no una preferencia: no
// se persiste ni viaja en la memoria de cuenta, igual que en el gestor documental.
function handleToggleArchived(on) {
  setScope(on ? 'archived' : 'active');
}

// Empieza apagado en cada visita, como su gemelo de documentos, y al girarlo
// suelta la seleccion si el proyecto elegido deja de listarse: si no, el listado
// quedaria filtrado por una fila que ya no se ve.
const showInactiveProjects = ref(false);

function handleToggleInactiveProjects(on) {
  showInactiveProjects.value = Boolean(on);
  const selected = store.facets.projects?.find(
    (entry) => String(entry.id) === String(navigationSelection.value),
  );
  if (!selected) return;
  const selectedIsInactive = selected.catalog_bucket === 'archived';
  if (showInactiveProjects.value !== selectedIsInactive) selectNavigation('all');
}

function handleSetOrder(order) {
  setOrder(order);
  persistPreference(
    { thread_order: currentFilters.order },
    'El orden cambió sólo por esta visita',
  );
}

function persistNavigationWidth(width) {
  persistPreference(
    { navigation_width: width },
    'El ancho cambió sólo por esta visita',
  );
}

function handleDrawerSelection(selection) {
  selectNavigation(selection);
  navigationDrawerOpen.value = false;
}

function threadHref(thread) {
  return router.resolve(threadLocation(thread.id)).href;
}

function openThreadFromRow(thread, event) {
  if (isPlainActivation(event)) workspaceOpenedLocally.value = true;
  openRow(threadHref(thread), event);
}

function markLinkActivation(_thread, event) {
  if (isPlainActivation(event)) workspaceOpenedLocally.value = true;
}

function handleWorkspaceOpenChange(open) {
  if (open) return;
  if (workspaceOpenedLocally.value) {
    workspaceOpenedLocally.value = false;
    router.back();
    return;
  }
  removeThreadFromUrl();
}

function selectedClientEntry(clientId) {
  return store.facets.clients.find((entry) => String(entry.id) === String(clientId));
}

async function openThreadForm() {
  threadFormErrors.value = {};
  Object.assign(threadForm, {
    client: null,
    clientLabel: '',
    project: null,
    title: '',
    folder: currentFilters.folder !== 'none' ? currentFilters.folder : '',
  });

  if (currentFilters.by === 'client' && currentFilters.client) {
    const client = selectedClientEntry(currentFilters.client);
    threadForm.client = Number(currentFilters.client);
    threadForm.clientLabel = client?.name || '';
  } else if (currentFilters.by === 'project' && currentFilters.project && currentFilters.project !== 'none') {
    const project = store.facets.projects.find(
      (entry) => String(entry.id) === String(currentFilters.project),
    );
    if (project && !project.unavailable) {
      threadForm.project = Number(project.id);
      threadForm.client = Number(project.client_id);
      threadForm.clientLabel = selectedClientEntry(project.client_id)?.name
        || project.client_name
        || '';
    }
  }
  let folder = visibleFolders.value.find((item) => String(item.id) === String(threadForm.folder));
  if (threadForm.folder && !folder) {
    const result = await store.fetchFolders({ client: threadForm.client });
    if (!result.success) { notify.error({ title: t('communicationFiling.loadError'), detail: result.message }); return; }
    folder = result.data.find((item) => String(item.id) === String(threadForm.folder));
    if (!folder) threadForm.folder = '';
  }
  if (folder) { threadForm.client = folder.client; threadForm.project = folder.project || threadForm.project; }
  threadFormOpen.value = true;
}

function onThreadClientSelect(client) {
  clearThreadFormError('client');
  threadForm.clientLabel = client?.name || '';
  threadForm.project = null;
  threadForm.folder = "";
}

async function createThread() {
  threadFormErrors.value = {
    ...(!threadForm.client ? { client: 'Elige un cliente.' } : {}),
    ...(!threadForm.title.trim() ? { title: 'Escribe el título del hilo.' } : {}),
  };
  if (Object.keys(threadFormErrors.value).length) return;

  const result = await store.createThread({
    client: threadForm.client,
    project: threadForm.project || null,
    title: threadForm.title.trim(),
    folder: threadForm.folder ? Number(threadForm.folder) : null,
  });
  if (!result.success) {
    threadFormErrors.value = result.fieldErrors || {};
    if (Object.keys(threadFormErrors.value).length) return;
    notify.error({ title: 'No se pudo crear el hilo', detail: result.message });
    return;
  }
  threadFormOpen.value = false;
  await reloadThreadsAndCounts();
  workspaceOpenedLocally.value = true;
  await router.push(threadLocation(result.data.id));
  notify.success({ title: 'Hilo creado' });
}
const folderProjectId = computed(() => currentFilters.by === 'project' && currentFilters.project !== 'none' ? currentFilters.project || null : null);
const folderClientId = computed(() => currentFilters.by === 'client'
  ? currentFilters.client || null
  : store.facets.projects.find((entry) => String(entry.id) === String(folderProjectId.value))?.client_id || null);
const childFolders = computed(() => visibleFolders.value.filter((folder) => (
  String(folder.parent || '') === String(currentFilters.folder === 'none' ? '-' : currentFilters.folder)
)));
function selectFolder(id) {
  currentFilters.folder = id;
  page.value = 1;
  navigationDrawerOpen.value = false;
}

const modalFormId = useId();
</script>
