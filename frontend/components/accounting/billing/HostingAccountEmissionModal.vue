<script setup>
import { computed, ref, watch } from 'vue'
import BaseModal from '~/components/base/BaseModal.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import { get_request } from '~/stores/services/request_http'
const props = defineProps({ modelValue: { type: Boolean, default: false }, record: { type: Object, default: null }, message: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])
const localePath = useLocalePath()
const overview = ref(null), error = ref(''), loading = ref(false), paymentId = ref(null)
let sequence = 0
const source = computed(() => overview.value?.accounting_sources?.find(row => row.id === props.record?.id))
const projectId = computed(() => props.record?.project_id || props.record?.project)
const ready = computed(() => !projectId.value || (!loading.value && !error.value && source.value?.operational
  && (!overview.value?.subscription || (overview.value.subscription.associated && !!paymentId.value))))
watch(() => [props.modelValue, props.record?.id], async () => {
  const request = ++sequence
  overview.value = null; paymentId.value = null; error.value = ''; loading.value = false
  if (!props.modelValue || !projectId.value) return
  loading.value = true
  try { const result = await get_request(`admin/billing-context/projects/${projectId.value}/hosting/`); if (request === sequence) overview.value = result.data.overview }
  catch (err) { if (request === sequence) error.value = err.response?.data?.detail || 'No se pudo validar el contexto de hosting.' }
  finally { if (request === sequence) loading.value = false }
})
function confirm() { emit('confirm', { hosting_payment_id: paymentId.value }); emit('update:modelValue', false) }
function cancel() { emit('cancel'); emit('update:modelValue', false) }
</script>
<template>
  <BaseModal :model-value="modelValue" kind="confirm" @update:model-value="cancel">
    <div class="space-y-4 p-5">
      <h2 class="text-xl font-semibold">Enviar cuenta de cobro</h2><p class="text-sm">{{ message }}</p>
      <p v-if="loading" role="status">Verificando hosting del proyecto…</p>
      <p v-if="error" role="alert" class="text-danger-strong">{{ error }}</p>
      <template v-if="projectId && overview">
        <p v-if="!source?.operational" class="text-sm text-warning-strong">El origen debe asociarse explícitamente y seleccionarse como operativo.</p>
        <NuxtLink :to="localePath(`/panel/accounting/project-hosting/${projectId}`)" class="text-sm text-text-brand">Conciliar hosting del proyecto</NuxtLink>
        <label v-if="overview.subscription" class="block text-sm">Obligación de suscripción<select v-model="paymentId" class="mt-1 w-full rounded-xl border border-border-default bg-surface p-2"><option :value="null">Seleccionar explícitamente…</option><option v-for="payment in overview.subscription.payments" :key="payment.id" :value="payment.id">#{{ payment.id }} · {{ payment.billing_period_start }} — {{ payment.billing_period_end }} · {{ payment.amount }} · {{ payment.status }}</option></select></label>
      </template>
      <div class="flex flex-wrap justify-end gap-3"><BaseButton variant="secondary" @click="cancel">Cancelar</BaseButton><BaseButton :disabled="!ready" :loading="loading" disabled-reason="Asocia el origen operativo y selecciona la obligación existente cuando hay suscripción." @click="confirm">Enviar al cliente</BaseButton></div>
    </div>
  </BaseModal>
</template>
