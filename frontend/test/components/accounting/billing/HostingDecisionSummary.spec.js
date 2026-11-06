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
  it('renders the proposed identity with readable subscription and record labels', () => {
    const wrapper = mountSummary({
      type: 'identity',
      decision: {
        payload: { reason: 'El cliente confirmó el dominio.' },
        result: { proposal: { subscription_id: 4, add_record_ids: [18], operational_record_id: 18 } },
      },
    })

    expect(wrapper.get('[data-testid="hosting-decision-summary"]').text())
      .toBe('Suscripción#4 · Business PlusRegistros contables que se asociarán#18 · aurora.coRegistro que se usará para cobrar#18 · aurora.coMotivo registradoEl cliente confirmó el dominio.')
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

    expect(wrapper.get('[data-testid="hosting-decision-summary"]').text())
      .toBe('Evidencias seleccionadas · Renovación 2026Pago #8Ciclo #9Cuenta #10Motivo registradoLos comprobantes corresponden al mismo ciclo.')
    expect(wrapper.text()).not.toContain('"payment_ids"')
    wrapper.unmount()
  })
})
