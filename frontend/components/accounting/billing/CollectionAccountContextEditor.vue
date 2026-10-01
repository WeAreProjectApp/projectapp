<script setup>
import { computed, ref, watch } from 'vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BillingContextFields from './BillingContextFields.vue'
import { get_request, patch_request } from '~/stores/services/request_http'
const props = defineProps({ accountId: { type: [String, Number], required: true }, projectId: { type: [String, Number], required: true } })
const emit = defineEmits(['saved'])
const options = ref(null), payments = ref([]), context = ref({}), version = ref(0), reason = ref('')
const error = ref(''), success = ref(''), loading = ref(false), saving = ref(false)
const valid = computed(() => context.value.billing_nature === 'contract' ? !!context.value.contract_id
  : context.value.billing_nature === 'hosting' && !!context.value.project_hosting_id)
let sequence = 0, saveSequence = 0
async function load() {
  const request = ++sequence
  saveSequence += 1
  loading.value = true; saving.value = false; options.value = null; context.value = {}; error.value = ''; success.value = ''
  try {
    const [a, b, c] = await Promise.all([
      get_request(`admin/billing-context/accounts/${props.accountId}/`),
      get_request(`admin/billing-context/projects/${props.projectId}/options/`),
      get_request(`admin/billing-context/projects/${props.projectId}/hosting/`),
    ])
    if (request !== sequence) return
    options.value = b.data; version.value = a.data.version
    context.value = { billing_nature: a.data.nature, contract_id: a.data.contract?.id || null,
                      amendment_id: a.data.amendment?.id || null, project_hosting_id: a.data.hosting_id || null }
    const sub = c.data.overview?.subscription
    payments.value = sub?.associated ? sub.payments : []
  } catch (err) {
    if (request === sequence) error.value = err.response?.data?.detail || 'No se pudo cargar la asociación.'
  } finally { if (request === sequence) loading.value = false }
}
async function save() {
  if (saving.value || !options.value || !valid.value || !reason.value.trim()) return
  const request = sequence
  const savingRequest = ++saveSequence
  saving.value = true; error.value = ''; success.value = ''
  try {
    await patch_request(`admin/billing-context/accounts/${props.accountId}/`, { ...context.value, expected_version: version.value, reason: reason.value })
    if (request !== sequence) return
    await load()
    if (request + 1 !== sequence) return
    reason.value = ''; success.value = 'Asociación guardada. El PDF y el snapshot financiero se conservan.'; emit('saved')
  } catch (err) { if (request === sequence) error.value = err.response?.data?.detail || 'No se pudo guardar. Actualiza si otro administrador cambió el contexto.' }
  finally { if (savingRequest === saveSequence) saving.value = false }
}
watch(() => [props.accountId, props.projectId], load, { immediate: true })
</script>
<template>
  <section class="space-y-3" data-testid="billing-context-editor">
    <h3 class="font-semibold text-text-default">Asociación del cobro al proyecto</h3>
    <p class="text-sm text-text-muted">La clasificación no modifica el documento emitido, sus importes ni sus pagos.</p>
    <p v-if="loading" role="status">Cargando asociación…</p>
    <form v-else class="space-y-3" @submit.prevent="save">
      <BillingContextFields v-model="context" :options="options" :payments="payments" />
      <label class="block text-sm text-text-default">Razón de la asociación o corrección<textarea v-model="reason" required class="mt-1 w-full rounded-xl border border-border-default bg-surface p-3" /></label>
      <BaseButton type="submit" :loading="saving" :disabled="!valid || !reason.trim()" disabled-reason="Selecciona naturaleza y vínculo, e indica la razón de la asociación.">Guardar asociación</BaseButton>
      <BaseButton variant="secondary" @click="load">Actualizar</BaseButton>
    </form>
    <p v-if="error" role="alert" class="text-danger-strong">{{ error }}</p>
    <p v-if="success" role="status" class="text-success-strong">{{ success }}</p>
  </section>
</template>
