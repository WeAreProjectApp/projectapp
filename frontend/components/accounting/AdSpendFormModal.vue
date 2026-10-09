<script setup>
import EntityHistorySection from '~/components/history/EntityHistorySection.vue';
import { useId, computed, ref, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'submit'])

const isEdit = computed(() => !!props.record)
const title = computed(() => (isEdit.value ? 'Editar Gasto en Ads' : 'Nuevo Gasto en Ads'))

const platformOptions = [
  { value: 'facebook', label: 'Facebook Ads' },
  { value: 'google', label: 'Google Ads' },
  { value: 'other', label: 'Otro' },
]

function defaultForm() {
  return {
    spend_date: '',
    platform: 'facebook',
    origin_card: '',
    amount: '',
    notes: '',
  }
}

const form = ref(defaultForm())

watch(
  () => [props.open, props.record],
  () => {
    if (!props.open) return
    if (props.record) {
      form.value = {
        spend_date: props.record.spend_date ?? '',
        platform: props.record.platform ?? 'facebook',
        origin_card: props.record.origin_card ?? '',
        amount: props.record.amount ?? '',
        notes: props.record.notes ?? '',
      }
    } else {
      form.value = defaultForm()
    }
  },
  { immediate: true },
)

function onSubmit() {
  const payload = {
    spend_date: form.value.spend_date,
    platform: form.value.platform,
    amount: form.value.amount,
  }
  payload.origin_card = form.value.origin_card
  payload.notes = form.value.notes
  emit('submit', payload)
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="form" title-id="ad-spend-form-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="ad-spend-form-title" class="text-lg font-bold text-text-default">{{ title }}</h3>
    </div>
    <EntityHistorySection v-if="open && record?.id" entity-type="ads" :object-id="record.id" class="mx-5" />
    <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Fecha" required>
          <BaseInput v-model="form.spend_date" type="date" required />
        </BaseFormField>
        <BaseFormField label="Plataforma">
          <BaseSelect v-model="form.platform" :options="platformOptions" />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Tarjeta origen">
          <BaseInput v-model="form.origin_card" placeholder="T.C 0655" />
        </BaseFormField>
        <BaseFormField label="Valor" required>
          <BaseCurrencyInput v-model="form.amount" required />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormField label="Notas">
        <BaseTextarea v-model="form.notes" :rows="3" />
      </BaseFormField>

    </form>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="secondary" @click="emit('close')">
          Cancelar
        </BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          :disabled="saving"
          data-testid="ad-spend-form-submit"
        >
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
