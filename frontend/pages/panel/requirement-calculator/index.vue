<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRequirementCalculatorStore } from '~/stores/requirement_calculator';
import DefinitionEditor from '~/components/RequirementCalculator/DefinitionEditor.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });
const { t } = useI18n();
const route = useRoute();
const localePath = useLocalePath();
const store = useRequirementCalculatorStore();
const projectId = computed(() => Number(route.query.project) || null);
const tab = ref('definition');
const definition = ref(null);
const baseline = ref('');
const note = ref('');
const documentId = ref('');
const selectedVersionId = ref(null);
const baseRevisionId = ref(null);
const confirmation = ref('');
const preview = ref('');
const success = ref('');
const historyOffset = ref(0);
const estimateOffset = ref(0);
const actual = ref({ estimate_id: '', actual_hours: '', hourly_cost_cop: '', evidence: '', cause: '' });
const selectedVersion = computed(() => store.projectVersion?.id === Number(selectedVersionId.value) ? store.projectVersion : null);
const readOnly = computed(() => Boolean(projectId.value && selectedVersion.value?.status !== 'draft'));
const dirty = computed(() => definition.value && JSON.stringify(definition.value) !== baseline.value);
const errorText = computed(() => store.error ? JSON.stringify(store.error, null, 2) : '');
const fieldClass = 'w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm text-input-text';

function setDefinition(value) {
  definition.value = value ? JSON.parse(JSON.stringify(value)) : null;
  baseline.value = JSON.stringify(definition.value);
  preview.value = '';
}
async function reload() {
  success.value = '';
  const general = await store.loadGeneral();
  if (!general) return;
  baseRevisionId.value = general.revision_id || null;
  documentId.value = general.document_candidates?.length === 1 ? general.document_candidates[0].id : '';
  if (projectId.value) {
    const project = await store.loadProject(projectId.value);
    if (!project) return;
    selectedVersionId.value = project.versions.find((row) => row.status === 'draft')?.id
      || project.versions.find((row) => row.document_id === project.calculator_document_id)?.id || null;
    await loadSelectedVersion(selectedVersionId.value);
  } else setDefinition(general.definition);
  await store.loadRevisions(historyOffset.value);
}
async function loadSelectedVersion(id) {
  setDefinition(null);
  if (!id) return;
  const version = await store.loadProjectVersion(Number(id));
  if (version && version.id === Number(selectedVersionId.value)) setDefinition(version.definition);
}
watch(projectId, reload);
onMounted(reload);

function payload() {
  const result = JSON.parse(JSON.stringify(definition.value));
  for (const size of result.sizes) if (size.standard_value_cop === '') size.standard_value_cop = null;
  for (const modifier of result.modifiers) {
    if (modifier.minimum === '') modifier.minimum = null;
    if (modifier.maximum === '') modifier.maximum = null;
  }
  if (result.calibration.hourly_cost_cop === '') result.calibration.hourly_cost_cop = null;
  return result;
}
async function save() {
  let result;
  if (projectId.value) {
    result = await store.saveDraft(selectedVersion.value.id, { definition: payload(), note: note.value, if_match: selectedVersion.value.if_match });
  } else {
    result = await store.saveGeneral({ definition: payload(), note: note.value, if_match: store.general.if_match,
      ...(!store.general.initialized && documentId.value ? { document_id: Number(documentId.value) } : {}) });
  }
  confirmation.value = '';
  if (result) {
    await reload();
    note.value = '';
    success.value = t('requirementCalculator.saved');
  }
}
async function createDraft() {
  const result = await store.createDraft(projectId.value, { base_revision_id: Number(baseRevisionId.value), note: note.value, if_match: store.project.if_match });
  if (result) {
    await reload();
    selectedVersionId.value = result.id;
    note.value = '';
    success.value = t('requirementCalculator.draftCreated');
  }
}
async function approve() {
  const result = await store.approveDraft(selectedVersion.value.id, { if_match: selectedVersion.value.if_match, note: note.value });
  confirmation.value = '';
  if (result) {
    await reload();
    selectedVersionId.value = result.id;
    note.value = '';
    success.value = t('requirementCalculator.approvedMessage');
  }
}
async function showPreview() {
  const result = await store.preview(payload());
  if (result) preview.value = result.markdown;
}
async function restoreToEditor(id) {
  const revision = await store.loadRevision(id);
  if (revision) {
    setDefinition(revision.definition);
    note.value = t('requirementCalculator.restoreNote', { id });
    tab.value = 'definition';
  }
}
async function selectTab(value) {
  tab.value = value;
  if (value === 'versions') await store.loadRevisions(historyOffset.value);
  if (value === 'calibration') {
    await store.loadCalibration();
    await store.loadEstimates(estimateOffset.value);
  }
}
async function historyPage(direction) {
  historyOffset.value += direction * 20;
  await store.loadRevisions(historyOffset.value);
}
async function estimatesPage(direction) {
  estimateOffset.value += direction * 20;
  await store.loadEstimates(estimateOffset.value);
}
async function saveActual() {
  const estimate = store.estimates.find((row) => row.id === Number(actual.value.estimate_id));
  const corrected = new Set(estimate?.actuals.map((row) => row.supersedes_id) || []);
  const last = estimate?.actuals.find((row) => !corrected.has(row.id));
  const result = await store.recordActual({ estimate_id: Number(actual.value.estimate_id),
    actual_hours: actual.value.actual_hours, evidence: actual.value.evidence, cause: actual.value.cause,
    ...(actual.value.hourly_cost_cop ? { hourly_cost_cop: actual.value.hourly_cost_cop } : {}),
    ...(last ? { supersedes_id: last.id } : {}) });
  if (result) {
    actual.value = { estimate_id: '', actual_hours: '', hourly_cost_cop: '', evidence: '', cause: '' };
    await selectTab('calibration');
    success.value = t('requirementCalculator.actualSaved');
  }
}
</script>

