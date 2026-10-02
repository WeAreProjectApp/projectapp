import { mount } from '@vue/test-utils'
import VatBreakdown from '~/components/accounting/VatBreakdown.vue'

function mountBreakdown(props = {}) {
  return mount(VatBreakdown, {
    props: { total: '119.00', rate: '19', ...props },
  })
}

describe('VatBreakdown', () => {
  it('renders the base tax and total for a total that includes VAT', () => {
    // Fails if the amount displayed to the client stops matching the VAT split sent in the document.
    const wrapper = mountBreakdown()

    expect(wrapper.get('[data-testid="vat-base"]').text()).toBe('$100 COP')
    expect(wrapper.get('[data-testid="vat-tax"]').text()).toBe('$19 COP')
    expect(wrapper.get('[data-testid="vat-total"]').text()).toBe('$119 COP')
  })

  it('shows an explicit zero VAT amount', () => {
    // Fails if a selected zero rate is rendered as an unrecorded tax value.
    const wrapper = mountBreakdown({ total: '45', rate: '0' })

    expect(wrapper.get('[data-testid="vat-tax"]').text()).toBe('$0 COP')
    expect(wrapper.text()).toContain('IVA (0 %)')
  })

  it('labels a historical amount with no VAT rate as unrecorded', () => {
    // Fails if historical documents without a VAT rate are silently displayed as exempt.
    const wrapper = mountBreakdown({ total: '45', rate: null })

    expect(wrapper.get('[data-testid="vat-tax"]').text()).toBe('IVA sin registrar')
    expect(wrapper.get('[data-testid="vat-total"]').text()).toBe('$45 COP')
  })

  it('uses a persisted tax amount when the document supplies one', () => {
    // Fails if issued documents stop rendering their stored tax split exactly as sent.
    const wrapper = mountBreakdown({ total: 119, rate: 19, tax: 19 })

    expect(wrapper.get('[data-testid="vat-base"]').text()).toBe('$100 COP')
    expect(wrapper.get('[data-testid="vat-tax"]').text()).toBe('$19 COP')
  })
})
