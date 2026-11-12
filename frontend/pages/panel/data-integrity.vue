<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useDataIntegrityStore } from '~/stores/data_integrity'
import { integrityDestination, integrityParams } from '~/utils/integrityInputs'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })
const { t } = useI18n()
const localePath = useLocalePath()
const route = useRoute(), router = useRouter()
const focused = ref(typeof route.query.finding === 'string' ? route.query.finding : '')
const store = useDataIntegrityStore()
const tab = ref('findings'), busy = ref(false), error = ref(''), notice = ref('')
const scopeKind = ref('all'), scopeId = ref(''), domain = ref(''), severity = ref(''), state = ref(focused.value ? 'all' : 'pending')
const selected = ref([]), choices = reactive({}), params = reactive({}), folders = ref([])
const pending = ref(null), preview = ref(null), reason = ref(''), activeScan = ref(null)
let timer, disposed = false
const key = () => crypto.randomUUID()
const scopeKinds = ['all', 'client', 'project', 'proposal', 'document', 'thread', 'income', 'expense', 'hosting', 'pocket_movement']
const domains = ['clients', 'projects', 'documents', 'communications', 'accounting', 'proposals', 'naming']
const options = (items, group) => items.map((value) => ({ value, label: t(`integrity.${group}.${value}`) }))
const tabs = computed(() => ['findings', 'history'].map((id) => ({ id, label: t(`integrity.${id}`) })))
const scope = () => ({ kind: scopeKind.value, ...(scopeKind.value !== 'all' ? { id: Number(scopeId.value) } : {}) })
const latest = computed(() => store.scans[0])
const lastCompleted = computed(() => store.lastCompletedScan || store.scans.find((scan) => scan.status === 'completed'))
const blockers = computed(() => [...(preview.value?.blockers || []), ...(preview.value?.steps || []).flatMap((step) => step.blockers || [])])
const date = (value) => value ? new Date(value).toLocaleString() : t('integrity.never')
async function run(action) {
  busy.value = true; error.value = ''; notice.value = ''
  try { await action() }
  catch (failure) { error.value = typeof failure.response?.data?.detail === 'string' ? failure.response.data.detail : t('integrity.error') }
  finally { busy.value = false }
}
async function reload(page = 1) {
  selected.value = []
  await store.loadFindings({ status: state.value, page, ...(domain.value ? { domains: domain.value } : {}), ...(severity.value ? { severity: severity.value } : {}), ...(activeScan.value ? { scan_id: activeScan.value } : {}), ...(focused.value ? { fingerprint: focused.value } : {}) })
  await Promise.all([store.loadScans(), store.loadHistory()])
}
function filter() { return run(() => reload()) }
async function poll(id) {
  const scan = await store.getScan(id)
  if (disposed) return
  if (['queued', 'running'].includes(scan.status)) timer = setTimeout(() => run(() => poll(id)), 2500)
  else {
    if (scan.status === 'failed') activeScan.value = null
    await reload()
    if (scan.status === 'failed') error.value = t('integrity.scanFailed')
  }
}
function scan() {
  return run(async () => {
    clearTimeout(timer)
    const result = await store.startScan({ scope: scope(), request_id: key(), ...(domain.value ? { domains: [domain.value] } : {}), ...(severity.value ? { severity: [severity.value] } : {}) })
    activeScan.value = result.id
    await store.loadScans()
    await poll(result.id)
  })
}
function allResults() { activeScan.value = null; focused.value = ''; router.replace({ query: {} }); return filter() }
function fields(row) { return Object.entries(row.inputs || {}) }
function inputOptions(row, name, field) {
  if (name === 'folder_id') return folders.value.filter((folder) => !folder.is_system_managed && !folder.is_archived).map((folder) => ({ value: folder.id, label: `${folder.name} · ${folder.id}` }))
  return field.options
}
function values(row) { return params[row.fingerprint] || (params[row.fingerprint] = { ...row.suggestion }) }
function prepareFixes() {
  return run(async () => {
    const fixes = store.findings.results.filter((row) => selected.value.includes(row.fingerprint)).map((row) => ({
      fingerprint: row.fingerprint, rule_id: row.rule_id, fix_kind: choices[row.fingerprint] || row.fixable_kinds[0], params: integrityParams(row.inputs, values(row)),
    }))
    const batch = { scope: scope(), fixes }
    preview.value = await store.preview(batch)
    pending.value = { action: 'apply', batch, request_id: key() }; reason.value = ''
  })
}
function review(row) {
  preview.value = null
  pending.value = { action: 'review', title: row.title, fingerprint: row.fingerprint, reviewAction: row.is_accepted ? 'reopen' : 'accept', request_id: key() }
  reason.value = ''
}
function prepareUndo(operation) {
  return run(async () => {
    preview.value = await store.undoPreview(operation.operation_id)
    pending.value = { action: 'undo', id: operation.operation_id, request_id: key() }; reason.value = ''
  })
}
async function confirm() {
  return run(async () => {
    const intent = pending.value
    const data = { reason: reason.value.trim(), request_id: intent.request_id }
    if (intent.action === 'review') await store.review({ ...data, fingerprint: intent.fingerprint, action: intent.reviewAction })
    else {
      data.expected_impact_hash = preview.value.impact_hash
      if (intent.action === 'apply') await store.apply({ ...intent.batch, ...data })
      else await store.undo(intent.id, data)
    }
    pending.value = null; preview.value = null
    await reload(); notice.value = t('integrity.saved')
  })
}
onMounted(() => run(async () => {
  await reload(); folders.value = await store.folders()
  const running = store.scans.find((scan) => ['queued', 'running'].includes(scan.status))
  if (running) await poll(running.id)
}))
onBeforeUnmount(() => { disposed = true; clearTimeout(timer) })
</script>

