/**
 * E2E tests for admin Web App Diagnostics — send initial and send final flows.
 *
 * Covers: edit page renders 4 tabs; status-conditional action buttons
 * trigger the correct API transition endpoints.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_DIAGNOSTIC_SEND_INITIAL,
  ADMIN_DIAGNOSTIC_SEND_FINAL,
  ADMIN_DIAGNOSTIC_MARK_IN_ANALYSIS,
} from '../helpers/flow-tags.js';

const authOk = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

function buildMockDiagnostic(overrides = {}) {
  return {
    id: 7,
    uuid: '7777-8888-9999-aaaa',
    title: 'Diagnóstico — TechCorp',
    status: 'draft',
    language: 'es',
    client: { name: 'TechCorp', email: 'tech@corp.com' },
    client_name: 'TechCorp',
    investment_amount: null,
    currency: 'COP',
    payment_terms: {},
    duration_label: '',
    size_category: '',
    radiography: {},
    view_count: 0,
    last_viewed_at: null,
    documents: [],
    attachments: [],
    public_url: '/diagnostic/7777-8888-9999-aaaa',
    ...overrides,
  };
}

function buildHandler(diagnostic, overrides = {}) {
  return async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return authOk;
    if (apiPath === `diagnostics/${diagnostic.id}/detail/`) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(diagnostic),
      };
    }
    for (const [path, response] of Object.entries(overrides)) {
      if (apiPath === path && (!response.method || response.method === method)) {
        return response;
      }
    }
    return null;
  };
}

test.describe('Admin Diagnostic — Send Flows', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  test('edit page renders all navigation tabs', {
    tag: [...ADMIN_DIAGNOSTIC_SEND_INITIAL, '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (edit-page render smoke; the send-initial action is covered by the send test below)
    const diagnostic = buildMockDiagnostic({ status: 'negotiating' });
    await mockApi(page, buildHandler(diagnostic));

    await page.goto('/panel/diagnostics/7/edit');
    await expect(page.getByRole('tab', { name: 'General', exact: true })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('tab', { name: 'Secciones' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Prompt diagnóstico' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'JSON' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Actividad' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Analytics' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Correos' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Documentos' })).toBeVisible();
  });

  for (const initialExpiry of [null, '2026-12-15T15:20:01Z']) {
    test(`shows ${initialExpiry ? 'the preset' : 'the new'} expiration after the initial send`, {
      tag: [...ADMIN_DIAGNOSTIC_SEND_INITIAL, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const diagnostic = buildMockDiagnostic({ expires_at: initialExpiry, days_remaining: initialExpiry ? 20 : null });
      const savedExpiry = initialExpiry || '2026-12-10T13:37:19.477Z';
      let sends = 0;

      await mockApi(page, async ({ apiPath, method }) => {
        if (apiPath === 'auth/check/') return authOk;
        if (apiPath === 'diagnostics/7/detail/') {
          return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnostic) };
        }
        if (apiPath === 'diagnostics/7/scorecard/') {
          return {
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              score: 9,
              checks: [
                { key: 'client_email', label: 'Email del cliente', passed: true, blocker: true },
                { key: 'client_phone', label: 'Teléfono del cliente (para WhatsApp)', passed: false, blocker: false },
              ],
              blockers: [],
              can_send: true,
              total_checks: 2,
              passed_checks: 1,
            }),
          };
        }
        if (apiPath === 'diagnostics/7/send-initial/' && method === 'POST') {
          sends += 1;
          Object.assign(diagnostic, { status: 'sent', expires_at: savedExpiry, days_remaining: 20 });
          return {
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(diagnostic),
          };
        }
        return null;
      });

      await page.goto('/panel/diagnostics/7/edit');
      const expiry = page.getByLabel('Vigencia de la propuesta');
      await expect(expiry).toHaveValue(initialExpiry?.slice(0, 16) || '');
      await expect(page.getByRole('button', { name: /enviar envío inicial/i })).toBeVisible({ timeout: 15000 });
      await page.getByRole('button', { name: /enviar envío inicial/i }).click();
      await expect(page.getByTestId('diagnostic-scorecard-modal')).toBeVisible();
      await page.getByTestId('scorecard-send-btn').click();

      await expect(page.getByTestId('diagnostic-scorecard-modal')).not.toBeVisible();
      await expect(expiry).toHaveValue(savedExpiry.slice(0, 16));
      await expect(page.getByTestId('diagnostic-expiration-chip')).toHaveText('Vence en 20 d');
      expect(sends).toBe(1);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await expect(expiry).toHaveValue(savedExpiry.slice(0, 16));
      await expect(page.getByTestId('diagnostic-expiration-chip')).toHaveText('Vence en 20 d');
    });
  }

  test('a failed initial send keeps the scorecard modal open with a fallback error', {
    // Bug this catches: a send failure that still dismisses the scorecard
    // modal, hiding the fact the diagnostic was never actually sent.
    tag: [...ADMIN_DIAGNOSTIC_SEND_INITIAL, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const diagnostic = buildMockDiagnostic({ status: 'draft' });

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authOk;
      if (apiPath === 'diagnostics/7/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnostic) };
      }
      if (apiPath === 'diagnostics/7/scorecard/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            score: 9,
            checks: [{ key: 'client_email', label: 'Email del cliente', passed: true, blocker: true }],
            blockers: [],
            can_send: true,
            total_checks: 1,
            passed_checks: 1,
          }),
        };
      }
      if (apiPath === 'diagnostics/7/send-initial/' && method === 'POST') {
        return { status: 400, contentType: 'application/json', body: '{}' };
      }
      return null;
    });

    await page.goto('/panel/diagnostics/7/edit');
    await expect(page.getByRole('button', { name: /enviar envío inicial/i })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: /enviar envío inicial/i }).click();

    const modal = page.getByTestId('diagnostic-scorecard-modal');
    await expect(modal).toBeVisible();
    await page.getByTestId('scorecard-send-btn').click();

    const toast = page.getByRole('alert').filter({ hasText: 'No se pudo enviar el diagnóstico.' });
    await expect(toast).toBeVisible({ timeout: 10000 });
    // The modal STAYS visible — a failed send must not look like a sent one.
    await expect(modal).toBeVisible();
    await expect(page.getByLabel('Vigencia de la propuesta')).toHaveValue('');
  });

  test('"Marcar en análisis" button POSTs to mark-in-analysis/ when initial has been sent', {
    tag: [...ADMIN_DIAGNOSTIC_MARK_IN_ANALYSIS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const diagnostic = buildMockDiagnostic({
      status: 'sent',
      initial_sent_at: '2026-04-16T10:00:00Z',
      final_sent_at: null,
      available_transitions: ['negotiating'],
    });
    let called = false;

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authOk;
      if (apiPath === 'diagnostics/7/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnostic) };
      }
      if (apiPath === 'diagnostics/7/mark-in-analysis/' && method === 'POST') {
        called = true;
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(buildMockDiagnostic({ status: 'negotiating' })),
        };
      }
      return null;
    });

    await page.goto('/panel/diagnostics/7/edit');
    await expect(page.getByTestId('diagnostic-next-action-analyze')).toBeVisible({ timeout: 15000 });
    await page.getByTestId('diagnostic-next-action-analyze').click();
    await page.getByRole('button', { name: 'Confirmar', exact: true }).click();

    await expect(() => expect(called).toBe(true)).toPass({ timeout: 5000 });
  });

  test('"Enviar diagnóstico final" button POSTs to send-final/ in NEGOTIATING state', {
    tag: [...ADMIN_DIAGNOSTIC_SEND_FINAL, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const diagnostic = buildMockDiagnostic({ status: 'negotiating' });
    let called = false;

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authOk;
      if (apiPath === 'diagnostics/7/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnostic) };
      }
      if (apiPath === 'diagnostics/7/scorecard/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            score: 9,
            checks: [
              { key: 'client_email', label: 'Email del cliente', passed: true, blocker: true },
              { key: 'client_phone', label: 'Teléfono del cliente (para WhatsApp)', passed: false, blocker: false },
            ],
            blockers: [],
            can_send: true,
            total_checks: 2,
            passed_checks: 1,
          }),
        };
      }
      if (apiPath === 'diagnostics/7/send-final/' && method === 'POST') {
        called = true;
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(buildMockDiagnostic({
            status: 'sent', final_sent_at: '2026-04-16T10:00:00Z',
          })),
        };
      }
      return null;
    });

    await page.goto('/panel/diagnostics/7/edit');
    await expect(page.getByRole('button', { name: /enviar diagnóstico final/i })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: /enviar diagnóstico final/i }).click();
    await expect(page.getByTestId('diagnostic-scorecard-modal')).toBeVisible();
    await page.getByTestId('scorecard-send-btn').click();

    await expect(() => expect(called).toBe(true)).toPass({ timeout: 5000 });
    // the scorecard modal dismisses once the send resolves
    await expect(page.getByTestId('diagnostic-scorecard-modal')).not.toBeVisible();
  });

  test('a failed final send keeps the scorecard modal open with a fallback error', {
    // Bug this catches: same class as the initial-send failure, on the
    // NEGOTIATING → final transition specifically.
    tag: [...ADMIN_DIAGNOSTIC_SEND_FINAL, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const diagnostic = buildMockDiagnostic({ status: 'negotiating' });

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authOk;
      if (apiPath === 'diagnostics/7/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnostic) };
      }
      if (apiPath === 'diagnostics/7/scorecard/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            score: 9,
            checks: [{ key: 'client_email', label: 'Email del cliente', passed: true, blocker: true }],
            blockers: [],
            can_send: true,
            total_checks: 1,
            passed_checks: 1,
          }),
        };
      }
      if (apiPath === 'diagnostics/7/send-final/' && method === 'POST') {
        return { status: 400, contentType: 'application/json', body: '{}' };
      }
      return null;
    });

    await page.goto('/panel/diagnostics/7/edit');
    await expect(page.getByRole('button', { name: /enviar diagnóstico final/i })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: /enviar diagnóstico final/i }).click();

    const modal = page.getByTestId('diagnostic-scorecard-modal');
    await expect(modal).toBeVisible();
    await page.getByTestId('scorecard-send-btn').click();

    const toast = page.getByRole('alert').filter({ hasText: 'No se pudo enviar el diagnóstico.' });
    await expect(toast).toBeVisible({ timeout: 10000 });
    await expect(modal).toBeVisible();
  });
});
