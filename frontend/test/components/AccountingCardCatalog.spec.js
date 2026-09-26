import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import AccountingCardCatalog from '../../components/accounting/AccountingCardCatalog.vue'
import BaseButton from '../../components/base/BaseButton.vue'
import BaseFormField from '../../components/base/BaseFormField.vue'
import BaseInput from '../../components/base/BaseInput.vue'
import BaseToggle from '../../components/base/BaseToggle.vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePanelNotify } from '../../composables/usePanelNotify'

jest.mock('../../composables/usePanelNotify', () => {
  const notify = { success: jest.fn(), error: jest.fn() }
  return { usePanelNotify: jest.fn(() => notify) }
})

const ConfirmModalStub = {
  props: ['modelValue'],
  template: '<div v-if="modelValue" data-testid="confirm-stub" />',
}

// BaseCurrencyInput formats/parses money; a plain numeric input keeps the
// v-model contract without pulling its masking logic into these tests.
const BaseCurrencyInputStub = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" v-bind="$attrs" />',
}

const card = (overrides = {}) => ({
  id: 1,
  name: 'T.C 0655',
  credit_limit: '9000000',
  is_active: true,
  statements_since: '2026-05-01',
  ...overrides,
})

function mountCatalog({ cards = [card()], results = {} } = {}) {
  const store = useAccountingStore()
  store.creditCards = cards
  store.fetchRecords = jest.fn().mockResolvedValue({ success: true })
  store.createRecord = jest.fn().mockResolvedValue(results.create ?? { success: true })
  store.updateRecord = jest.fn().mockResolvedValue(results.update ?? { success: true })
  store.deleteRecord = jest.fn().mockResolvedValue(results.delete ?? { success: true })
  const wrapper = mount(AccountingCardCatalog, {
    global: {
      components: { BaseButton, BaseFormField, BaseInput, BaseToggle },
      stubs: {
        ConfirmModal: ConfirmModalStub,
        BaseCurrencyInput: BaseCurrencyInputStub,
        NuxtLink: { template: '<a><slot /></a>' },
        // The row menu and the history dialog are BaseModals; inline here.
        BaseModal: {
          props: ['modelValue'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /></div>',
        },
        EntityHistoryTabs: {
          props: ['entityType', 'objectId'],
          template: '<section data-testid="history-tabs"><slot /></section>',
        },
      },
    },
  })
  return { wrapper, store }
}

async function chooseCardAction(wrapper, action) {
  await wrapper.get('[data-testid="card-catalog-actions-card-1"]').trigger('click')
  await wrapper.get(`[data-testid="card-catalog-action-${action}-card-1"]`).trigger('click')
  await flushPromises()
}

describe('AccountingCardCatalog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    jest.clearAllMocks()
  })

  it('loads the catalog on mount and renders a row per card', async () => {
    const { wrapper, store } = mountCatalog({ cards: [card(), card({ id: 2, name: 'T.C 0656' })] })
    await flushPromises()

    expect(store.fetchRecords).toHaveBeenCalledWith('creditCards')
    expect(wrapper.get('[data-testid="card-catalog-name-card-1"]').element.value).toBe('T.C 0655')
    expect(wrapper.get('[data-testid="card-catalog-name-card-2"]').element.value).toBe('T.C 0656')
  })

  it('trims the statements_since date down to its month', async () => {
    const { wrapper } = mountCatalog()
    await flushPromises()
    expect(wrapper.get('[data-testid="card-catalog-since-card-1"]').element.value).toBe('2026-05')
  })

  it('adds an empty draft row from the add button', async () => {
    const { wrapper } = mountCatalog()
    await flushPromises()

    await wrapper.get('[data-testid="card-catalog-add"]').trigger('click')

    expect(wrapper.get('[data-testid="card-catalog-name-draft-1"]').element.value).toBe('')
  })

  it('rejects saving a card without a name or a positive limit', async () => {
    const { wrapper, store } = mountCatalog()
    await flushPromises()
    await wrapper.get('[data-testid="card-catalog-add"]').trigger('click')

    await wrapper.get('[data-testid="card-catalog-save-draft-1"]').trigger('click')
    await flushPromises()

    expect(store.createRecord).not.toHaveBeenCalled()
    expect(usePanelNotify().error).toHaveBeenCalled()
  })

  it('creates a new card from a filled draft row', async () => {
    const { wrapper, store } = mountCatalog()
    await flushPromises()
    await wrapper.get('[data-testid="card-catalog-add"]').trigger('click')
    await wrapper.get('[data-testid="card-catalog-name-draft-1"]').setValue('T.C 0999')
    await wrapper.get('[data-testid="card-catalog-limit-draft-1"]').setValue('5000000')

    await wrapper.get('[data-testid="card-catalog-save-draft-1"]').trigger('click')
    await flushPromises()

    expect(store.createRecord).toHaveBeenCalledWith(
      'creditCards',
      expect.objectContaining({ name: 'T.C 0999', credit_limit: 5000000 }),
    )
    expect(usePanelNotify().success).toHaveBeenCalledWith('Tarjeta agregada.')
  })

  it('updates an existing card through the store', async () => {
    const { wrapper, store } = mountCatalog()
    await flushPromises()
    await wrapper.get('[data-testid="card-catalog-name-card-1"]').setValue('T.C 0655 renombrada')

    await wrapper.get('[data-testid="card-catalog-save-card-1"]').trigger('click')
    await flushPromises()

    expect(store.updateRecord).toHaveBeenCalledWith(
      'creditCards',
      1,
      expect.objectContaining({ name: 'T.C 0655 renombrada' }),
    )
    expect(usePanelNotify().success).toHaveBeenCalledWith('Tarjeta actualizada.')
  })

  it('surfaces the backend message when a save fails', async () => {
    const { wrapper } = mountCatalog({
      results: { update: { success: false, message: 'Cupo inválido' } },
    })
    await flushPromises()

    await wrapper.get('[data-testid="card-catalog-save-card-1"]').trigger('click')
    await flushPromises()

    expect(usePanelNotify().error).toHaveBeenCalledWith(
      expect.objectContaining({ detail: 'Cupo inválido' }),
    )
  })

  it('removes an unsaved draft row without asking for confirmation', async () => {
    const { wrapper, store } = mountCatalog()
    await flushPromises()
    await wrapper.get('[data-testid="card-catalog-add"]').trigger('click')

    await wrapper.get('[data-testid="card-catalog-delete-draft-1"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="card-catalog-name-draft-1"]').exists()).toBe(false)
    expect(store.deleteRecord).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="confirm-stub"]').exists()).toBe(false)
  })

  it('asks for confirmation before deleting a persisted card from its menu', async () => {
    const { wrapper, store } = mountCatalog()
    await flushPromises()

    await chooseCardAction(wrapper, 'delete')

    expect(wrapper.find('[data-testid="confirm-stub"]').exists()).toBe(true)
    expect(store.deleteRecord).not.toHaveBeenCalled()
  })

  // Bug caught: the history button received the editable copy, which drops the
  // notes and trims statements_since, so it showed unsaved values.
  it('feeds the history with the stored card, not the form being edited', async () => {
    const { wrapper } = mountCatalog({ cards: [card({ notes: 'Tarjeta de la empresa' })] })
    await flushPromises()
    await wrapper.get('[data-testid="card-catalog-name-card-1"]').setValue('Nombre sin guardar')

    await chooseCardAction(wrapper, 'history')

    const history = wrapper.get('[data-testid="history-tabs"]')
    expect(history.text()).toContain('T.C 0655')
    expect(history.text()).toContain('Tarjeta de la empresa')
    expect(history.text()).not.toContain('Nombre sin guardar')
  })
})
