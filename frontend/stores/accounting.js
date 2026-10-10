import { defineStore } from 'pinia';
import {
  get_request,
  create_request,
  patch_request,
  delete_request,
} from './services/request_http';
import { normalizeApiError, numericIdsFromError } from './services/normalize_api_error';
import { buildReceivablesSummary } from '~/utils/receivables';

/**
 * Accounting entities exposed by the backend (/api/accounting/...).
 * Every entity shares the same CRUD URL shape, so the store maps a key
 * to its endpoint path and the state array holding its records.
 */
const ACCOUNTING_ENTITIES = {
  incomes: { stateKey: 'incomes', path: 'accounting/incomes/' },
  expenses: { stateKey: 'expenses', path: 'accounting/expenses/' },
  hostings: { stateKey: 'hostings', path: 'accounting/hostings/' },
  pocket: { stateKey: 'pocketMovements', path: 'accounting/pocket/' },
  recurring: { stateKey: 'recurringPayments', path: 'accounting/recurring/' },
  recurringCategories: {
    stateKey: 'recurringCategories',
    path: 'accounting/recurring-categories/',
  },
  ads: { stateKey: 'adsRecords', path: 'accounting/ads/' },
  cards: { stateKey: 'cardSnapshots', path: 'accounting/card-snapshots/' },
  creditCards: { stateKey: 'creditCards', path: 'accounting/credit-cards/' },
  statements: { stateKey: 'statements', path: 'accounting/statements/' },
  merchantAliases: { stateKey: 'merchantAliases', path: 'accounting/merchant-aliases/' },
  notificationRecipients: {
    stateKey: 'notificationRecipients',
    path: 'accounting/notification-recipients/',
  },
};

function entityConfig(entity) {
  const config = ACCOUNTING_ENTITIES[entity];
  if (!config) throw new Error(`Unknown accounting entity: ${entity}`);
  return config;
}

function buildQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value));
    }
  });
  const encoded = query.toString();
  return encoded ? `?${encoded}` : '';
}

