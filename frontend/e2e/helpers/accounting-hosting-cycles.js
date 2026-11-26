import { expect } from './test.js';
import { chooseRowAction, openRowMenu } from './row-actions.js';

export function hostingRows({ billingSent }) {
  return [
    {
      id: 1,
      client_name: 'German',
    project_name: 'Kore',
    display_label: 'German — Kore',
      client: 5,
      client_display_name: 'Germán Franco',
      project: 10,
      project_id: 10,
      billing_email: 'german@korehealths.com',
      client_email: 'german@korehealths.com',
      domain_url: 'https://korehealths.com/',
      monthly_value: '91667.00',
      payment_modality: 'semiannual',
      payment_modality_label: 'Semestral',
      benefit: '',
      valid_from: '2026-03-02',
      valid_to: '2026-09-02',
      cycles_count: 1,
      payment_per_cycle: '550002.00',
      total_paid: '550002.00',
      billing_requested_at: billingSent ? '2026-07-16T10:00:00Z' : null,
      is_active: true,
      notes: '',
      created_at: '2026-03-02T10:00:00Z',
      updated_at: '2026-03-02T10:00:00Z',
    },
    {
      id: 2,
      client_name: 'Nestor',
    project_name: 'Xpandia',
    display_label: 'Nestor — Xpandia',
      client: null,
      client_display_name: null,
      billing_email: '',
      client_email: '',
      domain_url: 'https://xpandia.global/',
      monthly_value: '19000.00',
      payment_modality: 'nine_month',
      payment_modality_label: 'Cada 9 meses',
      benefit: '',
      valid_from: '2026-07-01',
      valid_to: '2027-07-01',
      cycles_count: 0,
      payment_per_cycle: '171000.00',
      total_paid: '0.00',
      billing_requested_at: null,
      is_active: true,
      notes: '',
      created_at: '2026-07-01T10:00:00Z',
      updated_at: '2026-07-01T10:00:00Z',
    },
  ];
}

export const BACKFILL_CYCLE = {
  id: 10,
  paid_at: '2026-01-02',
  modality: 'semiannual',
  modality_label: 'Semestral',
  amount: '550002.00',
  period_from: '2025-07-02',
  period_to: '2026-01-02',
  is_backfill: true,
  cycles_represented: 3,
  notes: 'Backfill histórico',
};

export const HOSTING_PERIOD = {
  income_id: 301,
  hosting_record_id: 1,
  project_hosting_id: 90,
  hosting_payment_id: 401,
  source: 'subscription',
  concept: 'Hosting Kore septiembre 2026',
  period_start: '2026-09-03',
  period_end: '2027-03-02',
  state: 'pending',
  amount: '550002.00',
  received: '0.00',
  balance: '550002.00',
  documents: [],
  cycles: [],
  liquids: [],
  version: 'hosting-period-401-v1',
};

function billingContext({ period = HOSTING_PERIOD, blocked = '' } = {}) {
  return {
    overview: {
      hosting_id: 90,
      reconciliation_required: false,
      accounting_sources: [{ id: 1, operational: true }],
    },
    selection: {
      requires_reconciliation: false,
      candidates: [{
        project_hosting_id: 90,
        hosting_record_id: 1,
        domain_url: 'https://korehealths.com/',
        payment_modality: 'semiannual',
        is_active: true,
        selectable: true,
        requires_association: false,
      }],
    },
    billing_period: { ...period, blocker: blocked || undefined },
  };
}

