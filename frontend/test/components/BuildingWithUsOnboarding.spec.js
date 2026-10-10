import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, onMounted, ref } from 'vue'
import Onboarding from '../../components/BuildingWithUs/Onboarding.vue'
import messages from '../../locales/buildingWithUs/es'

enableAutoUnmount(afterEach)
const originalI18n = global.useI18n
const STORAGE_KEY = 'projectapp-building-with-us-guide-seen'
const targets = [
  { testId: 'building-with-us-hero-aside' },
  { testId: 'building-with-us-origin' },
  { className: 'building-with-us-roles' },
  { className: 'building-with-us-models-nav' },
  { testId: 'building-with-us-periods' },
  { testId: 'building-with-us-milestones' },
  { className: 'building-with-us-faq' },
  { testId: 'building-with-us-download-pdf-floating' },
  { className: 'building-with-us-restart-guide' },
]

function addTargets(entries = targets) {
  entries.forEach(({ testId, className }) => {
    const element = document.createElement('div')
    if (testId) element.setAttribute('data-testid', testId)
    if (className) element.className = className
    document.body.appendChild(element)
  })
}

async function mountOnboarding() {
  // Public views start their guide after the document's targets are mounted.
  const Host = defineComponent({
    setup() {
      const guide = ref(null)
      onMounted(async () => {
        await nextTick()
        guide.value.start()
      })
      return () => h('div', [
        h(Onboarding, { ref: guide }),
        h('button', { 'data-testid': 'restart-guide', onClick: () => guide.value.forceStart() }, 'Restart'),
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

describe('BuildingWithUsOnboarding', () => {
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

  it('starts the first visit despite a completed financing guide', async () => {
    addTargets()
    window.localStorage.setItem('projectapp-financing-guide-seen', 'true')

    const wrapper = await mountOnboarding()

    expect(wrapper.get('[data-testid="building-with-us-guide-progress"]').text()).toBe('1/9')
    expect(wrapper.text()).toContain('Una alianza para construir')
  })

  it('keeps a previously seen guide closed', async () => {
    addTargets()
    window.localStorage.setItem(STORAGE_KEY, 'true')

    const wrapper = await mountOnboarding()

    expect(wrapper.find('[data-testid="building-with-us-guide"]').exists()).toBe(false)
  })

  it('skips absent targets', async () => {
    addTargets([{ testId: 'building-with-us-origin' }])

    const wrapper = await mountOnboarding()

    expect(wrapper.get('[data-testid="building-with-us-guide-progress"]').text()).toBe('1/1')
    expect(wrapper.text()).toContain('El problema es el punto de partida')
  })

  it('reopens a completed guide on demand', async () => {
    addTargets()
    window.localStorage.setItem(STORAGE_KEY, 'true')
    const wrapper = await mountOnboarding()

    await wrapper.get('[data-testid="restart-guide"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="building-with-us-guide-progress"]').text()).toBe('1/9')
  })
})
