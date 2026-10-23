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
  { target: '[data-testid="consulting-hero-aside"]', key: 'Hero', prefer: 'bottom' },
  { target: '[data-testid="consulting-areas"]', key: 'Areas', prefer: 'bottom' },
  { target: '[data-testid="consulting-impact"]', key: 'Impact', prefer: 'top' },
  { target: '[data-testid="consulting-deliverable"]', key: 'Deliverable', prefer: 'top' },
  { target: '[data-testid="consulting-faq"]', key: 'Faq', prefer: 'top' },
  { target: '[data-testid="consulting-download-pdf-floating"]', key: 'Actions', prefer: 'left' },
  { target: '.consulting-restart-guide', key: 'Restart', prefer: 'right' },
].map(({ target, key, prefer }) => ({
  target,
  prefer,
  title: t(`consulting.guide${key}Title`),
  description: t(`consulting.guide${key}Description`),
})))

const labels = computed(() => ({
  skip: t('consulting.guideSkip'),
  back: t('consulting.guideBack'),
  next: t('consulting.guideNext'),
  done: t('consulting.guideDone'),
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
    storage-key="projectapp-consulting-guide-seen"
    test-id-prefix="consulting-guide"
    :is-dark="props.isDark"
    @complete="emit('complete')"
  />
</template>
