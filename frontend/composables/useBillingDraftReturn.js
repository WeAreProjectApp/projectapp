import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProposalStore } from '~/stores/proposals'
import { get_request } from '~/stores/services/request_http'
import { usePanelNotify } from '~/composables/usePanelNotify'
import { readBillingReturnDraft, removeBillingReturnDraft, saveBillingReturnDraft } from '~/utils/billingReturnDraft'

export function useBillingDraftReturn({ kind, open, record = null }) {
  const route = useRoute(), router = useRouter(), localePath = useLocalePath()
  const { t } = useI18n()
  const auth = useProposalStore(), notify = usePanelNotify()
  const resumeDraft = ref(null)
  let draftId = null
  function clear() {
    removeBillingReturnDraft(draftId)
    draftId = null; resumeDraft.value = null
  }
  async function reconcile(payload) {
    const projectId = payload.selectedIncome?.project || payload.selectedIncome?.project_id || payload.record?.project || payload.record?.project_id
    if (!projectId) return
    try {
      const query = { ...route.query }; delete query.returnDraft
      const next = saveBillingReturnDraft(auth.adminUser?.id, { kind, projectId,
        origin: { path: route.path, query }, payload })
      removeBillingReturnDraft(draftId); draftId = next
      // The browser Back button must recover the same draft as the explicit link.
      await router.replace({ path: route.path, query: { ...query, returnDraft: next } })
      await router.push(localePath({ path: `/panel/accounting/project-hosting/${projectId}`, query: { returnDraft: next } }))
    } catch { notify.error({ title: t('hostingBilling.draftFailed') }) }
  }
  onMounted(async () => {
    const id = route.query.returnDraft
    if (typeof id !== 'string') return
    const draft = readBillingReturnDraft(id, auth.adminUser?.id)
    if (!draft || draft.kind !== kind || draft.origin.path !== route.path) return
    draftId = id
    try {
      const previous = draft.payload.selectedIncome || draft.payload.record
      const entity = kind === 'income-account' ? 'incomes' : 'hostings'
      const result = await get_request(`accounting/${entity}/${previous.id}/`)
      const current = result.data
      if (Number(current.project || current.project_id) !== Number(draft.projectId)
        || Number(current.client) !== Number(previous.client)) throw new Error('Ownership changed')
      resumeDraft.value = { ...draft.payload, ...(kind === 'income-account' ? { selectedIncome: current } : { record: current }) }
      if (record) record.value = current
      open.value = true
      const query = { ...route.query }; delete query.returnDraft
      await router.replace({ path: route.path, query })
    } catch { notify.error({ title: t('hostingBilling.draftMissing') }) }
  })
  return { resumeDraft, reconcile, clear }
}
