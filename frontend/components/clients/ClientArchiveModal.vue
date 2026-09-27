<script setup>
/**
 * Archiving a client, with the project cascade shown before it happens.
 *
 * The warning is not decoration. Suspending a project cancels its future
 * unpaid incomes and archives its future hosting charges, and unarchiving the
 * client does NOT bring them back — so the operator gets the counts, in the
 * same words the project state modal already uses for the same consequence,
 * before the confirm button turns on.
 */
import { computed, ref, watch } from 'vue';
import { useProposalClientsStore } from '~/stores/proposal_clients';

const props = defineProps({
  open: { type: Boolean, default: false },
  client: { type: Object, default: null },
});
const emit = defineEmits(['close', 'changed']);
const clientsStore = useProposalClientsStore();

const preview = ref(null);
const isLoadingPreview = ref(false);
const isSubmitting = ref(false);
const errorMessage = ref('');

const isArchived = computed(() => Boolean(props.client?.is_archived));
const clientName = computed(() => props.client?.name || 'este cliente');

// Same phrasing as ProjectStateTransitionModal: it is the product's voice for
// exactly this consequence, and two wordings for one effect would read as two
// different effects.
const impactMessages = computed(() => {
  if (!preview.value) return [];
  const totals = preview.value.totals || {};
  const messages = [
    'Se detienen nuevos cobros y avisos mientras los proyectos sigan '
    + 'suspendidos. La deuda ya causada se conserva.',
  ];
  if (totals.future_incomes) {
    messages.push(`${totals.future_incomes} ingresos futuros se marcarán como cancelados.`);
  }
  if (totals.future_payments) {
    messages.push(`${totals.future_payments} cobros futuros de hosting se archivarán.`);
  }
  messages.push('Reactivar después no revierte esas cancelaciones.');
  return messages;
});

const applyBlockReasons = computed(() => {
  if (isArchived.value) return [];
  const reasons = [];
  if (!preview.value) {
    reasons.push('Revisa las consecuencias antes de archivar.');
  }
  (preview.value?.projects || []).forEach((project) => {
    (project.blockers || []).forEach((blocker) => reasons.push(blocker.message));
  });
  return reasons;
});

/**
 * @param {boolean} preserveError keep a message the caller just set. The stale
 *   confirmation path reloads the impact AND has something to say about why:
 *   clearing here would wipe the only explanation the operator gets.
 */
async function loadPreview({ preserveError = false } = {}) {
  if (!props.client) return;
  isLoadingPreview.value = true;
  if (!preserveError) errorMessage.value = '';
  const result = await clientsStore.previewClientArchive(props.client.id);
  isLoadingPreview.value = false;
  if (result.success) {
    preview.value = result.data;
  } else {
    errorMessage.value = result.errors?.message
      || 'No se pudo calcular el impacto sobre los proyectos.';
  }
}

watch(() => props.open, (open) => {
  preview.value = null;
  errorMessage.value = '';
  isSubmitting.value = false;
  if (open && !isArchived.value) loadPreview();
}, { immediate: true });

async function submit() {
  if (!props.client) return;
  isSubmitting.value = true;
  errorMessage.value = '';
  const result = isArchived.value
    ? await clientsStore.unarchiveClient(props.client.id)
    : await clientsStore.archiveClient(
      props.client.id,
      (preview.value?.projects || []).map((project) => ({
        project_id: project.project_id,
        impact_token: project.impact_token,
      })),
    );
  isSubmitting.value = false;
  if (result.success) {
    emit('changed', { archived: !isArchived.value, data: result.data });
    emit('close');
    return;
  }
  // A 409 here means the world moved between preview and confirm. Re-previewing
  // silently would hand the operator a confirm button for numbers they never
  // read, so it says so and reloads the impact instead.
  errorMessage.value = result.errors?.message
    || 'No se pudo cambiar el estado del cliente.';
  if (!isArchived.value) loadPreview({ preserveError: true });
}
</script>

