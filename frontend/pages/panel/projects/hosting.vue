<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useHostingControlsStore } from '~/stores/hosting_controls'

definePageMeta({ middleware: ['admin-auth'], layout: 'admin' })
const store = useHostingControlsStore()
const route = useRoute()
const search = ref('')
const projectFilter = ref(route.query.project || '')
const drafts = reactive({})
const statusLabels = { confirmed: 'Confirmado por producción', pending: 'Pendiente de aplicación', disconnected: 'Sin conexión reciente', unintegrated: 'Sin integrar', error: 'Error de aplicación', suspended: 'Servicios suspendidos', removed: 'Retirado' }
const modeLabels = { normal: 'Funcionamiento normal', suspended: 'Pantalla de suspensión', banner: 'Banner de aviso' }
const modes = [{ key: 'suspended', prefix: 'suspension', label: 'Pantalla de suspensión' }, { key: 'banner', prefix: 'banner', label: 'Banner de aviso' }]
const options = computed(() => store.records.map(record => ({ label: record.name, description: record.targets[0]?.origins.join(', ') || 'Sin destino', testid: `hosting-target-${record.id}`, onClick: () => select(record.id) })))
const draft = computed(() => drafts[store.selected?.id])
let timer
let searchTimer

function initializeDrafts(data) {
  if (drafts[data.id]) return
  drafts[data.id] = Object.fromEntries(modes.map(mode => [mode.key, { title: data[`${mode.prefix}_title`], text: data[`${mode.prefix}_text`], version: data.version }]))
}
async function select(id) {
  try { initializeDrafts(await store.select(id)) } catch { store.error = 'No se pudo abrir el control de hosting.' }
}
async function load(page = 1) {
  await store.search(search.value, page, projectFilter.value)
}
function queueSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => load(), 250)
}
function advanceDraftVersions(previous) {
  for (const mode of modes) {
    if (draft.value[mode.key].version === previous) draft.value[mode.key].version = store.selected.version
  }
}
async function changeMode(key, enabled) {
  const previous = store.selected.version
  if (await store.save('mode', { expected_version: previous, mode: enabled ? key : 'normal' })) advanceDraftVersions(previous)
}
async function saveMessage(key) {
  const item = draft.value[key]
  if (await store.save('message', { expected_version: item.version, message_mode: key, title: item.title, text: item.text })) {
    advanceDraftVersions(item.version)
  }
}
async function refresh() {
  try { await store.refresh() } catch { store.error = 'No se pudo actualizar la confirmación de producción.' }
}
function reloadMessages() {
  // Explicit recovery discards drafts only when the operator chooses it.
  if (store.selected) {
    delete drafts[store.selected.id]
    initializeDrafts(store.selected)
    store.conflict = false
  }
}
onMounted(async () => {
  await load()
  if (store.records.length === 1) await select(store.records[0].id)
  timer = setInterval(refresh, 10000)
})
onBeforeUnmount(() => { clearInterval(timer); clearTimeout(searchTimer) })
</script>

