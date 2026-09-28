<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const { theme } = useAdditionalModulesTheme()
const { locale, t } = useI18n()
const runtimeConfig = useRuntimeConfig()
const switchLocalePath = useSwitchLocalePath()
const isEnglish = computed(() => locale.value.startsWith('en'))
const language = computed(() => (isEnglish.value ? 'en' : 'es'))
const catalog = ref(null)
const liveError = ref(false)

function unavailableCatalog() {
  return {
    language: language.value,
    categories: [],
    total_modules: 0,
    unavailable: true,
  }
}

const { data: initialCatalog } = await useAsyncData(
  `additional-module-catalog-${locale.value}`,
  async () => {
    const base = import.meta.server ? runtimeConfig.apiInternalOrigin : ''
    try {
      return await $fetch(`${base}/api/additional-modules/public/?lang=${language.value}`)
    } catch {
      // Builds and blue/green deploys can run before Django is reachable. The
      // page then prerenders a loading skeleton (never the empty state) and
      // the browser refresh below replaces it with the live catalog.
      return unavailableCatalog()
    }
  },
)

if (initialCatalog.value) catalog.value = initialCatalog.value

const catalogPending = computed(() => !catalog.value || catalog.value.unavailable === true)

async function loadCatalog() {
  try {
    catalog.value = await $fetch(`/api/additional-modules/public/?lang=${language.value}`)
    liveError.value = false
  } catch {
    liveError.value = !catalog.value || catalog.value.unavailable === true
  }
}

onMounted(loadCatalog)
watch(language, loadCatalog)

const canonicalPath = computed(() => (
  isEnglish.value ? '/en-us/additional-modules' : '/es-co/additional-modules'
))
const alternatePath = computed(() => (
  isEnglish.value ? '/es-co/additional-modules' : '/en-us/additional-modules'
))
const title = computed(() => (
  isEnglish.value
    ? 'Additional Modules for Digital Platforms | Project App.'
    : 'Módulos adicionales para plataformas | Project App.'
))
const description = computed(() => t('additionalModules.subtitle'))
const baseUrl = 'https://projectapp.co'
const itemList = computed(() => {
  const modules = (catalog.value?.categories || []).flatMap((category) => category.modules)
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: t('additionalModules.title'),
    numberOfItems: modules.length,
    itemListElement: modules.map((module, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: module.name,
      description: module.summary,
      url: `${baseUrl}${canonicalPath.value}#module-${module.slug}`,
    })),
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
  // An unknown catalog must not be advertised as an empty ItemList.
  script: catalogPending.value
    ? []
    : [
        {
          type: 'application/ld+json',
          innerHTML: JSON.stringify(itemList.value),
        },
      ],
}))

const pdfUrl = computed(() => `/api/additional-modules/public/pdf/?lang=${language.value}`)

async function retry() {
  liveError.value = false
  await loadCatalog()
}

async function changeLanguage(nextLanguage) {
  if (nextLanguage === language.value) return
  const path = switchLocalePath(nextLanguage === 'en' ? 'en-us' : 'es-co')
  if (path) await navigateTo(path)
}
</script>

<template>
  <section class="public-document-theme public-document-canvas min-h-screen" :data-theme="theme" data-testid="additional-modules-public-page">
    <div v-if="liveError" class="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-4 text-center">
      <h1 class="text-2xl font-medium text-text-brand">{{ t('additionalModules.loadError') }}</h1>
      <BaseButton class="mt-5" @click="retry">{{ t('additionalModules.retry') }}</BaseButton>
    </div>
    <AdditionalModulesCatalogView
      v-else
      :loading="catalogPending"
      :categories="catalog?.categories || []"
      :total-modules="catalog?.total_modules || 0"
      :download-url="pdfUrl"
      :language="language"
      :show-explainer="catalog?.show_explainer_video !== false"
      :explainer-resource="catalog?.explainer_video"
      @change-language="changeLanguage"
    />
  </section>
</template>
