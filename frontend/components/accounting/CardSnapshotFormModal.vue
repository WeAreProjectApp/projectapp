<script setup>
import EntityHistorySection from '~/components/history/EntityHistorySection.vue';
import { useId, computed, ref, watch } from 'vue'
import { formatMoney } from '~/utils/formatMoney'

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  saving: { type: Boolean, default: false },
  // Active catalog cards: [{ name, credit_limit }].
  cards: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'submit'])

const isEdit = computed(() => !!props.record)
const title = computed(() =>
  isEdit.value ? 'Editar Registro de Tarjeta' : 'Nuevo Registro de Tarjeta',
)

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function defaultForm() {
  return {
    snapshot_date: todayIso(),
    card_name: props.cards.length === 1 ? props.cards[0].name : '',
    available_amount: '',
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
        snapshot_date: props.record.snapshot_date ?? todayIso(),
        card_name: props.record.card_name ?? '',
        available_amount: props.record.available_amount ?? '',
        notes: props.record.notes ?? '',
      }
    } else {
      form.value = defaultForm()
    }
  },
  { immediate: true },
)

const cardOptions = computed(() => {
  const options = props.cards.map((card) => ({
    value: card.name,
    label: card.name,
  }))
  // A legacy record can reference a card missing from the catalog; keep
  // its own name selectable so edits don't force a card change.
  const current = props.record?.card_name
  if (current && !options.some((option) => option.value === current)) {
    options.push({ value: current, label: `${current} (fuera de catálogo)` })
  }
  return options
})

const selectedCard = computed(() =>
  props.cards.find((card) => card.name === form.value.card_name) || null,
)

const computedDebt = computed(() => {
  if (!selectedCard.value) return null
  const available = Number(form.value.available_amount)
  if (form.value.available_amount === '' || Number.isNaN(available)) return null
  return Number(selectedCard.value.credit_limit) - available
})

const debtPreview = computed(() => {
  if (!selectedCard.value) {
    return isEdit.value
      ? 'Tarjeta fuera de catálogo: la deuda registrada se mantiene.'
      : ''
  }
  const cupo = formatMoney(Number(selectedCard.value.credit_limit))
  if (computedDebt.value === null) return `Cupo ${cupo}`
  return `Deuda: ${formatMoney(computedDebt.value)} (cupo ${cupo} − disponible)`
})

const availableExceedsLimit = computed(() =>
  computedDebt.value !== null && computedDebt.value < 0,
)

function onSubmit() {
  if (availableExceedsLimit.value) return
  emit('submit', {
    snapshot_date: form.value.snapshot_date,
    card_name: form.value.card_name,
    available_amount: form.value.available_amount,
    notes: form.value.notes,
  })
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="form" title-id="card-snapshot-form-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="card-snapshot-form-title" class="text-lg font-bold text-text-default">{{ title }}</h3>
    </div>
    <EntityHistorySection v-if="open && record?.id" entity-type="card_snapshot" :object-id="record.id" class="mx-5" />
    <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Tarjeta" required>
          <BaseSelect
            v-model="form.card_name"
            :options="cardOptions"
            placeholder="Selecciona una tarjeta"
            required
            data-testid="card-snapshot-card-select"
          />
        </BaseFormField>
        <BaseFormField label="Fecha" required>
          <BaseInput v-model="form.snapshot_date" type="date" required />
        </BaseFormField>
      </BaseFormRow>

      <!-- Alone in a two-column row: an amount needs half the width. -->
      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Disponible" required>
          <BaseCurrencyInput v-model="form.available_amount" required />
        </BaseFormField>
        <template v-if="debtPreview" #help>
          <span
            id="card-snapshot-debt-preview"
            :class="availableExceedsLimit ? 'text-danger-strong' : 'text-text-subtle'"
            data-testid="card-snapshot-debt-preview"
          >
            {{ availableExceedsLimit
              ? 'El disponible no puede superar el cupo de la tarjeta.'
              : debtPreview }}
          </span>
        </template>
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
          :loading="saving"
          :disabled="availableExceedsLimit"
          disabled-reason="El disponible no puede superar el cupo de la tarjeta."
          :aria-describedby="availableExceedsLimit ? 'card-snapshot-debt-preview' : undefined"
          data-testid="card-snapshot-form-submit"
        >
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
