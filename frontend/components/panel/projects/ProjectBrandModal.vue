<script setup>
import { computed, onMounted, ref } from 'vue'
import { create_request, delete_request, get_request, patch_request } from '~/stores/services/request_http'

const props = defineProps({ project: { type: Object, required: true } })
const emit = defineEmits(['close'])
const { t } = useI18n()
const localePath = useLocalePath()
const assets = ref([])
const trees = ref([])
const available = ref([])
const selectedTree = ref('')
const title = ref('')
const category = ref('branding')
const file = ref(null)
const fileInput = ref(null)
const loading = ref(true)
const loaded = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const pendingDelete = ref(null)
const endpoint = `projects/${props.project.id}/brand/`
const categories = computed(() => ['branding', 'manual', 'design_system', 'logo', 'other'].map(value => ({ value, label: t(`projectBrand.categories.${value}`) })))
const choices = computed(() => [{ value: '', label: t('projectBrand.chooseLinktree') }, ...available.value.filter(tree => !tree.project).map(tree => ({ value: tree.id, label: `${tree.name} (@${tree.handle})` }))])

async function load() {
  loading.value = true
  loaded.value = false
  error.value = ''
  try {
    const [library, allTrees] = await Promise.all([get_request(endpoint), get_request('linktrees/admin/')])
    assets.value = library.data.assets
    trees.value = library.data.linktrees
    available.value = allTrees.data
    loaded.value = true
  } catch {
    error.value = t('projectBrand.loadError')
  } finally { loading.value = false }
}

async function mutate(action) {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await action()
    notice.value = t('projectBrand.saved')
  } catch (err) {
    const data = err.response?.data
    error.value = data?.file?.[0] || data?.title?.[0] || data?.detail || t('projectBrand.saveError')
  } finally { busy.value = false }
}

function associate(tree, project) {
  return mutate(async () => {
    const response = await patch_request(`linktrees/admin/${tree}/update/`, { project })
    available.value = available.value.map(item => item.id === tree ? { ...item, project } : item)
    trees.value = trees.value.filter(item => item.id !== tree)
    if (project) trees.value.push(response.data)
    selectedTree.value = ''
  })
}

function upload() {
  if (!file.value || !title.value.trim()) return
  if (file.value.size > 25 * 1024 * 1024) {
    error.value = t('projectBrand.tooLarge')
    return
  }
  return mutate(async () => {
    const data = new FormData()
    data.append('title', title.value.trim())
    data.append('category', category.value)
    data.append('file', file.value)
    const response = await create_request(endpoint, data)
    assets.value.unshift(response.data)
    title.value = ''
    file.value = null
    if (fileInput.value) fileInput.value.value = ''
  })
}

function removeAsset() {
  const asset = pendingDelete.value
  return mutate(async () => {
    await delete_request(`${endpoint}${asset.id}/`)
    assets.value = assets.value.filter(item => item.id !== asset.id)
    pendingDelete.value = null
  })
}
onMounted(load)
</script>

