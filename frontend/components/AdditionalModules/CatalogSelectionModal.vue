<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mode: { type: String, default: 'share' },
  categories: { type: Array, default: () => [] },
  modules: { type: Array, default: () => [] },
  clients: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  generatedUrl: { type: String, default: '' },
  /** Catalog-wide video switch: while off, no link shows the explainer. */
  catalogVideoVisible: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'submit'])
const { t } = useI18n()
const selectedIds = ref([])
const localError = ref('')
const copied = ref(false)
const autoRecipientLabel = ref('')
const form = reactive({ recipient_label: '', client_id: '', language: 'es', show_explainer_video: true })

const activeModules = computed(() => props.modules.filter((module) => (
  module.is_active && props.categories.find((category) => category.id === module.category)?.is_active
)))
const grouped = computed(() => props.categories.filter((category) => category.is_active).map((category) => ({
  ...category,
  modules: activeModules.value.filter((module) => module.category === category.id),
})).filter((category) => category.modules.length > 0))
const clientOptions = computed(() => [
  { value: '', label: t('additionalModules.noClient') },
  ...props.clients.map((client) => ({
    value: client.id,
    label: [client.name, client.company].filter(Boolean).join(' · ') || client.email,
  })),
])

watch(() => props.modelValue, (open) => {
  if (!open) return
  selectedIds.value = props.mode === 'pdf' ? activeModules.value.map((module) => module.id) : []
  form.recipient_label = ''
  form.client_id = ''
  form.language = 'es'
  form.show_explainer_video = true
  localError.value = ''
  copied.value = false
  autoRecipientLabel.value = ''
})

const localized = (value, field) => value?.[`${field}_${form.language}`] || ''

function selectClient(clientId) {
  const canAutofill = !form.recipient_label.trim()
    || form.recipient_label === autoRecipientLabel.value
  form.client_id = clientId
  const selected = props.clients.find((client) => String(client.id) === String(clientId))
  const label = selected
    ? [selected.name, selected.company].filter(Boolean).join(' · ') || selected.email
    : ''
  if (canAutofill) form.recipient_label = label
  autoRecipientLabel.value = label
}

function categorySelected(category) {
  return category.modules.every((module) => selectedIds.value.includes(module.id))
}

function toggleCategory(category, checked) {
  const ids = category.modules.map((module) => module.id)
  if (checked) {
    selectedIds.value = [...new Set([...selectedIds.value, ...ids])]
  } else {
    selectedIds.value = selectedIds.value.filter((id) => !ids.includes(id))
  }
}

function selectAll() {
  selectedIds.value = activeModules.value.map((module) => module.id)
}

function submit() {
  if (!selectedIds.value.length) {
    localError.value = t('additionalModules.selectAtLeastOne')
    return
  }
  if (props.mode === 'share' && !form.recipient_label.trim()) {
    localError.value = t('additionalModules.requiredFields')
    return
  }
  localError.value = ''
  emit('submit', props.mode === 'share' ? {
    recipient_label: form.recipient_label.trim(),
    client_id: form.client_id ? Number(form.client_id) : null,
    language: form.language,
    selected_module_ids: selectedIds.value,
    show_explainer_video: form.show_explainer_video,
  } : {
    language: form.language,
    module_ids: selectedIds.value,
    recipient_label: form.recipient_label.trim(),
  })
}

