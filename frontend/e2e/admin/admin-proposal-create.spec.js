/**
 * E2E tests for admin proposal creation flow.
 *
 * Covers: manual form fill + submit (verifying API payload),
 * JSON import tab toggle, validation on empty required fields.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { fillRichTextSource } from '../helpers/editorial.js';
import { ADMIN_PROPOSAL_CREATE, ADMIN_PROPOSAL_CREATE_FROM_JSON, ADMIN_PROPOSAL_CREATE_AND_SEND, ADMIN_PROPOSAL_CREATE_PREVIEW } from '../helpers/flow-tags.js';

const NEW_PROPOSAL_ID = 99;

const mockCreatedProposal = {
  id: NEW_PROPOSAL_ID,
  uuid: '99999999-9999-9999-9999-999999999999',
  title: 'Nueva Propuesta Web',
  client_name: 'Carlos López',
  client_email: 'carlos@test.com',
  email_intro: 'Esta propuesta resuelve el proceso manual para acelerar las ventas.',
  status: 'draft',
  sections: [],
  requirement_groups: [],
};

test.describe('Admin Proposal Create', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  test('renders proposal creation form with Importar JSON tab active by default', {
    tag: [...ADMIN_PROPOSAL_CREATE, '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the create page renders its three mode tabs with JSON active by default; the create interactions are covered by the tests below)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      return null;
    });
    await page.goto('/panel/proposals/create');

    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    // All three tab buttons visible
    await expect(page.getByRole('button', { name: 'Importar JSON' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Prompt IA' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Manual' })).toBeVisible();
    // JSON tab is active by default — textarea is rendered
    await expect(page.getByPlaceholder(/general/)).toBeVisible();
    // Manual mode form is not rendered
    await expect(page.getByLabel('Nombre')).not.toBeVisible();
  });

  test('fills manual form and submits, verifying API payload', {
    tag: [...ADMIN_PROPOSAL_CREATE, '@role:admin'],
  }, async ({ page }) => {
    let capturedPayload = null;

    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === 'proposals/create/') {
        capturedPayload = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Manual' }).click();

    // Fill required fields
    await page.getByLabel('Título').fill('Nueva Propuesta Web');
    await page.getByLabel('Nombre').fill('Carlos López');
    await page.getByLabel('Email').fill('carlos@test.com');
    await fillRichTextSource(page.getByTestId('create-email-intro'),
      'Esta propuesta mejora la captación digital para generar nuevas ventas.',
    );

    // Submit form — wait for the API response
    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes('proposals/create/')),
      page.getByRole('button', { name: /Crear Propuesta/i }).click(),
    ]);
    await response.finished();

    // Verify payload captured
    expect(capturedPayload).not.toBeNull();
    expect(capturedPayload.title).toBe('Nueva Propuesta Web');
    expect(capturedPayload.client_name).toBe('Carlos López');
    expect(capturedPayload.client_email).toBe('carlos@test.com');
    expect(capturedPayload.email_intro).toBe(
      'Esta propuesta mejora la captación digital para generar nuevas ventas.',
    );
    expect(capturedPayload.text_formats).toEqual({ '/email_intro': 'markdown_html_v1' });
  });

  test('a rejected submit shows the field error and keeps the admin on the create page', {
    // Bug this catches: an invalid payload that still navigates the admin
    // away from create, losing the entered form data.
    tag: [...ADMIN_PROPOSAL_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === 'proposals/create/') {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ client_email: ['Ingresa un correo válido.'] }),
        };
      }
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Manual' }).click();

    // Fill required fields — deliberately NOT total_investment, so "Crear y
    // Enviar" stays hidden and only the plain submit button is present.
    await page.getByLabel('Título').fill('Propuesta Rechazada');
    await page.getByLabel('Nombre').fill('Cliente Rechazado');
    await page.getByLabel('Email').fill('cliente@test.com');

    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes('proposals/create/')),
      page.getByRole('button', { name: /Crear Propuesta/i }).click(),
    ]);
    await response.finished();

    await expect(page.getByText('client_email: Ingresa un correo válido.')).toBeVisible({ timeout: 10000 });
    // Stays on create — no redirect to an edit page that doesn't exist.
    await expect(page).toHaveURL(/\/panel\/proposals\/create$/);
  });

  test('switching from Manual to JSON import tab hides manual form and shows textarea', {
    tag: [...ADMIN_PROPOSAL_CREATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });

    // Start in Manual mode so we have something to switch FROM
    await page.getByRole('button', { name: 'Manual' }).click();
    await expect(page.getByLabel('Título')).toBeVisible();

    // Switch to JSON import tab
    await page.getByRole('button', { name: 'Importar JSON' }).click();

    // Manual form fields hidden, JSON textarea visible
    await expect(page.getByLabel('Título')).not.toBeVisible();
    await expect(page.getByPlaceholder(/general/)).toBeVisible();
  });

  test('successful creation redirects to the new proposal edit page', {
    tag: [...ADMIN_PROPOSAL_CREATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      if (apiPath === 'proposals/create/') return { status: 201, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      if (apiPath === `proposals/${NEW_PROPOSAL_ID}/detail/`) return { status: 200, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Manual' }).click();

    await page.getByLabel('Título').fill('Nueva Propuesta Web');
    await page.getByLabel('Nombre').fill('Carlos López');
    await page.getByLabel('Email').fill('carlos@test.com');

    // Submit and wait for API response
    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes('proposals/create/')),
      page.getByRole('button', { name: /Crear Propuesta/i }).click(),
    ]);
    await response.finished();

    // Post-creation interstitial modal appears — click "Ir a Editar"
    await expect(page.getByText('Propuesta creada')).toBeVisible({ timeout: 5000 });
    await page.getByRole('button', { name: 'Ir a Editar' }).click();

    // Should redirect to edit page
    await expect(page).toHaveURL(/\/panel\/proposals\/\d+\/edit/, { timeout: 15000 });
  });

  test('selecting "Otro" project type shows custom text input', {
    tag: [...ADMIN_PROPOSAL_CREATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      return null;
    });
    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Manual' }).click();
    await expect(page.getByLabel('Título')).toBeVisible();

    const customInput = page.getByPlaceholder('Especificar tipo de proyecto...');
    await expect(customInput).not.toBeVisible();

    // quality: allow-fragile-selector (project type select has no testid, identified by default option text)
    await page.locator('select').filter({ hasText: 'Sin definir' }).first().selectOption('other');
    await expect(customInput).toBeVisible();
  });
});

test.describe('Admin Proposal Create from JSON', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  const validJson = JSON.stringify({
    general: { clientName: 'Ana Martínez' },
    executiveSummary: { paragraphs: ['Resumen ejecutivo.'] },
    _meta: {
      optional_metadata: {
        email_intro: 'Esta propuesta centraliza la operación para reducir reprocesos.',
      },
    },
  });

  const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

  test('pasting valid JSON shows preview with client name and section count', {
    tag: [...ADMIN_PROPOSAL_CREATE_FROM_JSON, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });
    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });

    // JSON tab is active by default
    const textarea = page.getByPlaceholder(/general/);
    await expect(textarea).toBeVisible();
    await textarea.fill(validJson);
    await textarea.dispatchEvent('input');

    await expect(page.getByText('Ana Martínez')).toContainText('Ana Martínez');
    await expect(page.getByText('Datos de la propuesta')).toBeVisible();
  });

  test('pasting JSON without general key shows validation error', {
    tag: ['@outcome:error', ...ADMIN_PROPOSAL_CREATE_FROM_JSON, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });
    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });

    const textarea = page.getByPlaceholder(/general/);
    await expect(textarea).toBeVisible();
    await textarea.fill(JSON.stringify({ executiveSummary: {} }));
    await textarea.dispatchEvent('input');

    await expect(page.getByText(/general.*clientName/i)).toContainText(/general.*clientName/i);
  });

  test('pasting invalid JSON shows syntax error', {
    tag: ['@outcome:error', ...ADMIN_PROPOSAL_CREATE_FROM_JSON, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });
    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });

    const textarea = page.getByPlaceholder(/general/);
    await expect(textarea).toBeVisible();
    await textarea.fill('{ invalid json }');
    await textarea.dispatchEvent('input');

    await expect(page.getByText('JSON inválido')).toContainText('JSON inválido');
  });

  test('importing JSON does not override the configured expiration default', {
    tag: [...ADMIN_PROPOSAL_CREATE_FROM_JSON, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath.startsWith('proposals/defaults/')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ language: 'es', expiration_days: 21, sections_json: [] }) };
      }
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });

    const textarea = page.getByPlaceholder(/general/);
    await expect(textarea).toBeVisible();
    await textarea.fill(JSON.stringify({
      general: { clientName: 'Diego Ramírez' },
      executiveSummary: { paragraphs: ['Resumen.'] },
      _meta: { optional_metadata: { expires_at: new Date(Date.now() + 29 * 24 * 60 * 60 * 1000).toISOString() } },
    }));
    await textarea.dispatchEvent('input');

    // The "Datos de la propuesta" section (with the expiration field) renders after parsing
    await expect(page.getByText('Datos de la propuesta')).toBeVisible();
    // Expiration must stay at the configured default (21), not the JSON's 29 days
    await expect(page.getByTestId('json-expires-days')).toHaveValue('21');
  });

  test('submitting valid JSON creates proposal and redirects to edit page', {
    tag: [...ADMIN_PROPOSAL_CREATE_FROM_JSON, '@role:admin'],
  }, async ({ page }) => {
    let capturedPayload = null;

    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'proposals/create-from-json/') {
        capturedPayload = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      if (apiPath === `proposals/${NEW_PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });

    const textarea = page.getByPlaceholder(/general/);
    await expect(textarea).toBeVisible();
    await textarea.fill(validJson);
    await textarea.dispatchEvent('input');

    await expect(page.getByText('Datos de la propuesta')).toBeVisible();

    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes('proposals/create-from-json/')),
      page.getByRole('button', { name: /Crear desde JSON/i }).click(),
    ]);
    await response.finished();

    expect(capturedPayload).not.toBeNull();
    expect(capturedPayload.client_name).toBe('Ana Martínez');
    expect(capturedPayload.email_intro).toBe(
      'Esta propuesta centraliza la operación para reducir reprocesos.',
    );
    expect(capturedPayload.sections.general.clientName).toBe('Ana Martínez');

    // Post-creation interstitial modal appears — click "Ir a Editar"
    await expect(page.getByText('Propuesta creada')).toBeVisible({ timeout: 5000 });
    await page.getByRole('button', { name: 'Ir a Editar' }).click();

    await expect(page).toHaveURL(/\/panel\/proposals\/\d+\/edit/, { timeout: 15000 });
  });
});

test.describe('Admin Proposal Create & Send', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

  test('"Crear y Enviar" button appears when client data is complete', {
    tag: [...ADMIN_PROPOSAL_CREATE_AND_SEND, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });
    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Manual' }).click();
    await expect(page.getByLabel('Título')).toBeVisible();

    // Button should not be visible initially
    await expect(page.getByRole('button', { name: /Crear y Enviar/i })).not.toBeVisible();

    // Fill required fields for direct send
    await page.getByLabel('Título').fill('Propuesta Directa');
    await page.getByLabel('Nombre').fill('Ana Test');
    await page.getByLabel('Email').fill('ana@test.com');
    await page.getByPlaceholder('3.500.000').fill('5000000');

    // Client and investment are insufficient until the send message exists.
    await expect(page.getByRole('button', { name: /Crear y Enviar/i })).not.toBeVisible();
    await fillRichTextSource(page.getByTestId('create-email-intro'),
      'Esta propuesta automatiza la operación para reducir reprocesos.',
    );

    await expect(page.getByRole('button', { name: /Crear y Enviar/i })).toBeVisible();
  });

  test('"Crear y Enviar" creates proposal, sends it, and redirects to edit page', {
    tag: [...ADMIN_PROPOSAL_CREATE_AND_SEND, '@role:admin'],
  }, async ({ page }) => {
    let sendCalled = false;

    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'proposals/create/') {
        return { status: 201, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      if (apiPath === `proposals/${NEW_PROPOSAL_ID}/send/`) {
        sendCalled = true;
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) };
      }
      if (apiPath === `proposals/${NEW_PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Manual' }).click();

    await page.getByLabel('Título').fill('Nueva Propuesta Web');
    await page.getByLabel('Nombre').fill('Carlos López');
    await page.getByLabel('Email').fill('carlos@test.com');
    await page.getByPlaceholder('3.500.000').fill('15000000');
    await fillRichTextSource(page.getByTestId('create-email-intro'),
      'Esta propuesta centraliza los pedidos para acelerar las entregas.',
    );

    await page.getByRole('button', { name: /Crear y Enviar/i }).click();

    // handleCreateAndSend creates + sends + redirects directly (no interstitial)
    // Wait for navigation to complete before asserting URL
    await page.waitForURL(/\/panel\/proposals\/\d+\/edit/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/panel\/proposals\/\d+\/edit/);
    expect(sendCalled).toBe(true);
  });

  test('"Crear y Enviar" surfaces a failed send instead of a silent success', {
    tag: [...ADMIN_PROPOSAL_CREATE_AND_SEND, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'proposals/create/') {
        return { status: 201, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      if (apiPath === `proposals/${NEW_PROPOSAL_ID}/send/`) {
        return { status: 400, contentType: 'application/json', body: JSON.stringify({ error: 'El cliente no tiene un correo válido.' }) };
      }
      if (apiPath === `proposals/${NEW_PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Manual' }).click();

    await page.getByLabel('Título').fill('Propuesta Sin Correo');
    await page.getByLabel('Nombre').fill('Laura Díaz');
    await page.getByLabel('Email').fill('laura@test.com');
    await page.getByPlaceholder('3.500.000').fill('8000000');
    await fillRichTextSource(page.getByTestId('create-email-intro'),
      'Esta propuesta elimina tareas manuales para responder más rápido.',
    );

    await page.getByRole('button', { name: /Crear y Enviar/i }).click();

    // The proposal DOES exist (create succeeded), so the admin still lands on
    // its edit view — but the failed send must be surfaced, never swallowed.
    await page.waitForURL(/\/panel\/proposals\/\d+\/edit/, { timeout: 15000 });
    await expect(page.getByText('Propuesta creada, pero el envío falló.')).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Admin Proposal Create Preview', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

  test('post-creation modal shows three action options', {
    tag: ['@outcome:success', '@outcome:display', ...ADMIN_PROPOSAL_CREATE_PREVIEW, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'proposals/create/') {
        return { status: 201, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Manual' }).click();

    await page.getByLabel('Título').fill('Nueva Propuesta Web');
    await page.getByLabel('Nombre').fill('Carlos López');
    await page.getByLabel('Email').fill('carlos@test.com');

    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes('proposals/create/')),
      page.getByRole('button', { name: /Crear Propuesta/i }).click(),
    ]);
    await response.finished();

    // Modal should appear with title and proposal name
    await expect(page.getByText('Propuesta creada')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Nueva Propuesta Web')).toBeVisible();

    // Should show "Ver Preview" link and "Ir a Editar" button
    await expect(page.getByText('Ver Preview')).toContainText('Ver Preview');
    await expect(page.getByRole('button', { name: 'Ir a Editar' })).toBeVisible();
  });

  test('post-creation modal shows "Enviar al Cliente" when client data is complete', {
    tag: ['@outcome:success', '@outcome:display', ...ADMIN_PROPOSAL_CREATE_PREVIEW, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'proposals/create/') {
        return { status: 201, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      return null;
    });

    await page.goto('/panel/proposals/create');
    await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Manual' }).click();

    await page.getByLabel('Título').fill('Nueva Propuesta Web');
    await page.getByLabel('Nombre').fill('Carlos López');
    await page.getByLabel('Email').fill('carlos@test.com');
    await page.getByPlaceholder('3.500.000').fill('15000000');
    await fillRichTextSource(page.getByTestId('create-email-intro'),
      'Esta propuesta centraliza el proceso para reducir tiempos de atención.',
    );

    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes('proposals/create/')),
      page.getByRole('button', { name: /Crear Propuesta/i }).click(),
    ]);
    await response.finished();

    await expect(page.getByText('Propuesta creada')).toBeVisible({ timeout: 5000 });
    // "Enviar al Cliente" button visible when canSendDirectly
    await expect(page.getByRole('button', { name: /Enviar al Cliente/i })).toContainText('Enviar al Cliente');
  });
});
