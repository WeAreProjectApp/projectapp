import { enableAutoUnmount, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useBuildingOnDemandTheme } from '../../composables/useBuildingOnDemandTheme'

enableAutoUnmount(afterEach)
const STORAGE_KEY = 'projectapp-building-on-demand-theme'

const ThemeControls = defineComponent({
  setup() {
    const { theme, toggle } = useBuildingOnDemandTheme()
    return () => h('section', { 'data-testid': 'demand-theme', 'data-theme': theme.value }, [
      h('button', { 'data-testid': 'theme-switch', onClick: toggle }, theme.value),
    ])
  },
})

describe('useBuildingOnDemandTheme', () => {
  beforeEach(() => window.localStorage.clear())
  afterEach(() => window.localStorage.clear())

  it('starts a standalone demand document independently from Building with Us', () => {
    window.localStorage.setItem('projectapp-building-with-us-theme', 'dark')

    const wrapper = mount(ThemeControls)

    expect(wrapper.get('[data-testid="demand-theme"]').attributes('data-theme')).toBe('light')
    expect(wrapper.get('[data-testid="theme-switch"]').text()).toBe('light')
  })

  it('restores the theme saved for the demand document', () => {
    window.localStorage.setItem(STORAGE_KEY, 'dark')

    const wrapper = mount(ThemeControls)

    expect(wrapper.get('[data-testid="demand-theme"]').attributes('data-theme')).toBe('dark')
    expect(wrapper.get('[data-testid="theme-switch"]').text()).toBe('dark')
  })

  it('persists a reader selecting the dark demand theme', async () => {
    const wrapper = mount(ThemeControls)

    await wrapper.get('[data-testid="theme-switch"]').trigger('click')

    expect(wrapper.get('[data-testid="demand-theme"]').attributes('data-theme')).toBe('dark')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('dark')
  })

  it('persists the return to the light demand theme', async () => {
    window.localStorage.setItem(STORAGE_KEY, 'dark')
    const wrapper = mount(ThemeControls)

    await wrapper.get('[data-testid="theme-switch"]').trigger('click')

    expect(wrapper.get('[data-testid="demand-theme"]').attributes('data-theme')).toBe('light')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('light')
  })

  it('normalizes an unsupported saved document theme', () => {
    window.localStorage.setItem(STORAGE_KEY, 'contrast')

    const wrapper = mount(ThemeControls)

    expect(wrapper.get('[data-testid="demand-theme"]').attributes('data-theme')).toBe('light')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('light')
  })

  it('shares a child viewer toggle with its public page', async () => {
    const Host = defineComponent({
      setup() {
        const { theme } = useBuildingOnDemandTheme()
        return () => h('main', { 'data-testid': 'theme-page', 'data-theme': theme.value }, [h(ThemeControls)])
      },
    })
    const wrapper = mount(Host)

    await wrapper.get('[data-testid="theme-switch"]').trigger('click')

    expect(wrapper.get('[data-testid="theme-page"]').attributes('data-theme')).toBe('dark')
    expect(wrapper.get('[data-testid="demand-theme"]').attributes('data-theme')).toBe('dark')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('dark')
  })
})
