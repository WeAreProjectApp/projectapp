import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_CLIENT_EMAIL_COPY_HISTORY,
  ADMIN_CLIENT_EMAIL_COPY_SETTINGS,
  ADMIN_OUTBOUND_EMAIL_HISTORY_BODY,
  ADMIN_OUTBOUND_EMAIL_HISTORY_ATTACHMENTS,
  ADMIN_OUTBOUND_EMAIL_HISTORY_FILTER,
  ADMIN_OUTBOUND_EMAIL_HISTORY_RESEND,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const authCheck = json({
  user: { username: 'admin', is_staff: true, is_superuser: true },
});

const defaults = {
  greeting: 'Hola',
  footer: 'Quedamos atentos.',
  config: { greeting: 'Hola {client_name}', footer: 'Quedamos atentos.', signer: 'carlos' },
  defaults: { greeting: 'Hola {client_name}', footer: 'Quedamos atentos.', signer: 'carlos' },
  available_signers: [{ key: 'carlos', name: 'Carlos', role: 'CTO' }],
  available_variables: ['client_name'],
};

const families = [
  { value: 'proposals', label: 'Propuestas' },
  { value: 'diagnostics', label: 'Diagnósticos' },
  { value: 'documents_communications', label: 'Documentos y comunicaciones' },
  { value: 'collections', label: 'Cuentas de cobro' },
  { value: 'accounting', label: 'Contabilidad' },
  { value: 'platform', label: 'Plataforma' },
  { value: 'tasks_operations', label: 'Tareas y operación' },
  { value: 'security', label: 'Seguridad y acceso' },
];

const configuredRecipient = {
  id: 8,
  email: 'audit@projectapp.co',
  is_active: true,
  families: ['proposals', 'collections'],
  family_labels: ['Propuestas', 'Cuentas de cobro'],
};

const history = {
  results: [{
    id: 41,
    subject: 'Seguimiento contractual',
    recipient: 'client@example.com',
    status: 'sent',
    sent_at: '2026-08-23T10:00:00Z',
    template_key: 'verification_code_password_reset',
    template_label: 'Código de recuperación',
    family: 'security',
    family_label: 'Seguridad y acceso',
    audience: 'security',
    audience_label: 'Seguridad y acceso',
    has_body: true,
    metadata: { greeting: 'Hola Ana', sections: ['Adjuntamos el contrato.'] },
    copies: [{
      id: 42,
      recipient: 'audit@projectapp.co',
      status: 'failed',
      status_label: 'Fallido',
      error_message: 'SMTP timeout interno',
    }, {
      id: 43,
      recipient: 'client@example.com',
      status: 'skipped',
      status_label: 'Omitido',
      error_message: 'Ya era destinatario del correo principal.',
    }],
  }],
  total: 1,
  page: 1,
  has_next: false,
  attachment_type_options: [
    { value: 'business:collection_account', label: 'Cuenta de cobro', group: 'business' },
  ],
};

