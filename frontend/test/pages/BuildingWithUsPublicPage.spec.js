import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref, Suspense } from 'vue'
import ProgramSkeleton from '../../components/BuildingWithUs/ProgramSkeleton.vue'
import PublicPage from '../../pages/building-with-us/index.vue'
import messages from '../../locales/buildingWithUs/es'

enableAutoUnmount(afterEach)
const GLOBAL_NAMES = [
  '$fetch', 'navigateTo', 'useAsyncData', 'useBuildingWithUsTheme',
  'useHead', 'useI18n', 'useRuntimeConfig', 'useSwitchLocalePath',
]
const originalGlobals = Object.fromEntries(GLOBAL_NAMES.map((name) => [name, global[name]]))
let currentLocale

function createProgram(overrides = {}) {
  return {
    language: 'es', version: 1, updated_at: '2026-10-09T00:00:00Z',
    canonical_path: '/es-co/building-with-us', alternate_path: '/en-us/building-with-us',
    pdf_path: '/api/building-with-us/public/pdf/?lang=es',
    seo: { title: 'Building with Us | Tu producto con Project App.', description: 'Incubamos productos con expertos de industria.' },
    hero: {
      eyebrow: 'Alianza de producto', title: 'Construye con nosotros',
      subtitle: 'Construimos para ti.', note: 'La participación se gana al cumplir los hitos pactados.',
    },
    ...overrides,
  }
}

const ProgramViewStub = {
  props: ['program', 'language', 'downloadUrl'],
  emits: ['change-language'],
  template: '<article><h1>{{ program.hero.title }}</h1><button data-testid="switch-language" @click="$emit(\'change-language\', \'en\')">English</button></article>',
}

const pending = () => new Promise(() => {})

