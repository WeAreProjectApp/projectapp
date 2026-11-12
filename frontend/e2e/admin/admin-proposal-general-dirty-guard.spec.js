import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_EDIT } from '../helpers/flow-tags.js';

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });
const notice = (page) => page.getByTestId('proposal-unsaved-notice');
const expiryDate = (page) => page.getByTestId('proposal-expiry-date');

function createProposal(overrides = {}) {
  return {
    id: 99226,
    uuid: '00000000-0000-4000-8000-000000099226',
    title: 'Propuesta PA-226',
    client_name: 'Cliente ficticio PA-226',
    client_email: 'pa226@example.test',
    client_phone: '',
    language: 'es',
    status: 'draft',
    total_investment: '5000000',
    currency: 'COP',
    view_count: 0,
    sent_at: null,
    is_active: true,
    reminder_days: 3,
    urgency_reminder_days: 15,
    proposal_source_hash: 'a'.repeat(64),
    sections: [],
    requirement_groups: [],
    change_logs: [],
    ...overrides,
  };
}

async function openGeneral(page, proposal, { failSave = false } = {}) {
  let savedProposal = { ...proposal };
  const updates = [];
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { id: 226, username: 'qa-admin', is_staff: true } });
    if (apiPath === `proposals/${proposal.id}/detail/`) return json(savedProposal);
    if (apiPath === 'proposals/') return json([savedProposal]);
    if (apiPath === `proposals/${proposal.id}/update/` && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      updates.push(payload);
      if (failSave) return json({ detail: 'No se pudo guardar la propuesta.' }, 500);
      savedProposal = { ...savedProposal, ...payload, proposal_source_hash: 'b'.repeat(64) };
      return json(savedProposal);
    }
    return null;
  });
  // quality: allow-deep-link (PA-226 reproduces a direct visit to the editor).
  await page.goto(`/es-co/panel/proposals/${proposal.id}/edit`, { waitUntil: 'domcontentloaded' });
  await expect(expiryDate(page)).toHaveValue(proposal.expires_at.slice(0, 16));
  return updates;
}

for (const fixture of [
  { name: 'expired proposal', status: 'expired', expires_at: '2026-10-15T14:30:00-05:00' },
  { name: 'future control', status: 'draft', expires_at: '2026-11-20T14:30:00-05:00' },
]) {
  test.describe(`General dirty guard — ${fixture.name}`, () => {
    test.setTimeout(60_000);
    test.use({ timezoneId: 'America/Bogota' });

    test.beforeEach(async ({ page }) => {
      await page.clock.setFixedTime(new Date('2026-11-06T15:00:00Z'));
      await setAuthLocalStorage(page, {
        token: 'e2e-admin-token',
        userAuth: { id: 226, role: 'admin', is_staff: true },
      });
    });

    // Catches hydration silently replacing the persisted expiry before any input.
    test('opens saved general data without protecting a clean exit', {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (PA-226 requires a clean direct opening of the editor).
      const proposal = createProposal(fixture);
      const updates = await openGeneral(page, proposal);

      await page.reload({ waitUntil: 'domcontentloaded' });
      await expect(expiryDate(page)).toHaveValue(proposal.expires_at.slice(0, 16));
      await expect(notice(page)).toBeHidden();
      await page.getByRole('link', { name: 'Volver a propuestas', exact: true }).click();

      await expect(page).toHaveURL(/\/panel\/proposals\/?$/);
      await expect(page.getByTestId('confirm-modal-confirm')).toBeHidden();
      expect(updates).toEqual([]);
    });

    test('clears the warning after restoring a general field', {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const proposal = createProposal(fixture);
      await openGeneral(page, proposal);
      const discount = page.getByTestId('general-finance-general-discount');

      await discount.fill('8');
      await expect(notice(page)).toContainText('Datos de la propuesta sin guardar');
      await discount.fill('0');

      await expect(notice(page)).toBeHidden();
      await expect(expiryDate(page)).toHaveValue(proposal.expires_at.slice(0, 16));
    });

    test('preserves a manually entered expiry near midnight', {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const proposal = createProposal(fixture);
      await openGeneral(page, proposal);

      await expiryDate(page).fill('2026-11-20T23:30');
      await expect(notice(page)).toBeVisible();
      await expect(page.getByTestId('proposal-expiry-days')).toHaveValue('14');
      await expect(expiryDate(page)).toHaveValue('2026-11-20T23:30');
      await expiryDate(page).fill(proposal.expires_at.slice(0, 16));

      await expect(notice(page)).toBeHidden();
    });

    test('tracks a real edit through the days control', {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const proposal = createProposal(fixture);
      await openGeneral(page, proposal);

      await page.getByTestId('proposal-expiry-days').fill('7');

      await expect(expiryDate(page)).toHaveValue('2026-11-13T14:30');
      await expect(notice(page)).toBeVisible();
      await expiryDate(page).fill(proposal.expires_at.slice(0, 16));
      await expect(notice(page)).toBeHidden();
    });

    test('persists a saved edit without rewriting an untouched expiry', {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const proposal = createProposal(fixture);
      const updates = await openGeneral(page, proposal);
      await page.getByTestId('general-finance-general-discount').fill('8');
      await expect(notice(page)).toBeVisible();

      await page.getByTestId('proposal-edit-submit').click();

      await expect(page.getByText('Propuesta actualizada.', { exact: true })).toBeVisible();
      await expect(notice(page)).toBeHidden();
      expect(updates).toEqual([{ discount_percent: 8, source_hash: proposal.proposal_source_hash }]);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('general-finance-general-discount')).toHaveValue('8');
      await expect(expiryDate(page)).toHaveValue(proposal.expires_at.slice(0, 16));
      await expect(notice(page)).toBeHidden();
    });

    test('protects the pending draft after a failed save', {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:failure'],
    }, async ({ page }) => {
      const proposal = createProposal(fixture);
      await openGeneral(page, proposal, { failSave: true });
      await page.getByTestId('general-finance-general-discount').fill('8');

      await page.getByTestId('proposal-edit-submit').click();

      await expect(page.getByText('Error al actualizar.', { exact: true })).toBeVisible();
      await expect(notice(page)).toBeVisible();
      await page.getByRole('link', { name: 'Volver a propuestas', exact: true }).click();
      await expect(page.getByTestId('confirm-modal-confirm')).toHaveText('Salir sin guardar');
      await page.getByRole('button', { name: 'Seguir editando', exact: true }).click();
      await expect(page.getByTestId('general-finance-general-discount')).toHaveValue('8');
      await expect(page).toHaveURL(new RegExp(`/panel/proposals/${proposal.id}/edit`));
    });
  });
}