const exactHistory = {
  results: [{
    id: 51,
    subject: 'Cuenta de cobro agosto',
    recipient: 'cliente@example.com',
    to_recipients: [{ email: 'cliente@example.com', status: 'sent' }],
    cc_recipients: [{ email: 'contabilidad@example.com', status: 'sent' }],
    status: 'sent',
    sent_at: '2026-08-28T10:00:00Z',
    template_key: 'collection_account_client',
    template_label: 'Cuenta de cobro',
    family: 'collections',
    family_label: 'Cuentas de cobro',
    audience: 'client',
    audience_label: 'Al cliente',
    has_body: true,
    metadata: {},
    copies: [{
      id: 52,
      recipient: 'carlos18bp@gmail.com',
      status: 'sent',
      status_label: 'Enviado',
      error_message: '',
    }],
    snapshot_state: 'captured',
    snapshot_notice: '',
    has_attachments: true,
    attachment_count: 1,
    message_size_bytes: 1887436,
    attachment_size_bytes: 1048576,
    can_resend: true,
    attachments: [{
      id: 71,
      filename: 'cuenta-cobro-agosto.pdf',
      mime_type: 'application/pdf',
      size_bytes: 1048576,
      format_kind: 'pdf',
      format_label: 'PDF',
      business_kind: 'collection_account',
      business_kind_label: 'Cuenta de cobro',
      exact_available: true,
      source_document: { id: 72, title: 'Cuenta de cobro agosto' },
      download_url: '/api/emails/history/51/attachments/71/',
      preview_url: '/api/emails/history/51/attachments/71/?inline=1',
    }],
    links: {
      content: [{ url: 'https://projectapp.co/platform/payments/7', label: 'Pagar ahora', group: 'content' }],
      template: [{ url: 'https://projectapp.co', label: 'ProjectApp', group: 'template' }],
    },
  }, {
    id: 53,
    subject: 'Confirmación sin archivos',
    recipient: 'cliente@example.com',
    status: 'sent',
    sent_at: '2026-08-27T10:00:00Z',
    template_key: 'proposal_reminder',
    template_label: 'Recordatorio',
    family: 'proposals',
    family_label: 'Propuestas',
    audience: 'client',
    audience_label: 'Al cliente',
    has_body: true,
    metadata: {},
    copies: [],
    snapshot_state: 'captured',
    snapshot_notice: '',
    has_attachments: false,
    attachment_count: 0,
    message_size_bytes: 3200,
    attachment_size_bytes: 0,
    can_resend: true,
    attachments: [],
    links: { content: [], template: [] },
  }, {
    id: 54,
    subject: 'Histórico anterior',
    recipient: 'cliente@example.com',
    status: 'sent',
    sent_at: '2026-01-01T10:00:00Z',
    template_key: 'branded_email',
    template_label: 'Correo personalizado',
    family: 'documents_communications',
    family_label: 'Documentos y comunicaciones',
    audience: 'client',
    audience_label: 'Al cliente',
    has_body: true,
    metadata: { attachment_names: ['contrato-antiguo.pdf'] },
    copies: [],
    snapshot_state: 'legacy_partial',
    snapshot_notice: 'Este correo es anterior al archivo exacto.',
    has_attachments: true,
    attachment_count: 1,
    message_size_bytes: null,
    attachment_size_bytes: null,
    can_resend: false,
    attachments: [{
      id: null,
      filename: 'contrato-antiguo.pdf',
      format_label: 'Tipo no archivado',
      size_bytes: null,
      exact_available: false,
      source_document: null,
      download_url: '',
      preview_url: '',
    }],
    links: { content: [], template: [] },
  }],
  total: 3,
  page: 1,
  has_next: false,
  attachment_type_options: [
    { value: 'business:collection_account', label: 'Cuenta de cobro', group: 'business' },
    { value: 'format:pdf', label: 'PDF', group: 'format' },
  ],
};

async function setupMocks(page, options = {}) {
  let rows = [...(options.recipients ?? [configuredRecipient])];
  const calls = [];
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath.startsWith('proposals/client-profiles/search/')) return json([]);
    if (apiPath === 'panel/dashboard/') return json({});
    if (apiPath === 'emails/defaults/' && method === 'GET') return json(defaults);
    if (apiPath === 'emails/history/41/body/' && method === 'GET') {
      calls.push({ method, path: apiPath, url: route.request().url() });
      return json({
        html: '<html><body><p>Código privado 123456</p></body></html>',
        text: 'Código privado 123456',
      });
    }
    if (apiPath === 'emails/history/51/attachments/71/' && method === 'GET') {
      calls.push({ method, path: apiPath, url: route.request().url() });
      return {
        status: 200,
        contentType: 'application/pdf',
        headers: { 'Content-Disposition': 'inline; filename="cuenta-cobro-agosto.pdf"' },
        body: '%PDF-1.4 exact snapshot',
      };
    }
    if (apiPath === 'emails/history/51/resend/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      calls.push({ method, path: apiPath, payload });
      if (options.resendFailure) return json({ detail: 'SMTP temporalmente no disponible.' }, 502);
      return json({
        email_log_id: 60,
        copy_notice: 'Las copias BCC configuradas se intentaron después del envío principal.',
      });
    }
    if (apiPath.startsWith('emails/history') && method === 'GET') {
      calls.push({ method, path: apiPath, url: route.request().url() });
      return json(options.history ?? history);
    }
    if (apiPath === 'emails/copy-recipients/' && method === 'GET') {
      return json({ results: rows, families, copy_mode: 'bcc' });
    }
    if (apiPath === 'emails/copy-recipients/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      calls.push({ method, payload });
      if (options.createError) return json(options.createError, 400);
      const created = { id: 9, ...payload, family_labels: [] };
      rows = [...rows, created];
      return json(created, 201);
    }
    if (apiPath === 'emails/copy-recipients/8/' && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      calls.push({ method, payload });
      if (options.patchFailure) return json(options.patchFailure, 503);
      rows = rows.map(row => row.id === 8 ? { ...row, ...payload } : row);
      return json(rows.find(row => row.id === 8));
    }
    if (apiPath === 'emails/copy-recipients/8/' && method === 'DELETE') {
      calls.push({ method });
      rows = rows.filter(row => row.id !== 8);
      return { status: 204, body: '' };
    }
    return null;
  });
  return calls;
}

