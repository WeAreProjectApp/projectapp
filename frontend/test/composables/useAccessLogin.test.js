const mockGetRequest = jest.fn()
const mockCreateRequest = jest.fn()
const mockPlatformGet = jest.fn()
const mockPlatformPost = jest.fn()

jest.mock('../../stores/services/request_http', () => ({
  get_request: mockGetRequest,
  create_request: mockCreateRequest,
}))

jest.mock('../../composables/usePlatformApi', () => ({
  usePlatformApi: () => ({ get: mockPlatformGet, post: mockPlatformPost }),
}))

const { useAccessLogin } = require('../../composables/useAccessLogin')

describe('useAccessLogin', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('posts to the panel email endpoint with its CSRF token', async () => {
    // Falla si una superficie omite CSRF o llama una ruta de acceso que no existe.
    mockGetRequest.mockResolvedValueOnce({ data: { csrf_token: 'panel-csrf-token' } })
    mockCreateRequest.mockResolvedValueOnce({ data: { challenge_id: 'challenge-1' } })

    const access = useAccessLogin('panel')
    await access.config()
    await access.post('email-request', { email: 'ana@example.com' })

    expect(mockGetRequest).toHaveBeenCalledWith('auth/config/')
    expect(mockCreateRequest).toHaveBeenCalledWith(
      'auth/panel/email-request/',
      { email: 'ana@example.com' },
      { skipAuth: true, skipRefresh: true, headers: { 'X-CSRFToken': 'panel-csrf-token' } },
    )
  })

  it('posts to the platform email endpoint with its CSRF token', async () => {
    // Falla si una superficie omite CSRF o llama una ruta de acceso que no existe.
    mockPlatformGet.mockResolvedValueOnce({ data: { csrf_token: 'platform-csrf-token' } })
    mockPlatformPost.mockResolvedValueOnce({ data: { challenge_id: 'challenge-1' } })

    const access = useAccessLogin('platform')
    await access.config()
    await access.post('email-request', { email: 'ana@example.com' })

    expect(mockPlatformGet).toHaveBeenCalledWith(
      '/api/auth/config/',
      { skipAuth: true, skipRefresh: true, headers: { 'X-CSRFToken': '' } },
    )
    expect(mockPlatformPost).toHaveBeenCalledWith(
      '/api/auth/platform/email-request/',
      { email: 'ana@example.com' },
      { skipAuth: true, skipRefresh: true, headers: { 'X-CSRFToken': 'platform-csrf-token' } },
    )
  })
})
