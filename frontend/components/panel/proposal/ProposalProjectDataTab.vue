<template>
  <div class="space-y-5" data-testid="proposal-project-data">
    <section class="rounded-xl border border-border-muted bg-surface p-5">
      <h2 class="mb-4 text-base font-semibold text-text-default">Cliente y datos de contacto</h2>
      <fieldset :disabled="saving">
        <ProposalClientFields :proposal="proposal" :form="form"
          @client-selected="emit('client-selected', $event)" @create-inline-client="emit('create-inline-client', $event)" />
      </fieldset>
      <p v-if="retainedProject" class="mt-3 text-sm text-text-muted" data-testid="proposal-retained-project-note">El cliente pertenece a los datos conservados del proyecto eliminado. Sus fases y entregables quedaron en consulta: reasígnala abajo a un proyecto vigente del mismo cliente.</p>
      <p v-else-if="proposal.linked_project" class="mt-3 text-sm text-text-muted">El cliente pertenece al proyecto vinculado. Para cambiar su propietario, usa la acción Cambiar cliente desde Proyectos.</p>
      <BaseButton variant="primary" size="sm" class="mt-4" :loading="saving" @click="emit('save-client')">Guardar cliente</BaseButton>
    </section>
    <section class="rounded-xl border border-border-muted bg-surface p-5">
      <h2 class="text-base font-semibold text-text-default">Proyecto</h2>
      <p class="mt-2 text-sm text-text-default" data-testid="proposal-linked-project">{{ linkedProjectLabel }}</p>
      <BaseButton v-if="!proposal.linked_project" variant="primary" size="sm" class="mt-4"
        :disabled="!canReview" disabled-reason="La revisión del proyecto está disponible cuando la propuesta está en negociación o aceptada."
        @click="emit('review')">Revisar cliente, proyecto y documentos</BaseButton>
      <p v-if="!proposal.linked_project && !canReview" class="mt-2 text-xs text-text-muted">Podrás vincular un proyecto en negociación o al aceptar la propuesta. Cambiar el estado no crea proyectos automáticamente.</p>
      <template v-if="proposal.linked_project">
        <p class="mt-3 text-sm text-text-muted">La reasignación conserva la propuesta y traslada sus fases y recursos al proyecto elegido del mismo cliente.</p>
        <p v-if="loading" role="status" class="mt-3 text-sm text-text-muted">Cargando proyectos…</p>
        <label for="proposal-reassignment-project" class="mt-4 block text-sm text-text-default">Proyecto de destino</label>
        <BaseSelect id="proposal-reassignment-project" v-model="targetProjectId" :disabled="busy || loading" data-testid="proposal-reassignment-project">
          <option value="">Seleccionar proyecto</option>
          <option v-for="project in eligibleProjects" :key="project.id" :value="project.id">{{ project.name }}</option>
        </BaseSelect>
        <label for="proposal-reassignment-reason" class="mt-3 block text-sm text-text-default">Motivo</label>
        <BaseTextarea id="proposal-reassignment-reason" v-model="reason" :disabled="busy" :rows="2" data-testid="proposal-reassignment-reason" />
        <div v-if="hostingDecisionNeeded" class="mt-3 space-y-2 rounded-lg border border-border-default p-3" data-testid="proposal-reassignment-hosting">
          <p class="text-sm text-text-default">El destino tiene hosting activo: decide cuándo empieza a cobrarse esta fase.</p>
          <label for="proposal-reassignment-hosting-date" class="block text-sm text-text-default">Nueva fecha de inicio de hosting</label>
          <BaseInput id="proposal-reassignment-hosting-date" v-model="hostingStartDate" type="date" :disabled="busy" data-testid="proposal-reassignment-hosting-date" />
          <BaseCheckbox v-model="acceptHostingStart" :disabled="busy" data-testid="proposal-reassignment-accept-hosting">Acepto que la fase empiece a cobrarse con la fecha actual</BaseCheckbox>
        </div>
        <BaseButton variant="secondary" size="sm" class="mt-3" :loading="busy"
          :disabled="!targetProjectId || !reason.trim() || busy" disabled-reason="Selecciona un destino y explica el motivo de la reasignación."
          data-testid="proposal-reassignment-preview" @click="previewReassignment">Revisar reasignación</BaseButton>
        <div v-if="impact" class="mt-4 rounded-lg border border-border-default p-4" data-testid="proposal-reassignment-impact">
          <p class="text-sm text-text-default">{{ impact.source_project.name }}<span v-if="impact.source_project.retained"> (proyecto eliminado)</span> → {{ impact.target_project.name }}</p>
          <p class="mt-2 text-xs text-text-muted">{{ impact.deliverable_ids.length }} entregables · {{ impact.phase_ids.length }} fases · {{ impact.approval_file_ids.length }} archivos de aprobación.</p>
          <ul v-if="impact.blockers.length" class="mt-3 list-disc pl-5 text-sm text-danger-strong"><li v-for="item in impact.blockers" :key="item.code">{{ item.message }}</li></ul>
          <BaseButton variant="primary" size="sm" class="mt-3" :loading="busy" :disabled="Boolean(impact.blockers.length) || busy"
            disabled-reason="Resuelve las dependencias indicadas antes de confirmar."
            data-testid="proposal-reassignment-confirm" @click="confirmReassignment">Confirmar reasignación</BaseButton>
        </div>
      </template>
      <p v-if="error" role="alert" class="mt-3 text-sm text-danger-strong">{{ error }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue';
import ProposalClientFields from './ProposalClientFields.vue';
import { get_request } from '~/stores/services/request_http';
import { useProposalStore } from '~/stores/proposals';
import { usePanelNotify } from '~/composables/usePanelNotify';
const props = defineProps({ proposal: { type: Object, required: true }, form: { type: Object, required: true }, saving: { type: Boolean, default: false } });
const emit = defineEmits(['save-client', 'client-selected', 'create-inline-client', 'review']);
const store = useProposalStore();
const notify = usePanelNotify();
const projects = ref([]);
const loading = ref(false);
const busy = ref(false);
const error = ref('');
const targetProjectId = ref('');
const reason = ref('');
const impact = ref(null);
// Explicit hosting decision, asked only after a preview reports that a due phase
// would join the target's active subscription (charged by the next daily run).
const hostingDecisionNeeded = ref(false);
const hostingStartDate = ref('');
const acceptHostingStart = ref(false);
let requestId = '';
const hostingOptions = () => ({
  ...(hostingStartDate.value ? { hosting_start_date: hostingStartDate.value } : {}),
  ...(acceptHostingStart.value ? { accept_hosting_start: true } : {}),
});
const canReview = computed(() => ['negotiating', 'accepted'].includes(props.proposal.status));
// A forced deletion can retain the proposal's deliverable without a project:
// still linked to that history (id null), never shown as "sin proyecto".
const retainedProject = computed(() => Boolean(props.proposal.linked_project) && props.proposal.linked_project.id == null);
const linkedProjectLabel = computed(() => {
  if (!props.proposal.linked_project) return 'Sin proyecto vinculado';
  if (retainedProject.value) return `${props.proposal.linked_project.name || 'Proyecto sin nombre'} — proyecto eliminado`;
  return props.proposal.linked_project.name;
});
const eligibleProjects = computed(() => projects.value.filter(row => Number(row.client?.profile_id) === Number(props.proposal.client?.id) && row.id !== props.proposal.linked_project?.id && row.status !== 'archived'));
watch([targetProjectId, reason, hostingStartDate, acceptHostingStart], () => { impact.value = null; requestId = ''; error.value = ''; });
onMounted(async () => {
  if (!props.proposal.linked_project || !props.proposal.client?.id) return;
  loading.value = true;
  try { projects.value = (await get_request('projects/', { params: { client_profile_id: props.proposal.client.id } })).data.results || []; }
  catch { error.value = 'No se pudieron cargar los proyectos. Vuelve a abrir esta página para reintentar.'; }
  finally { loading.value = false; }
});
async function previewReassignment() {
  busy.value = true;
  error.value = '';
  try {
    const result = await store.previewProjectReassignment(props.proposal.id, Number(targetProjectId.value), hostingOptions());
    if (!result.success) throw new Error(result.message || 'No se pudo revisar la reasignación.');
    impact.value = result.data;
    if (result.data.blockers.some(item => item.code === 'pending_hosting_start')) hostingDecisionNeeded.value = true;
    requestId = crypto.randomUUID();
  } catch (exception) { error.value = exception.message; }
  finally { busy.value = false; }
}
async function confirmReassignment() {
  if (!impact.value || impact.value.blockers.length || busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    const result = await store.reassignProject(props.proposal.id, { target_project_id: Number(targetProjectId.value), reason: reason.value.trim(), expected_impact_hash: impact.value.impact_hash, request_id: requestId, ...hostingOptions() });
    if (!result.success) {
      error.value = result.message || 'No se pudo reasignar. Vuelve a intentar con esta misma revisión.';
      if (result.status && result.status < 500) impact.value = null;
      return;
    }
    impact.value = null;
    targetProjectId.value = '';
    notify.success({ title: 'Propuesta reasignada; sus archivos y fases se conservaron.' });
  } catch (exception) { error.value = exception.message; impact.value = null; }
  finally { busy.value = false; }
}
</script>