<template>
  <BasePageShell width="panel">
    <header class="mb-6 space-y-3">
      <h1 class="text-2xl font-light text-text-default">{{ t('requirementCalculator.title') }}</h1>
      <p class="text-sm text-text-muted">{{ projectId ? store.project?.project_name : t('requirementCalculator.intro') }}</p>
      <BaseButton v-if="projectId" variant="link" :to="localePath('/panel/requirement-calculator')">{{ t('requirementCalculator.general') }}</BaseButton>
    </header>
    <p v-if="store.busy" role="status" class="mb-4 text-sm text-text-muted">{{ t('requirementCalculator.loading') }}</p>
    <pre v-if="store.error" role="alert" class="mb-4 whitespace-pre-wrap break-words rounded-xl bg-danger-soft p-4 text-sm text-danger-strong" data-testid="calculator-error">{{ errorText }}</pre>
    <p v-if="success" role="status" class="mb-4 rounded-xl bg-surface-muted p-4 text-sm text-text-default">{{ success }}</p>
    <nav v-if="!projectId" class="mb-6 flex flex-wrap gap-2" :aria-label="t('requirementCalculator.tabs')">
      <BaseButton v-for="value in ['definition', 'versions', 'calibration']" :key="value" :variant="tab === value ? 'primary' : 'secondary'" :aria-current="tab === value ? 'page' : undefined" @click="selectTab(value)">{{ t(`requirementCalculator.${value}`) }}</BaseButton>
    </nav>
    <section v-if="projectId && store.project" class="mb-6 space-y-4 rounded-xl border border-border-default p-4">
      <p class="text-sm text-text-muted">{{ store.project.calculator_document_id ? t('requirementCalculator.assigned') : t('requirementCalculator.unassigned') }}</p>
      <label v-if="store.project.versions.length" class="block text-sm text-text-default">{{ t('requirementCalculator.projectVersion') }}<select v-model="selectedVersionId" :class="fieldClass" data-testid="calculator-project-version" @change="loadSelectedVersion(selectedVersionId)"><option v-for="version in store.project.versions" :key="version.id" :value="version.id">#{{ version.id }} · {{ t(`requirementCalculator.${version.status}`) }} {{ version.document_id === store.project.calculator_document_id ? '✓' : '' }}</option></select></label>
      <BaseButton v-if="selectedVersion" variant="link" :to="localePath(selectedVersion.document_url)">{{ t('requirementCalculator.openDocument') }}</BaseButton>
      <template v-if="!store.project.versions.some((row) => row.status === 'draft') && store.general?.initialized">
        <label class="block text-sm text-text-default">{{ t('requirementCalculator.baseVersion') }}<input v-model="baseRevisionId" type="number" min="1" :class="fieldClass"></label>
        <label class="block text-sm text-text-default">{{ t('requirementCalculator.note') }}<input v-model="note" :class="fieldClass" data-testid="calculator-note"></label>
        <BaseButton :disabled="store.busy || !note.trim() || !baseRevisionId" :disabled-reason="t('requirementCalculator.noteRequired')" @click="createDraft">{{ t('requirementCalculator.createDraft') }}</BaseButton>
      </template>
      <details v-if="selectedVersion?.changes?.length" class="rounded-xl border border-border-default p-3"><summary class="cursor-pointer text-sm font-medium text-text-default">{{ t('requirementCalculator.versions') }}</summary><p v-for="change in selectedVersion.changes" :key="change.id" class="mt-2 text-sm text-text-muted">{{ change.created_at }} · {{ t(`requirementCalculator.${change.status}`) }} · {{ change.note }}</p></details>
      <p v-if="!store.general?.initialized" class="text-sm text-text-muted">{{ t('requirementCalculator.initializeFirst') }}</p>
    </section>
    <section v-if="tab === 'definition' && definition" class="space-y-5">
      <template v-if="readOnly">
        <p class="rounded-xl bg-surface-muted p-4 text-sm text-text-default">{{ t('requirementCalculator.frozen') }}</p>
        <dl class="grid gap-4 sm:grid-cols-2"><div v-for="size in definition.sizes" :key="size.id" class="rounded-xl border border-border-default p-4"><dt class="font-semibold text-text-default">{{ size.id }} · {{ size.label }}</dt><dd class="mt-2 text-sm text-text-muted">{{ size.definition }}</dd></div></dl>
      </template>
      <template v-else>
        <label v-if="!projectId && !store.general?.initialized" class="block text-sm text-text-default">{{ t('requirementCalculator.existingDocument') }}<select v-model="documentId" :class="fieldClass"><option value="">{{ t('requirementCalculator.newDocument') }}</option><option v-for="doc in store.general?.document_candidates || []" :key="doc.id" :value="doc.id">{{ doc.title }}</option></select></label>
        <DefinitionEditor v-model="definition" :parameters-only="Boolean(projectId)" />
        <label class="block text-sm text-text-default">{{ t('requirementCalculator.note') }}<textarea v-model="note" :class="fieldClass" data-testid="calculator-note" /></label>
        <div class="flex flex-wrap gap-3">
          <BaseButton variant="secondary" :disabled="store.busy" :disabled-reason="t('requirementCalculator.loading')" @click="showPreview">{{ t('requirementCalculator.preview') }}</BaseButton>
          <BaseButton :disabled="store.busy || !note.trim()" :disabled-reason="t('requirementCalculator.noteRequired')" data-testid="calculator-save" @click="projectId ? save() : confirmation = 'publish'">{{ t('requirementCalculator.save') }}</BaseButton>
          <BaseButton v-if="projectId" variant="accent" :disabled="store.busy || dirty || !note.trim()" :disabled-reason="dirty ? t('requirementCalculator.saveFirst') : t('requirementCalculator.noteRequired')" data-testid="calculator-approve" @click="confirmation = 'approve'">{{ t('requirementCalculator.approve') }}</BaseButton>
          <BaseButton v-if="!projectId && store.general?.document_url" variant="link" :to="localePath(store.general.document_url)">{{ t('requirementCalculator.openDocument') }}</BaseButton>
        </div>
      </template>
      <pre v-if="preview" class="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-surface-muted p-4 text-sm text-text-default" data-testid="calculator-preview">{{ preview }}</pre>
    </section>
    <section v-if="tab === 'versions' && !projectId" class="space-y-4">
      <article v-for="revision in store.revisions" :key="revision.id" class="space-y-2 rounded-xl border border-border-default p-4">
        <p class="font-semibold text-text-default">#{{ revision.id }} · {{ revision.created_at }}</p><p class="text-sm text-text-muted">{{ revision.note }}</p>
        <BaseButton variant="secondary" @click="restoreToEditor(revision.id)">{{ t('requirementCalculator.restore') }}</BaseButton>
      </article>
      <div class="flex flex-wrap gap-3"><BaseButton variant="secondary" :disabled="historyOffset === 0 || store.busy" :disabled-reason="t('requirementCalculator.firstPage')" @click="historyPage(-1)">{{ t('requirementCalculator.previous') }}</BaseButton><BaseButton variant="secondary" :disabled="historyOffset + 20 >= store.revisionCount || store.busy" :disabled-reason="t('requirementCalculator.lastPage')" @click="historyPage(1)">{{ t('requirementCalculator.next') }}</BaseButton></div>
    </section>
    <section v-if="tab === 'calibration' && !projectId" class="space-y-6">
      <p class="rounded-xl bg-surface-muted p-4 text-sm text-text-muted">{{ t('requirementCalculator.provisional') }}</p>
      <p v-if="store.calibration" class="text-sm text-text-default">{{ t('requirementCalculator.consistency', store.calibration.consistency) }}</p>
      <article v-for="cohort in store.calibration?.cohorts || []" :key="`${cohort.definition_digest}-${cohort.size}`" class="space-y-2 rounded-xl border border-border-default p-4">
        <p class="font-semibold text-text-default">{{ cohort.size }} · {{ t('requirementCalculator.revision') }} #{{ cohort.revision_id }}</p>
        <p class="text-sm text-text-muted">{{ t('requirementCalculator.measurement', { samples: cohort.samples, minimum: cohort.minimum_samples, hours: cohort.median_hours, deviation: cohort.deviation_percent }) }}</p>
        <p class="text-sm text-text-default">{{ t(`requirementCalculator.${cohort.status}`) }}</p>
        <p v-if="cohort.median_cost_cop" class="text-sm text-text-muted">{{ t('requirementCalculator.costMeasurement', { cost: cohort.median_cost_cop, value: cohort.standard_value_cop || '—', samples: cohort.cost_samples }) }}</p>
        <p v-if="cohort.covers_median_cost === false" class="text-sm text-danger-strong">{{ t('requirementCalculator.underCost') }}</p>
        <p v-if="cohort.propose_review" class="text-sm font-semibold text-danger-strong">{{ t('requirementCalculator.reviewSuggested') }}</p>
      </article>
      <div v-if="!store.calibration?.cohorts.length" class="text-sm text-text-muted">{{ t('requirementCalculator.noActuals') }}</div>
      <h2 class="text-lg font-semibold text-text-default">{{ t('requirementCalculator.estimates') }}</h2>
      <article v-for="estimate in store.estimates" :key="estimate.id" class="space-y-2 rounded-xl border border-border-default p-4"><p class="font-medium text-text-default">#{{ estimate.id }} · {{ estimate.size }} · {{ estimate.project_name }}</p><p class="whitespace-pre-wrap text-sm text-text-muted">{{ estimate.requirement }}</p><p class="text-sm text-text-default">{{ estimate.explanation }}</p><p v-for="event in estimate.actuals" :key="event.id" class="text-sm text-text-muted">#{{ event.id }} · {{ t('requirementCalculator.actual_hours') }}: {{ event.actual_hours }} · {{ event.evidence }} · {{ event.cause }}</p></article>
      <div class="flex flex-wrap gap-3"><BaseButton variant="secondary" :disabled="estimateOffset === 0 || store.busy" :disabled-reason="t('requirementCalculator.firstPage')" @click="estimatesPage(-1)">{{ t('requirementCalculator.previous') }}</BaseButton><BaseButton variant="secondary" :disabled="estimateOffset + 20 >= store.estimateCount || store.busy" :disabled-reason="t('requirementCalculator.lastPage')" @click="estimatesPage(1)">{{ t('requirementCalculator.next') }}</BaseButton></div>
      <form class="space-y-4 rounded-xl border border-border-default p-4" @submit.prevent="saveActual">
        <h2 class="font-semibold text-text-default">{{ t('requirementCalculator.recordActual') }}</h2>
        <label class="block text-sm text-text-default">{{ t('requirementCalculator.estimate') }}<select v-model="actual.estimate_id" data-testid="calculator-actual-estimate_id" required :class="fieldClass"><option value="">{{ t('requirementCalculator.choose') }}</option><option v-for="estimate in store.estimates" :key="estimate.id" :value="estimate.id">#{{ estimate.id }} · {{ estimate.size }}</option></select></label>
        <div class="grid gap-3 sm:grid-cols-2"><label v-for="field in ['actual_hours', 'hourly_cost_cop']" :key="field" class="block text-sm text-text-default">{{ t(`requirementCalculator.${field}`) }}<input v-model="actual[field]" :data-testid="`calculator-actual-${field}`" type="number" min="0.01" step="0.01" :required="field === 'actual_hours'" :class="fieldClass"></label></div>
        <label v-for="field in ['evidence', 'cause']" :key="field" class="block text-sm text-text-default">{{ t(`requirementCalculator.${field}`) }}<textarea v-model="actual[field]" :data-testid="`calculator-actual-${field}`" required :class="fieldClass" /></label>
        <p class="text-sm text-text-muted">{{ t('requirementCalculator.correctionHint') }}</p>
        <BaseButton data-testid="calculator-actual-submit" type="submit" :disabled="store.busy" :disabled-reason="t('requirementCalculator.loading')">{{ t('requirementCalculator.recordActual') }}</BaseButton>
      </form>
    </section>
    <ConfirmModal :model-value="Boolean(confirmation)" :title="t(confirmation === 'approve' ? 'requirementCalculator.approve' : 'requirementCalculator.save')" :message="t(confirmation === 'approve' ? 'requirementCalculator.approveConfirm' : 'requirementCalculator.publishConfirm')" :loading="store.busy" @confirm="confirmation === 'approve' ? approve() : save()" @cancel="confirmation = ''" />
  </BasePageShell>
</template>
