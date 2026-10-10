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
  { target: '[data-testid="building-with-us-hero-aside"]', key: 'Hero', prefer: 'bottom' },
  { target: '[data-testid="building-with-us-origin"]', key: 'Origin', prefer: 'bottom' },
  { target: '.building-with-us-roles', key: 'Roles', prefer: 'top' },
  { target: '.building-with-us-models-nav', key: 'Models', prefer: 'bottom' },
  { target: '[data-testid="building-with-us-periods"]', key: 'Periods', prefer: 'top' },
  { target: '[data-testid="building-with-us-milestones"]', key: 'Milestones', prefer: 'top' },
  { target: '.building-with-us-faq', key: 'Faq', prefer: 'top' },
  { target: '[data-testid="building-with-us-download-pdf-floating"]', key: 'Actions', prefer: 'left' },
  { target: '.building-with-us-restart-guide', key: 'Restart', prefer: 'right' },
].map(({ target, key, prefer }) => ({
  target,
  prefer,
  title: t(`buildingWithUs.guide${key}Title`),
  description: t(`buildingWithUs.guide${key}Description`),
})))

const labels = computed(() => ({
  skip: t('buildingWithUs.guideSkip'),
  back: t('buildingWithUs.guideBack'),
  next: t('buildingWithUs.guideNext'),
  done: t('buildingWithUs.guideDone'),
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
    storage-key="projectapp-building-with-us-guide-seen"
    test-id-prefix="building-with-us-guide"
    :is-dark="props.isDark"
    @complete="emit('complete')"
  />
</template>
