/**
 * Editorial communication composer regression coverage.
 *
 * Catches a channel composer that saves formatted source without its format
 * declaration, or displays the raw formatting markers after the message is read.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_CLIENT_COMMUNICATIONS } from '../helpers/flow-tags.js';

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'editor', is_staff: true } }),
};

const threadSummary = {
  id: 41,
  title: 'Aprobación editorial',
  status: 'open',
  client_id: 7,
  client_name: 'Ana Proyecto',
  client_email: 'ana@example.com',
  project_id: 19,
  project_name: 'Portal de clientes',
  messages_count: 1,
  draft_count: 0,
  channels: ['email'],
  latest_message: { id: 801, content: 'Mensaje inicial', occurred_at: '2026-10-23T08:00:00Z' },
  last_activity_at: '2026-10-23T08:00:00Z',
  closed_at: null,
  created_at: '2026-10-23T08:00:00Z',
  updated_at: '2026-10-23T08:00:00Z',
};

const initialMessage = {
  id: 801,
  thread_id: 41,
  channel: 'email',
  channel_display: 'Correo',
  direction: 'outgoing',
  direction_display: 'Saliente',
  status: 'sent',
  status_display: 'Enviado',
  subject: 'Contexto',
  content: '**Contexto destacado**',
  text_formats: { '/content': 'markdown_html_v1' },
  occurred_at: '2026-10-23T08:00:00Z',
  recorded_at: '2026-10-23T08:00:00Z',
  updated_at: '2026-10-23T08:00:00Z',
  source: 'manual',
  reply_to_id: null,
  has_reply: false,
  documents: [],
  date_corrections: [],
  created_by_name: 'Editor',
  voided_at: null,
  void_reason: '',
};

async function setupEditorialCommunications(page, { rejectMessage = false, onMessage = null } = {}) {
  const state = { messages: [{ ...initialMessage }] };
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'accounts/panel-preferences/communications/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ navigation_mode: 'project', thread_order: 'recent', page_size: 20, default_channel: 'email', show_manual_help: true, navigation_width: 288, legacy_import_allowed: false }) };
    }
    if (apiPath === 'accounts/saved-filter-tabs' || apiPath === 'accounts/saved-filter-tabs/') {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    if (apiPath === 'communications/threads/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({
        results: [{ ...threadSummary, messages_count: state.messages.length }],
        count: 1,
        page: 1,
        num_pages: 1,
        facets: { total: 1, navigation_total: 1, without_project_count: 0, projects: [{ id: 19, name: 'Portal de clientes', client_id: 7, client_name: 'Ana Proyecto', catalog_bucket: 'active', count: 1, unavailable: false }], clients: [{ id: 7, name: 'Ana Proyecto', count: 1, unavailable: false }], filters: { status: { open: 1, closed: 0 }, channel: { email: 1, whatsapp: 0 }, direction: { outgoing: 1, incoming: 0 }, message_status: { draft: 0, sent: 1, received: 0, failed: 0 }, reply_status: { answered: 0, unanswered: 1 } } },
      }) };
    }
    if (apiPath === 'communications/threads/tab-counts/' && method === 'POST') {
      const counts = Object.fromEntries(route.request().postDataJSON().tabs.map((tab) => [String(tab.id), 1]));
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ counts }) };
    }
    if (apiPath === 'communications/folders/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    if (apiPath === 'communications/threads/41/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...threadSummary, messages: state.messages }) };
    }
    if (apiPath === 'communications/threads/41/messages/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      onMessage?.(payload);
      if (rejectMessage) {
        return { status: 400, contentType: 'application/json', body: JSON.stringify({ detail: 'La comunicación no se pudo registrar.' }) };
      }
      const created = {
        ...initialMessage,
        id: 803,
        channel: payload.channel,
        channel_display: payload.channel === 'whatsapp' ? 'WhatsApp' : 'Correo',
        direction: payload.direction,
        direction_display: payload.direction === 'incoming' ? 'Entrante' : 'Saliente',
        status: payload.status,
        status_display: payload.status === 'draft' ? 'Borrador' : 'Enviado',
        subject: payload.subject,
        content: payload.content,
        text_formats: payload.text_formats,
        occurred_at: payload.occurred_at,
      };
      state.messages.push(created);
      return { status: 201, contentType: 'application/json', body: JSON.stringify(created) };
    }
    if (apiPath === 'documents/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  });
}

async function openComposer(page) {
  await page.goto('/es-co/panel/communications', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Comunicaciones', exact: true })).toHaveText('Comunicaciones');
  await page.getByTestId('communication-thread-row-41').click();
  await expect(page.getByRole('heading', { name: 'Aprobación editorial', exact: true })).toHaveText('Aprobación editorial');
  await page.getByTestId('communication-composer-toggle').click();
}

function composerEditor(page) {
  return page.getByTestId('communication-message-content');
}

test.describe('Editorial rich text in communications', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'editorial-communication-token',
      userAuth: { id: 762, role: 'admin', is_staff: true },
    });
  });

  test('registers formatted email source with readable output', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let submitted = null;
    await setupEditorialCommunications(page, { onMessage: (payload) => { submitted = payload; } });
    await openComposer(page);

    await page.getByTestId('communication-message-subject').fill('Aprobación editorial');
    const editor = composerEditor(page);
    await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await editor.getByTestId('rich-text-source-input').fill('**Aprobación editorial**\n\n- Alcance\n- Entrega');
    await editor.getByRole('tab', { name: /^Visual$/ }).click();
    await expect(editor.getByTestId('rich-text-visual-input')).toContainText('Aprobación editorial');

    await page.getByTestId('communication-register-sent').click();
    await expect.poll(() => submitted).toMatchObject({
      channel: 'email',
      content: '**Aprobación editorial**\n\n- Alcance\n- Entrega',
      text_formats: { '/content': 'markdown_html_v1' },
    });
    await expect(page.getByTestId('communication-message-803')).toContainText('Aprobación editorial');
    await expect(page.getByTestId('communication-message-803')).toContainText('Alcance');
  });

  test('registers WhatsApp source with its channel format', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let submitted = null;
    await setupEditorialCommunications(page, { onMessage: (payload) => { submitted = payload; } });
    await openComposer(page);

    await page.getByTestId('communication-message-channel').selectOption('whatsapp');
    const editor = composerEditor(page);
    await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    const source = editor.getByTestId('rich-text-source-input');
    await source.fill('*Confirmado por WhatsApp*');
    await editor.getByRole('tab', { name: /^Visual$/ }).click();
    await expect(editor.getByTestId('rich-text-visual-input')).toContainText('Confirmado por WhatsApp');
    await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await expect(source).toHaveValue('*Confirmado por WhatsApp*');

    await page.getByTestId('communication-register-sent').click();
    await expect.poll(() => submitted).toMatchObject({
      channel: 'whatsapp',
      content: '*Confirmado por WhatsApp*',
      text_formats: { '/content': 'whatsapp_v1' },
    });
    await expect(page.getByTestId('communication-message-803')).toContainText('Confirmado por WhatsApp');
  });

  test('keeps rejected source visible after a communication error', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    let submitted = null;
    await setupEditorialCommunications(page, {
      rejectMessage: true,
      onMessage: (payload) => { submitted = payload; },
    });
    await openComposer(page);

    const editor = composerEditor(page);
    await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    const source = editor.getByTestId('rich-text-source-input');
    await source.fill('**No debe perderse**');
    await page.getByTestId('communication-message-subject').fill('Error editorial');
    await page.getByTestId('communication-register-sent').click();

    await expect.poll(() => submitted).toMatchObject({ content: '**No debe perderse**' });
    await expect(page.getByRole('alert').filter({ hasText: 'No se pudo guardar el mensaje' }))
      .toContainText('No se pudo guardar el mensaje');
    await expect(source).toHaveValue('**No debe perderse**');
  });
});
