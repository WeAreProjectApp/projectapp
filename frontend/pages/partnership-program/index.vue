<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const { theme } = useFinancingTheme()
const { locale, t } = useI18n()
const runtimeConfig = useRuntimeConfig()
const switchLocalePath = useSwitchLocalePath()
const isEnglish = computed(() => locale.value.startsWith('en'))
const language = computed(() => (isEnglish.value ? 'en' : 'es'))
const program = ref(null)
const liveError = ref(false)

const { data: initialProgram } = await useAsyncData(
  `financing-program-${locale.value}`,
  async () => {
    const base = import.meta.server ? runtimeConfig.apiInternalOrigin : ''
    try {
      return await $fetch(`${base}/api/financing/public/?lang=${language.value}`)
    } catch {
      // Builds can run before Django is reachable: the page then prerenders a
      // loading skeleton that the browser refresh below replaces.
      return null
    }
  },
)

if (initialProgram.value) program.value = initialProgram.value

async function loadProgram() {
  try {
    program.value = await $fetch(`/api/financing/public/?lang=${language.value}`)
    liveError.value = false
  } catch {
    liveError.value = !program.value
  }
}

async function retry() {
  liveError.value = false
  await loadProgram()
}

onMounted(loadProgram)
watch(language, loadProgram)

const canonicalPath = computed(() => (
  isEnglish.value ? '/en-us/partnership-program' : '/es-co/partnership-program'
))
const alternatePath = computed(() => (
  isEnglish.value ? '/es-co/partnership-program' : '/en-us/partnership-program'
))
const pdfUrl = computed(() => `/api/financing/public/pdf/?lang=${language.value}`)
const baseUrl = 'https://projectapp.co'

const structuredData = computed(() => ({
  '@context': 'https://schema.org',
  '@type': 'Service',
  name: t('financing.title'),
  description: t('financing.metaDescription'),
  provider: {
    '@type': 'Organization',
    name: 'Project App.',
    url: baseUrl,
  },
  areaServed: 'CO',
  serviceType: isEnglish.value
    ? 'Software development partnership with financing'
    : 'Alianza de desarrollo de software con financiación',
  url: `${baseUrl}${canonicalPath.value}`,
}))

useHead(() => ({
  title: t('financing.metaTitle'),
  htmlAttrs: { lang: isEnglish.value ? 'en-US' : 'es-CO' },
  meta: [
    { name: 'description', content: t('financing.metaDescription') },
    { name: 'robots', content: 'index,follow' },
    { property: 'og:title', content: t('financing.metaTitle') },
    { property: 'og:description', content: t('financing.metaDescription') },
    { property: 'og:type', content: 'website' },
    { property: 'og:url', content: `${baseUrl}${canonicalPath.value}` },
    { name: 'twitter:card', content: 'summary' },
  ],
  link: [
    { rel: 'canonical', href: `${baseUrl}${canonicalPath.value}` },
    {
      rel: 'alternate',
      hreflang: isEnglish.value ? 'es-CO' : 'en-US',
      href: `${baseUrl}${alternatePath.value}`,
    },
    {
      rel: 'alternate',
      hreflang: isEnglish.value ? 'en-US' : 'es-CO',
      href: `${baseUrl}${canonicalPath.value}`,
    },
  ],
  script: [{ type: 'application/ld+json', innerHTML: JSON.stringify(structuredData.value) }],
}))

async function changeLanguage(nextLanguage) {
  if (nextLanguage === language.value) return
  const path = switchLocalePath(nextLanguage === 'en' ? 'en-us' : 'es-co')
  if (path) await navigateTo(path)
}
</script>

<template>
  <section class="public-document-theme public-document-canvas min-h-screen" :data-theme="theme" data-testid="financing-public-page">
    <div v-if="liveError" class="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-4 text-center">
      <h1 class="text-2xl font-medium text-text-brand">{{ t('financing.loadError') }}</h1>
      <BaseButton class="mt-5" @click="retry">{{ t('financing.retry') }}</BaseButton>
    </div>
    <FinancingProgramSkeleton v-else-if="!program" />
    <FinancingProgramView
      v-else
      :program="program"
      :download-url="pdfUrl"
      :language="language"
      @change-language="changeLanguage"
    />
  </section>
</template>
