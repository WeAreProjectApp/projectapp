/**
 * E2E: las filas navegables del panel se comportan como enlaces.
 *
 * Antes eran contenedores con un manejador de clic: ctrl+clic abría en la misma
 * pestaña (Documentos) o funcionaba sólo porque la página reimplementaba a mano
 * un pedazo del ancla (Propuestas, Diagnósticos).
 *
 * De los cinco gestos del criterio, tres se automatizan acá — clic simple,
 * ctrl+clic y clic con la rueda. Los otros dos ("abrir en pestaña nueva" y
 * "copiar dirección del enlace" del menú contextual) son chrome del navegador,
 * fuera de la página: lo que sí se puede afirmar es su precondición exacta —
 * que el título es un `a[href]` con la dirección correcta — y eso es lo que
 * asserta el primer test de cada listado.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_DOCUMENT_LIST, ADMIN_PROPOSAL_LIST, ADMIN_DIAGNOSTIC_LIST,
} from '../helpers/flow-tags.js';

const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
const authCheck = json({ user: { username: 'admin', is_staff: true } });

const documents = [{
  id: 1, title: 'Contrato de Servicios', status: 'published',
  client_name: 'ACME Corp', created_at: '2026-03-01T10:00:00Z', tag_details: [],
}];

// Las filas de subcarpeta sólo existen DENTRO de una carpeta: en la cima el
// listado sólo muestra documentos y la barra lateral lleva las carpetas.
const folders = [
  { id: 5, name: 'Clientes', parent: null, document_count: 0, children_count: 1 },
  { id: 9, name: 'Contratos 2024', parent: 5, document_count: 0, children_count: 0 },
];

const proposals = [{
  id: 1, uuid: '11111111-1111-1111-1111-111111111111', title: 'Plataforma E2E',
  client_name: 'Cliente E2E', client_email: 'a@e2e.com', client_phone: '+573001234567',
  status: 'draft', language: 'es', total_investment: '5000000', currency: 'COP',
  view_count: 0, heat_score: 0, sent_at: null, is_active: true, created_at: '2026-01-01T12:00:00Z',
}];

const diagnostics = [{
  id: 1, title: 'Diagnóstico Acme Corp', client: { name: 'Acme Corp', email: 'acme@example.com' },
  client_name: 'Acme Corp', status: 'draft', language: 'es', investment_amount: null,
  currency: 'COP', view_count: 0, created_at: '2026-04-01T10:00:00Z', updated_at: '2026-04-01T10:00:00Z',
}];

const handlers = {
  documents: async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'documents/') return json(documents);
    if (apiPath === 'documents/1/') return json({ ...documents[0], content: '# Contrato' });
    if (apiPath === 'document-folders/') return json(folders);
    if (apiPath === 'document-tags/') return json([]);
    return null;
  },
  proposals: async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'proposals/') return json(proposals);
    if (apiPath === 'proposals/1/') return json(proposals[0]);
    if (apiPath === 'proposals/dashboard/') return json({ total: 1, conversion_rate: 0 });
    if (apiPath === 'proposals/alerts/') return json([]);
    return null;
  },
  diagnostics: async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'diagnostics/') return json(diagnostics);
    if (apiPath === 'diagnostics/1/') return json(diagnostics[0]);
    return null;
  },
};

// Un listado a probar: dónde vive, qué celda es inerte (para que el gesto lo
// atienda el manejador de FILA y no el ancla), y a dónde debe llevar.
const LISTINGS = [
  {
    name: 'Documentos',
    tags: ADMIN_DOCUMENT_LIST,
    url: '/panel/documents',
    handler: handlers.documents,
    inertCell: 'doc-client-cell-1',
    titleLink: 'document-open-1',
    hrefPattern: /\/panel\/documents\/1\/edit\?from=\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?panel\/documents\?by=project%26focus=1$/,
    detail: /\/panel\/documents\/1\/edit/,
  },
  {
    name: 'Propuestas',
    tags: ADMIN_PROPOSAL_LIST,
    url: '/panel/proposals',
    handler: handlers.proposals,
    inertCell: 'proposal-row-id-1',
    titleLink: 'proposal-open-1',
    hrefPattern: /\/panel\/proposals\/1\/edit$/,
    detail: /\/panel\/proposals\/1\/edit/,
  },
  {
    name: 'Diagnósticos',
    tags: ADMIN_DIAGNOSTIC_LIST,
    url: '/panel/diagnostics',
    handler: handlers.diagnostics,
    inertCell: 'diagnostic-row-client-1',
    titleLink: 'diagnostic-open-1',
    hrefPattern: /\/panel\/diagnostics\/1\/edit$/,
    detail: /\/panel\/diagnostics\/1\/edit/,
  },
];

for (const listing of LISTINGS) {
  test.describe(`Filas navegables · ${listing.name}`, () => {
    test.setTimeout(60_000);

    test.beforeEach(async ({ page }) => {
      await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8800, role: 'admin', is_staff: true } });
    });

    test(`${listing.name}: el título de la fila publica la dirección y se abre con enter`, {
      tag: [...listing.tags, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      await mockApi(page, listing.handler);
      await page.goto(listing.url, { waitUntil: 'domcontentloaded' });

      const link = page.getByTestId(listing.titleLink);
      // La precondición de "abrir en pestaña nueva" y "copiar dirección" del
      // menú contextual: sin este href, ninguna de las dos existe.
      await expect(link).toHaveAttribute('href', listing.hrefPattern, { timeout: 20_000 });

      await link.press('Enter');

      // waitForURL y no sólo un timeout más grande: la ruta de detalle puede
      // estar sin compilar y el dev server la construye en el primer acceso,
      // así que hay que esperar la navegación antes de afirmar sobre ella.
      await page.waitForURL(listing.detail, { timeout: 40_000 });
      await expect(page).toHaveURL(listing.detail);
    });

    test(`${listing.name}: un clic simple en el cuerpo de la fila abre en la misma pestaña`, {
      tag: [...listing.tags, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      await mockApi(page, listing.handler);
      await page.goto(listing.url, { waitUntil: 'domcontentloaded' });

      await page.getByTestId(listing.inertCell).click({ timeout: 20_000 });

      await page.waitForURL(listing.detail, { timeout: 40_000 });
      await expect(page).toHaveURL(listing.detail);
    });

    test(`${listing.name}: ctrl+clic en el cuerpo de la fila abre otra pestaña`, {
      tag: [...listing.tags, '@role:admin', '@outcome:success'],
    }, async ({ page, context }) => {
      // Mocks a nivel de contexto: la pestaña nueva es otra página y sin esto
      // saldría a la API real.
      await mockApi(context, listing.handler);
      await page.goto(listing.url, { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId(listing.inertCell)).toBeVisible({ timeout: 20_000 });

      const popupPromise = context.waitForEvent('page');
      await page.getByTestId(listing.inertCell).click({ modifiers: ['ControlOrMeta'] });
      const popup = await popupPromise;

      await popup.waitForURL(listing.detail, { timeout: 25_000 });
      // El listado no se movió: eso es lo que hacía inservible el atajo.
      await expect(page).toHaveURL(new RegExp(`${listing.url}(\\?|$)`));
    });

    test(`${listing.name}: el clic con la rueda en el cuerpo de la fila abre otra pestaña`, {
      tag: [...listing.tags, '@role:admin', '@outcome:success'],
    }, async ({ page, context }) => {
      await mockApi(context, listing.handler);
      await page.goto(listing.url, { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId(listing.inertCell)).toBeVisible({ timeout: 20_000 });

      const popupPromise = context.waitForEvent('page');
      await page.getByTestId(listing.inertCell).click({ button: 'middle' });
      const popup = await popupPromise;

      await popup.waitForURL(listing.detail, { timeout: 25_000 });
      await expect(page).toHaveURL(new RegExp(`${listing.url}(\\?|$)`));
    });
  });
}

test.describe('Filas navegables · carpetas de Documentos', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8800, role: 'admin', is_staff: true } });
  });

  // La dirección `?folder=` ya existía y era restaurable; lo que faltaba era
  // que alguna fila la publicara.
  for (const locale of ['en-us', 'es-co']) {
    test(`Documentos: ctrl+clic abre la carpeta en ${locale}`, {
      tag: [...ADMIN_DOCUMENT_LIST, '@role:admin', '@outcome:success'],
    }, async ({ page, context }) => {
      await mockApi(context, handlers.documents);
      // Parado dentro de «Clientes», que es donde vive la fila de subcarpeta.
      await page.goto(`/${locale}/panel/documents?folder=5`, { waitUntil: 'domcontentloaded' });

      const folder = page.getByTestId('folder-open-9').first();
      await expect(folder).toHaveAttribute('href', `/${locale}/panel/documents?folder=9&by=project`, { timeout: 20_000 });

      const popupPromise = context.waitForEvent('page');
      await folder.click({ modifiers: ['ControlOrMeta'] });
      const popup = await popupPromise;
      await popup.bringToFront();

      await expect(popup).toHaveURL(new RegExp(`/${locale}/panel/documents\\?folder=9&by=project$`), { timeout: 25_000 });
      await expect(popup.getByRole('heading', { name: 'Contratos 2024', exact: true })).toBeVisible();
      // El listado de origen se quedó donde estaba.
      await expect(page).toHaveURL(new RegExp(`/${locale}/panel/documents\\?folder=5&by=project$`));
    });
  }
});

test.describe('Filas navegables · menú de acciones', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8800, role: 'admin', is_staff: true } });
  });

  // El menú es la única vía en pantallas táctiles, donde ctrl+clic no existe.
  // Y es donde vivía el <nuxtlink> muerto: los ítems con `to` se renderizaban
  // como un elemento desconocido, sin href y sin navegar.
  test('Propuestas: el menú de la fila ofrece abrir en otra pestaña como enlace real', {
    tag: [...ADMIN_PROPOSAL_LIST, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, handlers.proposals);
    await page.goto('/panel/proposals', { waitUntil: 'domcontentloaded' });

    await page.getByRole('button', { name: /Acciones de/ }).click({ timeout: 20_000 });

    const newTab = page.getByRole('link', { name: /Abrir en pestaña nueva/ });
    await expect(newTab).toHaveAttribute('href', /\/panel\/proposals\/1\/edit$/);
    await expect(newTab).toHaveAttribute('target', '_blank');
    // El vecino que estaba muerto: ahora es un enlace con dirección propia.
    await expect(page.getByRole('link', { name: /Editar propuesta/ }))
      .toHaveAttribute('href', /\/panel\/proposals\/1\/edit$/);
  });
});
