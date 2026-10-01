<script setup>
import EntityHistoryTabs from '~/components/history/EntityHistoryTabs.vue';
import { computed } from 'vue'
import ProjectAccessEditor from '~/components/projects/ProjectAccessEditor.vue'
import ProjectClientAccessPolicyEditor from '~/components/projects/client-access/ProjectClientAccessPolicyEditor.vue'
import { createProjectClientAccessApi } from '~/services/projectClientAccessApi'
import { createProjectAccessApi } from '~/services/projectAccessApi'
import {
  create_request,
  delete_request,
  get_request,
  patch_request,
} from '~/stores/services/request_http'

const props = defineProps({
  open: { type: Boolean, default: false },
  project: { type: Object, default: null },
})

const emit = defineEmits(['close'])
const { t } = useI18n()

const api = computed(() => {
  if (!props.project?.id) return null
  return createProjectAccessApi({
    get: get_request,
    post: create_request,
    patch: patch_request,
    remove: delete_request,
  }, `projects/${props.project.id}/access/`)
})
const clientApi = computed(() => createProjectClientAccessApi({ get: get_request, post: create_request, patch: patch_request }, props.project?.id))
</script>

<template>
  <BaseModal
    :model-value="open"
    kind="detail"
    full-height
    title-id="project-access-modal-title"
    @close="emit('close')"
    @update:model-value="(value) => { if (!value) emit('close') }"
  >
    <div v-if="open && project && api" class="flex h-full min-h-0 flex-col" data-testid="project-access-modal">
      <header class="flex items-start justify-between gap-4 border-b border-border-muted px-5 py-4 panel-portrait:px-6">
        <div class="min-w-0">
          <h2 id="project-access-modal-title" class="text-lg font-semibold text-text-default">
            {{ t('projectAccess.modalTitle') }}
          </h2>
          <p class="mt-1 truncate text-sm text-text-subtle">{{ project.name }}</p>
        </div>
        <BaseActionButton
          action="close"
          :label="t('projectAccess.actions.close')"
          data-testid="project-access-modal-close"
          @click="emit('close')"
        />
      </header>
      <div class="min-h-0 flex-1 overflow-y-auto p-4 panel-portrait:p-6">
        <EntityHistoryTabs entity-type="project" :object-id="project.id">
          <ProjectAccessEditor :key="project.id" :api="api" />
          <ProjectClientAccessPolicyEditor :key="project.id" class="mt-6" :project-id="project.id" :api="clientApi" />
        </EntityHistoryTabs>
      </div>
    </div>
  </BaseModal>
</template>
