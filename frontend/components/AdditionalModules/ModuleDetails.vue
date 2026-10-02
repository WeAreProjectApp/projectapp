<script setup>
import BaseCard from '~/components/base/BaseCard.vue'
import es from '~/locales/additionalModules/es'
import en from '~/locales/additionalModules/en'

const props = defineProps({
  module: { type: Object, required: true },
  language: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})

const { t } = useI18n()
const label = (key) => props.language ? (props.language === 'en' ? en : es)[key] : t(`additionalModules.${key}`)
</script>

<template>
  <div class="grid gap-4" :class="{ 'sm:grid-cols-2': !compact }">
    <BaseCard padding="md">
      <h3 class="text-sm font-medium uppercase tracking-wide text-text-brand">
        {{ label('whatIs') }}
      </h3>
      <p class="mt-3 break-words text-sm leading-6 text-text-muted">{{ module.what_is }}</p>
    </BaseCard>
    <BaseCard padding="md">
      <h3 class="text-sm font-medium uppercase tracking-wide text-text-brand">
        {{ label('purpose') }}
      </h3>
      <p class="mt-3 break-words text-sm leading-6 text-text-muted">{{ module.purpose }}</p>
    </BaseCard>
    <BaseCard padding="md">
      <h3 class="text-sm font-medium uppercase tracking-wide text-text-brand">
        {{ label('problemsSolved') }}
      </h3>
      <ul class="mt-3 space-y-2 text-sm leading-6 text-text-muted">
        <li v-for="item in module.problems_solved" :key="item" class="flex min-w-0 gap-2">
          <span aria-hidden="true" class="shrink-0 text-text-brand">•</span><span class="min-w-0 break-words">{{ item }}</span>
        </li>
      </ul>
    </BaseCard>
    <BaseCard padding="md">
      <h3 class="text-sm font-medium uppercase tracking-wide text-text-brand">
        {{ label('integrations') }}
      </h3>
      <ul class="mt-3 space-y-2 text-sm leading-6 text-text-muted">
        <li v-for="item in module.integrations" :key="item" class="flex min-w-0 gap-2">
          <span aria-hidden="true" class="shrink-0 text-text-brand">•</span><span class="min-w-0 break-words">{{ item }}</span>
        </li>
      </ul>
    </BaseCard>
    <BaseCard padding="md" :class="{ 'sm:col-span-2': !compact }">
      <h3 class="text-sm font-medium uppercase tracking-wide text-text-brand">
        {{ label('requirements') }}
      </h3>
      <ul class="mt-3 grid gap-2 text-sm leading-6 text-text-muted sm:grid-cols-2">
        <li v-for="item in module.implementation_requirements" :key="item" class="flex min-w-0 gap-2">
          <span aria-hidden="true" class="shrink-0 text-text-brand">•</span><span class="min-w-0 break-words">{{ item }}</span>
        </li>
      </ul>
    </BaseCard>
  </div>
</template>