async function mountPage() {
  const Host = defineComponent({
    render: () => h(Suspense, null, { default: () => h(PublicPage) }),
  })
  const wrapper = mount(Host, {
    global: {
      components: { BuildingWithUsProgramSkeleton: ProgramSkeleton },
      stubs: {
        BuildingWithUsProgramView: ProgramViewStub,
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('BuildingWithUs public page', () => {
  beforeEach(() => {
    currentLocale = ref('es-co')
    global.$fetch = jest.fn()
    global.navigateTo = jest.fn()
    global.useAsyncData = jest.fn(async (key, handler) => ({ data: ref(await handler()) }))
    global.useBuildingWithUsTheme = () => ({ theme: ref('light') })
    global.useHead = jest.fn()
    global.useI18n = () => ({ locale: currentLocale, t: (key) => messages[key.split('.').pop()] || key })
    global.useRuntimeConfig = () => ({ apiInternalOrigin: 'http://127.0.0.1:8000' })
    global.useSwitchLocalePath = () => (code) => `/${code}/building-with-us`
  })

  afterAll(() => {
    Object.entries(originalGlobals).forEach(([name, value]) => {
      if (value === undefined) delete global[name]
      else global[name] = value
    })
  })

  it('prerenders a skeleton after a failed build request', async () => {
    global.$fetch.mockRejectedValueOnce(new Error('ECONNREFUSED')).mockReturnValueOnce(pending())

    const wrapper = await mountPage()

    const skeleton = wrapper.get('[data-testid="building-with-us-program-skeleton"]')
    expect(skeleton.attributes('role')).toBe('status')
    expect(skeleton.text()).toBe('Cargando Building with Us…')
  })

  it('replaces the skeleton with live content', async () => {
    global.$fetch.mockRejectedValueOnce(new Error('ECONNREFUSED')).mockResolvedValueOnce(createProgram())

    const wrapper = await mountPage()

    expect(wrapper.get('[data-testid="building-with-us-program"]').text()).toContain('Construye con nosotros')
    expect(wrapper.find('[data-testid="building-with-us-program-skeleton"]').exists()).toBe(false)
  })

  it('recovers the program through retry', async () => {
    global.$fetch
      .mockRejectedValueOnce(new Error('ECONNREFUSED'))
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(createProgram())
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="building-with-us-retry"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="building-with-us-program"]').text()).toContain('Construye con nosotros')
    expect(wrapper.find('[data-testid="building-with-us-retry"]').exists()).toBe(false)
  })

  it('shows the skeleton during retry', async () => {
    global.$fetch
      .mockRejectedValueOnce(new Error('ECONNREFUSED'))
      .mockRejectedValueOnce(new Error('offline'))
      .mockReturnValueOnce(pending())
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="building-with-us-retry"]').trigger('click')

    expect(wrapper.get('[data-testid="building-with-us-program-skeleton"]').attributes('role')).toBe('status')
  })

  it('rejects an empty prerender payload', async () => {
    global.$fetch.mockResolvedValueOnce({}).mockReturnValueOnce(pending())

    const wrapper = await mountPage()

    expect(wrapper.get('[role="alert"]').text()).toContain('No pudimos cargar Building with Us.')
    expect(wrapper.find('[data-testid="building-with-us-program"]').exists()).toBe(false)
  })

  it('rejects an empty live payload', async () => {
    global.$fetch.mockRejectedValueOnce(new Error('ECONNREFUSED')).mockResolvedValueOnce({})

    const wrapper = await mountPage()

    expect(wrapper.get('[data-testid="building-with-us-retry"]').text()).toBe('Reintentar')
    expect(wrapper.find('[data-testid="building-with-us-program-skeleton"]').exists()).toBe(false)
  })

  it('publishes the canonical public URL', async () => {
    global.$fetch.mockResolvedValue(createProgram())
    await mountPage()

    const head = global.useHead.mock.calls[0][0]()

    expect(head.link).toContainEqual({ rel: 'canonical', href: 'https://projectapp.co/es-co/building-with-us' })
  })

  it('permits indexing of the public page', async () => {
    global.$fetch.mockResolvedValue(createProgram())
    await mountPage()

    const head = global.useHead.mock.calls[0][0]()

    expect(head.meta).toContainEqual({ name: 'robots', content: 'index,follow' })
  })

  it('uses the API SEO title', async () => {
    global.$fetch.mockResolvedValue(createProgram())
    await mountPage()

    const head = global.useHead.mock.calls[0][0]()

    expect(head.title).toBe('Building with Us | Tu producto con Project App.')
    expect(head.meta).toContainEqual({ property: 'og:title', content: 'Building with Us | Tu producto con Project App.' })
  })

  it('uses a localized SEO fallback while content is unavailable', async () => {
    global.$fetch.mockRejectedValueOnce(new Error('ECONNREFUSED')).mockReturnValueOnce(pending())
    await mountPage()

    const head = global.useHead.mock.calls[0][0]()

    expect(head.title).toBe(messages.metaTitle)
    expect(head.meta).toContainEqual({ name: 'description', content: messages.metaDescription })
  })

  it('publishes the language alternatives', async () => {
    global.$fetch.mockResolvedValue(createProgram())
    await mountPage()

    const head = global.useHead.mock.calls[0][0]()

    expect(head.link).toEqual(expect.arrayContaining([
      { rel: 'alternate', hreflang: 'es-CO', href: 'https://projectapp.co/es-co/building-with-us' },
      { rel: 'alternate', hreflang: 'en-US', href: 'https://projectapp.co/en-us/building-with-us' },
      { rel: 'alternate', hreflang: 'x-default', href: 'https://projectapp.co/es-co/building-with-us' },
    ]))
  })

  it('describes an incubation service in structured data', async () => {
    global.$fetch.mockResolvedValue(createProgram())
    await mountPage()

    const head = global.useHead.mock.calls[0][0]()
    const service = JSON.parse(head.script[0].innerHTML)

    expect(service['@type']).toBe('Service')
    expect(service.serviceType).toBe('Alianza de incubación y desarrollo de productos de software')
  })

  it('navigates to the requested locale', async () => {
    global.$fetch.mockResolvedValue(createProgram())
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="switch-language"]').trigger('click')

    expect(global.navigateTo).toHaveBeenCalledWith('/en-us/building-with-us')
  })

  it('requests localized content after a locale change', async () => {
    global.$fetch.mockResolvedValue(createProgram())
    await mountPage()

    currentLocale.value = 'en-us'
    await flushPromises()

    expect(global.$fetch).toHaveBeenLastCalledWith('/api/building-with-us/public/?lang=en')
  })

  it('ignores an outdated language response', async () => {
    let resolveSpanish
    const english = createProgram({
      language: 'en', hero: { title: 'Build with us' },
      canonical_path: '/en-us/building-with-us', alternate_path: '/es-co/building-with-us',
    })
    global.$fetch
      .mockRejectedValueOnce(new Error('ECONNREFUSED'))
      .mockReturnValueOnce(new Promise((resolve) => { resolveSpanish = resolve }))
      .mockResolvedValueOnce(english)
    const wrapper = await mountPage()

    currentLocale.value = 'en-us'
    await flushPromises()
    resolveSpanish(createProgram())
    await flushPromises()

    expect(wrapper.get('[data-testid="building-with-us-program"]').text()).toContain('Build with us')
  })
})
