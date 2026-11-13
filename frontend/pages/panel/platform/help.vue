<template>
  <div class="mx-auto max-w-screen-xl space-y-6" data-testid="platform-help-admin">
    <h1 class="text-2xl font-semibold">{{ tr('adminTitle') }}</h1>
    <p v-if="error" role="alert" class="text-danger-strong">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <NuxtLink :to="localePath('/panel/platform/feature-flags')" class="text-text-brand underline">{{ t('platformFeatures.manage') }}</NuxtLink>
    <section class="space-y-4 rounded-2xl border border-border-default bg-surface p-5">
      <h2 class="text-lg font-semibold">{{ tr('tours') }}</h2>
      <div class="flex flex-wrap gap-3"><BaseFormField :label="tr('selectTour')" for="help-selected-tour" class="min-w-0 flex-1"><BaseChoiceSelect id="help-selected-tour" v-model="selectedId" :options="store.tours.map(item => ({ value: item.id, label: `${item.content[`title_${language}`]} · ${item.published_revision || tr('draft')}` }))" /></BaseFormField><BaseButton @click="newTour">{{ tr('create') }}</BaseButton></div>
      <PlatformTourEditor v-if="selected" :key="selected.id || 'new'" :tour="selected" :targets="store.targets" :busy="busy" @save="saveTour" @publish="publish" @preview="showPreview" @revisions="showRevisions" />
      <div v-if="preview" class="space-y-3" data-testid="tour-admin-preview"><h3>{{ tr('preview') }}</h3><article v-for="step in preview.content.steps" :key="step.target" class="rounded-xl border border-border-default p-4"><h4 class="font-semibold">{{ step[`title_${language}`] }}</h4><p>{{ step[`description_${language}`] }}</p></article><BaseButton variant="ghost" @click="preview = null">{{ tr('close') }}</BaseButton></div>
      <details v-if="history.length" open><summary>{{ tr('revisions') }}</summary><article v-for="revision in history" :key="revision.number" class="mt-3 rounded-xl border border-border-default p-3"><p>{{ revision.number }} · {{ revision.content[`title_${language}`] }}</p><ol class="list-inside list-decimal"><li v-for="step in revision.content.steps" :key="step.target">{{ step[`title_${language}`] }} — {{ step[`description_${language}`] }}</li></ol></article></details>
    </section>
    <PlatformVideoResourcesManager />

    <section class="space-y-4 rounded-2xl border border-border-default bg-surface p-5"><h2 class="text-lg font-semibold">{{ tr('progressTitle') }}</h2><article v-for="row in store.progress.results" :key="`${row.user_id}:${row.tour}`" class="flex flex-wrap gap-3 border-b border-border-default pb-3"><span class="break-all">{{ row.user }}</span><span>{{ row.tour }}</span><span>{{ tr(`statuses.${row.status}`) }}</span></article><p v-if="!store.progress.results.length">{{ tr('empty') }}</p><div class="flex gap-3"><BaseButton :disabled="store.progress.page <= 1" :disabled-reason="tr('firstPage')" @click="loadProgress(store.progress.page - 1)">{{ tr('previousPage') }}</BaseButton><BaseButton :disabled="store.progress.page * 20 >= store.progress.count" :disabled-reason="tr('noMorePages')" @click="loadProgress(store.progress.page + 1)">{{ tr('nextPage') }}</BaseButton></div></section>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import BaseChoiceSelect from '~/components/base/BaseChoiceSelect.vue'
const localePath = useLocalePath()
import { usePlatformHelpAdminStore } from '~/stores/platform-help-admin'
import PlatformTourEditor from '~/components/platform/PlatformTourEditor.vue'
import PlatformVideoResourcesManager from '~/components/platform/PlatformVideoResourcesManager.vue'
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })
const { t, locale } = useI18n()
const tr = (key, params) => t(`platformHelp.${key}`, params)
const store = usePlatformHelpAdminStore()
const busy = ref(false), error = ref(''), message = ref(''), selectedId = ref(null), unsaved = ref(null), preview = ref(null), history = ref([])
const language = computed(() => locale.value.startsWith('en') ? 'en' : 'es')
const selected = computed(() => selectedId.value === 'new' ? unsaved.value : store.tours.find((tour) => tour.id === selectedId.value))
async function perform(action) { if (busy.value) return; busy.value = true; error.value = ''; message.value = ''; try { await action() } catch { error.value = tr('error') } finally { busy.value = false } }
function newTour() { selectedId.value = 'new'; unsaved.value = { slug: '', context: 'general', kind: 'novelty', priority: 100, is_active: true, content: { title_es: '', title_en: '', steps: [{ target: 'projects', title_es: '', title_en: '', description_es: '', description_en: '' }] } }; preview.value = null; history.value = [] }
function saveTour(tour) { return perform(async () => { const saved = await store.saveTour(tour); await store.load(); selectedId.value = saved.id; message.value = tr('saved') }) }
function publish(tour) { return perform(async () => { const saved = await store.saveTour(tour); await store.publish(saved); await store.load(); message.value = tr('saved') }) }
function showPreview(id) { return perform(async () => { preview.value = await store.preview(id) }) }
function showRevisions(id) { return perform(async () => { history.value = await store.revisions(id) }) }
function loadProgress(page) { return perform(() => store.loadProgress(page)) }
onMounted(() => perform(async () => { await store.load(); selectedId.value = store.tours[0]?.id; await store.loadProgress() }))
</script>
