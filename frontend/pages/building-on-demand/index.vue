<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { buildingOnDemandLanguage, buildingOnDemandPath, buildingOnDemandPdfUrl, isBuildingOnDemandProgram } from '~/utils/buildingOnDemand'

const { theme } = useBuildingOnDemandTheme()
const { locale, t } = useI18n()
const runtimeConfig = useRuntimeConfig()
const switchLocalePath = useSwitchLocalePath()
const language = computed(() => buildingOnDemandLanguage(locale.value))
const isEnglish = computed(() => language.value === 'en')
const program = ref(null)
const liveError = ref(false)
let latestRequest = 0

const { data: initialProgram } = await useAsyncData(
  `building-on-demand-program-${locale.value}`,
  async () => {
    const base = import.meta.server ? runtimeConfig.apiInternalOrigin : ''
    try {
      return await $fetch(`${base}/api/building-on-demand/public/?lang=${language.value}`)
    } catch {
      // Keep a neutral skeleton in prerendered HTML until the live API loads.
      return null
    }
  },
)

if (isBuildingOnDemandProgram(initialProgram.value)) program.value = initialProgram.value
else if (initialProgram.value !== null && initialProgram.value !== undefined) liveError.value = true

async function loadProgram() {
  const request = ++latestRequest
  try {
    const payload = await $fetch(`/api/building-on-demand/public/?lang=${language.value}`)
    if (request !== latestRequest) return
    if (!isBuildingOnDemandProgram(payload)) {
      program.value = null
      liveError.value = true
      return
    }
    program.value = payload
    liveError.value = false
  } catch {
    if (request === latestRequest) liveError.value = !program.value
  }
}

async function retry() {
  liveError.value = false
  await loadProgram()
}

onMounted(loadProgram)
watch(language, () => {
  program.value = null
  liveError.value = false
  void loadProgram()
})

const baseUrl = 'https://projectapp.co'
const canonicalPath = computed(() => program.value?.canonical_path || buildingOnDemandPath(language.value))
const alternatePath = computed(() => program.value?.alternate_path || buildingOnDemandPath(isEnglish.value ? 'es' : 'en'))
const spanishPath = computed(() => isEnglish.value ? alternatePath.value : canonicalPath.value)
const englishPath = computed(() => isEnglish.value ? canonicalPath.value : alternatePath.value)
const pdfUrl = computed(() => program.value?.pdf_path || buildingOnDemandPdfUrl(language.value))
const title = computed(() => program.value?.seo?.title || t('buildingOnDemand.metaTitle'))
const description = computed(() => program.value?.seo?.description || t('buildingOnDemand.metaDescription'))

const structuredData = computed(() => {
  const monthlyPrices = (program.value?.tiers?.items || [])
    .map((tier) => tier.monthly_price)
    .filter((price) => Number.isFinite(price) && price > 0)
  return {
    '@context': 'https://schema.org',
    '@type': 'Service',
    name: t('buildingOnDemand.title'),
    description: description.value,
    provider: { '@type': 'Organization', name: 'Project App.', url: baseUrl },
    areaServed: 'CO',
    serviceType: t('buildingOnDemand.serviceType'),
    url: `${baseUrl}${canonicalPath.value}`,
    ...(monthlyPrices.length ? {
      offers: {
        '@type': 'AggregateOffer',
        priceCurrency: 'COP',
        lowPrice: Math.min(...monthlyPrices),
        highPrice: Math.max(...monthlyPrices),
        offerCount: monthlyPrices.length,
      },
    } : {}),
  }
})

useHead(() => ({
  title: title.value,
  htmlAttrs: { lang: isEnglish.value ? 'en-US' : 'es-CO' },
  meta: [
    { name: 'description', content: description.value },
    { name: 'robots', content: 'index,follow' },
    { property: 'og:title', content: title.value },
    { property: 'og:description', content: description.value },
    { property: 'og:type', content: 'website' },
    { property: 'og:url', content: `${baseUrl}${canonicalPath.value}` },
    { property: 'og:locale', content: isEnglish.value ? 'en_US' : 'es_CO' },
    { name: 'twitter:card', content: 'summary' },
    { name: 'twitter:title', content: title.value },
    { name: 'twitter:description', content: description.value },
  ],
  link: [
    { rel: 'canonical', href: `${baseUrl}${canonicalPath.value}` },
    { rel: 'alternate', hreflang: 'es-CO', href: `${baseUrl}${spanishPath.value}` },
    { rel: 'alternate', hreflang: 'en-US', href: `${baseUrl}${englishPath.value}` },
    { rel: 'alternate', hreflang: 'x-default', href: `${baseUrl}${spanishPath.value}` },
  ],
  script: [{ type: 'application/ld+json', innerHTML: JSON.stringify(structuredData.value).replace(/</g, '\\u003c') }],
}))

async function changeLanguage(nextLanguage) {
  if (nextLanguage === language.value) return
  const path = switchLocalePath(nextLanguage === 'en' ? 'en-us' : 'es-co')
  if (path) await navigateTo(path)
}
</script>

<template>
  <section class="public-document-theme public-document-canvas min-h-screen" :data-theme="theme" data-testid="building-on-demand-public-page">
    <div v-if="liveError" class="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-4 text-center" role="alert">
      <h1 class="text-2xl font-medium text-text-brand">{{ t('buildingOnDemand.loadError') }}</h1>
      <BaseButton class="mt-5" data-testid="building-on-demand-retry" @click="retry">{{ t('buildingOnDemand.retry') }}</BaseButton>
    </div>
    <BuildingOnDemandProgramSkeleton v-else-if="!program" />
    <BuildingOnDemandProgramView
      v-else
      :program="program"
      :download-url="pdfUrl"
      :language="language"
      data-testid="building-on-demand-program"
      @change-language="changeLanguage"
    />
  </section>
</template>
