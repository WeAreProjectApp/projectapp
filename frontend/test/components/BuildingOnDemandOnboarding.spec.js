import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, onMounted, ref } from 'vue'
import Onboarding from '../../components/BuildingOnDemand/Onboarding.vue'
import messages from '../../locales/buildingOnDemand/es'

enableAutoUnmount(afterEach)
const originalI18n = global.useI18n
const STORAGE_KEY = 'projectapp-building-on-demand-guide-seen'
const targets = [
  { testId: 'building-on-demand-hero' },
  { testId: 'building-on-demand-cell' },
  { testId: 'building-on-demand-terms' },
  { testId: 'building-on-demand-tier-business', recommended: true },
  { testId: 'building-on-demand-bag' },
  { testId: 'building-on-demand-estimator' },
  { testId: 'building-on-demand-hosting' },
  { testId: 'building-on-demand-download-pdf-floating' },
  { testId: 'building-on-demand-guide-restart' },
]

function addTargets(entries = targets) {
  entries.forEach(({ testId, recommended }) => {
    const element = document.createElement('div')
    element.setAttribute('data-testid', testId)
    if (recommended) element.setAttribute('data-recommended', 'true')
    document.body.appendChild(element)
  })
}

async function mountOnboarding({ isDark = false } = {}) {
  const Host = defineComponent({
    setup() {
      const guide = ref(null)
      const completions = ref(0)
      onMounted(async () => {
        await nextTick()
        guide.value.start()
      })
      return () => h('div', [
        h(Onboarding, { ref: guide, isDark, onComplete: () => { completions.value += 1 } }),
        h('button', { 'data-testid': 'restart-guide', onClick: () => guide.value.forceStart() }, 'Restart'),
        h('span', { 'data-testid': 'guide-completions' }, completions.value),
      ])
    },
  })
  const wrapper = mount(Host, {
    global: {
      stubs: {
        Teleport: true,
        Transition: true,
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

async function readTourTitles(wrapper) {
  const titles = [wrapper.get('[role="dialog"] h2').text()]
  while (wrapper.find('[data-testid="building-on-demand-guide-next"]').exists()) {
    await wrapper.get('[data-testid="building-on-demand-guide-next"]').trigger('click')
    await flushPromises()
    titles.push(wrapper.get('[role="dialog"] h2').text())
  }
  return titles
}

describe('BuildingOnDemandOnboarding', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ''
    global.useI18n = () => ({ t: (key) => messages[key.split('.').pop()] || key })
  })

  afterEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ''
  })
  afterAll(() => { global.useI18n = originalI18n })

  it('opens the demand introduction despite a completed Building with Us guide', async () => {
    addTargets()
    window.localStorage.setItem('projectapp-building-with-us-guide-seen', 'true')

    const wrapper = await mountOnboarding()

    expect(wrapper.get('[data-testid="building-on-demand-guide-progress"]').text()).toBe('1/9')
    expect(wrapper.get('[role="dialog"] h2').text()).toBe(messages.guideHeroTitle)
  })

  it('visits the demand sections in the sales document order', async () => {
    addTargets()
    const wrapper = await mountOnboarding()

    const titles = await readTourTitles(wrapper)

    expect(titles).toEqual([
      messages.guideHeroTitle, messages.guideCellTitle, messages.guideTermsTitle,
      messages.guideRecommendedTitle, messages.guideBagTitle, messages.guideEstimatorTitle,
      messages.guideHostingTitle, messages.guideActionsTitle, messages.guideRestartTitle,
    ])
    expect(wrapper.get('[data-testid="building-on-demand-guide-progress"]').text()).toBe('9/9')
  })

  it('finds the recommended card without assuming its tier id', async () => {
    addTargets([{ testId: 'building-on-demand-tier-growth', recommended: true }])

    const wrapper = await mountOnboarding()

    expect(wrapper.get('[role="dialog"] h2').text()).toBe(messages.guideRecommendedTitle)
    expect(wrapper.get('[data-testid="building-on-demand-guide-progress"]').text()).toBe('1/1')
  })

  it('skips missing document sections in a partial preview', async () => {
    addTargets([{ testId: 'building-on-demand-estimator' }])

    const wrapper = await mountOnboarding()

    expect(wrapper.get('[role="dialog"]').text()).toContain(messages.guideEstimatorDescription)
    expect(wrapper.get('[data-testid="building-on-demand-guide-done"]').text()).toBe(messages.guideDone)
  })

  it('keeps a seen demand guide closed until the reader restarts it', async () => {
    addTargets()
    window.localStorage.setItem(STORAGE_KEY, 'true')
    const wrapper = await mountOnboarding()
    expect(wrapper.find('[data-testid="building-on-demand-guide"]').exists()).toBe(false)

    await wrapper.get('[data-testid="restart-guide"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="dialog"] h2').text()).toBe(messages.guideHeroTitle)
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('marks the guide seen when the reader finishes its available step', async () => {
    addTargets([{ testId: 'building-on-demand-guide-restart' }])
    const wrapper = await mountOnboarding()

    await wrapper.get('[data-testid="building-on-demand-guide-done"]').trigger('click')

    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('true')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="guide-completions"]').text()).toBe('1')
  })

  it('keeps the guide in the current dark document theme', async () => {
    addTargets()

    const wrapper = await mountOnboarding({ isDark: true })

    expect(wrapper.get('[role="dialog"]').attributes('data-theme')).toBe('dark')
    expect(wrapper.get('[role="dialog"] h2').text()).toBe(messages.guideHeroTitle)
  })
})
