import { defineComponent, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import { useBillingDraftReturn } from '../../composables/useBillingDraftReturn'
import { readBillingReturnDraft, saveBillingReturnDraft } from '../../utils/billingReturnDraft'
import hostingBilling from '../../locales/hostingBilling/es'
import { get_request } from '../../stores/services/request_http'
import { useProposalStore } from '../../stores/proposals'
import { usePanelNotify } from '../../composables/usePanelNotify'

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }))
jest.mock('../../composables/usePanelNotify', () => ({ usePanelNotify: jest.fn() }))

const notifyError = jest.fn()
const router = { replace: jest.fn(), push: jest.fn() }
const route = { path: '/panel/accounting/incomes', query: {} }
const originalCrypto = global.crypto
let randomUUID

const Harness = defineComponent({
  setup() {
    const open = ref(false)
    const record = ref(null)
    const billingReturn = useBillingDraftReturn({ kind: 'income-account', open, record })
    return { open, record, resumeDraft: billingReturn.resumeDraft, reconcile: billingReturn.reconcile }
  },
  template: `<section>
    <p data-testid="return-open">{{ open ? 'open' : 'closed' }}</p>
    <p data-testid="return-income">{{ resumeDraft?.selectedIncome?.id || 'none' }} · {{ record?.amount || 'none' }}</p>
    <button data-testid="return-reconcile" @click="reconcile({ selectedIncome: { id: 44, project: 7, client: 17 }, amount: '250000', billing_nature: 'hosting' })">Conciliar</button>
  </section>`,
})

function draft(payload = { selectedIncome: { id: 44, project: 7, client: 17 }, amount: '250000' }) {
  return saveBillingReturnDraft(12, {
    kind: 'income-account',
    projectId: 7,
    origin: { path: '/panel/accounting/incomes', query: { income: '44' } },
    payload,
  })
}

function mountHarness() {
  return mount(Harness, {
    global: {
      plugins: [createI18n({
        legacy: false,
        locale: 'es',
        messages: { es: { hostingBilling } },
      })],
    },
  })
}

describe('useBillingDraftReturn', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setActivePinia(createPinia())
    jest.clearAllMocks()
    randomUUID = jest.fn(() => 'draft-default')
    Object.defineProperty(global, 'crypto', { configurable: true, value: { randomUUID } })
    route.path = '/panel/accounting/incomes'
    route.query = {}
    global.useRoute = () => route
    global.useRouter = () => router
    global.useLocalePath = () => value => value
    useProposalStore().adminUser = { id: 12 }
    usePanelNotify.mockReturnValue({ error: notifyError })
    router.replace.mockResolvedValue(undefined)
    router.push.mockResolvedValue(undefined)
  })

  afterEach(() => {
    sessionStorage.clear()
    delete global.useRoute
    delete global.useRouter
    delete global.useLocalePath
    Object.defineProperty(global, 'crypto', { configurable: true, value: originalCrypto })
    jest.restoreAllMocks()
  })

  // Falla si un regreso válido no reabre la cuenta con el ingreso actual del servidor.
  it('restores an income with unchanged ownership', async () => {
    const id = draft()
    route.query = { returnDraft: id }
    get_request.mockResolvedValue({ data: { id: 44, project: 7, client: 17, amount: '250000' } })
    const wrapper = mountHarness()
    await flushPromises()

    expect(wrapper.get('[data-testid="return-open"]').text()).toBe('open')
    expect(wrapper.get('[data-testid="return-income"]').text()).toBe('44 · 250000')
    expect(router.replace).toHaveBeenCalledWith({
      path: '/panel/accounting/incomes', query: {},
    })
    wrapper.unmount()
  })

  // Falla si un ingreso reasignado abre una cuenta usando la pertenencia que ya no es válida.
  it('keeps the draft stored when current ownership changed', async () => {
    const id = draft()
    route.query = { returnDraft: id }
    get_request.mockResolvedValue({ data: { id: 44, project: 7, client: 99, amount: '250000' } })
    const wrapper = mountHarness()
    await flushPromises()

    expect(wrapper.get('[data-testid="return-open"]').text()).toBe('closed')
    expect(wrapper.get('[data-testid="return-income"]').text()).toBe('none · none')
    expect(readBillingReturnDraft(id, 12)).toEqual(expect.objectContaining({ projectId: 7 }))
    expect(notifyError).toHaveBeenCalledWith({ title: 'El formulario de origen ya no está disponible en esta pestaña.' })
    wrapper.unmount()
  })

  // Falla si una sesión sin usuario intenta consultar un borrador que no le pertenece.
  it('ignores a return draft when the current user is missing', async () => {
    const id = draft()
    route.query = { returnDraft: id }
    useProposalStore().adminUser = null
    const wrapper = mountHarness()
    await flushPromises()

    expect(wrapper.get('[data-testid="return-open"]').text()).toBe('closed')
    expect(get_request).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  // Falla si un parámetro corrupto intenta disparar una recarga de ingreso sin un borrador válido.
  it('ignores a malformed return draft before requesting an income', async () => {
    sessionStorage.setItem('projectapp:billing-return:broken', 'not-json')
    route.query = { returnDraft: 'broken' }
    const wrapper = mountHarness()
    await flushPromises()

    expect(wrapper.get('[data-testid="return-open"]').text()).toBe('closed')
    expect(get_request).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  // Falla si navegar a conciliación expone el formulario en la URL o pierde el regreso del navegador.
  it('stores an opaque draft before navigating to reconciliation', async () => {
    route.query = { income: '44', filter: 'pending', returnDraft: 'old-draft' }
    randomUUID.mockReturnValue('draft-230')
    const wrapper = mountHarness()
    await flushPromises()

    await wrapper.get('[data-testid="return-reconcile"]').trigger('click')
    await flushPromises()

    expect(router.replace).toHaveBeenCalledWith({
      path: '/panel/accounting/incomes',
      query: { income: '44', filter: 'pending', returnDraft: 'draft-230' },
    })
    expect(router.push).toHaveBeenCalledWith({
      path: '/panel/accounting/project-hosting/7', query: { returnDraft: 'draft-230' },
    })
    expect(readBillingReturnDraft('draft-230', 12)).toEqual(expect.objectContaining({
      projectId: 7,
      origin: { path: '/panel/accounting/incomes', query: { income: '44', filter: 'pending' } },
    }))
    expect(randomUUID).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  // Falla si una pestaña sin almacenamiento parece navegar aunque no pueda recuperar su formulario al volver.
  it('keeps the operator on the form when session storage rejects the draft', async () => {
    const setItem = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage disabled')
    })
    const wrapper = mountHarness()
    await flushPromises()

    await wrapper.get('[data-testid="return-reconcile"]').trigger('click')
    await flushPromises()

    expect(router.replace).not.toHaveBeenCalled()
    expect(router.push).not.toHaveBeenCalled()
    expect(notifyError).toHaveBeenCalledWith({ title: 'No se pudo conservar el formulario en esta pestaña. Permite el almacenamiento de sesión antes de salir.' })
    expect(setItem).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})
