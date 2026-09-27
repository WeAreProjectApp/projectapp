<script setup>
import { computed, ref, watch } from 'vue'
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  item: { type: Object, default: null },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const targetClientId = ref(null)
const targetClient = ref(null)

const isSameClient = computed(() => (
  targetClientId.value != null
  && Number(targetClientId.value) === Number(props.item?.sourceClientId)
))

const canConfirm = computed(() => Boolean(
  targetClientId.value != null && targetClient.value && !isSameClient.value && !props.busy,
))

const confirmBlockReason = computed(() => {
  if (props.busy) return ''
  if (targetClientId.value == null || !targetClient.value) return 'Elige el cliente de destino.'
  if (isSameClient.value) return 'Elige un cliente distinto al actual.'
  return ''
})

watch(() => props.modelValue, (isOpen) => {
  if (!isOpen) return
  targetClientId.value = null
  targetClient.value = null
})

const close = () => emit('update:modelValue', false)

const onClientSelect = (client) => {
  targetClient.value = client
}

const confirm = () => {
  if (!canConfirm.value) return
  emit('confirm', {
    targetClientId: Number(targetClientId.value),
    targetName: targetClient.value.name || targetClient.value.email || 'el cliente elegido',
  })
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    kind="confirm"
    title-id="client-reassign-title"
    @close="close"
  >
    <div class="px-6 pt-6 pb-2">
      <h3 id="client-reassign-title" class="break-words text-lg font-bold text-text-default">
        Mover {{ item?.type === 'proposal' ? 'propuesta' : 'diagnóstico' }}
      </h3>
      <p class="mt-1 break-words text-sm text-text-muted">{{ item?.title }}</p>
      <p class="mt-1 text-xs text-text-subtle">Actualmente pertenece a {{ item?.sourceClientName }}.</p>
    </div>

    <div class="space-y-4 px-6 py-4" data-testid="client-reassign-modal">
      <BaseFormField label="Cliente destino" required>
        <ClientAutocomplete
          v-model="targetClientId"
          test-id="client-reassign-target"
          placeholder="Buscar otro cliente..."
          :show-linked-hint="false"
          @select="onClientSelect"
        />
      </BaseFormField>

      <BaseAlert v-if="isSameClient" variant="warning">
        Elige un cliente distinto al actual.
      </BaseAlert>
    </div>

    <template #footer>
      <BaseModalActions>
        <BaseButton variant="secondary" size="md" @click="close">Cancelar</BaseButton>
        <BaseControlGate
          :reasons="confirmBlockReason ? [confirmBlockReason] : []"
          label="Mover no disponible"
          align="end"
        >
          <template #default="{ describedBy }">
            <BaseButton
              variant="primary"
              size="md"
              :loading="busy"
              :disabled="Boolean(confirmBlockReason)"
              :disabled-reason="confirmBlockReason"
              :aria-describedby="describedBy"
              data-testid="client-reassign-confirm"
              @click="confirm"
            >
              {{ busy ? 'Moviendo...' : 'Mover a otro cliente' }}
            </BaseButton>
          </template>
        </BaseControlGate>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