<template>
  <BaseModal :model-value="true" kind="detail" full-height title-id="project-brand-title" @close="emit('close')" @update:model-value="value => { if (!value) emit('close') }">
    <div class="flex h-full min-h-0 flex-col" data-testid="project-brand-modal">
      <header class="flex items-start justify-between gap-4 border-b border-border-muted px-5 py-4">
        <div class="min-w-0">
          <h2 id="project-brand-title" class="text-lg font-semibold text-text-default">{{ t('projectBrand.title') }}</h2>
          <p class="truncate text-sm text-text-subtle">{{ project.name }}</p>
        </div>
        <BaseActionButton action="close" :label="t('projectBrand.close')" @click="emit('close')" />
      </header>
      <div class="min-h-0 flex-1 space-y-6 overflow-y-auto p-4 panel-portrait:p-6">
        <p v-if="loading" role="status" class="text-sm text-text-subtle">{{ t('projectBrand.loading') }}</p>
        <p v-if="error" role="alert" class="text-sm text-danger-strong">{{ error }}</p>
        <p v-if="notice" role="status" class="text-sm text-text-brand">{{ notice }}</p>
        <BaseButton v-if="!loading && error" variant="secondary" :disabled="busy" :disabled-reason="t('projectBrand.saving')" @click="load">{{ t('projectBrand.retry') }}</BaseButton>
        <template v-if="!loading && loaded">
          <section class="space-y-3">
            <h3 class="font-semibold text-text-default">Linktrees</h3>
            <p class="text-sm text-text-subtle">{{ t('projectBrand.linktreeHint') }}</p>
            <div class="flex flex-col gap-2 panel-portrait:flex-row">
              <BaseSelect v-model="selectedTree" :options="choices" :aria-label="t('projectBrand.chooseLinktree')" class="panel-portrait:max-w-md" />
              <BaseButton :disabled="busy || !selectedTree" :disabled-reason="busy ? t('projectBrand.saving') : t('projectBrand.chooseLinktree')" @click="associate(selectedTree, project.id)">{{ t('projectBrand.link') }}</BaseButton>
            </div>
            <p v-if="!trees.length" class="text-sm text-text-subtle">{{ t('projectBrand.noLinktrees') }}</p>
            <ul class="space-y-2">
              <li v-for="tree in trees" :key="tree.id" class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-muted p-3">
                <NuxtLink :to="localePath(`/panel/linktrees/${tree.id}/edit`)" class="min-w-0 break-words text-sm text-text-brand hover:underline">{{ tree.name }} (@{{ tree.handle }})</NuxtLink>
                <BaseButton variant="ghost" size="sm" :disabled="busy" :disabled-reason="t('projectBrand.saving')" @click="associate(tree.id, null)">{{ t('projectBrand.unlink') }}</BaseButton>
              </li>
            </ul>
          </section>
          <section class="space-y-3">
            <h3 class="font-semibold text-text-default">{{ t('projectBrand.library') }}</h3>
            <p class="text-sm text-text-subtle">{{ t('projectBrand.privateHint') }}</p>
            <form class="space-y-3 rounded-xl border border-border-muted p-3" @submit.prevent="upload">
              <BaseFormRow :cols="2" :lg="3" :gap="4" :help="t('projectBrand.formats')" help-testid="project-brand-formats">
                <BaseFormField :label="t('projectBrand.assetTitle')" for="brand-title">
                  <BaseInput id="brand-title" v-model="title" required maxlength="200" />
                </BaseFormField>
                <BaseFormField :label="t('projectBrand.category')" for="brand-category">
                  <BaseSelect id="brand-category" v-model="category" :options="categories" />
                </BaseFormField>
                <BaseFormField :label="t('projectBrand.file')" for="brand-file">
                  <!-- design-tokens: allow-raw-input — native file picker. -->
                  <input id="brand-file" ref="fileInput" type="file" required class="block w-full min-w-0 text-sm text-text-default" accept=".pdf,.png,.jpg,.jpeg,.webp,.svg,.zip,.ai,.eps,.psd,.fig,.sketch,.docx,.pptx,.txt,.md,.json,.ttf,.otf,.woff,.woff2" @change="file = $event.target.files?.[0] || null" />
                </BaseFormField>
              </BaseFormRow>
              <BaseButton type="submit" :disabled="busy" :disabled-reason="t('projectBrand.saving')">{{ t('projectBrand.upload') }}</BaseButton>
            </form>
            <p v-if="!assets.length" class="text-sm text-text-subtle">{{ t('projectBrand.noAssets') }}</p>
            <ul class="space-y-2">
              <li v-for="asset in assets" :key="asset.id" class="rounded-lg border border-border-muted p-3">
                <p class="break-words font-medium text-text-default">{{ asset.title }}</p>
                <p class="break-all text-xs text-text-subtle">{{ t(`projectBrand.categories.${asset.category}`) }} · {{ asset.filename }} · {{ Math.ceil(asset.size / 1024) }} KB</p>
                <div class="mt-2 flex flex-wrap gap-2">
                  <BaseButton as="a" :to="`/api/${endpoint}${asset.id}/`" variant="secondary" size="sm">{{ t('projectBrand.download') }}</BaseButton>
                  <BaseButton variant="ghost" size="sm" :disabled="busy" :disabled-reason="t('projectBrand.saving')" @click="pendingDelete = asset">{{ t('projectBrand.remove') }}</BaseButton>
                </div>
                <div v-if="pendingDelete?.id === asset.id" class="mt-3 space-y-2" role="alert">
                  <p class="text-sm text-text-default">{{ t('projectBrand.confirmDelete', { title: asset.title }) }}</p>
                  <div class="flex gap-2">
                    <BaseButton variant="danger" size="sm" :disabled="busy" :disabled-reason="t('projectBrand.saving')" @click="removeAsset">{{ t('projectBrand.confirm') }}</BaseButton>
                    <BaseButton variant="secondary" size="sm" @click="pendingDelete = null">{{ t('projectBrand.cancel') }}</BaseButton>
                  </div>
                </div>
              </li>
            </ul>
          </section>
        </template>
      </div>
    </div>
  </BaseModal>
</template>
