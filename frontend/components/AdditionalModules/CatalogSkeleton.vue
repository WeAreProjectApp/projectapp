<script setup>
import BaseSkeleton from '~/components/base/BaseSkeleton.vue'

/**
 * Neutral placeholder for the module catalog while its data is pending.
 *
 * The public page is prerendered: when the build cannot reach the API it bakes
 * this skeleton (never the empty state), and the browser's live fetch replaces
 * it. Mirrors the controls, category index and card grid of CatalogView.
 */
const { t } = useI18n()
</script>

<template>
  <div
    class="mx-auto w-full max-w-[1400px] px-4 sm:px-6"
    role="status"
    aria-live="polite"
    data-testid="additional-modules-skeleton"
  >
    <span class="sr-only">{{ t('additionalModules.loading') }}</span>
    <div class="mb-8 flex justify-center" aria-hidden="true">
      <BaseSkeleton variant="card" class="!h-11 w-full max-w-md" />
    </div>
    <div class="mb-10 flex gap-2 overflow-hidden sm:flex-wrap sm:justify-center" aria-hidden="true">
      <BaseSkeleton
        v-for="chip in 4"
        :key="`chip-${chip}`"
        variant="card"
        class="!h-11 w-36 shrink-0 !rounded-full"
      />
    </div>
    <div class="mb-6 flex items-end justify-between gap-4 pb-4" aria-hidden="true">
      <BaseSkeleton class="!h-7 w-64 max-w-full" />
      <BaseSkeleton class="w-6" />
    </div>
    <div class="grid grid-cols-1 gap-4 pb-14 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-hidden="true">
      <div
        v-for="card in 8"
        :key="`card-${card}`"
        class="min-h-52 rounded-2xl border border-border-default bg-surface p-5 shadow-card"
      >
        <BaseSkeleton variant="card" class="mb-5 !h-12 w-12" />
        <BaseSkeleton class="!h-5 w-3/4" />
        <BaseSkeleton class="mt-4 w-full" />
        <BaseSkeleton class="mt-2 w-5/6" />
        <BaseSkeleton class="mt-6 w-24" />
      </div>
    </div>
  </div>
</template>
