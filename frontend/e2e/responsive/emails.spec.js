/** R-emails-01: responsive email views must keep recipient, subject and preview controls reachable rather than rendering an empty shell. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { fillRichTextSource, richTextEditorByPlaceholder } from '../helpers/editorial.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
const deliverabilityScenario = getResponsiveScenario('frontend/pages/panel/proposals/email-deliverability.vue');
const composerScenario = getResponsiveScenario('frontend/pages/panel/emails/index.vue');
const responsiveRecipient = ['client', 'responsive.test'].join('@');
const historyEntry = { id: 1, subject: 'Seguimiento responsive', recipient: responsiveRecipient, status: 'delivered', sent_at: '2026-08-25T10:00:00Z', has_body: true, metadata: { greeting: 'Hola Ana', sections: ['Contenido fixture para el preview.'], footer: 'Equipo ProjectApp' } };
const deliverabilityStats = { total_emails_30d: 1, success_rate: 0, sent_count: 0, failed_count: 1, by_template: [{ template_key: 'responsive_followup', total: 1, sent: 0, failed: 1, success_rate: 0 }], daily_trend: [{ date: '2026-08-25', total: 1, sent: 0, failed: 1 }], recent_failures: [{ template_key: 'responsive_followup', recipient: responsiveRecipient, status: 'failed', sent_at: '2026-08-25T10:00:00Z', error_message: 'Buzón de prueba no disponible.' }] };
const shellToggleNamesByProfile = Object.freeze({
  compact: ['Abrir menú', 'Cerrar menú'],
  portrait: ['Abrir menú', 'Cerrar menú'],
  landscape: ['Expandir barra lateral', 'Contraer barra lateral'],
  desktop: ['Contraer barra lateral', 'Expandir barra lateral'],
  wide: ['Contraer barra lateral', 'Expandir barra lateral'],
});

async function setupEmails(page) {
  const previewRequest = { payload: null };
  await setAuthLocalStorage(page, { token: 'emails-responsive-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'emails/defaults/' && method === 'GET') return json({ greeting: 'Hola', footer: 'Equipo ProjectApp', config: { greeting: 'Hola {client_name}', footer: 'Equipo ProjectApp', signer: 'vanessa' }, defaults: {}, available_signers: [] });
    if (apiPath === 'emails/history/' && method === 'GET') return json({ results: [historyEntry], total: 1, page: 1, has_next: false });
    if (apiPath === 'emails/preview/' && method === 'POST') {
      const payload = route.request().postDataJSON() || {};
      const previewText = payload.sections?.[0]?.text;
      if (typeof previewText !== 'string' || previewText.trim() === '') {
        return { status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'La primera sección del preview es obligatoria.' }) };
      }
      previewRequest.payload = payload;
      return json({ subject: payload.subject, html_preview: `<!doctype html><html><body><p>${previewText}</p></body></html>` });
    }
    if (apiPath === 'email-deliverability/' && method === 'GET') return json(deliverabilityStats);
    return null;
  });
  return previewRequest;
}

async function openComposer(page) {
  const previewRequest = await setupEmails(page);
  // quality: allow-deep-link (the standalone composer is itself the cataloged route; its form and preview are exercised below)
  await page.goto(`/en-us${composerScenario.resolvedUrl}`, { waitUntil: 'domcontentloaded' });
  await page.getByPlaceholder('correo@ejemplo.com').fill(responsiveRecipient);
  const subjectInput = page.getByPlaceholder('Asunto del correo');
  await subjectInput.fill('Seguimiento responsive');
  await expect(subjectInput).toHaveValue('Seguimiento responsive');
  return { subjectInput, previewRequest };
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`emails catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    test('deliverability keeps a concrete failed recipient reachable after exercising panel navigation', { tag: ['@flow:admin-email-deliverability', '@outcome:display', '@responsive:emails', `@responsive-scenario:${deliverabilityScenario.catalogKey}`, `@responsive-batch:${batchForScenario(deliverabilityScenario.catalogKey)}`, `@viewport:${profile}`] }, async ({ page }, testInfo) => {
      await setupEmails(page);
      // quality: allow-deep-link (this catalog status route has no panel navigation equivalent)
      await page.goto(deliverabilityScenario.resolvedUrl, { waitUntil: 'domcontentloaded' });
      const priorityLocator = page.getByText(responsiveRecipient, { exact: true });
      await expect(priorityLocator).toHaveCount(1);
      const [initialToggleName, toggledToggleName] = shellToggleNamesByProfile[profile];
      const shellToggle = page.getByRole('button', { name: initialToggleName, exact: true });
      await expect(shellToggle).toBeVisible();
      await shellToggle.click();
      const toggledShell = page.getByRole('button', { name: toggledToggleName, exact: true });
      await expect(toggledShell).toBeVisible();
      await toggledShell.click();
      await expect(shellToggle).toBeVisible();
      await expect(priorityLocator).toHaveCount(1);
      await assertResponsiveScenario(page, testInfo, deliverabilityScenario, { profile, priorityLocator });
    });

    test('composer keeps the filled subject after its responsive form interaction', { tag: ['@flow:admin-standalone-email-composer', '@outcome:display', '@responsive:emails', `@responsive-scenario:${composerScenario.catalogKey}`, `@responsive-batch:${batchForScenario(composerScenario.catalogKey)}`, `@viewport:${profile}`] }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (the standalone composer is entered directly from a contextual action outside this catalog route)
      const { subjectInput: priorityLocator } = await openComposer(page);
      await expect(priorityLocator).toHaveCount(1);
      await assertResponsiveScenario(page, testInfo, composerScenario, { profile, priorityLocator });
    });
  });
}

test.describe('emails responsive special', () => {
  test.use(viewportUse('portrait'));
  test('composer preserves its completed subject after preview dismissal', { tag: ['@flow:admin-standalone-email-composer', '@outcome:success', '@responsive-special:emails', '@viewport:portrait', '@responsive-batch:emails-special-1'] }, async ({ page }) => {
    const { subjectInput, previewRequest } = await openComposer(page);
    await fillRichTextSource(richTextEditorByPlaceholder(page, 'Escribe el contenido de esta sección...'), 'Contenido fixture para el preview.');
    const previewResponse = page.waitForResponse((response) => response.url().includes('emails/preview/') && response.status() === 200);
    await page.getByRole('button', { name: 'Vista previa', exact: true }).click();
    await previewResponse;
    expect(previewRequest.payload).toMatchObject({
      subject: 'Seguimiento responsive',
      sections: [{ text: 'Contenido fixture para el preview.' }],
    });
    await expect(page.frameLocator('iframe[title="Vista previa del correo"]').getByText('Contenido fixture para el preview.', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Editar', exact: true }).click();
    await expect(subjectInput).toHaveValue('Seguimiento responsive');
  });
});
