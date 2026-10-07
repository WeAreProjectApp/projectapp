import { createPinia, setActivePinia } from 'pinia'
import { usePlatformDeliveryStore } from '../../stores/platform-delivery'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const { usePlatformApi } = require('../../composables/usePlatformApi')

describe('Confirmed delivery source downloads', () => {
  let store
  let api
  let oldCreate
  let oldRevoke
  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformDeliveryStore()
    store.projectId = 7
    api = { get: jest.fn() }
    usePlatformApi.mockReturnValue(api)
    oldCreate = URL.createObjectURL
    oldRevoke = URL.revokeObjectURL
    URL.createObjectURL = jest.fn().mockReturnValue('blob:private-source')
    URL.revokeObjectURL = jest.fn()
  })
  afterEach(() => {
    jest.restoreAllMocks()
    URL.createObjectURL = oldCreate
    URL.revokeObjectURL = oldRevoke
  })

  it('loads the confirmed package files offered by the project', async () => {
    const approvalFiles = [{ id: 12, title: 'Custom agreement', filename: 'agreement.docx' }]
    api.get.mockResolvedValue({ data: { approval_files: approvalFiles } })

    await store.fetchDocumentOptions()

    expect(store.approvalFileOptions).toEqual(approvalFiles)
  })

  it('clears package choices when leaving their project', async () => {
    store.approvalFileOptions = [{ id: 12, title: 'Private agreement' }]
    api.get.mockRejectedValue({ response: { status: 404, data: { detail: 'Project unavailable' } } })

    await store.fetchDelivery(8)

    expect(store.approvalFileOptions).toEqual([])
  })

  it('downloads the original file without changing it to PDF', async () => {
    const mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    api.get.mockResolvedValue({ data: new Blob(['original bytes'], { type: mimeType }), headers: { 'content-type': mimeType } })
    const downloads = []
    jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { downloads.push(this.download) })

    const result = await store.downloadContractSource({
      source_download_url: '/api/accounts/projects/7/delivery/contracts/3/source/',
      source_filename: 'agreement.docx', source_content_type: mimeType,
    })

    expect(result.success).toBe(true)
    expect(downloads).toEqual(['agreement.docx'])
    expect(api.get).toHaveBeenCalledWith('/api/accounts/projects/7/delivery/contracts/3/source/', { responseType: 'blob', baseURL: '' })
    expect(URL.createObjectURL.mock.calls[0][0].type).toBe(mimeType)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-source')
  })
})
