<script setup>
import BaseSkeleton from '~/components/base/BaseSkeleton.vue'

const { t } = useI18n()
</script>

<template>
  <div class="public-document-canvas min-h-screen w-full" role="status" aria-live="polite" data-testid="building-with-us-program-skeleton">
    <span class="sr-only">{{ t('buildingWithUs.loading') }}</span>
    <div class="px-4 pb-14 pt-12 sm:px-6 sm:pb-20 sm:pt-16" aria-hidden="true">
      <div class="mx-auto max-w-[1200px]">
        <div class="mb-12 flex flex-wrap items-center justify-between gap-3">
          <BaseSkeleton class="w-28" />
          <BaseSkeleton variant="card" class="!h-10 w-40 !rounded-full" />
        </div>
        <div class="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-end">
          <div>
            <BaseSkeleton class="w-56 max-w-full" />
            <BaseSkeleton variant="card" class="mt-5 !h-12 w-full max-w-3xl sm:!h-16" />
            <BaseSkeleton variant="card" class="mt-3 !h-12 w-2/3 sm:!h-16" />
            <BaseSkeleton class="mt-7 w-full max-w-2xl" />
            <BaseSkeleton class="mt-3 w-5/6 max-w-2xl" />
            <div class="mt-8 flex flex-wrap gap-3">
              <BaseSkeleton variant="card" class="!h-12 w-44 !rounded-full" />
              <BaseSkeleton variant="card" class="!h-12 w-40 !rounded-full" />
            </div>
          </div>
          <div class="rounded-3xl border border-border-default bg-surface p-6 shadow-raised">
            <BaseSkeleton class="w-24" />
            <BaseSkeleton class="mt-5 !h-5 w-3/4" />
            <BaseSkeleton class="mt-4 w-full" />
            <BaseSkeleton class="mt-2 w-5/6" />
          </div>
        </div>
      </div>
    </div>
    <div class="mx-auto w-full max-w-[1200px] px-4 py-14 sm:px-6 sm:py-20" aria-hidden="true">
      <BaseSkeleton class="!h-8 w-2/3 max-w-xl" />
      <BaseSkeleton class="mt-4 w-full max-w-3xl" />
      <div class="mt-8 grid gap-5 lg:grid-cols-2">
        <BaseSkeleton v-for="role in 2" :key="role" variant="card" class="!h-72 !rounded-3xl" />
      </div>
      <div class="mt-8 grid gap-5 lg:grid-cols-3">
        <BaseSkeleton v-for="model in 3" :key="model" variant="card" class="!h-72 !rounded-3xl" />
      </div>
    </div>
  </div>
</template>
