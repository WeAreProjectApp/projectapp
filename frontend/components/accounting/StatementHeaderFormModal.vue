<script setup>
import { useId, ref, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  statement: { type: Object, default: null },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'submit'])

function emptyForm() {
  return {
    purchases_total: '',
    previous_balance: '',
    payments_total: '',
    interest_and_fees: '',
    closing_balance: '',
    minimum_payment: '',
    due_date: '',
    notes: '',
  }
}

const form = ref(emptyForm())

watch(
  () => [props.open, props.statement],
  () => {
    if (!props.open || !props.statement) return
    form.value = {
      purchases_total: props.statement.purchases_total ?? '',
      previous_balance: props.statement.previous_balance ?? '',
      payments_total: props.statement.payments_total ?? '',
      interest_and_fees: props.statement.interest_and_fees ?? '',
      closing_balance: props.statement.closing_balance ?? '',
      minimum_payment: props.statement.minimum_payment ?? '',
      due_date: props.statement.due_date ?? '',
      notes: props.statement.notes ?? '',
    }
  },
  { immediate: true },
)

function nullable(value) {
  return value === '' || value === null ? null : value
}

function onSubmit() {
  emit('submit', {
    purchases_total: form.value.purchases_total,
    previous_balance: nullable(form.value.previous_balance),
    payments_total: nullable(form.value.payments_total),
    interest_and_fees: nullable(form.value.interest_and_fees),
    closing_balance: nullable(form.value.closing_balance),
    minimum_payment: nullable(form.value.minimum_payment),
    due_date: nullable(form.value.due_date),
    notes: form.value.notes,
  })
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="form" title-id="statement-header-form-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="statement-header-form-title" class="text-lg font-bold text-text-default">
        Editar encabezado del extracto
      </h3>
      <p v-if="statement" class="text-xs text-text-subtle mt-1">
        {{ statement.card_name }} · <span class="capitalize">{{ statement.period_label }}</span>
        — la tarjeta y el período no se pueden cambiar.
      </p>
    </div>
    <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
      <BaseFormRow :cols="3" :gap="4">
        <BaseFormField label="Total compras" required>
          <BaseCurrencyInput v-model="form.purchases_total" required data-testid="statement-header-purchases" />
        </BaseFormField>
        <BaseFormField label="Saldo anterior">
          <BaseCurrencyInput v-model="form.previous_balance" data-testid="statement-header-previous-balance" />
        </BaseFormField>
        <BaseFormField label="Pagos y abonos">
          <BaseCurrencyInput v-model="form.payments_total" data-testid="statement-header-payments-total" />
        </BaseFormField>
        <BaseFormField label="Intereses y comisiones">
          <BaseCurrencyInput v-model="form.interest_and_fees" data-testid="statement-header-interest-and-fees" />
        </BaseFormField>
        <BaseFormField label="Saldo de cierre">
          <BaseCurrencyInput v-model="form.closing_balance" data-testid="statement-header-closing-balance" />
        </BaseFormField>
        <BaseFormField label="Pago mínimo">
          <BaseCurrencyInput v-model="form.minimum_payment" data-testid="statement-header-minimum-payment" />
        </BaseFormField>
        <BaseFormField label="Fecha límite de pago">
          <BaseInput v-model="form.due_date" type="date" data-testid="statement-header-due-date" />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormField label="Notas">
        <BaseTextarea v-model="form.notes" :rows="2" />
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
          data-testid="statement-header-form-submit"
        >
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
