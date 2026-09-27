import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import BaseToggle from '../../components/base/BaseToggle.vue'
import ProposalExplainerToggle from '../../components/panel/proposal/ProposalExplainerToggle.vue'
import { useExplainerVideosStore } from '../../stores/explainer_videos'

const visibleSettings = { show_proposal_video: true }
const eligibleProposal = {
  is_active: true,
  sections: [{ section_type: 'technical_document', is_enabled: true }],
}

function mountToggle({
  settings = visibleSettings,
  proposal = eligibleProposal,
  language = 'es',
  showLegal = true,
  modelValue = true,
  saving = false,
  fetchSettings = jest.fn().mockResolvedValue({ success: true }),
} = {}) {
  const store = useExplainerVideosStore()
  store.settings = settings
  store.fetchSettings = fetchSettings
  const wrapper = mount(ProposalExplainerToggle, {
    props: { proposal, language, showLegal, modelValue, saving },
    global: {
      components: { BaseToggle },
      stubs: { NuxtLink: { template: '<a><slot /></a>' } },
    },
  })
  return { wrapper, store, fetchSettings }
}

describe('ProposalExplainerToggle', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it.each([
    ['the global setting is disabled', { settings: { show_proposal_video: false } }, 'Oculto: el control general está apagado en Propuestas → Configuraciones.'],
    ['the proposal is English', { language: 'en' }, 'Oculto: el video solo está disponible en español.'],
    ['contract terms are unavailable', { showLegal: false }, 'Oculto: activa Contrato y condiciones para mostrar las cuatro opciones.'],
    ['technical detail is missing', { proposal: { is_active: true, sections: [] } }, 'Oculto: añade y activa el detalle técnico para mostrar las cuatro opciones.'],
    ['technical detail is disabled', { proposal: { is_active: true, sections: [{ section_type: 'technical_document', is_enabled: false }] } }, 'Oculto: añade y activa el detalle técnico para mostrar las cuatro opciones.'],
    ['the proposal is inactive', { proposal: { ...eligibleProposal, is_active: false } }, 'Oculto: la propuesta está inactiva.'],
  ])('shows the exact unavailable status when %s', (_scenario, options, expectedStatus) => {
    // Fails if the panel stops explaining why the customer cannot receive the welcome video.
    const { wrapper } = mountToggle(options)

    expect(wrapper.get('[data-testid="proposal-explainer-status"]').text()).toBe(expectedStatus)
  })

  it('shows the enabled status for a complete Spanish proposal', () => {
    // Fails if eligible proposals are described as hidden despite an enabled individual preference.
    const { wrapper } = mountToggle()

    expect(wrapper.get('[data-testid="proposal-explainer-status"]').text())
      .toBe('Visible al abrir la propuesta. Se reproduce cuando el cliente lo elige.')
  })

  it('emits the exact next individual preference from the enabled toggle', async () => {
    // Fails if the panel toggle does not send the client's new visibility choice to its form.
    const { wrapper } = mountToggle({ modelValue: true })

    await wrapper.get('[data-testid="proposal-explainer-toggle"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('locks the preference while the global setting is still loading', () => {
    // Fails if an editor can save an individual choice before its effective global visibility is known.
    const { wrapper, fetchSettings } = mountToggle({ settings: null })

    expect(fetchSettings).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="proposal-explainer-toggle"]').attributes('disabled')).toBe('')
    expect(wrapper.get('[data-testid="proposal-explainer-status"]').text()).toBe('Consultando el control general…')
  })

  it('retries the settings request after the initial load fails', async () => {
    // Fails if a temporary settings failure leaves the proposal editor without a recovery path.
    const store = useExplainerVideosStore()
    const fetchSettings = jest.fn()
      .mockResolvedValueOnce({ success: false })
      .mockImplementationOnce(async () => {
        store.settings = visibleSettings
        return { success: true }
      })
    const { wrapper } = mountToggle({ settings: null, fetchSettings })
    await flushPromises()

    expect(wrapper.get('[data-testid="proposal-explainer-status"]').text()).toBe('No se pudo consultar el control general.')
    await wrapper.get('[data-testid="proposal-explainer-retry"]').trigger('click')
    await flushPromises()

    expect(fetchSettings).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="proposal-explainer-status"]').text())
      .toBe('Visible al abrir la propuesta. Se reproduce cuando el cliente lo elige.')
  })
})
