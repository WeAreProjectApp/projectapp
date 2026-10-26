/**
 * Tests for the global panel dashboard store.
 */
import { setActivePinia, createPinia } from 'pinia'
import { usePanelDashboardStore } from '../../stores/panel_dashboard'

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
}))

const { get_request } = require('../../stores/services/request_http')

const SUMMARY = {
  generated_at: '2026-07-16T10:00:00-05:00',
  finance: { year: 2026, liquid_total: 1000 },
  proposals: { pipeline_value: 500, by_status: { sent: 1 } },
  additional_modules: {
    active_module_count: 23,
    active_share_count: 4,
    unopened_active_share_count: 2,
    last_viewed_at: '2026-07-16T10:00:00-05:00',
  },
  operations: { tasks: { open: 2, overdue: 1 } },
  attention: [{ type: 'tasks_overdue', severity: 'warning', count: 1, meta: {} }],
}

describe('usePanelDashboardStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePanelDashboardStore()
    jest.clearAllMocks()
    jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('starts empty with derived getters at rest', () => {
    expect(store.summary).toBeNull()
    expect(store.finance).toBeNull()
    expect(store.proposals).toBeNull()
    expect(store.additionalModules).toBeNull()
    expect(store.operations).toBeNull()
    expect(store.attention).toEqual([])
    expect(store.hasFinance).toBe(false)
  })

  it('fetchSummary stores the payload on success', async () => {
    get_request.mockResolvedValue({ data: SUMMARY })

    const result = await store.fetchSummary()

    expect(get_request).toHaveBeenCalledWith('panel/dashboard/')
    expect(result.success).toBe(true)
    expect(store.summary).toEqual(SUMMARY)
    expect(store.error).toBe(false)
    expect(store.loading).toBe(false)
  })

  it('fetchSummary exposes the finance getters on success', async () => {
    get_request.mockResolvedValue({ data: SUMMARY })

    await store.fetchSummary()

    expect(store.finance.year).toBe(2026)
    expect(store.additionalModules.active_module_count).toBe(23)
    expect(store.attention).toHaveLength(1)
    expect(store.hasFinance).toBe(true)
  })

  it('fetchSummary flags error and keeps summary null on failure', async () => {
    get_request.mockRejectedValue(new Error('boom'))

    const result = await store.fetchSummary()

    expect(result.success).toBe(false)
    expect(store.summary).toBeNull()
    expect(store.error).toBe(true)
    expect(store.loading).toBe(false)
  })

  it('hasFinance stays false when finance is null (staff user)', async () => {
    get_request.mockResolvedValue({ data: { ...SUMMARY, finance: null } })

    await store.fetchSummary()

    expect(store.hasFinance).toBe(false)
    expect(store.finance).toBeNull()
  })
})

describe('attention list totals', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    jest.clearAllMocks()
  })

  it('removes an alert whose condition is resolved', async () => {
    const store = usePanelDashboardStore()
    store.summary = { attention: [{ type: 'emails_failed', count: 2 }] }
    get_request.mockResolvedValueOnce({ data: { results: [], total: 0, page: 1, has_next: false } })

    await store.fetchAttentionPage('emails_failed')

    expect(store.attention).toEqual([])
    expect(store.attentionCount).toBe(0)
  })

  it('preserves a newer summary when an older page finishes', async () => {
    const store = usePanelDashboardStore()
    store.summary = { attention: [{ type: 'emails_failed', count: 2 }] }
    let finish
    get_request.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    const request = store.fetchAttentionPage('emails_failed')
    store.summary = { attention: [{ type: 'emails_failed', count: 4 }] }

    finish({ data: { total: 1, results: [] } })
    await request

    expect(store.attentionCount).toBe(4)
  })
})
