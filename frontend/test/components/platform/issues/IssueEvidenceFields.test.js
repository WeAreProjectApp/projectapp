import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import IssueEvidenceFields from '../../../../components/platform/issues/IssueEvidenceFields.vue'
import { usePlatformApi } from '../../../../composables/usePlatformApi'

jest.mock('../../../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))

function deferred() {
  let resolve
  const promise = new Promise((complete) => { resolve = complete })
  return { promise, resolve }
}

describe('IssueEvidenceFields', () => {
  let get

  beforeEach(() => {
    setActivePinia(createPinia())
    get = jest.fn()
    usePlatformApi.mockReturnValue({ get })
    global.useI18n = () => ({ t: (key) => key })
  })

  afterEach(() => {
    delete global.useI18n
    jest.restoreAllMocks()
  })

  it('keeps only the latest contract documents after an older request resolves late', async () => {
    // Falla si una respuesta atrasada vuelve a mostrar evidencia del contrato anterior.
    const previousRequest = deferred()
    const currentRequest = deferred()
    get
      .mockImplementationOnce(() => previousRequest.promise)
      .mockImplementationOnce(() => currentRequest.promise)

    const wrapper = mount(IssueEvidenceFields, {
      props: {
        admin: true,
        id: 'issue-evidence',
        projectId: 4,
        kind: 'bug',
        ticketId: 12,
        modelValue: { contract_id: 21, document_ids: [] },
      },
    })

    await wrapper.setProps({ modelValue: { contract_id: 22, document_ids: [] } })
    currentRequest.resolve({
      data: {
        contracts: [],
        documents: [{ id: 202, title: 'Documento del contrato vigente' }],
      },
    })
    await flushPromises()

    previousRequest.resolve({
      data: {
        contracts: [],
        documents: [{ id: 101, title: 'Documento del contrato anterior' }],
      },
    })
    await flushPromises()

    expect(get).toHaveBeenNthCalledWith(2, 'projects/4/issue-reports/context-options/', {
      params: { kind: 'bug', ticket_id: 12, contract_id: 22 },
    })
    expect(wrapper.text()).toContain('Documento del contrato vigente')
    expect(wrapper.text()).not.toContain('Documento del contrato anterior')
  })
})
