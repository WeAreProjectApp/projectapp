<template>
  <div class="mx-auto w-full max-w-7xl space-y-5" data-testid="access-page">
    <header class="flex flex-wrap items-start justify-between gap-3">
      <div><h1 class="text-2xl font-light text-text-default">Accesos</h1><p class="mt-1 text-sm text-text-muted">Controla qué cuentas pueden entrar a ProjectApp.</p></div>
      <BaseButton variant="primary" data-testid="access-create" @click="createOpen = true">Nuevo cliente</BaseButton>
    </header>
    <BaseSegmented v-model="group" :options="groupOptions" />
    <div class="flex flex-wrap gap-2" aria-label="Vistas rápidas">
      <BaseButton v-for="preset in presets" :key="preset.key" variant="secondary" size="sm" :data-testid="`access-preset-${preset.key}`" @click="applyPreset(preset.key)">{{ preset.label }} <BaseBadge>{{ store.counts[preset.key] || 0 }}</BaseBadge></BaseButton>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <BaseInput v-model="search" type="search" placeholder="Buscar por nombre, correo o empresa…" aria-label="Buscar accesos" class="w-full sm:max-w-sm" data-testid="access-search" />
      <BaseDropdown :items="savedItems" align="left"><template #trigger><BaseButton variant="secondary">Filtros guardados</BaseButton></template></BaseDropdown>
      <BaseDropdown :items="orderItems"><template #trigger><BaseButton variant="secondary">Orden: {{ orderLabel }}</BaseButton></template></BaseDropdown>
      <BaseButton variant="ghost" :disabled="activeFilters === 0 && !search" disabled-reason="No hay filtros activos." @click="clearFilters">Limpiar filtros {{ activeFilters ? `(${activeFilters})` : '' }}</BaseButton>
      <BaseButton variant="ghost" @click="saveOpen = true">Guardar vista</BaseButton>
    </div>
    <details class="rounded-xl border border-border-default bg-surface p-3" :open="!compact">
      <summary class="cursor-pointer text-sm text-text-muted">Filtros combinables · {{ activeFilters }} {{ activeFilters === 1 ? 'activo' : 'activos' }}</summary>
      <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <BaseFilterDropdown v-for="filter in filterOptions" :key="filter.key" :model-value="filters[filter.key]" :label="filter.label" :options="filter.options" :searchable="false" :test-id="`access-filter-${filter.key}`" @update:model-value="setFilter(filter.key, $event)" />
      </div>
    </details>
    <p class="text-sm text-text-muted" role="status">{{ store.count }} {{ store.count === 1 ? 'cuenta' : 'cuentas' }} · página {{ store.page }} de {{ store.pages }}</p>
    <BaseAlert v-if="store.error" variant="danger" role="alert">{{ store.error }} <BaseButton variant="link" @click="load">Reintentar</BaseButton></BaseAlert>
    <p v-if="store.loading" class="py-10 text-center text-text-muted" role="status">Cargando accesos…</p>
    <div v-else-if="!store.error && !store.hasResults" class="rounded-xl border border-border-default p-8 text-center">
      <p class="text-text-muted">{{ activeFilters || search ? 'No hay cuentas con estos filtros.' : 'Todavía no hay cuentas en este grupo.' }}</p>
      <BaseButton v-if="activeFilters || search" variant="link" @click="clearFilters">Ver todas</BaseButton>
    </div>
    <div v-else-if="!store.error" class="space-y-3">
      <article v-for="account in store.results" :key="account.id" class="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border-default bg-surface p-4" :data-testid="`access-row-${account.id}`">
        <div class="min-w-0 flex-1">
          <h2 class="break-words text-sm font-semibold text-text-default">{{ account.name }}</h2>
          <p class="mt-1 break-all text-sm text-text-muted">{{ account.email || 'Sin correo registrado' }}</p>
          <p v-if="account.company" class="mt-1 break-words text-xs text-text-muted">{{ account.company }}</p>
          <div class="mt-2 flex flex-wrap gap-2"><BaseBadge :variant="account.enabled ? 'primary' : 'neutral'">{{ account.enabled ? 'Habilitado' : 'Sin acceso' }}</BaseBadge><BaseBadge v-if="!account.onboarded">Sin primer acceso</BaseBadge><BaseBadge v-if="account.google_linked">Google vinculado</BaseBadge></div>
          <p class="mt-2 text-xs text-text-subtle">Último acceso: {{ account.last_login ? formatDate(account.last_login) : 'Todavía no ha entrado' }}{{ account.last_method ? ` · ${methodLabel(account.last_method)}` : '' }}</p>
        </div>
        <BaseDropdown :items="accountActions(account)"><template #trigger><BaseButton variant="ghost" :aria-label="`Acciones de ${account.email}`" :data-testid="`access-actions-${account.id}`">Acciones</BaseButton></template></BaseDropdown>
      </article>
    </div>
    <BasePagination :current-page="store.page" :total-pages="store.pages" :total-items="store.count" @prev="setPage(store.page - 1)" @next="setPage(store.page + 1)" @go="setPage" />
    <BaseModal :model-value="createOpen" kind="form" title-id="access-create-title" @close="createOpen = false">
      <form class="space-y-4 p-6" @submit.prevent="createClient">
        <h2 id="access-create-title" class="text-lg text-text-default">Nuevo cliente</h2>
        <p class="text-sm text-text-muted">Se registrará sin acceso. Podrás habilitarlo después de revisar su correo.</p>
        <BaseFormField label="Nombre" required><BaseInput v-model="newClient.name" required maxlength="150" /></BaseFormField>
        <BaseFormField label="Correo" required :error="fieldError"><BaseInput v-model="newClient.email" type="email" required /></BaseFormField>
        <BaseFormField label="Empresa"><BaseInput v-model="newClient.company" maxlength="200" /></BaseFormField>
        <BaseAlert v-if="actionError" variant="danger">{{ actionError }}</BaseAlert>
        <BaseModalActions><BaseButton variant="ghost" @click="createOpen = false">Cancelar</BaseButton><BaseButton type="submit" variant="primary" :loading="saving">Crear sin acceso</BaseButton></BaseModalActions>
      </form>
    </BaseModal>
    <BaseModal :model-value="Boolean(detail)" kind="detail" title-id="access-detail-title" @close="detail = null">
      <div v-if="detail" class="space-y-4 p-6">
        <h2 id="access-detail-title" class="break-words text-lg text-text-default">{{ detail.name }}</h2><p class="break-all text-sm text-text-muted">{{ detail.email }}</p>
        <p class="text-sm text-text-muted">{{ detail.enabled ? 'Acceso habilitado' : 'Acceso deshabilitado' }} · {{ detail.email_verified ? 'Correo verificado' : 'Correo sin verificar' }}</p>
        <BaseAlert v-if="actionError" variant="danger">{{ actionError }}</BaseAlert>
        <h3 class="font-semibold text-text-default">Actividad de acceso</h3>
        <p v-if="!detail.events.length" class="text-sm text-text-muted">Todavía no hay actividad registrada.</p>
        <ol class="space-y-3"><li v-for="event in detail.events" :key="event.id" class="rounded-lg border border-border-muted p-3 text-sm text-text-muted"><p>{{ eventLabel(event.action) }} · {{ formatDate(event.at) }}</p><p>{{ methodLabel(event.method) }} {{ event.surface }} {{ event.ip }}</p><p class="break-all text-xs">{{ event.device }}</p></li></ol>
        <BasePagination :current-page="detail.event_page" :total-pages="detail.event_pages" @prev="openDetail(detail, detail.event_page - 1)" @next="openDetail(detail, detail.event_page + 1)" @go="openDetail(detail, $event)" />
      </div>
    </BaseModal>
    <BaseModal :model-value="saveOpen" kind="form" title-id="access-save-title" @close="saveOpen = false"><form class="space-y-4 p-6" @submit.prevent="saveView"><h2 id="access-save-title">Guardar filtros</h2><BaseFormField label="Nombre de la vista" required><BaseInput v-model="viewName" required maxlength="80" /></BaseFormField><BaseAlert v-if="tabs.lastError.value" variant="danger">No pudimos guardar la vista.</BaseAlert><BaseButton variant="primary" type="submit" :disabled="tabs.isTabLimitReached.value" disabled-reason="Llegaste al límite de vistas guardadas.">Guardar</BaseButton></form></BaseModal>
    <ConfirmModal v-model="confirmState.open" :title="confirmState.title" :message="confirmState.message" :variant="confirmState.variant" :confirm-text="confirmState.confirmText" @confirm="handleConfirmed" @cancel="handleCancelled" />
    <BaseAlert v-if="actionError && !createOpen && !detail" variant="danger" role="alert">{{ actionError }}</BaseAlert>
  </div>
