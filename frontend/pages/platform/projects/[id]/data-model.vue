<template>
  <ProjectShell>
    <div id="platform-data-model" class="pb-12">
    <div v-if="dataModelStore.isLoading" class="py-20 text-center">
      <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-esmerald dark:border-t-lemon" />
    </div>

    <div v-else-if="dataModelStore.error" class="py-10 text-center" data-enter>
      <p class="text-sm text-red-600 dark:text-red-400">{{ dataModelStore.error }}</p>
      <BaseButton variant="secondary" size="sm" class="mt-3" @click="dataModelStore.fetchEntities(projectId)">
        Reintentar
      </BaseButton>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="mb-6" data-enter>
        <div class="flex items-center gap-3">
          <h1 class="text-xl font-bold text-text-default sm:text-2xl">Modelo de datos</h1>
          <span
            v-if="dataModelStore.entityCount"
            class="inline-flex h-6 min-w-[1.5rem] items-center justify-center rounded-full bg-indigo-500/10 px-2 text-[11px] font-semibold text-indigo-600 dark:text-indigo-400"
          >
            {{ dataModelStore.entityCount }}
          </span>
        </div>
      </div>

      <!-- Admin: JSON upload section -->
      <div
        v-if="authStore.isAdmin"
        class="mb-8 rounded-2xl border border-border-default bg-surface p-5"
        data-enter
      >
        <h2 class="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Subir modelo de datos</h2>

        <!-- Template buttons -->
        <div class="mb-4 flex flex-wrap gap-2">
          <BaseButton variant="secondary" size="sm" @click="copyTemplate">
            {{ templateCopied ? 'Copiado' : 'Copiar plantilla' }}
          </BaseButton>
          <BaseButton variant="secondary" size="sm" @click="downloadTemplate">
            Descargar plantilla
          </BaseButton>
        </div>

        <!-- File upload -->
        <div class="mb-3">
          <input
            ref="fileInput"
            type="file"
            accept=".json"
            class="text-xs text-text-muted file:mr-3 file:rounded-xl file:border-0 file:bg-surface-muted/30 file:px-3 file:py-2 file:text-xs file:font-medium file:text-text-default dark:file:bg-white/10 dark:file:text-accent"
            @change="handleFileUpload"
          />
        </div>

        <!-- Textarea -->
        <textarea
          v-model="jsonRaw"
          rows="10"
          placeholder='{"entities": [{"name": "...", "description": "...", "keyFields": "...", "relationship": "..."}]}'
          class="mb-3 w-full rounded-xl border border-border-default bg-surface-muted/20 px-4 py-3 font-mono text-xs text-text-default dark:bg-surface-muted dark:text-white"
          @input="parseJson"
        />

        <!-- Error -->
        <div v-if="jsonError" class="mb-3 rounded-xl bg-red-50 px-4 py-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">
          {{ jsonError }}
        </div>

        <!-- Preview -->
        <div v-if="jsonParsed && !jsonError" class="mb-3 rounded-xl bg-primary-soft px-4 py-2 text-xs text-text-brand">
          {{ jsonParsed.entities.length }} entidad{{ jsonParsed.entities.length !== 1 ? 'es' : '' }} detectada{{ jsonParsed.entities.length !== 1 ? 's' : '' }}:
          {{ jsonParsed.entities.map(e => e.name).join(', ') }}
        </div>

        <!-- Submit -->
        <BaseButton variant="accent" size="md" :disabled="!jsonParsed || jsonError || dataModelStore.isUploading" @click="handleSubmit">
          {{ dataModelStore.isUploading ? 'Subiendo...' : 'Subir modelo de datos' }}
        </BaseButton>

        <!-- Upload error -->
        <div v-if="uploadError" class="mt-3 rounded-xl bg-red-50 px-4 py-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">
          {{ uploadError }}
        </div>

        <!-- Upload success -->
        <div v-if="uploadSuccess" class="mt-3 rounded-xl bg-primary-soft px-4 py-2 text-xs text-text-brand">
          Modelo de datos actualizado correctamente.
        </div>
      </div>

      <!-- Entities table -->
      <div
        v-if="dataModelStore.entities.length"
        class="rounded-2xl border border-border-default bg-surface"
        data-enter
      >
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead>
              <tr class="border-b border-border-default">
                <th class="px-5 py-3 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Entidad</th>
                <th class="px-5 py-3 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Descripcion</th>
                <th class="px-5 py-3 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Campos clave</th>
                <th class="px-5 py-3 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Relacion</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entity in dataModelStore.entities"
                :key="entity.id"
                class="border-b border-border-muted last:border-0"
              >
                <td class="px-5 py-3 font-semibold text-text-default">{{ entity.name }}</td>
                <td class="px-5 py-3 text-xs text-text-muted">{{ entity.description || '\u2014' }}</td>
                <td class="px-5 py-3">
                  <div v-if="entity.key_fields" class="flex flex-wrap gap-1">
                    <span
                      v-for="field in entity.key_fields.split(',')"
                      :key="field.trim()"
                      class="rounded-md bg-surface-muted/30 px-2 py-0.5 text-[11px] font-medium text-text-default dark:bg-white/10 dark:text-text-brand"
                    >
                      {{ field.trim() }}
                    </span>
                  </div>
                  <span v-else class="text-xs text-text-muted">&mdash;</span>
                </td>
                <td class="px-5 py-3 text-xs text-text-muted">{{ entity.relationship || '\u2014' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-else
        class="rounded-2xl border border-border-default bg-surface p-10 text-center"
        data-enter
      >
        <p class="text-sm text-text-muted">No hay modelo de datos definido para este proyecto.</p>
        <p v-if="authStore.isAdmin" class="mt-2 text-xs text-text-muted">Sube un JSON con las entidades para empezar.</p>
      </div>
</template>
  </div>
  </ProjectShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformDataModelStore } from '~/stores/platform-data-model'
import { usePlatformProjectsStore } from '~/stores/platform-projects'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'

definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
usePageEntrance('#platform-data-model')

const route = useRoute()
const localePath = useLocalePath()
const authStore = usePlatformAuthStore()
const projectsStore = usePlatformProjectsStore()
const dataModelStore = usePlatformDataModelStore()

const projectId = computed(() => route.params.id)

const jsonRaw = ref('')
const jsonError = ref('')
const jsonParsed = ref(null)
const templateCopied = ref(false)
const uploadError = ref('')
const uploadSuccess = ref(false)
const fileInput = ref(null)

function parseJson() {
  jsonError.value = ''
  jsonParsed.value = null
  uploadSuccess.value = false
  uploadError.value = ''

  const raw = jsonRaw.value.trim()
  if (!raw) return

  try {
    const parsed = JSON.parse(raw)
    if (!parsed.entities || !Array.isArray(parsed.entities)) {
      jsonError.value = 'El JSON debe contener una clave "entities" con un array.'
      return
    }
    for (let i = 0; i < parsed.entities.length; i++) {
      const e = parsed.entities[i]
      if (!e.name || typeof e.name !== 'string') {
        jsonError.value = `La entidad #${i + 1} debe tener un campo "name" (string).`
        return
      }
    }
    jsonParsed.value = parsed
  } catch (err) {
    jsonError.value = `JSON invalido: ${err.message}`
  }
}

function handleFileUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    jsonRaw.value = e.target.result
    parseJson()
  }
  reader.readAsText(file)
}

async function copyTemplate() {
  const result = await dataModelStore.fetchTemplate(projectId.value)
  if (result.success) {
    await navigator.clipboard.writeText(JSON.stringify(result.data, null, 2))
    templateCopied.value = true
    setTimeout(() => { templateCopied.value = false }, 2000)
  }
}

async function downloadTemplate() {
  const result = await dataModelStore.fetchTemplate(projectId.value)
  if (result.success) {
    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'data-model-template.json'
    a.click()
    URL.revokeObjectURL(url)
  }
}

async function handleSubmit() {
  if (!jsonParsed.value) return
  uploadError.value = ''
  uploadSuccess.value = false

  const result = await dataModelStore.uploadEntities(projectId.value, jsonParsed.value)
  if (result.success) {
    uploadSuccess.value = true
    jsonRaw.value = ''
    jsonParsed.value = null
    if (fileInput.value) fileInput.value.value = ''
  } else {
    uploadError.value = result.message
  }
}

onMounted(async () => {
  await Promise.all([
    projectsStore.fetchProject(projectId.value),
    dataModelStore.fetchEntities(projectId.value),
  ])
})

</script>
