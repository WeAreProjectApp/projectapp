<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { useLocalePath } from '#imports';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
import ClientFormFields from '~/components/clients/ClientFormFields.vue';
import { emptyClientForm, clientFormPayload } from '~/utils/billingCode';
import { useProposalStore } from '~/stores/proposals';
import { useProjectStateStore } from '~/stores/project_states';
import { get_request } from '~/stores/services/request_http';
import es from '~/locales/proposalApproval/es';
import en from '~/locales/proposalApproval/en';

const props = defineProps({ visible: Boolean, proposal: { type: Object, default: () => ({}) }, acceptProposal: { type: Boolean, default: true } });
const localePath = useLocalePath();
const emit = defineEmits(['close', 'completed']);
const { locale } = useI18n();
const text = computed(() => locale.value.startsWith('en') ? en : es);
const store = useProposalStore();
const states = useProjectStateStore();
const preview = ref(null);
const loading = ref(false);
const saving = ref(false);
const error = ref('');
const errors = ref({});
const clientId = ref(null);
const clientLabel = ref('');
const createClient = ref(false);
const client = ref(emptyClientForm());
const projectId = ref('');
const createProject = ref(true);
const project = ref({ name: '', description: '', state_id: '' });
const projects = ref([]);
const projectReadError = ref(false);
const useContracts = ref(true);
const documents = ref([]);
const optionalIds = ref([]);
const requestId = ref('');
const errorElement = ref(null);
let generation = 0;
const linked = computed(() => !!preview.value?.linked_project);
const confirmed = computed(() => !!preview.value?.confirmed);
const projectOptions = computed(() => !clientId.value ? [] : projects.value.filter((row) => Number(row.client?.profile_id) === Number(clientId.value)).map((row) => ({ value: row.id, label: row.name })));
const stateOptions = computed(() => states.activeStates.map((row) => ({ value: row.id, label: row.name })));
const typeOptions = computed(() => [ ['contract',text.value.contract],['legal_annex',text.value.annex],['amendment',text.value.amendment],['other',text.value.other] ].map(([value,label]) => ({value,label})));
const clientErrors = computed(() => errors.value.new_client || {});
function customError(index) {
  const details = errors.value.custom_documents?.[index];
  if (typeof details === 'string') return details;
  if (details && typeof details === 'object') return Object.values(details).flat().filter(item => typeof item === 'string').join(' ');
  return '';
}
const summary = computed(() => preview.value?.commercial_summary || {});
const formatAmount = (amount) => Number(amount || 0).toLocaleString(locale.value);
const formatPayment = (item) => [item.label, item.description].filter(Boolean).join(' · ');
const formatHosting = (item) => [item.label, `${formatAmount(item.billing_amount)} ${item.currency || summary.value.currency || ''}`, item.months ? `${item.months} ${text.value.months}` : '', item.discount_percent ? `${item.discount_percent}% ${text.value.discount}` : '', item.effective_monthly != null ? `${formatAmount(item.effective_monthly)} ${text.value.monthly}` : ''].filter(Boolean).join(' · ');
const messageFor = (value) => Array.isArray(value) ? value.join(' ') : typeof value === 'string' ? value : '';
const fieldError = (field) => messageFor(errors.value[field]);
function newRequestId() { return globalThis.crypto.randomUUID(); }
function selectClient(selected) {
  clientId.value = selected?.id ?? null;
  clientLabel.value = selected?.name || '';
  createClient.value = false;
  projectId.value = '';
}
function stageClient(name = '') {
  createClient.value = true;
  client.value = { ...emptyClientForm(), name };
  clientId.value = null;
  projectId.value = '';
  createProject.value = true;
}
function toggleClient() { if (createClient.value) { createClient.value = false; } else stageClient(); }
function addFiles(event) {
  for (const file of Array.from(event.target.files || [])) {
    const valid = /\.(pdf|doc|docx|xls|xlsx|png|jpg|jpeg)$/i.test(file.name) && file.size <= 15 * 1024 * 1024 && file.size > 0;
    documents.value.push({ file, title: file.name.replace(/\.[^.]+$/, ''), document_type: 'contract', error: valid ? '' : text.value.invalidFile });
  }
  event.target.value = '';
}
async function focusError() { await nextTick(); errorElement.value?.focus(); }
async function load(reset = false) {
  const ticket = ++generation;
  loading.value = true;
  error.value = '';
  const [result, projectResult] = await Promise.all([store.fetchApproval(props.proposal.id), get_request('projects/?scope=all').catch(() => null), states.states.length ? Promise.resolve() : states.fetchCatalog()]);
  if (ticket !== generation || !props.visible) return;
  loading.value = false;
  projects.value = projectResult?.data?.results || [];
  projectReadError.value = !projectResult;
  if (!result.success) { error.value = result.message || text.value.loadError; return; }
  preview.value = result.data;
  requestId.value = newRequestId();
  if (reset) {
    errors.value = {};
    clientId.value = result.data.client?.profile_id ?? null;
    clientLabel.value = result.data.client?.name || '';
    createClient.value = false;
    projectId.value = result.data.linked_project?.id || '';
    createProject.value = !result.data.linked_project;
    project.value = { name: props.proposal.title || result.data.commercial_summary?.title || '', description: '', state_id: states.stateByKey('development')?.id || '' };
    useContracts.value = true;
    optionalIds.value = [];
    documents.value = [];
  }
}
watch(() => [props.visible, props.proposal.id], () => {
  if (props.visible) load(true); else { generation++; preview.value = null; }
}, { immediate: true });
watch(clientId, () => { if (!linked.value) projectId.value = ''; });
async function submit(action) {
  if (saving.value || loading.value) return;
  error.value = ''; errors.value = {};
  if (action === 'confirm') {
    if (!linked.value && (createClient.value ? !client.value.name.trim() : !clientId.value)) errors.value.client_profile_id = text.value.requiredClient;
    if (!linked.value && (createProject.value ? !project.value.name.trim() : !projectId.value)) errors.value.project_id = text.value.requiredProject;
    if (!useContracts.value && (!documents.value.length || documents.value.some((item) => item.error))) errors.value.custom_documents = text.value.requiredFiles;
    if (!useContracts.value && documents.value.some((item) => !item.title.trim())) errors.value.custom_documents = text.value.minTitle;
    if (useContracts.value && !preview.value?.contracts?.available) errors.value.contracts = text.value.unavailable;
    if (Object.keys(errors.value).length) { error.value = text.value.validation; await focusError(); return; }
  }
  const payload = action === 'retry' ? { action, request_id: requestId.value } : { action, accept_proposal: props.acceptProposal };
  if (action === 'confirm') {
    Object.assign(payload, { source_hash: preview.value.source_hash, request_id: requestId.value, use_proposal_contracts: useContracts.value, selected_document_ids: optionalIds.value });
    if (linked.value) { payload.client_profile_id = preview.value.client?.profile_id ?? preview.value.linked_project.client_profile_id; payload.project_id = preview.value.linked_project.id; }
    else if (createClient.value) payload.new_client = clientFormPayload(client.value); else payload.client_profile_id = Number(clientId.value);
    if (!linked.value && createProject.value) payload.new_project = { name: project.value.name.trim(), description: project.value.description, ...(project.value.state_id ? { state_id: Number(project.value.state_id) } : {}) }; else if (!linked.value) payload.project_id = Number(projectId.value);
    if (!useContracts.value) payload.custom_documents = documents.value.map(({title,document_type}) => ({title:title.trim(),document_type}));
  }
  if (action === 'retry') payload.request_id = requestId.value;
  saving.value = true;
  const result = await store.submitApproval(props.proposal.id, payload, action === 'confirm' && !useContracts.value ? documents.value.map((item) => item.file) : []);
  saving.value = false;
  if (result.success) { emit('completed', result.data); emit('close'); return; }
  errors.value = result.errors || {};
  error.value = result.status === 409 ? result.errors?.detail || text.value.stale : result.message || result.errors?.detail || text.value.saveError;
  await focusError();
}
function close() { if (!saving.value) emit('close'); }
</script>