export const useAccountingStore = defineStore('accounting', {
  /**
   * State of the Accounting store.
   *
   * Properties:
   * - incomes/expenses/hostings/pocketMovements/recurringPayments/
   *   adsRecords/cardSnapshots (Array): records per entity.
   * - metas (Object): list meta per entity key (balance, totals...).
   * - summary (Object|null): dashboard payload for selectedYear.
   * - changelog (Object): paginated audit log {results, count, page, numPages}.
   * - emailLog (Object): paginated send log, same shape as changelog.
   * - settings (Object|null): notification settings singleton.
   */
  state: () => ({
    incomes: [],
    expenses: [],
    hostings: [],
    pocketMovements: [],
    recurringPayments: [],
    recurringCategories: [],
    adsRecords: [],
    cardSnapshots: [],
    creditCards: [],
    collectionAccounts: [],
    collectionAccountsMeta: {},
    // Project options keyed by client profile id ('all' for the unscoped
    // list). A client gains a project far less often than a form reopens.
    projectsByClient: {},
    statements: [],
    merchantAliases: [],
    notificationRecipients: [],
    statementStatus: null,
    statementDetail: null,
    metas: {},
    summary: null,
    receivables: [],
    receivablesSummary: null,
    receivablesLoading: false,
    receivablesError: null,
    receivableUpdatingIds: [],
    stats: null,
    statsYear: null,
    changelog: { results: [], count: 0, page: 1, numPages: 1 },
    emailLog: { results: [], count: 0, page: 1, numPages: 1 },
    settings: null,
    selectedYear: new Date().getFullYear(),
    isLoading: false,
    isUpdating: false,
    error: null,
  }),

  getters: {
    /**
     * metaFor: last list meta for an entity key. The pocket balance lives
     * here too (meta.balance) — the server is its single owner.
     */
    metaFor: (state) => (entity) => state.metas[entity] || {},

    /**
     * recurringMonthlyTotalsBy: monthly COP totals of active payments grouped
     * by any field, read from `<field>_label` when the API exposes one.
     *
     * Monthly — not the raw charge — so every breakdown adds up to the
     * "Costo mensual (COP)" KPI. Summing `cop_equivalent` instead would count
     * a three-year domain renewal at its full price against a monthly total.
     */
    recurringMonthlyTotalsBy: (state) => (field) =>
      state.recurringPayments
        .filter((payment) => payment.is_active && !payment.is_archived)
        .reduce((totals, payment) => {
          const key = payment[`${field}_label`] || payment[field];
          if (key == null) return totals;
          totals[key] = (totals[key] || 0) + (Number(payment.monthly_cop_cost) || 0);
          return totals;
        }, {}),

    /**
     * recurringTotalsByFrequency / recurringTotalsByMethod: monthly COP totals
     * of active payments per frequency / payment method label.
     */
    recurringTotalsByFrequency() {
      return this.recurringMonthlyTotalsBy('frequency');
    },

    recurringTotalsByMethod() {
      return this.recurringMonthlyTotalsBy('payment_method');
    },

    /**
     * recurringTotalsByCategory: monthly COP totals per category, following
     * the catalog's own order and including a bucket for uncategorized rows.
     */
    recurringTotalsByCategory: (state) => {
      const totals = new Map(
        state.recurringCategories.map((category) => [category.id, {
          id: category.id,
          name: category.name,
          total: 0,
        }]),
      );
      let uncategorized = 0;

      state.recurringPayments
        .filter((payment) => payment.is_active && !payment.is_archived)
        .forEach((payment) => {
          const amount = Number(payment.monthly_cop_cost) || 0;
          const bucket = payment.category != null ? totals.get(payment.category) : null;
          if (bucket) bucket.total += amount;
          else uncategorized += amount;
        });

      const entries = [...totals.values()].filter((entry) => entry.total > 0);
      if (uncategorized > 0) {
        entries.push({ id: 'uncategorized', name: 'Sin categoría', total: uncategorized });
      }
      return entries;
    },
  },

  actions: {
    async fetchReceivables() {
      this.receivablesLoading = true;
      this.receivablesError = null;
      try {
        const response = await get_request('accounting/receivables/');
        this.receivables = response.data?.results || [];
        this.receivablesSummary = response.data?.summary || null;
        if (this.summary && this.receivablesSummary) {
          this.summary = {
            ...this.summary,
            receivables: this.receivablesSummary,
          };
        }
        return { success: true, data: response.data };
      } catch (error) {
        this.receivables = [];
        this.receivablesError = 'fetch_failed';
        console.error('Error fetching accounting receivables:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.receivablesLoading = false;
      }
    },

    async updateReceivableState(id, payload) {
      if (this.receivableUpdatingIds.includes(id)) {
        return { success: false, message: 'Este ingreso ya se está actualizando.' };
      }
      this.receivableUpdatingIds = [...this.receivableUpdatingIds, id];
      try {
        const response = await patch_request(
          `accounting/incomes/${id}/update/`, payload,
        );
        const replace = (row) => (row.id === id ? response.data : row);
        this.incomes = this.incomes.map(replace);
        if (this.receivablesSummary === null) {
          await this.fetchReceivables();
        } else {
          this.receivables = this.receivables.map(replace);
          this.receivablesSummary = buildReceivablesSummary(this.receivables);
          if (this.summary) {
            this.summary = {
              ...this.summary,
              receivables: this.receivablesSummary,
            };
          }
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error updating receivable state ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.receivableUpdatingIds = this.receivableUpdatingIds.filter(
          (recordId) => recordId !== id,
        );
      }
    },

    /**
     * fetchRecords: List an entity's records with optional query params
     * (year, kind, date_from, date_to, amount_min, amount_max, partner, q...).
     */
    async fetchRecords(entity, params = {}) {
      const config = entityConfig(entity);
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(
          `${config.path}${buildQuery(params)}`,
        );
        this[config.stateKey] = response.data.results ?? [];
        this.metas = { ...this.metas, [entity]: response.data.meta || {} };
        return { success: true, data: this[config.stateKey] };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error(`Error fetching accounting ${entity}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * _applyRecurringOrder: patch category/order locally and re-sort the list
     * the way the backend orders it (category order, then manual slot, then
     * name), so the store agrees with what the user just dropped.
     */
    _applyRecurringOrder(items) {
      const byId = new Map(items.map((item) => [item.id, item]));
      const categoryOrder = new Map(
        this.recurringCategories.map((category) => [category.id, category.order]),
      );

      const patched = this.recurringPayments.map((payment) => {
        const item = byId.get(payment.id);
        if (!item) return payment;
        const category = this.recurringCategories.find((c) => c.id === item.category);
        return {
          ...payment,
          order: item.order,
          category: item.category ?? null,
          category_name: category ? category.name : null,
        };
      });

      // Uncategorized rows sort last, matching the grouped view.
      const rank = (payment) =>
        payment.category != null
          ? (categoryOrder.get(payment.category) ?? Number.MAX_SAFE_INTEGER)
          : Number.MAX_SAFE_INTEGER;

      this.recurringPayments = patched.sort((a, b) =>
        rank(a) - rank(b)
        || (a.order ?? 0) - (b.order ?? 0)
        || String(a.name).localeCompare(String(b.name)),
      );
    },

    /**
     * reorderRecurring: persist a drag. Applies optimistically so the row
     * stays where it was dropped, and restores the previous slots if the
     * request fails — the snap-back is the error feedback.
     *
     * Items carry their category because a drag can move a row between
     * groups: [{ id, category, order }].
     */
    async reorderRecurring(items) {
      const previous = this.recurringPayments.map((payment) => ({
        id: payment.id,
        category: payment.category ?? null,
        order: payment.order ?? 0,
      }));

      this._applyRecurringOrder(items);
      this.isUpdating = true;
      this.error = null;
      try {
        await create_request('accounting/recurring/reorder/', { items });
        return { success: true };
      } catch (error) {
        this._applyRecurringOrder(previous);
        this.error = 'reorder_failed';
        console.error('Error reordering recurring payments:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    _replaceRecurring(payment) {
      this.recurringPayments = this.recurringPayments.map((row) =>
        row.id === payment.id ? payment : row,
      );
    },

    async fetchRecurringDuplicateDraft(id) {
      try {
        const response = await get_request(
          `accounting/recurring/${id}/duplicate-draft/`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error fetching recurring duplicate draft ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    async setRecurringActive(id, isActive) {
      return this._runRecurringAction(
        id, 'state/', { is_active: isActive }, 'state_failed',
      );
    },

    async archiveRecurring(id) {
      return this._runRecurringAction(id, 'archive/', {}, 'archive_failed');
    },

    async restoreRecurring(id) {
      return this._runRecurringAction(id, 'restore/', {}, 'restore_failed');
    },

    async muteRecurringReminders(id, payload) {
      return this._runRecurringAction(
        id, 'reminders/mute/', payload, 'mute_failed',
      );
    },

    async _runRecurringAction(id, suffix, payload, errorCode) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `accounting/recurring/${id}/${suffix}`, payload,
        );
        this._replaceRecurring(response.data);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = errorCode;
        console.error(`Error applying recurring action ${suffix} to ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    async bulkRecurringAction(ids, action) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          'accounting/recurring/bulk-action/',
          { recurring_ids: ids, action },
        );
        const replacements = new Map(
          (response.data.results || []).map((row) => [row.id, row]),
        );
        this.recurringPayments = this.recurringPayments.map(
          (row) => replacements.get(row.id) || row,
        );
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'bulk_action_failed';
        console.error(`Error applying recurring bulk action ${action}:`, error);
        return {
          success: false,
          ...normalizeApiError(error),
          missingIds: numericIdsFromError(error),
        };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * reorderRecurringCategories: persist the group order. Body is the id
     * array in its new order; array position becomes the new `order`.
     */
    async reorderRecurringCategories(ids) {
      const previous = this.recurringCategories;
      this.recurringCategories = ids
        .map((id, order) => {
          const category = previous.find((c) => c.id === id);
          return category ? { ...category, order } : null;
        })
        .filter(Boolean);

      this.isUpdating = true;
      this.error = null;
      try {
        await create_request('accounting/recurring-categories/reorder/', { ids });
        return { success: true };
      } catch (error) {
        this.recurringCategories = previous;
        this.error = 'reorder_failed';
        console.error('Error reordering recurring categories:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * createRecord: Create a record and prepend it to the local list.
     */
    async createRecord(entity, payload) {
      const config = entityConfig(entity);
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(`${config.path}create/`, payload);
        this[config.stateKey] = [response.data, ...this[config.stateKey]];
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'create_failed';
        console.error(`Error creating accounting ${entity}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * updateRecord: Patch a record and replace it in the local list.
     */
    async updateRecord(entity, id, payload) {
      const config = entityConfig(entity);
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(
          `${config.path}${id}/update/`, payload,
        );
        this[config.stateKey] = this[config.stateKey].map((record) =>
          record.id === id ? response.data : record,
        );
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'update_failed';
        console.error(`Error updating accounting ${entity} ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * deleteRecord: Delete a record and drop it from the local list.
     */
    async deleteRecord(entity, id) {
      const config = entityConfig(entity);
      this.isUpdating = true;
      this.error = null;
      try {
        await delete_request(`${config.path}${id}/delete/`);
        this[config.stateKey] = this[config.stateKey].filter(
          (record) => record.id !== id,
        );
        return { success: true };
      } catch (error) {
        this.error = 'delete_failed';
        console.error(`Error deleting accounting ${entity} ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * fetchStatementStatus: 12-month processed/draft/pending grid.
     */
    async fetchStatementStatus(year, cardName = '') {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(
          `accounting/statements/status/${buildQuery({ year, card_name: cardName })}`,
        );
        this.statementStatus = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error('Error fetching statement status:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchStatementDetail: header + transactions + category totals.
     */
    async fetchStatementDetail(id) {
      this.error = null;
      try {
        const response = await get_request(`accounting/statements/${id}/`);
        this.statementDetail = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error(`Error fetching statement ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * finalizeStatement: validate totals and mark processed.
     */
    async finalizeStatement(id, force = false) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `accounting/statements/${id}/finalize/`, { force },
        );
        this.statementDetail = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'update_failed';
        console.error(`Error finalizing statement ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * reopenStatement: processed → draft for corrections.
     */
    async reopenStatement(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `accounting/statements/${id}/reopen/`, {},
        );
        this.statementDetail = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'update_failed';
        console.error(`Error reopening statement ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * createStatementTransactions: batch-append lines to a draft statement.
     */
    async createStatementTransactions(statementId, transactions) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `accounting/statements/${statementId}/transactions/batch/`,
          { transactions },
        );
        if (this.statementDetail?.id === statementId) {
          await this.fetchStatementDetail(statementId);
        }
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'create_failed';
        console.error(`Error adding transactions to statement ${statementId}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * uploadStatementPdf: attach (or replace) the bank PDF of a statement.
     */
    async uploadStatementPdf(statementId, file) {
      this.isUpdating = true;
      this.error = null;
      try {
        const formData = new FormData();
        formData.append('file', file);
        const response = await create_request(
          `accounting/statements/${statementId}/pdf/upload/`, formData,
        );
        this.statementDetail = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'update_failed';
        console.error(`Error uploading statement PDF ${statementId}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * deleteStatementPdf: remove the attached bank PDF of a statement.
     */
    async deleteStatementPdf(statementId) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await delete_request(
          `accounting/statements/${statementId}/pdf/delete/`,
        );
        this.statementDetail = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'delete_failed';
        console.error(`Error deleting statement PDF ${statementId}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * updateStatementTransaction: patch one line of a draft statement.
     */
    async updateStatementTransaction(statementId, txId, payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(
          `accounting/statements/${statementId}/transactions/${txId}/update/`,
          payload,
        );
        if (this.statementDetail?.id === statementId) {
          this.statementDetail = {
            ...this.statementDetail,
            transactions: this.statementDetail.transactions.map((tx) =>
              tx.id === txId ? response.data : tx,
            ),
          };
        }
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'update_failed';
        console.error(`Error updating statement transaction ${txId}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * deleteStatementTransaction: remove one line of a draft statement.
     */
    async deleteStatementTransaction(statementId, txId) {
      this.isUpdating = true;
      this.error = null;
      try {
        await delete_request(
          `accounting/statements/${statementId}/transactions/${txId}/delete/`,
        );
        if (this.statementDetail?.id === statementId) {
          this.statementDetail = {
            ...this.statementDetail,
            transactions: this.statementDetail.transactions.filter(
              (tx) => tx.id !== txId,
            ),
          };
        }
        return { success: true };
      } catch (error) {
        this.error = 'delete_failed';
        console.error(`Error deleting statement transaction ${txId}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * settleIncome: liquidate an expected income and resolve its shortfall.
     *
     * With empty `deductions`/`expected_incomes` the backend behaves exactly
     * like creating a liquid child, so this is the single path for the
     * liquidate action. The caller refetches: the parent's `pending_amount`
     * and `payment_status` are server-computed, and deductions land in the
     * expenses list.
     */
    async settleIncome(incomeId, payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `accounting/incomes/${incomeId}/settle/`, payload,
        );
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'settle_failed';
        console.error(`Error settling income ${incomeId}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * fetchIncomePaymentConfirmation: who would receive the client's payment
     * confirmation for this income, or why it cannot go. Read when the
     * Liquidar modal opens; no state writes, like the cuenta preview.
     */
    async fetchIncomePaymentConfirmation(incomeId) {
      try {
        const response = await get_request(
          `accounting/incomes/${incomeId}/payment-confirmation/`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error reading payment confirmation of income ${incomeId}:`, error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * bulkSettleIncomes: register one abono distributed across several
     * expected incomes — one pocket movement, one liquid child per
     * allocation. Replaces the refreshed rows in place; the page still
     * refetches (children and the credit row are new rows the map cannot
     * insert, and the header meta is server-computed).
     */
    async bulkSettleIncomes(payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          'accounting/incomes/bulk-settle/', payload,
        );
        const updated = new Map(
          (response.data.results ?? []).map((row) => [row.id, row]),
        );
        if (updated.size) {
          this.incomes = this.incomes.map(
            (record) => updated.get(record.id) ?? record,
          );
        }
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'settle_failed';
        console.error('Error registering the abono:', error);
        return {
          success: false,
          ...normalizeApiError(error),
          missingIds: numericIdsFromError(error),
        };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * muteIncomeReminders: silence (or resume) one income's calendar notices.
     *
     * Its own endpoint rather than a plain field PATCH: the generic update path
     * emails both partners on every change, and silencing a receivable must
     * not generate a notification of its own.
     */
    async muteIncomeReminders(incomeId, payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `accounting/incomes/${incomeId}/mute/`, payload,
        );
        this.incomes = this.incomes.map(
          (r) => (r.id === incomeId ? response.data : r),
        );
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'mute_failed';
        console.error(`Error muting income ${incomeId}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * learnMerchantAlias: remember a hand-typed merchant for future statements.
     *
     * Upserts by normalized descriptor, so re-mapping a descriptor that already
     * has an alias corrects it instead of failing — that is exactly the case a
     * manual fix produces. With `statement_id` the backend also back-applies the
     * alias to the other unidentified rows of the same draft statement.
     */
    async learnMerchantAlias(payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          'accounting/merchant-aliases/learn/', payload,
        );
        await this.fetchRecords('merchantAliases');
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'alias_learn_failed';
        console.error('Error learning merchant alias:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * fetchSummary: Dashboard payload for a year (defaults to selectedYear).
     */
    async fetchSummary(year) {
      const targetYear = year || this.selectedYear;
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(
          `accounting/dashboard/?year=${targetYear}`,
        );
        this.summary = response.data;
        this.selectedYear = targetYear;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'summary_failed';
        console.error('Error fetching accounting summary:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchStats: Descriptive statistics for the analytics modals
     * (top concepts, category distribution, per-record describes).
     * Cached per year; callers pass force to refetch.
     */
    async fetchStats(year, { force = false } = {}) {
      const targetYear = year || this.selectedYear;
      if (!force && this.stats && this.statsYear === targetYear) {
        return { success: true, data: this.stats };
      }
      try {
        const response = await get_request(`accounting/stats/?year=${targetYear}`);
        this.stats = response.data;
        this.statsYear = targetYear;
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching accounting stats:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * fetchChangelog: Paginated audit log with optional filters
     * ({page, entity_type, object_id, action, actor, date_from, date_to}).
     */
    async fetchChangelog(params = {}) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(
          `accounting/change-logs/${buildQuery(params)}`,
        );
        this.changelog = {
          results: response.data.results,
          count: response.data.count,
          page: response.data.page,
          numPages: response.data.num_pages,
        };
        return { success: true, data: this.changelog };
      } catch (error) {
        this.error = 'changelog_failed';
        console.error('Error fetching accounting changelog:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchEmailLog: Paginated send log of the module's automated email
     * with optional filters ({page, template_key, status, recipient,
     * date_from, date_to}). Answers "who did this notice actually go to".
     */
    async fetchEmailLog(params = {}) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(
          `accounting/email-log/${buildQuery(params)}`,
        );
        this.emailLog = {
          results: response.data.results,
          count: response.data.count,
          page: response.data.page,
          numPages: response.data.num_pages,
        };
        return { success: true, data: this.emailLog };
      } catch (error) {
        this.error = 'email_log_failed';
        console.error('Error fetching accounting email log:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchHistoryTabCounts: how many rows each predefined tab is worth.
     *
     * The other accounting views count their tabs in the browser over the
     * rows already loaded; Historial paginates server-side, so an honest
     * badge — the (0) included — has to be asked for. Deliberately does not
     * touch `isLoading`: a stale badge must never blank the table.
     *
     * @param {'sends'|'changes'} scope
     * @param {Array<{id: string|number, filters: object}>} tabs
     */
    async fetchHistoryTabCounts(scope, tabs) {
      try {
        const response = await create_request(
          'accounting/history/tab-counts/', { scope, tabs },
        );
        return { success: true, counts: response.data.counts || {} };
      } catch (error) {
        console.error('Error fetching history tab counts:', error);
        return { success: false, counts: {}, ...normalizeApiError(error) };
      }
    },

    /**
     * fetchEmailBody: the message a send log row actually delivered.
     *
     * Kept out of `isLoading` and `error` like the tab counts: opening one
     * row's body must not blank the table behind the modal.
     */
    async fetchEmailBody(logId) {
      try {
        const response = await get_request(
          `accounting/email-log/${logId}/body/`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching email body:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * retryEmailLog: re-send a failed notice to the address on that row.
     *
     * Returns the new log entry, which points back at the original through
     * `retry_of` so the history shows both.
     */
    async retryEmailLog(logId) {
      try {
        const response = await create_request(
          `accounting/email-log/${logId}/retry/`, {},
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error retrying email log:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * fetchSettings: Notification settings singleton.
     */
    async fetchSettings() {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request('accounting/settings/');
        this.settings = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'settings_failed';
        console.error('Error fetching accounting settings:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * updateSettings: Patch recipients / notifications toggle.
     */
    async updateSettings(payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(
          'accounting/settings/update/', payload,
        );
        this.settings = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'settings_update_failed';
        console.error('Error updating accounting settings:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    // ── Collection accounts (cuentas de cobro) ──

    /**
     * fetchCollectionAccounts: Cobros monitor list + status counters.
     */
    async fetchCollectionAccounts(params = {}) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(
          `accounting/collection-accounts/${buildQuery(params)}`,
        );
        this.collectionAccounts = response.data.results ?? [];
        this.collectionAccountsMeta = response.data.meta ?? {};
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error('Error fetching collection accounts:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isLoading = false;
      }
    },

    /** One cuenta de cobro with its items, payment methods and notes. */
    async fetchCollectionAccount(id) {
      try {
        const response = await get_request(
          `accounting/collection-accounts/${id}/`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error fetching collection account ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * One income plus its settlement history and linked cuenta:
     * {income, liquid, expenses, collection_account}.
     */
    async fetchIncomeDetail(id) {
      try {
        const response = await get_request(`accounting/incomes/${id}/detail/`);
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error fetching income detail ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * Prefill for duplicating an income — the next period of a recurring
     * charge. Persists nothing: the form opens with this and the record is
     * created through the ordinary create endpoint once it is confirmed.
     */
    async fetchIncomeDuplicateDraft(id) {
      try {
        const response = await get_request(
          `accounting/incomes/${id}/duplicate-draft/`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error fetching income duplicate draft ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * Where a client's next hosting window starts. Creating an income has no
     * original to count from, so the antecedent — the last window already on
     * the book — is resolved server-side. Persists nothing.
     */
    async fetchIncomePeriodSuggestion({ client, project } = {}) {
      const params = new URLSearchParams();
      if (client) params.set('client', String(client));
      if (project) params.set('project', String(project));
      const query = params.toString();
      try {
        const response = await get_request(
          `accounting/incomes/period-suggestion/${query ? `?${query}` : ''}`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching income period suggestion:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * Projects to pick from, scoped to one client. Memoized per client:
     * the form re-opens far more often than a client gains a project.
     */
    async fetchProjectsForClient(clientProfileId) {
      const key = clientProfileId ?? 'all';
      if (this.projectsByClient[key]) {
        return { success: true, data: this.projectsByClient[key] };
      }
      try {
        const response = await get_request(
          `accounting/projects/${clientProfileId ? `?client=${clientProfileId}` : ''}`,
        );
        const results = response.data?.results ?? [];
        this.projectsByClient = { ...this.projectsByClient, [key]: results };
        return { success: true, data: results };
      } catch (error) {
        console.error('Error fetching projects:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * Create a project from a picker without leaving the form (crear al
     * vuelo). On success the memoized per-client list is updated in place —
     * and the 'all' key dropped — so every open picker sees the new project
     * without waiting out the cache. Returns the FULL annotated row: the
     * caller decides whether to offer the client's backlog from its
     * `unlinked_hostings_count`/`unlinked_incomes_count`; the picker cache
     * keeps only the lean entry it lists.
     */
    async createProjectForClient(clientProfileId, { name }) {
      try {
        const response = await create_request('projects/create/', {
          name,
          client_profile_id: clientProfileId,
        });
        const row = response.data;
        const entry = {
          id: row.id,
          name: row.name,
          status: row.status,
          status_label: row.status_label,
        };
        const key = clientProfileId ?? 'all';
        const next = [...(this.projectsByClient[key] ?? []), entry]
          .sort((a, b) => a.name.localeCompare(b.name));
        const cache = { ...this.projectsByClient, [key]: next };
        if (key !== 'all') delete cache.all;
        this.projectsByClient = cache;
        return { success: true, data: row };
      } catch (error) {
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudo crear el proyecto.'),
        };
      }
    },

    /**
     * Drop memoized picker lists so the next open refetches. The projects
     * module calls this after create/update/archive/restore — the memo is
     * otherwise permanent and a renamed or archived project would keep its
     * stale entry in every form.
     */
    invalidateProjectsCache(clientProfileId = null) {
      if (clientProfileId === null) {
        this.projectsByClient = {};
        return;
      }
      const cache = { ...this.projectsByClient };
      delete cache[clientProfileId];
      delete cache.all;
      this.projectsByClient = cache;
    },

    /**
     * sendHostingCollectionAccount: issue + email the cuenta de cobro of a
     * hosting. Returns {success, data: {document, email_sent}}.
     */
    async sendHostingCollectionAccount(hostingId, context = {}) {
      this.isUpdating = true;
      try {
        const response = await create_request(
          `accounting/hostings/${hostingId}/send-collection-account/`, context,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error sending collection account (hosting ${hostingId}):`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    async _collectionAccountAction(id, action) {
      this.isUpdating = true;
      try {
        const response = await create_request(
          `accounting/collection-accounts/${id}/${action}/`, {},
        );
        if (response.data?.id) {
          this.collectionAccounts = this.collectionAccounts.map((doc) =>
            doc.id === id ? response.data : doc,
          );
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error on collection account ${id} ${action}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * bulkAssignIncomeClient: link (or unlink, with client=null) several
     * incomes to one client. Replaces the affected rows in place so the
     * table reflects the change without a full refetch.
     */
    async bulkAssignIncomeClient(incomeIds, client) {
      this.isUpdating = true;
      try {
        const response = await create_request(
          'accounting/incomes/bulk-assign-client/',
          { income_ids: incomeIds, client },
        );
        const updated = new Map(
          (response.data.results ?? []).map((row) => [row.id, row]),
        );
        if (updated.size) {
          this.incomes = this.incomes.map(
            (record) => updated.get(record.id) ?? record,
          );
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error assigning client to incomes:', error);
        // `records_not_found` names rows that vanished under the open
        // dialog; `records_with_collection_account` names rows whose client
        // is frozen by an active cuenta. Either way the page drops exactly
        // those instead of clearing the whole selection.
        return {
          success: false,
          ...normalizeApiError(error),
          missingIds: [
            ...numericIdsFromError(error),
            ...numericIdsFromError(error, 'conflicting_ids'),
          ],
        };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * bulkAssignHostingClient: link (or unlink) several hostings to one
     * client. Replaces the affected rows in place, like the incomes one.
     */
    async bulkAssignHostingClient(hostingIds, client) {
      this.isUpdating = true;
      try {
        const response = await create_request(
          'accounting/hostings/bulk-assign-client/',
          { hosting_ids: hostingIds, client },
        );
        const updated = new Map(
          (response.data.results ?? []).map((row) => [row.id, row]),
        );
        if (updated.size) {
          this.hostings = this.hostings.map(
            (record) => updated.get(record.id) ?? record,
          );
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error assigning client to hostings:', error);
        return {
          success: false,
          ...normalizeApiError(error),
          missingIds: numericIdsFromError(error),
        };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * bulkAssignIncomeProject: link (or unlink, with project=null) several
     * incomes to one project. `results` also carries the liquid children
     * the cascade rewrote, so the in-place replacement misses nothing.
     */
    async bulkAssignIncomeProject(incomeIds, project) {
      this.isUpdating = true;
      try {
        const response = await create_request(
          'accounting/incomes/bulk-assign-project/',
          { income_ids: incomeIds, project },
        );
        const updated = new Map(
          (response.data.results ?? []).map((row) => [row.id, row]),
        );
        if (updated.size) {
          this.incomes = this.incomes.map(
            (record) => updated.get(record.id) ?? record,
          );
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error assigning project to incomes:', error);
        // `records_not_found` / `client_mismatch` name the rows that fell
        // out of the plan; the page drops exactly those from the selection.
        return {
          success: false,
          ...normalizeApiError(error),
          missingIds: [
            ...numericIdsFromError(error),
            ...numericIdsFromError(error, 'mismatched_ids'),
          ],
        };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * bulkAssignHostingProject: link (or unlink) several hostings to one
     * project. Replaces the affected rows in place, like the incomes one.
     */
    async bulkAssignHostingProject(hostingIds, project) {
      this.isUpdating = true;
      try {
        const response = await create_request(
          'accounting/hostings/bulk-assign-project/',
          { hosting_ids: hostingIds, project },
        );
        const updated = new Map(
          (response.data.results ?? []).map((row) => [row.id, row]),
        );
        if (updated.size) {
          this.hostings = this.hostings.map(
            (record) => updated.get(record.id) ?? record,
          );
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error assigning project to hostings:', error);
        return {
          success: false,
          ...normalizeApiError(error),
          missingIds: [
            ...numericIdsFromError(error),
            ...numericIdsFromError(error, 'mismatched_ids'),
          ],
        };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * createCollectionAccount: create + issue + email a cuenta linked to an
     * income (panel modal). Prepends the created document to the list.
     */
    async createCollectionAccount(payload) {
      this.isUpdating = true;
      try {
        const response = await create_request(
          'accounting/collection-accounts/create/', payload,
        );
        const document = response.data?.document;
        if (document?.id) {
          this.collectionAccounts = [document, ...this.collectionAccounts];
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error creating collection account:', error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * previewCollectionAccount: same payload as create; the backend renders
     * the real email + PDF inside a rolled-back transaction. No state writes.
     */
    async previewCollectionAccount(payload) {
      try {
        const response = await create_request(
          'accounting/collection-accounts/preview/', payload,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error previewing collection account:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * fetchCollectionAccountNextNumber: suggested per-client consecutivo
     * (never consumes the counter).
     */
    async fetchCollectionAccountNextNumber(clientProfileId) {
      try {
        const response = await get_request(
          `accounting/collection-accounts/next-number/?client_profile_id=${clientProfileId}`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching next collection number:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /**
     * searchIncomesForCollection: incomes eligible for a cuenta de cobro
     * (expected or liquid, never lost). Returns rows WITHOUT touching the
     * incomes tab state.
     */
    async searchIncomesForCollection(params = {}) {
      try {
        const response = await get_request(
          `accounting/incomes/${buildQuery({ kind: 'expected,liquid', ...params })}`,
        );
        return { success: true, data: response.data.results ?? [] };
      } catch (error) {
        console.error('Error searching incomes for collection:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    // ── Hosting cycles (payment history) ──

    async fetchHostingCycles(hostingId) {
      try {
        const response = await get_request(
          `accounting/hostings/${hostingId}/cycles/`,
        );
        return { success: true, data: response.data.results ?? [] };
      } catch (error) {
        console.error(`Error fetching cycles (hosting ${hostingId}):`, error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    async createHostingCycle(hostingId, payload) {
      this.isUpdating = true;
      try {
        const response = await create_request(
          `accounting/hostings/${hostingId}/cycles/create/`, payload,
        );
        if (response.data?.hosting) {
          this.hostings = this.hostings.map((record) =>
            record.id === hostingId ? response.data.hosting : record,
          );
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error creating cycle (hosting ${hostingId}):`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    async deleteHostingCycle(hostingId, cycleId) {
      this.isUpdating = true;
      try {
        await delete_request(
          `accounting/hostings/${hostingId}/cycles/${cycleId}/delete/`,
        );
        return { success: true };
      } catch (error) {
        console.error(`Error deleting cycle ${cycleId}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },

    async resendCollectionAccount(id) {
      return this._collectionAccountAction(id, 'resend');
    },

    async markCollectionAccountPaid(id) {
      return this._collectionAccountAction(id, 'mark-paid');
    },

    async cancelCollectionAccount(id) {
      return this._collectionAccountAction(id, 'cancel');
    },

    /**
     * deleteCollectionAccount: remove a cuenta created by mistake. Not a
     * sibling of the three above — those POST and get the updated row back,
     * this one DELETEs and the row stops existing, so it drops it locally
     * instead of swapping it. The page still refetches afterwards to bring
     * the header counters back in line.
     */
    async deleteCollectionAccount(id) {
      this.isUpdating = true;
      try {
        await delete_request(`accounting/collection-accounts/${id}/delete/`);
        this.collectionAccounts = this.collectionAccounts.filter(
          (doc) => doc.id !== id,
        );
        return { success: true };
      } catch (error) {
        console.error(`Error deleting collection account ${id}:`, error);
        return { success: false, ...normalizeApiError(error) };
      } finally {
        this.isUpdating = false;
      }
    },
  },
});
