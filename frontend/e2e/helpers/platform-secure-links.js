import { json } from './secure-links.js';
import { mockPlatformClient, setPlatformAuth } from './platform-auth.js';
import { mockApi } from './api.js';
import { waitForNuxtApp } from './navigation.js';

export const platformProject = Object.freeze({
  id: 1,
  name: 'Portal de comercio ACME',
  description: 'Proyecto de prueba aislado',
  status: 'active',
  status_label: 'Activo',
  current_state: { id: 2, name: 'Activo', system_key: 'active', operational_effect: 'operating', color: 'emerald' },
  progress: 65,
  client_id: mockPlatformClient.id,
  client_name: 'Client E2E',
  client_email: mockPlatformClient.email,
  client_company: mockPlatformClient.company_name,
});

export function platformSecureLink(overrides = {}) {
  return {
    id: 7,
    project: 1,
    title: 'Acceso de despliegue',
    secret_type: 'credentials',
    type_label: 'Credenciales de acceso',
    language: 'es',
    audience: 'team',
    status: 'active',
    validity_days: 7,
    expires_at: '2026-10-09T15:00:00Z',
    consumed_at: null,
    revoked_at: null,
    activation_count: 1,
    created_at: '2026-10-01T15:00:00Z',
    updated_at: '2026-10-01T15:00:00Z',
    replaces: null,
    replaced_by: null,
    capabilities: { copy_url: true, revoke: true, reactivate: false },
    ...overrides,
  };
}

export const platformSecureEvents = Object.freeze([
  { id: 1, kind: 'created', created_at: '2026-10-01T15:00:00Z', actor_kind: 'client', references: {} },
]);

const credentialsCatalog = Object.freeze([{
  key: 'credentials',
  label_es: 'Credenciales de acceso',
  label_en: 'Access credentials',
  fields: [
    { key: 'service', label_es: 'Nombre del sistema', label_en: 'System name', kind: 'text', required: false, max_length: 200 },
    { key: 'url', label_es: 'Dirección del sistema', label_en: 'System address', kind: 'url', required: false, max_length: 500 },
    { key: 'username', label_es: 'Usuario de la cuenta', label_en: 'Account username', kind: 'text', required: false, max_length: 200 },
    { key: 'password', label_es: 'Contraseña que quieres compartir', label_en: 'Password to share', kind: 'secret', required: true, max_length: 2000 },
    { key: 'note', label_es: 'Nota', label_en: 'Note', kind: 'textarea', required: false, max_length: 2000 },
  ],
}]);

export const createdPlatformSecureUrl = 'https://projectapp.test/secure-link/view#e2e-platform-token';

function listPayload(rows) {
  return {
    results: rows,
    count: rows.length,
    page: 1,
    page_size: 25,
    counts: { active: rows.filter((row) => row.status === 'active').length, consumed: rows.filter((row) => row.status === 'consumed').length, expired: 0, revoked: rows.filter((row) => row.status === 'revoked').length, all: rows.length },
  };
}

/**
 * Mock the JWT platform boundary only. The state is intentionally metadata-only:
 * test assertions may inspect the controlled POST body but never list history
 * or browser storage for a secret.
 */
export async function installPlatformSecureLinksMock(page, options = {}) {
  const state = { links: (options.links || [platformSecureLink()]).map((link) => structuredClone(link)) };
  const calls = { creates: [], events: 0, urls: 0, revokes: 0, reactivations: [] };
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(mockPlatformClient);
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([platformProject]);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') return json(platformProject);
    if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') return json([]);
    if (apiPath === 'accounts/projects/1/secure-links/types/' && method === 'GET') return json({ types: credentialsCatalog });
    if (apiPath === 'accounts/projects/1/secure-links/' && method === 'GET') return json(listPayload(state.links));
    if (apiPath === 'accounts/projects/1/secure-links/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      calls.creates.push(payload);
      if (options.create) return options.create({ payload, state, calls });
      const successor = platformSecureLink({ id: 8, title: payload.title, replaces: payload.replaces, updated_at: '2026-10-02T15:00:00Z' });
      state.links.unshift(successor);
      if (payload.replaces) {
        const source = state.links.find((link) => link.id === payload.replaces);
        if (source) source.replaced_by = successor.id;
      }
      return json({ link: successor, url: createdPlatformSecureUrl, replayed: false }, 201);
    }
    const match = apiPath.match(/^accounts\/projects\/1\/secure-links\/(\d+)\/(events\/|link\/|revoke\/|reactivate\/)?$/);
    if (!match) return null;
    const link = state.links.find((row) => row.id === Number(match[1]));
    if (!link) return json({ code: 'not_found' }, 404);
    if (match[2] === 'events/' && method === 'GET') {
      calls.events += 1;
      if (options.events) return options.events({ link, state, calls });
      return json({ results: platformSecureEvents, count: platformSecureEvents.length, page: 1, page_size: 25 });
    }
    if (match[2] === 'link/' && method === 'POST') {
      calls.urls += 1;
      if (options.url) return options.url({ link, state, calls });
      return json({ url: createdPlatformSecureUrl });
    }
    if (match[2] === 'revoke/' && method === 'POST') {
      calls.revokes += 1;
      if (options.revoke) return options.revoke({ link, state, calls });
      Object.assign(link, { status: 'revoked', revoked_at: '2026-10-02T15:00:00Z', updated_at: '2026-10-02T15:00:00Z', capabilities: { copy_url: false, revoke: true, reactivate: true } });
      return json(link);
    }
    if (match[2] === 'reactivate/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      calls.reactivations.push(payload);
      if (options.reactivate) return options.reactivate({ link, payload, state, calls });
      Object.assign(link, { status: 'active', revoked_at: null, updated_at: '2026-10-03T15:00:00Z', capabilities: { copy_url: true, revoke: true, reactivate: false } });
      return json({ link, url: createdPlatformSecureUrl });
    }
    if (!match[2] && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      Object.assign(link, { title: payload.title, updated_at: '2026-10-03T15:00:00Z' });
      return json(link);
    }
    return null;
  });
  return { state, calls };
}

export async function openPlatformSecureLinks(page) {
  await setPlatformAuth(page, { user: mockPlatformClient });
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await page.locator('[data-testid="project-row-1"]:visible, [data-testid="project-card-1"]:visible').click();
  const secureLinks = page.getByRole('link', { name: /^(Enlaces seguros|Secure links)$/ });
  await secureLinks.click();
  await page.waitForURL(/\/platform\/projects\/1\/secure-links$/, { waitUntil: 'domcontentloaded' });
  await page.getByTestId('platform-secure-workspace').waitFor({ state: 'visible' });
}
