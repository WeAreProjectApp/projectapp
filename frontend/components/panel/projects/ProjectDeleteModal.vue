<script setup>
import { computed, ref, watch } from 'vue'
import BaseModal from '~/components/base/BaseModal.vue'
import { usePanelProjectsStore } from '~/stores/panel_projects'

const props = defineProps({ project: { type: Object, default: null } })
const emit = defineEmits(['close', 'deleted', 'change-state'])
const store = usePanelProjectsStore()
const preview = ref(null)
const error = ref('')
const loading = ref(false)
const deleting = ref(false)
let requestVersion = 0
const blockers = computed(() => preview.value?.blockers || [])

async function loadPreview() {
  const project = props.project
  if (!project) return
  const version = ++requestVersion
  preview.value = null
  error.value = ''
  loading.value = true
  const result = await store.previewDeletion(project.id)
  if (version !== requestVersion) return
  loading.value = false
  if (result.success) preview.value = result.data
  else error.value = result.message
}

watch(() => props.project, (project) => {
  requestVersion += 1
  preview.value = null
  error.value = ''
  loading.value = false
  if (project) loadPreview()
}, { immediate: true })

async function confirmDeletion() {
  if (!preview.value?.can_delete || deleting.value) return
  deleting.value = true
  error.value = ''
  const result = await store.deleteProject(props.project.id)
  deleting.value = false
  if (result.success) emit('deleted', result)
  else {
    if (result.preview) preview.value = result.preview
    error.value = result.message
  }
}
</script>

<template>
  <BaseModal
    :model-value="Boolean(project)"
    kind="form"
    :close-on-backdrop="!deleting"
    :close-on-esc="!deleting"
    title-id="project-delete-title"
    @close="!deleting && emit('close')"
  >
    <div v-if="project" class="p-6" data-testid="project-delete-modal">
      <h3 id="project-delete-title" class="text-lg font-bold text-text-default">{{ $t('projectAccess.deletion.title') }}</h3>
      <p class="mt-2 break-words font-semibold text-text-default">{{ project.name }}</p>
      <p class="text-sm text-text-muted">{{ project.client_name || project.client?.name }}</p>
      <p v-if="loading" class="mt-4 text-sm text-text-muted" role="status">{{ $t('projectAccess.deletion.loading') }}</p>
      <p v-else-if="preview?.can_delete" class="mt-4 text-sm text-text-muted" data-testid="project-delete-warning">{{ $t('projectAccess.deletion.warning') }}</p>
      <template v-else-if="blockers.length">
        <p class="mt-4 text-sm text-text-muted">{{ $t('projectAccess.deletion.blocked') }}</p>
        <div class="mt-3 overflow-hidden rounded-lg border border-border-muted">
          <table class="w-full text-sm" data-testid="project-delete-dependencies">
            <caption class="sr-only">{{ $t('projectAccess.deletion.dependencies') }}</caption>
            <thead class="bg-surface-muted text-text-muted">
              <tr>
                <th scope="col" class="px-3 py-2 text-left">{{ $t('projectAccess.deletion.dependency') }}</th>
                <th scope="col" class="px-3 py-2 text-right">{{ $t('projectAccess.deletion.count') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in blockers" :key="item.key" class="border-t border-border-muted">
                <td class="break-words px-3 py-2 text-text-default">{{ $te(`projectAccess.deletion.labels.${item.key}`) ? $t(`projectAccess.deletion.labels.${item.key}`) : item.label }}</td>
                <td class="px-3 py-2 text-right tabular-nums text-text-default">{{ item.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="mt-3 text-sm text-text-muted">{{ $t('projectAccess.deletion.stateHint') }}</p>
      </template>
      <p v-if="error" role="alert" class="mt-4 text-sm text-danger-strong" data-testid="project-delete-error">{{ error }}</p>
      <div class="mt-6 flex flex-wrap justify-end gap-3">
        <BaseButton variant="ghost" :disabled="deleting" @click="emit('close')">{{ $t('projectAccess.actions.cancel') }}</BaseButton>
        <BaseButton v-if="!preview && !loading" variant="secondary" data-testid="project-delete-retry" @click="loadPreview">{{ $t('projectAccess.deletion.retry') }}</BaseButton>
        <BaseButton v-if="blockers.length" variant="secondary" data-testid="project-delete-change-state" @click="emit('change-state', project)">{{ $t('projectAccess.deletion.changeState') }}</BaseButton>
        <BaseButton v-if="preview?.can_delete" variant="danger" :loading="deleting" :disabled="deleting" data-testid="project-delete-confirm" @click="confirmDeletion">{{ $t('projectAccess.deletion.confirm') }}</BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