async function navigateToEmails(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  const navigation = page.getByRole('navigation', { name: 'Navegación del panel' });
  const emailLink = navigation.getByRole('link', { name: 'Emails', exact: true });
  await expect(emailLink).toBeVisible({ timeout: 20_000 });
  await Promise.all([
    page.waitForURL(/\/panel\/emails(?:\?|$)/, { waitUntil: 'domcontentloaded' }),
    emailLink.click(),
  ]);
  await expect(page.getByRole('heading', { name: 'Emails' }))
    .toBeVisible({ timeout: 20_000 });
}

async function openConfiguration(page) {
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Configuración' }).click();
  await expect(page.getByTestId('client-email-copy-settings')).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await setAuthLocalStorage(page, {
    token: 'e2e-admin-token',
    userAuth: { id: 8700, role: 'admin', is_staff: true, is_superuser: true },
  });
});

test('shows configured BCC families and the volume impact', {
  tag: [...ADMIN_CLIENT_EMAIL_COPY_SETTINGS, '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  await setupMocks(page);
  await openConfiguration(page);

  const row = page.getByTestId('client-copy-row-8');
  await expect(row).toContainText('audit@projectapp.co');
  await expect(row.getByText('Activo')).toBeVisible();
  await expect(page.getByText(/volumen SMTP/)).toBeVisible();
  await expect(page.getByText(/copia de forma oculta/)).toBeVisible();
  await expect(page.getByTestId('email-copy-security-warning'))
    .toContainText('códigos de verificación (OTP)');
  await expect(page.getByTestId('client-copy-8-proposals')).toBeChecked();
  await expect(page.getByTestId('client-copy-8-diagnostics')).not.toBeChecked();
});

test('adds a recipient subscribed to every family', {
  tag: [...ADMIN_CLIENT_EMAIL_COPY_SETTINGS, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const calls = await setupMocks(page, { recipients: [] });
  await openConfiguration(page);

  await page.getByTestId('client-copy-email').fill('new@projectapp.co');
  await page.getByTestId('client-copy-add').click();

  await expect(page.getByText('new@projectapp.co')).toBeVisible();
  const post = calls.find(call => call.method === 'POST');
  expect(post.payload.families).toEqual(families.map(item => item.value));
});

test('persists a changed family selection', {
  tag: [...ADMIN_CLIENT_EMAIL_COPY_SETTINGS, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const calls = await setupMocks(page);
  await openConfiguration(page);

  await page.getByTestId('client-copy-8-diagnostics').check();
  await page.getByTestId('client-copy-save-8').click();

  await expect.poll(() => calls.find(call => call.method === 'PATCH'))
    .toBeTruthy();
  expect(calls.find(call => call.method === 'PATCH').payload.families)
    .toEqual(['proposals', 'diagnostics', 'collections']);
});

test('pauses a configured recipient', {
  tag: [...ADMIN_CLIENT_EMAIL_COPY_SETTINGS, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const calls = await setupMocks(page);
  await openConfiguration(page);

  await page.getByTestId('client-copy-toggle-8').click();

  await expect(page.getByTestId('client-copy-row-8')).toContainText('Pausado');
  expect(calls.find(call => call.method === 'PATCH').payload)
    .toEqual({ is_active: false });
});

test('removes a configured recipient', {
  tag: [...ADMIN_CLIENT_EMAIL_COPY_SETTINGS, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const calls = await setupMocks(page);
  await openConfiguration(page);

  await page.getByTestId('client-copy-delete-8').click();

  await expect(page.getByTestId('client-copy-row-8')).toHaveCount(0);
  expect(calls.some(call => call.method === 'DELETE')).toBe(true);
});

test('shows duplicate-address validation from the API', {
  tag: [...ADMIN_CLIENT_EMAIL_COPY_SETTINGS, '@role:admin', '@outcome:error'],
}, async ({ page }) => {
  await setupMocks(page, {
    createError: { email: ['Ese correo ya está en la lista.'] },
  });
  await openConfiguration(page);

  await page.getByTestId('client-copy-email').fill('audit@projectapp.co');
  await page.getByTestId('client-copy-add').click();

  await expect(page.getByText('Ese correo ya está en la lista.')).toBeVisible();
});

test('keeps the active state when the pause request fails', {
  tag: [...ADMIN_CLIENT_EMAIL_COPY_SETTINGS, '@role:admin', '@outcome:failure'],
}, async ({ page }) => {
  await setupMocks(page, {
    patchFailure: { detail: 'Servicio temporalmente no disponible.' },
  });
  await openConfiguration(page);

  await page.getByTestId('client-copy-toggle-8').click();

  await expect(page.getByText('Servicio temporalmente no disponible.'))
    .toBeVisible();
  await expect(page.getByTestId('client-copy-row-8')).toContainText('Activo');
});

test('shows a failed BCC attempt under its primary history row', {
  tag: [...ADMIN_CLIENT_EMAIL_COPY_HISTORY, '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  await setupMocks(page);
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Historial' }).click();

  await page.getByText('Seguimiento contractual').click();

  const copies = page.getByTestId('email-copy-list-41');
  await expect(copies).toContainText('audit@projectapp.co');
  await expect(copies).toContainText('Fallido');
  await expect(copies).toContainText('SMTP timeout interno');
  await expect(copies).toContainText('Omitida');
  await expect(copies).toContainText('Ya era destinatario');
});

test('translates raw send states in the global Historial', {
  // Bug caught: shared email rows exposed Sent and Failed despite the Spanish panel locale.
  tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_FILTER, '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  const localizedHistory = {
    ...history,
    results: [{ ...history.results[0], status_label: 'Sent' }, {
      ...history.results[0], id: 44, recipient: 'fallido@example.com', status: 'failed', status_label: 'Failed', error_message: 'SMTP down',
    }],
  };
  await setupMocks(page, { history: localizedHistory });
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Historial' }).click();

  const historyRows = page.locator('tbody tr');
  await expect(historyRows.getByText('Enviado', { exact: true })).toBeVisible();
  await expect(historyRows.getByText('Fallido', { exact: true })).toBeVisible();
  await expect(historyRows.getByText('Sent', { exact: true })).toHaveCount(0);
  await expect(historyRows.getByText('Failed', { exact: true })).toHaveCount(0);
});

test('filters the universal outbound history by recipient, family, status and dates', {
  tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_FILTER, '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  const calls = await setupMocks(page);
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Historial' }).click();

  await page.getByRole('searchbox', { name: 'Buscar destinatario' })
    .fill('client@example.com');
  await page.getByLabel('Filtrar por familia').selectOption('security');
  await page.getByLabel('Filtrar por estado').selectOption('sent');
  await page.getByLabel('Filtrar por presencia de adjuntos').selectOption('true');
  await page.getByLabel('Filtrar por tipo de adjunto').selectOption('business:collection_account');
  await page.getByLabel('Fecha inicial').fill('2026-08-01');
  await page.getByLabel('Fecha final').fill('2026-08-26');
  await page.getByRole('button', { name: 'Aplicar filtros' }).click();

  await expect(page.getByText('Código de recuperación')).toBeVisible();
  await expect.poll(() => calls.some(call =>
    call.url?.includes('recipient=client%40example.com')
      && call.url.includes('family=security')
      && call.url.includes('status=sent')
      && call.url.includes('has_attachments=true')
      && call.url.includes('attachment_type=business%3Acollection_account')
      && call.url.includes('date_from=2026-08-01')
      && call.url.includes('date_to=2026-08-26'))).toBe(true);
});

test('lets an admin inspect the retained full body of a security email', {
  tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_BODY, '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  const calls = await setupMocks(page);
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Historial' }).click();

  await page.getByText('Seguimiento contractual').click();
  await page.getByTestId('email-history-view-body-41').click();

  await expect(page.getByTestId('email-body-modal')).toContainText('El correo como salió');
  await expect(page.getByTitle('Contenido del correo')).toBeVisible();
  await expect(page.frameLocator('[title="Contenido del correo"]')
    .getByText('Código privado 123456')).toBeVisible();
  expect(calls.some(call => call.path === 'emails/history/41/body/')).toBe(true);
});

test('shows exact attachment metadata and opens the retained PDF', {
  tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_ATTACHMENTS, '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  // Catches regressions where provenance becomes plain text or sent links lose their group or target URL.
  await setupMocks(page, { history: exactHistory });
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Historial' }).click();
  await page.getByText('Cuenta de cobro agosto', { exact: true }).first().click();

  const attachments = page.getByTestId('email-history-attachments-51');
  const attachment = page.getByTestId('email-attachment-71');
  await expect(attachments).toContainText('cuenta-cobro-agosto.pdf');
  await expect(attachments).toContainText('Cuenta de cobro · PDF · 1.0 MB');
  await expect(attachments).toContainText('Envío total: 1.8 MB');
  await expect(attachment.getByRole('link', { name: 'Cuenta de cobro agosto' }))
    .toHaveAttribute('href', '/en-us/panel/documents/72/edit');
  await page.getByRole('button', { name: 'Previsualizar' }).click();
  await expect(page.getByTestId('email-pdf-preview-frame')).toBeVisible();
  const links = page.getByTestId('email-history-links-51');
  await expect(links).toContainText('Contenido');
  await expect(links).toContainText('Plantilla y firma');
  await expect(links.getByRole('link', { name: 'Pagar ahora' }))
    .toHaveAttribute('href', 'https://projectapp.co/platform/payments/7');
  await expect(links.getByRole('link', { name: 'ProjectApp' }))
    .toHaveAttribute('href', 'https://projectapp.co');
});

test('states explicitly that a captured email had no attachments', {
  tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_ATTACHMENTS, '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  await setupMocks(page, { history: exactHistory });
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Historial' }).click();
  await page.getByText('Confirmación sin archivos').click();

  await expect(page.getByTestId('email-history-no-attachments-53'))
    .toHaveText('Este correo no llevaba adjuntos.');
});

test('discloses that a legacy attachment cannot be downloaded exactly', {
  tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_ATTACHMENTS, '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  await setupMocks(page, { history: exactHistory });
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Historial' }).click();
  await page.getByText('Histórico anterior').click();

  await expect(page.getByTestId('email-history-legacy-54'))
    .toContainText('anterior al archivo exacto');
  await expect(page.getByRole('link', { name: 'Descargar' })).toHaveCount(0);
});

test('resends an archived delivery after editing its visible recipient groups', {
  tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_RESEND, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const calls = await setupMocks(page, { history: exactHistory });
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Historial' }).click();
  await page.getByText('Cuenta de cobro agosto', { exact: true }).first().click();
  await page.getByTestId('email-history-resend-51').click();
  await expect(page.getByTestId('email-resend-to-field')).toContainText('cliente@example.com');
  await expect(page.getByTestId('email-resend-cc-field')).toContainText('contabilidad@example.com');
  await page.getByRole('button', { name: 'Quitar cliente@example.com' }).click();
  await page.getByRole('button', { name: 'Quitar contabilidad@example.com' }).click();
  const toInput = page.getByTestId('email-resend-to');
  await toInput.fill('nuevo@example.com');
  await toInput.press('Enter');
  await toInput.fill('socio@example.com');
  await toInput.press('Enter');
  const ccInput = page.getByTestId('email-resend-cc');
  await ccInput.fill('copia@example.com');
  await ccInput.press('Enter');
  await page.getByTestId('email-resend-confirm').click();

  await expect(page.getByTestId('email-resend-modal')).toHaveCount(0);
  expect(calls.find(call => call.path === 'emails/history/51/resend/').payload)
    .toEqual({
      recipient_emails: ['nuevo@example.com', 'socio@example.com'],
      cc_emails: ['copia@example.com'],
    });
});

test('keeps the resend failure visible for correction', {
  tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_RESEND, '@role:admin', '@outcome:failure'],
}, async ({ page }) => {
  await setupMocks(page, { history: exactHistory, resendFailure: true });
  await navigateToEmails(page);
  await page.getByRole('tab', { name: 'Historial' }).click();
  await page.getByText('Cuenta de cobro agosto', { exact: true }).first().click();
  await page.getByTestId('email-history-resend-51').click();
  await page.getByTestId('email-resend-confirm').click();

  await expect(page.getByTestId('email-resend-modal'))
    .toContainText('SMTP temporalmente no disponible.');
});
