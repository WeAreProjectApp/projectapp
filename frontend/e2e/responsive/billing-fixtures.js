import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { mockPlatformClient, setPlatformAuth } from '../helpers/platform-auth.js';

export const project = { id: 1, name: 'Proyecto Aurora', status: 'active', progress: 50 };
export const contractAccount = {
  id: 42, title: 'Implementación fase dos', public_number: 'PA-AUR-001',
  commercial_status: 'issued', currency: 'COP', total: '120000.00', due_date: '2026-10-15',
  project_id: 1, project_name: project.name, is_overdue: false,
  context: { nature: 'contract', contract: { id: 10, title: 'Contrato Aurora' }, amendment: { id: 11, title: 'Otrosí fase dos' } },
};
export const hostingAccount = {
  id: 43, title: 'Hosting octubre', public_number: 'PA-AUR-H-002',
  commercial_status: 'issued', currency: 'COP', total: '55000.00', due_date: '2026-10-20',
  project_id: 1, project_name: project.name, is_overdue: false,
  context: { nature: 'hosting', contract: null, amendment: null },
};

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });

function detail(row) {
  return {
    ...row, issue_date: '2026-10-01', subtotal: row.total, discount_total: '0.00', tax_total: '0.00',
    collection_account: { billing_concept: row.title, observations: 'Documento emitido.' },
    items: [{ id: row.id, description: row.title, quantity: 1, unit_price: row.total, line_total: row.total }],
    payment_methods: [],
  };
}

export async function setupPlatformBilling(page) {
  await setPlatformAuth(page, { user: mockPlatformClient });
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(mockPlatformClient);
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') return json({ unread_count: 0 });
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([project]);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') return json(project);
    if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') return json([]);
    if (apiPath === 'accounts/projects/1/subscription/' && method === 'GET') return json(null);
    if (apiPath === 'accounts/hosting/' && method === 'GET') return json([project]);
    if (apiPath === 'accounts/projects/1/hosting-context/' && method === 'GET') return json({
      has_hosting: true, reconciliation_required: true,
      subscription: { status: 'active', plan: 'semiannual', billing_amount: '330000.00', payments: [] },
      accounting_sources: [{ id: 30, domain_url: 'aurora.test', operational: true, associated: true, valid_from: '2026-10-01', valid_to: '2027-04-01', payment_modality: 'semiannual', payment_per_cycle: '330000.00', cycles: [{ id: 301, paid_at: '2026-10-01', period_to: '2027-04-01', amount: '330000.00' }] }],
      evidence_groups: [],
    });
    if (apiPath === 'accounts/collection-accounts/' && method === 'GET') {
      const nature = new URL(route.request().url()).searchParams.get('nature');
      if (nature === 'hosting') return json([hostingAccount]);
      return json([contractAccount, hostingAccount]);
    }
    if (apiPath === 'accounts/collection-accounts/42/' && method === 'GET') return json(detail(contractAccount));
    if (apiPath === 'accounts/collection-accounts/42/pdf/' && method === 'GET') return {
      status: 200, contentType: 'application/pdf', headers: { 'content-disposition': 'attachment; filename="PA-AUR-001.pdf"' }, body: '%PDF-1.4 account',
    };
    return null;
  });
}

export async function setupPanelBilling(page) {
  await setAuthLocalStorage(page, { token: 'responsive-billing-token', userAuth: { id: 1, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'accounting/collection-accounts/42/' && method === 'GET') return json({ ...contractAccount, project_id: 7 });
    if (apiPath === 'admin/billing-context/accounts/42/' && method === 'GET') return json({ version: 3, nature: 'contract', contract: { id: 10, title: 'Contrato Aurora' }, amendment: { id: 11, title: 'Otrosí permitido' }, hosting_id: null });
    if (apiPath === 'admin/billing-context/projects/7/options/' && method === 'GET') return json({ project_id: 7, project_name: project.name, hosting_id: 70, contracts: [{ id: 10, title: 'Contrato Aurora', amendments: [{ id: 11, title: 'Otrosí permitido' }] }] });
    if (apiPath === 'admin/billing-context/accounts/42/' && method === 'PATCH') return json({ version: 4, nature: 'contract', contract: { id: 10, title: 'Contrato Aurora' }, amendment: { id: 11, title: 'Otrosí permitido' }, hosting_id: null });
    if (apiPath === 'admin/billing-context/projects/7/hosting/' && method === 'GET') return json({
      inventory: {
        version: 4, project_name: project.name, hosting: { subscription_id: null, hosting_record_ids: [], operational_record_id: null },
        subscriptions: [{ id: 90, plan: 'semiannual', status: 'active', billing_amount: '330000.00' }],
        accounting_sources: [{ id: 30, domain_url: 'aurora.test', payment_modality: 'semiannual', payment_per_cycle: '330000.00', mapped_hosting_id: null, conflicts: [] }],
        pending_account_ids: [42], hosting_accounts: [{ id: 42, public_number: contractAccount.public_number, total: contractAccount.total, commercial_status: 'issued' }], events: [],
      },
      overview: { subscription: { associated: false, payments: [] }, accounting_sources: [{ id: 30, cycles: [] }], evidence_groups: [] },
    });
    if (apiPath === 'admin/billing-context/projects/7/hosting/' && method === 'POST') return json({ decision: 'ready', selected: [90, 30] });
    return null;
  });
}
