import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref, Suspense } from 'vue'
import ProgramSkeleton from '../../components/BuildingOnDemand/ProgramSkeleton.vue'
import ProgramView from '../../components/BuildingOnDemand/ProgramView.vue'
import PublicPage from '../../pages/building-on-demand/index.vue'
import { useBuildingOnDemandTheme } from '../../composables/useBuildingOnDemandTheme'
import spanishMessages from '../../locales/buildingOnDemand/es'
import englishMessages from '../../locales/buildingOnDemand/en'
import { createBuildingOnDemandProgram } from '../utils/buildingOnDemandFixture'

enableAutoUnmount(afterEach)
const GLOBAL_NAMES = [
  '$fetch', 'navigateTo', 'useAsyncData', 'useBuildingOnDemandTheme',
  'useHead', 'useI18n', 'useRuntimeConfig', 'useSwitchLocalePath',
]
const originalGlobals = Object.fromEntries(GLOBAL_NAMES.map((name) => [name, global[name]]))
let currentLocale
const GUIDE_KEY = 'projectapp-building-on-demand-guide-seen'

const pending = () => new Promise(() => {})

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

async function mountPage() {
  const Host = defineComponent({
    render: () => h(Suspense, null, { default: () => h(PublicPage) }),
  })
  const wrapper = mount(Host, {
    global: {
      components: {
        BuildingOnDemandProgramSkeleton: ProgramSkeleton,
        BuildingOnDemandProgramView: ProgramView,
      },
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

const pageHead = () => global.useHead.mock.calls[0][0]()

describe('BuildingOnDemand public page', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.localStorage.setItem(GUIDE_KEY, 'true')
    currentLocale = ref('es-co')
    global.$fetch = jest.fn()
    global.navigateTo = jest.fn()
    global.useAsyncData = jest.fn(async (key, handler) => ({ data: ref(await handler()) }))
    global.useBuildingOnDemandTheme = useBuildingOnDemandTheme
    global.useHead = jest.fn()
    global.useI18n = () => ({
      locale: currentLocale,
      t: (key, params = {}, options = {}) => {
        const activeLocale = options.locale || currentLocale.value
        const messages = activeLocale === 'en-us' ? englishMessages : spanishMessages
        return (messages[key.split('.').pop()] || key).replace(/\{(\w+)\}/g, (_, name) => params[name] ?? `{${name}}`)
      },
    })
    global.useRuntimeConfig = () => ({ apiInternalOrigin: 'http://127.0.0.1:8000' })
    global.useSwitchLocalePath = () => (code) => `/${code}/building-on-demand`
  })

  afterEach(() => {
    jest.clearAllMocks()
    window.localStorage.clear()
    document.body.innerHTML = ''
  })
  afterAll(() => {
    Object.entries(originalGlobals).forEach(([name, value]) => {
      if (value === undefined) delete global[name]
      else global[name] = value
    })
  })

  it('announces loading while the live document is pending', async () => {
    global.$fetch.mockRejectedValueOnce(new Error('build offline')).mockReturnValueOnce(pending())

    const wrapper = await mountPage()

    expect(wrapper.get('[data-testid="building-on-demand-program-skeleton"]').attributes()).toEqual(expect.objectContaining({
      role: 'status', 'aria-live': 'polite',
    }))
    expect(wrapper.text()).toBe(spanishMessages.loading)
  })

  it('shows the fetched sales document after hydration', async () => {
    const program = createBuildingOnDemandProgram()
    global.$fetch.mockRejectedValueOnce(new Error('build offline')).mockResolvedValueOnce(program)

    const wrapper = await mountPage()

    expect(wrapper.get('h1').text()).toBe(program.hero.title)
    expect(wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').attributes('aria-label')).toBe(spanishMessages.downloadPdf)
    expect(wrapper.find('[data-testid="building-on-demand-program-skeleton"]').exists()).toBe(false)
  })

  it('recovers from a live error when the reader retries', async () => {
    const program = createBuildingOnDemandProgram()
    global.$fetch
      .mockRejectedValueOnce(new Error('build offline'))
      .mockRejectedValueOnce(new Error('live offline'))
      .mockResolvedValueOnce(program)
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="building-on-demand-retry"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe(program.hero.title)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('announces loading during a retry request', async () => {
    global.$fetch
      .mockRejectedValueOnce(new Error('build offline'))
      .mockRejectedValueOnce(new Error('live offline'))
      .mockReturnValueOnce(pending())
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="building-on-demand-retry"]').trigger('click')

    expect(wrapper.get('[role="status"]').text()).toBe(spanishMessages.loading)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('offers retry for an invalid prerender document', async () => {
    const malformed = createBuildingOnDemandProgram()
    malformed.tiers.items = []
    global.$fetch.mockResolvedValueOnce(malformed).mockReturnValueOnce(pending())

    const wrapper = await mountPage()

    expect(wrapper.get('[role="alert"]').text()).toContain(spanishMessages.loadError)
    expect(wrapper.get('[data-testid="building-on-demand-retry"]').text()).toBe(spanishMessages.retry)
  })

  it('rejects malformed tier data returned by the live API', async () => {
    const malformed = createBuildingOnDemandProgram()
    malformed.tiers.items[0].bag_hours = null
    global.$fetch.mockRejectedValueOnce(new Error('build offline')).mockResolvedValueOnce(malformed)

    const wrapper = await mountPage()

    expect(wrapper.get('[role="alert"]').text()).toContain(spanishMessages.loadError)
    expect(wrapper.find('[data-testid="building-on-demand-program"]').exists()).toBe(false)
  })

  it('keeps prerendered content during a temporary live outage', async () => {
    const program = createBuildingOnDemandProgram()
    global.$fetch.mockResolvedValueOnce(program).mockRejectedValueOnce(new Error('live offline'))

    const wrapper = await mountPage()

    expect(wrapper.get('[data-testid="building-on-demand-program"]').text()).toContain(program.hero.title)
    expect(wrapper.find('[data-testid="building-on-demand-retry"]').exists()).toBe(false)
  })

  it('publishes the supplied SEO copy for social sharing', async () => {
    const program = createBuildingOnDemandProgram()
    global.$fetch.mockResolvedValue(program)
    await mountPage()

    const head = pageHead()

    expect(head.title).toBe(program.seo.title)
    expect(head.meta).toEqual(expect.arrayContaining([
      { name: 'description', content: program.seo.description },
      { property: 'og:title', content: program.seo.title },
      { property: 'og:description', content: program.seo.description },
      { name: 'twitter:title', content: program.seo.title },
      { name: 'twitter:description', content: program.seo.description },
    ]))
  })

  it.each([
    ['es-co', spanishMessages],
    ['en-us', englishMessages],
  ])('uses localized SEO during an unavailable %s document', async (locale, messages) => {
    currentLocale.value = locale
    global.$fetch.mockRejectedValueOnce(new Error('build offline')).mockReturnValueOnce(pending())
    await mountPage()

    const head = pageHead()

    expect(head.title).toBe(messages.metaTitle)
    expect(head.meta).toContainEqual({ name: 'description', content: messages.metaDescription })
  })

  it('publishes the English canonical with Spanish as the default alternative', async () => {
    currentLocale.value = 'en-us'
    global.$fetch.mockResolvedValue(createBuildingOnDemandProgram('en'))
    await mountPage()

    const head = pageHead()

    expect(head.htmlAttrs.lang).toBe('en-US')
    expect(head.link).toEqual([
      { rel: 'canonical', href: 'https://projectapp.co/en-us/building-on-demand' },
      { rel: 'alternate', hreflang: 'es-CO', href: 'https://projectapp.co/es-co/building-on-demand' },
      { rel: 'alternate', hreflang: 'en-US', href: 'https://projectapp.co/en-us/building-on-demand' },
      { rel: 'alternate', hreflang: 'x-default', href: 'https://projectapp.co/es-co/building-on-demand' },
    ])
  })

  it('permits search engines to index the sales document', async () => {
    global.$fetch.mockResolvedValue(createBuildingOnDemandProgram())
    await mountPage()

    const head = pageHead()

    expect(head.meta).toContainEqual({ name: 'robots', content: 'index,follow' })
    expect(head.link).toContainEqual({ rel: 'canonical', href: 'https://projectapp.co/es-co/building-on-demand' })
  })

  it('describes the monthly tier range as an aggregate service offer', async () => {
    global.$fetch.mockResolvedValue(createBuildingOnDemandProgram())
    await mountPage()

    const service = JSON.parse(pageHead().script[0].innerHTML)

    expect(service).toEqual(expect.objectContaining({
      '@type': 'Service',
      serviceType: spanishMessages.serviceType,
      url: 'https://projectapp.co/es-co/building-on-demand',
      offers: {
        '@type': 'AggregateOffer', priceCurrency: 'COP',
        lowPrice: 1800000, highPrice: 9600000, offerCount: 3,
      },
    }))
  })

  it('omits unavailable price figures from structured data', async () => {
    global.$fetch.mockRejectedValueOnce(new Error('build offline')).mockReturnValueOnce(pending())
    await mountPage()

    const service = JSON.parse(pageHead().script[0].innerHTML)

    expect(service).not.toHaveProperty('offers')
    expect(service.url).toBe('https://projectapp.co/es-co/building-on-demand')
  })

  it('escapes markup from API copy in the JSON-LD script', async () => {
    const program = createBuildingOnDemandProgram()
    program.seo.description = 'Texto </script> de prueba'
    global.$fetch.mockResolvedValue(program)
    await mountPage()

    const script = pageHead().script[0]

    expect(script.innerHTML).not.toContain('</script>')
    expect(JSON.parse(script.innerHTML).description).toBe(program.seo.description)
  })

  it('switches the sales document to the requested language route', async () => {
    global.$fetch.mockResolvedValue(createBuildingOnDemandProgram())
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="building-on-demand-language-en"]').trigger('click')

    expect(global.navigateTo).toHaveBeenCalledWith('/en-us/building-on-demand')
  })

  it('leaves the current language route in place', async () => {
    global.$fetch.mockResolvedValue(createBuildingOnDemandProgram())
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="building-on-demand-language-es"]').trigger('click')

    expect(global.navigateTo).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="building-on-demand-language-es"]').attributes('aria-selected')).toBe('true')
  })

  it('reloads the document for the new locale', async () => {
    const english = createBuildingOnDemandProgram('en')
    global.$fetch.mockResolvedValueOnce(createBuildingOnDemandProgram()).mockResolvedValueOnce(createBuildingOnDemandProgram()).mockResolvedValueOnce(english)
    const wrapper = await mountPage()

    currentLocale.value = 'en-us'
    await flushPromises()

    expect(global.$fetch).toHaveBeenLastCalledWith('/api/building-on-demand/public/?lang=en')
    expect(wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').attributes('aria-label')).toBe(englishMessages.downloadPdf)
    expect(wrapper.get('h1').text()).toBe(english.hero.title)
  })

  it('preserves the English document when a stale Spanish response arrives', async () => {
    const stale = deferred()
    const english = createBuildingOnDemandProgram('en')
    global.$fetch.mockRejectedValueOnce(new Error('build offline')).mockReturnValueOnce(stale.promise).mockResolvedValueOnce(english)
    const wrapper = await mountPage()
    currentLocale.value = 'en-us'
    await flushPromises()

    stale.resolve(createBuildingOnDemandProgram())
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe(english.hero.title)
    expect(wrapper.get('[data-testid="building-on-demand-language-en"]').attributes('aria-selected')).toBe('true')
  })

  it('preserves English loading when a stale Spanish request fails', async () => {
    const stale = deferred()
    global.$fetch.mockRejectedValueOnce(new Error('build offline')).mockReturnValueOnce(stale.promise).mockReturnValueOnce(pending())
    const wrapper = await mountPage()
    currentLocale.value = 'en-us'
    await flushPromises()

    stale.reject(new Error('Spanish offline'))
    await flushPromises()

    expect(wrapper.get('[role="status"]').text()).toBe(englishMessages.loading)
    expect(wrapper.find('[data-testid="building-on-demand-retry"]').exists()).toBe(false)
  })
})
