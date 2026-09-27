import { mount } from '@vue/test-utils'

import AdSpendFormModal from '../../components/accounting/AdSpendFormModal.vue'
import BaseButton from '../../components/base/BaseButton.vue'
import BaseFormField from '../../components/base/BaseFormField.vue'
import BaseInput from '../../components/base/BaseInput.vue'
import BaseSelect from '../../components/base/BaseSelect.vue'
import BaseTextarea from '../../components/base/BaseTextarea.vue'

const BaseModalStub = {
  props: ['modelValue'],
  emits: ['close'],
  template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
}

const BaseCurrencyInputStub = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<input data-testid="currency-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}

const RECORD = {
  spend_date: '2026-03-05',
  platform: 'google',
  origin_card: 'T.C 0655',
  amount: '150000',
  notes: 'Campaña marzo',
}

function mountModal(props = {}) {
  return mount(AdSpendFormModal, {
    props: { open: true, ...props },
    global: {
      components: { BaseButton, BaseFormField, BaseInput, BaseSelect, BaseTextarea },
      stubs: { BaseModal: BaseModalStub, BaseCurrencyInput: BaseCurrencyInputStub },
    },
  })
}

describe('AdSpendFormModal', () => {
  it('opens in create mode with the default platform', () => {
    const wrapper = mountModal()
    expect(wrapper.text()).toContain('Nuevo Gasto en Ads')
    expect(wrapper.find('select').element.value).toBe('facebook')
    expect(wrapper.find('input[type="date"]').element.value).toBe('')
  })

  it('prefills every field in edit mode', () => {
    const wrapper = mountModal({ record: { ...RECORD } })
    expect(wrapper.text()).toContain('Editar Gasto en Ads')
    expect(wrapper.find('input[type="date"]').element.value).toBe('2026-03-05')
    expect(wrapper.find('select').element.value).toBe('google')
    expect(wrapper.find('[data-testid="currency-stub"]').element.value).toBe('150000')
    expect(wrapper.find('textarea').element.value).toBe('Campaña marzo')
  })

  it('emits the full payload on submit', async () => {
    const wrapper = mountModal()
    await wrapper.find('input[type="date"]').setValue('2026-04-01')
    await wrapper.find('select').setValue('other')
    await wrapper.find('input[placeholder="T.C 0655"]').setValue('T.C 0656')
    await wrapper.find('[data-testid="currency-stub"]').setValue('99000')
    await wrapper.find('textarea').setValue('Prueba')
    await wrapper.find('form').trigger('submit')

    expect(wrapper.emitted('submit')[0][0]).toEqual({
      spend_date: '2026-04-01',
      platform: 'other',
      origin_card: 'T.C 0656',
      amount: '99000',
      notes: 'Prueba',
    })
  })

  it('emits close from the cancel button', async () => {
    const wrapper = mountModal()
    await wrapper.getComponent(BaseButton).trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('resets to the empty form when reopened without a record', async () => {
    const wrapper = mountModal({ record: { ...RECORD } })
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true, record: null })
    expect(wrapper.find('input[type="date"]').element.value).toBe('')
    expect(wrapper.find('select').element.value).toBe('facebook')
  })

  it('disables the submit button while saving', () => {
    const wrapper = mountModal({ saving: true })
    const submit = wrapper.get('[data-testid="ad-spend-form-submit"]')
    expect(submit.text()).toBe('Guardando...')
    expect(submit.attributes('disabled')).toBeDefined()
  })
})
