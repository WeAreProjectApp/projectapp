import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import BaseToggle from '../../components/base/BaseToggle.vue'
import ExplainerVisibilityToggle from '../../components/ExplainerVisibilityToggle.vue'
import { usePanelNotify } from '../../composables/usePanelNotify'
import { useExplainerVideosStore } from '../../stores/explainer_videos'

jest.mock('../../composables/usePanelNotify', () => {
  const notify = { success: jest.fn(), error: jest.fn() }
  return { usePanelNotify: jest.fn(() => notify) }
})

global.useI18n = jest.fn(() => ({ t: (key) => key }))

const bothVisible = { show_additional_modules_video: true, show_financing_video: true, show_building_on_demand_video: true }

function mountToggle({
  module = 'additional-modules',
  settings = bothVisible,
  result = { success: true },
} = {}) {
  const store = useExplainerVideosStore()
  store.settings = settings
  store.fetchSettings = jest.fn().mockResolvedValue({ success: true })
  store.setVisibility = jest.fn().mockResolvedValue(result)
  const namespace = module === 'financing' ? 'financing' : module === 'building-on-demand' ? 'buildingOnDemand' : 'additionalModules'
  const wrapper = mount(ExplainerVisibilityToggle, {
    props: { module, i18nNamespace: namespace, testId: module },
    global: { components: { BaseToggle } },
  })
  return { wrapper, store, notify: usePanelNotify() }
}

describe('ExplainerVisibilityToggle', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    jest.clearAllMocks()
  })

  it('reflects the stored switch of its own module', () => {
    const settings = { show_additional_modules_video: true, show_financing_video: false }

    const financing = mountToggle({ module: 'financing', settings }).wrapper
    const catalog = mountToggle({ module: 'additional-modules', settings }).wrapper

    expect(financing.get('[data-testid="financing-visibility-toggle"]').attributes('aria-checked')).toBe('false')
    expect(catalog.get('[data-testid="additional-modules-visibility-toggle"]').attributes('aria-checked')).toBe('true')
    expect(catalog.text()).toContain('additionalModules.explainerVisibilityLabel')
  })

  it('hides the video for clients and confirms the change', async () => {
    const { wrapper, store, notify } = mountToggle()

    await wrapper.get('[data-testid="additional-modules-visibility-toggle"]').trigger('click')
    await flushPromises()

    expect(store.setVisibility).toHaveBeenCalledWith('additional-modules', false)
    expect(notify.success).toHaveBeenCalledWith('additionalModules.explainerVisibilityOff')
  })

  it('reports a failed save without claiming the change', async () => {
    const { wrapper, notify } = mountToggle({
      module: 'financing',
      result: { success: false, errors: {} },
    })

    await wrapper.get('[data-testid="financing-visibility-toggle"]').trigger('click')
    await flushPromises()

    expect(notify.error).toHaveBeenCalledWith('financing.explainerVisibilityError')
    expect(notify.success).not.toHaveBeenCalled()
  })

  it('returns the Scrum switch to its stored visible state after a rejected save', async () => {
    // Fails if the Scrum visibility control sends another module or leaves clients with a falsely hidden state.
    const { wrapper, store, notify } = mountToggle({
      module: 'building-on-demand',
      result: { success: false, errors: { show_building_on_demand_video: ['Invalid value.'] } },
    })

    await wrapper.get('[data-testid="building-on-demand-visibility-toggle"]').trigger('click')
    await flushPromises()

    expect(store.setVisibility).toHaveBeenCalledWith('building-on-demand', false)
    expect(wrapper.get('[data-testid="building-on-demand-visibility-toggle"]').attributes('aria-checked')).toBe('true')
    expect(notify.error).toHaveBeenCalledWith('buildingOnDemand.explainerVisibilityError')
  })

  it('loads the switches and stays disabled until they arrive', () => {
    const { wrapper, store } = mountToggle({ settings: null })

    expect(store.fetchSettings).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="additional-modules-visibility-toggle"]').attributes('disabled')).toBeDefined()
  })
})
