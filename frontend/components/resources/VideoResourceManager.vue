<script setup>
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
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
})
const emit = defineEmits(['updated'])
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
  return 'No se pudo guardar el recurso. Revisa la conexión y vuelve a intentarlo.'
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
    if (current === generation && exception.code !== 'ERR_CANCELED') error.value = 'No se pudo consultar el video. Vuelve a cargar el recurso.'
  } finally {
    if (current === generation) busy.value = false
  }
}
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
      error.value = 'Selecciona un archivo MP4.'
      fileInput.value?.focus()
      return
    }
    if (!file.size || file.size > 250 * 1024 * 1024) {
      error.value = 'El video debe tener contenido y pesar como máximo 250 MB.'
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
    notice.value = 'Recurso actualizado.'
    emit('updated', updated)
    if (!props.proposalId) await explainers.fetchSettings()
  } catch (exception) {
    if (current !== generation) return
    if (exception.code === 'ERR_CANCELED') notice.value = 'Carga cancelada. Consulta el recurso para comprobar su estado.'
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
  <section class="my-6 space-y-4 rounded-2xl border border-border-default bg-surface p-5" data-testid="video-resource-manager" aria-label="Recursos de video">
    <h2 class="text-lg font-medium text-text-default">{{ proposalId ? 'Video personalizado de esta propuesta' : 'Recursos · Video general' }}</h2>
    <p class="text-sm text-text-subtle">{{ proposalId ? 'Aparece después de la bienvenida en Vista Ejecutiva y Propuesta Completa. Si lo quitas, también desaparece su sección.' : 'Este video se utiliza en las vistas públicas del módulo.' }}</p>
    <BaseFormField v-if="!proposalId" label="Idioma del video">
      <BaseSelect v-model="selectedLanguage" aria-label="Idioma del video">
        <option value="es">Español</option><option value="en">English</option>
      </BaseSelect>
    </BaseFormField>
    <video v-if="video" :key="video.src" :src="video.src" :poster="video.poster" controls playsinline preload="metadata" class="aspect-video w-full max-w-3xl rounded-xl bg-surface-muted" aria-label="Vista previa del video" />
    <p v-else-if="resource" class="text-sm text-text-muted">No hay video para este recurso.</p>
    <p v-if="resource?.filename" class="break-words text-sm text-text-subtle">{{ resource.filename }} · {{ (resource.size / 1024 / 1024).toFixed(1) }} MB</p>
    <BaseFormField :for="inputId" label="Archivo de video" hint="MP4 · H.264 · audio AAC opcional · hasta 250 MB y 4K" :error="error">
      <input :id="inputId" ref="fileInput" type="file" accept="video/mp4,.mp4" class="block w-full text-sm text-text-default" @change="selectFile" />
    </BaseFormField>
    <div v-if="busy" role="status" class="text-sm text-text-muted">
      {{ progress === 100 ? 'Validando el video…' : `Procesando… ${progress}%` }}
      <progress :value="progress" max="100" class="w-full" aria-label="Progreso de carga" />
    </div>
    <BaseAlert v-if="notice" variant="info" role="status">{{ notice }}</BaseAlert>
    <div class="flex flex-wrap gap-3">
      <BaseButton v-if="busy" variant="secondary" @click="controller?.abort()">Cancelar</BaseButton>
      <template v-else>
        <BaseButton v-if="resource" @click="save('upload')">{{ video ? 'Sustituir video' : 'Cargar video' }}</BaseButton>
        <BaseButton v-if="video" variant="secondary" @click="confirmRemove = true">Quitar video</BaseButton>
        <BaseButton v-if="resource && !proposalId && resource.mode !== 'default'" variant="secondary" @click="save('restore-default')">Restaurar predeterminado</BaseButton>
        <BaseButton variant="ghost" @click="load">Consultar recurso</BaseButton>
      </template>
    </div>
    <BaseModal :model-value="confirmRemove" kind="confirm" padding="md" @update:model-value="confirmRemove = $event">
      <h2 class="mb-3 text-lg font-medium text-text-default">Quitar video</h2>
      <p class="text-sm text-text-default">El video dejará de aparecer. Puedes cargar otro cuando lo necesites.</p>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="secondary" @click="confirmRemove = false">Cancelar</BaseButton>
          <BaseButton @click="confirmRemove = false; save('remove')">Quitar video</BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </section>
</template>
