<script setup>
import BaseSkeleton from '~/components/base/BaseSkeleton.vue'

const { t } = useI18n()
</script>

<template>
  <div class="public-document-canvas min-h-screen w-full" role="status" aria-live="polite" data-testid="building-on-demand-program-skeleton">
    <span class="sr-only">{{ t('buildingOnDemand.loading') }}</span>
    <div class="mx-auto w-full max-w-[1200px] px-4 pb-14 pt-12 sm:px-6 sm:pb-20 sm:pt-16" aria-hidden="true">
      <div class="mb-12 flex flex-wrap items-center justify-between gap-3">
        <BaseSkeleton class="w-40 max-w-full" />
        <BaseSkeleton variant="card" class="!h-10 w-40 !rounded-full" />
      </div>
      <BaseSkeleton variant="card" class="!h-12 w-full max-w-4xl sm:!h-16" />
      <BaseSkeleton variant="card" class="mt-3 !h-12 w-2/3 max-w-3xl sm:!h-16" />
      <BaseSkeleton class="mt-7 w-full max-w-3xl" />
      <BaseSkeleton class="mt-3 w-5/6 max-w-3xl" />
      <div class="mt-8 flex flex-wrap gap-3">
        <BaseSkeleton variant="card" class="!h-12 w-44 !rounded-full" />
        <BaseSkeleton variant="card" class="!h-12 w-40 !rounded-full" />
      </div>
      <BaseSkeleton variant="card" class="mt-8 !h-24 w-full max-w-4xl !rounded-2xl" />
      <div class="mt-20">
        <BaseSkeleton class="!h-8 w-2/3 max-w-xl" />
        <BaseSkeleton class="mt-4 w-full max-w-3xl" />
        <div class="mt-8 grid min-w-0 gap-5 md:grid-cols-2 lg:grid-cols-3">
          <BaseSkeleton v-for="role in 6" :key="role" variant="card" class="!h-40 min-w-0 !rounded-3xl" />
        </div>
      </div>
      <div class="mt-20">
        <BaseSkeleton class="!h-8 w-2/3 max-w-xl" />
        <BaseSkeleton variant="card" class="mt-6 !h-12 w-full max-w-xl !rounded-full" />
        <div class="mt-8 grid min-w-0 gap-5 md:grid-cols-2 lg:grid-cols-3">
          <BaseSkeleton v-for="tier in 3" :key="tier" variant="card" class="!h-96 min-w-0 !rounded-3xl" />
        </div>
      </div>
    </div>
  </div>
</template>
