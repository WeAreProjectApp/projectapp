/**
 * @flow:admin-client-communications
 * E2E coverage for the manual client communications registry.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_CLIENT_COMMUNICATIONS } from '../helpers/flow-tags.js';
import { PANEL_BREAKPOINTS } from '../../config/responsive.js';
import { viewportUse } from '../helpers/viewports.js';
import { fillRichTextSource } from '../helpers/editorial.js';

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const documentReference = {
  id: 73,
  title: 'Alcance fase 2',
  status: 'published',
  project_id: 19,
  client_user_id: 501,
};

const outgoingMessage = {
  id: 801,
  thread_id: 41,
  channel: 'email',
  channel_display: 'Correo',
  direction: 'outgoing',
  direction_display: 'Saliente',
  status: 'sent',
  status_display: 'Enviado',
  subject: 'Alcance para aprobación',
  content: 'Te compartimos el alcance actualizado.',
  occurred_at: '2026-08-24T14:00:00Z',
  recorded_at: '2026-08-24T14:05:00Z',
  updated_at: '2026-08-24T14:05:00Z',
  source: 'manual',
  reply_to_id: null,
  has_reply: true,
  documents: [documentReference],
  date_corrections: [],
  created_by_name: 'Admin',
  voided_at: null,
  void_reason: '',
};

const incomingMessage = {
  ...outgoingMessage,
  id: 802,
  channel: 'whatsapp',
  channel_display: 'WhatsApp',
  direction: 'incoming',
  direction_display: 'Entrante',
  status: 'received',
  status_display: 'Recibido',
  subject: '',
  content: 'Está aprobado, pueden continuar.',
  occurred_at: '2026-08-24T15:10:00Z',
  recorded_at: '2026-08-24T15:12:00Z',
  reply_to_id: 801,
  has_reply: false,
  documents: [],
};

const compactListMessage = `Confirmamos que el alcance incluye la revisión de accesibilidad,
  las pruebas de aceptación y el acompañamiento de salida para todo el equipo responsable,
  con una secuencia adicional que sólo corresponde leer dentro del hilo.`;

function listThread(overrides = {}) {
  return {
    id: 41,
    title: 'Aprobación de alcance',
    status: 'open',
    client_id: 7,
    client_name: 'Ana Proyecto',
    client_email: 'ana@example.com',
    project_id: 19,
    project_name: 'Portal de clientes',
    messages_count: 2,
    draft_count: 0,
    channels: ['email', 'whatsapp'],
    latest_message: {
      id: 802,
      direction: 'incoming',
      status: 'received',
      content: incomingMessage.content,
      occurred_at: incomingMessage.occurred_at,
    },
    last_activity_at: incomingMessage.occurred_at,
    closed_at: null,
    created_at: '2026-08-24T13:00:00Z',
    updated_at: '2026-08-24T15:12:00Z',
    ...overrides,
  };
}

function secondThread() {
  return listThread({
    id: 42,
    title: 'Coordinación de entrega',
    project_id: null,
    project_name: null,
    messages_count: 0,
    channels: [],
    latest_message: null,
  });
}

function additionalThread(id, title, overrides = {}) {
  return listThread({
    id,
    title,
    project_id: id + 100,
    project_name: `Proyecto ${id}`,
    messages_count: 1,
    channels: ['email'],
    latest_message: {
      id: id + 800,
      direction: 'outgoing',
      status: 'sent',
      content: `Seguimiento breve del hilo ${id}.`,
      occurred_at: '2026-08-23T14:00:00Z',
    },
    last_activity_at: '2026-08-23T14:00:00Z',
    ...overrides,
  });
}

function communicationFacets(projectName = 'Portal de clientes') {
  return {
    total: 5,
    navigation_total: 5,
    without_project_count: 1,
    projects: [
      {
        id: 19,
        name: projectName,
        client_id: 7,
        client_name: 'Ana Proyecto',
        catalog_bucket: 'active',
        count: 4,
        unavailable: false,
      },
      {
        id: 20,
        name: 'Kore',
        client_id: 7,
        client_name: 'Ana Proyecto',
        catalog_bucket: 'active',
        count: 0,
        unavailable: false,
      },
      {
        id: 21,
        name: 'PRUEBA',
        client_id: 7,
        client_name: 'Ana Proyecto',
        catalog_bucket: 'active',
        count: 0,
        unavailable: false,
      },
      {
        id: 22,
        name: 'Candle',
        client_id: 7,
        client_name: 'Ana Proyecto',
        catalog_bucket: 'archived',
        count: 0,
        unavailable: false,
      },
    ],
    clients: [{
      id: 7,
      name: 'Ana Proyecto',
      count: 5,
      unavailable: false,
    }],
    filters: {
      status: { open: 5, closed: 0 },
      channel: { email: 4, whatsapp: 1 },
      direction: { outgoing: 4, incoming: 1 },
      message_status: { draft: 1, sent: 3, received: 1, failed: 0 },
      reply_status: { answered: 1, unanswered: 3 },
    },
  };
}

const factorySavedTabs = [
  ['draft-pending', 'Borradores pendientes'],
  ['sent-unanswered', 'Enviados sin respuesta'],
  ['open', 'Abiertos'],
  ['closed', 'Cerrados'],
  ['channel-email', 'Correo'],
  ['channel-whatsapp', 'WhatsApp'],
].map(([builtinKey, name], index) => ({
  id: 1001 + index,
  view: 'communication',
  name,
  filters: {},
  base_filters: {},
  builtin_key: builtinKey,
  order: index,
  is_seeded: false,
  is_hidden: false,
}));

const communicationPreferenceDefaults = {
  navigation_mode: 'project',
  thread_order: 'recent',
  page_size: 20,
  default_channel: 'whatsapp',
  show_manual_help: true,
  navigation_width: 288,
};

async function setupCommunicationsApi(page, {
  listFailure = false,
  messageFailure = false,
  initialMessages = [outgoingMessage, incomingMessage],
  onMessage = null,
  onListRequest = null,
  onPreference = null,
  onSavedView = null,
  initialSavedTabs = [],
  initialPreferences = {},
  projectName = 'Portal de clientes',
} = {}) {
  let shouldFailList = listFailure;
  const state = {
    thread: {
      ...listThread({ project_name: projectName }),
      messages: initialMessages.map((message) => ({ ...message })),
    },
    preferences: {
      ...communicationPreferenceDefaults,
      ...initialPreferences,
    },
    savedTabs: [
      ...factorySavedTabs.map((tab) => ({ ...tab })),
      ...initialSavedTabs.map((tab, index) => ({
        id: 901 + index,
        view: 'communication',
        filters: {},
        base_filters: {},
        builtin_key: '',
        order: factorySavedTabs.length + index,
        is_seeded: false,
        is_hidden: false,
        ...tab,
      })),
    ],
  };

  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;

    if (apiPath === 'accounts/panel-preferences/communications/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...state.preferences, legacy_import_allowed: false }),
      };
    }

    if (apiPath === 'accounts/panel-preferences/communications/' && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      state.preferences = { ...state.preferences, ...payload };
      if (onPreference) onPreference(payload, { ...state.preferences });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(state.preferences),
      };
    }

    if (
      apiPath === 'accounts/panel-preferences/communications/reset/'
      && method === 'POST'
    ) {
      state.preferences = { ...communicationPreferenceDefaults };
      if (onPreference) onPreference({ reset: true }, { ...state.preferences });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(state.preferences),
      };
    }

    if (apiPath === 'communications/threads/' && method === 'GET') {
      if (onListRequest) onListRequest(route.request().url());
      if (shouldFailList) {
        return {
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'El registro no está disponible.' }),
        };
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            listThread({
              project_name: projectName,
              messages_count: state.thread.messages.length,
              latest_message: {
                ...state.thread.messages.at(-1),
                content: compactListMessage,
              },
            }),
            secondThread(),
            additionalThread(43, 'Seguimiento de implementación', { draft_count: 1 }),
            additionalThread(44, 'Revisión de contenidos'),
            additionalThread(45, 'Cierre de publicación'),
          ],
          count: 5,
          page: 1,
          num_pages: 1,
          facets: communicationFacets(projectName),
        }),
      };
    }

    if (apiPath === 'communications/threads/tab-counts/' && method === 'POST') {
      const knownCounts = {
        all: 5,
        'draft-pending': 1,
        'sent-unanswered': 0,
        open: 5,
        closed: 0,
        'channel-email': 4,
        'channel-whatsapp': 1,
      };
      const counts = Object.fromEntries(
        route.request().postDataJSON().tabs.map((tab) => [
          String(tab.id), knownCounts[String(tab.id)] ?? 5,
        ]),
      );
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ counts }),
      };
    }

    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      if (method === 'POST' && apiPath === 'accounts/saved-filter-tabs/') {
        const payload = route.request().postDataJSON();
        if (onSavedView) onSavedView(payload);
        const saved = {
          id: 901,
          ...payload,
          base_filters: payload.filters,
          builtin_key: '',
          order: state.savedTabs.length,
          is_seeded: false,
          is_hidden: false,
        };
        state.savedTabs.push(saved);
        return {
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(saved),
        };
      }
      if (method === 'POST' && apiPath === 'accounts/saved-filter-tabs/reset/') {
        const ownTabs = state.savedTabs.filter((tab) => !tab.builtin_key);
        state.savedTabs = [
          ...factorySavedTabs.map((tab) => ({ ...tab })),
          ...ownTabs.map((tab, index) => ({
            ...tab, order: factorySavedTabs.length + index,
          })),
        ];
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(state.savedTabs),
        };
      }
      if (method === 'PATCH') {
        const payload = route.request().postDataJSON();
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 901, view: 'communication', ...payload }),
        };
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(state.savedTabs),
      };
    }

    if (apiPath === 'communications/threads/41/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(state.thread),
      };
    }

    if (apiPath === 'communications/threads/41/messages/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      if (onMessage) onMessage(payload);
      if (messageFailure) {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'El hilo fue cerrado por otra sesión.' }),
        };
      }
      const created = {
        ...outgoingMessage,
        id: 803,
        channel: payload.channel,
        channel_display: payload.channel === 'email' ? 'Correo' : 'WhatsApp',
        direction: payload.direction,
        direction_display: payload.direction === 'incoming' ? 'Entrante' : 'Saliente',
        status: payload.status,
        status_display: payload.status === 'sent' ? 'Enviado' : 'Borrador',
        subject: payload.subject,
        content: payload.content,
        occurred_at: payload.occurred_at,
        reply_to_id: payload.reply_to,
        documents: [],
        has_reply: false,
      };
      state.thread.messages.push(created);
      state.thread.messages_count = state.thread.messages.length;
      state.thread.latest_message = created;
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(created),
      };
    }

    if (apiPath === 'communications/messages/803/mark-sent/' && method === 'POST') {
      const message = state.thread.messages.find((item) => item.id === 803);
      Object.assign(message, { status: 'sent', status_display: 'Enviado' });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...message, thread_id: 41 }),
      };
    }

    if (apiPath === 'documents/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([documentReference]),
      };
    }

    return null;
  });

  return {
    failList() {
      shouldFailList = true;
    },
  };
}

async function gotoCommunications(page) {
  // quality: allow-deep-link (the display outcome below covers entry through panel navigation)
  await page.goto('/panel/communications', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Comunicaciones', exact: true }))
    .toBeVisible({ timeout: 30_000 });
}

async function enterCommunicationsThroughPanel(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
  }
  const link = page.getByRole('link', { name: 'Hilos con clientes', exact: true });
  await expect(link).toBeVisible({ timeout: 25_000 });
  await link.click();
  await expect(page.getByRole('heading', { name: 'Comunicaciones', exact: true }))
    .toBeVisible({ timeout: 30_000 });
}

async function openMainThread(page) {
  await page.getByTestId('communication-thread-row-41').click();
  await expect(page).toHaveURL(/(?:\?|&)thread=41(?:&|$)/);
  await expect(page.locator('[data-modal-kind="workspace"]')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Aprobación de alcance', exact: true }))
    .toBeVisible();
}

async function expectFactoryFilterCounts(page) {
  if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
    const filterSelect = page.getByTestId('filter-tabs-select');
    const expectedLabels = [
      'Borradores pendientes (1)',
      'Enviados sin respuesta (0)',
      'Abiertos (5)',
      'Cerrados (0)',
      'Correo (4)',
      'WhatsApp (1)',
    ];
    for (const label of expectedLabels) await expect(filterSelect).toContainText(label);
    return;
  }

  const expectedCounts = {
    all: 5,
    'draft-pending': 1,
    'sent-unanswered': 0,
    open: 5,
    closed: 0,
    'channel-email': 4,
    'channel-whatsapp': 1,
  };
  for (const [id, count] of Object.entries(expectedCounts)) {
    await expect(page.getByTestId(`filter-tabs-count-${id}`)).toHaveText(`(${count})`);
  }
}

test.describe('Admin Client Communications', () => {
  test.describe.configure({ timeout: 60_000 });

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 9100, role: 'admin', is_staff: true },
    });
  });

  test.describe('desktop project catalog', () => {
    test.use(viewportUse('desktop'));

    test('shows the complete project catalog', {
      tag: [
        ...ADMIN_CLIENT_COMMUNICATIONS,
        '@role:admin',
        '@outcome:display',
        '@responsive:communications',
      ],
    }, async ({ page }) => {
      // Regression: the desktop catalog must not hide zero-content or archived projects.
      await setupCommunicationsApi(page);
      await enterCommunicationsThroughPanel(page);

      const navigation = page.getByTestId('communications-navigation-panel');
      await expect(navigation).toContainText('Portal de clientes');
      await expect(page.getByTestId('communications-navigation-project-20')).toContainText('Kore');
      await expect(page.getByTestId('communications-navigation-project-21')).toContainText('PRUEBA');
      // Las comunicaciones sueltas tienen su propia seccion, igual que las
      // carpetas propias del gestor documental.
      await expect(page.getByTestId('communications-own-section')).toContainText('Sin proyecto');

      // El interruptor de ciclo de vida es EXCLUYENTE: los archivados aparecen
      // al encenderlo, y los activos se retiran mientras dure.
      await expect(page.getByTestId('communications-navigation-archived-group'))
        .toHaveCount(0);
      await page.getByTestId('communications-inactive-projects-toggle').click();
      await expect(page.getByTestId('communications-navigation-archived-group'))
        .toContainText('Candle');
      await expect(page.getByTestId('communications-navigation-project-20')).toHaveCount(0);
    });
  });

  test('explains the manual channel scope', {
    tag: [
      ...ADMIN_CLIENT_COMMUNICATIONS,
      '@role:admin',
      '@outcome:display',
      '@responsive:communications',
    ],
  }, async ({ page }) => {
    await setupCommunicationsApi(page);
    await enterCommunicationsThroughPanel(page);

    const scope = page.getByTestId('communications-channel-scope');
    await expect(scope).toContainText('conserva el registro manual');
    await expect(scope).not.toContainText(/fase posterior|envío automático/i);
  });

  test('shows the bidirectional timeline and referenced documents', {
    tag: [
      ...ADMIN_CLIENT_COMMUNICATIONS,
      '@role:admin',
      '@outcome:display',
      '@responsive:communications',
    ],
  }, async ({ page }) => {
    // Regression: thread details must preserve message direction, replies, and document references.
    await setupCommunicationsApi(page);
    await enterCommunicationsThroughPanel(page);
    await openMainThread(page);

    const timeline = page.getByTestId('communication-timeline');
    await expect(page.getByText(/^(?:Hilo|Thread) #41$/)).toBeVisible();
    await expect(page.getByTestId('communication-thread-row-41')).toContainText('#41');
    await expect(page.getByTestId('communication-message-801'))
      .toContainText(/(?:Mensaje|Message) #801/);
    await expect(page.getByTestId('communication-message-802'))
      .toContainText(/(?:Mensaje|Message) #802/);
    await expect(page.getByTestId('communication-message-801')
      .getByText('Te compartimos el alcance actualizado.', { exact: true }))
      .toBeVisible();
    await expect(page.getByTestId('communication-message-802')
      .getByText('Está aprobado, pueden continuar.', { exact: true }))
      .toBeVisible();
    await expect(timeline.getByRole('link', { name: /#73 Alcance fase 2/ })).toBeVisible();
    await expect(page.getByTestId('communication-message-802')
      .getByRole('link', { name: /En respuesta.*Te compartimos el alcance actualizado/ }))
      .toHaveAttribute('href', '#communication-message-801');
    await expect(timeline.getByText('Respondido', { exact: true })).toBeVisible();
    await expect(timeline.getByText('Recibido', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Cerrar detalle del hilo' }).click();
    await expect(page).not.toHaveURL(/(?:\?|&)thread=/);
    await expect(page.getByTestId('communication-thread-row-41')).toBeVisible();
  });

  test('renders subject-only compact thread cards', {
    tag: [
      ...ADMIN_CLIENT_COMMUNICATIONS,
      '@role:admin',
      '@outcome:display',
      '@responsive:communications',
    ],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — this scenario validates the subject-only compact index contract)
    // quality: allow-deep-link (communications navigation is covered separately; this scenario isolates the responsive list render)
    await page.setViewportSize({ width: 412, height: 915 });
    await setupCommunicationsApi(page);
    await gotoCommunications(page);

    const list = page.getByTestId('communication-thread-list');
    const cards = list.locator('[data-testid^="communication-thread-row-"]');
    const mainCard = page.getByTestId('communication-thread-row-41');

    await expect(cards).toHaveCount(5);
    await expect(mainCard).toContainText('Aprobación de alcance');
    await expect(mainCard).toContainText('Ana Proyecto · Portal de clientes');
    await expect(mainCard).toContainText('WhatsApp');
    await expect(mainCard).toContainText('2 mensajes');
    await expect(page.getByTestId('communication-thread-row-43')).toContainText('1 borrador');
    await expect(mainCard).not.toContainText('Confirmamos que el alcance');
    await expect(mainCard).not.toContainText(compactListMessage);
    await expect(page.getByTestId('communication-thread-excerpt-41')).toHaveCount(0);
    await expect(page.getByText('Hilo', { exact: true })).toHaveCount(0);

    await expect.poll(() => list.evaluate((element) => getComputedStyle(element).overflowX))
      .toBe('hidden');
    const pageOverflow = await page.evaluate(() => (
      Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
      - document.documentElement.clientWidth
    ));
    expect(pageOverflow).toBeLessThanOrEqual(1);

    const visibleCards = await cards.evaluateAll((elements) => elements.filter((element) => {
      const rect = element.getBoundingClientRect();
      return rect.top < window.innerHeight && rect.bottom > 0;
    }).length);
    expect(visibleCards).toBeGreaterThan(1);
  });

  test('restores the selected order on a later visit', {
    tag: [
      ...ADMIN_CLIENT_COMMUNICATIONS,
      '@role:admin',
      '@outcome:success',
      '@responsive:communications',
    ],
  }, async ({ page }) => {
    const listRequests = [];
    const preferenceUpdates = [];
    await setupCommunicationsApi(page, {
      onListRequest: (url) => listRequests.push(url),
      onPreference: (payload) => preferenceUpdates.push(payload),
    });
    await gotoCommunications(page);

    const oldestOrder = page.getByTestId('communications-order-oldest');
    await oldestOrder.click();
    await expect(oldestOrder).toHaveAttribute('aria-selected', 'true');
    await expect(page).toHaveURL(/order=oldest/);
    await expect.poll(() => listRequests.some((url) => url.includes('order=oldest'))).toBe(true);
    await expect.poll(() => preferenceUpdates).toContainEqual({ thread_order: 'oldest' });

    const laterVisitRequestIndex = listRequests.length;
    await gotoCommunications(page);

    await expect(page.getByTestId('communications-order-oldest'))
      .toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('communications-order-control')).toContainText('Orden:');
    await expect.poll(() => listRequests
      .slice(laterVisitRequestIndex)
      .some((url) => url.includes('order=oldest'))).toBe(true);
  });

  test('shows every factory filter count', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupCommunicationsApi(page);
    await enterCommunicationsThroughPanel(page);
    await expectFactoryFilterCounts(page);
    await expect(page.getByTestId('filter-tabs-count-all')).toHaveText('(5)');
  });

  test('applies the unanswered factory cut', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const listRequests = [];
    await setupCommunicationsApi(page, {
      onListRequest: (url) => listRequests.push(url),
    });
    await gotoCommunications(page);

    if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
      await page.getByTestId('filter-tabs-select').selectOption('sent-unanswered');
    } else {
      await page.getByTestId('filter-tabs-tab-sent-unanswered').click();
    }

    await expect(page).toHaveURL(/status=open/);
    await expect(page).toHaveURL(/direction=outgoing/);
    await expect(page).toHaveURL(/message_status=sent/);
    await expect(page).toHaveURL(/reply_status=unanswered/);
    await expect.poll(() => listRequests.at(-1)).toContain('reply_status=unanswered');
  });

  test('preserves a saved view after factory reset', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupCommunicationsApi(page, {
      initialSavedTabs: [{
        name: 'Mi seguimiento',
        filters: { channel: ['email'] },
        base_filters: { channel: ['email'] },
      }],
    });
    await gotoCommunications(page);

    await expect(page.locator(
      '[data-testid="communications-settings"] + [data-testid="communications-new-thread"]',
    )).toBeVisible();
    await page.getByTestId('communications-settings').click();
    await expect(page.getByTestId('communications-new-thread')).toBeDisabled();
    await expect(page.getByTestId('filter-tabs-config')).toHaveCount(0);
    await expect(page.getByTestId('view-settings-panel'))
      .toContainText('Tus pestañas propias se conservan.');
    await page.getByTestId('view-settings-reset-tabs-communication').click();
    await expect(page.getByRole('dialog')).toContainText('Tus pestañas propias se conservarán.');
    const resetResponse = page.waitForResponse((response) => (
      response.url().includes('/api/accounts/saved-filter-tabs/reset/')
      && response.request().method() === 'POST'
    ));
    await page.getByTestId('confirm-modal-confirm').click();
    await resetResponse;
    await page.getByTestId('communication-settings-back').click();

    if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
      const filterSelect = page.getByTestId('filter-tabs-select');
      await expect(filterSelect).toContainText('Mi seguimiento · Propia');
      await filterSelect.selectOption('901');
    } else {
      await expect(page.getByTestId('filter-tabs-origin-901')).toHaveText('Propia');
      await page.getByTestId('filter-tabs-tab-901').click();
    }
    await expect(page).toHaveURL(/channel=email/);
  });

  test('navigates by client, combines message statuses and saves the view', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const listRequests = [];
    let savedPayload = null;
    await setupCommunicationsApi(page, {
      onListRequest: (url) => listRequests.push(url),
      onSavedView: (payload) => { savedPayload = payload; },
    });
    await gotoCommunications(page);

    await page.getByTestId('communications-navigation-without-project').click();
    await expect(page).toHaveURL(/project=none/);
    await page.getByTestId('communications-mode-client').click();
    await expect(page).toHaveURL(/by=client/);
    await expect(page).not.toHaveURL(/project=/);
    await page.getByTestId('communications-navigation-client-7').click();
    await expect(page).toHaveURL(/client=7/);

    await page.getByTestId('communications-filter-toggle').click();
    await page.getByTestId('communications-message-status-filter').click();
    const statusDialog = page.getByRole('dialog', { name: 'Estado del mensaje' });
    await statusDialog.locator('input[value="draft"]').check();
    await statusDialog.locator('input[value="sent"]').check();
    await page.keyboard.press('Escape');

    await expect.poll(() => listRequests.at(-1)).toContain('message_status=draft%2Csent');
    await page.getByTestId('filter-tabs-create').click();
    await page.getByTestId('filter-tabs-input').fill('Borradores y enviados');
    await page.getByTestId('filter-tabs-confirm').click();

    await expect.poll(() => savedPayload).toMatchObject({
      view: 'communication',
      name: 'Borradores y enviados',
      filters: {
        by: 'client',
        client: '7',
        message_status: ['draft', 'sent'],
      },
    });
    await expect(page.getByTestId('filter-tabs-tab-901')).toBeVisible();
    await expect(page.getByTestId('filter-tabs-origin-901')).toHaveText('Propia');

    await page.getByTestId('filter-tabs-all').click();
    await expect(page).not.toHaveURL(/client=7/);
    await page.getByTestId('filter-tabs-tab-901').click();
    await expect(page).toHaveURL(/client=7/);
    await expect(page).toHaveURL(/message_status=draft(?:%2C|,)sent/);
  });

  test('searches the thread list by project name', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const listRequests = [];
    await setupCommunicationsApi(page, {
      onListRequest: (url) => listRequests.push(url),
    });
    await gotoCommunications(page);

    await page.getByRole('textbox', { name: 'Buscar comunicaciones' })
      .fill('Portal de clientes');

    await expect(page).toHaveURL(/q=Portal(?:\+|%20)de(?:\+|%20)clientes/);
    await expect.poll(() => listRequests.at(-1)).toMatch(
      /q=Portal(?:\+|%20)de(?:\+|%20)clientes/,
    );
    await expect(page.getByTestId('communication-thread-row-41')).toBeVisible();
  });

  test('finds a thread from its visible record ID', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Regression: an ID-only search must retain the matching thread instead of treating # as noise.
    const listRequests = [];
    await setupCommunicationsApi(page, {
      onListRequest: (url) => listRequests.push(url),
    });
    await gotoCommunications(page);

    await page.getByTestId('communications-search').fill('#41');

    await expect(page).toHaveURL(/q=%2341/);
    await expect.poll(() => listRequests.at(-1)).toContain('q=%2341');
    await expect(page.getByTestId('communication-thread-row-41')).toContainText('#41');
  });

  test('keeps the manual notice dismissed until help reopens it', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const preferenceUpdates = [];
    await setupCommunicationsApi(page, {
      onPreference: (payload) => preferenceUpdates.push(payload),
    });
    // quality: allow-deep-link (panel entry is covered by the timeline display outcome)
    await gotoCommunications(page);

    await page.getByRole('button', { name: 'Cerrar alerta' }).click();
    await expect.poll(() => preferenceUpdates)
      .toContainEqual({ show_manual_help: false });
    await expect(page.getByTestId('communications-channel-scope')).toHaveCount(0);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('communications-channel-scope')).toHaveCount(0);

    await page.getByTestId('communications-show-help').click();
    await expect(page.getByTestId('communications-channel-scope')).toBeVisible();
  });

  test('persists the resized project navigation width', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const longProjectName = 'Portal de clientes con seguimiento contractual ampliado';
    const preferenceUpdates = [];
    await page.setViewportSize({ width: 1440, height: 900 });
    await setupCommunicationsApi(page, {
      projectName: longProjectName,
      onPreference: (payload) => preferenceUpdates.push(payload),
    });
    await gotoCommunications(page);

    const handle = page.getByTestId('communications-navigation-resize-handle');
    const projectName = page.getByTestId('communications-navigation-project-19')
      .locator('span[title]');
    await expect(projectName).toHaveAttribute('title', longProjectName);
    await expect(handle).toHaveAttribute('aria-valuenow', '288');
    await handle.press('End');
    await expect(handle).toHaveAttribute('aria-valuenow', '400');
    await expect.poll(() => preferenceUpdates)
      .toContainEqual({ navigation_width: 400 });

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('communications-navigation-resize-handle'))
      .toHaveAttribute('aria-valuenow', '400');
  });

  test('uses persisted settings for a new message', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let submittedPayload = null;
    const listRequests = [];
    const preferenceUpdates = [];
    await setupCommunicationsApi(page, {
      onMessage: (payload) => { submittedPayload = payload; },
      onListRequest: (url) => listRequests.push(url),
      onPreference: (payload) => preferenceUpdates.push(payload),
    });
    await gotoCommunications(page);

    await page.getByTestId('communications-settings').click();
    const settings = page.getByTestId('communication-settings-panel');
    await settings.getByTestId('communication-settings-default-channel')
      .getByRole('tab', { name: 'Correo' }).click();
    await settings.getByTestId('communication-settings-page-size')
      .getByRole('tab', { name: '50' }).click();
    await settings.getByTestId('communication-settings-save').click();
    await expect.poll(() => preferenceUpdates).toContainEqual({
      default_channel: 'email',
      page_size: 50,
    });
    await expect.poll(() => listRequests.some((url) => url.includes('page_size=50'))).toBe(true);

    await gotoCommunications(page);
    await page.getByTestId('communications-settings').click();
    await expect(page.getByTestId('communication-settings-default-channel')
      .getByRole('tab', { name: 'Correo' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('communication-settings-page-size')
      .getByRole('tab', { name: '50' })).toHaveAttribute('aria-selected', 'true');
    await page.getByTestId('communication-settings-back').click();
    await openMainThread(page);
    await page.getByTestId('communication-composer-toggle').click();

    await expect(page.getByTestId('communication-message-channel')).toHaveValue('email');
    await page.getByTestId('communication-message-subject')
      .fill('Inicio del trabajo');
    const composerContent = page.getByTestId('communication-message-content');
    await fillRichTextSource(composerContent, 'Confirmamos que el equipo inicia mañana.');
    await page.getByTestId('communication-register-sent').click();

    await expect.poll(() => submittedPayload).toMatchObject({
      channel: 'email',
      direction: 'outgoing',
      status: 'sent',
      subject: 'Inicio del trabajo',
      content: 'Confirmamos que el equipo inicia mañana.',
    });
    await expect(page.getByTestId('communication-timeline')
      .getByText('Confirmamos que el equipo inicia mañana.')).toBeVisible();
    await expect(page.getByText('Mensaje registrado', { exact: true })).toBeVisible();
  });

  test('keeps the composer visible when the API rejects a message', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupCommunicationsApi(page, { messageFailure: true });
    await gotoCommunications(page);
    await openMainThread(page);
    await page.getByTestId('communication-composer-toggle').click();

    const content = page.getByTestId('communication-message-content');
    await fillRichTextSource(content, 'Este texto no debe perderse.');
    await page.getByTestId('communication-register-sent').click();

    await expect(page.getByText('El hilo fue cerrado por otra sesión.', { exact: true }).first())
      .toBeVisible();
    await expect(content.getByTestId('rich-text-source-input'))
      .toHaveValue('Este texto no debe perderse.');
  });

  test('moves a long thread to its end and back without scrolling the page', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Regression: timeline shortcuts must scroll the modal history, not the page behind it.
    const longTimeline = Array.from({ length: 24 }, (_, index) => ({
      ...outgoingMessage,
      id: 900 + index,
      content: `Seguimiento ${index + 1}: ${'contenido extenso '.repeat(18)}`,
      occurred_at: `2026-08-24T${String(index % 20).padStart(2, '0')}:00:00Z`,
    }));
    await setupCommunicationsApi(page, { initialMessages: longTimeline });
    await gotoCommunications(page);
    await openMainThread(page);

    const timeline = page.getByTestId('communication-timeline');
    await page.getByTestId('communication-scroll-end').click();
    await expect.poll(() => timeline.evaluate((element) => element.scrollTop)).toBeGreaterThan(100);
    await expect(timeline.getByTestId('communication-message-923'))
      .toContainText('Seguimiento 24:');
    await expect(timeline.getByTestId('communication-message-923')).toBeInViewport();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);

    await page.getByTestId('communication-scroll-start').click();
    await expect.poll(() => timeline.evaluate((element) => element.scrollTop)).toBe(0);
    await expect(timeline.getByTestId('communication-message-900'))
      .toContainText('Seguimiento 1:');
    await expect(timeline.getByTestId('communication-message-900')).toBeInViewport();
  });

  test('opens the collapsed composer and preserves its details while replying', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Regression: collapsing message details must not discard a reply draft or leave Reply unable to reopen it.
    await setupCommunicationsApi(page);
    await gotoCommunications(page);
    await openMainThread(page);

    const composerToggle = page.getByTestId('communication-composer-toggle');
    const content = page.getByTestId('communication-message-content');
    await expect(composerToggle).toHaveAttribute('aria-expanded', 'false');
    await page.getByTestId('communication-message-802').getByRole('button', { name: 'Responder' }).click();
    await expect(composerToggle).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByTestId('communication-composer')).toContainText('Respuesta al mensaje #802');
    const visualContent = content.getByTestId('rich-text-visual-input');
    await expect(visualContent).toBeFocused();
    const detailsToggle = page.getByTestId('communication-details-toggle');
    await detailsToggle.click();
    const date = page.getByTestId('communication-message-date');
    await date.fill('2026-09-25T09:30');
    await visualContent.fill('La respuesta conserva su fecha.');
    await detailsToggle.click();

    await expect(detailsToggle).toHaveAttribute('aria-expanded', 'false');
    await expect(page.getByTestId('communication-details-summary')).toContainText('25/09/2026');
    await expect(date).toHaveValue('2026-09-25T09:30');
    await expect(visualContent).toContainText('La respuesta conserva su fecha.');
  });

  test('copies directly and marks a draft sent from the overflow menu', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Regression: copying must remain a direct action while Mark as sent stays available in More.
    const draft = {
      ...outgoingMessage,
      id: 803,
      status: 'draft',
      status_display: 'Borrador',
      content: 'Texto que debe copiarse sin abrir Más.',
      has_reply: false,
    };
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: async (text) => { window.__communicationCopiedText = text; } },
        configurable: true,
      });
    });
    await setupCommunicationsApi(page, { initialMessages: [outgoingMessage, draft] });
    await gotoCommunications(page);
    await openMainThread(page);

    await page.getByTestId('communication-copy-803').click();
    await expect.poll(() => page.evaluate(() => window.__communicationCopiedText))
      .toBe('Texto que debe copiarse sin abrir Más.');

    const actions = page.getByTestId('communication-message-actions-803');
    await expect(actions).toHaveAttribute('aria-haspopup', 'menu');
    await actions.click();
    await page.getByRole('menuitem', { name: 'Marcar enviado' }).click();
    await expect(page.getByTestId('communication-message-803')).toContainText('Enviado');
  });

  test('shows a recoverable state when the thread list cannot load', {
    tag: [...ADMIN_CLIENT_COMMUNICATIONS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const api = await setupCommunicationsApi(page);
    await gotoCommunications(page);
    api.failList();
    const failedList = page.waitForResponse((response) => (
      response.url().includes('/api/communications/threads/')
      && response.request().method() === 'GET'
      && response.status() === 503
    ));
    const refresh = page.getByRole('button', { name: 'Actualizar hilos' });
    await refresh.click();
    await failedList;

    await expect(refresh).toBeEnabled();
    await expect(page.getByRole('alert').filter({ hasText: 'El registro no está disponible.' }))
      .toContainText('No se pudieron cargar las comunicaciones.');
  });
});
