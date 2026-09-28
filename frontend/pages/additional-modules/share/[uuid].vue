<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const route = useRoute()
const { theme } = useAdditionalModulesTheme()
const { locale, t } = useI18n()
const switchLocalePath = useSwitchLocalePath()
const catalog = ref(null)
const isLoading = ref(true)
const errorState = ref('')

const shareUuid = computed(() => String(route.params.uuid || ''))
const language = computed(() => (locale.value.startsWith('en') ? 'en' : 'es'))
const shareEndpoint = computed(() => `/api/additional-modules/public/shares/${shareUuid.value}/`)
const catalogEndpoint = computed(() => `${shareEndpoint.value}?lang=${language.value}`)

function sessionId() {
  const key = `additional-modules-share-session:${shareUuid.value}`
  let value = sessionStorage.getItem(key)
  if (!value) {
    value = crypto.randomUUID().replaceAll('-', '')
    sessionStorage.setItem(key, value)
  }
  return value
}

async function loadCatalog() {
  isLoading.value = true
  errorState.value = ''
  try {
    catalog.value = await $fetch(catalogEndpoint.value)
  } catch (error) {
    errorState.value = error?.status === 410 || error?.statusCode === 410
      ? 'gone'
      : 'failed'
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => {
  await loadCatalog()
  if (!catalog.value) return
  $fetch(`${shareEndpoint.value}track/`, {
    method: 'POST',
    body: { session_id: sessionId() },
  }).catch(() => {})
})

watch(language, loadCatalog)

const canonicalPath = computed(() => (
  catalog.value?.canonical_path
  || (locale.value.startsWith('en')
    ? '/en-us/additional-modules'
    : '/es-co/additional-modules')
))
const title = computed(() => (
  locale.value.startsWith('en')
    ? 'Selected Additional Modules | Project App.'
    : 'Selección de módulos adicionales | Project App.'
))
const baseUrl = 'https://projectapp.co'

useHead(() => ({
  title: title.value,
  meta: [
    { name: 'description', content: t('additionalModules.subtitle') },
    { name: 'robots', content: 'noindex,nofollow,noarchive' },
    { property: 'og:title', content: title.value },
    { property: 'og:description', content: t('additionalModules.sharedNotice') },
  ],
  link: [
    { rel: 'canonical', href: `${baseUrl}${canonicalPath.value}` },
  ],
}))

const pdfUrl = computed(() => (
  `/api/additional-modules/public/shares/${shareUuid.value}/pdf/?lang=${language.value}`
))

async function changeLanguage(nextLanguage) {
  if (nextLanguage === language.value) return
  const path = switchLocalePath(nextLanguage === 'en' ? 'en-us' : 'es-co')
  if (path) await navigateTo(path)
}
</script>

<template>
  <section class="public-document-theme public-document-canvas min-h-screen" :data-theme="theme" data-testid="additional-modules-public-page">
    <div v-if="isLoading" class="flex min-h-[70vh] items-center justify-center" role="status">
      <span class="h-9 w-9 animate-spin rounded-full border-2 border-border-default border-t-primary" />
    </div>
    <div v-else-if="errorState" class="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-4 text-center">
      <h1 class="text-2xl font-medium text-text-brand">
        {{ errorState === 'gone' ? t('additionalModules.emptyTitle') : t('additionalModules.loadError') }}
      </h1>
      <p class="mt-3 text-text-muted">{{ t('additionalModules.emptyBody') }}</p>
      <BaseButton v-if="errorState !== 'gone'" class="mt-5" @click="loadCatalog">
        {{ t('additionalModules.retry') }}
      </BaseButton>
    </div>
    <AdditionalModulesCatalogView
      v-else
      :categories="catalog?.categories || []"
      :total-modules="catalog?.total_modules || 0"
      :download-url="pdfUrl"
      :language="language"
      :show-explainer="catalog?.show_explainer_video !== false"
      :explainer-resource="catalog?.explainer_video"
      is-shared
      @change-language="changeLanguage"
    />
  </section>
</template>
