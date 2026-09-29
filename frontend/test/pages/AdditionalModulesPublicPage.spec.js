import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref, Suspense } from 'vue'

import AdditionalModulesPage from '../../pages/additional-modules/index.vue'

const GLOBAL_NAMES = [
  '$fetch',
  'navigateTo',
  'useAdditionalModulesTheme',
  'useAsyncData',
  'useHead',
  'useI18n',
  'useRuntimeConfig',
  'useSwitchLocalePath',
]
const originalGlobals = Object.fromEntries(GLOBAL_NAMES.map((name) => [name, global[name]]))

const liveCatalog = {
  language: 'es',
  categories: [{
    slug: 'commerce',
    name: 'Comercio y transacciones',
    modules: [{ slug: 'electronic-invoicing', name: 'Facturación electrónica' }],
  }],
  total_modules: 1,
  show_explainer_video: true,
}

const CatalogViewStub = {
  props: ['loading', 'totalModules'],
  template: '<div data-testid="catalog-view" :data-loading="String(loading)" :data-total="String(totalModules)" />',
}

function pending() {
  return new Promise(() => {})
}

async function mountPage() {
  const Host = defineComponent({
    render: () => h(Suspense, null, { default: () => h(AdditionalModulesPage) }),
  })
  const wrapper = mount(Host, {
    global: { stubs: { AdditionalModulesCatalogView: CatalogViewStub } },
  })
  await flushPromises()
  return wrapper
}

describe('additional modules public page', () => {
  beforeEach(() => {
    global.$fetch = jest.fn()
    global.navigateTo = jest.fn()
    global.useAdditionalModulesTheme = () => ({ theme: ref('light') })
    // Mirrors Nuxt: the handler runs once and its result becomes the page payload.
    global.useAsyncData = jest.fn(async (key, handler) => ({ data: ref(await handler()) }))
    global.useHead = jest.fn()
    global.useI18n = () => ({ locale: ref('es-co'), t: (key) => key })
    global.useRuntimeConfig = () => ({ apiInternalOrigin: 'http://127.0.0.1:8000' })
    global.useSwitchLocalePath = () => (code) => `/${code}/additional-modules`
  })

  afterAll(() => {
    Object.entries(originalGlobals).forEach(([name, value]) => {
      if (value === undefined) delete global[name]
      else global[name] = value
    })
  })

  it('prerenders a loading skeleton when the build cannot reach the catalog API', async () => {
    // Fails if a failed build-time fetch bakes the empty catalog into the static HTML.
    global.$fetch.mockRejectedValueOnce(new Error('ECONNREFUSED')).mockReturnValueOnce(pending())

    const wrapper = await mountPage()

    expect(wrapper.get('[data-testid="catalog-view"]').attributes('data-loading')).toBe('true')
    expect(wrapper.text()).not.toContain('additionalModules.loadError')
  })

  it('omits the module list structured data while the catalog is pending', async () => {
    // Fails if the prerender advertises an empty ItemList to crawlers.
    global.$fetch.mockRejectedValueOnce(new Error('ECONNREFUSED')).mockReturnValueOnce(pending())

    await mountPage()

    const head = global.useHead.mock.calls[0][0]()
    expect(head.script).toEqual([])
    expect(head.title).toBe('Módulos adicionales para plataformas | Project App.')
  })

  it('replaces the skeleton with the live catalog after mount', async () => {
    global.$fetch.mockRejectedValueOnce(new Error('ECONNREFUSED')).mockResolvedValueOnce(liveCatalog)

    const wrapper = await mountPage()

    const view = wrapper.get('[data-testid="catalog-view"]')
    expect(view.attributes('data-loading')).toBe('false')
    expect(view.attributes('data-total')).toBe('1')
  })

  it('offers a retry when the live catalog request also fails', async () => {
    global.$fetch.mockRejectedValue(new Error('ECONNREFUSED'))

    const wrapper = await mountPage()

    expect(wrapper.get('h1').text()).toBe('additionalModules.loadError')
    expect(wrapper.find('[data-testid="catalog-view"]').exists()).toBe(false)
  })

  it('loads the live catalog from the retry button', async () => {
    global.$fetch
      .mockRejectedValueOnce(new Error('ECONNREFUSED'))
      .mockRejectedValueOnce(new Error('Service Unavailable'))
      .mockResolvedValueOnce(liveCatalog)
    const wrapper = await mountPage()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="catalog-view"]').attributes('data-total')).toBe('1')
    expect(global.$fetch).toHaveBeenLastCalledWith('/api/additional-modules/public/?lang=es')
  })
})
