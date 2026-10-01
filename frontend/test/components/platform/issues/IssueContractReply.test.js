import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BaseAlert from '../../../../components/base/BaseAlert.vue'
import BaseButton from '../../../../components/base/BaseButton.vue'
import BaseCheckbox from '../../../../components/base/BaseCheckbox.vue'
import BaseSelect from '../../../../components/base/BaseSelect.vue'
import BaseTextarea from '../../../../components/base/BaseTextarea.vue'
import IssueContractReply from '../../../../components/platform/issues/IssueContractReply.vue'
import { usePlatformApi } from '../../../../composables/usePlatformApi'

jest.mock('../../../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
jest.mock('../../../../composables/useClipboardFeedback', () => ({
  useClipboardFeedback: () => ({ copyText: jest.fn().mockResolvedValue(true) }),
}))

function deferred() {
  let resolve
  const promise = new Promise((complete) => { resolve = complete })
  return { promise, resolve }
}

const options = (contractId, title) => ({
  version: 7,
  contracts: [{ id: contractId, title }],
  amendments: [],
  documents: [],
  proposal_documents: [],
})
const replyContext = {
  id: '2f4d8f67-1b1f-46e2-9c60-42c5f6583334',
  captured_version: 7,
  destination: { ticket_version: 5 },
  prompt: 'Prepare a contractual answer.',
  template: {
    schema_version: 2,
    context_id: '2f4d8f67-1b1f-46e2-9c60-42c5f6583334',
    classifications: [],
    source_references: [],
  },
}
const preview = {
  valid: true,
  response_text: 'La solicitud está dentro del alcance.',
  classifications: [{ request: 'Validar inventario', classification: 'inside_scope' }],
  source_references: [],
}

function action(wrapper, label) {
  return wrapper.findAllComponents(BaseButton).find((button) => button.text() === label)
}

function mountReply(props = {}) {
  return mount(IssueContractReply, {
    props: {
      projectId: 4,
      kind: 'bug',
      contractId: 21,
      message: 'La pantalla muestra un error.',
      ticket: { id: 12, version: 5, origin_context: {} },
      ...props,
    },
    global: {
      components: { BaseAlert, BaseButton, BaseCheckbox, BaseSelect, BaseTextarea },
      stubs: {
        DeliveryPromptSources: true,
        NuxtLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('IssueContractReply', () => {
  let api
  let cryptoDescriptor

  beforeEach(() => {
    setActivePinia(createPinia())
    api = { get: jest.fn(), post: jest.fn() }
    usePlatformApi.mockReturnValue(api)
    global.useI18n = () => ({ t: (key) => key })
    cryptoDescriptor = Object.getOwnPropertyDescriptor(global, 'crypto')
    Object.defineProperty(global, 'crypto', {
      configurable: true,
      value: { randomUUID: jest.fn(() => 'd9e952ae-7100-4be1-a8d3-6ce2bc3bd0a3') },
    })
  })

  afterEach(() => {
    if (cryptoDescriptor) Object.defineProperty(global, 'crypto', cryptoDescriptor)
    else delete global.crypto
    delete global.useI18n
    jest.restoreAllMocks()
  })

  it('requires a fresh human review after preview text or JSON changes', async () => {
    // Falla si una revisión humana anterior autoriza contenido que luego cambió.
    api.get.mockResolvedValue({ data: options(21, 'Contrato de inventario') })
    api.post
      .mockResolvedValueOnce({ data: replyContext })
      .mockResolvedValueOnce({ data: preview })
      .mockResolvedValueOnce({ data: preview })
    const wrapper = mountReply()
    await flushPromises()

    await action(wrapper, 'platformIssues.reply.prepare').trigger('click')
    await flushPromises()
    await action(wrapper, 'platformIssues.reply.preview').trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenNthCalledWith(1, 'projects/4/issue-reports/bug/12/reply/contexts/', expect.objectContaining({
      expected_version: 7,
      expected_ticket_version: 5,
      contract_id: 21,
      request_id: 'd9e952ae-7100-4be1-a8d3-6ce2bc3bd0a3',
    }))
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual({
      context_id: replyContext.id,
      expected_version: 7,
      expected_ticket_version: 5,
      classifications: preview.classifications,
      source_references: [],
      human_reviewed: false,
    })

    await wrapper.get('[data-testid="issue-reply-human-reviewed"]').get('input').setValue(true)
    expect(wrapper.emitted('update:modelValue').at(-1)[0].human_reviewed).toBe(true)

    await wrapper.get('[data-testid="issue-reply-json"]').setValue(JSON.stringify({
      ...replyContext.template,
      response_text: 'Texto revisado después de la primera confirmación.',
    }))
    await flushPromises()
    expect(wrapper.emitted('update:modelValue').at(-1)[0].human_reviewed).toBe(false)

    await action(wrapper, 'platformIssues.reply.preview').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="issue-reply-human-reviewed"]').get('input').setValue(true)
    await wrapper.setProps({ message: 'Texto final editado por el equipo.' })
    await flushPromises()

    expect(wrapper.emitted('update:modelValue').at(-1)[0].human_reviewed).toBe(false)
  })

  it('ignores late options from the previous ticket and contract', async () => {
    // Falla si cambiar de ticket deja disponible el contrato de la respuesta HTTP anterior.
    const oldOptions = deferred()
    const currentOptions = deferred()
    api.get
      .mockImplementationOnce(() => oldOptions.promise)
      .mockImplementationOnce(() => currentOptions.promise)
    const wrapper = mountReply()

    await wrapper.setProps({
      ticket: { id: 13, version: 6, origin_context: {} },
      contractId: 22,
    })
    currentOptions.resolve({ data: options(22, 'Contrato vigente') })
    await flushPromises()
    oldOptions.resolve({ data: options(21, 'Contrato anterior') })
    await flushPromises()

    expect(api.get).toHaveBeenNthCalledWith(2, 'projects/4/issue-reports/bug/13/reply/options/', {})
    expect(wrapper.get('[data-testid="issue-contract-reply"]').text()).toContain('Contrato vigente')
    expect(wrapper.get('[data-testid="issue-contract-reply"]').text()).not.toContain('Contrato anterior')
  })
})
