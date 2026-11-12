import { usePlatformFeaturesStore } from '~/stores/platform-features'
import { defineStore } from 'pinia'
import {
  clearPlatformSession,
  readPlatformSession,
  usePlatformApi,
  writePlatformSession,
} from '~/composables/usePlatformApi'

function initialState() {
  return {
    user: null,
    accessToken: '',
    refreshToken: '',
    verificationToken: '',
    pendingEmail: '',
    isAuthenticated: false,
    role: '',
    isOnboarded: false,
    profileCompleted: false,
    isLoading: false,
    isVerifying: false,
    error: '',
    hasHydrated: false,
    hasValidatedSession: false,
    passwordReset: {
      email: null,
      requestToken: null,
      verifiedToken: null,
    },
  }
}

export const usePlatformAuthStore = defineStore('platformAuth', {
  state: () => initialState(),

  getters: {
    isAdmin: (state) => state.role === 'admin',
    isClient: (state) => state.role === 'client',
    displayName: (state) => {
      if (!state.user) return 'ProjectApp'
      const fullName = [state.user.first_name, state.user.last_name].filter(Boolean).join(' ').trim()
      return fullName || state.user.email || 'ProjectApp'
    },
    userInitials: (state) => {
      if (!state.user) return 'PA'
      const source = [state.user.first_name, state.user.last_name].filter(Boolean).join(' ').trim() || state.user.email || 'PA'
      return source
        .split(/\s+/)
        .slice(0, 2)
        /* c8 ignore next */
        .map((part) => part[0]?.toUpperCase() || '')
        .join('')
    },
    hasVerificationToken: (state) => Boolean(state.verificationToken),
    needsProfileCompletion: (state) => state.isOnboarded && !state.profileCompleted,
  },

  actions: {
    hydrate() {
      if (this.hasHydrated) return
      /* c8 ignore next */
      if (typeof window === 'undefined') return

      const session = readPlatformSession()
      this.accessToken = session.accessToken
      this.refreshToken = session.refreshToken
      this.verificationToken = session.verificationToken
      this.pendingEmail = session.pendingEmail
      this.user = session.user
      this.isAuthenticated = Boolean(session.accessToken)
      this.role = session.user?.role || ''
      this.isOnboarded = Boolean(session.user?.is_onboarded)
      this.profileCompleted = Boolean(session.user?.profile_completed)
      this.hasHydrated = true
      this.hasValidatedSession = false
    },

    resetState() {
      Object.assign(this, initialState(), { hasHydrated: true })
    },

    applyAuthenticatedSession(tokens, user) {
      this.user = user
      this.accessToken = tokens.access
      this.refreshToken = tokens.refresh
      this.verificationToken = ''
      this.pendingEmail = ''
      this.isAuthenticated = true
      this.role = user?.role || ''
      this.isOnboarded = Boolean(user?.is_onboarded)
      this.profileCompleted = Boolean(user?.profile_completed)
      this.error = ''
      this.hasValidatedSession = true
      writePlatformSession({
        accessToken: tokens.access,
        refreshToken: tokens.refresh,
        user,
        verificationToken: '',
        pendingEmail: '',
      })
    },

    applyVerificationState(verificationToken, pendingEmail) {
      this.user = null
      this.accessToken = ''
      this.refreshToken = ''
      this.isAuthenticated = false
      this.role = ''
      this.isOnboarded = false
      this.verificationToken = verificationToken
      this.pendingEmail = pendingEmail || ''
      this.error = ''
      this.hasValidatedSession = false
      writePlatformSession({
        accessToken: '',
        refreshToken: '',
        user: null,
        verificationToken,
        pendingEmail: pendingEmail || '',
      })
    },

    clearVerificationState() {
      this.verificationToken = ''
      this.pendingEmail = ''
      writePlatformSession({ verificationToken: '', pendingEmail: '' })
    },

    clearAuthenticatedSession() {
      this.user = null
      this.accessToken = ''
      this.refreshToken = ''
      this.isAuthenticated = false
      this.role = ''
      this.isOnboarded = false
      this.hasValidatedSession = false
      writePlatformSession({
        accessToken: '',
        refreshToken: '',
        user: null,
      })
    },

    startPasswordReset({ email, requestToken }) {
      this.passwordReset = {
        email: email || null,
        requestToken: requestToken || null,
        verifiedToken: null,
      }
    },

    markCodeVerified({ verifiedToken }) {
      this.passwordReset = {
        ...this.passwordReset,
        verifiedToken: verifiedToken || null,
      }
    },

    clearPasswordReset() {
      this.passwordReset = {
        email: null,
        requestToken: null,
        verifiedToken: null,
      }
    },

    async requestPasswordReset({ email }) {
      const trimmed = (email || '').trim().toLowerCase()
      if (!trimmed) {
        this.error = 'Ingresa tu email.'
        return { success: false, message: this.error }
      }
      this.isLoading = true
      this.error = ''
      try {
        const { post } = usePlatformApi()
        const response = await post(
          'password-reset/request/',
          { email: trimmed },
          { skipAuth: true, skipRefresh: true },
        )
        this.startPasswordReset({
          email: trimmed,
          requestToken: response.data.reset_request_token,
        })
        return { success: true }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos iniciar el flujo de recuperación.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async verifyResetCode({ code }) {
      const value = `${code || ''}`.trim()
      if (!this.passwordReset.requestToken) {
        return { success: false, message: 'Empieza desde la página inicial de recuperación.' }
      }
      if (!/^\d{6}$/.test(value)) {
        this.error = 'Ingresa un código válido de 6 dígitos.'
        return { success: false, message: this.error }
      }
      this.isVerifying = true
      this.error = ''
      try {
        const { post } = usePlatformApi()
        const response = await post(
          'password-reset/verify-code/',
          { reset_request_token: this.passwordReset.requestToken, code: value },
          { skipAuth: true, skipRefresh: true },
        )
        this.markCodeVerified({ verifiedToken: response.data.reset_verified_token })
        return { success: true }
      } catch (error) {
        const data = error.response?.data || {}
        const message = data.detail || 'No pudimos verificar el código.'
        this.error = message
        return {
          success: false,
          message,
          code: data.detail,
          attemptsLeft: data.attempts_left,
        }
      /* c8 ignore next 3 */
      } finally {
        this.isVerifying = false
      }
    },

    async confirmPasswordReset({ newPassword }) {
      const value = newPassword || ''
      if (!this.passwordReset.verifiedToken) {
        return { success: false, message: 'Completa primero la verificación del código.' }
      }
      if (value.length < 8) {
        this.error = 'La contraseña debe tener al menos 8 caracteres.'
        return { success: false, message: this.error }
      }
      this.isLoading = true
      this.error = ''
      try {
        const { post } = usePlatformApi()
        const response = await post(
          'password-reset/confirm/',
          { reset_verified_token: this.passwordReset.verifiedToken, new_password: value },
          { skipAuth: true, skipRefresh: true },
        )
        const tokens = { access: response.data.access, refresh: response.data.refresh }
        this.applyAuthenticatedSession(tokens, response.data.user)
        this.clearPasswordReset()
        return { success: true, user: response.data.user }
      } catch (error) {
        const data = error.response?.data || {}
        const message = data.detail || 'No pudimos restablecer la contraseña.'
        this.error = message
        return {
          success: false,
          message,
          code: data.detail,
          errors: data.errors,
        }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async login(payload) {
      const email = (payload?.email || '').trim().toLowerCase()
      const password = payload?.password || ''

      if (!email || !password) {
        this.error = 'Ingresa tu email y contraseña.'
        return { success: false, message: this.error }
      }

      this.isLoading = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const body = { email, password }
        if (payload.recaptcha_token) {
          body.recaptcha_token = payload.recaptcha_token
        }
        const response = await post(
          'login/',
          body,
          { skipAuth: true, skipRefresh: true },
        )

        if (response.data.requires_verification) {
          this.applyVerificationState(response.data.verification_token, response.data.email)
          return {
            success: true,
            requiresVerification: true,
            email: response.data.email,
          }
        }

        this.applyAuthenticatedSession(response.data.tokens, response.data.user)
        return {
          success: true,
          requiresVerification: false,
          user: response.data.user,
        }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos iniciar sesión en este momento.'
        this.error = message
        return { success: false, message, code: error.response?.data?.code }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async verify(payload) {
      const code = `${payload?.code || ''}`.trim()
      const newPassword = payload?.newPassword || ''

      if (!this.verificationToken) {
        this.error = 'No encontramos una sesión de verificación activa.'
        return { success: false, message: this.error }
      }

      if (!/^\d{6}$/.test(code)) {
        this.error = 'Ingresa un código válido de 6 dígitos.'
        return { success: false, message: this.error }
      }

      if (newPassword.length < 8) {
        this.error = 'La contraseña debe tener al menos 8 caracteres.'
        return { success: false, message: this.error }
      }

      this.isVerifying = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const response = await post(
          'verify/',
          { code, new_password: newPassword },
          {
            token: this.verificationToken,
            skipAuth: true,
            skipRefresh: true,
          },
        )

        this.applyAuthenticatedSession(response.data.tokens, response.data.user)
        return { success: true, user: response.data.user }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos completar la verificación.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isVerifying = false
      }
    },

    async resendCode() {
      if (!this.verificationToken) {
        this.error = 'No encontramos una sesión de verificación activa.'
        return { success: false, message: this.error }
      }

      this.isVerifying = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const response = await post(
          'resend-code/',
          {},
          {
            token: this.verificationToken,
            skipAuth: true,
            skipRefresh: true,
          },
        )

        return { success: true, message: response.data.detail || 'Código reenviado.' }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos reenviar el código.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isVerifying = false
      }
    },

    async exchangeImpersonationCode(code) {
      if (!code) {
        return { success: false, message: 'Código de acceso ausente.' }
      }
      try {
        const { post } = usePlatformApi()
        const response = await post(
          'impersonation/exchange/',
          { code },
          { skipAuth: true, skipRefresh: true },
        )
        this.applyAuthenticatedSession(
          { access: response.data.access, refresh: response.data.refresh },
          null,
        )
        return { success: true }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos iniciar la sesión.'
        this.error = message
        return { success: false, message }
      }
    },

    async fetchMe() {
      if (!this.accessToken) {
        return { success: false, message: 'No hay sesión activa.' }
      }

      this.isLoading = true
      this.error = ''

      try {
        const { get } = usePlatformApi()
        const response = await get('me/')
        this.user = response.data
        this.role = response.data.role || ''
        this.isOnboarded = Boolean(response.data.is_onboarded)
        this.profileCompleted = Boolean(response.data.profile_completed)
        this.isAuthenticated = true
        this.hasValidatedSession = true
        writePlatformSession({ user: response.data })
        return { success: true, user: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos cargar tu perfil.'
        this.error = message
        this.clearAuthenticatedSession()
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async updateProfile(payload) {
      this.isLoading = true
      this.error = ''

      try {
        const { patch } = usePlatformApi()
        const response = await patch('me/', payload)
        this.user = response.data
        this.role = response.data.role || this.role
        this.isOnboarded = Boolean(response.data.is_onboarded)
        this.profileCompleted = Boolean(response.data.profile_completed)
        writePlatformSession({ user: response.data })
        return { success: true, user: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos actualizar tu perfil.'
        this.error = message
        return { success: false, message, errors: error.response?.data }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async uploadAvatar(file) {
      this.isLoading = true
      this.error = ''

      try {
        const formData = new FormData()
        formData.append('avatar', file)
        const { request } = usePlatformApi()
        const response = await request({
          url: 'me/',
          method: 'PATCH',
          data: formData,
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        this.user = response.data
        writePlatformSession({ user: response.data })
        return { success: true, user: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos actualizar tu avatar.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async completeProfile(formData) {
      this.isLoading = true
      this.error = ''

      try {
        const { request } = usePlatformApi()
        const response = await request({
          url: 'me/complete-profile/',
          method: 'POST',
          data: formData,
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        this.user = response.data
        this.role = response.data.role || this.role
        this.isOnboarded = Boolean(response.data.is_onboarded)
        this.profileCompleted = Boolean(response.data.profile_completed)
        writePlatformSession({ user: response.data })
        return { success: true, user: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos completar tu perfil.'
        this.error = message
        return { success: false, message, errors: error.response?.data }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async refreshTokenAction() {
      if (!this.refreshToken) {
        return { success: false, message: 'No hay refresh token disponible.' }
      }

      try {
        const { refreshPlatformAccessToken } = usePlatformApi()
        const session = await refreshPlatformAccessToken()
        this.accessToken = session.accessToken
        this.refreshToken = session.refreshToken
        this.isAuthenticated = Boolean(session.accessToken)
        return { success: true, accessToken: session.accessToken }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos renovar la sesión.'
        this.error = message
        this.logout()
        return { success: false, message }
      }
    },

    logout() {
      usePlatformFeaturesStore().reset()
      clearPlatformSession()
      this.resetState()
    },
  },
})
