import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref, Suspense } from 'vue'

import FinancingProgramSkeleton from '../../components/Financing/ProgramSkeleton.vue'
import PartnershipProgramPage from '../../pages/partnership-program/index.vue'

const GLOBAL_NAMES = [
  '$fetch',
  'navigateTo',
  'useAsyncData',
  'useFinancingTheme',
  'useHead',
  'useI18n',
  'useRuntimeConfig',
  'useSwitchLocalePath',
]
const originalGlobals = Object.fromEntries(GLOBAL_NAMES.map((name) => [name, global[name]]))

const liveProgram = { hero: { title: 'Construimos hoy. Crecemos contigo.' } }

const ProgramViewStub = {
  props: ['program'],
  template: '<article data-testid="program-view">{{ program.hero.title }}</article>',
}

function pending() {
  return new Promise(() => {})
}

async function mountPage() {
  const Host = defineComponent({
    render: () => h(Suspense, null, { default: () => h(PartnershipProgramPage) }),
  })
  const wrapper = mount(Host, {
    global: {
      components: { FinancingProgramSkeleton },
      stubs: { FinancingProgramView: ProgramViewStub },
    },
  })
  await flushPromises()
  return wrapper
}

describe('partnership program public page', () => {
  beforeEach(() => {
    global.$fetch = jest.fn()
    global.navigateTo = jest.fn()
    // Mirrors Nuxt: the handler runs once and its result becomes the page payload.
    global.useAsyncData = jest.fn(async (key, handler) => ({ data: ref(await handler()) }))
    global.useFinancingTheme = () => ({ theme: ref('light') })
    global.useHead = jest.fn()
    global.useI18n = () => ({ locale: ref('es-co'), t: (key) => key })
    global.useRuntimeConfig = () => ({ apiInternalOrigin: 'http://127.0.0.1:8000' })
    global.useSwitchLocalePath = () => (code) => `/${code}/partnership-program`
  })

  afterAll(() => {
    Object.entries(originalGlobals).forEach(([name, value]) => {
      if (value === undefined) delete global[name]
      else global[name] = value
    })
  })

  it('prerenders a loading skeleton when the build cannot reach the program API', async () => {
    // Fails if a failed build-time fetch bakes a bare spinner into the static HTML.
    global.$fetch.mockRejectedValueOnce(new Error('ECONNREFUSED')).mockReturnValueOnce(pending())

    const wrapper = await mountPage()

    const skeleton = wrapper.get('[data-testid="financing-program-skeleton"]')
    expect(skeleton.attributes('role')).toBe('status')
    expect(skeleton.text()).toBe('financing.loading')
  })

  it('replaces the skeleton with the live program after mount', async () => {
    global.$fetch.mockRejectedValueOnce(new Error('ECONNREFUSED')).mockResolvedValueOnce(liveProgram)

    const wrapper = await mountPage()

    expect(wrapper.get('[data-testid="program-view"]').text()).toBe('Construimos hoy. Crecemos contigo.')
    expect(wrapper.find('[data-testid="financing-program-skeleton"]').exists()).toBe(false)
  })

  it('offers a retry when the live program request also fails', async () => {
    global.$fetch.mockRejectedValue(new Error('ECONNREFUSED'))

    const wrapper = await mountPage()

    expect(wrapper.get('h1').text()).toBe('financing.loadError')
    expect(wrapper.find('[data-testid="financing-program-skeleton"]').exists()).toBe(false)
  })

  it('shows the skeleton while the retry is loading', async () => {
    // Fails if retrying keeps the error on screen until the request settles.
    global.$fetch
      .mockRejectedValueOnce(new Error('ECONNREFUSED'))
      .mockRejectedValueOnce(new Error('Service Unavailable'))
      .mockReturnValueOnce(pending())
    const wrapper = await mountPage()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="financing-program-skeleton"]').text()).toBe('financing.loading')
    expect(wrapper.text()).not.toContain('financing.loadError')
  })
})
