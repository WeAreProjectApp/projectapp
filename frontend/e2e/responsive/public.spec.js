/** R-public-01: public CTAs and fixture content must remain usable without floating UI covering the primary action. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';
import { financingProgramFixture } from '../helpers/financing-fixture.js';
import { SECURE_LINK_TOKEN, publicStatus, revealedContent, secureLinkTypes } from '../helpers/secure-links.js';

const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
const uuid = '11111111-1111-4111-8111-111111111111';
const landingWhatsappUrl = 'https://wa.me/573238122373?text=Hi%2C%20I%20want%20to%20quote%20my%20software%20project';
const post = { id: 1, title: 'Artículo responsive', title_es: 'Artículo responsive', title_en: 'Responsive article', slug: 'responsive-fixture', excerpt: 'Contenido fixture concreto.', excerpt_es: 'Contenido fixture concreto.', excerpt_en: 'Concrete fixture content.', content: '<p>Contenido fixture concreto.</p>', content_es: '<p>Contenido fixture concreto.</p>', content_en: '<p>Concrete fixture content.</p>', is_published: true, published_at: '2026-09-01T00:00:00Z', category: 'ai', read_time_minutes: 4 };
const work = { id: 1, title: 'Proyecto responsive', title_es: 'Proyecto responsive', title_en: 'Responsive project', slug: 'responsive-fixture', excerpt: 'Caso fixture.', excerpt_es: 'Caso fixture.', excerpt_en: 'Fixture case.', content_json: {}, is_published: true, published_at: '2026-09-01T00:00:00Z' };
const moduleFixture = { slug: 'responsive-module', icon: '◫', name: 'Módulo responsive', summary: 'Detalle fixture accionable.', what_is: 'Módulo de prueba.', purpose: 'Probar CTA.', problems_solved: [], integrations: [], implementation_requirements: [] };
const tree = { handle: 'responsive-fixture', kind: 'personal', display_name: 'Perfil responsive', role: 'ProjectApp', vcard_first_name: 'Perfil', vcard_last_name: 'Responsive', buttons: [{ id: 1, tier: 'primary', action: 'vcard', label: 'Guardar contacto', href: '', kind: 'download-vcard', is_pending: false, is_active: true }], pwa_enabled: false, badge_text: 'FIXTURE' };
const proposal = { id: 1, uuid, title: 'Propuesta responsive', client_name: 'Cliente fixture', status: 'sent', language: 'es', total_investment: '5000000', currency: 'COP', requirement_groups: [], sections: [{ id: 1, section_type: 'greeting', title: 'Bienvenida', order: 0, is_enabled: true, content_json: { proposalTitle: 'Propuesta responsive', clientName: 'Cliente fixture' } }, { id: 2, section_type: 'executive_summary', title: 'Resumen', order: 1, is_enabled: true, content_json: { title: 'Propuesta responsive', paragraphs: ['Resultado concreto'] } }] };
const diagnostic = { uuid, title: 'Diagnóstico responsive', client_name: 'Cliente fixture', status: 'sent', language: 'es', sections: [{ id: 1, section_type: 'purpose', title: 'Propósito', order: 0, is_enabled: true, visibility: 'both', content_json: { title: 'Propósito', paragraphs: ['Resultado concreto'] } }], render_context: { client_name: 'Cliente fixture', currency: 'COP' } };
const visualKeys = [
  'frontend/pages/index.vue', 'frontend/pages/landing-apps.vue', 'frontend/pages/landing-software.vue', 'frontend/pages/landing-web-design.vue', 'frontend/pages/about-us.vue', 'frontend/pages/contact.vue', 'frontend/pages/contact-success.vue', 'frontend/pages/portfolio-works/index.vue', 'frontend/pages/portfolio-works/[slug].vue', 'frontend/pages/blog/index.vue', 'frontend/pages/blog/[slug].vue', 'frontend/pages/lk/[handle].vue', 'frontend/pages/privacy-policy.vue', 'frontend/pages/terms-and-conditions.vue', 'frontend/pages/auth/linkedin/callback.vue', 'frontend/pages/[...slug].vue', 'frontend/pages/additional-modules/index.vue', 'frontend/pages/additional-modules/share/[uuid].vue', 'frontend/pages/partnership-program/index.vue', 'frontend/pages/proposal/[uuid]/index.vue', 'frontend/pages/diagnostic/[uuid]/index.vue', 'frontend/pages/secure-link/index.vue', 'frontend/pages/secure-link/view.vue',
].map(getResponsiveScenario);
const linkedInCallbackScenario = getResponsiveScenario('frontend/pages/auth/linkedin/callback.vue');
const fallbackScenario = getResponsiveScenario('frontend/pages/[...slug].vue');
const interactiveVisualKeys = visualKeys.filter((scenario) => (
  scenario.catalogKey !== linkedInCallbackScenario.catalogKey
  && scenario.catalogKey !== fallbackScenario.catalogKey
));
const flows = {
  'frontend/pages/index.vue': 'public-home', 'frontend/pages/landing-apps.vue': 'public-landing-apps', 'frontend/pages/landing-software.vue': 'public-landing-software', 'frontend/pages/landing-web-design.vue': 'public-landing-web-design', 'frontend/pages/about-us.vue': 'public-about-us', 'frontend/pages/contact.vue': 'public-contact-submit', 'frontend/pages/contact-success.vue': 'public-contact-submit', 'frontend/pages/portfolio-works/index.vue': 'public-portfolio', 'frontend/pages/portfolio-works/[slug].vue': 'public-portfolio-detail', 'frontend/pages/blog/index.vue': 'blog-list', 'frontend/pages/blog/[slug].vue': 'blog-detail', 'frontend/pages/lk/[handle].vue': 'public-linktree-view', 'frontend/pages/privacy-policy.vue': 'public-privacy-policy', 'frontend/pages/terms-and-conditions.vue': 'public-terms-conditions', 'frontend/pages/auth/linkedin/callback.vue': 'admin-blog-linkedin-connect', 'frontend/pages/[...slug].vue': 'public-route-not-found', 'frontend/pages/additional-modules/index.vue': 'public-additional-modules-detail', 'frontend/pages/additional-modules/share/[uuid].vue': 'public-additional-modules-share', 'frontend/pages/partnership-program/index.vue': 'public-financing-terms', 'frontend/pages/proposal/[uuid]/index.vue': 'proposal-view-navigation', 'frontend/pages/diagnostic/[uuid]/index.vue': 'diagnostic-public-view', 'frontend/pages/secure-link/index.vue': 'public-secure-link-create', 'frontend/pages/secure-link/view.vue': 'public-secure-link-reveal',
};
const outcomes = {
  'frontend/pages/auth/linkedin/callback.vue': 'error',
  'frontend/pages/[...slug].vue': 'failure',
  'frontend/pages/partnership-program/index.vue': 'success',
};
const resolvedRoutes = {
  'frontend/pages/portfolio-works/index.vue': '/en-us/portfolio-works',
  'frontend/pages/portfolio-works/[slug].vue': '/en-us/portfolio-works/responsive-fixture',
  'frontend/pages/blog/index.vue': '/en-us/blog',
  'frontend/pages/blog/[slug].vue': '/en-us/blog/responsive-fixture',
  'frontend/pages/proposal/[uuid]/index.vue': `/en-us/proposal/${uuid}`,
  'frontend/pages/diagnostic/[uuid]/index.vue': `/en-us/diagnostic/${uuid}`,
  'frontend/pages/partnership-program/index.vue': '/es-co/partnership-program',
  'frontend/pages/secure-link/index.vue': '/es-co/secure-link',
  'frontend/pages/secure-link/view.vue': `/es-co/secure-link/view#${SECURE_LINK_TOKEN}`,
  'frontend/pages/[...slug].vue': '/responsive-e2e-not-found',
};

async function setupPublic(page) {
  await page.addInitScript(() => localStorage.setItem('proposal_onboarding_seen', 'true'));
  await page.addInitScript(() => {
    localStorage.setItem('projectapp-additional-modules-guide-seen', 'true');
    localStorage.setItem('projectapp-financing-guide-seen', 'true');
  });
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'portfolio/' && method === 'GET') return json([work]);
    if (apiPath === 'portfolio/responsive-fixture/' && method === 'GET') return json(work);
    if (apiPath === 'blog/' && method === 'GET') return json({ results: [post], count: 1, page: 1, total_pages: 1 });
    if (apiPath === 'blog/responsive-fixture/' && method === 'GET') return json(post);
    if (apiPath === 'linktrees/public/responsive-fixture/' && method === 'GET') return json(tree);
    if (apiPath === 'additional-modules/public/' && method === 'GET') return json({ language: 'es', total_modules: 1, categories: [{ slug: 'fixture', name: 'Fixture', modules: [moduleFixture] }] });
    if (apiPath === `additional-modules/public/shares/${uuid}/` && method === 'GET') return json({ language: 'es', total_modules: 1, is_shared: true, categories: [{ slug: 'fixture', name: 'Fixture', modules: [moduleFixture] }] });
    if (apiPath === `additional-modules/public/shares/${uuid}/track/` && method === 'POST') return json({ status: 'recorded' });
    if (apiPath === 'financing/public/' && method === 'GET') return json(financingProgramFixture('es'));
    if (apiPath === `proposals/${uuid}/`) return json(proposal);
    if (apiPath === `diagnostics/public/${uuid}/`) return json(diagnostic);
    if (apiPath.includes('/track')) return json({ ok: true, view_count: 1 });
    if (apiPath.endsWith('/respond/') && method === 'POST') return json({ ...diagnostic, status: 'accepted' });
    if (apiPath === 'new-contact/' && method === 'POST') return json({ id: 1, subject: 'Contacto responsive' });
    if (apiPath === 'secure-links/public/types/' && method === 'GET') return json({ types: secureLinkTypes });
    if (apiPath === 'secure-links/public/status/' && method === 'POST') return json(publicStatus());
    if (apiPath === 'secure-links/public/reveal/' && method === 'POST') return json(revealedContent);
    return null;
  });
}

async function switchToSpanish(page) {
  await page.getByRole('button', { name: 'Switch to Spanish' }).click();
  await expect(page).toHaveURL(/\/es-co\//);
}

async function openLandingWhatsapp(page) {
  await page.context().route('https://wa.me/**', (route) => route.fulfill({ status: 200, contentType: 'text/html', body: '<main>WhatsApp</main>' }));
  const hero = page.locator('section').filter({ has: page.getByRole('heading', { level: 1 }) });
  const cta = hero.getByRole('link', { name: 'Contact us on WhatsApp', exact: true });
  await expect(cta).toHaveAttribute('href', landingWhatsappUrl);
  const popupPromise = page.waitForEvent('popup');
  await cta.click();
  const popup = await popupPromise;
  await expect(popup).toHaveURL(landingWhatsappUrl);
  await popup.close();
  return cta;
}

async function downloadLinktreeContact(page) {
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Guardar contacto', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('perfil-responsive-projectapp.vcf');
  return page.getByRole('button', { name: 'Guardar contacto', exact: true });
}

async function openProposalExecutiveView(page) {
  const gatewayHeading = page.getByRole('heading', { name: '¿Cómo prefieres explorar esta propuesta?' });
  await page.getByRole('button', { name: /Vista Ejecutiva/ }).click();
  await expect(gatewayHeading).not.toBeVisible();
}

async function exercise(page, scenario) {
  await setupPublic(page);
  // quality: allow-deep-link (public catalog routes include emailed, QR and static legal entry points with fixture-resolved dynamic values)
  const route = resolvedRoutes[scenario.catalogKey] ?? scenario.resolvedUrl;
  await page.goto(route, { waitUntil: 'domcontentloaded' });
  const entries = {
    'frontend/pages/index.vue': { action: () => openLandingWhatsapp(page), assert: (locator) => expect(locator).toHaveAttribute('href', landingWhatsappUrl) },
    'frontend/pages/landing-apps.vue': { action: async () => { await switchToSpanish(page); return page.getByRole('heading', { level: 1, name: /Tu App Lista para Descargar\s+en 30 Días\./ }); }, assert: (locator) => expect(locator).toContainText('Tu App Lista para Descargar') },
    'frontend/pages/landing-software.vue': { action: async () => { await switchToSpanish(page); return page.getByRole('heading', { level: 1, name: /Desarrollamos el Software que tu empresa necesita\.\s+Listo en 30 Días\./ }); }, assert: (locator) => expect(locator).toContainText('Desarrollamos el Software que tu empresa necesita.') },
    'frontend/pages/landing-web-design.vue': { action: async () => { await switchToSpanish(page); return page.getByRole('heading', { level: 1, name: /En el panorama digital actual, un diseño web profesional es crucial/ }); }, assert: (locator) => expect(locator).toContainText('En el panorama digital actual') },
    'frontend/pages/about-us.vue': { action: async () => { await switchToSpanish(page); return page.getByRole('heading', { level: 1, name: /Buscamos la\s+Perfección\s+Todo el Tiempo/ }); }, assert: (locator) => expect(locator).toContainText('Buscamos la') },
    'frontend/pages/contact.vue': { action: async () => { const fullName = page.getByPlaceholder('Full name'); await fullName.fill('Contacto responsive'); await page.getByRole('button', { name: /500-5K/ }).click(); return fullName; }, assert: (locator) => expect(locator).toHaveValue('Contacto responsive') },
    'frontend/pages/contact-success.vue': { action: async () => { await switchToSpanish(page); return page.getByRole('heading', { level: 1, name: '¡Gracias por contactarnos! ✨', exact: true }); }, assert: (locator) => expect(locator).toContainText('¡Gracias por contactarnos!') },
    'frontend/pages/portfolio-works/index.vue': { action: async () => { await page.getByRole('list', { name: 'Portfolio projects' }).getByRole('link', { name: /^Proyecto responsive/ }).click(); await expect(page).toHaveURL('/en-us/portfolio-works/responsive-fixture'); await page.getByRole('link', { name: 'All projects', exact: true }).click(); await expect(page).toHaveURL('/en-us/portfolio-works'); return page.getByRole('list', { name: 'Portfolio projects' }).getByRole('link', { name: /^Proyecto responsive/ }); }, assert: (locator) => expect(locator).toContainText('Proyecto responsive') },
    'frontend/pages/portfolio-works/[slug].vue': { action: async () => { await page.getByRole('link', { name: 'All projects', exact: true }).click(); await expect(page).toHaveURL('/en-us/portfolio-works'); await page.getByRole('list', { name: 'Portfolio projects' }).getByRole('link', { name: /^Proyecto responsive/ }).click(); await expect(page).toHaveURL('/en-us/portfolio-works/responsive-fixture'); return page.getByRole('heading', { name: 'Proyecto responsive', exact: true }); }, assert: (locator) => expect(locator).toHaveText('Proyecto responsive') },
    'frontend/pages/blog/index.vue': { action: async () => { await page.getByRole('link', { name: 'Artículo responsive', exact: true }).click(); await expect(page).toHaveURL('/en-us/blog/responsive-fixture'); await page.getByRole('link', { name: 'Back to blog', exact: true }).click(); await expect(page).toHaveURL('/en-us/blog'); return page.getByRole('link', { name: 'Artículo responsive', exact: true }); }, assert: (locator) => expect(locator).toHaveText('Artículo responsive') },
    'frontend/pages/blog/[slug].vue': { action: async () => { await page.getByRole('link', { name: 'Back to blog', exact: true }).click(); await expect(page).toHaveURL('/en-us/blog'); await page.getByRole('link', { name: 'Artículo responsive', exact: true }).click(); await expect(page).toHaveURL('/en-us/blog/responsive-fixture'); return page.getByRole('heading', { name: 'Artículo responsive', exact: true }); }, assert: (locator) => expect(locator).toHaveText('Artículo responsive') },
    'frontend/pages/lk/[handle].vue': { action: () => downloadLinktreeContact(page), assert: (locator) => expect(locator).toHaveText('Guardar contacto') },
    'frontend/pages/privacy-policy.vue': { action: async () => { await switchToSpanish(page); return page.getByRole('heading', { level: 1, name: 'Política de Privacidad', exact: true }); }, assert: (locator) => expect(locator).toHaveText('Política de Privacidad') },
    'frontend/pages/terms-and-conditions.vue': { action: async () => { await switchToSpanish(page); return page.getByRole('heading', { level: 1, name: 'Términos y Condiciones', exact: true }); }, assert: (locator) => expect(locator).toHaveText('Términos y Condiciones') },
    'frontend/pages/additional-modules/index.vue': { action: async () => { await page.getByTestId('additional-module-card-responsive-module').click(); return page.getByTestId('additional-module-detail-modal'); }, assert: (locator) => expect(locator).toContainText('Módulo responsive') },
    'frontend/pages/additional-modules/share/[uuid].vue': { action: async () => { await page.getByTestId('additional-module-card-responsive-module').click(); return page.getByTestId('additional-module-detail-modal'); }, assert: (locator) => expect(locator).toContainText('Módulo responsive') },
    'frontend/pages/partnership-program/index.vue': { action: async () => { await page.getByTestId('financing-term-trigger-code-custody').click(); return page.getByTestId('financing-term-code-custody'); }, assert: (locator) => expect(locator).toContainText('La custodia no transfiere la propiedad intelectual.') },
    'frontend/pages/proposal/[uuid]/index.vue': { action: async () => { await openProposalExecutiveView(page); const next = page.getByTestId('nav-next'); await expect(next).toBeVisible({ timeout: 35_000 }); return next; }, assert: (locator) => expect(locator).toContainText('Siguiente') },
    'frontend/pages/diagnostic/[uuid]/index.vue': { action: async () => { await page.getByTestId('diagnostic-start-journey').click(); return page.getByText('Propósito', { exact: true }); }, assert: (locator) => expect(locator).toHaveText('Propósito') },
    'frontend/pages/secure-link/index.vue': { action: async () => { const name = page.getByTestId('secure-link-public-name'); await name.fill('Cliente responsive'); return name; }, assert: (locator) => expect(locator).toHaveValue('Cliente responsive') },
    'frontend/pages/secure-link/view.vue': { action: async () => { await page.getByTestId('secure-link-reveal').click(); return page.getByTestId('secure-link-text-service'); }, assert: (locator) => expect(locator).toHaveText('Django admin') },
  }[scenario.catalogKey];
  const priorityLocator = await entries.action();
  await entries.assert(priorityLocator);
  return priorityLocator;
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`public catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    for (const scenario of interactiveVisualKeys) {
      test(`${scenario.label} keeps fixture content reachable after its CTA`, { tag: [`@flow:${flows[scenario.catalogKey]}`, `@outcome:${outcomes[scenario.catalogKey] ?? 'display'}`, '@responsive:public', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`] }, async ({ page }, testInfo) => {
        const priorityLocator = await exercise(page, scenario);
        await expect(priorityLocator).toHaveCount(1);
        await assertResponsiveScenario(page, testInfo, scenario, { profile, priorityLocator });
      });
    }

    test('LinkedIn callback failure keeps its explicit browser-return message visible', { tag: ['@flow:admin-blog-linkedin-connect', '@outcome:error', '@responsive:public', `@responsive-scenario:${linkedInCallbackScenario.catalogKey}`, `@responsive-batch:${batchForScenario(linkedInCallbackScenario.catalogKey)}`, `@viewport:${profile}`] }, async ({ page }, testInfo) => {
      await setupPublic(page);
      // quality: allow-no-interaction (the query-free OAuth callback is a terminal browser return and has no safe in-page action)
      await page.goto(linkedInCallbackScenario.resolvedUrl, { waitUntil: 'domcontentloaded' });
      const priorityLocator = page.getByText('No se recibió código de autorización.', { exact: true });
      await expect(priorityLocator).toHaveText('No se recibió código de autorización.');
      await assertResponsiveScenario(page, testInfo, linkedInCallbackScenario, { profile, priorityLocator });
    });

    test('catch-all keeps its public not-found state inside the responsive shell', { tag: ['@flow:public-route-not-found', '@outcome:failure', '@responsive:public', `@responsive-scenario:${fallbackScenario.catalogKey}`, `@responsive-batch:${batchForScenario(fallbackScenario.catalogKey)}`, `@viewport:${profile}`] }, async ({ page }, testInfo) => {
      await setupPublic(page);
      // quality: allow-no-interaction (the catch-all is a terminal public-layout state and intentionally exposes no control)
      await page.goto(resolvedRoutes[fallbackScenario.catalogKey], { waitUntil: 'domcontentloaded' });
      const priorityLocator = page.getByText('Page not found', { exact: true });
      await expect(priorityLocator).toHaveText('Page not found');
      await assertResponsiveScenario(page, testInfo, fallbackScenario, { profile, priorityLocator });
    });
  });
}

test.describe('public responsive CTA specials', () => {
  test.use(viewportUse('compact'));
  test('proposal next CTA advances past the fixture greeting', { tag: ['@flow:proposal-view-navigation', '@outcome:success', '@responsive-special:public', '@viewport:compact', '@responsive-batch:public-special-1'] }, async ({ page }) => {
    await setupPublic(page); await page.addInitScript(() => localStorage.setItem('proposal_onboarding_seen', 'true'));
    await page.goto(`/en-us/proposal/${uuid}`, { waitUntil: 'domcontentloaded' }); await openProposalExecutiveView(page); await page.getByTestId('nav-next').click();
    await expect(page.getByText('Resultado concreto', { exact: true })).toBeVisible();
  });
});
