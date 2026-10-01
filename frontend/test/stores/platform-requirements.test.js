import { setActivePinia, createPinia } from 'pinia'
import { usePlatformRequirementsStore } from '../../stores/platform-requirements'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const { usePlatformApi } = require('../../composables/usePlatformApi')
const createRequirement = (overrides = {}) => ({ id: 8, stage_id: 4, stage_title: 'Client review', phase_id: 3, phase_title: 'Delivery phase', title: 'Test invoices', review_status: 'in_review', ...overrides })

describe('Requirement selector', () => {
  let api
  beforeEach(() => {
    setActivePinia(createPinia())
    api = { get: jest.fn() }
    usePlatformApi.mockReturnValue(api)
  })
  afterEach(() => jest.restoreAllMocks())

  it('provides stage information to bug selection', async () => {
    api.get.mockResolvedValue({ data: [createRequirement()] })
    const store = usePlatformRequirementsStore()
    const result = await store.fetchProjectRequirements(7)
    expect(result.data[0].stage_title).toBe('Client review')
    expect(store.requirements).toEqual(result.data)
  })

  it('preserves a visible error when the project is unavailable', async () => {
    api.get.mockRejectedValue({ response: { data: { detail: 'Project unavailable' } } })
    const result = await usePlatformRequirementsStore().fetchProjectRequirements(7)
    expect(result).toEqual({ success: false, message: 'Project unavailable' })
  })
})
