<script setup>
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import { useEntityHistoryStore } from '~/stores/entity_history';
import HistoryValue from './HistoryValue.vue';
import BasePagination from '~/components/base/BasePagination.vue';

const props = defineProps({ entityType: { type: String, required: true }, objectId: { type: [Number, String], required: true } });
const store = useEntityHistoryStore();
const result = ref(null);
const order = ref('recent');
const page = ref(1);
const loading = ref(false);
const error = ref('');
const detail = ref(null);
const comparison = ref(null);
const selected = ref([]);
const revealed = ref({});
const busy = ref(false);
const retryAction = shallowRef(null);
let listGeneration = 0;
let detailGeneration = 0;
const actions = { created: 'Creado', updated: 'Modificado', deleted: 'Eliminado', baseline: 'Estado inicial del historial', sent_version: 'Versión enviada' };
const date = (value) => value ? new Date(value).toLocaleString('es-CO', { timeZone: 'America/Bogota' }) : '';
const rows = computed(() => comparison.value?.changes || detail.value?.changes || []);
const protectedLabel = (field) => {
  if (field.startsWith('access_notes.')) {
    return `nota: ${detail.value?.snapshot?.access_notes?.[field.split('.')[1]]?.title || 'Sin título'}`;
  }
  return `contraseña · ${field.includes('production') ? 'Producción' : field.includes('staging') ? 'Staging' : 'Anterior'}`;
};

function goToPage(value) {
  const target = Math.max(1, Math.min(Number(value), result.value?.num_pages || 1));
  if (loading.value || target === page.value) return;
  page.value = target;
  load();
}
const pagination = computed(() => ({
  currentPage: page.value, totalPages: result.value?.num_pages || 1,
  totalItems: result.value?.count || 0,
  rangeFrom: result.value?.count ? (page.value - 1) * 20 + 1 : 0,
  rangeTo: Math.min(page.value * 20, result.value?.count || 0),
  alwaysShow: true,
}));

async function load() {
  const current = ++listGeneration;
  loading.value = true;
  error.value = '';
  revealed.value = {};
  try {
    const response = await store.list(props.entityType, props.objectId, page.value, order.value);
    if (current === listGeneration) result.value = response;
  } catch {
    if (current === listGeneration) { error.value = 'No se pudo cargar el historial. Intenta de nuevo.'; retryAction.value = load; }
  } finally {
    if (current === listGeneration) loading.value = false;
  }
}

async function openVersion(id) {
  const current = ++detailGeneration;
  revealed.value = {};
  comparison.value = null;
  detail.value = null;
  busy.value = true;
  error.value = '';
  try {
    const response = await store.version(props.entityType, props.objectId, id);
    if (current === detailGeneration) detail.value = response;
  } catch {
    if (current === detailGeneration) { error.value = 'No se pudo consultar la versión. Intenta de nuevo.'; retryAction.value = () => openVersion(id); }
  } finally {
    if (current === detailGeneration) busy.value = false;
  }
}

function select(entry) {
  const existing = selected.value.findIndex((row) => row.id === entry.id);
  if (existing !== -1) selected.value.splice(existing, 1);
  else selected.value = [...selected.value.slice(-1), entry];
}

async function compare(ids) {
  comparison.value = null;
  const current = ++detailGeneration;
  revealed.value = {};
  busy.value = true;
  error.value = '';
  try {
    const response = await store.compare(props.entityType, props.objectId, ids[0], ids[1]);
    if (current === detailGeneration) comparison.value = response;
  } catch {
    if (current === detailGeneration) { error.value = 'No se pudieron comparar las versiones. Intenta de nuevo.'; retryAction.value = () => compare(ids); }
  } finally {
    if (current === detailGeneration) busy.value = false;
  }
}

async function reveal(field) {
  const current = detailGeneration;
  const revision = detail.value.id;
  if (field in revealed.value) { delete revealed.value[field]; return; }
  error.value = '';
  try {
    const response = await store.reveal(props.entityType, props.objectId, revision, field);
    if (current === detailGeneration && detail.value?.id === revision) revealed.value[field] = response.secret;
  } catch {
    if (current === detailGeneration) { error.value = 'No se pudo revelar este valor protegido.'; retryAction.value = () => reveal(field); }
  }
}

function clearDetail() {
  detailGeneration++;
  detail.value = null;
  comparison.value = null;
  revealed.value = {};
  busy.value = false;
  error.value = '';
  retryAction.value = null;
}
function compareSelected() {
  const ordered = [...selected.value].sort((a, b) => a.number - b.number);
  compare(ordered.map((entry) => entry.id));
}
watch(() => [props.entityType, props.objectId], () => {
  page.value = 1; result.value = null; selected.value = []; clearDetail(); load();
}, { immediate: true });
watch(order, () => { page.value = 1; load(); });
onBeforeUnmount(() => { listGeneration++; detailGeneration++; revealed.value = {}; });
</script>