<template>
  <div class="mx-auto w-full max-w-5xl space-y-6" data-testid="hosting-control-page">
    <NuxtLink to="/panel/projects" class="text-text-brand underline">Volver a Proyectos</NuxtLink>
    <header>
      <h1 class="text-2xl font-light text-text-default">Control de hosting</h1>
      <p class="mt-2 text-sm text-text-muted">Aviso visual por producción. La aplicación conserva sus servicios y datos.</p>
    </header>
    <div class="grid gap-3 sm:grid-cols-2">
      <BaseInput v-model="search" placeholder="Buscar proyecto o dominio" aria-label="Buscar producción" data-testid="hosting-search" @update:model-value="queueSearch" />
      <BaseDropdown :items="options" align="left" width="w-full">
        <template #trigger>
          <BaseButton variant="secondary" class="w-full" :disabled="store.saving" disabled-reason="Espera el guardado en curso antes de cambiar de producción." data-testid="hosting-selector">{{ store.selected?.name || 'Seleccionar producción' }}</BaseButton>
        </template>
      </BaseDropdown>
    </div>
    <div class="flex flex-wrap items-center gap-3">
      <BaseButton v-if="projectFilter" variant="link" @click="projectFilter = ''; load()">Ver todas las producciones</BaseButton>
      <BaseButton variant="secondary" :disabled="store.page <= 1 || store.loading" disabled-reason="No hay página anterior disponible." @click="load(store.page - 1)">Anterior</BaseButton>
      <span class="text-sm text-text-muted">Página {{ store.page }} de {{ store.pages }}</span>
      <BaseButton variant="secondary" :disabled="store.page >= store.pages || store.loading" disabled-reason="No hay más resultados disponibles." @click="load(store.page + 1)">Siguiente</BaseButton>
    </div>
    <p v-if="store.loading" role="status" class="text-text-muted">Consultando producciones…</p>
    <BaseAlert v-if="store.error" variant="danger" role="alert" data-testid="hosting-error">{{ store.error }}</BaseAlert>
    <BaseButton v-if="store.conflict" variant="secondary" @click="refresh">Consultar la versión vigente</BaseButton>
    <BaseButton v-if="store.conflict" variant="secondary" @click="reloadMessages">Descartar borradores y cargar mensajes consultados</BaseButton>
    <BaseEmptyState v-if="!store.loading && !store.records.length" title="Sin producciones registradas" description="Revisa el filtro o completa el registro del inventario y su integración." />

    <template v-if="store.selected && draft">
      <section class="rounded-xl border border-border-default bg-surface p-5 space-y-3" aria-label="Destino de producción">
        <h2 class="text-lg font-semibold text-text-default">{{ store.selected.name }}</h2>
        <p class="text-sm text-text-muted">{{ store.selected.client || 'Sin vínculo comercial' }} · {{ store.selected.server }} · Producción</p>
        <p class="font-medium text-text-default" data-testid="hosting-configured-mode">Configurado: {{ modeLabels[store.selected.mode] }}</p>
        <div v-for="target in store.selected.targets" :key="target.key" class="space-y-1 border-t border-border-muted pt-3">
          <p v-for="origin in target.origins" :key="origin" class="break-all text-sm text-text-default">{{ origin }}</p>
          <p class="text-sm text-text-muted" :data-testid="`hosting-status-${target.key}`">{{ statusLabels[target.state] }}</p>
          <p v-if="target.acknowledged_at" class="text-xs text-text-subtle">Última confirmación: {{ new Date(target.acknowledged_at).toLocaleString() }} · versión {{ target.acknowledged_version }}</p>
          <p v-if="target.error" class="text-sm text-danger-strong">{{ target.error }}</p>
        </div>
        <BaseButton variant="secondary" @click="refresh">Actualizar confirmación</BaseButton>
      </section>
      <p class="text-sm text-text-muted">Activar un modo desactiva el otro. Ambos apagados restablecen el funcionamiento normal. El cambio puede tardar hasta 30 segundos en una producción conectada.</p>
      <div class="grid gap-5 lg:grid-cols-2">
        <section v-for="mode in modes" :key="mode.key" class="min-w-0 rounded-xl border border-border-default bg-surface p-5 space-y-4">
          <div class="flex items-center justify-between gap-3">
            <h2 class="font-semibold text-text-default">{{ mode.label }}</h2>
            <BaseToggle :model-value="store.selected.mode === mode.key" :aria-label="mode.label" :disabled="store.saving" disabled-reason="Espera a que termine el guardado." :data-testid="`hosting-switch-${mode.key}`" @update:model-value="changeMode(mode.key, $event)" />
          </div>
          <BaseFormField :label="`Título de ${mode.label.toLowerCase()}`">
            <BaseInput v-model="draft[mode.key].title" :maxlength="200" :aria-label="`Título de ${mode.label.toLowerCase()}`" :data-testid="`hosting-title-${mode.key}`" />
          </BaseFormField>
          <BaseFormField :label="`Texto de ${mode.label.toLowerCase()}`">
            <BaseTextarea v-model="draft[mode.key].text" :maxlength="2000" :rows="5" :aria-label="`Texto de ${mode.label.toLowerCase()}`" :data-testid="`hosting-text-${mode.key}`" />
          </BaseFormField>
          <div class="rounded-lg border border-border-muted bg-surface-raised p-4 text-text-default" aria-label="Vista previa">
            <p class="font-semibold break-words">{{ draft[mode.key].title }}</p>
            <p class="mt-2 whitespace-pre-wrap break-words text-sm">{{ draft[mode.key].text }}</p>
          </div>
          <BaseButton variant="primary" :disabled="store.saving || !draft[mode.key].title.trim() || !draft[mode.key].text.trim()" disabled-reason="Completa título y texto, y espera cualquier guardado en curso." :data-testid="`hosting-save-${mode.key}`" @click="saveMessage(mode.key)">Guardar mensaje</BaseButton>
          <p class="text-xs text-text-subtle">Guardar este mensaje no cambia el modo ni el otro mensaje.</p>
        </section>
      </div>
      <section class="space-y-3" aria-label="Historial de hosting">
        <h2 class="text-lg font-semibold text-text-default">Historial</h2>
        <p v-if="!store.events.length" class="text-sm text-text-muted">Sin cambios registrados.</p>
        <article v-for="event in store.events" :key="event.id" class="rounded-lg border border-border-muted bg-surface p-4 text-sm text-text-default">
          <p>{{ event.actor }} · {{ event.source }} · {{ new Date(event.at).toLocaleString() }}</p>
          <p>Versión {{ event.version }} · {{ modeLabels[event.before.mode] }} → {{ modeLabels[event.after.mode] }}</p>
          <details class="mt-2"><summary>Ver mensajes anteriores y nuevos</summary><pre class="mt-2 whitespace-pre-wrap break-words text-xs">{{ JSON.stringify({ antes: event.before, después: event.after }, null, 2) }}</pre></details>
        </article>
      </section>
    </template>
  </div>
</template>
