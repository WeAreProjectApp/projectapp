<script setup>
import BaseModal from '~/components/base/BaseModal.vue'

defineProps({
  project: { type: Object, default: null },
})
const emit = defineEmits(['close', 'action'])
const actions = [
  { id: 'ideas', icon: 'list', label: 'projectIdeas.navigation' },
  { id: 'brand', icon: 'folders', label: 'projectBrand.title' },
  { id: 'detail', icon: 'view', label: 'projectAccess.projectActions.detail' },
  { id: 'space', icon: 'open-platform', label: 'projectAccess.projectActions.space' },
  { id: 'edit', icon: 'edit', label: 'projectAccess.projectActions.edit' },
  { id: 'communications', icon: 'communications', label: 'projectAccess.projectActions.communications' },
  { id: 'state', icon: 'change-status', label: 'projectAccess.projectActions.state' },
  { id: 'history', icon: 'list', label: 'projectAccess.projectActions.history' },
  { id: 'delete', icon: 'delete', label: 'projectAccess.deletion.title', danger: true },
]
</script>

<template>
  <BaseModal
    :model-value="Boolean(project)"
    kind="confirm"
    size="sm"
    title-id="project-actions-title"
    @close="emit('close')"
  >
    <div v-if="project" data-testid="project-actions-modal">
      <div class="border-b border-border-muted px-6 pb-4 pt-6">
        <h3 id="project-actions-title" class="text-base font-bold text-text-default">{{ project.name }}</h3>
        <p class="mt-1 text-sm text-text-muted">{{ project.client_name || project.client?.name }}</p>
      </div>
      <ul class="py-2">
        <li v-for="action in actions" :key="action.id">
          <!-- design-tokens: allow-raw-button -->
          <button
            type="button"
            class="flex w-full items-center gap-3 px-6 py-3 text-left text-sm transition-colors"
            :class="action.danger ? 'text-danger-strong hover:bg-danger-soft' : 'text-text-default hover:bg-surface-raised'"
            :data-testid="`project-actions-${action.id}`"
            @click="emit('action', action.id, project)"
          >
            <BaseActionIcon :action="action.icon" class="h-5 w-5" />
            <span>{{ $t(action.label) }}</span>
          </button>
        </li>
      </ul>
      <div class="border-t border-border-muted px-6 py-3 text-right">
        <BaseButton variant="ghost" size="sm" @click="emit('close')">{{ $t('projectAccess.actions.close') }}</BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
