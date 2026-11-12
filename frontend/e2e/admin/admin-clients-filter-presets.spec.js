/**
 * FLOW: admin-clients-filter-presets
 *
 * E2E for the two-level filters in /panel/clients: the business module (level 1)
 * decides which subfilters level 2 offers without narrowing anything itself,
 * and those subfilters carry a match count before being applied, narrow the
 * list on click, toggle back off, survive a reload through ?clientModule= and
 * ?clientTab=, combine with the server-side search box and with the transversal
 * client-status selector, and hand off to Hostings already filtered by the
 * client.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_CLIENTS_FILTER_PRESETS } from '../helpers/flow-tags.js';

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({
    user: { username: 'admin', is_staff: true, is_superuser: true },
  }),
};

function client(overrides) {
  return {
    email: 'cliente@test.com',
    phone: '',
    company: '',
    is_onboarded: true,
    is_email_placeholder: false,
    total_proposals: 1,
    projects_count: 0,
    diagnostics_count: 0,
    incomes_count: 0,
    hostings_count: 0,
    active_hostings_count: 0,
    active_projects_count: 0,
    diagnostic_incomes_count: 0,
    diagnostics_without_proposal_count: 0,
    emails_sent_count: 0,
    emails_failed_count: 0,
    last_email_at: null,
    is_orphan: false,
    is_archived: false,
    archived_at: null,
    accepted_count: 0,
    last_status: 'sent',
    last_sent_at: '2026-05-01T10:00:00Z',
    project_types: [],
    market_types: [],
    documents_count: 0,
    documents_no_project_count: 0,
    document_folders_count: 0,
    last_document_at: null,
    nit: '900123456',
    cedula: '',
    billing_code: 'ACME',
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-05-01T10:00:00Z',
    ...overrides,
  };
}

// Two clients pay hosting today, a third only has an expired one, a fourth
// none at all — so "cobrado" (2) and "histórico" (3) are visibly different.
//
// "Sin contacto en los últimos 30 días" is measured against the clock, so the
// one client who counts as warm has to stay warm: a literal date would freeze
// on the day it was written and silently flip the client to cold a month
// later, which is the same reason the Historial's date tabs are builtin
// rather than seeded.
const daysAgo = (n) => new Date(Date.now() - n * 86400000).toISOString();

// The diagnostic and email facts ride the same four rows: Kore was billed a
// diagnostic that never turned into a proposal and has been written to twice
// (once failed, and recently); Mimittos has a diagnostic with a proposal
// after it and one send long enough ago to be cold; Senses has neither.
const CHARGED_ONE = client({
  id: 101, name: 'Kore Healths', company: 'Kore',
  hostings_count: 2, active_hostings_count: 1,
  // También el único con documentos: alimenta el módulo Documentos sin sumar
  // otra fila al fixture.
  documents_count: 3, documents_no_project_count: 1,
  document_folders_count: 2,
  last_document_at: '2026-08-10T10:00:00Z',
  diagnostics_count: 1, diagnostic_incomes_count: 1,
  diagnostics_without_proposal_count: 1,
  emails_sent_count: 2, emails_failed_count: 1,
  last_email_at: daysAgo(2),
});
const CHARGED_TWO = client({
  id: 102, name: 'Mimittos SAS', company: 'Mimittos',
  hostings_count: 1, active_hostings_count: 1,
  diagnostics_count: 1,
  emails_sent_count: 1,
  last_email_at: daysAgo(120),
});
const EXPIRED_ONLY = client({
  id: 103, name: 'Senses Candles', company: 'Senses',
  hostings_count: 1, active_hostings_count: 0,
});
const NO_HOSTING = client({ id: 104, name: 'Vastago Studio', company: 'Vastago' });

const ALL_CLIENTS = [CHARGED_ONE, CHARGED_TWO, EXPIRED_ONLY, NO_HOSTING];

const HOSTING_ROW = {
  id: 9001,
  client: 101,
  client_name: 'Kore Healths - Kore',
  client_display_name: 'Kore Healths',
  project: null,
  project_name: '',
  domain_url: 'https://korehealths.com/',
  monthly_value: '91667.00',
  payment_modality: 'semiannual',
  payment_modality_label: 'Semestral',
  valid_from: '2026-01-20',
  valid_to: '2026-07-20',
  is_active: true,
  total_paid: '550002.00',
  cycles_count: 1,
  billing_email: 'kore@test.com',
  billing_requested_at: null,
  notes: '',
};

const EMAIL_ROW = {
  id: 5001,
  template_key: 'collection_account_sent',
  template_label: 'Cuenta de cobro',
  recipient: 'kore@test.com',
  subject: 'Cuenta de cobro CC-001',
  status: 'sent',
  status_label: 'Sent',
  error_message: '',
  sent_at: '2026-05-01T10:00:00Z',
  origin_action: '',
  origin_action_label: '',
  targets: [],
  has_body: true,
  is_retryable: false,
  retry_blocked_reason: '',
  retry_of: null,
  audience: 'client',
  audience_label: 'Al cliente',
  proposal: null,
};
const FAILED_EMAIL_ROW = {
  ...EMAIL_ROW,
  id: 5002,
  recipient: 'fallido@kore.test',
  status: 'failed',
  status_label: 'Failed',
  error_message: 'SMTP temporalmente no disponible',
  is_retryable: true,
};

function setupMock(page) {
  return mockApi(page, async ({ route, apiPath }) => {
    if (apiPath === 'auth/check/') return authCheck;

    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }

    if (apiPath === 'proposals/client-profiles/status-counts/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ all: 4, active: 4, orphans: 0, archived: 0 }),
      };
    }

    if (/^proposals\/client-profiles\/\d+\/emails\/$/.test(apiPath)) {
      const audience = new URL(route.request().url())
        .searchParams.get('audience') || 'client';
      const rows = audience === 'internal' ? [] : [EMAIL_ROW, FAILED_EMAIL_ROW];
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: rows, count: rows.length, page: 1, num_pages: 1,
        }),
      };
    }

    if (apiPath === 'proposals/client-profiles/') {
      const search = (new URL(route.request().url())
        .searchParams.get('search') || '').toLowerCase();
      const rows = search
        ? ALL_CLIENTS.filter((c) => c.name.toLowerCase().includes(search))
        : ALL_CLIENTS;
      return { status: 200, contentType: 'application/json', body: JSON.stringify(rows) };
    }

    // Destino del salto del pill de Documentos: el gestor monta lista,
    // contadores, carpetas, etiquetas y el picker de proyectos del filtro.
    if (apiPath === 'documents/counts/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          documents: { active: 0, archived: 0, unfiled_active: 0, unfiled_archived: 0 },
          folders: { active: 0, archived: 0 },
        }),
      };
    }
    if (apiPath === 'documents/') {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    if (apiPath === 'document-folders/' || apiPath === 'document-tags/') {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }

    if (apiPath === 'accounting/hostings/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [HOSTING_ROW], meta: {} }),
      };
    }

    if (apiPath.startsWith('accounting/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], meta: {} }),
      };
    }

    return null;
  });
}

async function gotoClients(page) {
  await page.goto('/panel/clients');
  await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible({ timeout: 30_000 });
}

const rowsShown = (page) => page.locator('[data-testid^="client-row-"]');

/** Level 1 is the way into level 2: the subfilters only exist under a module. */
async function openModule(page, moduleId) {
  await page.getByTestId(`clients-module-${moduleId}`).click();
}