export function buildHandler({
  calls,
  emailSent = true,
  cycles = [],
  createCycleError,
  loadCyclesError,
  cycleReceiptError,
  cycleReceiptBlocker,
  nextIncomeError,
}) {
  const state = { billingSent: false, cycles: [...cycles], nextIncomeId: null };
  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { username: 'admin', is_staff: true, is_superuser: true },
        }),
      };
    }
    if (apiPath === 'accounting/hostings/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: hostingRows({ billingSent: state.billingSent }),
          meta: {
            active_count: 2,
            monthly_income: '110667.00',
            expiring_soon_count: 0,
            total_paid: '550002.00',
          },
        }),
      };
    }
    if (
      apiPath === 'accounting/hostings/1/send-collection-account/'
      && method === 'POST'
    ) {
      calls.push({ apiPath, method });
      state.billingSent = true;
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          document: { id: 77, public_number: 'PA-2026-0007' },
          email_sent: emailSent,
        }),
      };
    }
    if (apiPath === 'admin/billing-context/projects/10/hosting/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(billingContext()),
      };
    }
    if (apiPath === 'accounting/hostings/1/cycle-receipt/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          incomes: [{ ...HOSTING_PERIOD, blocker: cycleReceiptBlocker || undefined }],
        }),
      };
    }
    if (apiPath === 'accounting/hostings/1/cycle-receipt/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (cycleReceiptError) {
        return {
          status: cycleReceiptError.status,
          contentType: 'application/json',
          body: JSON.stringify({ detail: cycleReceiptError.detail }),
        };
      }
      const preview = new URL(route.request().url()).searchParams.get('preview') === '1';
      if (preview) {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            preview_hash: 'receipt-preview-v1',
            rows: [{ income_id: 301, validity_target: '2027-03-02' }],
          }),
        };
      }
      const cycle = {
        ...BACKFILL_CYCLE,
        id: 50,
        paid_at: body.paid_at,
        amount: String(body.amount),
        is_backfill: false,
        cycles_represented: 1,
        notes: body.notes || '',
      };
      state.cycles = [cycle, ...state.cycles];
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          cycle,
          allocation_id: 91,
          settlement_id: 'settlement-1',
          already_registered: false,
          period: { ...HOSTING_PERIOD, received: String(body.amount), balance: '0.00' },
        }),
      };
    }
    if (apiPath === 'accounting/hostings/1/next-income/' && method === 'GET') {
      if (nextIncomeError) {
        return { status: nextIncomeError.status, contentType: 'application/json', body: JSON.stringify({ detail: nextIncomeError.detail }) };
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          client_name: 'Germán Franco', project_name: 'Kore', service: 'korehealths.com',
          reference_start: '2026-09-03', reference_end: '2027-03-02', version: 'next-income-v1',
          existing_income_id: state.nextIncomeId,
          fields: { concept: 'Hosting Kore marzo 2027', period_start: '2027-03-03', period_end: '2027-09-02', total_amount: '550002.00' },
        }),
      };
    }
    if (apiPath === 'accounting/hostings/1/next-income/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      state.nextIncomeId = 302;
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          client_name: 'Germán Franco', project_name: 'Kore', service: 'korehealths.com',
          reference_start: '2026-09-03', reference_end: '2027-03-02', version: 'next-income-v1',
          existing_income_id: 302,
          fields: { concept: 'Hosting Kore marzo 2027', period_start: '2027-03-03', period_end: '2027-09-02', total_amount: '550002.00' },
        }),
      };
    }
    if (apiPath === 'accounting/hostings/1/cycles/' && method === 'GET') {
      if (loadCyclesError) {
        return {
          status: loadCyclesError.status,
          contentType: 'application/json',
          body: JSON.stringify({ detail: loadCyclesError.detail }),
        };
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: state.cycles }),
      };
    }
    if (
      apiPath === 'accounting/hostings/1/cycles/create/'
      && method === 'POST'
    ) {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (createCycleError) {
        return {
          status: createCycleError.status,
          contentType: 'application/json',
          body: JSON.stringify({ detail: createCycleError.detail }),
        };
      }
      const cycle = {
        ...BACKFILL_CYCLE,
        id: 50,
        paid_at: body.paid_at,
        amount: String(body.amount),
        is_backfill: false,
        cycles_represented: 1,
        notes: body.notes || '',
      };
      state.cycles = [cycle, ...state.cycles];
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          cycle,
          hosting: {
            ...hostingRows({ billingSent: state.billingSent })[0],
            cycles_count: state.cycles.length,
          },
        }),
      };
    }
    if (
      apiPath === 'accounting/hostings/1/cycles/10/delete/'
      && method === 'DELETE'
    ) {
      calls.push({ apiPath, method });
      state.cycles = state.cycles.filter((cycle) => cycle.id !== 10);
      return { status: 204, contentType: 'application/json', body: '' };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  };
}

export async function gotoHostings(page) {
  await page.goto('/es/panel', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('panel-sidebar').getByRole('link', { name: 'Hostings', exact: true }).first().click();
  await expect(
    page.getByRole('heading', { name: 'Hostings', exact: true }),
  ).toBeVisible({ timeout: 25_000 });
  await expect(page.getByTestId('accounting-row-1')).toBeVisible();
}

/** Every hosting action lives in the row's three-dot menu, at every width. */
export function openHostingMenu(page, id) {
  return openRowMenu(page, { kebab: `hosting-actions-${id}`, menu: 'hosting-actions-modal' });
}

export function chooseHostingAction(page, id, action) {
  return chooseRowAction(page, {
    kebab: `hosting-actions-${id}`,
    menu: 'hosting-actions-modal',
    action: `hosting-${action}-${id}`,
  });
}
