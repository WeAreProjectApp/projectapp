<script setup>
import { computed, ref, watch } from 'vue'
import BillingContextFields from './BillingContextFields.vue'
import { get_request } from '~/stores/services/request_http'
const props = defineProps({ projectId: { type: [String, Number], default: null }, modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue', 'valid'])
const localePath = useLocalePath()
const options = ref(null)
const payments = ref([])
const error = ref('')
const loading = ref(false)
let sequence = 0
const valid = computed(() => !props.projectId || (!loading.value && !error.value && (
  props.modelValue.billing_nature === 'contract' && !!props.modelValue.contract_id
  || props.modelValue.billing_nature === 'hosting' && !!props.modelValue.project_hosting_id
     && (!payments.value.length || !!props.modelValue.hosting_payment_id)
)))
watch(valid, value => emit('valid', value), { immediate: true })
async function load(id) {
  const request = ++sequence
  options.value = null; payments.value = []; error.value = ''; loading.value = true
  emit('update:modelValue', {})
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
  <section v-if="projectId" class="space-y-2">
    <p v-if="loading" role="status" class="text-sm text-text-muted">Consultando vínculos del proyecto…</p>
    <div v-else-if="error" role="alert" class="text-sm text-danger-strong"><p>{{ error }}</p><button type="button" @click="load(projectId)">Reintentar</button></div>
    <BillingContextFields v-else :model-value="modelValue" :options="options" :payments="payments" @update:model-value="emit('update:modelValue', $event)" />
    <NuxtLink :to="localePath(`/panel/accounting/project-hosting/${projectId}`)" class="text-sm text-text-brand">Conciliar hosting del proyecto</NuxtLink>
  </section>
</template>
