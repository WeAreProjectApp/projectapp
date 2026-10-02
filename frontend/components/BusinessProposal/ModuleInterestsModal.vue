<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import BaseModal from '~/components/base/BaseModal.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import ModuleDetails from '~/components/AdditionalModules/ModuleDetails.vue'
import ExplainerVideoCard from '~/components/ExplainerVideoCard.vue'
import { useExplainerVideo } from '~/composables/useExplainerVideos'
import { useProposalDarkMode } from '~/composables/useProposalDarkMode'
import { get_request, put_request } from '~/stores/services/request_http'
import additionalModulesEs from '~/locales/additionalModules/es'
import additionalModulesEn from '~/locales/additionalModules/en'

const props = defineProps({
  visible: { type: Boolean, default: false },
  proposalUuid: { type: String, required: true },
  language: { type: String, default: 'es' },
  preview: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'saved'])
const { isDark } = useProposalDarkMode()
const catalog = ref(null)
const selected = ref([])
const previous = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const success = ref(false)
const videoCard = ref(null)
let generation = 0
const contentLocale = computed(() => props.language === 'en' ? 'en-us' : 'es-co')
const contentMessages = { 'es-co': { additionalModules: additionalModulesEs }, 'en-us': { additionalModules: additionalModulesEn } }
const video = useExplainerVideo('additional-modules', computed(() => props.language), computed(() => catalog.value?.explainer_video))
const copy = {
  es: {
    title: 'Explora los módulos adicionales', intro: 'Descubre cómo ampliar tu proyecto. Guarda los módulos que te interesan y conversemos sobre su alcance. Tu selección no cambia la propuesta, la inversión ni el plazo.',
    close: 'Cerrar', loading: 'Cargando módulos…', empty: 'Todavía no hay módulos disponibles.', retry: 'Reintentar', loadError: 'No pudimos cargar los módulos. Inténtalo de nuevo.',
    save: 'Guardar mi interés', saveError: 'No pudimos guardar tu interés. Tu selección sigue aquí; puedes reintentar.', saved: 'Interés guardado. Revisaremos contigo el alcance antes de actualizar la propuesta.',
    interested: 'Me interesa', detail: 'Ver detalles', count: 'Módulos de interés', preview: 'Vista previa: el interés no se guardará.', unavailable: 'Intereses anteriores que ya no están en el catálogo',
  },
  en: {
    title: 'Explore additional modules', intro: 'Discover ways to expand your project. Save the modules that interest you and let’s discuss their scope. Your selection does not change the proposal, investment or timeline.',
    close: 'Close', loading: 'Loading modules…', empty: 'No modules are available yet.', retry: 'Try again', loadError: 'We could not load the modules. Please try again.',
    save: 'Save my interests', saveError: 'We could not save your interests. Your selection is still here; please try again.', saved: 'Interests saved. We will discuss the scope with you before updating the proposal.',
    interested: 'I’m interested', detail: 'View details', count: 'Modules of interest', preview: 'Preview: interests will not be saved.', unavailable: 'Previous interests no longer in the catalog',
  },
}
const t = computed(() => copy[props.language] || copy.es)
const unavailable = computed(() => {
  const active = new Set((catalog.value?.categories || []).flatMap(category => category.modules.map(module => module.id)))
  return previous.value.filter(module => !active.has(module.id))
})
const endpoint = computed(() => `proposals/${props.proposalUuid}/module-interests/`)

async function load() {
  const token = ++generation
  loading.value = true
  error.value = ''
  catalog.value = null
  success.value = false
  try {
    const [modules, interests] = await Promise.all([
      get_request(`additional-modules/public/?lang=${props.language}`),
      get_request(endpoint.value),
    ])
    if (token !== generation) return
    catalog.value = modules.data
    previous.value = interests.data.modules || []
    selected.value = previous.value.map(module => module.id)
  } catch {
    if (token === generation) error.value = t.value.loadError
  } finally {
    if (token === generation) loading.value = false
  }
}

async function save() {
  if (saving.value) return
  if (props.preview) { error.value = t.value.preview; return }
  const token = generation
  saving.value = true
  error.value = ''
  success.value = false
  try {
    const response = await put_request(endpoint.value, { module_ids: selected.value })
    if (token !== generation) return
    if (response.data.status === 'skipped') { error.value = t.value.preview; return }
    previous.value = response.data.modules
    success.value = true
    emit('saved', response.data)
  } catch {
    if (token === generation) error.value = t.value.saveError
  } finally {
    saving.value = false
  }
}

