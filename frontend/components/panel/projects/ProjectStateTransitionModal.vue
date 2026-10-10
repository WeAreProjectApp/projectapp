<script setup>
import { computed, ref, watch } from 'vue';
import { useI18n } from '#imports';
import { useProjectStateStore } from '~/stores/project_states';
import { usePanelProjectsStore } from '~/stores/panel_projects';
import { stateBadgeVariant } from '~/utils/documentState';
import ProjectStateHelpBadge from './ProjectStateHelpBadge.vue';

const props = defineProps({
  open: { type: Boolean, default: false },
  project: { type: Object, default: null },
  allowForceDelete: { type: Boolean, default: false },
  isSuperuser: { type: Boolean, default: false },
});
const emit = defineEmits(['close', 'changed', 'deleted']);
const stateStore = useProjectStateStore();
const projectStore = usePanelProjectsStore();
const forceMode = ref(false);
const deletionPreview = ref(null);
const deletionLoading = ref(false);
const deleting = ref(false);
const deletionError = ref('');
const confirmation = ref('');
const selectedDeletionKeys = ref([]);
const { locale } = useI18n();
const deletionLabel = (item) => locale.value.startsWith('en') ? item.label_en || item.label : item.label;
const deletionDescription = (item) => locale.value.startsWith('en') ? item.description_en || item.description : item.description;
let deletionVersion = 0;
const offersForceDelete = computed(() => props.allowForceDelete && props.isSuperuser);
const deleteBlockReasons = computed(() => {
  const reasons = [];
  if (!deletionPreview.value || deletionLoading.value) reasons.push('Revisa las dependencias antes de confirmar.');
  if (deletionPreview.value && !deletionPreview.value.can_delete) reasons.push('Resuelve los datos compartidos o protegidos antes de eliminar.');
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
  deletionLoading.value = true;
  const result = await projectStore.previewDeletion(id, { force: true, deleteKeys: [...selectedDeletionKeys.value] });
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
  stateStore.clearPreview();
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
  const result = await projectStore.deleteProject(props.project.id, {
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

const selectedStateId = ref('');
const useExactTime = ref(false);
const effectiveAt = ref('');
const note = ref('');
const resolutions = ref({});
const reviewAttempted = ref(false);
const previewErrorMessage = ref('');
const applyErrorMessage = ref('');

const selectedState = computed(() => stateStore.activeStates.find(
  (state) => state.id === Number(selectedStateId.value),
));
const preview = computed(() => stateStore.preview);
const isDecommission = computed(
  () => selectedState.value?.operational_effect === 'decommissioned',
);
const isDirectDecommission = computed(() => (
  isDecommission.value
  && props.project?.current_state?.operational_effect !== 'suspended'
));
const stateError = computed(() => (
  reviewAttempted.value && !selectedStateId.value
    ? 'Elige el nuevo estado del proyecto.'
    : ''
));
const noteError = computed(() => (
  isDirectDecommission.value && !note.value.trim()
    ? 'Escribe una nota porque la baja omite el paso previo por Suspendido.'
    : ''
));

function incomeResolutionError(income) {
  if (!isDecommission.value) return '';
  return ['keep_receivable', 'write_off'].includes(resolutions.value[income.id])
    ? ''
    : `Decide qué hacer con el ingreso "${income.concept}".`;
}

const applyBlockReasons = computed(() => {
  const reasons = [];
  if (!selectedStateId.value) reasons.push('Elige el nuevo estado del proyecto.');
  if (!preview.value) reasons.push('Revisa las consecuencias antes de confirmar el cambio.');
  reasons.push(...(preview.value?.blockers || []).map((blocker) => blocker.message));
  if (isDecommission.value) {
    (preview.value?.pending_incomes || []).forEach((income) => {
      const error = incomeResolutionError(income);
      if (error) reasons.push(error);
    });
  }
  if (noteError.value) reasons.push(noteError.value);
  return reasons;
});
const canApply = computed(() => applyBlockReasons.value.length === 0);

const impactMessages = computed(() => {
  if (!preview.value) return [];
  const messages = [];
  if (preview.value.target_effect === 'suspended') {
    messages.push('Se detienen nuevos cobros y avisos mientras el proyecto siga suspendido. La deuda ya causada se conserva.');
  }
  if (preview.value.future_incomes?.length) {
    messages.push(`${preview.value.future_incomes.length} ingresos futuros se marcarán como cancelados.`);
  }
  if (preview.value.future_payments?.length) {
    messages.push(`${preview.value.future_payments.length} cobros futuros de hosting se archivarán.`);
  }
  if (['completed', 'decommissioned'].includes(preview.value.target_effect)) {
    messages.push(`${preview.value.active_hostings?.length || 0} hostings activos se desactivarán y la suscripción dejará de generar cobros.`);
  }
  if (preview.value.target_effect === 'completed') {
    messages.push('Completado registra que el proyecto terminó como debía y quedó financieramente cerrado.');
  }
  if (preview.value.target_effect === 'decommissioned') {
    messages.push('Dado de baja es definitivo; no atribuye culpa ni equivale a una pausa.');
  }
  return messages;
});

watch([() => props.open, () => props.project?.id], async ([open]) => {
  deletionVersion += 1;
  forceMode.value = false;
  selectedDeletionKeys.value = [];
  confirmation.value = '';
  deletionPreview.value = null;
  deletionLoading.value = false;
  deletionError.value = '';
  if (!open) return;
  stateStore.clearPreview();
  selectedStateId.value = '';
  useExactTime.value = false;
  effectiveAt.value = '';
  note.value = '';
  resolutions.value = {};
  reviewAttempted.value = false;
  previewErrorMessage.value = '';
  applyErrorMessage.value = '';
  if (!stateStore.states.length) await stateStore.fetchCatalog();
});

watch([selectedStateId, useExactTime, effectiveAt], () => {
  stateStore.clearPreview();
  resolutions.value = {};
  previewErrorMessage.value = '';
  applyErrorMessage.value = '';
});

function money(value) {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

async function reviewImpact() {
  reviewAttempted.value = true;
  if (!selectedStateId.value || !props.project?.id) return;
  previewErrorMessage.value = '';
  applyErrorMessage.value = '';
  const payload = { state_id: Number(selectedStateId.value) };
  if (useExactTime.value && effectiveAt.value) {
    payload.effective_at = new Date(effectiveAt.value).toISOString();
  }
  const result = await stateStore.previewTransition(props.project.id, payload);
  if (!result.success) previewErrorMessage.value = result.message;
}

async function applyState() {
  if (!canApply.value || !props.project?.id) return;
  applyErrorMessage.value = '';
  const payload = {
    state_id: Number(selectedStateId.value),
    impact_token: preview.value.impact_token,
    effective_at: preview.value.effective_at,
    note: note.value.trim(),
    resolutions: isDecommission.value
      ? preview.value.pending_incomes.map((income) => ({
        income_id: income.id,
        action: resolutions.value[income.id],
      }))
      : [],
  };
  const result = await stateStore.applyTransition(props.project.id, payload);
  if (!result.success) {
    applyErrorMessage.value = result.message;
    return;
  }
  emit('changed', result.data.project);
  emit('close');
}
</script>

<template>
  <BaseModal
    :model-value="open"
    kind="form"
    title-id="project-state-transition-title"
    :close-on-backdrop="!deleting"
    :close-on-esc="!deleting"
    @close="!deleting && emit('close')"
  >
    <div class="border-b border-border-muted px-6 pb-4 pt-6">
      <h2 id="project-state-transition-title" class="text-lg font-bold text-text-default">Cambiar estado</h2>
      <p class="mt-1 text-sm text-text-subtle">
        {{ project?.name }} · {{ project?.status_label || 'Sin clasificar' }}
      </p>
    </div>

    <div class="space-y-5 px-6 py-5" data-testid="project-state-transition-modal">
      <div v-if="offersForceDelete" class="flex items-center justify-between gap-4 rounded-lg border border-border-muted p-4">
        <div>
          <p class="font-semibold text-text-default">{{ $t('projectAccess.deletion.forceTitle') }}</p>
          <p class="mt-1 text-sm text-text-muted">{{ $t('projectAccess.deletion.forceHint') }}</p>
        </div>
        <BaseToggle
          v-model="forceMode"
          :aria-label="$t('projectAccess.deletion.forceTitle')"
          :disabled="deleting"
          disabled-reason="La eliminación está en curso."
          on-class="bg-danger-strong"
          data-testid="project-force-delete-toggle"
        />
      </div>

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
                <p class="mt-1 text-xs" :class="selectedDeletionKeys.includes(item.key) ? 'text-danger-strong' : 'text-text-subtle'">{{ $t(selectedDeletionKeys.includes(item.key) ? 'projectAccess.deletion.selected' : 'projectAccess.deletion.retained') }}</p>
              </div>
              <BaseToggle
                :model-value="selectedDeletionKeys.includes(item.key)"
                :aria-label="`${$t('projectAccess.deletion.selectCategory')} ${deletionLabel(item)}`"
                :disabled="deleting"
                disabled-reason="La eliminación está en curso."
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
      <template v-else>
      <BaseAlert v-if="project?.state_review_required" variant="warning">
        Este proyecto viene del catálogo anterior. Revisa y confirma su estado real.
      </BaseAlert>
      <BaseAlert v-if="project?.state_suggestion" variant="warning" data-testid="project-state-suggestion">
        {{ project.state_suggestion.message }}
      </BaseAlert>

      <!-- Alone in a two-column row: a state name needs half the width. -->
      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField
          v-slot="{ invalid, errorId }"
          label="Nuevo estado"
          required
          :error="stateError"
        >
          <select
            v-model="selectedStateId"
            aria-label="Nuevo estado del proyecto"
            :aria-invalid="invalid || undefined"
            :aria-describedby="errorId"
            data-testid="project-state-target"
            class="w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm"
          >
            <option value="">Selecciona el estado real…</option>
            <option
              v-for="state in stateStore.activeStates.filter((item) => item.id !== project?.current_state?.id)"
              :key="state.id"
              :value="state.id"
            >
              {{ state.name }}
            </option>
          </select>
        </BaseFormField>
      </BaseFormRow>

      <div v-if="selectedState" class="rounded-lg bg-surface-raised px-3 py-3 text-sm" data-testid="project-state-selected-help">
        <div class="flex items-center gap-2">
          <BaseBadge :variant="stateBadgeVariant(selectedState)">{{ selectedState.name }}</BaseBadge>
          <ProjectStateHelpBadge
            :state="selectedState"
            position="bottom"
            test-id="project-transition-state-help"
          />
        </div>
        <p class="mt-2 text-text-muted">{{ selectedState.description }}</p>
      </div>

      <label class="flex items-center gap-2 text-xs text-text-muted">
        <BaseToggle v-model="useExactTime" size="sm" />
        Registrar una fecha efectiva anterior
      </label>
      <input
        v-if="useExactTime"
        v-model="effectiveAt"
        type="datetime-local"
        :max="new Date().toISOString().slice(0, 16)"
        aria-label="Fecha efectiva de la transición"
        class="w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm panel-portrait:max-w-[17rem]"
      />

      <section
        class="space-y-3"
        aria-labelledby="project-state-review-title"
        data-testid="project-state-review-step"
      >
        <div>
          <h3 id="project-state-review-title" class="text-sm font-semibold text-text-default">
            Revisar consecuencias
          </h3>
          <p id="project-state-confirm-help" class="mt-1 text-xs text-text-muted">
            Calcula el impacto del estado elegido. La confirmación se habilita después de completar las decisiones necesarias.
          </p>
        </div>
        <BaseAlert
          v-if="previewErrorMessage"
          variant="danger"
          data-testid="project-state-error"
        >
          {{ previewErrorMessage }}
        </BaseAlert>
        <BaseButton
          variant="secondary"
          class="w-full"
          data-testid="project-state-preview"
          :loading="stateStore.isUpdating"
          @click="reviewImpact"
        >
          {{ stateStore.isUpdating && !preview ? 'Calculando…' : 'Revisar consecuencias' }}
        </BaseButton>
      </section>
      </template>

      <section v-if="preview" class="space-y-4 rounded-xl border border-border-default bg-surface-raised p-4" data-testid="project-state-impact">
        <h3 class="font-semibold text-text-default">Consecuencias antes de confirmar</h3>
        <ul class="space-y-2 text-sm text-text-muted">
          <li v-for="message in impactMessages" :key="message">• {{ message }}</li>
        </ul>

        <BaseAlert v-for="blocker in preview.blockers" :key="blocker.code" variant="danger">
          {{ blocker.message }}
        </BaseAlert>

        <div v-if="preview.pending_incomes?.length" class="space-y-2">
          <h4 class="text-sm font-semibold text-text-default">Ingresos ya causados</h4>
          <article v-for="income in preview.pending_incomes" :key="income.id" class="rounded-lg border border-border-muted bg-surface p-3">
            <div class="flex flex-wrap justify-between gap-2 text-sm">
              <span class="font-medium text-text-default">{{ income.concept }}</span>
              <span class="text-text-muted">Pendiente: {{ money(income.pending_amount) }}</span>
            </div>
            <BaseFormField
              v-if="isDecommission"
              v-slot="{ invalid, errorId }"
              class="mt-2"
              :error="incomeResolutionError(income)"
            >
              <select
                v-model="resolutions[income.id]"
                :aria-label="`Decisión para ${income.concept}`"
                :aria-invalid="invalid || undefined"
                :aria-describedby="errorId"
                class="w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm"
                :data-testid="`project-state-income-${income.id}`"
              >
                <option value="">Decide qué hacer…</option>
                <option value="keep_receivable">Conservar por cobrar, sin avisos automáticos</option>
                <option value="write_off">Dar el saldo por perdido</option>
              </select>
            </BaseFormField>
            <p v-else class="mt-1 text-xs text-text-subtle">La deuda se conserva.</p>
          </article>
        </div>

        <BaseFormField
          v-slot="{ invalid, errorId }"
          label="Nota de la transición"
          :required="isDirectDecommission"
          :error="noteError"
          :hint="isDirectDecommission ? 'Obligatoria porque la baja omite el paso previo por Suspendido.' : 'Queda registrada en el histórico.'"
        >
          <BaseTextarea
            v-model="note"
            :rows="3"
            :error="invalid"
            :aria-describedby="errorId"
            data-testid="project-state-note"
            placeholder="Contexto de la decisión…"
          />
        </BaseFormField>

        <BaseAlert
          v-if="applyErrorMessage"
          variant="danger"
          data-testid="project-state-error"
        >
          {{ applyErrorMessage }}
        </BaseAlert>
      </section>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton variant="secondary" :disabled="deleting" disabled-reason="La eliminación está en curso." @click="emit('close')">Cancelar</BaseButton>
        <BaseButton
          v-if="forceMode"
          variant="danger"
          data-testid="project-force-delete-confirm"
          :loading="deleting"
          :disabled="Boolean(deleteBlockReasons.length) || deleting"
          :disabled-reason="deleting ? 'La eliminación está en curso.' : deleteBlockReasons.join(' ')"
          @click="confirmForceDeletion"
        >{{ $t('projectAccess.deletion.forceConfirm') }}</BaseButton>
        <BaseButton
          v-else
          variant="primary"
          data-testid="project-state-apply"
          :loading="stateStore.isUpdating"
          :disabled="Boolean(applyBlockReasons.length)"
          :disabled-reason="applyBlockReasons.join(' ')"
          aria-describedby="project-state-confirm-help"
          @click="applyState"
        >
          {{ stateStore.isUpdating && preview ? 'Aplicando…' : 'Confirmar cambio' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
