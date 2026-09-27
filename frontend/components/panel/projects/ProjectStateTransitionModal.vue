<script setup>
import { computed, ref, watch } from 'vue';
import { useProjectStateStore } from '~/stores/project_states';
import { stateBadgeVariant } from '~/utils/documentState';
import ProjectStateHelpBadge from './ProjectStateHelpBadge.vue';

const props = defineProps({
  open: { type: Boolean, default: false },
  project: { type: Object, default: null },
});
const emit = defineEmits(['close', 'changed']);
const stateStore = useProjectStateStore();

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

watch(() => props.open, async (open) => {
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
    @close="emit('close')"
  >
    <div class="border-b border-border-muted px-6 pb-4 pt-6">
      <h2 id="project-state-transition-title" class="text-lg font-bold text-text-default">Cambiar estado</h2>
      <p class="mt-1 text-sm text-text-subtle">
        {{ project?.name }} · {{ project?.status_label || 'Sin clasificar' }}
      </p>
    </div>

    <div class="space-y-5 px-6 py-5" data-testid="project-state-transition-modal">
      <BaseAlert v-if="project?.state_review_required" variant="warning">
        Este proyecto viene del catálogo anterior. Revisa y confirma su estado real.
      </BaseAlert>
      <BaseAlert v-if="project?.state_suggestion" variant="warning" data-testid="project-state-suggestion">
        {{ project.state_suggestion.message }}
      </BaseAlert>

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
        class="w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm"
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
        <BaseButton variant="secondary" @click="emit('close')">Cancelar</BaseButton>
        <BaseButton
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