function close() {
  videoCard.value?.pause()
  generation += 1
  emit('close')
}
watch(() => [props.visible, props.proposalUuid, props.language], ([visible]) => {
  if (visible) void load()
  else { generation += 1; videoCard.value?.pause() }
}, { immediate: true })
watch(selected, () => { success.value = false }, { deep: true })
onBeforeUnmount(() => { generation += 1; videoCard.value?.pause() })
</script>

<template>
  <BaseModal :model-value="visible" kind="detail" :full-height="true" :theme="isDark ? 'dark' : 'light'" @close="close">
    <div class="shrink-0">
      <div class="flex items-start justify-between gap-4 border-b border-border-default p-5 sm:px-8">
        <div>
          <h2 class="text-xl font-semibold text-text-brand">{{ t.title }}</h2>
          <p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{{ t.intro }}</p>
        </div>
        <BaseButton variant="ghost" icon-only :aria-label="t.close" @click="close">✕</BaseButton>
      </div>
    </div>
    <div class="min-h-0 flex-1 space-y-6 overflow-y-auto p-5 sm:p-8" data-testid="module-interests-modal">
      <p v-if="loading" role="status" class="text-text-muted">{{ t.loading }}</p>
      <div v-else-if="!catalog" role="alert" class="space-y-3 text-danger-strong">
        <p>{{ error }}</p><BaseButton variant="secondary" @click="load">{{ t.retry }}</BaseButton>
      </div>
      <template v-else>
        <ExplainerVideoCard v-if="catalog.show_explainer_video !== false && video" ref="videoCard" :video="video" i18n-namespace="additionalModules" :content-locale="contentLocale" :content-messages="contentMessages" test-id="module-interests-video" class="mx-auto max-w-3xl" />
        <p v-if="!catalog.categories?.length" class="text-text-muted">{{ t.empty }}</p>
        <details v-for="(category, index) in catalog.categories" :key="category.id || category.slug" :open="index === 0" class="rounded-2xl border border-border-default bg-surface">
          <summary class="cursor-pointer p-5 text-lg font-medium text-text-brand">{{ category.name }} <span class="text-sm text-text-subtle">({{ category.modules.length }})</span></summary>
          <div class="grid gap-3 px-4 pb-4 sm:grid-cols-2">
            <article v-for="module in category.modules" :key="module.id" class="rounded-xl border border-border-default p-4">
              <h3 class="font-semibold text-text-brand">{{ module.icon }} {{ module.name }}</h3>
              <p class="mt-2 text-sm leading-6 text-text-muted">{{ module.summary }}</p>
              <label class="my-3 flex cursor-pointer items-center gap-2 text-sm font-medium text-text-brand">
                <input v-model="selected" :value="module.id" type="checkbox" :aria-label="`${t.interested}: ${module.name}`" :disabled="saving" class="h-4 w-4 rounded border-input-border accent-primary" />
                {{ t.interested }}
              </label>
              <details>
                <summary class="cursor-pointer text-sm text-text-muted">{{ t.detail }}</summary>
                <ModuleDetails :module="module" :language="language" compact class="mt-3" />
              </details>
            </article>
          </div>
        </details>
        <div v-if="unavailable.length" class="space-y-3 rounded-xl border border-border-default p-4">
          <h3 class="font-medium text-text-brand">{{ t.unavailable }}</h3>
          <label v-for="module in unavailable" :key="module.id" class="flex items-center gap-2 text-sm text-text-muted">
            <input v-model="selected" type="checkbox" :value="module.id" :disabled="saving" />
            {{ module[`name_${language}`] || module.name_es }}
          </label>
        </div>
      </template>
    </div>
    <template #footer>
      <div class="space-y-3 border-t border-border-default bg-surface p-5 sm:px-8">
        <p v-if="catalog && error" role="alert" class="text-sm text-danger-strong">{{ error }}</p>
        <p v-if="success" role="status" class="text-sm text-text-brand">{{ t.saved }}</p>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <span class="text-sm text-text-muted">{{ t.count }}: {{ selected.length }}</span>
          <BaseButton :loading="saving" :disabled="!catalog || loading" :disabled-reason="t.loading" @click="save">{{ t.save }}</BaseButton>
        </div>
      </div>
    </template>
  </BaseModal>
</template>
