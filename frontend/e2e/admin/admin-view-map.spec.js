/**
 * E2E tests for the admin view-map reference page.
 *
 * Covers: page render, search filtering, reset behavior, copy reference feedback,
 * seeded filter tabs, configured default view mode, the operational Explorer,
 * and the Configuración tab.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_VIEW_MAP, LAYOUT_ICON_INTERACTION_FEEDBACK } from '../helpers/flow-tags.js';

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const seededTabs = [
  { id: 1, view: 'view_map', name: 'Admin', filters: { audiences: ['admin'] }, order: 0 },
  { id: 2, view: 'view_map', name: 'Público', filters: { audiences: ['public'] }, order: 1 },
  { id: 3, view: 'view_map', name: 'Cliente', filters: { audiences: ['client'] }, order: 2 },
  { id: 4, view: 'view_map', name: 'Dashboards', filters: { viewTypes: ['dashboard'] }, order: 3 },
  { id: 5, view: 'view_map', name: 'Configuración', filters: { viewTypes: ['config'] }, order: 4 },
];

function jsonResponse(body) {
  return { status: 200, contentType: 'application/json', body: JSON.stringify(body) };
}

function viewMapSettings(overrides = {}) {
  return jsonResponse({
    default_view_mode: 'list',
    default_filters: {},
    updated_at: '2026-07-16T10:00:00Z',
    ...overrides,
  });
}

test.describe('Admin View Map', () => {
  test.describe.configure({ mode: 'serial' });
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8800, role: 'admin', is_staff: true },
    });
  });

  test('renders the view map with grouped route inventory', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 1 })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Sitio publico')).toBeVisible();
    await expect(page.getByText('Panel administrativo')).toBeVisible();
    await expect(page.getByText('/panel/views', { exact: true })).toBeVisible();
  });

  test('search filters results and clearing search restores the catalog', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 1 })).toBeVisible({ timeout: 30_000 });

    const search = page.getByPlaceholder('Buscar vista por nombre, URL, referencia o archivo...');
    await search.fill('/panel/views');

    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 3 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Inicio', level: 3 })).not.toBeVisible();

    await search.fill('');

    await expect(page.getByRole('heading', { name: 'Inicio', level: 3 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 3 })).toBeVisible();
  });

  test('map mode drills down into a module and back', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 1 })).toBeVisible({ timeout: 30_000 });

    await page.getByTestId('view-mode-map').click();
    await expect(page.getByTestId('view-module-grid')).toBeVisible();

    await page.getByTestId('view-module-card-admin-panel').click();
    await expect(page.getByTestId('view-module-detail')).toBeVisible();
    await expect(page).toHaveURL(/viewMode=map/);
    await expect(page).toHaveURL(/module=admin-panel/);
    await expect(page.getByRole('heading', { name: 'Blog', level: 3 })).toBeVisible();

    await page.getByTestId('view-module-back').click();
    await expect(page.getByTestId('view-module-grid')).toBeVisible();
    await expect(page).not.toHaveURL(/module=/);
  });

  test('direct link opens map mode with a module preselected', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    await page.goto('/panel/views?viewMode=map&module=client-platform', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('view-module-detail')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Plataforma de clientes').first()).toBeVisible();
  });

  test('explorer exposes Platform capabilities from its product space', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page
      .getByRole('navigation', { name: 'Navegación del panel' })
      .getByRole('link', { name: 'Mapa de vistas', exact: true })
      .click();
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 1 }))
      .toBeVisible({ timeout: 30_000 });
    await page.getByTestId('view-mode-explorer').click();

    await expect(page.getByTestId('view-operational-explorer')).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid^="view-explorer-node-"]')).toHaveCount(3);
    await expect(page.getByTestId('view-explorer-node-panel-internal')).toBeVisible();
    await expect(page.getByTestId('view-explorer-node-client-platform')).toBeVisible();
    await expect(page.getByTestId('view-explorer-node-public-experiences')).toBeVisible();

    await page.getByTestId('view-explorer-motion-toggle').click();
    await page.getByTestId('view-explorer-node-client-platform').click();

    await expect(page).toHaveURL(/viewMode=explorer/);
    await expect(page).toHaveURL(/node=client-platform/);
    await expect(page.locator('[data-testid^="view-explorer-node-platform-"]')).toHaveCount(8);
    await expect(page.getByTestId('view-explorer-relation')).toHaveCount(9);
    await expect(page.getByTestId('view-explorer-detail')).toContainText('Valor operativo');
  });

  test('guided Panel tour advances and exits without losing context', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    // quality: allow-deep-link (the behavior under test starts at the Explorer mode selector; panel navigation is covered separately)
    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('view-mode-explorer').click();
    await expect(page.getByTestId('view-operational-explorer')).toBeVisible({ timeout: 30_000 });

    await page.getByTestId('view-explorer-motion-toggle').click();
    await page.getByTestId('view-explorer-node-panel-internal').click();
    await expect(page.locator('[data-testid^="view-explorer-node-panel-"]')).toHaveCount(8);

    await page.getByTestId('view-explorer-node-panel-content').hover();
    await expect(page.getByTestId('view-explorer-detail')).toContainText('Vista previa');
    await expect(page.getByTestId('view-explorer-detail')).toContainText('Contenido');

    await page.getByTestId('view-explorer-detail').hover();
    await page.getByTestId('view-explorer-start-tour').click();
    await expect(page).toHaveURL(/tour=panel-internal/);
    await expect(page).toHaveURL(/node=panel-overview-work/);
    await expect(page.getByTestId('view-explorer-tour-controls')).toContainText('Paso 1 de 8');

    await page.getByTestId('view-explorer-tour-next').click();
    await expect(page).toHaveURL(/node=panel-commercial/);
    await expect(page.getByTestId('view-explorer-tour-controls')).toContainText('Paso 2 de 8');

    await page.getByTestId('view-explorer-tour-stop').click();
    await expect(page).not.toHaveURL(/tour=/);
    await expect(page).toHaveURL(/node=panel-commercial/);
    await expect(page.getByTestId('view-explorer-tour-controls')).toHaveCount(0);
  });

  test('explorer presents public content and commercial experiences', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    // quality: allow-deep-link (the behavior under test starts at the Explorer mode selector; panel navigation is covered separately)
    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('view-mode-explorer').click();
    await expect(page.getByTestId('view-operational-explorer')).toBeVisible({ timeout: 30_000 });

    await page.getByTestId('view-explorer-motion-toggle').click();
    await page.getByTestId('view-explorer-node-public-experiences').click();

    await expect(page.locator('[data-testid^="view-explorer-node-public-"]')).toHaveCount(7);
    await expect(page.getByTestId('view-explorer-center')).toContainText('Experiencias públicas');
    await expect(page.getByTestId('view-explorer-node-public-additional-modules-experience')).toBeVisible();
    await expect(page.getByTestId('view-explorer-node-public-financing-experience')).toBeVisible();
    await expect(page.getByTestId('view-explorer-node-public-content-proof')).toBeVisible();
  });

  test('explorer keeps orbit nodes inside its stage', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    // quality: allow-deep-link (responsive geometry is local to the Explorer canvas; panel navigation is covered separately)
    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('view-mode-explorer').click();
    await expect(page.getByTestId('view-operational-explorer')).toBeVisible({ timeout: 30_000 });

    const orbitNodes = page.locator('[data-testid^="view-explorer-node-"]');
    await expect(orbitNodes).toHaveCount(3);

    const clippedNodeCount = await orbitNodes.evaluateAll((nodes) => {
      const stage = document.querySelector('[data-testid="view-explorer-stage"]').getBoundingClientRect();
      return nodes.filter((node) => {
        const box = node.getBoundingClientRect();
        return box.left < stage.left
          || box.right > stage.right
          || box.top < stage.top
          || box.bottom > stage.bottom;
      }).length;
    });

    expect(clippedNodeCount).toBe(0);
  });

  test('direct explorer link opens a feature detail', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    // quality: allow-deep-link (this test verifies the shareable Explorer node URL contract)
    await page.goto('/panel/views?viewMode=explorer&node=platform-document-portal', {
      waitUntil: 'domcontentloaded',
    });

    const detail = page.getByTestId('view-explorer-detail');
    await expect(detail.getByRole('heading', { name: 'Revisar y aprobar documentos' })).toBeVisible({ timeout: 30_000 });
    await expect(detail).toContainText('aprobación verificable');

    await detail.getByText('Referencia técnica secundaria').click();
    await expect(detail.getByText('/platform/documents', { exact: true })).toBeVisible();
  });

  test('copy reference button shows copied feedback', {
    tag: [...ADMIN_VIEW_MAP, ...LAYOUT_ICON_INTERACTION_FEEDBACK, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 1 })).toBeVisible({ timeout: 30_000 });

    const viewCard = page.locator('article').filter({ hasText: '/panel/views' });
    const copyButton = viewCard.getByRole('button', { name: 'Copiar referencia' });
    await expect(copyButton).not.toHaveAttribute('title', /.+/);

    await copyButton.hover();
    const tooltip = page.getByRole('tooltip');
    await expect(tooltip).toHaveCount(1);
    await expect(tooltip).toHaveText('Copiar');

    const copyControl = viewCard.locator('[data-panel-action="copy"]');
    await Promise.all([
      expect.poll(() => copyControl.evaluate((control) => {
        const animations = control.getAnimations({ subtree: true });
        return {
          activationState: control.dataset.activationState,
          hasRunningAnimation: animations.some(animation => animation.playState === 'running'),
          hasVerticalHop: animations.some(animation => (
            animation.effect?.getKeyframes()
              .some(frame => String(frame.transform).includes('translateY(-3px)'))
          )),
          hasAnimatedOutline: animations.some(animation => (
            animation.effect?.getKeyframes()
              .some(frame => frame.outlineColor || frame.outlineOffset)
          )),
        };
      })).toEqual({
        activationState: 'active',
        hasRunningAnimation: true,
        hasVerticalHop: true,
        hasAnimatedOutline: false,
      }),
      copyButton.click(),
    ]);

    const successButton = viewCard.getByRole('button', { name: 'Copiado: referencia' });
    await expect(successButton).toBeVisible({ timeout: 5000 });
    await expect(successButton).toHaveAttribute('data-action-status', 'success');
    await expect(successButton).toHaveAttribute('data-displayed-action', 'complete');
    await expect(tooltip).toHaveText('Copiado: referencia');
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toBe('[Panel administrativo] Mapa de vistas — /panel/views');
  });

  test('copy reference button reports a blocked clipboard write', {
    tag: [...LAYOUT_ICON_INTERACTION_FEEDBACK, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 1 })).toBeVisible({ timeout: 30_000 });
    await page.evaluate(() => {
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: {
          writeText: () => Promise.reject(new DOMException('Clipboard blocked', 'NotAllowedError')),
        },
      });
    });

    const viewCard = page.locator('article').filter({ hasText: '/panel/views' });
    await viewCard.getByRole('button', { name: 'Copiar referencia' }).click();

    const failedButton = viewCard.getByRole('button', { name: 'No se pudo copiar la referencia' });
    await expect(failedButton).toBeVisible({ timeout: 5000 });
    await expect(failedButton).toHaveAttribute('data-action-status', 'danger');
    await expect(failedButton).toHaveAttribute('data-displayed-action', 'copy');
    await expect(page.getByRole('tooltip')).toHaveText('No se pudo copiar la referencia');
    await expect(page.getByRole('alert')).toContainText('No se pudo copiar la referencia');
  });

  test('icon feedback uses a static contrast change with reduced motion', {
    tag: [...LAYOUT_ICON_INTERACTION_FEEDBACK, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });

    // quality: allow-deep-link (panel navigation is covered above; this test isolates reduced-motion feedback on the icon control)
    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 1 })).toBeVisible({ timeout: 30_000 });

    const viewCard = page.locator('article').filter({ hasText: '/panel/views' });
    const copyButton = viewCard.getByRole('button', { name: 'Copiar referencia' });
    const copyControl = viewCard.locator('[data-panel-action="copy"]');
    await Promise.all([
      expect.poll(() => copyControl.evaluate((control) => {
        const iconContent = control.querySelector('.base-button__icon-content');
        const iconStyle = window.getComputedStyle(iconContent);
        return {
          activationState: control.dataset.activationState,
          animationCount: control.getAnimations({ subtree: true }).length,
          iconOpacity: iconStyle.opacity,
          iconTransform: iconStyle.transform,
        };
      })).toEqual({
        activationState: 'active',
        animationCount: 0,
        iconOpacity: '0.6',
        iconTransform: 'none',
      }),
      copyButton.click(),
    ]);
  });

  test('seeded filter tabs render and selecting Dashboards filters the catalog', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'accounts/saved-filter-tabs/') return jsonResponse(seededTabs);
      if (apiPath === 'view-map/admin/settings/') return viewMapSettings();
      return null;
    });

    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 1 })).toBeVisible({ timeout: 30_000 });

    for (const tab of seededTabs) {
      await expect(page.getByTestId(`filter-tabs-tab-${tab.id}`)).toBeVisible();
    }

    await page.getByTestId('filter-tabs-tab-4').click();

    await expect(page.getByRole('heading', { name: 'Dashboard del panel', level: 3 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 3 })).not.toBeVisible();
  });

  test('configured default view mode opens the page in map mode', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'view-map/admin/settings/') return viewMapSettings({ default_view_mode: 'map' });
      return null;
    });

    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('view-module-grid')).toBeVisible({ timeout: 30_000 });
    await expect(page).toHaveURL(/viewMode=map/);
  });

  test('configured explorer default opens the operational view', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'view-map/admin/settings/') {
        return viewMapSettings({ default_view_mode: 'explorer' });
      }
      return null;
    });

    // quality: allow-no-interaction (the server-configured entry mode is applied during page hydration)
    // quality: allow-deep-link (loading the route is the behavior under test for the configured default)
    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('view-operational-explorer')).toBeVisible({ timeout: 30_000 });
    await expect(page).toHaveURL(/viewMode=explorer/);
  });

  test('?viewMode=list wins over the configured map default', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'view-map/admin/settings/') return viewMapSettings({ default_view_mode: 'map' });
      return null;
    });

    await page.goto('/panel/views?viewMode=list', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('heading', { name: 'Inicio', level: 3 })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('view-module-grid')).not.toBeVisible();
  });

  test('config tab saves the default view mode and shows a toast', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let patchBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'view-map/admin/settings/') return viewMapSettings();
      if (apiPath === 'view-map/admin/settings/update/' && method === 'PATCH') {
        patchBody = route.request().postDataJSON();
        return viewMapSettings({ default_view_mode: 'map' });
      }
      return null;
    });

    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Mapa de vistas', level: 1 })).toBeVisible({ timeout: 30_000 });

    await page.getByTestId('view-map-section-config').click();
    await expect(page.getByText('Vista por defecto')).toBeVisible();
    await expect(page.getByText('Filtros por defecto')).toBeVisible();

    await page.getByTestId('view-map-default-mode').getByTestId('view-mode-map').click();

    await expect(page.getByText('Vista por defecto guardada.')).toBeVisible({ timeout: 5000 });
    expect(patchBody).toEqual({ default_view_mode: 'map' });
  });

  test('settings save failure shows an error toast', {
    tag: [...ADMIN_VIEW_MAP, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'view-map/admin/settings/') return viewMapSettings();
      if (apiPath === 'view-map/admin/settings/update/' && method === 'PATCH') {
        return {
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'temporary failure' }),
        };
      }
      return null;
    });

    await page.goto('/panel/views', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('view-map-section-config').click();
    await page.getByTestId('view-map-default-mode').getByTestId('view-mode-explorer').click();

    await expect(page.getByText('No se pudo guardar la vista por defecto.')).toBeVisible({ timeout: 5000 });
  });
});