</template>
<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { usePanelAccessStore } from '~/stores/panel_access';
import { useProposalStore } from '~/stores/proposals';
import { useSavedFilterTabs } from '~/composables/useSavedFilterTabs';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { useIsMobile } from '~/composables/useIsMobile';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });
const store = usePanelAccessStore();
const proposalStore = useProposalStore();
const route = useRoute(); const router = useRouter();
const { isMobile: compact } = useIsMobile();
const tabs = useSavedFilterTabs('access');
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const keys = ['enabled', 'onboarded', 'verified', 'google', 'last_access'];
const filters = reactive(Object.fromEntries(keys.map((key) => [key, String(route.query[key] || '').split(',').filter(Boolean)])));
const group = ref(route.query.group === 'team' ? 'team' : 'clients');
const search = ref(String(route.query.search || ''));
const order = ref(String(route.query.order || 'email'));
const createOpen = ref(false); const saveOpen = ref(false); const viewName = ref('');
const detail = ref(null); const saving = ref(false); const fieldError = ref(''); const actionError = ref('');
const newClient = reactive({ name: '', email: '', company: '' });
const groupOptions = computed(() => [{ value: 'clients', label: 'Clientes' }, ...(proposalStore.isSuperuser ? [{ value: 'team', label: 'Equipo' }] : [])]);
const presets = [{ key: 'all', label: 'Todos' }, { key: 'enabled', label: 'Habilitados' }, { key: 'disabled', label: 'Sin habilitar' }, { key: 'pending', label: 'Sin primer acceso' }];
const yesNo = [{ value: 'true', label: 'Sí' }, { value: 'false', label: 'No' }];
const filterOptions = [
  { key: 'enabled', label: 'Habilitado', options: yesNo }, { key: 'onboarded', label: 'Primer acceso', options: yesNo },
  { key: 'verified', label: 'Correo verificado', options: yesNo }, { key: 'google', label: 'Google vinculado', options: yesNo },
  { key: 'last_access', label: 'Último acceso', options: [{ value: 'never', label: 'Nunca' }, { value: '7', label: 'Últimos 7 días' }, { value: '30', label: 'Últimos 30 días' }] },
];
const activeFilters = computed(() => keys.filter((key) => filters[key].length).length);
const orderLabels = { email: 'Correo', name: 'Nombre', recent: 'Acceso reciente' };
const orderLabel = computed(() => orderLabels[order.value] || 'Correo');
const orderItems = Object.entries(orderLabels).map(([value, label]) => ({ label, onClick: () => { order.value = value; } }));
const savedItems = computed(() => tabs.savedTabs.value.length ? tabs.savedTabs.value.flatMap((tab) => [{ label: tab.name, onClick: () => applyView(tab.filters) }, { label: `Eliminar ${tab.name}`, danger: true, onClick: () => tabs.deleteTab(tab.id) }]) : [{ label: 'No hay vistas guardadas', disabled: true }]);
let searchTimer; let detailRequest = 0; let hydratingQuery = false;
function query(page = 1) { return { group: group.value, search: search.value.trim(), order: order.value, page: String(page), ...Object.fromEntries(keys.map((key) => [key, filters[key].join(',')])) }; }
function load() { return store.fetchList(route.query); }
function update(page = 1) { if (hydratingQuery) return; router.replace({ query: query(page) }); }
function setPage(page) { update(page); }
function setFilter(key, values) { filters[key] = key === 'last_access' ? values.slice(-1) : values; }
function clearFilters() { search.value = ''; keys.forEach((key) => { filters[key] = []; }); }
function applyPreset(key) { clearFilters(); if (key === 'enabled') filters.enabled = ['true']; if (key === 'disabled') filters.enabled = ['false']; if (key === 'pending') filters.onboarded = ['false']; }
function applyView(values) { search.value = values.search || ''; order.value = values.order || 'email'; group.value = values.group || 'clients'; keys.forEach((key) => { filters[key] = String(values[key] || '').split(',').filter(Boolean); }); }
async function saveView() { if (await tabs.saveTab(viewName.value.trim(), query())) { saveOpen.value = false; viewName.value = ''; } }
watch([group, order, filters], () => update(), { deep: true });
watch(search, () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => update(), 300); });
watch(() => route.query, async () => {
  hydratingQuery = true;
  clearTimeout(searchTimer);
  group.value = route.query.group === 'team' ? 'team' : 'clients';
  search.value = String(route.query.search || '');
  order.value = String(route.query.order || 'email');
  keys.forEach((key) => { filters[key] = String(route.query[key] || '').split(',').filter(Boolean); });
  await nextTick(); clearTimeout(searchTimer); hydratingQuery = false; load();
});
onMounted(() => { load(); tabs.loadTabs(); });
onUnmounted(() => { clearTimeout(searchTimer); detailRequest += 1; });
usePanelRefresh(load);
function accountActions(account) { return [
  { label: 'Ver detalle y actividad', onClick: () => openDetail(account) },
  { label: account.enabled ? 'Deshabilitar acceso' : 'Habilitar acceso', danger: account.enabled, onClick: () => confirmChange(account, { enabled: !account.enabled }) },
  ...(account.google_linked ? [{ label: 'Desvincular Google', danger: true, onClick: () => confirmChange(account, { unlink_google: true }) }] : []),
]; }
async function openDetail(account, page = 1) { const requestId = ++detailRequest; actionError.value = ''; try { const data = await store.detail(account.id, page); if (requestId === detailRequest) detail.value = data; } catch { actionError.value = 'No pudimos cargar el detalle. Intenta de nuevo.'; } }
function confirmChange(account, changes) { requestConfirm({ title: changes.unlink_google ? 'Desvincular Google' : changes.enabled ? 'Habilitar acceso' : 'Deshabilitar acceso', message: `Se actualizará el acceso de ${account.email}. Deshabilitar o desvincular cierra sus sesiones anteriores.`, onConfirm: async () => { actionError.value = ''; try { await store.change(account.id, changes); await load(); } catch (failure) { actionError.value = readableError(failure); } } }); }
async function createClient() { if (saving.value) return; saving.value = true; fieldError.value = ''; actionError.value = ''; try { await store.createClient({ ...newClient }); createOpen.value = false; Object.assign(newClient, { name: '', email: '', company: '' }); group.value = 'clients'; clearFilters(); await load(); } catch (failure) { fieldError.value = failure.response?.data?.email?.[0] || ''; actionError.value = readableError(failure); } finally { saving.value = false; } }
function readableError(failure) { const data = failure.response?.data; return typeof data === 'string' ? data : Array.isArray(data) ? data[0] : data?.detail || 'No pudimos guardar el cambio. Revisa los datos.'; }
function formatDate(value) { return new Date(value).toLocaleString('es-CO'); }
function methodLabel(value) { return ({ code: 'Código por correo', google: 'Google', password: 'Contraseña' })[value] || ''; }
function eventLabel(value) { return ({ login: 'Inicio de sesión', enabled: 'Acceso habilitado', disabled: 'Acceso deshabilitado', google_unlinked: 'Google desvinculado', created: 'Cuenta creada' })[value] || value; }
</script>
