<script setup>
import { computed, ref, watch } from 'vue'
import BaseRowLink from '~/components/base/BaseRowLink.vue'
import { useRowNavigation } from '~/composables/useRowNavigation'
import { usePlatformBillingStore } from '~/stores/platform-billing'
import { usePlatformProjectsStore } from '~/stores/platform-projects'

const props = defineProps({ projectId: { type: [String, Number], default: null } })
const route = useRoute()
const localePath = useLocalePath()
const { t, locale } = useI18n()
const { openRow } = useRowNavigation()
const store = usePlatformBillingStore()
const projects = usePlatformProjectsStore()
const nature = ref('')
const status = ref('')
const selectedProject = ref('')
const contractId = ref('')
const amendmentId = ref('')
const hostingId = ref('')
const activeProject = computed(() => props.projectId || selectedProject.value)
const contracts = computed(() => store.options?.contracts || [])
const amendments = computed(() => contracts.value.find(row => String(row.id) === String(contractId.value))?.amendments || [])
const href = row => localePath(`/platform/collection-accounts/${row.id}`)
const money = row => new Intl.NumberFormat(locale.value, { style: 'currency', currency: row.currency || 'COP' }).format(Number(row.total))
const contextLabel = row => !row.project_id ? t('platformBilling.nonProjectAccount') : row.context?.nature === 'hosting' ? t('platformBilling.hosting') : row.context?.contract?.title || t('platformBilling.pendingAssociation')
const groups = computed(() => {
  const values = new Map()
  for (const row of store.accounts) {
    const label = `${row.project_name || t('platformBilling.noProject')} · ${contextLabel(row)}${row.context?.amendment ? ` · ${row.context.amendment.title}` : ''}`
    const key = [row.project_id, row.context?.nature, row.context?.contract?.id, row.context?.amendment?.id, row.context?.hosting_id].join(':')
    if (!values.has(key)) values.set(key, { key, label, rows: [] })
    values.get(key).rows.push(row)
  }
  return [...values.values()]
})
function hydrateFilters() {
  selectedProject.value = props.projectId ? '' : String(route.query.project_id || '')
  nature.value = String(route.query.nature || '')
  status.value = String(route.query.commercial_status || '')
  contractId.value = String(route.query.contract_id || '')
  amendmentId.value = String(route.query.amendment_id || '')
  hostingId.value = String(route.query.hosting_id || '')
}
function resetContextFilters() { contractId.value = ''; amendmentId.value = ''; hostingId.value = '' }
async function load() {
  await store.fetchAccounts({
    project_id: activeProject.value || undefined, nature: nature.value || undefined,
    contract_id: contractId.value || undefined,
    amendment_id: amendmentId.value || undefined,
    commercial_status: status.value || undefined,
    hosting_id: hostingId.value || undefined,
  })
}
watch([() => props.projectId, () => route.query], hydrateFilters, { immediate: true })
watch(activeProject, id => {
  if (id) store.fetchOptions(id)
  else store.clear('options')
}, { immediate: true })
watch([activeProject, nature, status, contractId, amendmentId, hostingId], load, { immediate: true })
if (!props.projectId) projects.fetchProjects()
</script>

<template>
  <section class="space-y-5" data-testid="billing-account-list">
    <h1 class="text-2xl font-semibold text-text-default">{{ t('platformBilling.accounts') }}</h1>
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <label v-if="!projectId" class="text-sm text-text-default">{{ t('platformBilling.project') }}
        <select v-model="selectedProject" class="mt-1 w-full rounded-xl border border-border-default bg-surface p-2" @change="resetContextFilters">
          <option value="">{{ t('platformBilling.all') }}</option>
          <option v-for="project in projects.projects" :key="project.id" :value="String(project.id)">{{ project.name }}</option>
        </select>
      </label>
      <label class="text-sm text-text-default">{{ t('platformBilling.nature') }}
        <select v-model="nature" class="mt-1 w-full rounded-xl border border-border-default bg-surface p-2" @change="resetContextFilters">
          <option value="">{{ t('platformBilling.all') }}</option>
          <option value="contract">{{ t('platformBilling.contract') }}</option>
          <option value="hosting">{{ t('platformBilling.hosting') }}</option>
          <option value="pending">{{ t('platformBilling.pendingAssociation') }}</option>
        </select>
      </label>
      <label v-if="activeProject" class="text-sm text-text-default">{{ t('platformBilling.contract') }}
        <select v-model="contractId" class="mt-1 w-full rounded-xl border border-border-default bg-surface p-2" @change="amendmentId = ''; hostingId = ''">
          <option value="">{{ t('platformBilling.all') }}</option>
          <option v-for="contract in contracts" :key="contract.id" :value="String(contract.id)">{{ contract.title }}</option>
        </select>
      </label>
      <label v-if="contractId" class="text-sm text-text-default">{{ t('platformBilling.amendment') }}
        <select v-model="amendmentId" class="mt-1 w-full rounded-xl border border-border-default bg-surface p-2">
          <option value="">{{ t('platformBilling.all') }}</option>
          <option v-for="amendment in amendments" :key="amendment.id" :value="String(amendment.id)">{{ amendment.title }}</option>
        </select>
      </label>
      <label class="text-sm text-text-default">{{ t('platformBilling.state') }}
        <select v-model="status" class="mt-1 w-full rounded-xl border border-border-default bg-surface p-2">
          <option value="">{{ t('platformBilling.all') }}</option>
          <option v-for="value in ['issued', 'paid', 'cancelled']" :key="value" :value="value">{{ t(`platformBilling.states.${value}`) }}</option>
        </select>
      </label>
    </div>
    <p v-if="store.loading.accounts" role="status" class="text-text-muted">{{ t('platformBilling.loading') }}</p>
    <div v-else-if="store.errors.accounts" role="alert" class="rounded-xl border border-border-default p-4 text-text-default">
      <p>{{ store.errors.accounts }}</p>
      <button class="mt-2 font-medium text-text-brand" @click="load">{{ t('platformBilling.retry') }}</button>
    </div>
    <p v-else-if="!store.accounts.length" class="text-text-muted" data-testid="billing-accounts-empty">{{ t('platformBilling.noAccounts') }}</p>
    <div v-else class="space-y-6">
      <section v-for="group in groups" :key="group.key" class="space-y-2">
        <h2 class="text-sm font-semibold text-text-default">{{ group.label }}</h2>
        <ul class="space-y-2">
          <li v-for="row in group.rows" :key="row.id" class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-default bg-surface p-4" @click="openRow(href(row), $event)" @auxclick.middle="openRow(href(row), $event)">
            <div class="relative min-w-0">
              <BaseRowLink :to="href(row)" stretch>{{ row.public_number || row.title }}</BaseRowLink>
              <p class="text-sm text-text-muted">{{ row.title }}</p>
            </div>
            <div class="text-right text-sm text-text-default">
              <p class="font-semibold">{{ money(row) }}</p>
              <p>{{ t(`platformBilling.states.${row.commercial_status}`) }}<span v-if="row.is_overdue"> · {{ t('platformBilling.states.overdue') }}</span></p>
              <p v-if="row.due_date" class="text-text-muted">{{ t('platformBilling.due') }}: {{ row.due_date }}</p>
            </div>
          </li>
        </ul>
      </section>
    </div>
  </section>
</template>
