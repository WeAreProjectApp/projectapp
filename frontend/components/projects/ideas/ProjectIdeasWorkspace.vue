<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { usePlatformIdeasStore } from '~/stores/platform-ideas'
import { normalizeApiError } from '~/stores/services/normalize_api_error'
import { formatDateTime } from '~/utils/formatDate'
import ProjectIdeaComposer from './ProjectIdeaComposer.vue'
import ProjectIdeaHistory from './ProjectIdeaHistory.vue'
import ProjectIdeaCollectionBuilder from './ProjectIdeaCollectionBuilder.vue'
import ProjectIdeaCollectionCard from './ProjectIdeaCollectionCard.vue'

const props = defineProps({ projectId: { type: Number, required: true }, api: { type: Object, required: true }, isAdmin: Boolean, canWrite: { type: Boolean, default: true } })
const { t } = useI18n()
const store = usePlatformIdeasStore()
const editing = ref(null)
const composerKey = ref(0)
const selectedIds = ref([])
const historyId = ref(null)
const localError = ref('')
const createdCollection = ref(null)
const selected = computed(() => store.items.filter((item) => selectedIds.value.includes(item.id)))

async function load(page = 1) {
  localError.value = ''
  createdCollection.value = null
  const loaded = await store.load(props.projectId, props.api, page)
  if (loaded && props.isAdmin) {
    try { await store.loadCollections(props.api) }
    catch (error) { localError.value = normalizeApiError(error).message }
  }
}
watch(() => props.projectId, () => {
  editing.value = null
  selectedIds.value = []
  historyId.value = null
  localError.value = ''
  composerKey.value += 1
  load()
}, { immediate: true })

async function submit(text) {
  const result = await store.mutate(props.api, editing.value ? 'edit' : 'create', { text, idea: editing.value })
  if (result) { editing.value = null; composerKey.value += 1 }
}
async function archive(item) {
  await store.mutate(props.api, item.archived ? 'restore' : 'archive', { idea: item })
  selectedIds.value = []
}
async function collect(title) {
  const result = await store.mutate(props.api, 'collect', { title, selected: selected.value })
  if (result) { createdCollection.value = result; selectedIds.value = []; await loadCollections(1) }
}
async function loadCollections(page) {
  try { await store.loadCollections(props.api, page) }
  catch (error) { localError.value = normalizeApiError(error).message }
}
onBeforeUnmount(() => store.reset())
</script>

<template>
  <section class="space-y-6 text-text-default" data-testid="project-ideas-workspace">
    <header class="space-y-2">
      <h2 class="text-lg font-semibold">{{ t('projectIdeas.title') }}</h2>
      <p class="text-sm text-text-subtle">{{ t('projectIdeas.notice') }}</p>
    </header>
    <ProjectIdeaComposer v-if="canWrite" :key="composerKey" :initial="editing?.text || ''" :editing="Boolean(editing)" :busy="store.busy" @submit="submit" @cancel="editing = null; composerKey += 1" />
    <div v-if="store.error || localError" role="alert" class="space-y-2 rounded-xl border border-border-default p-4">
      <p>{{ store.error || localError }}</p>
      <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" type="button" @click="load()">{{ t('projectIdeas.retry') }}</BaseButton>
    </div>
    <p v-if="store.loading" role="status">{{ t('projectIdeas.loading') }}</p>
    <p v-else-if="!store.items.length">{{ t('projectIdeas.empty') }}</p>
    <article v-for="item in store.items" :key="item.id" class="space-y-3 rounded-xl border border-border-default p-4" :data-testid="`project-idea-${item.id}`">
      <div class="flex flex-wrap items-center gap-2 text-sm text-text-subtle">
        <span>{{ item.author }} · {{ formatDateTime(item.created_at) }}</span>
        <span v-if="item.archived" class="rounded-lg bg-surface-muted px-2 py-1">{{ t('projectIdeas.archived') }}</span>
        <span v-if="item.revision_number > 1">{{ t('projectIdeas.edited') }} · {{ formatDateTime(item.updated_at) }}</span>
      </div>
      <p class="whitespace-pre-wrap break-words" data-testid="idea-text">{{ item.text }}</p>
      <div class="flex flex-wrap items-center gap-2">
        <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="item.can_edit && canWrite" type="button" @click="editing = item; composerKey += 1">{{ t('projectIdeas.edit') }}</BaseButton>
        <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" type="button" @click="historyId = item.id">{{ t('projectIdeas.history') }}</BaseButton>
        <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="isAdmin" type="button" :disabled="store.busy" @click="archive(item)">{{ t(item.archived ? 'projectIdeas.restore' : 'projectIdeas.archive') }}</BaseButton>
        <label v-if="isAdmin" class="flex min-h-11 items-center gap-2 px-2 text-sm">
          <input v-model="selectedIds" type="checkbox" :value="item.id" :aria-label="`${t('projectIdeas.select')} ${item.id}`" />{{ t('projectIdeas.select') }}
        </label>
      </div>
    </article>
    <div v-if="store.count > 20" class="flex gap-3">
      <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="store.page > 1" type="button" @click="selectedIds = []; load(store.page - 1)">{{ t('projectIdeas.previous') }}</BaseButton>
      <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="store.page * 20 < store.count" type="button" @click="selectedIds = []; load(store.page + 1)">{{ t('projectIdeas.next') }}</BaseButton>
    </div>
    <ProjectIdeaHistory v-if="historyId" :key="`${projectId}-${historyId}`" :api="api" :idea-id="historyId" @close="historyId = null" />
    <ProjectIdeaCollectionBuilder v-if="isAdmin" :selected="selected" :busy="store.busy" @submit="collect" />
    <section v-if="isAdmin" class="space-y-3">
      <h3 class="font-medium">{{ t('projectIdeas.collections') }}</h3>
      <p class="text-sm text-text-subtle">{{ t('projectIdeas.collectionNotice') }}</p>
      <ProjectIdeaCollectionCard v-for="collection in store.collections" :key="collection.id" :collection="collection" :api="api" :initial-detail="createdCollection" />
      <div v-if="store.collectionCount > 20" class="flex gap-3">
        <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="store.collectionPage > 1" type="button" @click="loadCollections(store.collectionPage - 1)">{{ t('projectIdeas.previous') }}</BaseButton>
        <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="store.collectionPage * 20 < store.collectionCount" type="button" @click="loadCollections(store.collectionPage + 1)">{{ t('projectIdeas.next') }}</BaseButton>
      </div>
    </section>
  </section>
</template>
