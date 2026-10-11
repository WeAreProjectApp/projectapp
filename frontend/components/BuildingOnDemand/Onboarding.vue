<script setup>
import { computed, ref } from 'vue'
import PublicGuidedTour from '~/components/PublicGuidedTour.vue'

const props = defineProps({
  isDark: { type: Boolean, default: false },
})
const emit = defineEmits(['complete'])
const { t } = useI18n()
const tour = ref(null)

const steps = computed(() => [
  { target: '[data-testid="building-on-demand-hero"]', key: 'Hero', prefer: 'bottom' },
  { target: '[data-testid="building-on-demand-cell"]', key: 'Cell', prefer: 'bottom' },
  { target: '[data-testid="building-on-demand-terms"]', key: 'Terms', prefer: 'bottom' },
  { target: '[data-recommended="true"][data-testid^="building-on-demand-tier-"]', key: 'Recommended', prefer: 'top' },
  { target: '[data-testid="building-on-demand-bag"]', key: 'Bag', prefer: 'top' },
  { target: '[data-testid="building-on-demand-estimator"]', key: 'Estimator', prefer: 'top' },
  { target: '[data-testid="building-on-demand-hosting"]', key: 'Hosting', prefer: 'top' },
  { target: '[data-testid="building-on-demand-download-pdf-floating"]', key: 'Actions', prefer: 'left' },
  { target: '[data-testid="building-on-demand-guide-restart"]', key: 'Restart', prefer: 'right' },
].map(({ target, key, prefer }) => ({
  target,
  prefer,
  title: t(`buildingOnDemand.guide${key}Title`),
  description: t(`buildingOnDemand.guide${key}Description`),
})))

const labels = computed(() => ({
  skip: t('buildingOnDemand.guideSkip'),
  back: t('buildingOnDemand.guideBack'),
  next: t('buildingOnDemand.guideNext'),
  done: t('buildingOnDemand.guideDone'),
}))

defineExpose({
  start: () => tour.value?.start(),
  forceStart: () => tour.value?.forceStart(),
})
</script>

<template>
  <PublicGuidedTour
    ref="tour"
    :steps="steps"
    :labels="labels"
    storage-key="projectapp-building-on-demand-guide-seen"
    test-id-prefix="building-on-demand-guide"
    :is-dark="props.isDark"
    @complete="emit('complete')"
  />
</template>
