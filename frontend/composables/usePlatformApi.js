import axios from 'axios'

export const PLATFORM_STORAGE_KEYS = {
  accessToken: 'platform_access_token',
  refreshToken: 'platform_refresh_token',
  user: 'platform_user',
  verificationToken: 'platform_verification_token',
  pendingEmail: 'platform_pending_email',
}

let platformApiInstance = null
let hasPlatformInterceptors = false

function isClient() {
  return typeof window !== 'undefined'
}

function setOrRemoveStorageValue(key, value) {
  /* c8 ignore next */
  if (!isClient()) return
  if (value === undefined) return
  if (value === null || value === '') {
    localStorage.removeItem(key)
    return
  }
  localStorage.setItem(key, value)
}

function safeJsonParse(value) {
  if (!value) return null
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

export function readPlatformSession() {
  /* c8 ignore next 9 */
  if (!isClient()) {
    return {
      accessToken: '',
      refreshToken: '',
      user: null,
      verificationToken: '',
      pendingEmail: '',
    }
  }

  return {
    accessToken: localStorage.getItem(PLATFORM_STORAGE_KEYS.accessToken) || '',
    refreshToken: localStorage.getItem(PLATFORM_STORAGE_KEYS.refreshToken) || '',
    user: safeJsonParse(localStorage.getItem(PLATFORM_STORAGE_KEYS.user)),
    verificationToken: localStorage.getItem(PLATFORM_STORAGE_KEYS.verificationToken) || '',
    pendingEmail: localStorage.getItem(PLATFORM_STORAGE_KEYS.pendingEmail) || '',
  }
}

export function writePlatformSession(payload = {}) {
  if (!isClient()) return

  if ('accessToken' in payload) {
    setOrRemoveStorageValue(PLATFORM_STORAGE_KEYS.accessToken, payload.accessToken)
  }

  if ('refreshToken' in payload) {
    setOrRemoveStorageValue(PLATFORM_STORAGE_KEYS.refreshToken, payload.refreshToken)
  }

  if ('user' in payload) {
    setOrRemoveStorageValue(
      PLATFORM_STORAGE_KEYS.user,
      payload.user ? JSON.stringify(payload.user) : '',
    )
  }

  if ('verificationToken' in payload) {
    setOrRemoveStorageValue(PLATFORM_STORAGE_KEYS.verificationToken, payload.verificationToken)
  }

  if ('pendingEmail' in payload) {
    setOrRemoveStorageValue(PLATFORM_STORAGE_KEYS.pendingEmail, payload.pendingEmail)
  }
}

export function clearPlatformSession() {
  if (!isClient()) return
  Object.values(PLATFORM_STORAGE_KEYS).forEach((key) => localStorage.removeItem(key))
}

function redirectToPlatformLogin() {
  /* c8 ignore next */
  if (!isClient()) return

  const currentPath = `${window.location.pathname}${window.location.search}`
  const stripped = currentPath.replace(/^\/[a-z]{2}-[a-z]{2}/, '')
  if (stripped.startsWith('/platform/login') || stripped.startsWith('/platform/verify')) return

  const localeMatch = currentPath.match(/^\/([a-z]{2}-[a-z]{2})\//)
  const prefix = localeMatch ? `/${localeMatch[1]}` : ''
  window.location.href = `${prefix}/platform/login?redirect=${encodeURIComponent(currentPath)}`
}

async function refreshPlatformAccessToken() {
  const session = readPlatformSession()
  if (!session.refreshToken) {
    throw new Error('Refresh token no disponible.')
  }

  const response = await axios.post(
    '/api/accounts/token/refresh/',
    { refresh: session.refreshToken },
    {
      headers: {
        'Content-Type': 'application/json',
      },
      skipPlatformAuth: true,
      skipPlatformRefresh: true,
    },
  )

  const refreshedSession = {
    accessToken: response.data.access,
    refreshToken: response.data.refresh || session.refreshToken,
  }

  writePlatformSession(refreshedSession)

  return refreshedSession
}

function shouldAttemptRefresh(config = {}, status) {
  if (status !== 401 || config._platformRetry || config.skipPlatformRefresh) return false

  const requestUrl = `${config.baseURL || ''}${config.url || ''}`
  if (requestUrl.includes('login/')) return false
  if (requestUrl.includes('verify/')) return false
  if (requestUrl.includes('resend-code/')) return false
  if (requestUrl.includes('token/refresh/')) return false

  return true
}

function getPlatformApiInstance() {
  if (!platformApiInstance) {
    platformApiInstance = axios.create({
      baseURL: '/api/accounts/',
      headers: {
        'Content-Type': 'application/json',
      },
    })
  }

  if (!hasPlatformInterceptors) {
    platformApiInstance.interceptors.request.use((config) => {
      if (config.skipPlatformAuth) return config

      const hasAuthorizationHeader = config.headers?.Authorization || config.headers?.authorization
      if (hasAuthorizationHeader) return config

      const session = readPlatformSession()
      if (!session.accessToken) return config

      config.headers = {
        ...(config.headers || {}),
        Authorization: `Bearer ${session.accessToken}`,
      }

      return config
    })

    platformApiInstance.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.data?.code === 'feature_disabled') {
          const { usePlatformFeaturesStore } = await import('~/stores/platform-features')
          usePlatformFeaturesStore().markDisabled(error.response.data.feature)
        }
        const originalRequest = error.config || {}
        const responseStatus = error.response?.status

        if (!shouldAttemptRefresh(originalRequest, responseStatus)) {
          throw error
        }

        const session = readPlatformSession()
        if (!session.refreshToken) {
          clearPlatformSession()
          redirectToPlatformLogin()
          throw error
        }

        originalRequest._platformRetry = true

        try {
          const refreshedSession = await refreshPlatformAccessToken()
          originalRequest.headers = {
            ...(originalRequest.headers || {}),
            Authorization: `Bearer ${refreshedSession.accessToken}`,
          }
          return platformApiInstance(originalRequest)
        } catch (refreshError) {
          clearPlatformSession()
          redirectToPlatformLogin()
          throw refreshError
        }
      },
    )

    hasPlatformInterceptors = true
  }

  return platformApiInstance
}

export function usePlatformApi() {
  const api = getPlatformApiInstance()

  const request = ({
    url,
    method = 'GET',
    data,
    params,
    token,
    headers: extraHeaders,
    skipAuth = false,
    skipRefresh = false,
    ...axiosConfig
  }) => {
    const headers = { ...(extraHeaders || {}) }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
    return api.request({
      url,
      method,
      data,
      params,
      skipPlatformAuth: skipAuth,
      skipPlatformRefresh: skipRefresh,
      headers: Object.keys(headers).length ? headers : undefined,
      ...axiosConfig,
    })
  }

  return {
    request,
    get: (url, config = {}) => request({ url, method: 'GET', ...config }),
    post: (url, data, config = {}) => request({ url, method: 'POST', data, ...config }),
    patch: (url, data, config = {}) => request({ url, method: 'PATCH', data, ...config }),
    put: (url, data, config = {}) => request({ url, method: 'PUT', data, ...config }),
    delete: (url, config = {}) => request({ url, method: 'DELETE', ...config }),
    refreshPlatformAccessToken,
  }
}
