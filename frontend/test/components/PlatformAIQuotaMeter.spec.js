import { mount } from '@vue/test-utils'
import PlatformAIQuotaMeter from '../../components/platform/PlatformAIQuotaMeter.vue'

const translate = (key, params = {}) => ({
  'platformAI.quotaSummary': `${params.used} usados de ${params.limit}; quedan ${params.remaining}`,
  'platformAI.quotaLabel': 'Cupo compartido de IA',
  'platformAI.quotaWindow': `Ventana móvil de ${params.minutes} minutos.`,
  'platformAI.quotaNext': `Próximo cupo: ${params.date}.`,
  'platformAI.quotaEmpty': 'Cupo agotado.',
}[key] || key)

describe('PlatformAIQuotaMeter', () => {
  beforeEach(() => { global.useI18n = () => ({ t: translate, locale: { value: 'es-CO' } }) })
  afterEach(() => { delete global.useI18n; jest.restoreAllMocks() })

  it('shows used and remaining requests in the rolling window', () => {
    // Falla si el cliente ve un reinicio total en vez del cupo restante de la ventana móvil.
    jest.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('24/10/2026, 12:30')
    const wrapper = mount(PlatformAIQuotaMeter, {
      props: { quota: { used: 3, limit: 8, remaining: 5, window_minutes: 300, next_available_at: '2026-10-24T12:30:00Z' } },
    })

    expect(wrapper.get('[data-testid="platform-ai-quota"]').text()).toBe('3 usados de 8; quedan 5Ventana móvil de 300 minutos. Próximo cupo: 24/10/2026, 12:30.')
    wrapper.unmount()
  })

  it('explains an exhausted shared allowance', () => {
    // Falla si llegar al límite oculta que la siguiente solicitud debe esperar una liberación.
    const wrapper = mount(PlatformAIQuotaMeter, {
      props: { quota: { used: 8, limit: 8, remaining: 0, window_minutes: 300, next_available_at: null } },
    })

    expect(wrapper.get('[data-testid="platform-ai-quota"]').text()).toBe('8 usados de 8; quedan 0Ventana móvil de 300 minutos. Cupo agotado.')
    wrapper.unmount()
  })
})
