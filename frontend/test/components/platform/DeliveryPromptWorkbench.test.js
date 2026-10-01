import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DeliveryPromptWorkbench from '../../../components/platform/delivery/DeliveryPromptWorkbench.vue'
import { usePlatformDeliveryStore } from '../../../stores/platform-delivery'
import spanish from '../../../locales/platformDelivery/es'

jest.mock('../../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
jest.mock('../../../composables/useClipboardFeedback', () => ({
  useClipboardFeedback: () => ({ copyText: jest.fn().mockResolvedValue(true) }),
}))
const { usePlatformApi } = require('../../../composables/usePlatformApi')
const translate = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key
const contextId = 'ba809dd2-35c1-4857-8b1c-b1c43e24c925'
const citation = () => ({ source_key: 'source-1', locator: 'lines:1-2', quote: 'Alcance de inventario.' })
const createContext = (overrides = {}) => ({
  id: contextId, mode: 'guides', prompt: 'Guías sobre el contrato seleccionado.',
  complete: true, version: 4, warnings: [],
  template: { schema_version: 2, context_id: contextId, scopes: [] },
  sources: [{
    source_key: 'source-1', title: 'Contrato de inventario', origin: 'signature',
    source_id: 3, role: 'contract', version: 2, date: '2026-09-30',
    sha256: 'a'.repeat(64), status: 'included', warnings: [],
    fragments: [{ locator: 'lines:1-2', text: 'Alcance de inventario.' }],
  }], ...overrides,
})
const createReply = () => ({
  schema_version: 2, context_id: contextId, response_text: 'Atenderemos la validación del inventario.',
  classifications: [{ request: 'Validar inventario', classification: 'inside_scope', rationale: 'Lo contempla el contrato.', citations: [citation()] }],
})

describe('Source selection for delivery prompts', () => {
  let api
  let store
  const wrappers = []
  beforeEach(() => {
    setActivePinia(createPinia())
    global.useI18n = () => ({ t: translate })
    api = { get: jest.fn(), request: jest.fn() }
    usePlatformApi.mockReturnValue(api)
    store = usePlatformDeliveryStore()
    store.projectId = 7
    store.workspace = {
      project: { id: 7 }, version: 4,
      contracts: [
        { id: 3, title: 'Contrato de inventario', amendments: [{ id: 4, title: 'Otrosí inventario' }] },
        { id: 6, title: 'Contrato de ventas', amendments: [] },
      ],
      scopes: [{ id: 2, contract_id: 3, amendment_id: 4, title: 'Inventario', phases: [{ id: 5, stages: [{ id: 11 }] }] }],
    }
    api.get.mockResolvedValue({ data: {
      contracts: store.contracts,
      documents: [{ id: 8, title: 'Anexo de inventario', source_version: 2 }],
      proposal_documents: [],
    } })
  })
  afterEach(() => {
    wrappers.forEach((wrapper) => wrapper.unmount())
    wrappers.length = 0
    delete global.useI18n
    jest.clearAllMocks()
  })
  async function renderWorkbench(props = {}) {
    const wrapper = mount(DeliveryPromptWorkbench, {
      props: { mode: 'guides', ...props },
      global: { stubs: { NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } },
    })
    wrappers.push(wrapper)
    await flushPromises()
    return wrapper
  }
  async function prepareGuides(wrapper, data = createContext()) {
    api.request.mockResolvedValueOnce({ data })
    await wrapper.get('[data-testid="delivery-prompt-contract"]').setValue('3')
    await wrapper.get('[data-testid="delivery-prompt-prepare"]').trigger('click')
    await flushPromises()
  }

  it('requires an explicit contract before capturing sources', async () => {
    const wrapper = await renderWorkbench()
    await wrapper.get('[data-testid="delivery-prompt-prepare"]').trigger('click')
    expect(api.request).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Completa este campo.')
  })

  it('prepares initial guides without a stage', async () => {
    const wrapper = await renderWorkbench()
    await prepareGuides(wrapper)
    expect(api.request.mock.calls[0][0].data).toEqual(expect.objectContaining({ mode: 'guides', contract_id: 3, sources: [], amendment_ids: [] }))
    expect(api.request.mock.calls[0][0].data.stage_id).toBeUndefined()
    expect(wrapper.get('[data-testid="delivery-prompt-sources"]').text()).toContain('Contrato de inventario')
  })

  it('requires a basis for an explicitly selected annex', async () => {
    const wrapper = await renderWorkbench()
    await wrapper.get('[data-testid="delivery-prompt-contract"]').setValue('3')
    await wrapper.get('[data-testid="delivery-prompt-select-document-8"] input').setValue(true)
    await wrapper.get('[data-testid="delivery-prompt-prepare"]').trigger('click')
    expect(api.request).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Completa este campo.')
  })

  it('retains an annex selection separately from its contractual interpretation', async () => {
    const wrapper = await renderWorkbench()
    await wrapper.get('[data-testid="delivery-prompt-contract"]').setValue('3')
    await wrapper.get('[data-testid="delivery-prompt-select-document-8"] input').setValue(true)
    await wrapper.get('#delivery-source-role-document-8').setValue('contractual_annex')
    await wrapper.get('#delivery-source-note-document-8').setValue('Anexo referido en el apartado de inventario.')
    api.request.mockResolvedValueOnce({ data: createContext() })
    await wrapper.get('[data-testid="delivery-prompt-prepare"]').trigger('click')
    await flushPromises()
    expect(api.request.mock.calls[0][0].data.sources).toEqual([{ document_id: 8, role: 'contractual_annex', applicability_note: 'Anexo referido en el apartado de inventario.' }])
  })

  it('invalidates retained output when switching contracts', async () => {
    const wrapper = await renderWorkbench()
    await prepareGuides(wrapper)
    await wrapper.get('[data-testid="delivery-prompt-contract"]').setValue('6')
    expect(wrapper.find('[data-testid="delivery-prompt-sources"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="delivery-prompt-apply"]').exists()).toBe(false)
  })

  it('replaces the prior scope amendment when switching the selected scope', async () => {
    store.workspace.contracts[0].amendments.push({ id: 9, title: 'Otrosí de almacenes' })
    store.workspace.scopes.push({ id: 12, contract_id: 3, amendment_id: 9, title: 'Almacenes', phases: [] })
    const wrapper = await renderWorkbench()
    await wrapper.get('[data-testid="delivery-prompt-contract"]').setValue('3')
    await wrapper.get('[data-testid="delivery-prompt-scope"]').setValue('2')
    await wrapper.get('[data-testid="delivery-prompt-scope"]').setValue('12')
    api.request.mockResolvedValueOnce({ data: createContext() })
    await wrapper.get('[data-testid="delivery-prompt-prepare"]').trigger('click')
    await flushPromises()
    expect(api.request.mock.calls[0][0].data.amendment_ids).toEqual([9])
  })

  it('shows missing sources before using the prompt', async () => {
    const wrapper = await renderWorkbench()
    await prepareGuides(wrapper, createContext({
      complete: false, warnings: ['Falta el anexo técnico.'],
      sources: [{ source_key: 'missing-1', title: 'Anexo técnico', role: 'missing', status: 'missing', warnings: [], fragments: [] }],
    }))
    expect(wrapper.get('[data-testid="delivery-prompt-incomplete"]').text()).toContain('fuentes incompletas')
    expect(wrapper.get('[data-testid="delivery-prompt-source-missing-1"]').text()).toContain('Faltante')
  })

  it('rejects a JSON from another captured context', async () => {
    const wrapper = await renderWorkbench()
    await prepareGuides(wrapper)
    await wrapper.get('[data-testid="delivery-prompt-json"]').setValue(JSON.stringify({ schema_version: 2, context_id: 'different-context', scopes: [] }))
    await wrapper.get('[data-testid="delivery-prompt-preview"]').trigger('click')
    expect(api.request).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Este JSON pertenece a otra selección de fuentes.')
  })

  it('requires another preview after editing validated JSON', async () => {
    const wrapper = await renderWorkbench()
    await prepareGuides(wrapper)
    api.request.mockResolvedValueOnce({ data: { valid: true, summary: { stages: 1 }, payload: createContext().template } })
    await wrapper.get('[data-testid="delivery-prompt-preview"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-prompt-apply"]').element.disabled).toBe(false)
    await wrapper.get('[data-testid="delivery-prompt-json"]').setValue('{}')
    expect(wrapper.get('[data-testid="delivery-prompt-apply"]').element.disabled).toBe(true)
  })

  it('uses the stage contract when preparing a response', async () => {
    const wrapper = await renderWorkbench({ mode: 'reply', stage: { id: 11 } })
    api.request.mockResolvedValueOnce({ data: createContext({ mode: 'reply', template: createReply() }) })
    await wrapper.get('[data-testid="delivery-prompt-prepare"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-prompt-contract"]').element.disabled).toBe(true)
    expect(api.request.mock.calls[0][0].data).toEqual(expect.objectContaining({ mode: 'reply', stage_id: 11, contract_id: 3, scope_id: 2, amendment_ids: [4] }))
  })

  it('passes a validated response draft for manual review without sending it', async () => {
    const wrapper = await renderWorkbench({ mode: 'reply', stage: { id: 11 } })
    api.request.mockResolvedValueOnce({ data: createContext({ mode: 'reply', template: createReply() }) })
    await wrapper.get('[data-testid="delivery-prompt-prepare"]').trigger('click')
    await flushPromises()
    api.request.mockResolvedValueOnce({ data: { valid: true, payload: createReply(), classifications: createReply().classifications } })
    await wrapper.get('[data-testid="delivery-prompt-preview"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="delivery-prompt-reply-draft"]').setValue('Revisamos el pedido y atenderemos el inventario.')
    await wrapper.get('[data-testid="delivery-prompt-use-reply"]').trigger('click')
    expect(wrapper.emitted('reply')[0][0]).toEqual(expect.objectContaining({ message: 'Revisamos el pedido y atenderemos el inventario.', context_id: contextId, classifications: createReply().classifications, source_references: [citation()] }))
    expect(api.request.mock.calls.map(([request]) => request.url)).toEqual(['projects/7/delivery/prompt/', 'projects/7/delivery/reply/preview/'])
  })
})
