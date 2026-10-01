/**
 * E2E tests for platform hosting subscription flow.
 *
 * @flow:platform-hosting-subscription
 * Covers: hosting plan selection (client), subscription activation, payment via mocked Wompi,
 *         Netflix-style active state, admin read-only view.
 *         Wompi payment endpoints are mocked — no real transactions.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_HOSTING_SUBSCRIPTION } from '../helpers/flow-tags.js';
import {
  setPlatformAuth,
  mockPlatformAdmin,
  mockPlatformClient,
} from '../helpers/platform-auth.js';

const mockProject = {
  id: 1, name: 'E-commerce Platform', status: 'active', progress: 33,
  client_id: 9002, client_name: 'Client E2E', client_email: 'client@e2e-test.com',
  client_company: 'ACME Corp', proposal_id: 1, proposal_title: 'Propuesta E-commerce',
  start_date: '2025-01-01', estimated_end_date: '2025-06-30',
  hosting_start_date: '2025-04-01',
  hosting_tiers: [
    { frequency: 'nine_month', months: 9, label: 'Cada 9 meses', badge: 'Máximo descuento', discount_percent: 40, base_monthly: 250000, effective_monthly: 150000, billing_amount: 1350000, currency: 'COP' },
    { frequency: 'semiannual', months: 6, label: 'Semestral', badge: '20% dcto', discount_percent: 20, base_monthly: 250000, effective_monthly: 200000, billing_amount: 1200000, currency: 'COP' },
    { frequency: 'quarterly', months: 3, label: 'Trimestral', badge: '10% dcto', discount_percent: 10, base_monthly: 250000, effective_monthly: 225000, billing_amount: 675000, currency: 'COP' },
  ],
  payment_milestones: [],
  has_subscription: false,
};

// Use dynamic dates so the subscriptionUpToDate getter works regardless of when tests run
function futureDate(daysFromNow) {
  const d = new Date(); d.setDate(d.getDate() + daysFromNow);
  return d.toISOString().split('T')[0];
}
function pastDate(daysAgo) {
  const d = new Date(); d.setDate(d.getDate() - daysAgo);
  return d.toISOString().split('T')[0];
}

const mockSubscription = {
  id: 1, plan: 'quarterly', plan_display: 'Trimestral',
  base_monthly_amount: '250000.00', discount_percent: 10,
  effective_monthly_amount: '225000.00', billing_amount: '675000.00',
  status: 'active', status_display: 'Activa',
  start_date: pastDate(30), next_billing_date: futureDate(60),
  project_id: 1, project_name: 'E-commerce Platform',
  payments: [
    {
      id: 1, amount: '675000.00', description: 'Hosting Trimestral',
      billing_period_start: pastDate(30), billing_period_end: futureDate(60),
      due_date: pastDate(30), status: 'paid', paid_at: pastDate(30) + 'T12:00:00Z',
      wompi_payment_link_url: null, project_id: 1, project_name: 'E-commerce Platform',
    },
  ],
  created_at: pastDate(30) + 'T10:00:00Z', updated_at: pastDate(30) + 'T10:00:00Z',
};

// The hosting payments page builds its plan breakdown from project phases
// (GET projects/:id/phases/). Each phase carries its own hosting_tiers.
const mockPhases = [
  {
    id: 11, order: 1, hosting_start_date: pastDate(60), hosting_activated_at: pastDate(30) + 'T10:00:00Z',
    proposal: { id: 1, title: 'Fase 1 — Sitio base' },
    hosting_tiers: [
      { frequency: 'quarterly', months: 3, label: 'Trimestral', discount_percent: 10, base_monthly: 250000, monthly_equivalent: 225000, billing_amount: 675000 },
      { frequency: 'semiannual', months: 6, label: 'Semestral', discount_percent: 20, base_monthly: 250000, monthly_equivalent: 200000, billing_amount: 1200000 },
      { frequency: 'nine_month', months: 9, label: 'Cada 9 meses', discount_percent: 40, base_monthly: 250000, monthly_equivalent: 150000, billing_amount: 1350000 },
    ],
  },
];

const meResponse = (user) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(user) });

function setupMocksNoSubscription(page, { user }) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProject) };
    }
    if (apiPath === 'accounts/projects/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([mockProject]) };
    }
    if (apiPath === 'accounts/hosting/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([mockProject]) };
    }
    if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockPhases) };
    }
    if (apiPath === 'accounts/projects/1/subscription/' && method === 'GET') {
      return { status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'No hay suscripción.' }) };
    }
    if (apiPath === 'accounts/projects/1/subscription/' && method === 'POST') {
      return { status: 201, contentType: 'application/json', body: JSON.stringify(mockSubscription) };
    }
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
    }
    return null;
  });
}

function setupMocksWithSubscription(page, { user }) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...mockProject, has_subscription: true }) };
    }
    if (apiPath === 'accounts/projects/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([{ ...mockProject, has_subscription: true }]) };
    }
    if (apiPath === 'accounts/hosting/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([{ ...mockProject, has_subscription: true }]) };
    }
    if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockPhases) };
    }
    if (apiPath === 'accounts/projects/1/subscription/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockSubscription) };
    }
    if (apiPath === 'accounts/subscriptions/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([{ ...mockSubscription, pending_payments: 0 }]) };
    }
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
    }
    return null;
  });
}

async function navigateFromGlobalHostingToProject(page) {
  await page.goto('/en-us/platform/projects', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Hosting', exact: true }).click();
  await expect(page).toHaveURL(/\/en-us\/platform\/payments$/);
  const projectLink = page.getByTestId('billing-hosting-list').getByRole('link', { name: 'E-commerce Platform', exact: true });
  await expect(projectLink).toHaveCount(1);
  await projectLink.click();
  await expect(page).toHaveURL(/\/en-us\/platform\/projects\/1\/payments$/);
}

test.describe('Platform Hosting Subscription — Client selects plan', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformClient });
  });

  test('client sees hosting plan selection when no subscription exists', {
    // Bug this catches: a broken project row or Hosting link can make plan
    // selection unreachable even when the payments route itself still renders.
    tag: ['@flow:platform-hosting-subscription', '@outcome:display', '@module:platform', '@priority:P1', '@role:platform-client'],
  }, async ({ page }) => {
    await setupMocksNoSubscription(page, { user: mockPlatformClient });
    // quality: allow-deep-link (the authenticated platform root lands on the project list; this journey then clicks the project row and Hosting link through the UI)
    await navigateFromGlobalHostingToProject(page);

    await expect(page.getByRole('heading', { name: 'Activa tu plan de hosting' })).toHaveText('Activa tu plan de hosting');
    await expect(page.getByRole('button', { name: 'Trimestral', exact: true })).toHaveText('Trimestral');
    await expect(page.getByRole('button', { name: 'Semestral', exact: true })).toHaveText('Semestral');
    await expect(page.getByRole('button', { name: 'Cada 9 meses', exact: true })).toHaveText('Cada 9 meses');
  });

  test('client can select a plan and activate subscription', {
    tag: [...PLATFORM_HOSTING_SUBSCRIPTION, '@role:platform-client'],
  }, async ({ page }) => {
    await setupMocksNoSubscription(page, { user: mockPlatformClient });
    await navigateFromGlobalHostingToProject(page);
    await page.getByRole('heading', { name: 'Activa tu plan de hosting' }).waitFor({ state: 'visible', timeout: 30000 });

    await page.getByRole('button', { name: 'Trimestral' }).click();
    const activateBtn = page.getByRole('button', { name: /activar plan/i });
    await expect(activateBtn).toBeEnabled();
    await activateBtn.click();
  });

  test('selecting the nine-month plan recomputes the total and activates with plan:nine_month', {
    tag: [...PLATFORM_HOSTING_SUBSCRIPTION, '@role:platform-client'],
  }, async ({ page }) => {
    await setupMocksNoSubscription(page, { user: mockPlatformClient });
    await navigateFromGlobalHostingToProject(page);
    await page.getByRole('heading', { name: 'Activa tu plan de hosting' }).waitFor({ state: 'visible', timeout: 30000 });

    await page.getByRole('button', { name: 'Cada 9 meses', exact: true }).click();

    // Total recomputes to the nine-month billing amount (1.350.000 COP).
    await expect(page.getByRole('row').filter({ hasText: 'Total a pagar ahora' })).toContainText('1.350.000');
    const activateBtn = page.getByRole('button', { name: /activar plan cada 9 meses/i });
    await expect(activateBtn).toBeEnabled();

    const [req] = await Promise.all([
      page.waitForRequest((r) => r.url().includes('accounts/projects/1/subscription/') && r.method() === 'POST'),
      activateBtn.click(),
    ]);
    expect(req.postDataJSON()).toMatchObject({ plan: 'nine_month' });
  });

  test('activating a plan fails and re-enables the CTA with the fallback error', {
    // Bug this catches: an activation failure that leaves the CTA
    // permanently disabled, or fails to surface any error, leaving the
    // client stuck with no visible plan and no way to retry.
    tag: [...PLATFORM_HOSTING_SUBSCRIPTION, '@role:platform-client', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformClient);
      if (apiPath === 'accounts/projects/1/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProject) };
      }
      if (apiPath === 'accounts/projects/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([mockProject]) };
      }
      if (apiPath === 'accounts/hosting/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([mockProject]) };
      }
      if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockPhases) };
      }
      if (apiPath === 'accounts/projects/1/subscription/' && method === 'GET') {
        return { status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'No hay suscripción.' }) };
      }
      if (apiPath === 'accounts/projects/1/subscription/' && method === 'POST') {
        // No `detail` body — exercises the fallback message branch.
        return { status: 500, contentType: 'application/json', body: '{}' };
      }
      if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
      }
      return null;
    });

    await navigateFromGlobalHostingToProject(page);
    await page.getByRole('heading', { name: 'Activa tu plan de hosting' }).waitFor({ state: 'visible', timeout: 30000 });

    await page.getByRole('button', { name: 'Trimestral' }).click();
    const activateBtn = page.getByRole('button', { name: /activar plan/i });
    await expect(activateBtn).toBeEnabled();
    await activateBtn.click();

    await expect(page.getByText('Error activando el plan de hosting.')).toBeVisible({ timeout: 10000 });
    // The CTA re-enables — the client is not stuck with a permanently
    // disabled button and no way to retry.
    await expect(activateBtn).toBeEnabled();
  });

  test('a pending subscription keeps the frequency editable and re-persists on change', {
    // Bug this catches: the frequencyEditable gate regressing so a PENDING
    // subscription's frequency becomes locked (the client could never fix a
    // wrong initial pick before the first payment settles).
    tag: ['@outcome:success', ...PLATFORM_HOSTING_SUBSCRIPTION, '@role:platform-client'],
  }, async ({ page }) => {
    const mockPendingSubscription = {
      ...mockSubscription,
      status: 'pending',
      status_display: 'Pendiente',
      has_payment_source: false,
    };
    let patchBody = null;

    await mockApi(page, async ({ apiPath, method, route }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformClient);
      if (apiPath === 'accounts/projects/1/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...mockProject, has_subscription: true }) };
      }
      if (apiPath === 'accounts/projects/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([{ ...mockProject, has_subscription: true }]) };
      }
      if (apiPath === 'accounts/hosting/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([{ ...mockProject, has_subscription: true }]) };
      }
      if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockPhases) };
      }
      if (apiPath === 'accounts/projects/1/subscription/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockPendingSubscription) };
      }
      // The frequency pill click persists via PATCH while the subscription
      // is pending — must be mocked or the click hits an unhandled route.
      if (apiPath === 'accounts/projects/1/subscription/' && method === 'PATCH') {
        patchBody = route.request().postDataJSON();
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...mockPendingSubscription, ...patchBody }) };
      }
      if (apiPath === 'accounts/subscriptions/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([{ ...mockPendingSubscription, pending_payments: 1 }]) };
      }
      if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
      }
      return null;
    });

    // quality: allow-deep-link (arrives via projects list -> project row click -> Hosting tab click, mirroring platform-client-documents.spec.js's accepted entry pattern; not a deep link straight to /payments)
    await navigateFromGlobalHostingToProject(page);
    await page.getByRole('heading', { name: /hosting trimestral/i }).waitFor({ state: 'visible', timeout: 30000 });

    // Unlike the active-subscription display test below, the frequency
    // pills ARE visible while pending.
    const nineMonthPill = page.getByRole('button', { name: 'Cada 9 meses', exact: true });
    await expect(nineMonthPill).toBeVisible();

    await Promise.all([
      page.waitForRequest((r) => r.url().includes('accounts/projects/1/subscription/') && r.method() === 'PATCH'),
      nineMonthPill.click(),
    ]);

    expect(patchBody).toMatchObject({ plan: 'nine_month' });
    // The breakdown total recomputes to the nine-month billing amount from the
    // mocked phase tiers (content-bearing, not just a visibility check).
    await expect(page.getByRole('row').filter({ hasText: 'Total cada 9 meses' })).toContainText('1.350.000');
  });

  test('active subscription shows auto-renewal up-to-date card', {
    // Bug this catches: navigation can reach a stale page that omits the
    // active subscription and automatic-renewal state for the client.
    tag: ['@flow:platform-hosting-subscription', '@outcome:display', '@module:platform', '@priority:P1', '@role:platform-client'],
  }, async ({ page }) => {
    await setupMocksWithSubscription(page, { user: mockPlatformClient });
    // quality: allow-deep-link (the authenticated platform root lands on the project list; this journey then clicks the project row and Hosting link through the UI)
    await navigateFromGlobalHostingToProject(page);

    await expect(page.getByRole('heading', { name: 'Hosting Trimestral' })).toHaveText('Hosting Trimestral');
    await expect(page.getByText('Activa', { exact: true })).toHaveText('Activa');
    await expect(page.getByText(/se renueva y cobra automáticamente/i)).toContainText('Se renueva y cobra automáticamente');
  });
});

test.describe('Platform Hosting Subscription — Admin view', () => {
  test.setTimeout(60_000);

  test('admin sees waiting message when no subscription exists', {
    // Bug this catches: admin navigation may reach Hosting without the
    // per-phase tier table or the no-subscription status for that client.
    tag: ['@flow:platform-hosting-subscription', '@outcome:display', '@module:platform', '@priority:P1', '@role:platform-admin'],
  }, async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
    await setupMocksNoSubscription(page, { user: mockPlatformAdmin });
    // quality: allow-deep-link (the authenticated platform root lands on the project list; this journey then clicks the project row and Hosting link through the UI)
    await navigateFromGlobalHostingToProject(page);

    await expect(page.getByRole('cell', { name: 'Trimestral', exact: true })).toHaveText('Trimestral');
    await expect(page.getByText('El cliente aún no ha activado su plan de hosting.')).toHaveText('El cliente aún no ha activado su plan de hosting.');
    await expect(page.getByRole('button', { name: /activar plan/i })).not.toBeVisible();
  });

  test('admin sees subscription status when active', {
    // Bug this catches: an admin can navigate to Hosting but lose the active
    // subscription summary, masking a client's billing state.
    tag: ['@flow:platform-hosting-subscription', '@outcome:display', '@module:platform', '@priority:P1', '@role:platform-admin'],
  }, async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
    await setupMocksWithSubscription(page, { user: mockPlatformAdmin });
    // quality: allow-deep-link (the authenticated platform root lands on the project list; this journey then clicks the project row and Hosting link through the UI)
    await navigateFromGlobalHostingToProject(page);

    await expect(page.getByRole('heading', { name: 'Hosting Trimestral' })).toHaveText('Hosting Trimestral');
    await expect(page.getByText('Activa', { exact: true })).toHaveText('Activa');
  });
});
