import { mount } from '@vue/test-utils'
import MonitoringEvidence from '../../components/monitoring/MonitoringEvidence.vue'

global.useI18n = () => ({ t: key => key })

describe('MonitoringEvidence', () => {
  it('omits empty observations while retaining zero and false in the readable summary', () => {
    // quality: allow-no-interaction (la evidencia es una lectura estática de una observación ya recibida).
    // Falla si valores válidos como cero o falso se eliminan junto con el ruido vacío de una alerta.
    const wrapper = mount(MonitoringEvidence, {
      props: { evidence: { message: 'Disco al límite', count: 0, result: false, service: '', missing: null } },
    })

    expect(wrapper.text()).toContain('monitoring.fields.messageDisco al límite')
    expect(wrapper.text()).toContain('monitoring.fields.count0')
    expect(wrapper.text()).toContain('monitoring.fields.resultfalse')
    expect(wrapper.text()).not.toContain('monitoring.fields.service')
    expect(wrapper.text()).toContain('"service": ""')
    expect(wrapper.text()).toContain('"missing": null')
  })
})
