import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import HostingDecisionSummary from '../../../../components/accounting/billing/HostingDecisionSummary.vue'
import hostingBilling from '../../../../locales/hostingBilling/es'

const inventory = {
  subscriptions: [{ id: 4, plan: 'Business Plus' }],
  accounting_sources: [{ id: 18, domain_url: 'aurora.co' }],
}

function mountSummary(props) {
  return mount(HostingDecisionSummary, {
    props: { inventory, ...props },
    global: {
      plugins: [createI18n({
        legacy: false,
        locale: 'es',
        messages: { es: { hostingBilling } },
      })],
    },
  })
}

describe('HostingDecisionSummary', () => {
  // Falla si la revisión de identidad vuelve a mostrar la estructura técnica en vez de sus referencias reconocibles.
  it('renders a readable identity decision', () => {
    const wrapper = mountSummary({
      type: 'identity',
      decision: {
        payload: { reason: 'El cliente confirmó el dominio.' },
        result: { proposal: { subscription_id: 4, add_record_ids: [18], operational_record_id: 18 } },
      },
    })

    expect(wrapper.text()).toContain('#4 · Business Plus')
    expect(wrapper.text()).toContain('#18 · aurora.co')
    expect(wrapper.text()).toContain('El cliente confirmó el dominio.')
    expect(wrapper.text()).not.toContain('{"subscription_id"')
    wrapper.unmount()
  })

  // Falla si la revisión de evidencias oculta pagos, ciclos o cuentas que el operador está por equivaler.
  it('renders the selected evidence as named records', () => {
    const wrapper = mountSummary({
      type: 'evidence',
      decision: {
        payload: { reason: 'Los comprobantes corresponden al mismo ciclo.' },
        result: { proposal: { label: 'Renovación 2026', payment_ids: [8], cycle_ids: [9], document_ids: [10] } },
      },
    })

    expect(wrapper.text()).toContain('Renovación 2026')
    expect(wrapper.text()).toContain('Pago #8')
    expect(wrapper.text()).toContain('Ciclo #9')
    expect(wrapper.text()).toContain('Cuenta #10')
    expect(wrapper.text()).not.toContain('"payment_ids"')
    wrapper.unmount()
  })
})
