<script setup>
import { computed, ref, watch } from 'vue'
import BaseButton from '~/components/base/BaseButton.vue'
import { get_request, create_request } from '~/stores/services/request_http'
import { INPUT_FIELD_BASE, INPUT_FIELD_SIZE } from '~/components/base/inputClasses'
const props = defineProps({ projectId: { type: [String, Number], required: true } })
const localePath = useLocalePath()
const inventory = ref(null), overview = ref(null), error = ref(''), loading = ref(false), saving = ref(false)
const identity = ref({ subscription_id: null, hosting_record_ids: [], operational_record_id: null, reason: '' })
const evidence = ref({ group_id: null, label: '', payment_ids: [], cycle_ids: [], document_ids: [], reason: '' })
const preview = ref(null), previewType = ref('')
const fieldClass = `${INPUT_FIELD_BASE} ${INPUT_FIELD_SIZE.md || ''}`
const cycles = computed(() => (overview.value?.accounting_sources || []).flatMap(row => row.cycles))
let sequence = 0, mutationSequence = 0
async function load() {
  const request = ++sequence
  mutationSequence += 1
  loading.value = true; saving.value = false; inventory.value = null; overview.value = null; preview.value = null; error.value = ''
  try {
    const result = await get_request(`admin/billing-context/projects/${props.projectId}/hosting/`)
    if (request !== sequence) return
    inventory.value = result.data.inventory; overview.value = result.data.overview
    const current = inventory.value.hosting
    identity.value = { subscription_id: current?.subscription_id || null, hosting_record_ids: current?.hosting_record_ids || [], operational_record_id: current?.operational_record_id || null, reason: '' }
    evidence.value = { group_id: null, label: '', payment_ids: [], cycle_ids: [], document_ids: [], reason: '' }
  } catch (err) { if (request === sequence) error.value = err.response?.data?.detail || 'No se pudo cargar el inventario.' }
  finally { if (request === sequence) loading.value = false }
}
function editGroup(id) {
  const group = overview.value?.evidence_groups.find(row => row.id === Number(id))
  evidence.value = { group_id: group?.id || null, label: group?.label || '', reason: '',
    payment_ids: group?.evidence.filter(row => row.kind === 'payment').map(row => row.id) || [],
    cycle_ids: group?.evidence.filter(row => row.kind === 'cycle').map(row => row.id) || [],
    document_ids: group?.evidence.filter(row => row.kind === 'account').map(row => row.id) || [] }
}
async function review(type) {
  if (!inventory.value || saving.value) return
  const request = ++mutationSequence
  const projectId = props.projectId
  saving.value = true; error.value = ''; preview.value = null
  const data = { ...(type === 'identity' ? identity.value : evidence.value), expected_version: inventory.value.version }
  const payload = JSON.parse(JSON.stringify(data))
  try {
    const result = await create_request(`admin/billing-context/projects/${projectId}/${type === 'identity' ? 'hosting' : 'evidence'}/?preview=1`, payload)
    if (request !== mutationSequence) return
    preview.value = { result: result.data, payload }; previewType.value = type
  } catch (err) { if (request === mutationSequence) error.value = err.response?.data?.detail || 'No se pudo previsualizar la conciliación.' }
  finally { if (request === mutationSequence) saving.value = false }
}
async function apply() {
  const current = preview.value
  if (!current || saving.value) return
  const request = ++mutationSequence
  const projectId = props.projectId
  saving.value = true; error.value = ''
  try {
    await create_request(`admin/billing-context/projects/${projectId}/${previewType.value === 'identity' ? 'hosting' : 'evidence'}/`, current.payload)
    if (request === mutationSequence) await load()
  } catch (err) { if (request === mutationSequence) error.value = err.response?.data?.detail || 'No se pudo aplicar. Actualiza el inventario si cambió.' }
  finally { if (request === mutationSequence) saving.value = false }
}
watch([identity, evidence], () => { preview.value = null; mutationSequence += 1; saving.value = false }, { deep: true })
watch(() => props.projectId, load, { immediate: true })
</script>
<template>
  <section class="space-y-5" data-testid="hosting-reconciliation">
    <h1 class="text-2xl font-semibold text-text-default">Conciliación del hosting del proyecto</h1>
    <p class="text-sm text-text-muted">Las asociaciones conservan cobros, pagos, ciclos y PDF. No registran pagos ni confirman equivalencias por texto, fechas o importes.</p>
    <p v-if="loading" role="status">Cargando inventario…</p>
    <p v-if="error" role="alert" class="text-danger-strong">{{ error }}</p>
    <BaseButton variant="secondary" @click="load">Actualizar inventario</BaseButton>
    <template v-if="inventory">
      <h2 class="font-semibold">{{ inventory.project_name }} · versión {{ inventory.version }}</h2>
      <section class="space-y-2 rounded-xl border border-border-default p-4">
        <h3 class="font-semibold">Orígenes y contradicciones</h3>
        <p v-if="!inventory.accounting_sources.length" class="text-sm text-text-muted">Sin origen contable registrado.</p>
        <p v-for="source in inventory.accounting_sources" :key="source.id" class="text-sm">#{{ source.id }} · {{ source.domain_url || 'Sin dominio' }} · {{ source.payment_modality }} · {{ source.payment_per_cycle }} · {{ source.mapped_hosting_id ? 'Asociado' : 'Pendiente de asociar' }}<span v-if="source.conflicts.length" class="block text-danger-strong">{{ source.conflicts.join(' ') }}</span></p>
      </section>
      <form class="space-y-3 rounded-xl border border-border-default p-4" @submit.prevent="review('identity')">
        <h3 class="font-semibold">Un único hosting del proyecto</h3>
        <label class="block text-sm">Suscripción de plataforma<select v-model="identity.subscription_id" :disabled="!!inventory.hosting?.subscription_id" title="Una suscripción ya asociada conserva su historia y no se reemplaza." :class="fieldClass"><option :value="null">Sin asociación</option><option v-for="sub in inventory.subscriptions" :key="sub.id" :value="sub.id">#{{ sub.id }} · {{ sub.plan }} · {{ sub.status }} · {{ sub.billing_amount }}</option></select></label>
        <fieldset class="space-y-2"><legend class="text-sm">Registros contables asociados (incluye históricos)</legend><label v-for="source in inventory.accounting_sources" :key="source.id" class="flex items-center gap-2 text-sm"><input v-model="identity.hosting_record_ids" type="checkbox" :value="source.id" :disabled="!!source.mapped_hosting_id || !!source.conflicts.length" :title="source.conflicts.length ? source.conflicts.join(' ') : 'Las asociaciones históricas se conservan.'" />#{{ source.id }} · {{ source.domain_url || 'Sin dominio' }}</label><p class="text-xs text-text-muted">Se agregan orígenes verificados y se conservan las asociaciones históricas. El origen operativo se elige por separado.</p></fieldset>
        <label class="block text-sm">Origen contable operativo<select v-model="identity.operational_record_id" :class="fieldClass"><option :value="null">Pendiente de seleccionar</option><option v-for="source in inventory.accounting_sources" :key="source.id" :value="source.id">#{{ source.id }} · {{ source.domain_url || 'Sin dominio' }}</option></select></label>
        <label class="block text-sm">Razón<textarea v-model="identity.reason" required :class="fieldClass" /></label>
        <BaseButton type="submit" :loading="saving" textPolicy="wrap">Previsualizar asociación</BaseButton>
      </form>
      <section v-if="inventory.pending_account_ids.length" class="space-y-2 rounded-xl border border-border-default p-4">
        <h3 class="font-semibold">Cuentas históricas pendientes de asociar</h3>
        <NuxtLink v-for="id in inventory.pending_account_ids" :key="id" :to="localePath(`/panel/accounting/collection-context/${id}`)" class="mr-4 inline-block text-text-brand">Cuenta #{{ id }}</NuxtLink>
      </section>
      <form v-if="inventory.hosting" class="space-y-3 rounded-xl border border-border-default p-4" @submit.prevent="review('evidence')">
        <h3 class="font-semibold">Equivalencia explícita de evidencias</h3>
        <label class="block text-sm">Grupo<select :value="evidence.group_id || ''" :class="fieldClass" @change="editGroup($event.target.value)"><option value="">Nuevo grupo</option><option v-for="group in overview.evidence_groups" :key="group.id" :value="group.id">#{{ group.id }} · {{ group.label }}</option></select></label>
        <label class="block text-sm">Nombre de la obligación<input v-model="evidence.label" required :class="fieldClass" /></label>
        <fieldset class="space-y-2"><legend class="text-sm">Pagos existentes de suscripción</legend><label v-for="payment in overview.subscription?.payments || []" :key="payment.id" class="flex items-center gap-2 text-sm"><input v-model="evidence.payment_ids" type="checkbox" :value="payment.id" />#{{ payment.id }} · {{ payment.billing_period_start }} — {{ payment.billing_period_end }} · {{ payment.amount }} · {{ payment.status }}</label></fieldset>
        <fieldset class="space-y-2"><legend class="text-sm">Ciclos contables pagados existentes</legend><label v-for="cycle in cycles" :key="cycle.id" class="flex items-center gap-2 text-sm"><input v-model="evidence.cycle_ids" type="checkbox" :value="cycle.id" />#{{ cycle.id }} · origen #{{ cycle.hosting_record_id }} · {{ cycle.paid_at }} · {{ cycle.amount }}</label></fieldset>
        <fieldset class="space-y-2"><legend class="text-sm">Cuentas asociadas al hosting</legend><label v-for="account in inventory.hosting_accounts" :key="account.id" class="flex items-center gap-2 text-sm"><input v-model="evidence.document_ids" type="checkbox" :value="account.id" />#{{ account.id }} · {{ account.public_number }} · {{ account.total }} · {{ account.commercial_status }}</label></fieldset>
        <label class="block text-sm">Razón y evidencia de equivalencia<textarea v-model="evidence.reason" required :class="fieldClass" /></label>
        <BaseButton type="submit" :loading="saving" textPolicy="wrap">Previsualizar conciliación de evidencias</BaseButton>
      </form>
      <section v-if="preview" class="space-y-3 rounded-xl border border-border-default bg-surface-muted p-4" data-testid="hosting-reconciliation-preview">
        <h3 class="font-semibold">Revisión de la decisión</h3>
        <pre class="overflow-x-auto whitespace-pre-wrap text-xs">{{ JSON.stringify(preview.result, null, 2) }}</pre>
        <p class="text-sm">Se guardará únicamente la asociación explícita de estas referencias.</p>
        <BaseButton :loading="saving" @click="apply">Aplicar conciliación</BaseButton>
      </section>
      <section class="space-y-2">
        <h3 class="font-semibold">Trazabilidad administrativa</h3>
        <p v-if="!inventory.events.length" class="text-sm text-text-muted">Sin decisiones administrativas registradas.</p>
        <p v-for="event in inventory.events" :key="event.id" class="text-sm">{{ event.created_at }} · {{ event.reason }} · responsable #{{ event.actor_id || 'Sistema' }}</p>
      </section>
    </template>
  </section>
</template>
