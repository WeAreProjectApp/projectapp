import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import AdditionalModulesCatalogView from '../../components/AdditionalModules/CatalogView.vue'

global.useI18n = jest.fn(() => ({
  t: (key, params = {}) => `${key}${params.name ? `:${params.name}` : ''}`,
}))

const moduleItem = {
  slug: 'electronic-invoicing',
  icon: '🧾',
  name: 'Facturación electrónica',
  summary: 'Emite documentos fiscales desde la plataforma.',
  what_is: 'Una integración fiscal.',
  purpose: 'Automatizar la emisión.',
  problems_solved: ['Evita digitación doble'],
  integrations: ['Proveedor autorizado'],
  implementation_requirements: ['Credenciales del proveedor'],
}

const categories = [{
  slug: 'commerce',
  name: 'Comercio y transacciones',
  modules: [moduleItem],
}]

const ModalStub = {
  props: ['modelValue', 'theme'],
  template: '<div v-if="modelValue" data-testid="modal-stub"><slot /></div>',
}

const OnboardingStub = {
  methods: {
    start() {},
    forceStart() {},
  },
  template: '<div data-testid="additional-modules-onboarding-stub" />',
}

function mountCatalog(props = {}, { renderExplainer = false } = {}) {
  document.body.innerHTML = ''
  return mount(AdditionalModulesCatalogView, {
    props: {
      categories,
      totalModules: 1,
      downloadUrl: '/api/catalog.pdf',
      ...props,
    },
    global: {
      stubs: {
        BaseAlert: { template: '<div role="alert"><slot /></div>' },
        BaseModal: ModalStub,
        BaseCard: { template: '<article><slot /></article>' },
        NuxtLink: { template: '<a><slot /></a>' },
        AdditionalModulesOnboarding: OnboardingStub,
        AdditionalModulesShareButton: {
          template: '<button data-testid="additional-modules-share-floating" />',
        },
        ...(renderExplainer ? {} : {
          ExplainerVideoCard: {
            props: ['video', 'variant', 'testId'],
            template: '<div :data-testid="`${testId}-card`" :data-variant="variant" :data-video-id="video.id" :data-language="video.language" />',
          },
        }),
      },
    },
    attachTo: document.body,
  })
}

