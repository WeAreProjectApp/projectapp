<script setup>
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  links: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
  /** Catalog-wide video switch: while off, no link shows the explainer. */
  catalogVideoVisible: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'status', 'copy', 'video'])
const { t, locale } = useI18n()

function formatDate(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale.value, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function opensLabel(link) {
  if (!link.view_count) return t('additionalModules.neverOpened')
  if (link.view_count === 1) return t('additionalModules.openedOnce')
  return t('additionalModules.openedMany', { count: link.view_count })
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    kind="workspace"
    padding="none"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="flex min-h-0 flex-col">
      <header class="flex items-start justify-between gap-4 border-b border-border-default px-5 py-5 sm:px-7">
        <div>
          <h2 class="text-xl font-medium text-text-brand">{{ t('additionalModules.trackingTitle') }}</h2>
          <p class="mt-1 text-sm text-text-muted">{{ t('additionalModules.panelDescription') }}</p>
        </div>
        <BaseButton variant="ghost" icon-only :aria-label="t('additionalModules.close')" @click="emit('update:modelValue', false)">
          <span aria-hidden="true" class="text-xl">×</span>
        </BaseButton>
      </header>

      <div class="overflow-y-auto px-5 py-5 sm:px-7">
        <p
          v-if="!catalogVideoVisible && links.length"
          class="mb-4 rounded-lg bg-surface-raised px-4 py-3 text-sm text-text-muted"
          data-testid="additional-share-history-video-catalog-off"
        >
          {{ t('additionalModules.shareVideoCatalogOff') }}
        </p>
        <BaseEmptyState
          v-if="!links.length"
          :title="t('additionalModules.noShares')"
          :description="t('additionalModules.selectionHelp')"
        />
        <ul v-else class="space-y-3" data-testid="additional-share-history">
          <li
            v-for="link in links"
            :key="link.uuid"
            class="rounded-xl border border-border-default bg-surface p-4"
          >
            <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="font-medium text-text-brand">{{ link.recipient_label }}</h3>
                  <BaseBadge :variant="link.is_active ? 'success' : 'neutral'">
                    {{ link.is_active ? t('additionalModules.active') : t('additionalModules.retired') }}
                  </BaseBadge>
                  <BaseBadge :variant="link.view_count ? 'info' : 'neutral'">{{ opensLabel(link) }}</BaseBadge>
                </div>
                <p v-if="link.client_name" class="mt-1 text-sm text-text-muted">{{ link.client_name }}</p>
                <div class="mt-3 flex flex-wrap gap-1.5">
                  <BaseBadge v-for="module in link.selected_modules" :key="module.id" variant="neutral" size="sm">
                    {{ link.language === 'en' ? module.name_en : module.name_es }}
                  </BaseBadge>
                </div>
                <dl class="mt-4 grid gap-2 text-xs text-text-muted sm:grid-cols-3">
                  <div><dt class="font-medium text-text-default">{{ t('additionalModules.createdAt') }}</dt><dd>{{ formatDate(link.created_at) }}</dd></div>
                  <div><dt class="font-medium text-text-default">{{ t('additionalModules.firstOpened') }}</dt><dd>{{ formatDate(link.first_viewed_at) }}</dd></div>
                  <div><dt class="font-medium text-text-default">{{ t('additionalModules.lastOpened') }}</dt><dd>{{ formatDate(link.last_viewed_at) }}</dd></div>
                </dl>
                <div class="mt-4 flex items-center gap-3">
                  <BaseToggle
                    size="sm"
                    :model-value="link.show_explainer_video !== false"
                    :disabled="saving"
                    :aria-label="t('additionalModules.shareVideoToggleAria', { label: link.recipient_label })"
                    :data-testid="`additional-share-history-video-toggle-${link.uuid}`"
                    @update:model-value="emit('video', { link, value: $event })"
                  />
                  <span class="text-sm text-text-muted">{{ t('additionalModules.shareVideoLabel') }}</span>
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <BaseButton variant="secondary" size="sm" @click="emit('copy', link)">{{ t('additionalModules.copyLink') }}</BaseButton>
                <BaseButton as="a" :to="link.public_path" target="_blank" rel="noopener noreferrer" variant="secondary" size="sm">
                  {{ t('additionalModules.openLink') }}
                </BaseButton>
                <BaseButton
                  :variant="link.is_active ? 'danger-ghost' : 'secondary'"
                  size="sm"
                  :loading="saving"
                  @click="emit('status', { link, action: link.is_active ? 'revoke' : 'restore' })"
                >
                  {{ link.is_active ? t('additionalModules.revoke') : t('additionalModules.restore') }}
                </BaseButton>
              </div>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </BaseModal>
</template>
