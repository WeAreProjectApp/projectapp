import { flushPromises, mount } from '@vue/test-utils'
import BaseRowLink from '~/components/base/BaseRowLink.vue'
import PocketMovementAllocationDetails from '~/components/accounting/PocketMovementAllocationDetails.vue'
import PocketMovementDetailModal from '~/components/accounting/PocketMovementDetailModal.vue'
import { get_request } from '~/stores/services/request_http'

jest.mock('~/stores/services/request_http', () => ({ get_request: jest.fn() }))

const originalUseI18n = global.useI18n
const originalUseLocalePath = global.useLocalePath
const messages = {
  belongsTo: 'Pertenece a', company: 'Empresa', gustavo: 'Gustavo', carlos: 'Carlos', unlinked: 'Sin vincular',
  title: 'Detalle del movimiento', close: 'Cerrar', loading: 'Cargando el movimiento…',
  missing: 'Este movimiento ya no existe.', failed: 'No se pudo cargar el movimiento.', retry: 'Reintentar',
  movement: 'Datos del movimiento', type: 'Tipo', balance: 'Saldo del bolsillo después del movimiento',
  links: 'Pertenencia y vínculo', linked: 'Registro vinculado', income: 'Ingreso', expense: 'Gasto',
  category: 'Categoría del gasto', notes: 'Notas', noNotes: 'Sin notas.', allocations: 'Reparto del abono',
  allocation: 'Importe imputado', pending: 'Pendiente actual', total: 'Total del reparto', credit: 'Saldo a favor',
  discrepancy: 'El total del reparto no coincide con el valor del movimiento.',
}
const t = (key) => messages[key.replace('accountingPocket.', '')] || key

const detail = {
  id: 71,
  concept: 'Abono Kore fase 3',
  movement_date: '2026-10-07',
  direction: 'in',
  direction_label: 'Ingreso',
  amount: '176120.00',
  running_balance: '1025120.00',
  linked_ledger: 'company',
  notes: 'Cliente pidió imputar primero la fase 2.',
  linked_record_detail: { id: 21, type: 'expense', concept: 'Comisión pasarela', category_label: 'Comisiones' },
  allocation_details: [
    { income_id: 31, expected_income_id: 31, concept: 'Fase 2', amount: '120000.00', pending_amount: '0.00' },
    { income_id: 32, expected_income_id: 32, concept: 'Fase 3', amount: '56120.00', pending_amount: '43880.00' },
  ],
}

const NuxtLinkStub = {
  props: ['to'],
  computed: {
    href() {
      if (typeof this.to === 'string') return this.to
      const query = new URLSearchParams(this.to?.query || {}).toString()
      return query ? `${this.to.path}?${query}` : this.to?.path
    },
  },
  template: '<a :href="href"><slot /></a>',
}

const ModalStub = {
  props: ['modelValue', 'kind'],
  emits: ['close'],
  template: '<section v-if="modelValue" :data-kind="kind"><slot /><slot name="footer" /></section>',
}
const HistoryTabsStub = {
  props: ['entityType', 'objectId'],
  template: '<section data-testid="history-tabs" :data-entity="entityType" :data-object="objectId"><slot /></section>',
}

function mountDetail(props = {}) {
  return mount(PocketMovementDetailModal, {
    props: { open: true, movementId: 71, ...props },
    global: {
      components: { BaseRowLink, PocketMovementAllocationDetails },
      stubs: { NuxtLink: NuxtLinkStub, BaseModal: ModalStub, EntityHistoryTabs: HistoryTabsStub },
    },
  })
}

beforeAll(() => {
  global.useI18n = () => ({ t })
  global.useLocalePath = () => (value) => value
})

afterAll(() => {
  global.useI18n = originalUseI18n
  global.useLocalePath = originalUseLocalePath
})