<template>
  <BasePageShell data-testid="data-integrity-page">
    <header class="mb-6 space-y-2">
      <h1 class="text-2xl font-semibold text-text-default">{{ t('integrity.title') }}</h1>
      <p class="text-sm text-text-muted">{{ t('integrity.hint') }}</p>
      <p class="text-sm text-text-subtle">{{ t('integrity.lastReview') }}: {{ date(lastCompleted?.finished_at) }}</p>
      <p v-if="latest?.coverage?.evaluated_rules" class="text-sm text-text-subtle">{{ t('integrity.coverage', { evaluated: latest.coverage.evaluated_rules.length, skipped: latest.coverage.skipped_rules?.length || 0 }) }}</p>
      <p v-if="latest" class="text-sm text-text-subtle" aria-live="polite">{{ t('integrity.latest') }}: {{ t(`integrity.scanStatus.${latest.status}`) }}</p>
    </header>
    <BaseAlert v-if="error && !pending" variant="danger" role="alert">{{ error }}</BaseAlert>
    <BaseAlert v-if="notice" variant="success" role="status">{{ notice }}</BaseAlert>
    <BaseResponsiveTabs v-model="tab" :tabs="tabs" :aria-label="t('integrity.title')" />
    <section v-if="tab === 'findings'" class="mt-4 space-y-4">
      <form class="grid min-w-0 gap-3 panel-portrait:grid-cols-2" @submit.prevent="scan">
        <BaseFormField :label="t('integrity.scope')" for="integrity-scope"><BaseSelect id="integrity-scope" v-model="scopeKind" :options="options(scopeKinds, 'scopes')" /></BaseFormField>
        <BaseFormField v-if="scopeKind !== 'all'" :label="t('integrity.recordId')" for="integrity-record"><BaseInput id="integrity-record" v-model="scopeId" type="number" min="1" required /></BaseFormField>
        <BaseButton type="submit" :loading="busy" data-testid="integrity-scan">{{ t('integrity.scan') }}</BaseButton>
      </form>
      <form class="grid min-w-0 gap-3 panel-portrait:grid-cols-3" @submit.prevent="filter">
        <BaseFormField :label="t('integrity.domain')" for="integrity-domain"><BaseSelect id="integrity-domain" v-model="domain" :options="[{ value: '', label: t('integrity.any') }, ...options(domains, 'domains')]" /></BaseFormField>
        <BaseFormField :label="t('integrity.severity')" for="integrity-severity"><BaseSelect id="integrity-severity" v-model="severity" :options="[{ value: '', label: t('integrity.any') }, ...options(['high', 'medium', 'low'], 'severities')]" /></BaseFormField>
        <BaseFormField :label="t('integrity.status')" for="integrity-status"><BaseSelect id="integrity-status" v-model="state" :options="options(['pending', 'accepted', 'resolved', 'all'], 'statuses')" /></BaseFormField>
        <BaseButton type="submit" :loading="busy" variant="secondary">{{ t('integrity.filter') }}</BaseButton>
        <BaseButton v-if="activeScan || focused" variant="ghost" @click="allResults">{{ t('integrity.allResults') }}</BaseButton>
      </form>
      <p v-if="!store.findings.count" class="py-4 text-text-muted" data-testid="integrity-empty">{{ t('integrity.empty') }}</p>
      <article v-for="row in store.findings.results" :key="row.fingerprint" class="min-w-0 space-y-3 rounded-xl border border-border-muted bg-surface p-4" :data-testid="`integrity-finding-${row.rule_id}`">
        <h2 class="break-words font-semibold text-text-default">{{ row.title }}</h2>
        <p class="text-xs text-text-muted">{{ t(`integrity.domains.${row.domain}`) }} · {{ t(`integrity.severities.${row.severity}`) }}</p>
        <p class="break-words text-sm text-text-default">{{ row.message }}</p>
        <p class="text-sm text-text-muted">{{ row.resolution?.reason }}</p>
        <ul class="space-y-1">
          <li v-for="subject in row.subjects" :key="`${subject.model}:${subject.id}`" class="break-words text-sm">
            <BaseRowLink v-if="integrityDestination(subject)" :to="localePath(integrityDestination(subject))">{{ subject.label }}</BaseRowLink>
            <span v-else class="text-text-muted">{{ subject.label }}</span>
          </li>
        </ul>
        <template v-if="row.fixable_kinds?.length && row.is_present">
          <BaseCheckbox v-model="selected" :value="row.fingerprint">{{ t('integrity.select') }}</BaseCheckbox>
          <div v-if="selected.includes(row.fingerprint)" class="grid min-w-0 gap-3 panel-portrait:grid-cols-2">
            <BaseFormField :label="t('integrity.correction')" :for="`fix-${row.id}`"><BaseSelect :id="`fix-${row.id}`" :model-value="choices[row.fingerprint] || row.fixable_kinds[0]" :options="options(row.fixable_kinds, 'kinds')" @update:model-value="choices[row.fingerprint] = $event" /></BaseFormField>
            <BaseFormField v-for="[name, field] in fields(row)" :key="name" :label="name === 'folder_id' ? t('integrity.folder') : field.label" :for="`param-${row.id}-${name}`">
              <BaseSelect v-if="inputOptions(row, name, field)" :id="`param-${row.id}-${name}`" :model-value="values(row)[name] ?? ''" :options="inputOptions(row, name, field)" :placeholder="t('integrity.choose')" @update:model-value="values(row)[name] = $event" />
              <BaseInput v-else :id="`param-${row.id}-${name}`" :model-value="values(row)[name] ?? ''" @update:model-value="values(row)[name] = $event" />
            </BaseFormField>
          </div>
        </template>
        <BaseButton v-if="row.is_present" size="sm" variant="ghost" @click="review(row)">{{ t(row.is_accepted ? 'integrity.reopen' : 'integrity.accept') }}</BaseButton>
      </article>
      <BaseButton v-if="selected.length" :loading="busy" data-testid="integrity-preview" @click="prepareFixes">{{ t('integrity.preview') }} ({{ selected.length }}/20)</BaseButton>
      <div v-if="store.findings.pages > 1" class="flex flex-wrap gap-2">
        <BaseButton v-if="store.findings.page > 1" variant="secondary" @click="run(() => reload(store.findings.page - 1))">{{ t('integrity.previous') }}</BaseButton>
        <BaseButton v-if="store.findings.page < store.findings.pages" variant="secondary" @click="run(() => reload(store.findings.page + 1))">{{ t('integrity.next') }}</BaseButton>
      </div>
    </section>
    <section v-else class="mt-4 space-y-4" data-testid="integrity-history">
      <article v-for="operation in store.operations.results" :key="operation.operation_id" class="space-y-2 rounded-xl border border-border-muted bg-surface p-4">
        <h2 class="font-medium text-text-default">{{ t(operation.kind === 'undo' ? 'integrity.undo' : 'integrity.correction') }} #{{ operation.operation_id }}</h2>
        <p class="break-words text-sm text-text-muted">{{ operation.reason }} · {{ operation.actor }} · {{ date(operation.created_at) }}</p>
        <BaseButton v-if="operation.kind === 'apply' && !operation.reverted_by" size="sm" variant="secondary" @click="prepareUndo(operation)">{{ t('integrity.undoPreview') }}</BaseButton>
      </article>
      <div v-if="store.operations.pages > 1" class="flex flex-wrap gap-2">
        <BaseButton v-if="store.operations.page > 1" variant="secondary" @click="run(() => store.loadHistory(store.operations.page - 1))">{{ t('integrity.previous') }}</BaseButton>
        <BaseButton v-if="store.operations.page < store.operations.pages" variant="secondary" @click="run(() => store.loadHistory(store.operations.page + 1))">{{ t('integrity.next') }}</BaseButton>
      </div>
      <h2 class="font-semibold text-text-default">{{ t('integrity.reviews') }}</h2>
      <p v-for="reviewRow in store.reviews" :key="reviewRow.id" class="break-words text-sm text-text-muted">{{ t(reviewRow.action === 'accept' ? 'integrity.accept' : 'integrity.reopen') }} · {{ reviewRow.reason }} · {{ reviewRow.actor }} · {{ date(reviewRow.created_at) }}</p>
    </section>
    <BaseModal :model-value="Boolean(pending)" kind="form" @update:model-value="!busy && (pending = null)">
      <div class="min-w-0 space-y-4 p-5" data-testid="integrity-confirm-modal">
        <h2 class="text-lg font-semibold text-text-default">{{ t('integrity.confirmTitle') }}</h2>
        <p v-if="pending?.title" class="break-words text-sm text-text-default">{{ pending.title }}</p>
        <p v-for="(item, index) in blockers" :key="index" class="text-sm text-danger-strong">{{ item.message }}</p>
        <div v-for="step in preview?.steps || []" :key="step.fingerprint || step.rule_id" class="space-y-2">
          <p v-for="(change, index) in step.changes || []" :key="index" class="break-words text-sm text-text-default">{{ change.label }}: {{ change.before }} → {{ change.after }}</p>
          <p v-for="subject in step.subjects || []" :key="`${subject.model}:${subject.id}`" class="break-words text-sm text-text-muted">{{ subject.label }}</p>
        </div>
        <BaseFormField :label="t('integrity.reason')" for="integrity-reason"><BaseTextarea id="integrity-reason" v-model="reason" maxlength="2000" /></BaseFormField>
        <BaseAlert v-if="error" variant="danger" role="alert">{{ error }}</BaseAlert>
      </div>
      <BaseModalActions>
        <BaseButton variant="secondary" :loading="busy" @click="pending = null">{{ t('integrity.cancel') }}</BaseButton>
        <BaseButton v-if="reason.trim() && !preview?.blocked" :loading="busy" data-testid="integrity-confirm" @click="confirm">{{ t('integrity.confirm') }}</BaseButton>
      </BaseModalActions>
    </BaseModal>
  </BasePageShell>
</template>
