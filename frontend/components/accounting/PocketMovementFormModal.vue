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
const title = computed(() =>
  isEdit.value ? 'Editar Movimiento de bolsillo' : 'Nuevo Movimiento de bolsillo',
)

const directionOptions = [
  { value: 'in', label: 'Ingreso' },
  { value: 'out', label: 'Egreso' },
]

// For egresos the selector attributes the draw: pocket money is company
// money, so a partner option creates a company expense fully assigned to
// that partner (it always counts against the company utility).
const ledgerOptions = computed(() =>
  form.value.direction === 'out'
    ? [
        { value: 'company', label: 'Empresa' },
        { value: 'gustavo', label: 'Gustavo' },
        { value: 'carlos', label: 'Carlos' },
      ]
    : [
        { value: 'company', label: 'Empresa' },
        { value: 'gustavo', label: 'Personal Gustavo' },
        { value: 'carlos', label: 'Personal Carlos' },
      ],
)

const ledgerLabel = computed(() =>
  form.value.direction === 'out' ? 'Atribuir a' : 'Contabilidad',
)

// Egresos are what the pocket mostly records, so a new movement opens on the
// common case: no toggle to flip before saving, and no egreso filed as an
// ingreso by leaving the default untouched. Editing keeps whatever the record
// has (see the watch below).
function defaultForm() {
  return {
    concept: '',
    movement_date: '',
    direction: 'out',
    amount: '',
    ledger: 'company',
    notes: '',
  }
}

const form = ref(defaultForm())

const isLinked = computed(() => isEdit.value && !!props.record?.is_auto_managed)
// Historical movements (unlinked) have no mirrored record to assign a ledger to.
const showLedger = computed(() => !isEdit.value || isLinked.value)
const directionLocked = computed(() => isLinked.value)

watch(
  () => [props.open, props.record],
  () => {
    if (!props.open) return
    if (props.record) {
      form.value = {
        concept: props.record.concept ?? '',
        movement_date: props.record.movement_date ?? '',
        direction: props.record.direction ?? 'in',
        amount: props.record.amount ?? '',
        ledger: props.record.linked_ledger ?? 'company',
        notes: props.record.notes ?? '',
      }
    } else {
      form.value = defaultForm()
    }
  },
  { immediate: true },
)

// Pocket IN feeds the company pocket: personal ledgers only apply to egresos.
watch(
  () => form.value.direction,
  (direction) => {
    if (direction === 'in') form.value.ledger = 'company'
  },
)

function onSubmit() {
  const payload = {
    concept: form.value.concept,
    movement_date: form.value.movement_date,
    direction: form.value.direction,
    amount: form.value.amount,
  }
  if (showLedger.value) payload.ledger = form.value.ledger
  payload.notes = form.value.notes
  emit('submit', payload)
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="form" title-id="pocket-movement-form-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="pocket-movement-form-title" class="text-lg font-bold text-text-default">{{ title }}</h3>
    </div>
    <EntityHistorySection v-if="open && record?.id" entity-type="pocket" :object-id="record.id" class="mx-5" />
    <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
      <BaseFormField label="Concepto" required>
        <BaseInput v-model="form.concept" required />
      </BaseFormField>

      <BaseFormRow
        :cols="2"
        :gap="4"
        at="sm"
        :help="directionLocked ? 'La dirección se fija al crear el movimiento vinculado.' : ''"
      >
        <BaseFormField label="Fecha" required>
          <BaseInput v-model="form.movement_date" type="date" required />
        </BaseFormField>
        <BaseFormField label="Dirección" required>
          <BaseSegmented
            v-model="form.direction"
            :options="directionOptions"
            :disabled="directionLocked"
            disabled-reason="La dirección se fija al crear el movimiento vinculado."
            full-width
          />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormField v-if="showLedger" :label="ledgerLabel" required>
        <BaseSegmented
          v-model="form.ledger"
          :options="ledgerOptions"
          :disabled="form.direction === 'in'"
          disabled-reason="Los ingresos al bolsillo siempre son de la empresa."
          full-width
          data-testid="pocket-movement-ledger"
        />
        <p v-if="form.direction === 'in'" class="text-xs text-text-subtle mt-1">
          Los ingresos al bolsillo siempre son de la empresa.
        </p>
        <p v-else class="text-xs text-text-subtle mt-1">
          El egreso resta a la utilidad de la empresa: Empresa lo reparte
          50/50; Gustavo o Carlos lo registra como retiro de ese socio.
        </p>
      </BaseFormField>

      <BaseFormField label="Valor" required>
        <BaseCurrencyInput v-model="form.amount" required />
      </BaseFormField>

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
          data-testid="pocket-movement-form-submit"
        >
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
