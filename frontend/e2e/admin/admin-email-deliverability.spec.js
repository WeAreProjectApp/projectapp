/**
 * E2E tests for admin email deliverability dashboard flow.
 *
 * @flow:admin-email-deliverability
 * Covers: browser history restores delivery stats; the former route renders
 *         the email status tab for staff without a page transition error.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_EMAIL_DELIVERABILITY } from '../helpers/flow-tags.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const mockDeliverabilityData = {
  total_emails_30d: 42,
  success_rate: 95.2,
  sent_count: 40,
  failed_count: 2,
  by_template: [
    { template_key: 'proposal_sent', total: 30, sent: 29, failed: 1, success_rate: 96.7 },
    { template_key: 'proposal_reminder', total: 12, sent: 11, failed: 1, success_rate: 91.7 },
  ],
  daily_trend: [
    { date: '2026-03-18', total: 5, failed: 0 },
    { date: '2026-03-19', total: 8, failed: 1 },
  ],
  recent_failures: [
    {
      template_key: 'proposal_sent', recipient: 'client@example.com',
      status: 'bounced', sent_at: '2026-03-18T09:00:00Z', error_message: 'Mailbox full',
    },
  ],
};

test.describe('Admin Email Deliverability Dashboard', () => {
  test.setTimeout(60_000);
  test.use({ viewport: { width: 1440, height: 900 } });

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true, is_superuser: false } });
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'email-deliverability/') return { status: 200, contentType: 'application/json', body: JSON.stringify(mockDeliverabilityData) };
      if (apiPath === 'emails/defaults/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ greeting: 'Hola', footer: 'Equipo', config: {}, defaults: {} }) };
      if (apiPath === 'emails/history/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [], total: 0, page: 1, has_next: false }) };
      if (apiPath === 'emails/copy-recipients/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [], families: [] }) };
      return null;
    });
  });

  test('restores email status after returning from the Dashboard', {
    tag: [...ADMIN_EMAIL_DELIVERABILITY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (Dashboard is the panel entry; reach email statistics through navigation clicks)
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Emails', exact: true }).click();
    await page.getByRole('tab', { name: 'Estado de los emails', exact: true }).click();
    await expect(page.getByText('client@example.com', { exact: true })).toBeVisible();
    await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
    await expect(page).toHaveURL(/\/es-co\/panel$/);
    await page.goBack({ waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/tab=status/);
    await expect(page.getByText('42', { exact: true }).first()).toHaveText('42');
    await expect(page.getByText('client@example.com', { exact: true })).toBeVisible();
  });

  test.describe('Former deliverability bookmark', () => {
    test.use({ viewport: { width: 2560, height: 1440 }, colorScheme: 'dark' });

    test('renders usable email status from the former staff bookmark', {
      tag: [...ADMIN_EMAIL_DELIVERABILITY, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const pageErrors = [];
      page.on('pageerror', error => pageErrors.push(error.message));

      // quality: allow-deep-link (the former staff bookmark is the compatibility entry under test)
      await page.goto('/es-co/panel/proposals/email-deliverability', { waitUntil: 'domcontentloaded' });

      await expect(page).toHaveURL(/\/es-co\/panel\/emails\?tab=status$/);
      await expect(page.getByRole('tab', { name: 'Estado de los emails', exact: true })).toHaveAttribute('aria-selected', 'true');
      await expect(page.getByText('42', { exact: true }).first()).toBeVisible();
      await expect(page.getByText('client@example.com', { exact: true })).toBeVisible();
      await page.getByRole('tab', { name: 'Historial', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Historial de correos enviados', exact: true })).toBeVisible();
      expect(pageErrors).toEqual([]);
    });
  });
});