<template>
  <BaseModal
    :model-value="open"
    kind="form"
    title-id="client-archive-title"
    @close="emit('close')"
  >
    <div class="border-b border-border-muted px-6 pb-4 pt-6">
      <h2 id="client-archive-title" class="text-lg font-bold text-text-default">
        {{ isArchived ? 'Desarchivar cliente' : 'Archivar cliente' }}
      </h2>
      <p class="mt-1 text-sm text-text-subtle">{{ clientName }}</p>
    </div>

    <div
      class="space-y-5 px-6 py-5"
      data-testid="client-archive-modal"
    >
      <template v-if="isArchived">
        <p class="text-sm text-text-default">
          El cliente vuelve a las listas activas y a los buscadores.
        </p>
        <BaseAlert variant="warning" data-testid="client-archive-unarchive-note">
          Sus proyectos siguen suspendidos. Reactivarlos es una decisión aparte:
          los ingresos que la cascada canceló no vuelven solos, así que
          devolverlos a activo dejaría las cifras mintiendo.
        </BaseAlert>
      </template>

      <template v-else>
        <p class="text-sm text-text-default">
          El cliente sale de las listas activas, de los buscadores y de los
          avisos automáticos.
        </p>

        <p v-if="isLoadingPreview" class="text-sm text-text-subtle" data-testid="client-archive-loading">
          Calculando el impacto sobre sus proyectos…
        </p>

        <section
          v-else-if="preview"
          class="space-y-4 rounded-xl border border-border-default bg-surface-raised p-4"
          data-testid="client-archive-impact"
        >
          <template v-if="preview.projects.length">
            <div>
              <h3 class="text-sm font-semibold text-text-default">
                {{ preview.projects.length }}
                {{ preview.projects.length === 1 ? 'proyecto pasará' : 'proyectos pasarán' }}
                a «{{ preview.target_state_name }}»
              </h3>
              <ul class="mt-2 space-y-1 text-sm text-text-subtle">
                <li
                  v-for="project in preview.projects"
                  :key="project.project_id"
                  :data-testid="`client-archive-project-${project.project_id}`"
                >
                  {{ project.project_name }} · ahora en «{{ project.current_state }}»
                </li>
              </ul>
            </div>
            <ul class="space-y-1 text-sm text-text-default">
              <li v-for="message in impactMessages" :key="message">• {{ message }}</li>
            </ul>
          </template>
          <p v-else class="text-sm text-text-subtle" data-testid="client-archive-no-projects">
            No tiene proyectos activos: archivarlo no cambia ningún estado ni
            cancela ningún cobro.
          </p>

          <div v-if="preview.skipped.length" data-testid="client-archive-skipped">
            <h3 class="text-sm font-semibold text-text-default">Sin cambios</h3>
            <ul class="mt-2 space-y-1 text-sm text-text-subtle">
              <li v-for="item in preview.skipped" :key="item.project_id">
                {{ item.project_name }} · {{ item.label }}
              </li>
            </ul>
          </div>
        </section>
      </template>

      <BaseAlert v-if="errorMessage" variant="danger" data-testid="client-archive-error">
        {{ errorMessage }}
      </BaseAlert>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton variant="secondary" @click="emit('close')">Cancelar</BaseButton>
        <BaseControlGate
          :reasons="applyBlockReasons"
          label="Archivar no disponible"
          align="end"
        >
          <template #default="{ describedBy }">
            <BaseButton
              variant="primary"
              data-testid="client-archive-confirm"
              :loading="isSubmitting"
              :disabled="Boolean(applyBlockReasons.length)"
              :disabled-reason="applyBlockReasons.join(' ')"
              :aria-describedby="describedBy"
              @click="submit"
            >
              {{ isArchived ? 'Desarchivar' : 'Archivar' }}
            </BaseButton>
          </template>
        </BaseControlGate>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
