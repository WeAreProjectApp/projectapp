import { newRequestId } from '~/services/projectCollaborationRequests'

// Drafts stay in the originating browser tab. URLs carry only an opaque ID.
const prefix = 'projectapp:billing-return:'
const allowedOrigin = path => /^\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?panel\/accounting\/(?:incomes|collections|hostings)$/.test(path || '')
const validId = id => typeof id === 'string' && /^[a-zA-Z0-9-]{1,80}$/.test(id)

export function saveBillingReturnDraft(actorId, draft) {
  if (!actorId || !allowedOrigin(draft.origin?.path)) throw new Error('Invalid draft owner or origin')
  const id = newRequestId()
  sessionStorage.setItem(`${prefix}${id}`, JSON.stringify({ ...draft, actorId, schema: 1 }))
  return id
}

export function readBillingReturnDraft(id, actorId) {
  if (!validId(id) || !actorId) return null
  try {
    const draft = JSON.parse(sessionStorage.getItem(`${prefix}${id}`))
    if (draft?.schema !== 1 || String(draft.actorId) !== String(actorId) || !allowedOrigin(draft.origin?.path)) return null
    if (!['income-account', 'hosting-emission'].includes(draft.kind) || !draft.projectId || !draft.payload) return null
    return draft
  } catch { return null }
}

export function removeBillingReturnDraft(id) {
  if (!validId(id)) return
  try { sessionStorage.removeItem(`${prefix}${id}`) } catch { /* Storage may be disabled after returning. */ }
}
