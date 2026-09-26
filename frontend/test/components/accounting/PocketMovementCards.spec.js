import { mount } from '@vue/test-utils'
import PocketMovementActionsModal from '~/components/accounting/PocketMovementActionsModal.vue'
import PocketMovementCards from '~/components/accounting/PocketMovementCards.vue'

const MOVEMENT = {
  id: 7,
  concept: 'Pago de infraestructura con referencia extensa',
  movement_date: '2026-08-28',
  direction: 'out',
  direction_label: 'Egreso',
  amount: '2272000.00',
  running_balance: '-149000.00',
  is_auto_managed: true,
}

const RowActionsStub = {
  props: ['row'],
  emits: ['open'],
  template: '<button :data-testid="`stub-actions-${row.id}`" @click="$emit(\'open\', row)">Acciones</button>',
}

function mountCards(props = {}) {
  return mount(PocketMovementCards, {
    props: { rows: [MOVEMENT], ...props },
    global: {
      stubs: {
        NuxtLink: { template: '<a><slot /></a>' },
        PocketMovementRowActionsButton: RowActionsStub,
      },
    },
  })
}

function mountActions(record = MOVEMENT) {
  return mount(PocketMovementActionsModal, {
    props: { open: true, record },
    global: {
      stubs: {
        NuxtLink: { template: '<a><slot /></a>' },
        BaseModal: {
          props: ['modelValue', 'kind'],
          emits: ['close'],
          template: '<div><slot /></div>',
        },
      },
    },
  })
}

describe('PocketMovementCards', () => {
  it('renders the complete ledger reading in one card', () => {
    const wrapper = mountCards()
    const card = wrapper.get('[data-testid="pocket-card-7"]')

    expect(card.text()).toContain(MOVEMENT.concept)
    expect(wrapper.get('[data-testid="pocket-amount-7"]').text()).toBe('-$2.272.000')
    expect(wrapper.get('[data-testid="pocket-date-7"]').text()).toBe('Vie, 28 ago 2026')
    expect(wrapper.get('[data-testid="pocket-direction-7"]').text()).toBe('Egreso')
  })

  it('renders the linked state label in full', () => {
    const badge = mountCards().get('[data-testid="pocket-linked-7"]')

    expect(badge.text()).toBe('Vinculado')
  })

  it('labels the unfiltered running figure as the resulting balance', () => {
    const wrapper = mountCards()
    const balance = wrapper.get('[data-testid="pocket-running-balance-7"]')

    expect(balance.text()).toBe('$-149.000')
    expect(wrapper.get('[data-testid="pocket-card-7"]').text()).toContain('Saldo después')
  })

  it('renames the running figure when filters are active', () => {
    const wrapper = mountCards({ hasActiveFilters: true })

    expect(wrapper.get('[data-testid="pocket-card-7"]').text())
      .toContain('Acumulado filtrado')
  })

  it('forwards the selected row from the leading action', async () => {
    const wrapper = mountCards()

    await wrapper.get('[data-testid="stub-actions-7"]').trigger('click')

    expect(wrapper.emitted('open-actions')[0]).toEqual([MOVEMENT])
  })

  it('opens the allocation detail from the shortened chip', async () => {
    const allocated = {
      ...MOVEMENT,
      is_auto_managed: false,
      allocations: [{ id: 1 }, { id: 2 }],
    }
    const wrapper = mountCards({ rows: [allocated] })

    await wrapper.get('[data-testid="pocket-allocations-7"]').trigger('click')

    expect(wrapper.emitted('open-allocations')[0]).toEqual([allocated])
  })
})

describe('PocketMovementActionsModal', () => {
  it('names the movement being acted on', () => {
    const wrapper = mountActions()

    expect(wrapper.get('[data-testid="pocket-actions-modal"]').text())
      .toContain(MOVEMENT.concept)
  })

  it('emits edit for the selected movement', async () => {
    const wrapper = mountActions()

    await wrapper.get('[data-testid="pocket-action-edit-7"]').trigger('click')

    expect(wrapper.emitted('edit')[0]).toEqual([MOVEMENT])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits delete for the selected movement', async () => {
    const wrapper = mountActions()

    await wrapper.get('[data-testid="pocket-action-delete-7"]').trigger('click')

    expect(wrapper.emitted('delete')[0]).toEqual([MOVEMENT])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  // Bug caught: Detalle e historial overflowed the kebab track onto the ledger.
  it('emits history for the selected movement', async () => {
    const wrapper = mountActions()

    await wrapper.get('[data-testid="pocket-action-history-7"]').trigger('click')

    expect(wrapper.emitted('history')[0]).toEqual([MOVEMENT])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('offers the note only for a movement that has one', async () => {
    expect(mountActions().find('[data-testid="pocket-action-notes-7"]').exists()).toBe(false)

    const withNote = { ...MOVEMENT, notes: 'Pagado con la tarjeta de la empresa' }
    const wrapper = mountActions(withNote)
    await wrapper.get('[data-testid="pocket-action-notes-7"]').trigger('click')

    expect(wrapper.emitted('notes')[0]).toEqual([withNote])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
