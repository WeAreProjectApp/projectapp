<script setup>
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseButton from '~/components/base/BaseButton.vue'

defineProps({ context: { type: Object, required: true } })
const emit = defineEmits(['download'])
const { t } = useI18n()
const tone = (status) => status === 'included' ? 'success' : status === 'partial' ? 'warning' : 'danger'
</script>

<template>
  <section class="min-w-0 space-y-4" data-testid="delivery-prompt-sources">
    <h3 class="text-base font-semibold text-text-default">{{ t('platformDelivery.promptSources.title') }}</h3>
    <p class="text-sm text-text-muted">{{ t('platformDelivery.promptSources.retained') }}</p>
    <p v-if="context.id" class="break-all text-xs text-text-muted">{{ t('platformDelivery.promptSources.context') }}: {{ context.id }}</p>
    <BaseAlert v-if="context.complete === false" variant="warning" data-testid="delivery-prompt-incomplete">
      {{ t('platformDelivery.promptSources.incomplete') }}
    </BaseAlert>
    <ul v-if="context.warnings?.length" class="list-disc space-y-1 pl-5 text-sm text-text-muted">
      <li v-for="(warning, index) in context.warnings" :key="index">{{ warning }}</li>
    </ul>
    <section v-if="context.missing_sources?.length" class="space-y-2">
      <h4 class="text-sm font-semibold text-text-default">{{ t('platformDelivery.promptAuthoring.missingSources') }}</h4>
      <ul class="list-disc space-y-1 pl-5 text-sm text-text-muted"><li v-for="(source, index) in context.missing_sources" :key="index">{{ source }}</li></ul>
    </section>
    <section v-if="context.uncertainties?.length" class="space-y-2">
      <h4 class="text-sm font-semibold text-text-default">{{ t('platformDelivery.promptAuthoring.uncertainties') }}</h4>
      <ul class="list-disc space-y-1 pl-5 text-sm text-text-muted"><li v-for="(uncertainty, index) in context.uncertainties" :key="index">{{ uncertainty }}</li></ul>
    </section>
    <article v-for="source in context.sources || []" :key="source.source_key" class="min-w-0 space-y-3 rounded-xl border border-border-default p-4" :data-testid="`delivery-prompt-source-${source.source_key}`">
      <header class="flex flex-wrap items-start justify-between gap-2">
        <div class="min-w-0 flex-1">
          <p class="break-words text-sm font-semibold text-text-default">{{ source.title }}</p>
          <p class="text-xs text-text-muted">{{ source.source_key }} · {{ t(`platformDelivery.promptSources.roles.${source.role}`) }}</p>
        </div>
        <BaseBadge :variant="tone(source.status)">{{ t(`platformDelivery.promptSources.status.${source.status}`) }}</BaseBadge>
      </header>
      <dl class="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
        <div><dt class="text-text-muted">{{ t('platformDelivery.promptSources.origin') }}</dt><dd class="break-words text-text-default">{{ source.origin }} · {{ source.source_id || t('platformDelivery.promptSources.unknown') }}</dd></div>
        <div><dt class="text-text-muted">{{ t('platformDelivery.promptSources.version') }}</dt><dd class="break-words text-text-default">{{ source.version ?? t('platformDelivery.promptSources.unknown') }}</dd></div>
        <div><dt class="text-text-muted">{{ t('platformDelivery.promptSources.date') }}</dt><dd class="break-words text-text-default">{{ source.date || t('platformDelivery.promptSources.unknown') }}</dd></div>
        <div><dt class="text-text-muted">SHA-256</dt><dd class="break-all font-mono text-text-default">{{ source.sha256 || t('platformDelivery.promptSources.unknown') }}</dd></div>
      </dl>
      <p v-if="source.applicability_note" class="whitespace-pre-line break-words text-sm text-text-default">{{ source.applicability_note }}</p>
      <BaseButton v-if="source.file_url || source.download_url" variant="secondary" size="sm" @click="emit('download', source)">{{ t('platformDelivery.promptSources.downloadCopy') }}</BaseButton>
      <ul v-if="source.warnings?.length" class="list-disc space-y-1 pl-5 text-sm text-text-muted"><li v-for="(warning, index) in source.warnings" :key="index">{{ warning }}</li></ul>
      <details v-if="source.fragments?.length" class="rounded-xl bg-surface-raised p-3">
        <summary class="cursor-pointer text-sm font-medium text-text-default">{{ t('platformDelivery.promptSources.fragments') }}</summary>
        <div class="mt-3 max-h-64 space-y-4 overflow-auto">
          <section v-for="fragment in source.fragments" :key="fragment.locator" class="min-w-0 space-y-1">
            <h4 class="break-words text-xs font-semibold text-text-default">{{ fragment.locator }}</h4>
            <p class="whitespace-pre-wrap break-words text-xs text-text-muted">{{ fragment.text }}</p>
          </section>
        </div>
      </details>
    </article>
    <p class="text-sm text-text-muted">{{ t('platformDelivery.promptSources.humanReview') }}</p>
  </section>
</template>
