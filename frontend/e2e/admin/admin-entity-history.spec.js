/**
 * Per-record history journeys for documents, proposals, projects, clients and
 * accounting snapshots. Each assertion protects the operator-facing audit
 * surface from silently becoming an empty or stale timeline.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_ACCOUNTING_RECORD_HISTORY,
  ADMIN_CLIENT_CHANGE_HISTORY,
  ADMIN_DOCUMENT_CHANGE_HISTORY,
  ADMIN_PROJECT_CHANGE_HISTORY,
  ADMIN_PROPOSAL_CHANGE_HISTORY,
} from '../helpers/flow-tags.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });
const auth = json({ user: { username: 'Admin E2E', is_staff: true, is_superuser: true } });

function entry(id, number, field, actor = 'Admin E2E', action = 'updated') {
  return {
    id,
    number,
    action,
    occurred_at: `2026-09-${String(number).padStart(2, '0')}T10:00:00Z`,
    actor,
    source: 'http',
    complete: true,
    fields: [{ name: field, label: FIELD_LABELS[field] || field }],
  };
}

const FIELD_LABELS = {
  content_markdown: 'Contenido',
  total_investment: 'Inversión',
  repository_url: 'Repositorio',
  email: 'Correo electrónico',
  available_amount: 'Disponible',
  debt_amount: 'Deuda',
};

function historyList(rows, { sent = null } = {}) {
  return {
    count: rows.length,
    page: 1,
    num_pages: 1,
    object_label: 'Registro E2E',
    latest_change: rows[0] && { occurred_at: rows[0].occurred_at, actor: rows[0].actor },
    last_sent_version: sent,
    results: rows,
  };
}

function version(id, number, changes, extra = {}) {
  return { id, number, action: 'updated', complete: true, snapshot: {}, changes, protected_fields: [], ...extra };
}

const document = {
  id: 1,
  title: 'Contrato de Servicios',
  status: 'draft',
  content_markdown: '# Contrato\n\nContenido vigente',
  client_name: 'ACME',
  created_at: '2026-09-01T10:00:00Z',
};
const proposal = {
  id: 1,
  uuid: '11111111-1111-1111-1111-111111111111',
  title: 'Propuesta Atlas', client_name: 'ACME', client_email: 'acme@example.test',
  client_phone: '+573001234567', status: 'sent', language: 'es', total_investment: '5000000',
  currency: 'COP', view_count: 0, heat_score: 5, sent_at: '2026-09-02T10:00:00Z',
  is_active: true, created_at: '2026-09-01T10:00:00Z', sections: [], requirement_groups: [],
};
const project = {
  id: 1, name: 'Atlas', description: 'Portal de ACME', status: 'active', status_label: 'Activo',
  client: { profile_id: 101, name: 'Ana Auditora', company: 'ACME' }, hostings_count: 0, incomes_count: 0,
};
const client = {
  id: 101, name: 'Ana Auditora', email: 'ana@acme.example', phone: '+573001112233', company: 'ACME',
  is_onboarded: true, is_email_placeholder: false, total_proposals: 1, is_orphan: false,
  created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-02T10:00:00Z',
};
const card = {
  id: 7, card_name: 'T.C E2E', snapshot_date: '2026-09-02', available_amount: '450000.00',
  debt_amount: '7550000.00', notes: 'Corte E2E', created_at: '2026-09-02T10:00:00Z', updated_at: '2026-09-02T10:00:00Z',
};

async function installFixtures(page, { fail = null, onCall = () => {} } = {}) {
  let failures = { list: 0, version: 0, compare: 0, reveal: 0 };
  const histories = {
    document: [entry(102, 2, 'content_markdown'), entry(101, 1, 'content_markdown')],
    proposal: [entry(202, 3, 'total_investment'), entry(201, 2, 'total_investment')],
    project: [entry(301, 2, 'repository_url')],
    client: [entry(402, 2, 'email'), entry(401, 1, 'email')],
    card_snapshot: [entry(502, 2, 'debt_amount'), entry(501, 1, 'available_amount')],
  };

  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return auth;
    if (apiPath === 'documents/1/detail/') return json(document);
    if (apiPath === 'documents/') return json([document]);
    if (['document-folders/', 'document-tags/', 'document-states/', 'document-state-groups/', 'accounting/projects/'].includes(apiPath)) return json([]);
    if (apiPath === 'proposals/1/detail/') return json(proposal);
    if (apiPath === 'proposals/') return json([proposal]);
    if (apiPath === 'projects/' && method === 'GET') return json({ results: [project], meta: { total: 1, by_state: [], review_required: 0, clients_without_projects: 0, records_without_project: 0 } });
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/') return json([]);
    if (apiPath === 'projects/1/access/' && method === 'GET') {
      return json({
        project: { id: 1, name: 'Atlas', client_name: 'Ana Auditora' }, repository_url: 'https://git.example.test/acme/atlas',
        environments: [{ environment: 'production', label: 'Producción', site_url: 'https://atlas.example.test', admin_url: 'https://atlas.example.test/admin/', admin_username: 'atlas-admin', has_password: true, updated_by: 'Admin E2E' }],
        notes: [{ id: 17, title: 'Acceso principal', content: '', has_content: true, is_sensitive: true, updated_by: 'Admin E2E' }], legacy_access: null,
      });
    }
    if (apiPath === 'proposals/client-profiles/status-counts/') return json({ all: 1, active: 1, orphans: 0, inactive: 0 });
    if (apiPath === 'proposals/client-profiles/' && method === 'GET') return json([client]);
    if (apiPath === 'proposals/client-profiles/101/' && method === 'GET') return json({ ...client, proposals: [], diagnostics: [] });
    if (apiPath === 'accounting/card-snapshots/' && method === 'GET') return json({ results: [card], meta: {} });
    if (apiPath === 'accounting/credit-cards/' && method === 'GET') return json({ results: [{ id: 7, name: 'T.C E2E', credit_limit: '8000000.00', is_active: true, statements_since: '2026-09-01' }], meta: {} });
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);

    const listMatch = apiPath.match(/^entity-history\/(document|proposal|project|client|card_snapshot)\/(\d+)\/$/);
    if (listMatch && method === 'GET') {
      const type = listMatch[1];
      onCall({ kind: 'list', type, url: route.request().url() });
      if (fail === 'list' && failures.list++ === 0) return json({ detail: 'Timeline unavailable' }, 503);
      const url = new URL(route.request().url());
      const rows = url.searchParams.get('order') === 'oldest' ? [...histories[type]].reverse() : histories[type];
      return json(historyList(rows, type === 'proposal' ? { sent: histories.proposal[1] } : {}));
    }
    const versionMatch = apiPath.match(/^entity-history\/(document|proposal|project|client|card_snapshot)\/\d+\/versions\/(\d+)\/$/);
    if (versionMatch && method === 'GET') {
      const type = versionMatch[1]; const id = Number(versionMatch[2]);
      onCall({ kind: 'version', type, id });
      if (fail === 'version' && failures.version++ === 0) return json({ detail: 'Version unavailable' }, 503);
      const details = {
        document: version(id, 2, [{ field: 'content_markdown', label: 'Contenido', old: 'Contenido anterior', new: 'Contenido vigente' }]),
        proposal: version(id, id === 201 ? 2 : 3, [{ field: 'total_investment', label: 'Inversión', old: '5000000', new: '6500000' }]),
        project: version(id, 2, [{ field: 'repository_url', label: 'Repositorio', old: 'https://git.example.test/old', new: 'https://git.example.test/acme/atlas' }], { protected_fields: ['access.production.password'] }),
        client: version(id, 2, [{ field: 'email', label: 'Correo electrónico', old: 'ana@old.example', new: 'ana@acme.example' }], { snapshot: { email: 'ana@acme.example' } }),
        card_snapshot: version(id, 2, [{ field: 'available_amount', label: 'Disponible', old: '300000', new: '450000' }, { field: 'debt_amount', label: 'Deuda', old: '7700000', new: '7550000' }]),
      };
      return json(details[type]);
    }
    const compareMatch = apiPath.match(/^entity-history\/(document|proposal|project|client|card_snapshot)\/\d+\/compare\/$/);
    if (compareMatch && method === 'GET') {
      const type = compareMatch[1]; const url = new URL(route.request().url());
      onCall({ kind: 'compare', type, from: url.searchParams.get('from'), to: url.searchParams.get('to') });
      if (fail === 'compare' && failures.compare++ === 0) return json({ detail: 'Compare unavailable' }, 503);
      const values = type === 'proposal'
        ? [{ field: 'total_investment', label: 'Inversión', old: '5000000', new: '6500000' }]
        : [{ field: 'available_amount', label: 'Disponible', old: '300000', new: '450000' }, { field: 'debt_amount', label: 'Deuda', old: '7700000', new: '7550000' }];
      return json({ from: { number: Number(url.searchParams.get('from')) === 201 ? 2 : 1 }, to: { number: 3 }, changes: values });
    }
    const revealMatch = apiPath.match(/^entity-history\/project\/1\/versions\/(\d+)\/reveal\/$/);
    if (revealMatch && method === 'POST') {
      const field = route.request().postDataJSON().field;
      onCall({ kind: 'reveal', revision: Number(revealMatch[1]), field });
      if (fail === 'reveal' && failures.reveal++ === 0) return json({ detail: 'Reveal unavailable' }, 503);
      return json({ secret: 'atlas-production-secret' });
    }
    return null;
  });
}

async function openDocumentHistory(page) {
  await navigateFromPanel(page, 'Gestor Documental');
  const documentLink = page.getByRole('link', { name: 'Contrato de Servicios', exact: true });
  await expect(documentLink).toHaveText('Contrato de Servicios');
  await documentLink.click();
  await expect(page.getByTestId('doc-editor-title')).toHaveText('Contrato de Servicios');
  await page.getByTestId('entity-history-tabs').getByLabel('Secciones').selectOption('history');
  await expect(page.getByTestId('entity-history')).toBeVisible();
}

async function openProposalHistory(page) {
  await navigateFromPanel(page, 'Propuestas');
  await expect(page.getByTestId('proposal-open-1')).toContainText('Propuesta Atlas');
  await page.getByTestId('proposal-open-1').click();
  await expect(page.getByText('Propuesta Atlas', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Historial', exact: true }).click();
  await expect(page.getByTestId('entity-history')).toBeVisible();
}

async function openProjectHistory(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Proyectos', exact: true }).click();
  await expect(page.getByTestId('project-detail-1')).toBeVisible();
  await page.getByTestId('project-detail-1').click();
  await expect(page.getByTestId('project-access-modal')).toBeVisible();
  await page.getByRole('tab', { name: 'Historial', exact: true }).click();
  await expect(page.getByTestId('entity-history')).toBeVisible();
}

async function openClientHistory(page) {
  await navigateFromPanel(page, 'Clientes');
  await expect(page.getByTestId('client-row-101')).toBeVisible();
  await page.getByTestId('client-header-101').click();
  await page.getByTestId('open-entity-history').click();
  await expect(page.getByTestId('entity-history')).toBeVisible();
}

async function openCardHistory(page) {
  await navigateFromPanel(page, 'Tarjetas');
  await expect(page.getByTestId('accounting-row-7')).toContainText('T.C E2E');
  // Detail and history live in the row's three-dot menu, not beside it.
  await page.getByTestId('cards-actions-7').click();
  await page.getByTestId('cards-action-history-7').click();
  await expect(page.getByRole('heading', { name: 'Detalle del registro' })).toBeVisible();
  await page.getByTestId('entity-history-tabs').getByLabel('Secciones').selectOption('history');
  await expect(page.getByTestId('entity-history')).toBeVisible();
}

async function navigateFromPanel(page, item) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  if (page.viewportSize().width < 1024) {
    const menu = page.getByRole('button', { name: 'Abrir menú' });
    await expect(menu).toBeVisible();
    await menu.click();
    await expect(page.getByRole('dialog', { name: 'Menú principal' })).toBeVisible();
  }
  await page.getByRole('link', { name: item, exact: true }).click();
}

test.beforeEach(async ({ page }) => {
  await setAuthLocalStorage(page, { token: 'entity-history-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
});

test.describe('document history', () => {
  test.use(viewportUse('compact'));

  // Bug caught: a compact document editor could hide or horizontally clip its audit timeline.
  test('shows the latest document revision on a compact editor', { tag: [...ADMIN_DOCUMENT_CHANGE_HISTORY, '@role:admin', '@outcome:display', '@viewport:compact'] }, async ({ page }) => {
    await installFixtures(page); await openDocumentHistory(page);
    await expect(page.getByTestId('history-latest')).toContainText('Admin E2E');
    await expect(page.getByTestId('history-entry-102')).toContainText('Contenido');
    await expect(page.getByTestId('history-order')).toHaveValue('recent');
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(412);
  });

  // Bug caught: consulting a document version could show a different revision or omit the actual content delta.
  test('consults a document revision with its before and after content', { tag: [...ADMIN_DOCUMENT_CHANGE_HISTORY, '@role:admin', '@outcome:success', '@viewport:compact'] }, async ({ page }) => {
    await installFixtures(page); await openDocumentHistory(page);
    await page.getByTestId('history-entry-102').getByRole('button', { name: 'Consultar' }).click();
    await expect(page.getByTestId('history-version-detail')).toContainText('Versión 2');
    await expect(page.getByTestId('history-version-detail')).toContainText('Contenido anterior');
    await expect(page.getByTestId('history-version-detail')).toContainText('Contenido vigente');
  });

  // Bug caught: a list outage was rendered as an empty history and could not be retried.
  test('retries a failed document history list', { tag: [...ADMIN_DOCUMENT_CHANGE_HISTORY, '@role:admin', '@outcome:failure', '@viewport:compact'] }, async ({ page }) => {
    const calls = []; await installFixtures(page, { fail: 'list', onCall: (call) => calls.push(call) }); await openDocumentHistory(page);
    await expect(page.getByRole('alert')).toContainText('No se pudo cargar el historial');
    await page.getByRole('alert').getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.getByTestId('history-entry-102')).toContainText('Contenido');
    expect(calls.filter((call) => call.kind === 'list' && call.type === 'document')).toHaveLength(2);
  });
});

test.describe('proposal history', () => {
  // Bug caught: the proposal editor could lose its history tab or hide the immutable sent marker.
  test('shows the sent proposal revision in the editor', { tag: [...ADMIN_PROPOSAL_CHANGE_HISTORY, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    await installFixtures(page); await openProposalHistory(page);
    await expect(page.getByTestId('history-latest')).toContainText('Admin E2E');
    await expect(page.getByLabel('Seleccionar versión 3')).toBeVisible();
    await expect(page.getByText('Última versión enviada:')).toBeVisible();
  });

  // Bug caught: a later proposal edit could be substituted for the version actually sent to the client.
  test('compares the sent proposal version with a later investment', { tag: [...ADMIN_PROPOSAL_CHANGE_HISTORY, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    await installFixtures(page); await openProposalHistory(page);
    await page.getByRole('button', { name: 'Consultar envío' }).click();
    await page.getByTestId('history-entry-202').getByRole('button', { name: 'Consultar' }).click();
    await page.getByRole('button', { name: 'Comparar con envío' }).click();
    await expect(page.getByTestId('history-version-detail')).toContainText('Comparación v2 → v3');
    await expect(page.getByTestId('history-version-detail')).toContainText('5000000');
    await expect(page.getByTestId('history-version-detail')).toContainText('6500000');
  });

  // Bug caught: comparison retry could clear selection and submit a different version pair.
  test('retries a failed proposal comparison with the selected pair', { tag: [...ADMIN_PROPOSAL_CHANGE_HISTORY, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
    const calls = []; await installFixtures(page, { fail: 'compare', onCall: (call) => calls.push(call) }); await openProposalHistory(page);
    await page.getByLabel('Seleccionar versión 3').check(); await page.getByLabel('Seleccionar versión 2').check();
    await page.getByTestId('history-compare').click();
    await expect(page.getByRole('alert')).toContainText('No se pudieron comparar las versiones');
    await page.getByRole('alert').getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.getByTestId('history-version-detail')).toContainText('Comparación v2 → v3');
    expect(calls.filter((call) => call.kind === 'compare')).toEqual([{ kind: 'compare', type: 'proposal', from: '201', to: '202' }, { kind: 'compare', type: 'proposal', from: '201', to: '202' }]);
  });
});

test.describe('project history', () => {
  // Bug caught: project access details exposed URLs and notes without the project-specific history panel.
  test('opens project URL history from the access modal', { tag: [...ADMIN_PROJECT_CHANGE_HISTORY, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    await installFixtures(page); await openProjectHistory(page);
    await expect(page.getByTestId('project-access-modal')).toContainText('Atlas');
    await expect(page.getByTestId('history-entry-301')).toContainText('Repositorio');
  });

  // Bug caught: an authorized administrator could not reveal a protected historical credential during investigation.
  test('reveals a protected project value only after the explicit action', { tag: [...ADMIN_PROJECT_CHANGE_HISTORY, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    await installFixtures(page); await openProjectHistory(page);
    await page.getByTestId('history-entry-301').getByRole('button', { name: 'Consultar' }).click();
    await expect(page.getByTestId('history-revealed')).toHaveCount(0);
    await page.getByRole('button', { name: /Revelar contraseña · Producción/ }).click();
    await expect(page.getByTestId('history-revealed')).toHaveText('atlas-production-secret');
  });

  // Bug caught: a failed protected-value request prevented retrying the exact revision and field.
  test('retries a failed protected project reveal', { tag: [...ADMIN_PROJECT_CHANGE_HISTORY, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
    const calls = []; await installFixtures(page, { fail: 'reveal', onCall: (call) => calls.push(call) }); await openProjectHistory(page);
    await page.getByTestId('history-entry-301').getByRole('button', { name: 'Consultar' }).click();
    await page.getByRole('button', { name: /Revelar contraseña · Producción/ }).click();
    await expect(page.getByRole('alert')).toContainText('No se pudo revelar este valor protegido');
    await page.getByRole('alert').getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.getByTestId('history-revealed')).toHaveText('atlas-production-secret');
    expect(calls.filter((call) => call.kind === 'reveal')).toEqual([{ kind: 'reveal', revision: 301, field: 'access.production.password' }, { kind: 'reveal', revision: 301, field: 'access.production.password' }]);
  });
});

test.describe('client history', () => {
  // Bug caught: an expanded client card lacked contact and billing audit information.
  test('shows the client contact history from its expanded card', { tag: [...ADMIN_CLIENT_CHANGE_HISTORY, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    await installFixtures(page); await openClientHistory(page);
    await expect(page.getByTestId('history-entry-402')).toContainText('Correo electrónico');
    await expect(page.getByTestId('history-latest')).toContainText('Admin E2E');
  });

  // Bug caught: changing chronology changed the select label but retained reverse-chronological rows.
  test('loads client entries oldest first when chronology changes', { tag: [...ADMIN_CLIENT_CHANGE_HISTORY, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    const calls = []; await installFixtures(page, { onCall: (call) => calls.push(call) }); await openClientHistory(page);
    await expect(page.locator('[data-testid^="history-entry-"]').first()).toHaveAttribute('data-testid', 'history-entry-402');
    await page.getByTestId('history-order').selectOption('oldest');
    await expect(page.locator('[data-testid^="history-entry-"]').first()).toHaveAttribute('data-testid', 'history-entry-401');
    expect(calls.filter((call) => call.kind === 'list' && call.type === 'client').at(-1).url).toContain('order=oldest');
  });

  // Bug caught: a failed client-version fetch lost the selected revision and forced reopening the card.
  test('retries a failed client version without losing its revision', { tag: [...ADMIN_CLIENT_CHANGE_HISTORY, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
    const calls = []; await installFixtures(page, { fail: 'version', onCall: (call) => calls.push(call) }); await openClientHistory(page);
    await page.getByTestId('history-entry-402').getByRole('button', { name: 'Consultar' }).click();
    await expect(page.getByRole('alert')).toContainText('No se pudo consultar la versión');
    await page.getByRole('alert').getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.getByTestId('history-version-detail')).toContainText('ana@acme.example');
    expect(calls.filter((call) => call.kind === 'version' && call.type === 'client').map((call) => call.id)).toEqual([402, 402]);
  });
});

test.describe('accounting record history', () => {
  test.use(viewportUse('compact'));

  // Bug caught: a mobile accounting row opened data detail but not its per-record history.
  test('shows a card snapshot history in the reusable mobile detail modal', { tag: [...ADMIN_ACCOUNTING_RECORD_HISTORY, '@role:admin', '@outcome:display', '@viewport:compact'] }, async ({ page }) => {
    await installFixtures(page); await openCardHistory(page);
    await expect(page.getByTestId('history-entry-502')).toContainText('Deuda');
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(412);
  });

  // Bug caught: the reusable accounting modal compared values from a different record or revision pair.
  test('compares two card snapshot versions', { tag: [...ADMIN_ACCOUNTING_RECORD_HISTORY, '@role:admin', '@outcome:success', '@viewport:compact'] }, async ({ page }) => {
    const calls = []; await installFixtures(page, { onCall: (call) => calls.push(call) }); await openCardHistory(page);
    await page.getByLabel('Seleccionar versión 2').check(); await page.getByLabel('Seleccionar versión 1').check();
    await page.getByTestId('history-compare').click();
    await expect(page.getByTestId('history-version-detail')).toContainText('Disponible');
    await expect(page.getByTestId('history-version-detail')).toContainText('300000');
    await expect(page.getByTestId('history-version-detail')).toContainText('7550000');
    expect(calls.filter((call) => call.kind === 'compare')).toEqual([{ kind: 'compare', type: 'card_snapshot', from: '501', to: '502' }]);
  });

  // Bug caught: an accounting history request failure appeared as a real empty audit trail.
  test('retries a failed card snapshot history list', { tag: [...ADMIN_ACCOUNTING_RECORD_HISTORY, '@role:admin', '@outcome:failure', '@viewport:compact'] }, async ({ page }) => {
    const calls = []; await installFixtures(page, { fail: 'list', onCall: (call) => calls.push(call) }); await openCardHistory(page);
    await expect(page.getByRole('alert')).toContainText('No se pudo cargar el historial');
    await page.getByRole('alert').getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.getByTestId('history-entry-502')).toContainText('Deuda');
    expect(calls.filter((call) => call.kind === 'list' && call.type === 'card_snapshot')).toHaveLength(2);
  });
});
