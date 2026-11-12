<script setup>
import { computed, ref, watch } from 'vue'
import BaseModal from '~/components/base/BaseModal.vue'
import { useI18n } from '#imports'
import { usePanelProjectsStore } from '~/stores/panel_projects'

const props = defineProps({ project: { type: Object, default: null }, isSuperuser: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'deleted', 'change-state'])
const store = usePanelProjectsStore()
const preview = ref(null)
const error = ref('')
const loading = ref(false)
const deleting = ref(false)
let requestVersion = 0
const blockers = computed(() => preview.value?.blockers || [])
const forceMode = ref(false);
const deletionPreview = ref(null);
const deletionLoading = ref(false);
const deletionError = ref('');
const confirmation = ref('');
const selectedDeletionKeys = ref([]);
const { locale } = useI18n();
const deletionLabel = (item) => locale.value.startsWith('en') ? item.label_en || item.label : item.label;
const deletionDescription = (item) => locale.value.startsWith('en') ? item.description_en || item.description : item.description;
let deletionVersion = 0;
const offersForceDelete = computed(() => props.isSuperuser);
const deleteBlockReasons = computed(() => {
  const reasons = [];
  if (deletionError.value) reasons.push(deletionError.value);
  if (!deletionPreview.value || deletionLoading.value) reasons.push('Revisa las dependencias antes de confirmar.');
  if (deletionPreview.value && !deletionPreview.value.can_delete) {
    const blockers = deletionPreview.value.blockers || [];
    reasons.push(...(blockers.length ? blockers.map(item => item.message)
      : ['La revisión no permite eliminar esta selección.']));
  }
  if (confirmation.value !== 'DELETE') reasons.push('Escribe exactamente DELETE en mayúsculas.');
  return reasons;
});

async function loadDeletionPreview({ resetSelection = false } = {}) {
  const id = props.project?.id;
  if (!id || !offersForceDelete.value) return;
  const version = ++deletionVersion;
  confirmation.value = '';
  if (resetSelection) selectedDeletionKeys.value = [];
  deletionError.value = '';
  deletionPreview.value = null;
  deletionLoading.value = true;
  const result = await store.previewDeletion(id, { force: true, deleteKeys: [...selectedDeletionKeys.value] });
  if (version !== deletionVersion || !forceMode.value) return;
  deletionLoading.value = false;
  if (result.success) deletionPreview.value = result.data;
  else deletionError.value = result.message;
}

watch(forceMode, (enabled) => {
  deletionVersion += 1;
  confirmation.value = '';
  deletionPreview.value = null;
  deletionLoading.value = false;
  deletionError.value = '';
  selectedDeletionKeys.value = [];
  if (enabled) loadDeletionPreview();
});

function toggleDeletionCategory(key, enabled) {
  selectedDeletionKeys.value = enabled
    ? [...new Set([...selectedDeletionKeys.value, key])]
    : selectedDeletionKeys.value.filter((item) => item !== key);
  loadDeletionPreview();
}

async function confirmForceDeletion() {
  if (deleting.value || deleteBlockReasons.value.length || !offersForceDelete.value) return;
  deleting.value = true;
  deletionError.value = '';
  const result = await store.deleteProject(props.project.id, {
    force: true, delete_keys: [...selectedDeletionKeys.value], confirmation: confirmation.value,
    impact_token: deletionPreview.value.impact_token,
  });
  deleting.value = false;
  if (result.success) {
    emit('deleted', result);
    emit('close');
  } else {
    confirmation.value = '';
    // A returned conflict is a new review, never an authorization to retry
    // using the confirmation of the old dependency graph.
    deletionPreview.value = result.preview || null;
    selectedDeletionKeys.value = result.preview?.delete_keys || [];
    deletionError.value = result.message;
  }
}


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
  deletionVersion += 1
  forceMode.value = false
  confirmation.value = ''
  deletionPreview.value = null
  preview.value = null
  error.value = ''
  loading.value = false
  if (project) loadPreview()
}, { immediate: true })

