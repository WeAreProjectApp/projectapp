<script setup>
import { computed, onMounted } from 'vue'

import BaseToggle from '~/components/base/BaseToggle.vue'
import { usePanelNotify } from '~/composables/usePanelNotify'
import { useExplainerVideosStore } from '~/stores/explainer_videos'

const props = defineProps({
  /** Explainer id from useExplainerVideos(): which module's switch this row drives. */
  module: {
    type: String,
    required: true,
    validator: (value) => ['additional-modules', 'financing', 'proposal'].includes(value),
  },
  /** Locale namespace that holds the explainerVisibility* keys. */
  i18nNamespace: {
    type: String,
    required: true,
    validator: (value) => ['additionalModules', 'financing', 'proposalExplainer'].includes(value),
  },
  testId: { type: String, default: 'explainer' },
})

const { t } = useI18n()
const notify = usePanelNotify()
const store = useExplainerVideosStore()

const ns = computed(() => props.i18nNamespace)
const visible = computed(() => store.isVisible(props.module))
// Until the settings load the stored state is unknown, so the switch stays locked.
const disabled = computed(() => store.isUpdating || !store.settings)

onMounted(() => {
  if (!store.settings && !store.isLoading) store.fetchSettings()
})

async function changeVisibility(value) {
  const result = await store.setVisibility(props.module, value)
  if (result.success) {
    notify.success(t(`${ns.value}.${value ? 'explainerVisibilityOn' : 'explainerVisibilityOff'}`))
  } else {
    notify.error(t(`${ns.value}.explainerVisibilityError`))
  }
}
</script>

<template>
  <div
    :data-testid="`${testId}-visibility`"
    class="flex items-start justify-between gap-4 rounded-2xl border border-border-default bg-surface p-4 shadow-card"
  >
    <div class="min-w-0">
      <p class="text-sm font-medium text-text-default">{{ t(`${ns}.explainerVisibilityLabel`) }}</p>
      <p class="mt-1 text-xs leading-5 text-text-muted">{{ t(`${ns}.explainerVisibilityHelp`) }}</p>
    </div>
    <BaseToggle
      :model-value="visible"
      :disabled="disabled"
      disabled-reason="Espera a que termine de cargar o guardar la configuración."
      :aria-label="t(`${ns}.explainerVisibilityLabel`)"
      :data-testid="`${testId}-visibility-toggle`"
      @update:model-value="changeVisibility"
    />
  </div>
</template>
