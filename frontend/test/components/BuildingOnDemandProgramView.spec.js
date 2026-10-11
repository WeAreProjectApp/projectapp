import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import ProgramView from '../../components/BuildingOnDemand/ProgramView.vue'
import messages from '../../locales/buildingOnDemand/es'
import englishMessages from '../../locales/buildingOnDemand/en'
import { createBuildingOnDemandProgram } from '../utils/buildingOnDemandFixture'

enableAutoUnmount(afterEach)

const originalI18n = global.useI18n
const originalFetch = global.fetch
const originalCreateObjectURL = URL.createObjectURL
const originalRevokeObjectURL = URL.revokeObjectURL
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
const originalShare = Object.getOwnPropertyDescriptor(navigator, 'share')
const GUIDE_KEY = 'projectapp-building-on-demand-guide-seen'

function translate(key, params = {}, options = {}) {
  const dictionary = options.locale === 'en-us' ? englishMessages : messages
  return (dictionary[key.split('.').pop()] || key).replace(/\{(\w+)\}/g, (_, name) => params[name] ?? `{${name}}`)
}

function mountProgram(props = {}) {
  return mount(ProgramView, {
    props: { program: createBuildingOnDemandProgram(), downloadUrl: '/api/building-on-demand/public/pdf/?lang=es', ...props },
    attachTo: document.body,
    global: {
      stubs: {
        Teleport: true,
        Transition: true,
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
}

function mockPdf(disposition = '') {
  global.fetch.mockResolvedValue({
    ok: true, headers: { get: () => disposition },
    blob: jest.fn().mockResolvedValue(new Blob(['PDF'], { type: 'application/pdf' })),
  })
}

describe('BuildingOnDemandProgramView', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.localStorage.setItem(GUIDE_KEY, 'true')
    global.useI18n = () => ({ t: translate })
    global.fetch = jest.fn()
    URL.createObjectURL = jest.fn(() => 'blob:building-on-demand')
    URL.revokeObjectURL = jest.fn()
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: jest.fn().mockResolvedValue(undefined) } })
    Object.defineProperty(navigator, 'share', { configurable: true, value: undefined })
  })

  afterEach(() => {
    jest.restoreAllMocks()
    window.localStorage.clear()
    document.body.innerHTML = ''
    window.history.replaceState({}, '', '/')
  })

  afterAll(() => {
    global.useI18n = originalI18n
    global.fetch = originalFetch
    URL.createObjectURL = originalCreateObjectURL
    URL.revokeObjectURL = originalRevokeObjectURL
    delete navigator.clipboard
    delete navigator.share
    if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard)
    if (originalShare) Object.defineProperty(navigator, 'share', originalShare)
  })

  describe('content', () => {
    it('presents the sections in the sales journey order', () => {
      const wrapper = mountProgram()

      const sections = wrapper.findAll('[data-document-enter]')
      expect(sections.map((section) => section.attributes('data-testid'))).toEqual([
        'building-on-demand-hero', 'building-on-demand-cell', 'building-on-demand-fit',
        'building-on-demand-tiers', 'building-on-demand-bag', 'building-on-demand-estimator',
        'building-on-demand-hosting', 'building-on-demand-faq', undefined, 'building-on-demand-disclaimer',
      ])
      expect(wrapper.get('[data-testid="building-on-demand-positioning"]').text()).toBe(createBuildingOnDemandProgram().hero.positioning)
    })

    it('links the hero actions to the interactive sections', () => {
      const wrapper = mountProgram()

      expect(wrapper.get('[data-testid="building-on-demand-view-tiers"]').attributes('href')).toBe('#tiers')
      expect(wrapper.get('[data-testid="building-on-demand-tiers"]').attributes('id')).toBe('tiers')
      expect(wrapper.get('[data-testid="building-on-demand-view-estimator"]').attributes('href')).toBe('#estimator')
      expect(wrapper.get('[data-testid="building-on-demand-estimator"]').attributes('id')).toBe('estimator')
    })

    it('compares the complete cell with the available tier roles', () => {
      const wrapper = mountProgram()

      expect(wrapper.findAll('[data-testid^="building-on-demand-role-"]').map((role) => role.get('h3').text())).toEqual([
        'Dos desarrolladores', 'Líder de proyecto', 'Diseñador', 'Arquitecto de desarrollo', 'Scrum Master', 'QA',
      ])
      expect(wrapper.get('[data-testid="building-on-demand-cell"]').text()).toContain(createBuildingOnDemandProgram().cell.note)
      expect(wrapper.get('[data-testid="building-on-demand-tier-business"]').attributes('data-recommended')).toBe('true')
    })

    it('distinguishes suitable work from a dedicated development project', () => {
      const wrapper = mountProgram()

      expect(wrapper.get('[data-testid="building-on-demand-good-for"]').text()).toContain('Organizar herramientas que crecieron sin estructura.')
      expect(wrapper.get('[data-testid="building-on-demand-not-for"]').text()).toContain('Eso requiere un proyecto completo de desarrollo.')
    })

    it('updates every tier price from the selected prepaid term', async () => {
      const wrapper = mountProgram()

      await wrapper.get('[data-testid="building-on-demand-term-quarterly"]').trigger('click')

      expect(wrapper.get('[data-testid="building-on-demand-price-starter"]').text()).toContain('$1.710.000 COP')
      expect(wrapper.get('[data-testid="building-on-demand-price-business"]').text()).toContain('$3.780.000 COP')
      expect(wrapper.get('[data-testid="building-on-demand-price-enterprise"]').text()).toContain('$8.160.000 COP')
      expect(wrapper.get('[data-testid="building-on-demand-total-business"]').text()).toContain('$11.340.000 COP')
      expect(wrapper.get('[data-testid="building-on-demand-terms"]').text()).toContain(createBuildingOnDemandProgram().terms.note)
    })

    it('returns the term selector to monthly pricing', async () => {
      const wrapper = mountProgram()
      await wrapper.get('[data-testid="building-on-demand-term-nine-month"]').trigger('click')

      await wrapper.get('[data-testid="building-on-demand-term-monthly"]').trigger('click')

      expect(wrapper.get('[data-testid="building-on-demand-price-business"]').text()).toContain('$4.200.000 COP')
      expect(wrapper.find('[data-testid="building-on-demand-total-business"]').exists()).toBe(false)
      expect(wrapper.get('[data-testid="building-on-demand-terms"]').text()).not.toContain(createBuildingOnDemandProgram().terms.note)
    })

    it('resets a removed term after a public program refresh', async () => {
      const wrapper = mountProgram()
      await wrapper.get('[data-testid="building-on-demand-term-quarterly"]').trigger('click')
      const program = createBuildingOnDemandProgram()
      program.terms.items = [program.terms.items[0]]

      await wrapper.setProps({ program })

      expect(wrapper.get('[data-testid="building-on-demand-term-monthly"]').attributes('aria-selected')).toBe('true')
      expect(wrapper.get('[data-testid="building-on-demand-price-starter"]').text()).toContain('$1.800.000 COP')
    })

    it('keeps preventive server care outside the monthly bag', () => {
      const program = createBuildingOnDemandProgram()
      const wrapper = mountProgram({ program })

      expect(wrapper.get('[data-testid="building-on-demand-hosting"]').text()).toContain(program.hosting.note)
      expect(wrapper.findAll('[data-testid^="building-on-demand-hosting-"]').map((feature) => feature.get('h3').text())).toEqual(program.hosting.features.map((feature) => feature.title))
      expect(wrapper.get('[data-testid="building-on-demand-bag"]').text()).toContain(program.bag.rules[2].summary)
    })

    it('keeps private payload extras outside the sales document', () => {
      const program = createBuildingOnDemandProgram()
      program.internal = { provider: 'PRIVATE_PROVIDER_SENTINEL', hour_cost: 55000 }
      program.contract = { markdown: 'PRIVATE_AGREEMENT_SENTINEL', pdf_path: '/api/building-on-demand/admin/contract/pdf/' }
      const wrapper = mountProgram({ program })

      expect(wrapper.text()).not.toContain('PRIVATE_PROVIDER_SENTINEL')
      expect(wrapper.text()).not.toContain('PRIVATE_AGREEMENT_SENTINEL')
      expect(wrapper.find('a[href*="/contract/"]').exists()).toBe(false)
      expect(wrapper.get('[data-testid="building-on-demand-disclaimer"]').text()).toBe(program.legal.disclaimer)
    })

    it('closes an expanded FAQ answer on a second click', async () => {
      const wrapper = mountProgram()
      const trigger = wrapper.get('[data-testid="building-on-demand-faq-trigger-unused-hours"]')
      await trigger.trigger('click')
      expect(wrapper.get('[data-testid="building-on-demand-faq-panel-unused-hours"]').text()).toBe(createBuildingOnDemandProgram().faq.items[0].answer)

      await trigger.trigger('click')

      expect(trigger.attributes('aria-expanded')).toBe('false')
      expect(wrapper.get('[data-testid="building-on-demand-faq-panel-unused-hours"]').isVisible()).toBe(false)
    })

    it('emits the English locale selected in the document header', async () => {
      const wrapper = mountProgram()

      await wrapper.get('[data-testid="building-on-demand-language-en"]').trigger('click')

      expect(wrapper.emitted('change-language')).toEqual([['en']])
      expect(wrapper.get('[data-testid="building-on-demand-language-es"]').attributes('aria-selected')).toBe('true')
    })

    it('localizes preview chrome for an English program', () => {
      const wrapper = mountProgram({ program: createBuildingOnDemandProgram('en'), language: 'en', floatingActions: false })

      expect(wrapper.get('[data-testid="building-on-demand-view-tiers"]').text()).toBe('View tiers')
      expect(wrapper.get('[data-testid="building-on-demand-hero-aside"]').text()).toContain('A complete cell to help your product evolve')
      expect(wrapper.get('[data-testid="building-on-demand-theme-toggle"]').attributes('aria-label')).toBe('Toggle theme')
    })
  })

  describe('document actions', () => {
    it('persists the preview theme without floating actions', async () => {
      const wrapper = mountProgram({ floatingActions: false })

      await wrapper.get('[data-testid="building-on-demand-theme-toggle"]').trigger('click')

      expect(wrapper.get('[data-testid="building-on-demand-program"]').attributes('data-theme')).toBe('dark')
      expect(window.localStorage.getItem('projectapp-building-on-demand-theme')).toBe('dark')
      expect(wrapper.find('[data-testid="building-on-demand-guide-restart"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="building-on-demand-share"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="building-on-demand-download-pdf-floating"]').exists()).toBe(false)
    })

    it('restarts the remembered guide from its floating control', async () => {
      const wrapper = mountProgram()
      await flushPromises()

      await wrapper.get('[data-testid="building-on-demand-guide-restart"]').trigger('click')
      await flushPromises()

      expect(wrapper.get('[data-testid="building-on-demand-guide-progress"]').text()).toBe('1/9')
      expect(wrapper.get('[data-testid="building-on-demand-guide"]').text()).toContain(messages.guideHeroTitle)
      expect(window.localStorage.getItem(GUIDE_KEY)).toBeNull()
    })

    it('starts the guide after the public section targets mount', async () => {
      window.localStorage.removeItem(GUIDE_KEY)
      const wrapper = mountProgram()

      await flushPromises()

      expect(wrapper.get('[data-testid="building-on-demand-guide-progress"]').text()).toBe('1/9')
      expect(wrapper.get('[data-testid="building-on-demand-guide"]').text()).toContain(messages.guideHeroDescription)
    })

    it.each([
      ['', 'es', 'building-on-demand-es.pdf'],
      ['', 'en', 'building-on-demand-en.pdf'],
      ['attachment; filename="programa.pdf"', 'es', 'programa.pdf'],
      ["attachment; filename*=UTF-8''c%C3%A9lula.pdf", 'es', 'célula.pdf'],
      ["attachment; filename*=UTF-8''%ZZ; filename=programa.pdf", 'es', 'programa.pdf'],
    ])('downloads the PDF named by %s in %s', async (disposition, language, expectedFilename) => {
      mockPdf(disposition)
      let savedDownload
      jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { savedDownload = { filename: this.download, href: this.href } })
      const wrapper = mountProgram({ language })

      await wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').trigger('click')
      await flushPromises()

      expect(savedDownload).toEqual({ filename: expectedFilename, href: 'blob:building-on-demand' })
      expect(global.fetch).toHaveBeenCalledWith('/api/building-on-demand/public/pdf/?lang=es', { credentials: 'same-origin' })
      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:building-on-demand')
    })

    it('allows a PDF retry after a rejected request', async () => {
      global.fetch.mockRejectedValueOnce(new Error('offline'))
      const wrapper = mountProgram()
      await wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').trigger('click')
      await flushPromises()
      expect(wrapper.get('[data-testid="building-on-demand-pdf-error"]').text()).toBe(messages.pdfError)
      mockPdf()
      jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

      await wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').trigger('click')
      await flushPromises()

      expect(wrapper.find('[data-testid="building-on-demand-pdf-error"]').exists()).toBe(false)
      expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    })

    it('reports an unsuccessful PDF response before saving a file', async () => {
      global.fetch.mockResolvedValue({ ok: false, status: 503 })
      const wrapper = mountProgram()

      await wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').trigger('click')
      await flushPromises()

      expect(wrapper.get('[data-testid="building-on-demand-pdf-error"]').text()).toBe(messages.pdfError)
      expect(URL.createObjectURL).not.toHaveBeenCalled()
      expect(wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').attributes('disabled')).toBeUndefined()
    })

    it('blocks a duplicate download while the PDF request is pending', async () => {
      let resolvePdf
      global.fetch.mockReturnValue(new Promise((resolve) => { resolvePdf = resolve }))
      const wrapper = mountProgram()
      await wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').trigger('click')

      await wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').trigger('click')

      expect(global.fetch).toHaveBeenCalledTimes(1)
      expect(wrapper.get('[data-testid="building-on-demand-download-pdf-floating"]').attributes('disabled')).toBeDefined()
      resolvePdf({ ok: false, status: 500 })
      await flushPromises()
    })

    it('omits the PDF action when a download is unavailable', () => {
      const wrapper = mountProgram({ downloadUrl: '' })

      expect(wrapper.find('[data-testid="building-on-demand-download-pdf-floating"]').exists()).toBe(false)
      expect(wrapper.get('[data-testid="building-on-demand-share"]').attributes('aria-label')).toBe(messages.shareCurrent)
    })

    it('copies the locale specific public document URL', async () => {
      window.history.replaceState({}, '', '/es-co/building-on-demand')
      const wrapper = mountProgram()

      await wrapper.get('[data-testid="building-on-demand-share"]').trigger('click')
      await wrapper.get('[data-testid="building-on-demand-copy-link"]').trigger('click')
      await flushPromises()

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost/es-co/building-on-demand')
      expect(wrapper.get('[data-testid="building-on-demand-share-feedback"]').text()).toBe(messages.copied)
      expect(wrapper.get('[data-testid="building-on-demand-share-dialog"]').attributes('aria-label')).toBe(messages.shareCurrent)
    })

    it('replaces an unsafe final contact URL with WhatsApp', () => {
      const program = createBuildingOnDemandProgram()
      program.cta.whatsapp_url = 'javascript:alert(1)'
      program.cta.button_label = ''
      const wrapper = mountProgram({ program })

      const contact = wrapper.get('[data-testid="building-on-demand-cta"]')
      expect(contact.attributes('href')).toBe('https://wa.me/573238122373')
      expect(contact.attributes('rel')).toBe('noopener noreferrer')
      expect(contact.text()).toBe(messages.whatsappCta)
    })
  })
})
