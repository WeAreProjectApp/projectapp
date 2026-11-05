import { createPinia, setActivePinia } from 'pinia'
import { useDataIntegrityStore } from '../../stores/data_integrity'
import { get_request } from '../../stores/services/request_http'

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  post_request: jest.fn(),
}))

describe('useDataIntegrityStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useDataIntegrityStore()
    jest.clearAllMocks()
  })

  it('loadFindings retains the paginated API result', async () => {
    const findings = {
      results: [{ id: 14, rule_code: 'DC9', status: 'open' }],
      count: 1,
      page: 2,
      pages: 3,
    }
    get_request.mockResolvedValueOnce({ data: findings })

    await store.loadFindings({ status: 'open', page: 2 })

    // Fails if the list drops pagination or the finding returned by the integrity API.
    expect(get_request).toHaveBeenCalledWith('data-integrity/findings/?status=open&page=2')
    expect(store.findings).toEqual(findings)
  })

  it('loadHistory stores operations with their review records', async () => {
    const operations = { results: [{ id: 4, action: 'move_document' }], count: 1 }
    const reviews = { results: [{ id: 9, finding_id: 14, decision: 'accepted' }] }
    get_request
      .mockResolvedValueOnce({ data: operations })
      .mockResolvedValueOnce({ data: reviews })

    await store.loadHistory(3)

    // Fails if the history page loses either audited corrections or accepted findings.
    expect(get_request).toHaveBeenNthCalledWith(1, 'data-integrity/operations/?page=3')
    expect(get_request).toHaveBeenNthCalledWith(2, 'data-integrity/reviews/')
    expect(store.operations).toEqual(operations)
    expect(store.reviews).toEqual([{ id: 9, finding_id: 14, decision: 'accepted' }])
  })
})