describe('PocketMovementDetailModal', () => {
  beforeEach(() => { jest.clearAllMocks() })

  // Bug caught: opening a closed overlay loaded details before the user requested one.
  it('fetches the movement only after the detail opens', async () => {
    get_request.mockResolvedValueOnce({ data: detail })
    const wrapper = mountDetail({ open: false })
    await flushPromises()

    expect(get_request).not.toHaveBeenCalled()
    await wrapper.setProps({ open: true })
    await flushPromises()

    expect(get_request).toHaveBeenCalledWith('accounting/pocket/71/')
  })

  // Bug caught: the modal showed raw decimals and ISO dates instead of the ledger's vocabulary.
  it('renders the concept, date, type and signed currency in ledger form', async () => {
    get_request.mockResolvedValueOnce({ data: { ...detail, direction: 'out', direction_label: 'Egreso' } })
    const wrapper = mountDetail()
    await flushPromises()

    expect(wrapper.get('[data-testid="pocket-detail-concept"]').text()).toBe('Abono Kore fase 3')
    expect(wrapper.get('[data-testid="pocket-detail-amount"]').text()).toBe('-$176.120')
    expect(wrapper.text()).toContain('Mié, 7 oct 2026')
    expect(wrapper.text()).toContain('Egreso')
  })

  // Bug caught: a detail omitted both the movement owner and its post-movement balance.
  it('renders the attribution and resulting pocket balance', async () => {
    get_request.mockResolvedValueOnce({ data: detail })
    const wrapper = mountDetail()
    await flushPromises()

    expect(wrapper.get('[data-testid="pocket-detail-attribution"]').text()).toBe('Empresa')
    expect(wrapper.get('[data-testid="pocket-detail-balance"]').text()).toBe('$1.025.120')
  })

  // Bug caught: linked expenses opened the income list or hid their category.
  it('links an expense detail with its category', async () => {
    get_request.mockResolvedValueOnce({ data: detail })
    const wrapper = mountDetail()
    await flushPromises()

    expect(wrapper.get('[data-testid="pocket-detail-linked-record"]').attributes('href'))
      .toBe('/panel/accounting/expenses?expense=21')
    expect(wrapper.text()).toContain('Comisiones')
  })

  // Bug caught: the movement detail retained only a hand-written note instead of the allocation data.
  it('renders every allocation with its current pending balance and total', async () => {
    get_request.mockResolvedValueOnce({ data: detail })
    const wrapper = mountDetail()
    await flushPromises()

    expect(wrapper.findAll('[data-testid="pocket-allocation-detail-row"]')).toHaveLength(2)
    expect(wrapper.get('[data-testid="pocket-allocation-detail-total"]').text()).toBe('$176.120')
    expect(wrapper.findAll('[data-testid="pocket-allocation-pending"]')[1].text()).toBe('$43.880')
  })

  // Bug caught: unlinked historic movements looked linked to a nonexistent record.
  it('labels an unlinked movement without allocations', async () => {
    get_request.mockResolvedValueOnce({ data: { ...detail, linked_ledger: null, linked_record_detail: null, allocation_details: [] } })
    const wrapper = mountDetail()
    await flushPromises()

    expect(wrapper.get('[data-testid="pocket-detail-attribution"]').text()).toBe('Sin vincular')
    expect(wrapper.text()).toContain('Registro vinculado')
    expect(wrapper.text()).toContain('Sin vincular')
  })

  // Bug caught: an absent note rendered as a blank section that appeared to have lost information.
  it('shows the explicit no-notes value when notes are empty', async () => {
    get_request.mockResolvedValueOnce({ data: { ...detail, notes: '' } })
    const wrapper = mountDetail()
    await flushPromises()

    expect(wrapper.get('[data-testid="pocket-detail-notes"]').text()).toBe('Sin notas.')
  })

  // Bug caught: a transient failure gave no way to request the detail again.
  it('retries a failed detail request through the same endpoint', async () => {
    get_request
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ data: detail })
    const wrapper = mountDetail()
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(get_request).toHaveBeenNthCalledWith(2, 'accounting/pocket/71/')
    expect(wrapper.get('[data-testid="pocket-detail-concept"]').text()).toBe('Abono Kore fase 3')
  })

  // Bug caught: a deleted movement offered a retry that could never recover the missing record.
  it('does not offer retry for a missing movement', async () => {
    get_request.mockRejectedValueOnce({ response: { status: 404 } })
    const wrapper = mountDetail()
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('Este movimiento ya no existe.')
    expect(wrapper.findAll('button')).toHaveLength(1)
  })

  // Bug caught: the compact detail stopped carrying the movement history identity.
  it('binds the history tabs to the loaded pocket movement', async () => {
    get_request.mockResolvedValueOnce({ data: detail })
    const wrapper = mountDetail()
    await flushPromises()

    expect(wrapper.get('[data-testid="history-tabs"]').attributes('data-entity')).toBe('pocket')
    expect(wrapper.get('[data-testid="history-tabs"]').attributes('data-object')).toBe('71')
  })
})