async function confirmDeletion() {
  if (forceMode.value || !preview.value?.can_delete || deleting.value || loading.value) return
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
      <div class="mt-2 flex items-start justify-between gap-4">
        <p class="min-w-0 break-words font-semibold text-text-default">{{ project.name }}</p>
        <div v-if="offersForceDelete" class="flex shrink-0 items-center gap-2" data-testid="project-delete-force-control">
          <span class="text-sm text-text-default">{{ $t('projectAccess.deletion.forceTitle') }}</span>
          <BaseToggle v-model="forceMode" :aria-label="$t('projectAccess.deletion.forceTitle')"
            :disabled="deleting" disabled-reason="La eliminación está en curso."
            on-class="bg-danger-strong" data-testid="project-force-delete-toggle" />
        </div>
      </div>
      <p class="text-sm text-text-muted">{{ project.client_name || project.client?.name }}</p>
      <template v-if="!forceMode">
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
      </template>
      <section v-if="forceMode" class="space-y-4" data-testid="project-force-delete-review">
        <BaseAlert variant="danger">{{ $t('projectAccess.deletion.forceWarning') }}</BaseAlert>
        <p v-if="deletionLoading" role="status" class="text-sm text-text-muted">{{ $t('projectAccess.deletion.loading') }}</p>
        <template v-if="deletionPreview">
          <p class="text-sm text-text-muted">{{ $t('projectAccess.deletion.forcePreserved') }}</p>
          <ul class="divide-y divide-border-muted rounded-lg border border-border-muted" data-testid="project-force-delete-dependencies">
            <li v-for="item in deletionPreview.dependencies" :key="item.key" class="flex items-start gap-3 px-3 py-3 text-sm">
              <div class="min-w-0 flex-1">
                <p class="break-words font-semibold text-text-default">{{ deletionLabel(item) }} <span class="tabular-nums">({{ item.count }})</span></p>
                <p class="mt-1 break-words text-text-muted">{{ deletionDescription(item) }}</p>
                <p class="mt-1 text-xs" :class="selectedDeletionKeys.includes(item.key) ? 'text-danger-strong' : 'text-text-muted'">{{ $t(selectedDeletionKeys.includes(item.key) ? 'projectAccess.deletion.selected' : 'projectAccess.deletion.retained') }}</p>
              </div>
              <BaseToggle
                :model-value="selectedDeletionKeys.includes(item.key)"
                :aria-label="`${$t('projectAccess.deletion.selectCategory')} ${deletionLabel(item)}`"
                :disabled="deleting || deletionLoading || item.selectable === false"
                :disabled-reason="item.selectable === false ? deletionDescription(item) : 'La revisión está en curso.'"
                on-class="bg-danger-strong"
                :data-testid="`project-delete-category-${item.key}`"
                @update:model-value="toggleDeletionCategory(item.key, $event)"
              />
            </li>
          </ul>
          <p class="text-sm text-text-muted">{{ $t('projectAccess.deletion.operationalRemoved') }}</p>
          <p class="text-sm text-text-muted">{{ $t('projectAccess.deletion.automationsStopped') }}</p>
          <BaseAlert v-if="deletionPreview.blockers?.length" variant="warning" data-testid="project-force-delete-blockers">
            <ul class="space-y-2"><li v-for="(blocker, index) in deletionPreview.blockers" :key="index">{{ blocker.message }}</li></ul>
          </BaseAlert>
          <BaseFormField v-slot="{ errorId }" :label="$t('projectAccess.deletion.confirmationLabel')" required :hint="$t('projectAccess.deletion.confirmationHint')">
            <BaseInput
              v-model="confirmation"
              autocomplete="off"
              autocapitalize="off"
              :spellcheck="false"
              :aria-label="$t('projectAccess.deletion.confirmationLabel')"
              :aria-describedby="errorId"
              :disabled="deleting"
              disabled-reason="La eliminación está en curso."
              data-testid="project-force-delete-confirmation"
            />
          </BaseFormField>
        </template>
        <BaseAlert v-if="deletionError" variant="danger" role="alert" data-testid="project-force-delete-error">{{ deletionError }}</BaseAlert>
        <BaseButton v-if="!deletionPreview && !deletionLoading" variant="secondary" data-testid="project-force-delete-retry" @click="loadDeletionPreview">{{ $t('projectAccess.deletion.retry') }}</BaseButton>
      </section>
      <p v-if="error && !forceMode" role="alert" class="mt-4 text-sm text-danger-strong" data-testid="project-delete-error">{{ error }}</p>
      <div class="mt-6 flex flex-wrap justify-end gap-3">
        <BaseButton variant="ghost" :disabled="deleting" disabled-reason="La eliminación está en curso." @click="emit('close')">{{ $t('projectAccess.actions.cancel') }}</BaseButton>
        <BaseButton v-if="!forceMode && !preview && !loading" variant="secondary" data-testid="project-delete-retry" @click="loadPreview">{{ $t('projectAccess.deletion.retry') }}</BaseButton>
        <BaseButton v-if="!forceMode && blockers.length" variant="secondary" data-testid="project-delete-change-state" @click="emit('change-state', project)">{{ $t('projectAccess.deletion.changeState') }}</BaseButton>
        <BaseButton v-if="!forceMode && preview?.can_delete" variant="danger" :loading="deleting" :disabled="deleting" data-testid="project-delete-confirm" @click="confirmDeletion">{{ $t('projectAccess.deletion.confirm') }}</BaseButton>
        <BaseButton v-if="forceMode" variant="danger" data-testid="project-force-delete-confirm"
          :loading="deleting" :disabled="Boolean(deleteBlockReasons.length) || deleting"
          :disabled-reason="deleting ? 'La eliminación está en curso.' : deleteBlockReasons.join(' ')"
          @click="confirmForceDeletion">{{ $t('projectAccess.deletion.forceConfirm') }}</BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