async function copyGeneratedUrl() {
  if (!props.generatedUrl) return
  await navigator.clipboard.writeText(props.generatedUrl)
  copied.value = true
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    kind="wizard"
    padding="none"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="flex min-h-0 flex-col">
      <header class="flex items-start justify-between gap-4 border-b border-border-default px-5 py-5 sm:px-7">
        <div>
          <h2 class="text-xl font-medium text-text-brand">
            {{ mode === 'share' ? t('additionalModules.selectionTitleShare') : t('additionalModules.selectionTitlePdf') }}
          </h2>
          <p class="mt-1 text-sm text-text-muted">{{ t('additionalModules.selectionHelp') }}</p>
        </div>
        <BaseButton variant="ghost" icon-only :aria-label="t('additionalModules.close')" @click="emit('update:modelValue', false)">
          <span aria-hidden="true" class="text-xl">×</span>
        </BaseButton>
      </header>

      <div v-if="generatedUrl" class="space-y-5 px-5 py-8 sm:px-7">
        <BaseAlert variant="success" :title="t('additionalModules.linkReady')">
          {{ generatedUrl }}
        </BaseAlert>
        <div class="flex flex-wrap gap-2">
          <BaseButton data-testid="additional-share-copy" @click="copyGeneratedUrl">
            {{ copied ? t('additionalModules.copied') : t('additionalModules.copyLink') }}
          </BaseButton>
          <BaseButton as="a" :to="generatedUrl" target="_blank" rel="noopener" variant="secondary">
            {{ t('additionalModules.openLink') }}
          </BaseButton>
        </div>
      </div>

      <template v-else>
        <div class="grid min-h-0 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div class="space-y-4 px-5 py-5 sm:px-7">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <span class="text-sm font-medium text-text-muted">
                {{ t('additionalModules.selectedCount', { count: selectedIds.length }) }}
              </span>
              <div class="flex gap-2">
                <BaseButton variant="ghost" size="sm" @click="selectAll">{{ t('additionalModules.selectAll') }}</BaseButton>
                <BaseButton variant="ghost" size="sm" @click="selectedIds = []">{{ t('additionalModules.clearSelection') }}</BaseButton>
              </div>
            </div>

            <section v-for="category in grouped" :key="category.id" class="rounded-xl border border-border-default bg-surface">
              <div class="border-b border-border-default bg-surface-raised px-4 py-3">
                <BaseCheckbox
                  :model-value="categorySelected(category)"
                  @update:model-value="toggleCategory(category, $event)"
                >
                  <span class="font-medium">{{ localized(category, 'name') }}</span>
                </BaseCheckbox>
              </div>
              <div class="grid gap-2 p-4 sm:grid-cols-2">
                <BaseCheckbox
                  v-for="module in category.modules"
                  :key="module.id"
                  v-model="selectedIds"
                  :value="module.id"
                  :data-testid="`additional-select-module-${module.id}`"
                >
                  <span class="flex gap-2"><span aria-hidden="true">{{ module.icon }}</span>{{ localized(module, 'name') }}</span>
                </BaseCheckbox>
              </div>
            </section>
          </div>

          <aside class="space-y-4 border-t border-border-default bg-surface-raised px-5 py-5 lg:border-l lg:border-t-0 sm:px-7">
            <BaseFormField
              :label="t('additionalModules.recipientLabel')"
              for="additional-share-recipient"
              :required="mode === 'share'"
              :hint="mode === 'pdf' ? t('additionalModules.pdfRecipientHelp') : ''"
            >
              <BaseInput id="additional-share-recipient" v-model="form.recipient_label" data-testid="additional-share-recipient" />
            </BaseFormField>
            <BaseFormField
              :label="t('additionalModules.optionalClient')"
              for="additional-share-client"
            >
              <BaseSelect
                id="additional-share-client"
                data-testid="additional-share-client"
                :model-value="form.client_id"
                :options="clientOptions"
                @update:model-value="selectClient"
              />
            </BaseFormField>
            <BaseFormField :label="t('additionalModules.language')" for="additional-share-language">
              <BaseSegmented
                id="additional-share-language"
                v-model="form.language"
                :options="[
                  { value: 'es', label: t('additionalModules.spanish'), testId: 'additional-selection-language-es' },
                  { value: 'en', label: t('additionalModules.english'), testId: 'additional-selection-language-en' },
                ]"
              />
            </BaseFormField>
            <div v-if="mode === 'share'" class="space-y-2">
              <div class="flex items-start justify-between gap-4">
                <div class="min-w-0">
                  <p class="text-sm font-medium text-text-default">{{ t('additionalModules.shareVideoLabel') }}</p>
                  <p class="mt-1 text-xs leading-5 text-text-muted">{{ t('additionalModules.shareVideoHint') }}</p>
                </div>
                <BaseToggle
                  v-model="form.show_explainer_video"
                  :aria-label="t('additionalModules.shareVideoLabel')"
                  data-testid="additional-share-video-toggle"
                />
              </div>
              <p
                v-if="!catalogVideoVisible"
                class="rounded-lg bg-surface px-3 py-2 text-xs leading-5 text-text-muted"
                data-testid="additional-share-video-catalog-off"
              >
                {{ t('additionalModules.shareVideoCatalogOff') }}
              </p>
            </div>
            <BaseAlert variant="info">{{ t('additionalModules.noPriceNotice') }}</BaseAlert>
            <BaseAlert v-if="localError || errorMessage" variant="danger">{{ localError || errorMessage }}</BaseAlert>
          </aside>
        </div>

      </template>
    </div>
    <template #footer>
      <BaseModalActions v-if="(!(generatedUrl))">
        <BaseButton variant="ghost" @click="emit('update:modelValue', false)">{{ t('additionalModules.cancel') }}</BaseButton>
        <BaseButton :loading="saving" data-testid="additional-selection-submit" @click="submit">
          {{ mode === 'share' ? t('additionalModules.generate') : t('additionalModules.download') }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
