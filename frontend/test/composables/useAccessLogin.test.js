const mockGetRequest = jest.fn()
const mockCreateRequest = jest.fn()

jest.mock('../../stores/services/request_http', () => ({
  get_request: mockGetRequest,
  create_request: mockCreateRequest,
}))

jest.mock('axios', () => jest.requireActual('axios'))

function loadAccessLogin(adapter) {
  jest.resetModules()
  const axios = require('axios').default
  axios.defaults.adapter = adapter
  return require('../../composables/useAccessLogin').useAccessLogin
}

describe('useAccessLogin', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    jest.resetModules()
    localStorage.clear()
  })

  it('posts to the panel email endpoint with its CSRF token', async () => {
    // Falla si una superficie omite CSRF o llama una ruta de acceso que no existe.
    mockGetRequest.mockResolvedValueOnce({ data: { csrf_token: 'panel-csrf-token' } })
    mockCreateRequest.mockResolvedValueOnce({ data: { challenge_id: 'challenge-1' } })
    const useAccessLogin = loadAccessLogin(jest.fn())

    const access = useAccessLogin('panel')
    await access.config()
    const login = await access.post('email-request', { email: 'ana@example.com' })

    expect(mockGetRequest).toHaveBeenCalledWith('auth/config/')
    expect(mockCreateRequest).toHaveBeenCalledWith(
      'auth/panel/email-request/',
      { email: 'ana@example.com' },
      { skipAuth: true, skipRefresh: true, headers: { 'X-CSRFToken': 'panel-csrf-token' } },
    )
    expect(login).toEqual({ challenge_id: 'challenge-1' })
  })

  it('sends platform access requests outside the accounts base path', async () => {
    // quality: allow-call-contract (the HTTP destination is the composable's public contract)
    // Falla si Axios vuelve a prefijar estas rutas con /api/accounts/ o agrega una sesión de cliente.
    const requests = []
    let axios
    const adapter = jest.fn((config) => {
      requests.push({
        authorization: config.headers.get('Authorization'),
        csrf: config.headers.get('X-CSRFToken'),
        destination: axios.getUri(config),
        method: config.method,
      })
      return Promise.resolve({
        config,
        data: requests.length === 1
          ? { csrf_token: 'platform-csrf-token' }
          : { challenge_id: 'challenge-1' },
        headers: {},
        status: 200,
        statusText: 'OK',
      })
    })
    localStorage.setItem('platform_access_token', 'client-session-token')
    localStorage.setItem('platform_refresh_token', 'client-refresh-token')
    jest.resetModules()
    axios = require('axios').default
    axios.defaults.adapter = adapter
    const { useAccessLogin } = require('../../composables/useAccessLogin')

    const access = useAccessLogin('platform')
    await access.config()
    const login = await access.post('email-request', { email: 'ana@example.com' })

    expect(requests).toEqual([
      { authorization: undefined, csrf: '', destination: '/api/auth/config/', method: 'get' },
      {
        authorization: undefined,
        csrf: 'platform-csrf-token',
        destination: '/api/auth/platform/email-request/',
        method: 'post',
      },
    ])
    expect(adapter).toHaveBeenCalledTimes(2)
    expect(login).toEqual({ challenge_id: 'challenge-1' })
  })
})