<template>
  <section class="min-w-0 space-y-4 text-text-default" data-testid="entity-history">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold">Historial</h2>
        <p v-if="result?.latest_change" class="text-sm text-text-muted" data-testid="history-latest">
          Último cambio: {{ date(result.latest_change.occurred_at) }} · {{ result.latest_change.actor }}
        </p>
      </div>
      <label class="text-sm">Orden
        <select v-model="order" class="ml-2 rounded-lg border border-border-default bg-surface px-3 py-2 text-text-default" data-testid="history-order">
          <option value="recent">Más reciente primero</option><option value="oldest">Más antiguo primero</option>
        </select>
      </label>
    </div>
    <div v-if="error" role="alert" class="rounded-lg bg-danger-soft p-3 text-danger-strong">
      {{ error }} <BaseButton variant="secondary" size="sm" @click="retryAction?.()">Reintentar</BaseButton>
    </div>
    <p v-if="loading" role="status" class="text-sm text-text-muted">Cargando historial…</p>
    <p v-else-if="result && !result.count" class="text-sm text-text-muted">Todavía no hay cambios registrados. Los cambios anteriores al inicio del historial pueden no estar disponibles.</p>
    <div v-if="result?.last_sent_version" class="rounded-lg border border-border-muted p-3 text-sm">
      Última versión enviada: {{ date(result.last_sent_version.occurred_at) }}
      <BaseButton size="sm" variant="secondary" @click="openVersion(result.last_sent_version.id)">Consultar envío</BaseButton>
      <BaseButton v-if="detail?.complete && detail.id !== result.last_sent_version.id" size="sm" variant="secondary" @click="compare([result.last_sent_version.id, detail.id])">Comparar con envío</BaseButton>
    </div>
    <div v-if="selected.length" class="flex flex-wrap items-center gap-2 text-sm">
      <span>Versiones seleccionadas: {{ selected.map((row) => row.number).join(' y ') }}</span>
      <BaseButton v-if="selected.length === 2" variant="secondary" data-testid="history-compare" @click="compareSelected">Comparar versiones</BaseButton>
      <BaseButton variant="ghost" @click="selected = []">Limpiar selección</BaseButton>
    </div>
    <BasePagination v-if="result && !loading" v-bind="pagination" aria-label="Paginación del historial"
      @prev="goToPage(page - 1)" @next="goToPage(page + 1)" @go="goToPage" />
    <ol class="divide-y divide-border-muted">
      <li v-for="entry in result?.results || []" :key="entry.id" class="flex flex-wrap items-start gap-3 py-3" :data-testid="`history-entry-${entry.id}`">
        <label v-if="entry.complete" class="flex items-center gap-2 py-2 text-sm">
          <input type="checkbox" :checked="selected.some((row) => row.id === entry.id)" :aria-label="`Seleccionar versión ${entry.number}`" @change="select(entry)">
          v{{ entry.number }}
        </label>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium">{{ actions[entry.action] || 'Evento registrado' }} · {{ date(entry.occurred_at) }}</p>
          <p class="text-sm text-text-muted">{{ entry.actor }}{{ entry.source.startsWith('mcp:') ? ' · Integración' : '' }}</p>
          <p class="break-words text-xs text-text-muted">{{ entry.fields.map((field) => field.label).join(', ') }}</p>
          <p v-if="!entry.complete" class="text-xs text-text-subtle">Evento anterior sin versión completa.</p>
        </div>
        <BaseButton variant="secondary" size="sm" @click="openVersion(entry.id)">Consultar</BaseButton>
      </li>
    </ol>
    <BasePagination v-if="result && !loading" v-bind="pagination" aria-label="Paginación del historial al final"
      @prev="goToPage(page - 1)" @next="goToPage(page + 1)" @go="goToPage" />
    <p v-if="busy" role="status" class="text-sm text-text-muted">Consultando versión…</p>
    <div v-if="detail || comparison" class="space-y-4 rounded-xl border border-border-muted bg-surface-raised p-4" data-testid="history-version-detail">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="font-semibold">{{ comparison ? `Comparación v${comparison.from.number} → v${comparison.to.number}` : `Versión ${detail.number || 'histórica'}` }}</h3>
        <BaseButton variant="ghost" @click="clearDetail">Cerrar consulta</BaseButton>
      </div>
      <BaseButton v-if="detail?.previous_id && !comparison" variant="secondary" @click="compare([detail.previous_id, detail.id])">Comparar con la anterior</BaseButton>
      <p v-if="comparison && !rows.length" class="text-sm text-text-muted">No hay diferencias entre estas versiones.</p>
      <div v-for="change in rows" :key="change.field" class="space-y-2 border-b border-border-muted pb-3">
        <h4 class="text-sm font-semibold">{{ change.label }}</h4>
        <div class="grid min-w-0 gap-4 panel-landscape:grid-cols-2">
          <div class="min-w-0"><p class="text-xs text-text-muted">Antes</p><HistoryValue :value="change.old" /></div>
          <div class="min-w-0"><p class="text-xs text-text-muted">Después</p><HistoryValue :value="change.new" /></div>
        </div>
        <pre v-if="change.lines?.length" class="max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs">{{ change.lines.join('\n') }}</pre>
      </div>
      <BaseButton v-if="!comparison && (detail?.snapshot?.generated_file || detail?.snapshot?.pdf_file || detail?.snapshot?.archived_pdf)" as="a" :to="`/api/entity-history/${entityType}/${objectId}/versions/${detail.id}/file/`" target="_blank" rel="noopener noreferrer" variant="secondary">Ver PDF de esta versión</BaseButton>
      <details v-if="detail?.snapshot && !comparison" data-testid="history-full-version">
        <summary class="cursor-pointer py-2 font-medium">Ver versión completa</summary>
        <HistoryValue :value="detail.snapshot" :labels="detail.labels" />
      </details>
      <div v-if="detail?.protected_fields?.length && !comparison" class="space-y-3">
        <p class="text-sm text-text-muted">Valores protegidos de esta versión. Se ocultan al cerrar la consulta.</p>
        <div v-for="field in detail.protected_fields" :key="field" class="space-y-2">
          <BaseButton size="sm" variant="secondary" textPolicy="wrap" @click="reveal(field)">{{ field in revealed ? 'Ocultar' : 'Revelar' }} {{ protectedLabel(field) }}</BaseButton>
          <p v-if="field in revealed" class="whitespace-pre-wrap break-words text-sm" data-testid="history-revealed">{{ revealed[field] || 'Sin valor' }}</p>
        </div>
      </div>
    </div>
  </section>
</template>
