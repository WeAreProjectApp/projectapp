/**
 * R-mcp-01/R-mcp-02: MCP accordion controls must remain touch-reachable and
 * long credential/activity values must remain inside the viewport.
 */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { PANEL_VIEWPORTS, viewportUse } from '../helpers/viewports.js';
import { expectCompactModal } from '../helpers/modal-layout.js';
import { batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
const LONG_LABEL = 'credencial-auditoria-externa-con-etiqueta-deliberadamente-extensa-para-medicion';
const LONG_ACTOR = 'mcp_blog_actor_with_an_intentionally_long_service_identity';
const LONG_REQUEST_ID = 'request-123e4567-e89b-12d3-a456-426614174000-with-a-long-trace-suffix';
const connector = {
  slug: 'blog',
  name: 'Blog Publisher',
  description: 'Publica contenido fixture.',
  is_active: false,
  has_token: false,
  token_prefix: '',
  connection_status: 'error',
  credentials: [{
    id: 7,
    label: LONG_LABEL,
    token_prefix: 'scope123',
    allowed_tools: ['get_blog_template'],
    actor: LONG_ACTOR,
    is_usable: true,
    expires_at: null,
    last_used_at: null,
  }],
  recent_events: [{
    event: 'handshake',
    ok: true,
    detail: 'initialize OK',
    credential_prefix: 'scope123',
    request_id: LONG_REQUEST_ID,
    duration_ms: 12,
    created_at: '2026-09-30T10:00:00Z',
  }],
  tools: [
    { name: 'get_blog_template', description: 'Consulta el template del blog.', risk: 'read' },
    { name: 'create_blog_post', description: 'Crea un post.', risk: 'write' },
  ],
};
const scenario = getResponsiveScenario('frontend/pages/panel/mcps/index.vue');
const MCP_DISPLAY_PROFILES = Object.freeze(['portrait', 'compact', 'landscape', 'desktop', 'wide']);

test.setTimeout(60_000);

async function setup(page, { onCredentialMutation } = {}) {
  await setAuthLocalStorage(page, { token: 'mcp-responsive-token', userAuth: { id: 1, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'mcp-connectors/' && method === 'GET') return json([connector]);
    if (apiPath === 'mcp-connectors/blog/generate-token/' && method === 'POST') return json({ connector_url: 'https://projectapp.test/api/mcp/blog/token/', token_prefix: 'token' });
    if (apiPath === 'mcp-connectors/blog/' && method === 'PATCH') return json({ ...connector, is_active: true });
    if (apiPath === 'mcp-connectors/blog/credentials/7/' && ['PATCH', 'DELETE'].includes(method)) {
      onCredentialMutation?.(method);
      return json(connector);
    }
    if (apiPath === 'mcp-connectors/blog/credentials/' && method === 'POST') {
      onCredentialMutation?.(method);
      return json(connector);
    }
    return null;
  });
}

async function navigateToMcps(page) {
  await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(page.getByTestId('mcp-card-blog')).toBeVisible();
  await expect(page.getByTestId('mcp-card-blog')).toContainText('Blog Publisher');
}

async function expectInsideViewport(page, locator, expectedText) {
  await expect(locator).toBeVisible();
  await expect(locator).toContainText(expectedText);
  const geometry = await locator.evaluate((element) => {
    const range = document.createRange();
    range.selectNodeContents(element);
    const fragments = Array.from(range.getClientRects());
    const elementRect = element.getBoundingClientRect();
    return {
      elementLeft: elementRect.left,
      elementRight: elementRect.right,
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
      fragmentLeft: Math.min(...fragments.map((rect) => rect.left)),
      fragmentRight: Math.max(...fragments.map((rect) => rect.right)),
    };
  });
  const viewport = page.viewportSize();
  expect(geometry.elementLeft, `${expectedText} salió por la izquierda`).toBeGreaterThanOrEqual(-1);
  expect(geometry.elementRight, `${expectedText} salió por la derecha`).toBeLessThanOrEqual(viewport.width + 1);
  expect(geometry.fragmentLeft, `${expectedText} tiene glifos fuera por la izquierda`).toBeGreaterThanOrEqual(-1);
  expect(geometry.fragmentRight, `${expectedText} tiene glifos fuera por la derecha`).toBeLessThanOrEqual(viewport.width + 1);
  expect(geometry.scrollWidth, `${expectedText} desborda su contenedor`).toBeLessThanOrEqual(geometry.clientWidth + 1);
}

async function expectSummaryHeight(summary, name) {
  const box = await summary.boundingBox();
  expect(box, `No se pudo medir ${name}`).not.toBeNull();
  expect(box.height, `${name} quedó por debajo del mínimo táctil`).toBeGreaterThanOrEqual(43.5);
}

async function openLongMcpDetails(page) {
  await page.getByTestId('mcp-card-header-blog').click();
  await page.getByTestId('mcp-credentials-toggle-blog').click();
  await page.getByTestId('mcp-activity-toggle-blog').click();
  await page.getByTestId('mcp-tools-toggle-blog').click();
}

for (const profile of MCP_DISPLAY_PROFILES) {
  test.describe(`mcp catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    test('connector reveals long MCP values inside the viewport', { tag: ['@flow:admin-mcps', '@outcome:display', '@responsive:mcp', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`] }, async ({ page }, testInfo) => {
      // Bug this catches: accordions can remain collapsed or let a long label,
      // actor, or request ID escape the screen at a supported viewport.
      await setup(page);
      // quality: allow-deep-link (the authenticated MCP fixture enters the owned page, then operates its real accordions and controls)
      await navigateToMcps(page);
      await openLongMcpDetails(page);

      const credential = page.getByTestId('mcp-credential-7');
      const label = credential.getByText(LONG_LABEL, { exact: true });
      const actor = credential.getByText(`Actor: ${LONG_ACTOR}`);
      const requestId = page.getByTestId('mcp-activity-list-blog').getByText(`Request ${LONG_REQUEST_ID}`, { exact: true });
      const priorityLocator = page.getByText('create_blog_post', { exact: true });
      await expectInsideViewport(page, label, LONG_LABEL);
      await expectInsideViewport(page, actor, `Actor: ${LONG_ACTOR}`);
      await expectInsideViewport(page, requestId, `Request ${LONG_REQUEST_ID}`);
      await expect(priorityLocator).toBeVisible();
      await expect(priorityLocator).toHaveText('create_blog_post');
      await assertResponsiveScenario(page, testInfo, scenario, { profile, priorityLocator });
    });
  });
}

