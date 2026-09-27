<template>
  <BaseModal
    :model-value="open"
    kind="detail"
    title-id="project-assign-unlinked-title"
    @close="emit('close')"
  >
    <div class="px-6 pt-6 pb-2">
      <h3 id="project-assign-unlinked-title" class="text-lg font-bold text-text-default">
        Asignar registros a "{{ project?.name }}"
      </h3>
      <p class="text-sm text-text-subtle mt-1">
        Registros de {{ clientName }} que siguen sin proyecto. Nada se asigna
        sin tu confirmación: desmarca lo que no pertenezca a este proyecto.
      </p>
    </div>

    <div class="px-6 py-4" data-testid="project-assign-unlinked-modal">
      <p v-if="isLoadingPreview" class="text-sm text-text-subtle">
        Cargando registros...
      </p>

      <BaseAlert
        v-else-if="errorMessage"
        variant="warning"
        class="mb-4"
        data-testid="project-assign-unlinked-error"
      >
        {{ errorMessage }}
      </BaseAlert>

      <p
        v-if="!isLoadingPreview && isEmpty"
        class="text-sm text-text-subtle"
        data-testid="project-assign-unlinked-empty"
      >
        Todos los registros de este cliente ya tienen proyecto.
      </p>

      <template v-if="!isLoadingPreview && !isEmpty">
        <section v-if="hostings.length" class="mb-4">
          <h4 class="text-xs font-semibold uppercase tracking-wide text-text-subtle mb-2">
            Hostings ({{ hostings.length }})
          </h4>
          <ul class="space-y-1.5">
            <li v-for="record in hostings" :key="`hosting-${record.id}`">
              <BaseCheckbox
                v-model="selectedHostingIds"
                :value="record.id"
                :data-testid="`project-assign-unlinked-hosting-${record.id}`"
              >
                {{ record.label }}
              </BaseCheckbox>
            </li>
          </ul>
        </section>

        <section v-if="incomes.length" class="mb-4">
          <h4 class="text-xs font-semibold uppercase tracking-wide text-text-subtle mb-2">
            Ingresos ({{ incomes.length }})
          </h4>
          <ul class="space-y-1.5">
            <li v-for="record in incomes" :key="`income-${record.id}`">
              <BaseCheckbox
                v-model="selectedIncomeIds"
                :value="record.id"
                :data-testid="`project-assign-unlinked-income-${record.id}`"
              >
                {{ record.label }}
                <span class="text-xs text-text-subtle">
                  · {{ record.kind_label }} · {{ record.period_label }}
                </span>
              </BaseCheckbox>
            </li>
          </ul>
        </section>

        <section v-if="documents.length">
          <h4 class="text-xs font-semibold uppercase tracking-wide text-text-subtle mb-2">
            Documentos ({{ documents.length }})
          </h4>
          <ul class="space-y-1.5">
            <li v-for="record in documents" :key="`document-${record.id}`">
              <BaseCheckbox
                v-model="selectedDocumentIds"
                :value="record.id"
                :data-testid="`project-assign-unlinked-document-${record.id}`"
              >
                {{ record.number || record.label }}
                <span v-if="record.type_label" class="text-xs text-text-subtle">
                  · {{ record.type_label }}
                </span>
              </BaseCheckbox>
            </li>
          </ul>
        </section>
      </template>
    </div>

    <template #footer>
      <BaseModalActions>
        <BaseButton
          variant="secondary"
          size="sm"
          data-testid="project-assign-unlinked-cancel"
          @click="emit('close')"
        >
          {{ isEmpty ? 'Cerrar' : 'Cancelar' }}
        </BaseButton>
        <BaseControlGate
          v-if="!isEmpty"
          :reasons="selectedCount === 0 ? ['Selecciona al menos un registro para asignar.'] : []"
          label="Asignar no disponible"
          align="end"
        >
          <template #default="{ describedBy }">
            <BaseButton
              variant="primary"
              size="sm"
              :loading="store.isUpdating || isLoadingPreview"
              :disabled="selectedCount === 0"
              disabled-reason="Selecciona al menos un registro para asignar."
              :aria-describedby="describedBy"
              data-testid="project-assign-unlinked-confirm"
              @click="confirmAssign"
            >
              {{ store.isUpdating ? 'Asignando...' : `Asignar ${selectedCount} ${selectedCount === 1 ? 'registro' : 'registros'}` }}
            </BaseButton>
          </template>
        </BaseControlGate>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseCheckbox from '~/components/base/BaseCheckbox.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelProjectsStore } from '~/stores/panel_projects';

/**
 * The confirmation step of the assign flow (PA-51): shows the FULL list of
 * the client's records without a project and only sends the ids the
 * operator left checked. A 409 (the list moved between preview and apply)
 * reloads the preview instead of guessing — the plan the user sees is
 * always the plan that runs.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  project: { type: Object, default: null },
});

const emit = defineEmits(['close', 'assigned']);

const store = usePanelProjectsStore();
const notify = usePanelNotify();

const isLoadingPreview = ref(false);
const errorMessage = ref('');
const hostings = ref([]);
const incomes = ref([]);
const documents = ref([]);
const clientName = ref('');
const selectedHostingIds = ref([]);
const selectedIncomeIds = ref([]);
const selectedDocumentIds = ref([]);

const selectedCount = computed(
  () => selectedHostingIds.value.length
    + selectedIncomeIds.value.length
    + selectedDocumentIds.value.length,
);
const isEmpty = computed(
  () => hostings.value.length === 0
    && incomes.value.length === 0
    && documents.value.length === 0,
);

async function loadPreview() {
  isLoadingPreview.value = true;
  const result = await store.fetchUnlinkedRecords(props.project.id);
  isLoadingPreview.value = false;
  if (!result.success) {
    hostings.value = [];
    incomes.value = [];
    documents.value = [];
    errorMessage.value = result.message;
    return;
  }
  hostings.value = result.data.hostings;
  incomes.value = result.data.incomes;
  documents.value = result.data.documents ?? [];
  clientName.value = result.data.client?.name || '';
  // Everything checked by default: the common case is "yes, all of it",
  // and unchecking is the deliberate exception.
  selectedHostingIds.value = result.data.hostings.map((record) => record.id);
  selectedIncomeIds.value = result.data.incomes.map((record) => record.id);
  selectedDocumentIds.value = documents.value.map((record) => record.id);
}

watch(() => props.open, (open) => {
  if (open && props.project) {
    errorMessage.value = '';
    loadPreview();
  }
});

async function confirmAssign() {
  errorMessage.value = '';
  const result = await store.assignUnlinkedRecords(props.project.id, {
    hosting_ids: selectedHostingIds.value,
    income_ids: selectedIncomeIds.value,
    document_ids: selectedDocumentIds.value,
  });
  if (result.success) {
    notify.success({
      title: `Registros asignados a "${props.project.name}"`,
      detail: `${result.data.assigned_hostings} hostings, `
        + `${result.data.assigned_incomes} ingresos y `
        + `${result.data.assigned_documents ?? 0} documentos.`,
    });
    emit('assigned', result.data);
    return;
  }
  if (result.code === 'records_not_found' || result.code === 'records_changed') {
    // The list moved under the open dialog; show the fresh plan.
    errorMessage.value = 'La lista cambió mientras confirmabas. Revísala de nuevo.';
    await loadPreview();
    return;
  }
  errorMessage.value = result.message;
}
</script>
