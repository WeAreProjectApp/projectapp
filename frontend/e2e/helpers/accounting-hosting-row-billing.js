import { gotoHostings, hostingRows } from './accounting-hosting-cycles.js';
import { mockApi } from './api.js';
import { setAuthLocalStorage } from './auth.js';

export const billingServices = [
  {
    id: 1, name: 'Alfa', project: 10, client: 71, canonical: 31, payment: 48,
    period: ['2026-04-01', '2026-06-30'], balance: '180000.00', amount: '240000.00', received: '60000.00',
  },
  {
    id: 2, name: 'Beta', project: 20, client: 72, canonical: 32, payment: null,
    period: ['2026-07-01', '2026-09-30'], balance: '45000.00', amount: '45000.00', received: '0.00',
  },
];

export function billingRow(service, billingSent = false) {
  const email = service.name.toLowerCase() + '@example.invalid';
  return {
    ...hostingRows({ billingSent })[0],
    id: service.id,
    project: service.project,
    project_id: service.project,
    client: service.client,
    client_name: 'Cliente ' + service.name,
    client_display_name: 'Cliente ' + service.name,
    project_name: 'Proyecto ' + service.name,
    display_label: 'Hosting ' + service.name,
    domain_url: service.name.toLowerCase() + '.example.invalid',
    client_email: email,
    billing_email: email,
    payment_per_cycle: '999999.00',
    payment_modality: 'quarterly',
    payment_modality_label: 'Trimestral',
  };
}

function billingContext(service) {
  return {
    overview: {
      project_id: service.project, hosting_id: service.canonical, reconciliation_required: false,
      accounting_sources: [{ id: service.id, associated: true, operational: true }],
    },
    selection: { requires_reconciliation: false, blockers: [] },
    billing_period: {
      project_id: service.project, project_hosting_id: service.canonical, hosting_record_id: service.id,
      client_id: service.client, currency: 'COP', period_start: service.period[0], period_end: service.period[1],
      source: service.payment ? 'subscription' : 'expected_income', hosting_payment_id: service.payment,
      income_id: service.payment ? null : 75, documents: [], amount: service.amount, received: service.received,
      balance: service.balance, state: service.payment ? 'partial' : 'pending', version: 'review-' + service.id,
    },
  };
}

const noRecipient = {
  ...hostingRows({ billingSent: false })[1],
  id: 3, client: null, client_name: 'Sin contacto', client_display_name: null, project: 30, project_id: 30,
  project_name: 'Proyecto Gamma', display_label: 'Hosting Gamma', domain_url: 'gamma.example.invalid',
  billing_email: '', client_email: '',
};

const json = (data, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(data) });

export async function openHostingBillingList(page, { conflict = false, wrongClient = false, emailSent = true } = {}) {
  const writes = [];
  const issued = new Set();
  const admin = { id: 9001, username: 'admin', role: 'admin', is_staff: true, is_superuser: true };
  await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: admin });
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: admin });
    if (apiPath === 'accounting/hostings/' && method === 'GET') {
      const rows = billingServices.map(service => billingRow(service, issued.has(service.id)));
      return json({ results: [...rows, noRecipient], meta: {} });
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);

    const service = billingServices.find(item => apiPath === `admin/billing-context/projects/${item.project}/hosting/`);
    if (service && method === 'GET') {
      const response = billingContext(service);
      if (wrongClient) response.billing_period.client_id = billingServices[1].client;
      return json(response);
    }
    if (method === 'GET' || !/^(accounting\/hostings\/|admin\/billing-context\/)/.test(apiPath)) return null;

    writes.push({ apiPath, method, body: route.request().postDataJSON() });
    const recipient = billingServices.find(item => apiPath === `accounting/hostings/${item.id}/send-collection-account/`);
    if (!recipient || method !== 'POST') return json({ detail: 'Acción inesperada.' }, 400);
    if (conflict) return json({ detail: 'El período cambió. Consulta de nuevo el período del servicio.' }, 400);
    issued.add(recipient.id);
    return json({ document: { id: 93, public_number: 'DEV-0093' }, email_sent: emailSent }, 201);
  });
  await gotoHostings(page);
  return writes;
}