for (const profile of ['portrait', 'compact']) {
  test.describe(`mcp touch summaries · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    test('MCP accordion summaries meet the touch minimum', { tag: ['@flow:admin-mcps', '@outcome:display', '@responsive:mcp', '@responsive-special:mcp', `@viewport:${profile}`, '@responsive-batch:mcp-special-1'] }, async ({ page }) => {
      // Bug this catches: compact or portrait accordion summaries can become
      // too short to operate reliably by touch.
      await setup(page);
      // quality: allow-deep-link (the authenticated MCP fixture enters the owned page, then operates its real accordions and controls)
      await navigateToMcps(page);
      await page.getByTestId('mcp-card-header-blog').click();
      await expect(page.getByTestId('mcp-credentials-toggle-blog')).toHaveText('Credenciales (1)');
      await expectSummaryHeight(page.getByTestId('mcp-credentials-toggle-blog'), 'Credenciales');
      await expectSummaryHeight(page.getByTestId('mcp-activity-toggle-blog'), 'Actividad reciente');
      await expectSummaryHeight(page.getByTestId('mcp-tools-toggle-blog'), 'Funciones disponibles');
    });
  });
}

test.describe('mcp responsive special', () => {
  test.use(viewportUse('portrait'));
  test('cancelling credential editing avoids credential mutation', { tag: ['@flow:admin-mcps', '@outcome:success', '@responsive-special:mcp', '@viewport:portrait', '@responsive-batch:mcp-special-1'] }, async ({ page }, testInfo) => {
    // Bug this catches: the portrait editor can become inaccessible or send a
    // credential write after an operator cancels the form.
    const credentialMutations = [];
    await setup(page, { onCredentialMutation: (method) => credentialMutations.push(method) });
    await navigateToMcps(page);
    await page.getByTestId('mcp-card-header-blog').click();
    await page.getByTestId('mcp-credentials-toggle-blog').click();
    await page.getByTestId('mcp-credential-edit-7').click();

    const form = page.getByTestId('mcp-credential-modal');
    const dialog = page.getByRole('dialog').filter({ has: form });
    const cancel = dialog.getByRole('button', { name: 'Cancelar', exact: true });
    await expect(form).toContainText('Editar credencial');
    await expect(cancel).toHaveText('Cancelar');
    await expectCompactModal(dialog, page.viewportSize(), {
      lines: [{ fields: [dialog.getByTestId('mcp-credential-label'), dialog.getByTestId('mcp-credential-expiry')] }],
    });
    await assertResponsiveScenario(page, testInfo, scenario, {
      profile: 'portrait',
      modalLocator: dialog,
      finalActionLocator: cancel,
    });
    await cancel.click();
    await expect(form).toHaveCount(0);
    expect(credentialMutations).toEqual([]);
  });

  test('connector dismisses its generated token dialog', { tag: ['@flow:admin-mcps', '@outcome:success', '@responsive-special:mcp', '@viewport:portrait', '@responsive-batch:mcp-special-1'] }, async ({ page }) => {
    await setup(page);
    await navigateToMcps(page);
    await page.getByTestId('mcp-card-header-blog').click();
    await page.getByTestId('mcp-generate-token-blog').click();
    await expect(page.getByTestId('mcp-token-url')).toContainText('/api/mcp/blog/token/');
    await page.getByTestId('mcp-token-close').click();
    await expect(page.getByTestId('mcp-token-modal')).toHaveCount(0);
  });

  test('connector exposes its active state after the touch toggle', { tag: ['@flow:admin-mcps', '@outcome:success', '@responsive-special:mcp', '@viewport:portrait', '@responsive-batch:mcp-special-1'] }, async ({ page }) => {
    await setup(page);
    await navigateToMcps(page);
    await page.getByTestId('mcp-card-header-blog').click();
    await page.getByTestId('mcp-toggle-blog').click();
    await expect(page.getByTestId('mcp-status-blog')).toHaveText('Activo');
  });
});

test.describe('mcp compact short viewport', () => {
  test.use({
    ...viewportUse('compact'),
    viewport: { ...PANEL_VIEWPORTS.compact, height: 480 },
  });
  test('credential summary remains reachable in compact short height', { tag: ['@flow:admin-mcps', '@outcome:display', '@responsive:mcp', '@responsive-special:mcp', '@viewport:compact', '@responsive-batch:mcp-special-1'] }, async ({ page }) => {
    // quality: allow-duplicate (per-viewport contract: admin-mcps at compact 412×480)
    // Bug this catches: a short compact viewport can hide the first expanded
    // accordion control below the fold before an operator can reach it.
    await setup(page);
    // quality: allow-deep-link (the authenticated MCP fixture enters the owned page, then operates its real accordions and controls)
    await navigateToMcps(page);
    await page.getByTestId('mcp-card-header-blog').click();
    const credentialsSummary = page.getByTestId('mcp-credentials-toggle-blog');
    await credentialsSummary.scrollIntoViewIfNeeded();
    await credentialsSummary.click();
    const credential = page.getByTestId('mcp-credential-7');
    await expectInsideViewport(page, credential.getByText(LONG_LABEL, { exact: true }), LONG_LABEL);
    await expectInsideViewport(page, credential.getByText(`Actor: ${LONG_ACTOR}`), `Actor: ${LONG_ACTOR}`);
    const box = await credentialsSummary.boundingBox();
    expect(box, 'No se pudo medir Credenciales en alto reducido').not.toBeNull();
    expect(box.y + box.height, 'Credenciales quedó fuera del alto reducido').toBeLessThanOrEqual(481);
  });
});
