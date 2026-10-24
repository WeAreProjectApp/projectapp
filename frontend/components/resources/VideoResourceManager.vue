<script setup>
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
import { useI18n } from '#imports'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import BaseModal from '~/components/base/BaseModal.vue'
import BaseModalActions from '~/components/base/BaseModalActions.vue'
import { explainerVideoFor } from '~/composables/useExplainerVideos'
import { useVideoResourcesStore } from '~/stores/video_resources'
import { useExplainerVideosStore } from '~/stores/explainer_videos'

const props = defineProps({
  module: { type: String, default: 'proposal' },
  proposalId: { type: Number, default: null },
  language: { type: String, default: 'es' },
  languages: { type: Array, default: () => ['es', 'en'] },
})
const emit = defineEmits(['updated'])
const { t } = useI18n()
const label = (key, params) => t(`videoResources.${key}`, params)
const store = useVideoResourcesStore()
const explainers = useExplainerVideosStore()
const selectedLanguage = ref(props.language)
const resource = ref(null)
const error = ref('')
const notice = ref('')
const busy = ref(false)
const progress = ref(0)
const selectedFile = ref(null)
const confirmRemove = ref(false)
const fileInput = ref(null)
const inputId = useId()
let controller
let generation = 0
const path = computed(() => props.proposalId
  ? `video-resources/admin/proposals/${props.proposalId}/`
  : `video-resources/admin/modules/${props.module}/${selectedLanguage.value}/`)
const video = computed(() => resource.value?.mode === 'uploaded'
  ? resource.value.video
  : resource.value?.mode === 'default' ? explainerVideoFor(props.module, selectedLanguage.value) : null)

function messageFor(exception) {
  const data = exception.response?.data
  if (data?.file) return [].concat(data.file).join(' ')
  if (data?.detail) return String(data.detail)
  return label('saveError')
}

async function load() {
  const current = ++generation
  controller?.abort()
  controller = new AbortController()
  resource.value = null
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
  busy.value = true
  error.value = ''
  try {
    const data = await store.fetchResource(path.value, { signal: controller.signal })
    if (current === generation) resource.value = data
  } catch (exception) {
    if (current === generation && exception.code !== 'ERR_CANCELED') error.value = label('loadError')
  } finally {
    if (current === generation) busy.value = false
  }
}
watch(() => props.language, (value) => { selectedLanguage.value = value })
watch(path, load, { immediate: true })
onBeforeUnmount(() => { generation++; controller?.abort() })

function selectFile(event) {
  selectedFile.value = event.target.files?.[0] || null
  error.value = ''
  notice.value = ''
}

async function save(action) {
  error.value = ''
  notice.value = ''
  if (action === 'upload') {
    const file = selectedFile.value
    if (!file || !file.name.toLowerCase().endsWith('.mp4') || (file.type && file.type !== 'video/mp4')) {
      error.value = label('invalidFile')
      fileInput.value?.focus()
      return
    }
    if (!file.size || file.size > 250 * 1024 * 1024) {
      error.value = label('invalidSize')
      fileInput.value?.focus()
      return
    }
  }
  if (!resource.value) return
  const current = ++generation
  controller = new AbortController()
  busy.value = true
  progress.value = 0
  const data = new FormData()
  data.append('revision', resource.value.revision)
  data.append('action', action)
  if (action === 'upload') data.append('file', selectedFile.value)
  try {
    const updated = await store.updateResource(path.value, data, {
      signal: controller.signal,
      onUploadProgress: ({ loaded, total }) => { progress.value = total ? Math.round(100 * loaded / total) : 0 },
    })
    if (current !== generation) return
    resource.value = updated
    selectedFile.value = null
    if (fileInput.value) fileInput.value.value = ''
    notice.value = label('saved')
    emit('updated', updated)
    if (!props.proposalId && !props.module.startsWith('platform-')) await explainers.fetchSettings()
  } catch (exception) {
    if (current !== generation) return
    if (exception.code === 'ERR_CANCELED') notice.value = label('cancelled')
    else error.value = messageFor(exception)
    // The server may have completed a cancelled transfer; also resolve stale revisions.
    if (exception.code === 'ERR_CANCELED' || exception.response?.status === 409) {
      try { resource.value = await store.fetchResource(path.value) } catch { /* The retry remains visible. */ }
    }
  } finally {
    if (current === generation) busy.value = false
  }
}
</script>

<template>
  <section class="my-6 space-y-4 rounded-2xl border border-border-default bg-surface p-5" data-testid="video-resource-manager" :aria-label="label('title')">
    <h2 class="text-lg font-medium text-text-default">{{ label(proposalId ? 'personalizedTitle' : 'title') }}</h2>
    <p class="text-sm text-text-subtle">{{ label(proposalId ? 'personalizedDescription' : 'description') }}</p>
    <BaseFormField v-if="!proposalId" :label="label('language')">
      <BaseSelect v-model="selectedLanguage" :aria-label="label('language')">
        <option v-for="language in languages" :key="language" :value="language">{{ label(language === 'es' ? 'spanish' : 'english') }}</option>
      </BaseSelect>
    </BaseFormField>
    <video v-if="video" :key="video.src" :src="video.src" :poster="video.poster" controls playsinline preload="metadata" class="aspect-video w-full max-w-3xl rounded-xl bg-surface-muted" :aria-label="label('preview')" />
    <p v-else-if="resource" class="text-sm text-text-muted">{{ label('empty') }}</p>
    <p v-if="resource?.filename" class="break-words text-sm text-text-subtle">{{ resource.filename }} · {{ (resource.size / 1024 / 1024).toFixed(1) }} MB</p>
    <BaseFormField :for="inputId" :label="label('file')" :hint="label('hint')" :error="error">
      <input :id="inputId" ref="fileInput" type="file" accept="video/mp4,.mp4" class="block w-full text-sm text-text-default" @change="selectFile" />
    </BaseFormField>
    <div v-if="busy" role="status" class="text-sm text-text-muted">
      {{ label(progress === 100 ? 'validating' : 'processing', { progress }) }}
      <progress :value="progress" max="100" class="w-full" :aria-label="label('progress')" />
    </div>
    <BaseAlert v-if="notice" variant="info" role="status">{{ notice }}</BaseAlert>
    <div class="flex flex-wrap gap-3">
      <BaseButton v-if="busy" variant="secondary" @click="controller?.abort()">{{ label('cancel') }}</BaseButton>
      <template v-else>
        <BaseButton v-if="resource" @click="save('upload')">{{ label(video ? 'replace' : 'upload') }}</BaseButton>
        <BaseButton v-if="video" variant="secondary" @click="confirmRemove = true">{{ label('remove') }}</BaseButton>
        <BaseButton v-if="resource && !proposalId && resource.mode !== 'default'" variant="secondary" @click="save('restore-default')">{{ label('restore') }}</BaseButton>
        <BaseButton variant="ghost" @click="load">{{ label('reload') }}</BaseButton>
      </template>
    </div>
    <BaseModal :model-value="confirmRemove" kind="confirm" padding="md" @update:model-value="confirmRemove = $event">
      <h2 class="mb-3 text-lg font-medium text-text-default">{{ label('remove') }}</h2>
      <p class="text-sm text-text-default">{{ label('removeHelp') }}</p>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="secondary" @click="confirmRemove = false">{{ label('cancel') }}</BaseButton>
          <BaseButton @click="confirmRemove = false; save('remove')">{{ label('remove') }}</BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </section>
</template>
