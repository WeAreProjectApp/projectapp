jest.mock('~/stores/platform-features', () => ({ usePlatformFeaturesStore: () => ({ refresh: async () => true, routeAllowed: () => true, enabled: () => true }) }))
/**
 * Tests for the platform-auth route middleware — role-aware landing.
 *
 * The changeset routes authenticated clients to the document portal
 * (/platform/documents) from the login and verify pages, while admins keep
 * landing on the dashboard. Nuxt auto-imports (defineNuxtRouteMiddleware,
 * navigateTo) are stubbed as globals, mirroring the composable tests.
 */
global.defineNuxtRouteMiddleware = (fn) => fn
global.navigateTo = jest.fn((path) => path)

const mockAuth = {
  hydrate: jest.fn(),
  fetchMe: jest.fn(),
  logout: jest.fn(),
  accessToken: 'tok',
  hasValidatedSession: true,
  isAuthenticated: true,
  isOnboarded: true,
  needsProfileCompletion: false,
  profileCompleted: true,
  hasVerificationToken: false,
  role: 'client',
  isClient: true,
}
jest.mock('~/stores/platform-auth', () => ({
  usePlatformAuthStore: () => mockAuth,
}))

const middleware = require('../../middleware/platform-auth').default

describe('platform-auth middleware — role-aware landing', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    Object.assign(mockAuth, {
      hasValidatedSession: true,
      isAuthenticated: true,
      isOnboarded: true,
      needsProfileCompletion: false,
      isClient: true,
      role: 'client',
    })
  })

  it('sends an authenticated client from the login page to the documents portal', async () => {
    mockAuth.isClient = true
    await middleware({ path: '/platform/login', fullPath: '/platform/login' })
    expect(global.navigateTo).toHaveBeenCalledWith('/platform/documents')
  })

  it('sends an authenticated admin from the login page to the dashboard', async () => {
    mockAuth.isClient = false
    mockAuth.role = 'admin'
    await middleware({ path: '/platform/login', fullPath: '/platform/login' })
    expect(global.navigateTo).toHaveBeenCalledWith('/platform/dashboard')
  })

  it('sends a verified client to the documents portal preserving the locale prefix', async () => {
    mockAuth.isClient = true
    await middleware({ path: '/es-co/platform/verify', fullPath: '/es-co/platform/verify' })
    expect(global.navigateTo).toHaveBeenCalledWith('/es-co/platform/documents')
  })
})
