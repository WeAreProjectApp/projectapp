import { mount } from '@vue/test-utils'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseCurrencyInput from '~/components/base/BaseCurrencyInput.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseInput from '~/components/base/BaseInput.vue'
import BaseSegmented from '~/components/base/BaseSegmented.vue'
import VatAmountInput from '~/components/accounting/VatAmountInput.vue'

function mountInput(props = {}) {
  return mount(VatAmountInput, {
    props: { modelValue: 119, rate: 19, ...props },
    global: {
      components: {
        BaseButton,
        BaseCurrencyInput,
        BaseFormField,
        BaseInput,
        BaseSegmented,
        NuxtLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

function amountInput(wrapper) {
  return wrapper.get('[data-testid="vat-amount"]')
}

function rateInput(wrapper) {
  return wrapper.get('[data-testid="vat-rate"]')
}

function tab(wrapper, label) {
  return wrapper.findAll('[role="tab"]').find((candidate) => candidate.text() === label)
}

function button(wrapper, label) {
  return wrapper.findAll('button').find((candidate) => candidate.text() === label)
}

describe('VatAmountInput', () => {
  it('shows the pre-VAT amount when the user changes input mode', async () => {
    // Fails if switching modes changes the money being edited instead of converting its presentation.
    const wrapper = mountInput()

    await tab(wrapper, 'Antes de IVA').trigger('click')

    expect(amountInput(wrapper).element.value).toBe('100')
  })

  it('restores the included total when the user returns to total mode', async () => {
    // Fails if toggling modes permanently replaces the original total with its pre-VAT amount.
    const wrapper = mountInput()

    await tab(wrapper, 'Antes de IVA').trigger('click')
    await tab(wrapper, 'Total con IVA').trigger('click')

    expect(amountInput(wrapper).element.value).toBe('119')
  })

  it('emits the total and capture mode for a pre-VAT amount', async () => {
    // Fails if the form sends the entered base instead of the total the server must persist.
    const wrapper = mountInput()

    await tab(wrapper, 'Antes de IVA').trigger('click')
    await amountInput(wrapper).setValue('100,05')

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual(['119.06'])
    expect(wrapper.emitted('capture').at(-1)).toEqual([{ amount: 100.05, amount_mode: 'before_vat' }])
  })

  it('recalculates the emitted total when the rate changes in pre-VAT mode', async () => {
    // Fails if a rate edit leaves the server capture total at the previous percentage.
    const wrapper = mountInput()

    await tab(wrapper, 'Antes de IVA').trigger('click')
    await rateInput(wrapper).setValue('10')

    expect(wrapper.emitted('update:rate').at(-1)).toEqual(['10'])
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual(['110.00'])
    expect(wrapper.emitted('capture').at(-1)).toEqual([{ amount: '100.00', amount_mode: 'before_vat' }])
  })

  it('keeps an included total when its rate changes after leaving pre-VAT mode', async () => {
    // Fails if a stale pre-VAT capture turns a confirmed $119 total into $110 after its rate changes.
    const wrapper = mountInput()

    await tab(wrapper, 'Antes de IVA').trigger('click')
    await amountInput(wrapper).setValue('100')
    await tab(wrapper, 'Total con IVA').trigger('click')
    await rateInput(wrapper).setValue('10')

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual(['119.00'])
    expect(wrapper.emitted('capture').at(-1)).toEqual([{ amount: 119, amount_mode: 'vat_included' }])
  })

  it('captures zero VAT from the Sin IVA action', async () => {
    // Fails if the shortcut only changes the displayed rate and does not send the exempt capture to the server.
    const wrapper = mountInput()

    await button(wrapper, 'Sin IVA').trigger('click')

    expect(wrapper.emitted('update:rate').at(-1)).toEqual([0])
    expect(wrapper.emitted('capture').at(-1)).toEqual([{ amount: 119, amount_mode: 'vat_included' }])
  })

  it('keeps an optional blank amount null after selecting Sin IVA', async () => {
    // Fails if a Hosting rate edit turns an absent cycle amount into an empty capture that blocks server derivation.
    const wrapper = mountInput({ modelValue: null, required: false })

    await button(wrapper, 'Sin IVA').trigger('click')

    expect(amountInput(wrapper).element.value).toBe('')
    expect(wrapper.emitted('update:rate').at(-1)).toEqual([0])
    expect(wrapper.emitted('capture').at(-1)).toEqual([null])
  })

  it('reopens in total mode after its reset key changes', async () => {
    // Fails if opening a new account reuses the previous form's pre-VAT entry mode.
    const wrapper = mountInput({ resetKey: 1 })

    await tab(wrapper, 'Antes de IVA').trigger('click')
    await wrapper.setProps({ resetKey: 2 })

    expect(tab(wrapper, 'Total con IVA').attributes('aria-selected')).toBe('true')
    expect(amountInput(wrapper).element.value).toBe('119')
  })

  it('shows a validation message for a VAT rate above one hundred percent', async () => {
    // Fails if invalid financial input can reach the form without a visible correction message.
    const wrapper = mountInput()

    await tab(wrapper, 'Antes de IVA').trigger('click')
    await rateInput(wrapper).setValue('101')

    expect(wrapper.get('[role="alert"]').text()).toBe('Revisa el importe y el porcentaje de IVA.')
  })
})
