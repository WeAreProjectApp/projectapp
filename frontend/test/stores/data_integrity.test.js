import { createPinia, setActivePinia } from 'pinia'
import { useDataIntegrityStore } from '../../stores/data_integrity'

jest.mock('axios', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
}))

import axios from 'axios'

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
    axios.get.mockResolvedValueOnce({ data: findings })

    await store.loadFindings({ status: 'open', page: 2 })

    // Fails if the list drops pagination or the finding returned by the integrity API.
    expect(axios.get).toHaveBeenCalledWith(
      '/api/data-integrity/findings/?status=open&page=2',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    )
    expect(store.findings).toEqual(findings)
  })

  it('loadHistory stores operations with their review records', async () => {
    const operations = { results: [{ id: 4, action: 'move_document' }], count: 1 }
    const reviews = { results: [{ id: 9, finding_id: 14, decision: 'accepted' }] }
    axios.get
      .mockResolvedValueOnce({ data: operations })
      .mockResolvedValueOnce({ data: reviews })

    await store.loadHistory(3)

    // Fails if the history page loses either audited corrections or accepted findings.
    expect(axios.get).toHaveBeenNthCalledWith(
      1,
      '/api/data-integrity/operations/?page=3',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    )
    expect(axios.get).toHaveBeenNthCalledWith(
      2,
      '/api/data-integrity/reviews/',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    )
    expect(store.operations).toEqual(operations)
    expect(store.reviews).toEqual([{ id: 9, finding_id: 14, decision: 'accepted' }])
  })

  it('startScan returns the persisted scan', async () => {
    const payload = { scope: { kind: 'project', id: 12 }, request_id: 'project-12-scan' }
    const scan = { id: 27, status: 'queued', scope: { kind: 'project', id: 12 } }
    axios.post.mockResolvedValueOnce({ data: scan })

    const result = await store.startScan(payload)

    // Fails if starting a scan posts to another resource or loses the selected scope.
    expect(axios.post).toHaveBeenCalledWith(
      '/api/data-integrity/scans/',
      payload,
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    )
    expect(result).toEqual(scan)
  })
})
