import {
  readBillingReturnDraft,
  removeBillingReturnDraft,
  saveBillingReturnDraft,
} from '../../utils/billingReturnDraft'

const prefix = 'projectapp:billing-return:'
const validDraft = {
  kind: 'income-account',
  projectId: 7,
  payload: { amount: '250000', billing_nature: 'hosting' },
  origin: { path: '/panel/accounting/incomes', query: { income: '44' } },
}

describe('billingReturnDraft', () => {
  beforeEach(() => sessionStorage.clear())
  afterEach(() => sessionStorage.clear())

  // Falla si volver desde conciliación no recupera en esta pestaña el ingreso y sus campos escritos.
  it('restores a draft for its originating actor', () => {
    const id = saveBillingReturnDraft(12, validDraft)

    expect(readBillingReturnDraft(id, 12)).toEqual({
      ...validDraft,
      actorId: 12,
      schema: 1,
    })
  })

  // Falla si el borrador se reutiliza después de volver al formulario y limpiar su regreso.
  it('removes a saved draft after the return completes', () => {
    const id = saveBillingReturnDraft(12, validDraft)
    const siblingId = saveBillingReturnDraft(12, validDraft)
    removeBillingReturnDraft(id)

    expect(readBillingReturnDraft(id, 12)).toBeNull()
    expect(readBillingReturnDraft(siblingId, 12)).toEqual({ ...validDraft, actorId: 12, schema: 1 })
  })

  // Falla si contenido corrupto o de otra persona puede recuperar un formulario ajeno.
  it.each([
    ['malformed', 'broken-json', 12],
    ['another actor', JSON.stringify({ ...validDraft, actorId: 33, schema: 1 }), 12],
  ])('denies a %s stored draft', (_case, stored, actorId) => {
    sessionStorage.setItem(`${prefix}shared`, stored)

    expect(readBillingReturnDraft('shared', actorId)).toBeNull()
  })

  // Falla si una URL distinta a los formularios de contabilidad puede inyectar un regreso al flujo.
  it('denies a draft from an unrelated origin', () => {
    const siblingId = saveBillingReturnDraft(12, validDraft)
    sessionStorage.setItem(`${prefix}foreign`, JSON.stringify({
      ...validDraft,
      actorId: 12,
      schema: 1,
      origin: { path: '/panel/clients', query: {} },
    }))

    expect(readBillingReturnDraft('foreign', 12)).toBeNull()
    expect(readBillingReturnDraft(siblingId, 12)).toEqual({ ...validDraft, actorId: 12, schema: 1 })
  })
})