test.describe('Admin Clients Filter Presets', () => {
  test.describe.configure({ timeout: 60_000 });

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true, is_superuser: true },
    });
  });

  test('picking a module swaps the subfilters without narrowing the list', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (reaching /panel/clients through the sidebar is
    // its own flow and is baselined the same way across every clients spec;
    // these tests start from the list because the filter bar is the subject)
    await setupMock(page);
    await gotoClients(page);

    await openModule(page, 'hosting');

    // The module groups; it does not cut. All four clients are still listed.
    await expect(rowsShown(page)).toHaveCount(4);
    await expect(page.getByTestId('filter-tabs-tab-hosting-charged')).toBeVisible();
    await expect(page.getByTestId('filter-tabs-tab-no-hosting')).toBeVisible();

    // And the subfilters of the module left behind are gone from the row.
    await openModule(page, 'proposals');
    await expect(page.getByTestId('filter-tabs-tab-hosting-charged')).toHaveCount(0);
    await expect(page.getByTestId('filter-tabs-tab-status-draft')).toBeVisible();
    await expect(rowsShown(page)).toHaveCount(4);
  });

  test('the count each subfilter advertises is the list it actually leaves', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (same baseline as its sibling above)
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'hosting');

    // Readable with the full list still on screen, before applying anything,
    // and in parentheses so the number never reads as part of the name.
    await expect(rowsShown(page)).toHaveCount(4);
    await expect(page.getByTestId('filter-tabs-count-hosting-charged')).toHaveText('(2)');
    await expect(page.getByTestId('filter-tabs-count-hosting-any')).toHaveText('(3)');
    await expect(page.getByTestId('filter-tabs-count-no-hosting')).toHaveText('(1)');

    // And the advertised number is honest: applying it leaves exactly that many.
    await page.getByTestId('filter-tabs-tab-hosting-any').click();
    await expect(rowsShown(page)).toHaveCount(3);
    await expect(page.getByTestId('filter-tabs-count-hosting-any')).toHaveText('(3)');
  });

  test('an empty subfilter shows (0) rather than hiding its count', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (same baseline as its sibling above)
    await setupMock(page);
    await gotoClients(page);

    // No client in the fixture has an active project: knowing the set is empty
    // is information, and hiding it would force a click to find out.
    await openModule(page, 'projects');
    await expect(page.getByTestId('filter-tabs-count-active-project')).toHaveText('(0)');
  });

  test('applying the hosting subfilter narrows the list and stamps the URL', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'hosting');

    await page.getByTestId('filter-tabs-tab-hosting-charged').click();

    await expect(rowsShown(page)).toHaveCount(2);
    await expect(page.getByText('Kore Healths')).toBeVisible();
    await expect(page.getByText('Senses Candles')).not.toBeVisible();
    await expect(page).toHaveURL(/clientTab=hosting-charged/);
    await expect(page).toHaveURL(/clientModule=hosting/);
  });

  test('pressing the applied subfilter again restores the full list', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'hosting');

    await page.getByTestId('filter-tabs-tab-hosting-charged').click();
    await expect(rowsShown(page)).toHaveCount(2);

    await page.getByTestId('filter-tabs-tab-hosting-charged').click();

    await expect(rowsShown(page)).toHaveCount(4);
    await expect(page.getByText('Vastago Studio')).toBeVisible();
    await expect(page).not.toHaveURL(/clientTab=/);
    // Still reading the Hosting module, just without a cut applied.
    await expect(page.getByTestId('filter-tabs-tab-hosting-charged')).toBeVisible();
  });

  test('removing the chip also drops the tab that was highlighting it', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'hosting');

    await page.getByTestId('filter-tabs-tab-hosting-charged').click();
    await expect(rowsShown(page)).toHaveCount(2);

    // The chip lives in the filter panel and names the module it comes from.
    await page.getByTestId('clients-filter-toggle').click();
    await expect(page.getByText('Hosting: Con hosting cobrado')).toBeVisible();
    await page.getByTestId('client-filter-chip-hostingStatus').click();

    // Tab, chip and panel are one state: the list reopens and no tab stays lit.
    await expect(rowsShown(page)).toHaveCount(4);
    await expect(page.getByText('Hosting: Con hosting cobrado')).toHaveCount(0);
    await expect(page).not.toHaveURL(/clientTab=hosting-charged/);
  });

  test('the panel can rebuild a predefined filter on its own', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);

    // Every predefined filter is also a composable control, so a cut is
    // reachable without going through its tab.
    await page.getByTestId('clients-filter-toggle').click();
    await page.getByTestId('client-filter-hosting-status').click();
    await page.getByRole('checkbox', { name: 'Con hosting cobrado' }).check();

    await expect(rowsShown(page)).toHaveCount(2);
    await expect(page.getByText('Kore Healths')).toBeVisible();

    // Y ahora el eje admite varios valores: sumar "histórico" ensancha el
    // corte en vez de reemplazarlo.
    await page.getByRole('checkbox', { name: 'Con hosting (histórico)' }).check();
    await expect(rowsShown(page)).toHaveCount(3);
  });

  test('the shared link reopens the list already filtered', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the shareable URL is itself the feature under
    // test; reaching the view by clicking would exercise the click path, which
    // the sibling tests already cover)
    // quality: allow-no-interaction (the contract is that the filter is
    // restored before the user touches anything — interacting first would mask
    // a broken restore)
    await setupMock(page);
    await page.goto('/panel/clients?clientTab=hosting-any');
    await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible({ timeout: 30_000 });

    await expect(rowsShown(page)).toHaveCount(3);
    await expect(page.getByText('Kore Healths')).toBeVisible();
    await expect(page.getByText('Vastago Studio')).not.toBeVisible();
    // The subfilter brought its own module along, so level 2 is the right one.
    await expect(page.getByTestId('filter-tabs-tab-no-hosting')).toBeVisible();
  });

  test('search narrows the subfilter instead of cancelling it', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'hosting');

    await page.getByTestId('filter-tabs-tab-hosting-charged').click();
    await expect(rowsShown(page)).toHaveCount(2);

    const searched = page.waitForRequest((req) => req.url().includes('search=Mimittos'));
    await page.getByTestId('clients-search-input').fill('Mimittos');
    await searched;

    // The subfilter is still on: only the searched client that also pays hosting.
    await expect(rowsShown(page)).toHaveCount(1);
    await expect(page.getByText('Mimittos SAS')).toBeVisible();
    await expect(page).toHaveURL(/clientTab=hosting-charged/);
  });

  test('the client status is transversal and travels in the URL', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'hosting');
    await page.getByTestId('filter-tabs-tab-hosting-charged').click();

    // Status combines with the module instead of replacing it: the request
    // carries the status cut while the subfilter stays applied.
    const refetched = page.waitForRequest((req) => req.url().includes('orphans=true'));
    await page.getByTestId('clients-status-orphans').click();
    await refetched;

    await expect(page).toHaveURL(/status=orphans/);
    await expect(page.getByTestId('filter-tabs-tab-hosting-charged')).toBeVisible();
  });

  test('the row count opens Hostings already filtered by that client', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);

    // The hosting count only appears while the Hosting module is being read.
    await expect(page.getByTestId('client-hostings-101')).toHaveCount(0);
    await openModule(page, 'hosting');
    await expect(page.getByTestId('client-hostings-101')).toHaveText('2 hostings');

    await page.getByTestId('client-hostings-101').click();

    await expect(page).toHaveURL(/\/panel\/accounting\/hostings\?client=101/);
    // Landed on Hostings with that client's row in view and the client filter
    // already seeded (one chip, not the unfiltered list).
    await expect(page.getByRole('link', { name: 'https://korehealths.com/' }))
      .toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('accounting-filter-chip')).toHaveCount(1);
  });
  test('the Documentos module shows its three subfilters with honest counts', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (same baseline as its siblings above)
    await setupMock(page);
    await gotoClients(page);

    await openModule(page, 'documents');

    // El módulo agrupa sin recortar; cada subfiltro anuncia su corte real.
    await expect(rowsShown(page)).toHaveCount(4);
    await expect(page.getByTestId('filter-tabs-count-docs-with')).toHaveText('(1)');
    await expect(page.getByTestId('filter-tabs-count-docs-none')).toHaveText('(3)');
    await expect(page.getByTestId('filter-tabs-count-docs-no-project')).toHaveText('(1)');
    await expect(page.getByTestId('filter-tabs-count-docs-with-folder')).toHaveText('(1)');

    await page.getByTestId('filter-tabs-tab-docs-with').click();
    await expect(rowsShown(page)).toHaveCount(1);
  });

  test('reading "Con carpeta" the row counts folders, and still jumps to Documentos', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'documents');

    // Con el módulo abierto la píldora cuenta documentos…
    await expect(page.getByTestId('client-documents-101')).toContainText('3 docs');

    await page.getByTestId('filter-tabs-tab-docs-with-folder').click();

    // …y bajo este corte cuenta lo que el corte mira: sus carpetas.
    await expect(rowsShown(page)).toHaveCount(1);
    await expect(page.getByTestId('client-folders-101')).toContainText('2 carpetas');

    await page.getByTestId('client-folders-101').click();

    await expect(page).toHaveURL(/\/panel\/documents\?client=101/);
  });

  test('the row doc count opens Documents already filtered by that client', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);

    // El conteo (con la fecha del último) sólo aparece con el módulo activo.
    await expect(page.getByTestId('client-documents-101')).toHaveCount(0);
    await openModule(page, 'documents');
    await expect(page.getByTestId('client-documents-101')).toContainText('3 docs');

    await page.getByTestId('client-documents-101').click();

    await expect(page).toHaveURL(/\/panel\/documents\?client=101/);
    await expect(page.getByTestId('doc-association-filters'))
      .toBeVisible({ timeout: 30_000 });
  });

  test('the diagnostic module lists the ones no proposal followed', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'diagnostics');

    // The commercially valuable cut: Kore was diagnosed and nothing followed;
    // Mimittos was diagnosed and a proposal did.
    await expect(page.getByTestId('filter-tabs-count-diagnostic-unconverted'))
      .toHaveText('(1)');
    await page.getByTestId('filter-tabs-tab-diagnostic-unconverted').click();

    await expect(rowsShown(page)).toHaveCount(1);
    await expect(page.getByText('Kore Healths')).toBeVisible();
    await expect(page).toHaveURL(/clientTab=diagnostic-unconverted/);
  });

  test('a billed diagnostic counts even where no diagnostic entity exists', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (same baseline as its siblings above)
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'diagnostics');

    // Only Kore has a diagnostic income; two clients have no diagnostic at all.
    await expect(page.getByTestId('filter-tabs-count-diagnostic-billed'))
      .toHaveText('(1)');
    await expect(page.getByTestId('filter-tabs-count-no-diagnostic'))
      .toHaveText('(2)');
  });

  test('the emails module counts who has gone quiet, never-written included', {
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);
    await openModule(page, 'emails');

    // Cold is deliberately a superset of "sin ningun correo": the two who
    // never got anything, plus Mimittos whose only send is months old.
    await expect(page.getByTestId('filter-tabs-count-no-emails')).toHaveText('(2)');
    await expect(page.getByTestId('filter-tabs-count-emails-cold')).toHaveText('(3)');

    await page.getByTestId('filter-tabs-tab-emails-failed').click();

    await expect(rowsShown(page)).toHaveCount(1);
    await expect(page.getByText('Kore Healths')).toBeVisible();
  });

  test('the row shows the contact and opens the history from it', {
    // Bug caught: raw sent/failed states leaked as English labels in the client email history.
    tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoClients(page);

    // Like the hosting pill, it only appears while its module is being read.
    await expect(page.getByTestId('client-emails-101')).toHaveCount(0);
    await openModule(page, 'emails');
    await expect(page.getByTestId('client-emails-101')).toContainText('2 correos');

    await page.getByTestId('client-emails-101').click();

    await expect(page.getByTestId('client-emails-modal')).toBeVisible();
    await expect(page.getByTestId('email-log-row-5001')).toContainText('Enviado');
    await expect(page.getByTestId('email-log-row-5001')).not.toContainText('Sent');
    await expect(page.getByTestId('email-log-row-5002')).toContainText('Fallido');
    await expect(page.getByTestId('email-log-row-5002')).not.toContainText('Failed');
  });
});
