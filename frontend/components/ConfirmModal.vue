<template>
  <BaseModal
    :model-value="modelValue"
    :size="size"
    :kind="size === 'md' ? 'confirm' : ''"
    :close-on-backdrop="!hideCancel && !loading"
    :close-on-esc="!hideCancel && !loading"
    @update:model-value="(v) => !v && handleCancel()"
  >
    <!-- Header -->
    <div class="px-6 pt-6 pb-2">
      <div class="flex items-start gap-4">
        <div
          class="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
          :class="variantClasses.iconBg"
        >
          <component :is="variantIcon" class="w-5 h-5" :class="variantClasses.iconColor" />
        </div>
        <div class="flex-1 min-w-0">
          <h3 class="text-lg font-bold text-text-default">{{ title }}</h3>
          <p class="mt-1 text-sm text-text-muted leading-relaxed">{{ message }}</p>

          <!--
            Detalle estructurado del alcance (p. ej. la lista de registros que
            una acción masiva va a tocar). Va entre el mensaje y la reja: lo
            que se va a cambiar se lee antes de poder confirmarlo.
          -->
          <div v-if="$slots.default" class="mt-3" data-testid="confirm-modal-detail">
            <slot />
          </div>

          <!--
            La salida va ANTES del campo de confirmación, no después: tiene que
            estar en el camino de lectura antes de que el usuario llegue a la reja.
          -->
          <div
            v-if="secondaryHint"
            class="mt-3 rounded-lg border border-border-muted bg-surface-muted px-3 py-2"
            data-testid="confirm-modal-secondary-hint"
          >
            <p class="text-xs text-text-muted leading-relaxed">{{ secondaryHint }}</p>
          </div>

          <div v-if="requireTypeText" class="mt-4">
            <label class="block text-xs text-text-muted mb-1.5">
              Escribe <span class="font-mono font-bold text-text-default">{{ requireTypeText }}</span> para confirmar
            </label>
            <input
              ref="typeInputRef"
              v-model="typedValue"
              type="text"
              autocomplete="off"
              spellcheck="false"
              data-testid="confirm-type-input"
              :placeholder="requireTypeText"
              class="w-full px-3 py-2 text-sm font-mono text-input-text bg-input-bg border border-input-border placeholder:text-text-subtle rounded-lg focus:outline-none focus:ring-2 focus:ring-danger-strong/40 focus:border-danger-strong/60"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <template #footer>
      <BaseModalActions>
        <BaseButton
          v-if="!hideCancel"
          variant="ghost"
          size="md"
          :disabled="loading"
          @click="handleCancel"
        >
          {{ cancelText }}
        </BaseButton>
        <!--
          Entre Cancelar y Confirmar: el destructivo se queda a la derecha.
          Nunca se deshabilita con `canConfirm` — es una salida, no un paso más.
        -->
        <BaseButton
          v-if="secondaryText"
          :variant="secondaryVariant"
          size="md"
          :disabled="loading"
          data-testid="confirm-modal-secondary"
          @click="handleSecondary"
        >
          {{ secondaryText }}
        </BaseButton>
        <BaseButton
          :variant="variant === 'danger' ? 'danger' : 'primary'"
          size="md"
          data-testid="confirm-modal-confirm"
          :disabled="!canConfirm || loading"
          :loading="loading"
          @click="handleConfirm"
        >
          {{ confirmText }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from '@heroicons/vue/24/outline'
import { oneOf } from './base/propValidators'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: 'Confirmar acción' },
  message: { type: String, default: '¿Estás seguro de que deseas continuar?' },
  confirmText: { type: String, default: 'Confirmar' },
  cancelText: { type: String, default: 'Cancelar' },
  variant: {
    type: String,
    default: 'warning',
    validator: oneOf(['warning', 'danger', 'info']),
  },
  requireTypeText: { type: String, default: '' },
  hideCancel: { type: Boolean, default: false },
  // Ancho del diálogo, reenviado a BaseModal. Sólo lo suben los confirms que
  // llevan detalle en el slot; el resto se queda en el 'md' de siempre.
  size: {
    type: String,
    default: 'md',
    validator: oneOf(['sm', 'md', 'lg', 'xl', '2xl', '5xl', 'full']),
  },
  // Acción alternativa no destructiva. Opcional: sin `secondaryText` el modal
  // se comporta exactamente como antes para todos los call sites existentes.
  secondaryText: { type: String, default: '' },
  secondaryVariant: {
    type: String,
    default: 'secondary',
    validator: oneOf(['secondary', 'ghost', 'primary']),
  },
  secondaryHint: { type: String, default: '' },
  // Acción de confirmación en vuelo (opt-in del composable): el botón gira,
  // el resto se bloquea y el modal no se puede cerrar hasta que termine.
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel', 'secondary'])

const typeInputRef = ref(null)
const typedValue = ref('')

const canConfirm = computed(() => {
  if (!props.requireTypeText) return true
  return typedValue.value === props.requireTypeText
})

const VARIANTS = {
  warning: { iconBg: 'bg-warning-soft', iconColor: 'text-warning-strong', icon: ExclamationTriangleIcon },
  danger: { iconBg: 'bg-danger-soft', iconColor: 'text-danger-strong', icon: ExclamationCircleIcon },
  info: { iconBg: 'bg-primary-soft', iconColor: 'text-text-brand', icon: InformationCircleIcon },
}

const variantClasses = computed(() => VARIANTS[props.variant] || VARIANTS.warning)
const variantIcon = computed(() => variantClasses.value.icon)

function handleConfirm() {
  if (!canConfirm.value) return
  emit('confirm')
  emit('update:modelValue', false)
}

function handleSecondary() {
  emit('secondary')
  emit('update:modelValue', false)
}

function handleCancel() {
  if (props.loading) return
  emit('cancel')
  emit('update:modelValue', false)
}

watch(() => props.modelValue, (val) => {
  typedValue.value = ''
  if (val && props.requireTypeText) {
    nextTick(() => typeInputRef.value?.focus())
  }
})
</script>
