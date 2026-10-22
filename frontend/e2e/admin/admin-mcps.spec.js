/**
 * E2E tests for the MCPs panel section (superuser-only).
 *
 * FLOW: admin-mcps
 * Covers: connector inventory, one-time secrets, active toggle, scoped
 *         credential lifecycle and superuser gating redirect.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_MCPS } from '../helpers/flow-tags.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

const CONNECTOR = {
  slug: 'content',
  name: 'Contenido',
  description: 'Permite a Claude gestionar el contenido del blog y LinkedIn.',
  is_active: false,
  has_token: false,
  token_prefix: '',
  last_used_at: null,
  tool_count: 2,
  risk_counts: { read: 1, write: 1, sensitive: 0 },
  is_legacy: false,
  credentials: [
    {
      id: 7,
      label: 'Auditoría',
      token_prefix: 'scope123',
      allowed_tools: ['get_blog_template'],
      actor: 'mcp_content',
      is_usable: true,
      expires_at: null,
      revoked_at: null,
      last_used_at: null,
    },
  ],
  connection_status: 'error',
  recent_events: [
    {
      event: 'origin_rejected',
      ok: false,
      detail: 'https://evil.example',
      created_at: '2026-07-03T10:00:00-05:00',
    },
    {
      event: 'handshake',
      ok: true,
      detail: 'initialize OK',
      credential_prefix: 'scope123',
      request_id: '123e4567-e89b-12d3-a456-426614174000',
      duration_ms: 12,
      object_refs: [{ field: 'post_id', value: 8 }],
      created_at: '2026-07-03T09:58:00-05:00',
    },
  ],
  tools: [
    { name: 'get_blog_template', description: 'Template JSON de contenido.', risk: 'read' },
    { name: 'create_blog_post', description: 'Crea un post.', risk: 'write' },
  ],
};

const RETIRING_CONNECTOR = {
  slug: 'blog',
  name: 'Gestor de Blogs',
  description: 'Compatibilidad temporal para configuraciones anteriores.',
  is_active: true,
  has_token: true,
  token_prefix: 'legacy12',
  tool_count: 1,
  risk_counts: { read: 1, write: 0, sensitive: 0 },
  is_legacy: true,
  lifecycle: 'retiring',
  replacement: 'content',
  last_legacy_use_at: '2026-10-18T14:30:00Z',
  consumers_verified_at: '2026-10-17T10:00:00Z',
  connection_status: 'connected',
  credentials: [{
    id: 17,
    label: 'Automatización antigua',
    token_prefix: 'legacy17',
    allowed_tools: ['get_blog_template'],
    actor: 'mcp_blog',
    is_usable: true,
    expires_at: null,
    revoked_at: null,
    last_used_at: '2026-10-18T14:30:00Z',
  }],
  recent_events: [],
  tools: [{ name: 'get_blog_template', description: 'Consulta el template del blog.', risk: 'read' }],
};

const SECTION_CONNECTORS = [
  {
    slug: 'commercial',
    name: 'Comercial',
    description: 'Gestiona la relación con clientes y el proceso de venta: fichas, propuestas, diagnósticos, documentos contractuales, seguimiento, correos y valores predeterminados. Organiza sus funciones en Clientes, Propuestas y Diagnósticos, y Configuración. Para paquetes de horas y módulos adicionales usa Nuestra oferta; para alianzas y células usa Programas.',
    section_note: 'Comercial reúne Clientes; Propuestas y Diagnósticos; y Configuración (Defaults y entregabilidad email). Paquetes de horas y módulos adicionales se administran en Nuestra oferta (offerings). Los programas y sus contratos se administran en Programas (programs).',
  },
  {
    slug: 'offerings',
    name: 'Nuestra oferta',
    description: 'Administra lo que ofrecemos al cliente: paquetes de horas, precios y configuración; y módulos adicionales, categorías, orden, enlaces compartidos, PDFs y videos. Las propuestas y los diagnósticos se gestionan en Comercial. Las condiciones, contratos y versiones de las alianzas y células se gestionan en Programas.',
    section_note: 'Nuestra oferta reúne Paquetes de horas y Módulos adicionales. Clientes, propuestas, diagnósticos y Defaults están en Comercial (commercial). Programa de Alianza, Building with Us y Células están en Programas (programs).',
  },
  {
    slug: 'programs',
    name: 'Programas',
    description: 'Administra nuestros programas y sus condiciones. Reúne las alianzas —Programa de Alianza y Building with Us— y las Células de Building on Demand, con sus acuerdos, contratos, economía interna, documentos y versiones. Para preparar una propuesta usa Comercial; para paquetes de horas y módulos adicionales usa Nuestra oferta.',
    section_note: 'Programas reúne las alianzas (Programa de Alianza y Building with Us) y las Células de Building on Demand, incluidos contratos, economía y versiones. Paquetes de horas y módulos adicionales están en Nuestra oferta (offerings); clientes, propuestas y diagnósticos en Comercial (commercial).',
  },
].map((connector) => ({
  ...connector,
  is_active: true,
  has_token: false,
  token_prefix: '',
  last_used_at: null,
  tool_count: 1,
  risk_counts: { read: 1, write: 0, sensitive: 0 },
  is_legacy: false,
  credentials: [],
  connection_status: 'connected',
  recent_events: [],
  tools: [{ name: `get_${connector.slug}_summary`, description: 'Consulta el resumen del módulo.', risk: 'read' }],
}));

const TOKEN_RESPONSE = {
  connector_url: 'https://projectapp.co/api/mcp/content/e2e-token-abc123/',
  token_prefix: 'e2e-toke',
};

const SCOPED_TOKEN_RESPONSE = {
  id: 7,
  label: 'Auditoría',
  connector_url: 'https://projectapp.co/api/mcp/content/e2e-scoped-token/',
  token_prefix: 'e2e-scop',
  allowed_tools: ['get_blog_template'],
};

function buildHandler({ isSuperuser = true, credentialCreateError = false } = {}) {
  const connector = JSON.parse(JSON.stringify(CONNECTOR));
  const retiringConnector = JSON.parse(JSON.stringify(RETIRING_CONNECTOR));
  const sectionConnectors = JSON.parse(JSON.stringify(SECTION_CONNECTORS));
  return ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { username: 'admin', is_staff: true, is_superuser: isSuperuser },
        }),
      };
    }
    if (apiPath === 'mcp-connectors/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([connector, ...sectionConnectors, retiringConnector]),
      };
    }
    if (apiPath === 'mcp-connectors/content/generate-token/' && method === 'POST') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TOKEN_RESPONSE),
      };
    }
    if (apiPath === 'mcp-connectors/content/credentials/' && method === 'POST') {
      if (credentialCreateError) {
        return {
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ label: 'Ya existe una credencial con esa etiqueta.' }),
        };
      }
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(SCOPED_TOKEN_RESPONSE),
      };
    }
    if (apiPath === 'mcp-connectors/content/credentials/7/' && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      connector.credentials[0] = {
        ...connector.credentials[0],
        allowed_tools: payload.allowed_tools,
        expires_at: payload.expires_at,
      };
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(connector),
      };
    }
    if (apiPath === 'mcp-connectors/content/credentials/7/rotate/' && method === 'POST') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...SCOPED_TOKEN_RESPONSE,
          connector_url: 'https://projectapp.co/api/mcp/content/e2e-replacement-token/',
        }),
      };
    }
    if (apiPath === 'mcp-connectors/content/credentials/7/' && method === 'DELETE') {
      connector.credentials[0] = {
        ...connector.credentials[0],
        is_usable: false,
        revoked_at: '2026-09-02T12:00:00Z',
      };
      return { status: 204, body: '' };
    }
    if (apiPath === 'mcp-connectors/content/' && method === 'PATCH') {
      connector.is_active = true;
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(connector),
      };
    }
    if (apiPath === 'mcp-connectors/blog/credentials/17/' && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      retiringConnector.credentials[0] = {
        ...retiringConnector.credentials[0],
        allowed_tools: payload.allowed_tools,
        expires_at: payload.expires_at,
      };
      return { status: 200, contentType: 'application/json', body: JSON.stringify(retiringConnector) };
    }
    if (apiPath === 'mcp-connectors/blog/credentials/17/' && method === 'DELETE') {
      retiringConnector.credentials[0] = {
        ...retiringConnector.credentials[0],
        is_usable: false,
        revoked_at: '2026-10-19T12:00:00Z',
      };
      return { status: 204, body: '' };
    }
    return null;
  };
}

async function assertSegmentedConnectorDescriptions(page) {
  await mockApi(page, buildHandler());
  await page.goto('/en-us/panel/mcps', { waitUntil: 'domcontentloaded' });

  await page.getByTestId('mcp-card-header-commercial').click();
  await expect(page.getByTestId('mcp-detail-commercial').filter({ hasText: 'Gestiona la relación con clientes y el proceso de venta' })).toBeVisible();
  await expect(page.getByTestId('mcp-scope-commercial').filter({ hasText: 'Paquetes de horas y módulos adicionales se administran en Nuestra oferta' })).toBeVisible();

  await page.getByTestId('mcp-card-header-offerings').click();
  await expect(page.getByTestId('mcp-detail-offerings').filter({ hasText: 'Administra lo que ofrecemos al cliente' })).toBeVisible();
  await expect(page.getByTestId('mcp-scope-offerings').filter({ hasText: 'Programa de Alianza, Building with Us y Células están en Programas' })).toBeVisible();

  await page.getByTestId('mcp-card-header-programs').click();
  await expect(page.getByTestId('mcp-detail-programs').filter({ hasText: 'Administra nuestros programas y sus condiciones' })).toBeVisible();

  const horizontalOverflow = await page.evaluate(() => (
    Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
      - document.documentElement.clientWidth
  ));
  expect(horizontalOverflow).toBeLessThanOrEqual(1);
}

test.describe('Panel MCPs', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('renders the canonical content connector card with its tools', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:display', '@responsive:mcp'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    // quality: allow-deep-link (authenticated panel landing; MCPs is reached through the sidebar below)
    await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
    await page
      .getByRole('navigation', { name: 'Navegación del panel' })
      .getByRole('link', { name: 'MCPs', exact: true })
      .click();

    await expect(page).toHaveURL(/\/panel\/mcps/);
    await expect(page.getByTestId('mcp-card-content')).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('mcp-card-header-content')).toContainText('Contenido');

    // Collapsed accordion row: token, status and tools live in the body and
    // are hidden until the row is expanded.
    await expect(page.getByText('sin generar')).not.toBeVisible();
    await expect(page.getByText('create_blog_post')).not.toBeVisible();

    // Collapsible step-by-step connection guide (native <details>) is present.
    await expect(page.getByTestId('mcps-guide')).toBeVisible();
    await expect(page.getByText('¿Cómo conectar un conector a Claude?')).toBeVisible();

    // Expanding the row reveals the detail body: token, connection status,
    // and the activity/tools sub-accordions.
    await page.getByTestId('mcp-card-header-content').click();
    await expect(page.getByTestId('mcp-detail-content')).toBeVisible();
    await expect(page.getByText('sin generar')).toBeVisible();

    await expect(page.getByTestId('mcp-connection-content')).toContainText('Error de conexión');
    await expect(page.getByTestId('mcp-connection-content')).toContainText('https://evil.example');
    await expect(page.getByTestId('mcp-risk-summary-content')).toContainText('Lectura 1');
    await expect(page.getByTestId('mcp-risk-summary-content')).toContainText('Edición 1');

    // Recent activity sub-accordion expands with the event trail.
    await page.getByTestId('mcp-activity-toggle-content').click();
    await expect(page.getByTestId('mcp-activity-list-content')).toContainText('Origin rechazado');
    await expect(page.getByTestId('mcp-activity-list-content')).toContainText('Conexión (initialize)');
    await expect(page.getByTestId('mcp-activity-list-content')).toContainText('Credencial scope123');
    await expect(page.getByTestId('mcp-activity-list-content')).toContainText('post_id=8');

    // Available tools sub-accordion expands with the tool list.
    await page.getByTestId('mcp-tools-toggle-content').click();
    await expect(page.getByText('create_blog_post')).toBeVisible();
  });

  test.describe('Segmented connector descriptions', () => {
    test.describe('desktop viewport', () => {
      test.use(viewportUse('desktop'));
      test('describes each segmented connector inside its expanded card', {
        tag: [...ADMIN_MCPS, '@role:admin', '@outcome:success', '@responsive:mcp', '@viewport:desktop'],
      }, async ({ page }) => {
        await assertSegmentedConnectorDescriptions(page);
        await expect(page.getByTestId('mcp-scope-programs').filter({ hasText: 'clientes, propuestas y diagnósticos en Comercial' })).toBeVisible();
      });
    });

    test.describe('compact viewport', () => {
      test.use(viewportUse('compact'));
      test('keeps each segmented connector description visible at phone width', {
        tag: [...ADMIN_MCPS, '@role:admin', '@outcome:success', '@responsive:mcp', '@viewport:compact'],
      }, async ({ page }) => {
        await assertSegmentedConnectorDescriptions(page);
        await expect(page.getByTestId('mcp-scope-programs').filter({ hasText: 'clientes, propuestas y diagnósticos en Comercial' })).toBeVisible();
      });
    });
  });

  test('groups the retiring connector with its replacement and last legacy use', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Bug this catches: a compatibility connector can be shown as canonical,
    // hiding both its migration target and the evidence needed to retire it.
    await mockApi(page, buildHandler());
    // quality: allow-deep-link (authenticated panel landing; MCPs is reached through the sidebar below)
    await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
    await page
      .getByRole('navigation', { name: 'Navegación del panel' })
      .getByRole('link', { name: 'MCPs', exact: true })
      .click();

    await expect(page.getByTestId('mcps-canonical')).toContainText('Contenido');
    await expect(page.getByTestId('mcps-retiring')).toContainText('Gestor de Blogs');
    await page.getByTestId('mcp-card-header-blog').click();
    await expect(page.getByTestId('mcp-migration-blog')).toContainText('Migra a content');
    await expect(page.getByTestId('mcp-migration-blog')).toContainText('Último uso antiguo: Dom, 18 oct 2026, 09:30.');
    await expect(page.getByTestId('mcp-create-credential-blog')).toHaveCount(0);
  });

  test('edits and revokes an existing credential on a retiring connector', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Bug this catches: retiring a connector can incorrectly disable cleanup
    // of its existing credentials or expose the old credential after revoke.
    await mockApi(page, buildHandler());
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('mcp-card-blog')).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('mcp-card-header-blog').click();
    await page.getByTestId('mcp-credentials-toggle-blog').click();
    await page.getByTestId('mcp-credential-edit-17').click();
    await page.getByTestId('mcp-credential-scope').selectOption('all');
    await page.getByTestId('mcp-credential-save').click();
    await expect(page.getByTestId('mcp-credential-17')).toContainText('Todas las funciones');

    await page.getByTestId('mcp-credential-revoke-17').click();
    await expect(page.getByTestId('confirm-modal-confirm')).toHaveText('Revocar');
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(page.getByTestId('mcp-credential-17')).toContainText('No disponible');
    await expect(page.getByTestId('mcp-credential-revoke-17')).toHaveCount(0);
  });

  test('generates a token and shows the one-time connector URL modal', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('mcp-card-content')).toBeVisible({ timeout: 25_000 });
    // The generate-token button lives in the expanded body, so open the row first.
    await page.getByTestId('mcp-card-header-content').click();
    await page.getByTestId('mcp-generate-token-content').click();

    await expect(page.getByTestId('mcp-token-modal')).toBeVisible();
    await expect(page.getByTestId('mcp-token-url')).toContainText('/api/mcp/content/');

    await page.getByTestId('mcp-token-close').click();
    await expect(page.getByTestId('mcp-token-modal')).not.toBeVisible();
  });

  test('activates the connector via the toggle', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('mcp-card-content')).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('mcp-toggle-content').click();
    await expect(page.getByTestId('mcp-toggle-content')).toHaveAttribute('aria-checked', 'true');
  });

  test('creates a read-only credential and reveals its URL once', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('mcp-card-content')).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('mcp-card-header-content').click();
    await page.getByTestId('mcp-create-credential-content').click();
    await expect(page.getByTestId('mcp-credential-modal')).toBeVisible();
    await page.getByTestId('mcp-credential-label').fill('Lectura externa');
    await page.getByTestId('mcp-credential-save').click();

    await expect(page.getByTestId('mcp-token-modal')).toBeVisible();
    await expect(page.getByTestId('mcp-token-url')).toContainText('e2e-scoped-token');
  });

  test('edits the scope of an existing credential', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('mcp-card-content')).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('mcp-card-header-content').click();
    await page.getByTestId('mcp-credentials-toggle-content').click();
    await page.getByTestId('mcp-credential-edit-7').click();
    await page.getByTestId('mcp-credential-scope').selectOption('all');
    await page.getByTestId('mcp-credential-save').click();

    await expect(page.getByTestId('mcp-credential-modal')).not.toBeVisible();
    await expect(page.getByTestId('mcp-credential-7')).toContainText('Todas las funciones');
  });

  test('rotates one credential and reveals only the replacement URL', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('mcp-card-content')).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('mcp-card-header-content').click();
    await page.getByTestId('mcp-credentials-toggle-content').click();
    await page.getByTestId('mcp-credential-rotate-7').click();

    await expect(page.getByTestId('mcp-token-modal')).toBeVisible();
    await expect(page.getByTestId('mcp-token-url')).toContainText('e2e-replacement-token');
  });

  test('revokes one credential after operator confirmation', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('mcp-card-content')).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('mcp-card-header-content').click();
    await page.getByTestId('mcp-credentials-toggle-content').click();
    await page.getByTestId('mcp-credential-revoke-7').click();
    await expect(page.getByTestId('confirm-modal-confirm')).toHaveText('Revocar');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByTestId('mcp-credential-7')).toContainText('No disponible');
    await expect(page.getByTestId('mcp-credential-revoke-7')).toHaveCount(0);
  });

  test('rejects a custom credential scope with no selected tools', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('mcp-card-content')).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('mcp-card-header-content').click();
    await page.getByTestId('mcp-create-credential-content').click();
    await page.getByTestId('mcp-credential-label').fill('Sin alcance');
    await page.getByTestId('mcp-credential-scope').selectOption('custom');
    await page.getByTestId('mcp-credential-save').click();

    await expect(page.getByTestId('mcp-credential-modal')).toContainText(
      'Selecciona al menos una función',
    );
  });

  test('keeps the credential form open when creation is rejected', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ credentialCreateError: true }));
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('mcp-card-content')).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('mcp-card-header-content').click();
    await page.getByTestId('mcp-create-credential-content').click();
    await page.getByTestId('mcp-credential-label').fill('Auditoría');
    await page.getByTestId('mcp-credential-save').click();

    await expect(page.getByTestId('mcp-credential-modal')).toBeVisible();
    await expect(page.getByTestId('mcp-credential-modal')).toContainText(
      'Ya existe una credencial con esa etiqueta.',
    );
  });

  test('staff non-superuser is redirected away from /panel/mcps', {
    tag: [...ADMIN_MCPS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Bug this catches: a staff user without the superuser role can reach
    // MCP credentials by typing the protected panel address directly.
    await mockApi(page, buildHandler({ isSuperuser: false }));
    await page.goto('/panel/mcps', { waitUntil: 'domcontentloaded' });

    await expect(page).toHaveURL(
      /\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?panel\/?(?:[?#].*)?$/,
      { timeout: 25_000 },
    );
    await page
      .getByRole('navigation', { name: 'Navegación del panel' })
      .getByRole('link', { name: 'Dashboard', exact: true })
      .click();
    await expect(page).toHaveURL(/\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?panel\/?$/);
  });
});