<template>
  <BaseModal :model-value="visible" kind="form-wide" :close-on-esc="!saving" :close-on-backdrop="!saving" @close="close">
    <div class="space-y-5 px-6 py-6" data-testid="proposal-approval-modal">
      <h2 class="break-words text-lg font-bold text-text-default">{{ text.title }}</h2>
      <p v-if="loading" role="status" class="text-text-muted">{{ text.loading }}</p>
      <div v-if="error" ref="errorElement" tabindex="-1" role="alert" data-testid="approval-review-error" class="rounded-lg bg-danger-soft p-3 text-sm text-danger-strong">
        <p>{{ error }}</p>
        <p v-for="(value,key) in errors" :key="key">{{ messageFor(value) }}</p>
        <BaseButton type="button" variant="secondary" size="sm" :disabled="saving" :disabled-reason="text.processing" @click="load(false)">{{ text.reload }}</BaseButton>
      </div>
      <template v-if="preview && !loading">
        <div v-if="linked" class="space-y-2 rounded-lg bg-surface-raised p-4 text-sm text-text-default">
          <p>{{ confirmed ? text.linked : text.limitedRetry }}</p><p class="break-words">{{ text.client }}: {{ preview.client?.name }}</p><p class="break-words">{{ text.project }}: {{ preview.linked_project.name }}</p>
        </div>
        <template v-else>
          <BaseFormField :label="text.client" required :error="fieldError('client_profile_id')">
            <ClientAutocomplete v-if="!createClient" v-model="clientId" :aria-label="text.client" :initial-label="clientLabel" test-id="approval-client" allow-create @select="selectClient" @create-new="stageClient" />
            <BaseButton type="button" variant="link" size="sm" data-testid="approval-toggle-client" @click="toggleClient">{{ createClient ? text.existingClient : text.newClient }}</BaseButton>
            <ClientFormFields v-if="createClient" v-model="client" dense :errors="clientErrors" testid-prefix="approval-new-client" />
          </BaseFormField>
          <BaseFormField :label="text.project" required :error="fieldError('project_id')">
            <div class="flex flex-wrap gap-3 text-sm text-text-default">
              <label><input v-model="createProject" type="radio" :value="true" name="approval-project-mode" /> {{ text.newProject }}</label>
              <label v-if="!createClient"><input v-model="createProject" type="radio" :value="false" name="approval-project-mode" /> {{ text.existingProject }}</label>
            </div>
            <BaseSelect v-if="!createProject" v-model="projectId" :options="projectOptions" :placeholder="text.chooseProject" :aria-label="text.project" data-testid="approval-project" />
            <p v-if="projectReadError" role="status" class="text-sm text-warning-strong">{{ text.projectReadError }}</p>
          </BaseFormField>
          <div v-if="createProject" class="space-y-3 rounded-lg border border-border-default p-4">
            <BaseFormField :label="text.projectName" required :error="messageFor(errors.new_project?.name)"><BaseInput v-model="project.name" data-testid="approval-project-name" :aria-label="text.projectName" /></BaseFormField>
            <BaseFormField :label="text.description" :error="messageFor(errors.new_project?.description)"><BaseTextarea v-model="project.description" :rows="2" :aria-label="text.description" /></BaseFormField>
            <BaseFormField :label="text.state" :error="messageFor(errors.new_project?.state_id)"><BaseSelect v-model="project.state_id" :options="stateOptions" :aria-label="text.state" /></BaseFormField>
          </div>
        </template>
        <section class="space-y-2 rounded-lg bg-surface-raised p-4 text-sm text-text-default">
          <h3 class="font-semibold">{{ text.summary }}</h3>
          <p class="break-words">{{ summary.title }}</p><div><p class="font-medium">{{ text.scope }}</p><ul class="list-disc space-y-1 break-words pl-5"><li v-for="(title,index) in summary.scope || []" :key="index">{{ title }}</li></ul><p v-if="!summary.scope?.length">{{ text.none }}</p></div><p>{{ text.investment }}: {{ Number(summary.total_investment || 0).toLocaleString(locale) }} {{ summary.currency }}</p>
          <div><p class="font-medium">{{ text.payments }}</p><ul><li v-for="(payment,index) in summary.payment_milestones || []" :key="index" class="break-words">{{ formatPayment(payment) }}</li></ul><p v-if="!summary.payment_milestones?.length">{{ text.none }}</p></div><div><p class="font-medium">{{ text.hosting }}</p><ul><li v-for="(tier,index) in summary.hosting_tiers || []" :key="index" class="break-words">{{ formatHosting(tier) }}</li></ul><p v-if="!summary.hosting_tiers?.length">{{ text.none }}</p></div>
          <p class="text-text-muted">{{ text.corrections }}</p><BaseButton as="NuxtLink" :to="localePath(`/panel/proposals/${proposal.id}/edit`)" variant="link" size="sm" :disabled="saving" :disabled-reason="text.processing" @click="close">{{ text.editProposal }}</BaseButton>
        </section>
        <template v-if="!confirmed">
          <div class="space-y-3">
            <button type="button" role="switch" :aria-checked="useContracts" class="flex items-center gap-3 text-left text-sm font-medium text-text-default" data-testid="approval-contract-switch" @click="useContracts = !useContracts">
              <span class="rounded-full px-3 py-1" :class="useContracts ? 'bg-primary text-white' : 'bg-surface-raised text-text-muted'">{{ useContracts ? '✓' : '—' }}</span>{{ text.contracts }}
            </button>
            <p v-if="useContracts" class="text-sm text-text-muted">{{ preview.contracts?.modality === 'split' ? text.split : text.combined }}</p>
            <p v-if="useContracts && !preview.contracts?.available" role="status" class="text-sm text-warning-strong">{{ preview.contracts?.error || text.unavailable }}</p>
            <div v-if="!useContracts" class="space-y-3">
              <p class="text-sm text-text-muted">{{ text.customHint }}</p>
              <BaseFormField :label="text.custom" :error="fieldError('custom_documents')"><input type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg" :aria-label="text.custom" data-testid="approval-custom-files" class="block w-full min-w-0 text-sm text-text-default" @change="addFiles" /></BaseFormField>
              <div v-for="(item,index) in documents" :key="index" class="space-y-2 rounded-lg border border-border-default p-3" data-testid="approval-custom-document">
                <p class="break-all text-sm text-text-default">{{ item.file.name }} · {{ (item.file.size / 1024).toFixed(1) }} KB</p>
                <BaseInput v-model="item.title" :aria-label="text.documentTitle" />
                <BaseSelect v-model="item.document_type" :options="typeOptions" :aria-label="text.documentType" />
                <p v-if="item.error || customError(index)" role="alert" class="text-sm text-danger-strong">{{ item.error || customError(index) }}</p>
                <BaseButton type="button" variant="secondary" size="sm" :aria-label="`${text.remove} ${item.file.name}`" @click="documents.splice(index,1)">{{ text.remove }}</BaseButton>
              </div>
            </div>
            <fieldset v-if="preview.optional_documents?.length" class="space-y-2 text-sm text-text-default"><legend class="font-medium">{{ text.optional }}</legend><label v-for="document in preview.optional_documents" :key="document.id" class="flex items-start gap-2 break-words"><input v-model="optionalIds" type="checkbox" :value="document.id" />{{ document.title }}</label></fieldset>
          </div>
        </template>
        <section class="space-y-2 text-sm text-text-default" data-testid="approval-packet-preview">
          <h3 class="font-semibold">{{ text.packet }}</h3><p>{{ text.always }}</p>
          <ul v-if="!confirmed" class="list-disc space-y-1 break-words pl-5"><li>{{ text.commercial }}</li><li>{{ text.technical }}</li><li v-for="document in useContracts ? preview.contracts?.documents || [] : documents" :key="document.id || document.file.name">{{ document.title }}</li><li v-for="document in preview.optional_documents?.filter(item => optionalIds.includes(item.id)) || []" :key="document.id">{{ document.title }}</li></ul>
          <template v-else><p>{{ text.limitedRetry }}</p><ul class="space-y-2"><li v-for="file in preview.confirmed_files" :key="file.id"><p class="break-all">{{ file.title }} · {{ file.filename }} · {{ (file.size / 1024).toFixed(1) }} KB</p><PanelDownloadLink :url="file.download_url" :filename="file.filename" :label="text.download" expected-type="" /></li></ul></template>
        </section>
      </template>
    </div>
    <template #footer><BaseModalActions>
      <BaseButton type="button" variant="secondary" :disabled="saving" :disabled-reason="text.processing" @click="close">{{ text.cancel }}</BaseButton>
      <BaseButton v-if="!linked" type="button" variant="secondary" :disabled="saving || loading || !preview" :disabled-reason="saving ? text.processing : loading ? text.loading : text.loadError" data-testid="approval-defer" @click="submit('defer')">{{ acceptProposal ? text.defer : text.later }}</BaseButton>
      <BaseButton v-if="confirmed" type="button" variant="primary" :loading="saving" :disabled="loading || !preview" :disabled-reason="loading ? text.loading : text.loadError" data-testid="approval-retry" @click="submit('retry')">{{ text.retry }}</BaseButton>
      <BaseButton v-else type="button" variant="primary" :loading="saving" :disabled="loading || !preview" :disabled-reason="loading ? text.loading : text.loadError" data-testid="approval-confirm" @click="submit('confirm')">{{ acceptProposal ? text.confirm : text.link }}</BaseButton>
    </BaseModalActions></template>
  </BaseModal>
</template>
