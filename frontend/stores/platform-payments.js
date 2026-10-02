import { defineStore } from 'pinia'
import { buildPlatformListUrl } from '~/composables/useIncludeArchivedQuery'
import { usePlatformApi } from '~/composables/usePlatformApi'

export const usePlatformPaymentsStore = defineStore('platformPayments', {
  state: () => ({
    subscriptions: [],
    currentSubscription: null,
    payments: [],
    proposals: [],
    phases: [],
    isLoading: false,
    isUpdating: false,
    error: '',
    subscriptionRequest: 0,
    phasesRequest: 0,
  }),

  getters: {
    otherPayments() {
      const currentId = this.currentPeriodPayment?.id
      return this.payments.filter(payment => payment.id !== currentId)
        .sort((a, b) => String(b.billing_period_start).localeCompare(String(a.billing_period_start)))
    },
    /**
     * Payment that needs user action NOW:
     * - overdue or failed: always show
     * - processing: always show (waiting for confirmation)
     * - pending: only show if due_date is within 7 days or past
     */
    currentPeriodPayment: (state) => {
      const now = new Date()
      const sevenDaysFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)

      const urgent = state.payments.filter((p) => {
        if (['overdue', 'failed', 'processing'].includes(p.status)) return true
        if (p.status === 'pending' && p.due_date) {
          return new Date(p.due_date) <= sevenDaysFromNow
        }
        return false
      })
      if (urgent.length === 0) return null
      const priority = { overdue: 0, failed: 1, processing: 2, pending: 3 }
      /* c8 ignore next */
      urgent.sort((a, b) => (priority[a.status] ?? 9) - (priority[b.status] ?? 9))
      return urgent[0]
    },

    /**
     * Next renewal date (from subscription or next pending payment).
     */
    nextRenewalDate: (state) => {
      if (!state.currentSubscription) return null
      return state.currentSubscription.next_billing_date
    },

    /**
     * Past payments: all paid + failed, sorted newest first.
     * Excludes the current urgent payment and future pending ones.
     */
    pastPayments: (state) => {
      return state.payments
        .filter((p) => p.status === 'paid' || p.status === 'failed')
        .sort((a, b) => new Date(b.billing_period_start) - new Date(a.billing_period_start))
    },

    /**
     * True when subscription is active and no payment action is needed right now.
     */
    subscriptionUpToDate() {
      if (!this.currentSubscription) return false
      if (this.currentSubscription.status !== 'active') return false
      return !this.currentPeriodPayment
    },
  },

  actions: {
    async fetchProposals() {
      try {
        const { get } = usePlatformApi()
        const response = await get('proposals/')
        this.proposals = response.data
        return { success: true }
      } catch (error) {
        return { success: false, message: error.response?.data?.detail || 'Error cargando propuestas.' }
      }
    },

    async fetchSubscriptions(includeArchived = false) {
      this.isLoading = true
      this.error = ''

      try {
        const { get } = usePlatformApi()
        const url = buildPlatformListUrl('subscriptions/', {}, includeArchived)
        const response = await get(url)
        this.subscriptions = response.data
        return { success: true }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos cargar las suscripciones.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async fetchProjectSubscription(projectId) {
      const request = ++this.subscriptionRequest
      this.currentSubscription = null
      this.payments = []
      this.isLoading = true
      this.error = ''

      try {
        const { get } = usePlatformApi()
        const response = await get(`projects/${projectId}/subscription/`)
        if (request !== this.subscriptionRequest) return { success: false, stale: true }
        this.currentSubscription = response.data
        this.payments = response.data.payments || []
        return { success: true, data: response.data }
      } catch (error) {
        if (request !== this.subscriptionRequest) return { success: false, stale: true }
        if (error.response?.status === 404) {
          this.currentSubscription = null
          this.payments = []
          return { success: true, data: null }
        }
        const message = error.response?.data?.detail || 'Error cargando suscripción.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        if (request === this.subscriptionRequest) this.isLoading = false
      }
    },

    async fetchProjectPayments(projectId, includeArchived = false) {
      this.isLoading = true
      this.error = ''

      try {
        const { get } = usePlatformApi()
        const url = buildPlatformListUrl(`projects/${projectId}/payments/`, {}, includeArchived)
        const response = await get(url)
        this.payments = response.data
        return { success: true }
      } catch (error) {
        const message = error.response?.data?.detail || 'Error cargando pagos.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async updateSubscription(projectId, payload) {
      this.isUpdating = true
      this.error = ''

      try {
        const { patch } = usePlatformApi()
        const response = await patch(`projects/${projectId}/subscription/`, payload)
        this.currentSubscription = response.data
        this.payments = response.data.payments || []
        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'Error actualizando suscripción.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async startCardSetup(projectId, cardData) {
      this.error = ''
      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/subscription/card/`, cardData)
        return { success: true, data: response.data }
      } catch (error) {
        return { success: false, message: error.response?.data?.detail || 'No se pudo registrar la tarjeta.' }
      }
    },

    async getCardSetupStatus(projectId, paymentSourceId) {
      try {
        const { get } = usePlatformApi()
        const response = await get(`projects/${projectId}/subscription/card/${paymentSourceId}/status/`)
        return { success: true, data: response.data }
      } catch (error) {
        return { success: false, message: error.response?.data?.detail || 'Error consultando el estado de la tarjeta.' }
      }
    },

    async confirmCardSetup(projectId, paymentSourceId, cardMeta) {
      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/subscription/card/${paymentSourceId}/confirm/`, cardMeta)
        if (response.data.subscription) {
          this.currentSubscription = response.data.subscription
          this.payments = response.data.subscription.payments || []
        }
        return { success: true, data: response.data }
      } catch (error) {
        return { success: false, message: error.response?.data?.detail || 'No se pudo confirmar la tarjeta.' }
      }
    },

    async deletePaymentMethod(projectId) {
      this.isUpdating = true
      this.error = ''
      try {
        const { delete: del } = usePlatformApi()
        const response = await del(`projects/${projectId}/subscription/card/remove/`)
        if (response.data.subscription) {
          this.currentSubscription = response.data.subscription
          this.payments = response.data.subscription.payments || []
        }
        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No se pudo eliminar la tarjeta.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async chargeStored(projectId, paymentId) {
      this.isUpdating = true
      this.error = ''
      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/payments/${paymentId}/charge/`, {})
        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'Error procesando el cobro.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async verifyTransaction(projectId, paymentId, transactionId = null) {
      try {
        const { post } = usePlatformApi()
        const body = transactionId ? { transaction_id: transactionId } : {}
        const response = await post(`projects/${projectId}/payments/${paymentId}/verify/`, body)
        return { success: true, data: response.data }
      } catch (error) {
        return { success: false, message: error.response?.data?.detail || 'Error verificando transacción.' }
      }
    },

    async generatePaymentLink(projectId, paymentId) {
      this.isUpdating = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/payments/${paymentId}/generate-link/`)

        const idx = this.payments.findIndex((p) => p.id === paymentId)
        if (idx !== -1) {
          this.payments[idx] = {
            ...this.payments[idx],
            wompi_payment_link_url: response.data.wompi_payment_link_url,
            status: 'processing',
          }
        }

        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'Error generando link de pago.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async fetchProjectPhases(projectId) {
      const request = ++this.phasesRequest
      this.phases = []
      try {
        const { get } = usePlatformApi()
        const response = await get(`projects/${projectId}/phases/`)
        if (request !== this.phasesRequest) return { success: false, stale: true }
        this.phases = response.data
        return { success: true, data: response.data }
      } catch (error) {
        if (request !== this.phasesRequest) return { success: false, stale: true }
        return { success: false, message: error.response?.data?.detail || 'Error cargando fases.' }
      }
    },

    async patchPhaseHostingDate(projectId, phaseId, hostingStartDate) {
      this.isUpdating = true
      try {
        const { patch } = usePlatformApi()
        const response = await patch(`projects/${projectId}/phases/${phaseId}/`, {
          hosting_start_date: hostingStartDate,
        })
        const idx = this.phases.findIndex((p) => p.id === phaseId)
        if (idx !== -1) this.phases[idx] = response.data
        return { success: true, data: response.data }
      } catch (error) {
        return { success: false, message: error.response?.data?.detail || 'Error guardando fecha.' }
      } finally {
        this.isUpdating = false
      }
    },

    async registerManualPayment(projectId, { frequency, amount, billing_period_start, description }) {
      this.isUpdating = true
      this.error = ''
      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/payments/manual/`, {
          frequency,
          amount,
          billing_period_start,
          description,
        })
        this.payments.unshift(response.data)
        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || JSON.stringify(error.response?.data) || 'Error registrando el pago.'
        this.error = message
        return { success: false, message }
      } finally {
        this.isUpdating = false
      }
    },
  },
})
