import { usePlatformFeaturesStore } from '~/stores/platform-features'

import { usePlatformAuthStore } from '~/stores/platform-auth'

export default defineNuxtRouteMiddleware(async (to) => {
  // Strip optional i18n locale prefix (e.g. /en-us, /es-co) for path matching
  const rawPath = to.path.replace(/^\/[a-z]{2}(-[a-z]{2})?(?=\/)/, '')

  if (!rawPath.startsWith('/platform')) return

  // Extract locale prefix from the current path for redirects
  const localeMatch = to.path.match(/^\/([a-z]{2}(-[a-z]{2})?)(?=\/)/)
  const prefix = localeMatch ? `/${localeMatch[1]}` : ''
  const lp = (path) => `${prefix}${path}`

  const authStore = usePlatformAuthStore()
  authStore.hydrate()
  const landing = async () => {
    if (!authStore.isClient) return '/platform/dashboard'
    const features = usePlatformFeaturesStore()
    if (!await features.refresh()) return '/platform/projects'
    return features.enabled('platform.documents') ? '/platform/documents' : '/platform/projects'
  }

  const isLoginPage = rawPath === '/platform/login'
  const isVerifyPage = rawPath === '/platform/verify'
  const isCompleteProfilePage = rawPath === '/platform/complete-profile'
  const isPasswordResetPage =
    rawPath === '/platform/forgot-password'
    || rawPath === '/platform/verify-code'
    || rawPath === '/platform/reset-password'
  const redirectTarget = lp(`/platform/login?redirect=${encodeURIComponent(to.fullPath)}`)

  if (authStore.accessToken && !authStore.hasValidatedSession) {
    const result = await authStore.fetchMe()
    if (!result.success) {
      authStore.logout()
      if (!isLoginPage && !isVerifyPage && !isPasswordResetPage) {
        return navigateTo(redirectTarget)
      }
    }
  }

  // Password-recovery pages are public (no auth check, no redirect to login).
  if (isPasswordResetPage) {
    return
  }

  if (isLoginPage) {
    if (authStore.isAuthenticated && authStore.isOnboarded) {
      if (authStore.needsProfileCompletion) {
        return navigateTo(lp('/platform/complete-profile'))
      }
      return navigateTo(lp(await landing()))
    }

    if (authStore.hasVerificationToken && !authStore.isOnboarded) {
      return navigateTo(lp('/platform/verify'))
    }

    return
  }

  if (isVerifyPage) {
    if (authStore.isAuthenticated && authStore.isOnboarded) {
      if (authStore.needsProfileCompletion) {
        return navigateTo(lp('/platform/complete-profile'))
      }
      return navigateTo(lp(await landing()))
    }

    if (!authStore.hasVerificationToken && !authStore.isAuthenticated) {
      return navigateTo(lp('/platform/login'))
    }

    return
  }

  if (!authStore.accessToken) {
    return navigateTo(redirectTarget)
  }

  if (!authStore.isOnboarded) {
    return navigateTo(lp('/platform/verify'))
  }

  if (isCompleteProfilePage) {
    if (authStore.profileCompleted) {
      return navigateTo(lp('/platform/dashboard'))
    }
    return
  }

  if (authStore.needsProfileCompletion) {
    return navigateTo(lp('/platform/complete-profile'))
  }

  if (authStore.isClient && rawPath !== '/platform/unavailable') {
    const features = usePlatformFeaturesStore()
    const loaded = await features.refresh()
    if (!loaded && !features.routeAllowed(rawPath)) return navigateTo(lp('/platform/unavailable?reason=load'))
    if (!features.routeAllowed(rawPath)) return navigateTo(lp('/platform/unavailable'))
  }

  if (to.meta.platformRole === 'admin' && authStore.role !== 'admin') {
    return navigateTo(lp('/platform/dashboard'))
  }

  if (to.meta.platformRole === 'client' && authStore.role !== 'client') {
    return navigateTo(lp('/platform/dashboard'))
  }
})
