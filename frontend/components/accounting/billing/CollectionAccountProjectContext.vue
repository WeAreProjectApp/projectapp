<script setup>
import { computed, ref, watch } from 'vue'
import BillingContextFields from './BillingContextFields.vue'
import { get_request } from '~/stores/services/request_http'
const props = defineProps({
  projectId: { type: [String, Number], default: null },
  modelValue: { type: Object, required: true },
  validationError: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'valid', 'validation-message'])
const localePath = useLocalePath()
const options = ref(null)
const payments = ref([])
const error = ref('')
const loading = ref(false)
let sequence = 0
const validationMessage = computed(() => {
  if (!props.projectId) return ''
  if (loading.value) return 'Espera a que carguen las opciones de cobro del proyecto.'
  if (error.value) return error.value
  const context = props.modelValue
  if (!context.billing_nature) return 'En «Cobro del proyecto», elige si cobras un contrato o el hosting.'
  if (context.billing_nature === 'contract') {
    if (!options.value?.contracts?.length) return 'Este proyecto no tiene contratos disponibles para vincular el cobro. Agrega un contrato en los documentos del proyecto.'
    if (!options.value.contracts.some(row => Number(row.id) === Number(context.contract_id))) return 'Selecciona el contrato que corresponde a esta cuenta de cobro.'
    return ''
  }
  if (context.billing_nature === 'hosting') {
    if (!options.value?.hosting_id) return 'Asocia el hosting al proyecto desde «Conciliar hosting del proyecto» antes de emitir esta cuenta.'
    if (Number(context.project_hosting_id) !== Number(options.value.hosting_id)) return 'Selecciona el hosting del proyecto para esta cuenta de cobro.'
    if (payments.value.length && !payments.value.some(row => Number(row.id) === Number(context.hosting_payment_id))) return 'Selecciona el período de hosting que estás cobrando.'
    return ''
  }
  return 'Elige un tipo de cobro válido: contrato o hosting.'
})
const valid = computed(() => !validationMessage.value)
watch(valid, value => emit('valid', value), { immediate: true })
watch(validationMessage, value => emit('validation-message', value), { immediate: true })
async function load(id, previousId) {
  const request = ++sequence
  options.value = null; payments.value = []; error.value = ''; loading.value = true
  // Clear links when changing project, but preserve the reviewed choice when
  // this component remounts on returning from the preview.
  if (!id || (previousId !== undefined && Number(previousId) !== Number(id))) emit('update:modelValue', {})
  if (!id) { loading.value = false; return }
  try {
    const [a, b] = await Promise.all([
      get_request(`admin/billing-context/projects/${id}/options/`),
      get_request(`admin/billing-context/projects/${id}/hosting/`),
    ])
    if (sequence !== request) return
    options.value = a.data
    const sub = b.data.overview?.subscription
    payments.value = sub?.associated ? sub.payments : []
  } catch (err) {
    if (sequence === request) error.value = err.response?.data?.detail || 'No se pudo consultar el contexto del proyecto.'
  } finally {
    if (sequence === request) loading.value = false
  }
}
watch(() => props.projectId, load, { immediate: true })
</script>
<template>
  <section v-if="projectId" class="space-y-2" data-testid="collection-form-project-context">
    <h4 class="text-sm font-semibold text-text-default">Cobro del proyecto</h4>
    <p class="text-xs text-text-muted">Indica qué estás cobrando y selecciona el contrato o el período de hosting al que corresponde.</p>
    <p v-if="loading" role="status" class="text-sm text-text-muted">Consultando vínculos del proyecto…</p>
    <div v-else-if="error" role="alert" class="text-sm text-danger-strong"><p>{{ error }}</p><button type="button" @click="load(projectId)">Reintentar</button></div>
    <BillingContextFields v-else :model-value="modelValue" :options="options" :payments="payments" @update:model-value="emit('update:modelValue', $event)" />
    <p v-if="validationError && !error" role="alert" class="text-sm text-danger-strong" data-testid="collection-form-project-context-error">{{ validationError }}</p>
    <NuxtLink :to="localePath(`/panel/accounting/project-hosting/${projectId}`)" class="text-sm text-text-brand">Conciliar hosting del proyecto</NuxtLink>
  </section>
</template>