describe('AdditionalModulesCatalogView', () => {
  beforeEach(() => {
    window.localStorage.clear()
    global.fetch = jest.fn()
    URL.createObjectURL = jest.fn(() => 'blob:catalog')
    URL.revokeObjectURL = jest.fn()
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('renders the one-screen category index without prices', () => {
    const wrapper = mountCatalog()

    expect(wrapper.text()).toContain('Comercio y transacciones')
    expect(wrapper.text()).toContain('Facturación electrónica')
    expect(wrapper.text()).toContain('Emite documentos fiscales')
    expect(wrapper.text()).not.toMatch(/\$|COP|USD/)
    expect(wrapper.get('[data-testid="additional-modules-download-pdf"]').element.tagName)
      .toBe('BUTTON')
  })

  it('opens all five content blocks in a modal', async () => {
    const wrapper = mountCatalog()

    await wrapper.get('[data-testid="additional-module-card-electronic-invoicing"]').trigger('click')

    const modal = wrapper.get('[data-testid="additional-module-detail-modal"]')
    expect(modal.text()).toContain('Una integración fiscal.')
    expect(modal.text()).toContain('Automatizar la emisión.')
    expect(modal.text()).toContain('Evita digitación doble')
    expect(modal.text()).toContain('Proveedor autorizado')
    expect(modal.text()).toContain('Credenciales del proveedor')
  })

  it('returns focus to the selected card after closing the modal', async () => {
    const wrapper = mountCatalog({ downloadUrl: '' })
    const card = wrapper.get('[data-testid="additional-module-card-electronic-invoicing"]')
    card.element.focus()
    await card.trigger('click')

    const closeButton = wrapper.get('[aria-label="additionalModules.close"]')
    await closeButton.trigger('click')
    await nextTick()

    expect(document.activeElement).toBe(card.element)
  })

  it('shows an explicit empty state when no active modules remain', () => {
    const wrapper = mountCatalog({ categories: [], totalModules: 0 })

    expect(wrapper.text()).toContain('additionalModules.emptyTitle')
    expect(wrapper.find('[data-testid^="additional-module-card-"]').exists()).toBe(false)
  })

  it('shows a loading skeleton instead of the empty state while the catalog is pending', () => {
    // Fails if a prerender whose API fetch failed bakes «No hay módulos disponibles».
    const wrapper = mountCatalog({ categories: [], totalModules: 0, loading: true })

    const skeleton = wrapper.get('[data-testid="additional-modules-skeleton"]')
    expect(skeleton.attributes('role')).toBe('status')
    expect(skeleton.text()).toBe('additionalModules.loading')
    expect(wrapper.text()).not.toContain('additionalModules.emptyTitle')
  })

  it('keeps the catalog heading while the catalog is pending', () => {
    // Fails if the pending prerender loses its indexable title or offers a PDF of nothing.
    const wrapper = mountCatalog({ categories: [], totalModules: 0, loading: true })

    expect(wrapper.get('h1').text()).toBe('additionalModules.title')
    expect(wrapper.find('[data-testid="additional-modules-download-pdf"]').exists()).toBe(false)
  })

  it('shows compact rows after selecting list view', async () => {
    const wrapper = mountCatalog()

    await wrapper.get('[data-testid="additional-view-list"]').trigger('click')

    expect(wrapper.get('[data-testid="additional-module-list-electronic-invoicing"]').text())
      .toContain('Facturación electrónica')
    expect(wrapper.find('[data-testid="additional-module-card-electronic-invoicing"]').exists())
      .toBe(false)
  })

  it('reveals module content from the accordion trigger', async () => {
    const wrapper = mountCatalog()
    await wrapper.get('[data-testid="additional-view-accordion"]').trigger('click')
    const trigger = wrapper.get('[data-testid="additional-module-accordion-trigger-electronic-invoicing"]')

    await trigger.trigger('click')

    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('[data-testid="additional-module-accordion-electronic-invoicing"]').text())
      .toContain('Credenciales del proveedor')
  })

  it('requests the selected catalog language', async () => {
    const wrapper = mountCatalog({ language: 'es' })

    await wrapper.get('[data-testid="additional-language-en"]').trigger('click')

    expect(wrapper.emitted('change-language')).toEqual([['en']])
  })

  it('remembers the selected public catalog theme', async () => {
    const wrapper = mountCatalog()

    await wrapper.get('[data-testid="additional-modules-theme-toggle"]').trigger('click')

    expect(wrapper.get('[data-theme="dark"]').exists()).toBe(true)
    expect(window.localStorage.getItem('projectapp-additional-modules-theme')).toBe('dark')

    wrapper.unmount()
    const restored = mountCatalog()
    expect(restored.get('[data-theme="dark"]').exists()).toBe(true)
  })

  it('downloads through the floating PDF action', async () => {
    const clickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    global.fetch.mockResolvedValue({
      ok: true,
      blob: jest.fn().mockResolvedValue(new Blob(['pdf'])),
      headers: { get: jest.fn(() => 'attachment; filename="catalogo.pdf"') },
    })
    const wrapper = mountCatalog()

    await wrapper.get('[data-testid="additional-modules-download-pdf-floating"]').trigger('click')
    await Promise.resolve()
    await nextTick()

    expect(global.fetch).toHaveBeenCalledWith('/api/catalog.pdf', { credentials: 'same-origin' })
    expect(clickSpy).toHaveBeenCalledTimes(1)
  })
})

describe('AdditionalModulesCatalogView explainer video', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('places the Spanish explainer between the title and the first module', () => {
    const wrapper = mountCatalog({ language: 'es' })

    const card = wrapper.get('[data-testid="additional-modules-explainer-card"]')
    expect(card.attributes('data-variant')).toBe('hero')
    expect(card.attributes('data-video-id')).toBe('additional-modules')
    expect(card.attributes('data-language')).toBe('es')
    expect(card.classes()).toContain('additional-modules-explainer')

    const heading = wrapper.get('h1').element
    const firstModule = wrapper.get('[data-testid="additional-module-card-electronic-invoicing"]').element
    expect(heading.compareDocumentPosition(card.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(card.element.compareDocumentPosition(firstModule) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('hides the explainer while no English render exists', () => {
    const wrapper = mountCatalog({ language: 'en' })

    expect(wrapper.get('h1').text()).toContain('additionalModules.title')
    expect(wrapper.find('[data-testid="additional-modules-explainer-card"]').exists()).toBe(false)
  })

  it('omits the explainer together with the public header', () => {
    const wrapper = mountCatalog({ language: 'es', showHeader: false })

    expect(wrapper.find('[data-testid="additional-modules-explainer-card"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="additional-module-card-electronic-invoicing"]').exists()).toBe(true)
  })

  it('hides the explainer until the catalog payload arrives', () => {
    // Fails if a video the panel switched off flashes inside the prerendered skeleton.
    const wrapper = mountCatalog({ language: 'es', categories: [], totalModules: 0, loading: true })

    expect(wrapper.find('[data-testid="additional-modules-explainer-card"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="additional-modules-skeleton"]').attributes('aria-live')).toBe('polite')
  })

  it('hides the Spanish explainer when the panel switch turns it off', () => {
    const wrapper = mountCatalog({ language: 'es', showExplainer: false })

    expect(wrapper.find('[data-testid="additional-modules-explainer-card"]').exists()).toBe(false)
    expect(wrapper.get('h1').text()).toContain('additionalModules.title')
    expect(wrapper.find('[data-testid="additional-module-card-electronic-invoicing"]').exists()).toBe(true)
  })

  it('renders the uploaded video source in English', async () => {
    // Fails if an uploaded English resource is discarded because no bundled English render exists.
    jest.spyOn(document, 'hasFocus').mockReturnValue(true)
    jest.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    const playSpy = jest.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    const wrapper = mountCatalog({
      language: 'en',
      showExplainer: true,
      explainerResource: {
        mode: 'uploaded',
        video: {
          id: 'additional-modules',
          source: 'uploaded',
          src: '/api/video-resources/id/22/video/',
          poster: '/api/video-resources/id/22/poster/',
          durationSeconds: 42,
          width: 1920,
          height: 1080,
        },
      },
    }, { renderExplainer: true })

    await wrapper.get('[data-testid="additional-modules-explainer-play"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="additional-modules-explainer-player"]').attributes('src'))
      .toBe('/api/video-resources/id/22/video/')
    expect(playSpy).toHaveBeenCalledTimes(1)
  })

  it('hides a removed explainer resource in Spanish', () => {
    // Fails if a resource removed in the panel or MCP revives the bundled card.
    const wrapper = mountCatalog({
      language: 'es',
      showExplainer: true,
      explainerResource: { mode: 'none' },
    }, { renderExplainer: true })

    expect(wrapper.find('[data-testid="additional-modules-explainer-card"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="additional-modules-catalog"]').text())
      .toContain('additionalModules.title')
  })
})
