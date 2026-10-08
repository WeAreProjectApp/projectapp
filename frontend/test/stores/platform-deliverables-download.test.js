import { createPinia, setActivePinia } from 'pinia'
import { usePlatformDeliverablesStore } from '../../stores/platform-deliverables'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const { usePlatformApi } = require('../../composables/usePlatformApi')
const apiUrl = '/api/accounts/projects/7/deliverables/9/file/'

describe('Private Platform resource downloads', () => {
  let store
  let get
  let downloads
  let click
  let clickedLink
  let originalCreate
  let originalRevoke

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformDeliverablesStore()
    get = jest.fn()
    usePlatformApi.mockReturnValue({ get })
    downloads = []
    clickedLink = null
    originalCreate = URL.createObjectURL
    originalRevoke = URL.revokeObjectURL
    URL.createObjectURL = jest.fn().mockReturnValue('blob:retained-resource')
    URL.revokeObjectURL = jest.fn()
    click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      clickedLink = this
      downloads.push({ filename: this.download, url: this.href })
    })
  })
  afterEach(() => {
    click.mockRestore()
    URL.createObjectURL = originalCreate
    URL.revokeObjectURL = originalRevoke
    jest.useRealTimers()
    jest.clearAllMocks()
    document.body.innerHTML = ''
  })

  function availableFile(headers) {
    jest.useFakeTimers()
    const body = new Blob(['retained signed bytes'], { type: 'application/pdf' })
    get.mockResolvedValueOnce({ data: body, headers })
    return body
  }

  it('downloads the authenticated API body under a safe backend filename', async () => {
    const body = availableFile({ 'content-disposition': 'attachment; filename="signed/copy.pdf"' })

    const result = await store.downloadFile({ file_url: apiUrl, file_name: 'metadata.pdf' })

    expect(result).toEqual({ success: true })
    expect(get).toHaveBeenCalledWith(apiUrl, { responseType: 'blob', baseURL: '' })
    expect(URL.createObjectURL).toHaveBeenCalledWith(body)
    expect(downloads).toEqual([{ filename: 'signed-copy.pdf', url: 'blob:retained-resource' }])
    expect(clickedLink.isConnected).toBe(false)
    jest.runOnlyPendingTimers()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:retained-resource')
  })

  it('uses the extended UTF-8 filename declared by the backend', async () => {
    availableFile({ 'content-disposition': "attachment; filename=plain.pdf; filename*=UTF-8''otros%C3%AD%20firmado.pdf" })

    const result = await store.downloadFile({ file_url: apiUrl, file_name: 'metadata.pdf' })

    expect(result.success).toBe(true)
    expect(downloads[0].filename).toBe('otrosí firmado.pdf')
    jest.runOnlyPendingTimers()
  })

  it('preserves the resource filename when the response has no disposition', async () => {
    availableFile({})

    const result = await store.downloadFile({ file_url: apiUrl, file_name: 'original-guide.docx' })

    expect(result.success).toBe(true)
    expect(downloads[0].filename).toBe('original-guide.docx')
    jest.runOnlyPendingTimers()
  })

  it('names a resource without filename metadata', async () => {
    availableFile(undefined)

    const result = await store.downloadFile({ file_url: apiUrl })

    expect(result.success).toBe(true)
    expect(downloads[0].filename).toBe('resource')
    jest.runOnlyPendingTimers()
  })

  it('returns the permission explanation received as a JSON blob', async () => {
    const body = new Blob([JSON.stringify({ detail: 'No puedes descargar este archivo.' })], { type: 'application/json' })
    get.mockRejectedValueOnce({ response: { status: 403, data: body, headers: { 'content-type': 'application/json' } } })

    const result = await store.downloadFile({ file_url: apiUrl })

    expect(result).toEqual({ success: false, message: 'No puedes descargar este archivo.' })
    expect(downloads).toEqual([])
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  it('reports a lost connection without creating a download', async () => {
    get.mockRejectedValueOnce(new Error('Connection lost'))

    const result = await store.downloadFile({ file_url: apiUrl })

    expect(result).toEqual({ success: false, message: 'No pudimos descargar el archivo. Inténtalo de nuevo.' })
    expect(downloads).toEqual([])
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  it.each(['/media/private/contract.pdf', 'https://elsewhere.example.test/api/accounts/file/'])('rejects a download URL outside the Platform API: %s', async (file_url) => {
    const result = await store.downloadFile({ file_url })

    expect(result).toEqual({ success: false, message: 'El archivo no tiene una descarga disponible.' })
    expect(get).not.toHaveBeenCalled()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })
})
