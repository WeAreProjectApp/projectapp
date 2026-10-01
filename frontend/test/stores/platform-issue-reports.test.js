import { createPinia, setActivePinia } from 'pinia'
import { usePlatformIssueReportsStore } from '../../stores/platform-issue-reports'
import { usePlatformBugReportsStore } from '../../stores/platform-bug-reports'
import { usePlatformApi } from '../../composables/usePlatformApi'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const ticket = (overrides = {}) => ({ id: 12, status: 'resolved', version: 3, admin_response: 'Fixed', comments: [], ...overrides })
let get, post
beforeEach(() => {
  setActivePinia(createPinia())
  get = jest.fn()
  post = jest.fn()
  usePlatformApi.mockReturnValue({ get, post })
})
afterEach(() => jest.restoreAllMocks())

describe('Issue reports store', () => {
  it('loads options for the selected ticket context', async () => {
    get.mockResolvedValue({ data: { requirements: [], contracts: [], documents: [] } })
    const store = usePlatformIssueReportsStore()
    await store.contextOptions(4, { kind: 'bug', ticket_id: 12 })
    expect(get).toHaveBeenCalledWith('projects/4/issue-reports/context-options/', { params: { kind: 'bug', ticket_id: 12 } })
  })

  it('reports unavailable ticket options', async () => {
    get.mockRejectedValue({ response: { status: 404, data: { detail: 'Ticket not found.' } } })
    const result = await usePlatformIssueReportsStore().contextOptions(4, { kind: 'bug', ticket_id: 12 })
    expect(result).toEqual({ success: false, message: 'Ticket not found.' })
  })

  it('refreshes the reopened ticket in the list', async () => {
    const store = usePlatformBugReportsStore()
    store.bugReports = [ticket()]
    post.mockResolvedValue({ data: { content: 'Still fails' } })
    get.mockResolvedValue({ data: ticket({ status: 'reported', version: 4 }) })
    await store.reopenBugReport(4, 12, { content: 'Still fails', expected_version: 3 })
    expect(store.bugReports[0].status).toBe('reported')
    expect(store.currentBugReport.admin_response).toBe('Fixed')
  })

  it('keeps the resolved ticket on a reopen conflict', async () => {
    const store = usePlatformBugReportsStore()
    store.bugReports = [ticket()]
    post.mockRejectedValue({ response: { status: 409, data: { detail: 'Refresh the ticket.' } } })
    const result = await store.reopenBugReport(4, 12, { content: 'Still fails', expected_version: 3 })
    expect(store.bugReports[0].status).toBe('resolved')
    expect(result.message).toBe('Refresh the ticket.')
    expect(store.isUpdating).toBe(false)
  })
})
