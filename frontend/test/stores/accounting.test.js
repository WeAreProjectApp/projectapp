/**
 * Tests for accounting store (panel, superuser-only module).
 */
import { setActivePinia, createPinia } from 'pinia'
import { useAccountingStore } from '../../stores/accounting'

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}))

const {
  get_request,
  create_request,
  patch_request,
  delete_request,
} = require('../../stores/services/request_http')

function apiError(status, data) {
  return { response: { status, data } }
}

describe('useAccountingStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useAccountingStore()
    jest.clearAllMocks()
    jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty records and no summary', () => {
      expect(store.incomes).toEqual([])
      expect(store.pocketMovements).toEqual([])
      expect(store.summary).toBeNull()
      expect(store.settings).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.isUpdating).toBe(false)
    })
  })

  describe('fetchRecords', () => {
    it('fills the entity array and meta on success', async () => {
      get_request.mockResolvedValue({
        data: { results: [{ id: 1, concept: 'Kore' }], meta: { balance: '10.00' } },
      })
      const result = await store.fetchRecords('pocket', { year: 2026 })
      expect(get_request).toHaveBeenCalledWith('accounting/pocket/?year=2026')
      expect(result.success).toBe(true)
      expect(store.pocketMovements).toEqual([{ id: 1, concept: 'Kore' }])
      expect(store.metas.pocket).toEqual({ balance: '10.00' })
    })

    it('omits empty params from the query string', async () => {
      get_request.mockResolvedValue({ data: { results: [], meta: {} } })
      await store.fetchRecords('incomes', { kind: '', q: null })
      expect(get_request).toHaveBeenCalledWith('accounting/incomes/')
    })

    it('normalizes API errors on failure', async () => {
      get_request.mockRejectedValue(
        apiError(400, { error: 'Fecha inválida', code: 'bad_date' }),
      )
      const result = await store.fetchRecords('incomes')
      expect(result.success).toBe(false)
      expect(result.message).toBe('Fecha inválida')
      expect(store.error).toBe('fetch_failed')
    })

    // The invariant useRowSelection rests on: the list is only ever replaced
    // by a successful response. If a failed refetch blanked it, the selection
    // prune would read "every record is gone" and wipe a live selection.
    it('keeps the previous list when the refetch fails', async () => {
      store.incomes = [{ id: 1, concept: 'Kore - Inicio' }]
      get_request.mockRejectedValue(apiError(500, { error: 'Boom' }))

      await store.fetchRecords('incomes')

      expect(store.incomes).toEqual([{ id: 1, concept: 'Kore - Inicio' }])
    })

    it('throws for unknown entities', async () => {
      await expect(store.fetchRecords('nope')).rejects.toThrow(
        'Unknown accounting entity',
      )
    })
  })

  describe('mutations', () => {
    it('createRecord posts to create/ and prepends the record', async () => {
      store.incomes = [{ id: 1 }]
      create_request.mockResolvedValue({ data: { id: 2, concept: 'Nuevo' } })
      const result = await store.createRecord('incomes', { concept: 'Nuevo' })
      expect(create_request).toHaveBeenCalledWith(
        'accounting/incomes/create/', { concept: 'Nuevo' },
      )
      expect(result.success).toBe(true)
      expect(store.incomes[0]).toEqual({ id: 2, concept: 'Nuevo' })
    })

    it('fetchIncomeDuplicateDraft reads the draft without writing anything', async () => {
      get_request.mockResolvedValue({
        data: { concept: 'Kore - Hosting anual', kind: 'expected' },
      })

      const result = await store.fetchIncomeDuplicateDraft(7)

      expect(get_request).toHaveBeenCalledWith(
        'accounting/incomes/7/duplicate-draft/',
      )
      expect(create_request).not.toHaveBeenCalled()
      expect(result.data.kind).toBe('expected')
    })

    it('fetchRecurringDuplicateDraft reads a create prefill', async () => {
      get_request.mockResolvedValue({
        data: { name: 'Figma equipo', cycle_anchor_date: '2026-10-17' },
      })

      const result = await store.fetchRecurringDuplicateDraft(12)

      expect(get_request).toHaveBeenCalledWith(
        'accounting/recurring/12/duplicate-draft/',
      )
      expect(create_request).not.toHaveBeenCalled()
      expect(result.data.cycle_anchor_date).toBe('2026-10-17')
    })

    it.each([
      ['state', (current) => current.setRecurringActive(12, false), 'state/', { is_active: false }],
      ['archive', (current) => current.archiveRecurring(12), 'archive/', {}],
      ['restore', (current) => current.restoreRecurring(12), 'restore/', {}],
      [
        'reminder mute',
        (current) => current.muteRecurringReminders(12, { muted: true, until: null }),
        'reminders/mute/',
        { muted: true, until: null },
      ],
    ])('routes the recurring %s action', async (_label, action, suffix, payload) => {
      store.recurringPayments = [{ id: 12, name: 'Viejo' }, { id: 13 }]
      create_request.mockResolvedValue({ data: { id: 12, name: 'Actualizado' } })

      const result = await action(store)

      expect(create_request).toHaveBeenCalledWith(
        `accounting/recurring/12/${suffix}`,
        payload,
      )
      expect(result.success).toBe(true)
      expect(store.recurringPayments[0].name).toBe('Actualizado')
      expect(store.recurringPayments[1]).toEqual({ id: 13 })
    })

    // Falla si el silencio usa la mutación genérica que notifica al cliente.
    it('posts an income reminder mute to its dedicated endpoint', async () => {
      create_request.mockResolvedValue({
        data: {
          id: 12,
          concept: 'Hosting anual',
          reminders_muted: true,
          reminders_muted_until: '2026-09-30',
        },
      })

      const result = await store.muteIncomeReminders(12, {
        muted: true,
        until: '2026-09-30',
      })

      expect(create_request).toHaveBeenCalledWith(
        'accounting/incomes/12/mute/',
        { muted: true, until: '2026-09-30' },
      )
      expect(result.success).toBe(true)
    })

    // Falla si la respuesta del ingreso 12 reemplaza una fila distinta.
    it('replaces only the targeted income row after muting reminders', async () => {
      store.incomes = [
        { id: 12, concept: 'Hosting anual', reminders_muted: false },
        { id: 13, concept: 'Hosting mensual', reminders_muted: false },
      ]
      create_request.mockResolvedValue({
        data: {
          id: 12,
          concept: 'Hosting anual',
          reminders_muted: true,
          reminders_muted_until: '2026-09-30',
        },
      })

      await store.muteIncomeReminders(12, {
        muted: true,
        until: '2026-09-30',
      })

      expect(store.incomes).toEqual([
        {
          id: 12,
          concept: 'Hosting anual',
          reminders_muted: true,
          reminders_muted_until: '2026-09-30',
        },
        { id: 13, concept: 'Hosting mensual', reminders_muted: false },
      ])
    })

    // Falla si un error deja el panel bloqueado o cambia el ingreso sin persistirlo.
    it('keeps the income list intact when muting reminders fails', async () => {
      store.incomes = [{ id: 12, concept: 'Hosting anual', reminders_muted: false }]
      create_request.mockRejectedValue(apiError(503, { error: 'Servicio no disponible' }))

      const result = await store.muteIncomeReminders(12, { muted: true, until: null })

      expect(result.success).toBe(false)
      expect(store.isUpdating).toBe(false)
      expect(store.incomes).toEqual([
        { id: 12, concept: 'Hosting anual', reminders_muted: false },
      ])
    })

    it('replaces every row returned by a recurring bulk action', async () => {
      store.recurringPayments = [
        { id: 12, is_active: true },
        { id: 13, is_active: true },
        { id: 14, is_active: true },
      ]
      create_request.mockResolvedValue({
        data: {
          updated: 2,
          results: [
            { id: 12, is_active: false },
            { id: 13, is_active: false },
          ],
        },
      })

      const result = await store.bulkRecurringAction([12, 13], 'deactivate')

      expect(create_request).toHaveBeenCalledWith(
        'accounting/recurring/bulk-action/',
        { recurring_ids: [12, 13], action: 'deactivate' },
      )
      expect(result.data.updated).toBe(2)
      expect(store.recurringPayments.map((row) => row.is_active))
        .toEqual([false, false, true])
    })

    it('returns missing ids from a stale recurring selection', async () => {
      create_request.mockRejectedValue(apiError(409, {
        error: 'Algunos pagos ya no existen.',
        code: 'records_not_found',
        missing_ids: [12, '13'],
      }))

      const result = await store.bulkRecurringAction([12, 13], 'archive')

      expect(result.success).toBe(false)
      expect(result.missingIds).toEqual([12, 13])
    })

    it('settleIncome posts the settlement to the income endpoint', async () => {
      create_request.mockResolvedValue({
        data: { income: { id: 7 }, liquid: { id: 8 }, expenses: [{ id: 9 }] },
      })

      const result = await store.settleIncome(7, {
        concept: 'Kore',
        total_amount: '992000.00',
        deductions: [{ type: 'gateway_fee', detail: '', amount: '8000.00' }],
        expected_incomes: [],
      })

      expect(create_request).toHaveBeenCalledWith(
        'accounting/incomes/7/settle/',
        expect.objectContaining({ total_amount: '992000.00' }),
      )
      expect(result.success).toBe(true)
      expect(result.data.expenses).toHaveLength(1)
    })

    it('settleIncome surfaces the backend message on failure', async () => {
      create_request.mockRejectedValue({
        response: { status: 400, data: { detail: 'no puede superar el saldo' } },
      })

      const result = await store.settleIncome(7, { total_amount: '1.00' })

      expect(result.success).toBe(false)
      expect(result.message).toContain('saldo')
    })

    it('fetchIncomePaymentConfirmation reads who would receive the email', async () => {
      get_request.mockResolvedValue({
        data: { can_send: true, recipient: 'pagos@acme.co' },
      })

      const result = await store.fetchIncomePaymentConfirmation(7)

      expect(get_request).toHaveBeenCalledWith(
        'accounting/incomes/7/payment-confirmation/',
      )
      expect(result).toEqual({
        success: true, data: { can_send: true, recipient: 'pagos@acme.co' },
      })
      expect(store.isUpdating).toBe(false)
    })

    it('fetchIncomePaymentConfirmation reports a failure without state writes', async () => {
      get_request.mockRejectedValue(apiError(404, { detail: 'No encontrado.' }))

      const result = await store.fetchIncomePaymentConfirmation(99)

      expect(result.success).toBe(false)
      expect(store.error).toBeNull()
    })

    it('updateRecord patches update/ and replaces the record', async () => {
      store.expenses = [{ id: 5, concept: 'Viejo' }, { id: 6 }]
      patch_request.mockResolvedValue({ data: { id: 5, concept: 'Nuevo' } })
      const result = await store.updateRecord('expenses', 5, { concept: 'Nuevo' })
      expect(patch_request).toHaveBeenCalledWith(
        'accounting/expenses/5/update/', { concept: 'Nuevo' },
      )
      expect(result.success).toBe(true)
      expect(store.expenses[0].concept).toBe('Nuevo')
      expect(store.expenses[1]).toEqual({ id: 6 })
    })

    it('deleteRecord removes the record from the list', async () => {
      store.hostings = [{ id: 7 }, { id: 8 }]
      delete_request.mockResolvedValue({})
      const result = await store.deleteRecord('hostings', 7)
      expect(delete_request).toHaveBeenCalledWith(
        'accounting/hostings/7/delete/',
      )
      expect(result.success).toBe(true)
      expect(store.hostings).toEqual([{ id: 8 }])
    })

    it('surfaces the backend message on mutation failure', async () => {
      create_request.mockRejectedValue(
        apiError(400, {
          error: 'Este movimiento del bolsillo es gestionado automáticamente.',
          code: 'auto_managed_movement',
        }),
      )
      const result = await store.createRecord('pocket', {})
      expect(result.success).toBe(false)
      expect(result.code).toBe('auto_managed_movement')
    })
  })

  describe('summary, changelog and settings', () => {
    it('fetchSummary queries the dashboard for the given year', async () => {
      get_request.mockResolvedValue({ data: { year: 2026, expected_total: 100 } })
      const result = await store.fetchSummary(2026)
      expect(get_request).toHaveBeenCalledWith('accounting/dashboard/?year=2026')
      expect(result.success).toBe(true)
      expect(store.summary.year).toBe(2026)
      expect(store.selectedYear).toBe(2026)
    })

    it('fetchChangelog maps pagination fields', async () => {
      get_request.mockResolvedValue({
        data: { results: [{ id: 1 }], count: 25, page: 2, num_pages: 3 },
      })
      await store.fetchChangelog({ page: 2, entity_type: 'income' })
      expect(get_request).toHaveBeenCalledWith(
        'accounting/change-logs/?page=2&entity_type=income',
      )
      expect(store.changelog).toEqual({
        results: [{ id: 1 }], count: 25, page: 2, numPages: 3,
      })
    })

    it('fetchSettings and updateSettings hit the settings endpoints', async () => {
      get_request.mockResolvedValue({
        data: { notifications_enabled: true },
      })
      await store.fetchSettings()
      expect(get_request).toHaveBeenCalledWith('accounting/settings/')

      patch_request.mockResolvedValue({
        data: { notifications_enabled: false },
      })
      const result = await store.updateSettings({ notifications_enabled: false })
      expect(patch_request).toHaveBeenCalledWith(
        'accounting/settings/update/',
        { notifications_enabled: false },
      )
      expect(result.success).toBe(true)
      expect(store.settings.notifications_enabled).toBe(false)
    })

    it('fetchEmailLog maps pagination fields', async () => {
      get_request.mockResolvedValue({
        data: { results: [{ id: 7 }], count: 40, page: 2, num_pages: 2 },
      })

      await store.fetchEmailLog({ page: 2, status: 'failed' })

      expect(get_request).toHaveBeenCalledWith(
        'accounting/email-log/?page=2&status=failed',
      )
      expect(store.emailLog).toEqual({
        results: [{ id: 7 }], count: 40, page: 2, numPages: 2,
      })
    })

    it('fetchEmailLog surfaces its own error code', async () => {
      get_request.mockRejectedValue(apiError(500, { error: 'boom' }))

      const result = await store.fetchEmailLog()

      expect(result.success).toBe(false)
      expect(store.error).toBe('email_log_failed')
    })

    it('fetchHistoryTabCounts posts the tab specs and returns the counts', async () => {
      create_request.mockResolvedValue({
        data: { counts: { all: 12, failed: 2, bounced: 0 } },
      })

      const result = await store.fetchHistoryTabCounts('sends', [
        { id: 'all', filters: {} },
        { id: 'failed', filters: { status: ['failed'] } },
      ])

      expect(create_request).toHaveBeenCalledWith(
        'accounting/history/tab-counts/',
        {
          scope: 'sends',
          tabs: [
            { id: 'all', filters: {} },
            { id: 'failed', filters: { status: ['failed'] } },
          ],
        },
      )
      expect(result).toEqual({
        success: true, counts: { all: 12, failed: 2, bounced: 0 },
      })
    })

    it('fetchEmailBody returns the stored message', async () => {
      get_request.mockResolvedValue({
        data: { id: 7, html: '<p>Hola</p>', text: 'Hola' },
      })

      const result = await store.fetchEmailBody(7)

      expect(get_request).toHaveBeenCalledWith('accounting/email-log/7/body/')
      expect(result.success).toBe(true)
      expect(result.data.html).toBe('<p>Hola</p>')
    })

    it('a missing body is an answer, not a blank table', async () => {
      store.error = null
      get_request.mockRejectedValue(
        apiError(404, { error: 'Sin cuerpo guardado.', code: 'body_not_stored' }),
      )

      const result = await store.fetchEmailBody(7)

      expect(result.success).toBe(false)
      expect(result.message).toContain('Sin cuerpo guardado')
      expect(store.error).toBeNull()
    })

    it('retryEmailLog posts to the row and returns the new entry', async () => {
      create_request.mockResolvedValue({ data: { id: 12, retry_of: 7 } })

      const result = await store.retryEmailLog(7)

      expect(create_request).toHaveBeenCalledWith(
        'accounting/email-log/7/retry/', {},
      )
      expect(result).toEqual({ success: true, data: { id: 12, retry_of: 7 } })
    })

    it('a refused retry surfaces the reason it was refused', async () => {
      create_request.mockRejectedValue(
        apiError(400, { error: 'Este aviso resume varios registros del día.' }),
      )

      const result = await store.retryEmailLog(7)

      expect(result.success).toBe(false)
      expect(result.message).toContain('resume varios registros')
    })

    it('a failed count query never blanks the table', async () => {
      store.error = null
      store.isLoading = false
      create_request.mockRejectedValue(apiError(500, { error: 'boom' }))

      const result = await store.fetchHistoryTabCounts('sends', [])

      expect(result.success).toBe(false)
      expect(result.counts).toEqual({})
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(false)
    })

    it('routes the recipient CRUD to the notification-recipients endpoints', async () => {
      create_request.mockResolvedValue({ data: { id: 3, email: 'ana@test.com' } })
      patch_request.mockResolvedValue({
        data: { id: 3, email: 'ana@test.com', is_active: false },
      })

      await store.createRecord('notificationRecipients', { email: 'ana@test.com' })
      await store.updateRecord('notificationRecipients', 3, { is_active: false })

      expect(create_request).toHaveBeenCalledWith(
        'accounting/notification-recipients/create/',
        { email: 'ana@test.com' },
      )
      expect(patch_request).toHaveBeenCalledWith(
        'accounting/notification-recipients/3/update/',
        { is_active: false },
      )
      expect(store.notificationRecipients[0].is_active).toBe(false)
    })
  })

  describe('getters', () => {
    // The pocket running balance moved out of the store to
    // `utils/pocketRunningBalance`: the page accumulates over the rows its
    // filters left, so the store no longer owns that view.
    // See frontend/test/utils/pocketRunningBalance.test.js.

    it('recurringTotalsByFrequency sums active payments only', () => {
      store.recurringPayments = [
        {
          is_active: true, frequency: 'monthly', frequency_label: 'Mensual',
          payment_method_label: 'T.C', monthly_cop_cost: '800000.00',
        },
        {
          is_active: true, frequency: 'monthly', frequency_label: 'Mensual',
          payment_method_label: 'Efectivo', monthly_cop_cost: '400000.00',
        },
        {
          is_active: false, frequency: 'monthly', frequency_label: 'Mensual',
          payment_method_label: 'T.C', monthly_cop_cost: '99999.00',
        },
        {
          is_active: true, is_archived: true, frequency: 'monthly',
          frequency_label: 'Mensual', payment_method_label: 'T.C',
          monthly_cop_cost: '88888.00',
        },
      ]
      expect(store.recurringTotalsByFrequency).toEqual({ Mensual: 1200000 })
      expect(store.recurringTotalsByMethod).toEqual({
        'T.C': 800000, Efectivo: 400000,
      })
    })

    it('recurring breakdowns prorate long frequencies instead of counting the full charge', () => {
      store.recurringPayments = [
        {
          is_active: true, frequency: 'triennial', frequency_label: 'Cada 3 años',
          cop_equivalent: '161964.00', monthly_cop_cost: '4499.00',
        },
      ]
      // The raw charge is 161.964 every three years; the monthly view is 4.499,
      // which is what makes the breakdown add up to the monthly KPI.
      expect(store.recurringTotalsByFrequency).toEqual({ 'Cada 3 años': 4499 })
    })

    it('recurring breakdowns split each custom cycle under its own label', () => {
      store.recurringPayments = [
        {
          is_active: true, frequency: 'custom', frequency_label: 'Cada 5 meses',
          cop_equivalent: '500000.00', monthly_cop_cost: '100000.00',
        },
        {
          is_active: true, frequency: 'custom', frequency_label: 'Cada 7 meses',
          cop_equivalent: '700000.00', monthly_cop_cost: '100000.00',
        },
        {
          is_active: true, frequency: 'quarterly', frequency_label: 'Trimestral',
          cop_equivalent: '300000.00', monthly_cop_cost: '100000.00',
        },
      ]
      // Two custom cycles of different length are different frequencies, so a
      // shared "Personalizada" bucket would hide what the operator is paying for.
      expect(store.recurringTotalsByFrequency).toEqual({
        'Cada 5 meses': 100000,
        'Cada 7 meses': 100000,
        Trimestral: 100000,
      })
    })

    it('recurringTotalsByCategory follows the catalog order and buckets the uncategorized', () => {
      store.recurringCategories = [
        { id: 1, name: 'IA', order: 0 },
        { id: 2, name: 'Infraestructura', order: 1 },
        { id: 3, name: 'Vacía', order: 2 },
      ]
      store.recurringPayments = [
        { is_active: true, category: 2, monthly_cop_cost: '32900.00' },
        { is_active: true, category: 1, monthly_cop_cost: '800000.00' },
        { is_active: true, category: null, monthly_cop_cost: '1000.00' },
        { is_active: false, category: 1, monthly_cop_cost: '99999.00' },
      ]

      expect(store.recurringTotalsByCategory).toEqual([
        { id: 1, name: 'IA', total: 800000 },
        { id: 2, name: 'Infraestructura', total: 32900 },
        { id: 'uncategorized', name: 'Sin categoría', total: 1000 },
      ])
    })
  })

  describe('reordering', () => {
    it('reorderRecurring posts the items and re-sorts the local list', async () => {
      const store = useAccountingStore()
      store.recurringCategories = [{ id: 1, name: 'IA', order: 0 }]
      store.recurringPayments = [
        { id: 10, name: 'Chat-GPT', category: 1, order: 0 },
        { id: 11, name: 'Claude Code 20x', category: 1, order: 1 },
      ]
      create_request.mockResolvedValueOnce({ data: { reordered: 2 } })

      const items = [
        { id: 11, category: 1, order: 0 },
        { id: 10, category: 1, order: 1 },
      ]
      const result = await store.reorderRecurring(items)

      expect(result.success).toBe(true)
      expect(create_request).toHaveBeenCalledWith(
        'accounting/recurring/reorder/', { items },
      )
      expect(store.recurringPayments.map((p) => p.id)).toEqual([11, 10])
    })

    it('reorderRecurring restores the previous order when the request fails', async () => {
      const store = useAccountingStore()
      store.recurringCategories = [{ id: 1, name: 'IA', order: 0 }]
      store.recurringPayments = [
        { id: 10, name: 'Chat-GPT', category: 1, order: 0 },
        { id: 11, name: 'Claude Code 20x', category: 1, order: 1 },
      ]
      create_request.mockRejectedValueOnce(new Error('boom'))

      const result = await store.reorderRecurring([
        { id: 11, category: 1, order: 0 },
        { id: 10, category: 1, order: 1 },
      ])

      expect(result.success).toBe(false)
      expect(store.error).toBe('reorder_failed')
      expect(store.recurringPayments.map((p) => p.id)).toEqual([10, 11])
    })

    it('reorderRecurringCategories renumbers the catalog and rolls back on failure', async () => {
      const store = useAccountingStore()
      store.recurringCategories = [
        { id: 1, name: 'IA', order: 0 },
        { id: 2, name: 'Infraestructura', order: 1 },
      ]
      create_request.mockRejectedValueOnce(new Error('boom'))

      const result = await store.reorderRecurringCategories([2, 1])

      expect(result.success).toBe(false)
      expect(store.recurringCategories.map((c) => c.id)).toEqual([1, 2])
    })
  })
})
