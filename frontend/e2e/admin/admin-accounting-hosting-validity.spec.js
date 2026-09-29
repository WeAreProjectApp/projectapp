/**
 * Responsive validity contract for accounting hostings.
 *
 * Bug caught: a cycle count could paint over the end of a validity range,
 * clip a wrapped date, lose a null-endpoint placeholder, or stop opening the
 * selected hosting's cycle history.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

const PROFILES = Object.freeze(['compact', 'portrait', 'landscape', 'desktop', 'wide']);

const HOSTING_ROWS = Object.freeze([
  {
    id: 101,
    client: 501,
    client_name: 'Cliente Vigente',
    client_display_name: 'Cliente Vigente',
    display_label: 'Cliente Vigente — Proyecto Vigente',
    project: 701,
    project_name: 'Proyecto Vigente',
    billing_email: 'vigente@example.test',
    client_email: 'vigente@example.test',
    domain_url: 'https://vigente.example.test/',
    monthly_value: '91667.00',
    payment_modality: 'semiannual',
    payment_modality_label: 'Semestral',
    benefit: '',
    valid_from: '2026-01-15',
    valid_to: '2027-12-31',
    cycles_count: 1234,
    payment_per_cycle: '550002.00',
    total_paid: '1234000.00',
    billing_requested_at: null,
    is_active: true,
    notes: '',
    weight_pct: 0,
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 102,
    client: 502,
    client_name: 'Cliente Sin Inicio',
    client_display_name: 'Cliente Sin Inicio',
    display_label: 'Cliente Sin Inicio — Proyecto Final',
    project: 702,
    project_name: 'Proyecto Final',
    billing_email: 'sin-inicio@example.test',
    client_email: 'sin-inicio@example.test',
    domain_url: 'https://sin-inicio.example.test/',
    monthly_value: '19000.00',
    payment_modality: 'nine_month',
    payment_modality_label: 'Cada 9 meses',
    benefit: '',
    valid_from: null,
    valid_to: '2027-12-31',
    cycles_count: 2,
    payment_per_cycle: '171000.00',
    total_paid: '342000.00',
    billing_requested_at: null,
    is_active: true,
    notes: '',
    weight_pct: 0,
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 103,
    client: 503,
    client_name: 'Cliente Sin Final',
    client_display_name: 'Cliente Sin Final',
    display_label: 'Cliente Sin Final — Proyecto Inicio',
    project: 703,
    project_name: 'Proyecto Inicio',
    billing_email: 'sin-final@example.test',
    client_email: 'sin-final@example.test',
    domain_url: 'https://sin-final.example.test/',
    monthly_value: '19000.00',
    payment_modality: 'quarterly',
    payment_modality_label: 'Trimestral',
    benefit: '',
    valid_from: '2026-01-15',
    valid_to: null,
    cycles_count: 3,
    payment_per_cycle: '57000.00',
    total_paid: '171000.00',
    billing_requested_at: null,
    is_active: true,
    notes: '',
    weight_pct: 0,
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 104,
    client: 504,
    client_name: 'Cliente Sin Vigencia',
    client_display_name: 'Cliente Sin Vigencia',
    display_label: 'Cliente Sin Vigencia — Proyecto Sin Fechas',
    project: 704,
    project_name: 'Proyecto Sin Fechas',
    billing_email: 'sin-vigencia@example.test',
    client_email: 'sin-vigencia@example.test',
    domain_url: 'https://sin-vigencia.example.test/',
    monthly_value: '19000.00',
    payment_modality: 'quarterly',
    payment_modality_label: 'Trimestral',
    benefit: '',
    valid_from: null,
    valid_to: null,
    cycles_count: 4,
    payment_per_cycle: '57000.00',
    total_paid: '228000.00',
    billing_requested_at: null,
    is_active: true,
    notes: '',
    weight_pct: 0,
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
]);

async function mockHostingValidityApi(page) {
  await setAuthLocalStorage(page, {
    token: 'hosting-validity-token',
    userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
  });

  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { username: 'admin', is_staff: true, is_superuser: true } }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    if (apiPath === 'accounting/dashboard/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ year: 2026, partners: {}, monthly: [], expected_current_month: {}, card_debt: {}, ads: {}, hostings: {} }),
      };
    }
    if (apiPath === 'accounting/hostings/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: HOSTING_ROWS,
          meta: {
            active_count: 4,
            monthly_income: '148667.00',
            expiring_soon_count: 0,
            total_paid: '1975000.00',
            without_client_count: 0,
            without_project_count: 0,
          },
        }),
      };
    }
    if (apiPath === 'accounting/hostings/101/cycles/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [] }) };
    }
    return null;
  });
}

function visibleTestId(page, testId) {
  return page.locator(`[data-testid="${testId}"]:visible`);
}

const subnavActionByProfile = Object.freeze({
  compact: (page) => visibleTestId(page, 'accounting-subnav-select').selectOption('hostings'),
  portrait: (page) => visibleTestId(page, 'accounting-subnav-select').selectOption('hostings'),
  landscape: (page) => visibleTestId(page, 'accounting-subnav-hostings').click(),
  desktop: (page) => visibleTestId(page, 'accounting-subnav-hostings').click(),
  wide: (page) => visibleTestId(page, 'accounting-subnav-hostings').click(),
});

async function expectValidityGeometry(page) {
  const geometry = await page.evaluate(() => {
    const visible = (testId) => {
      const matches = [...document.querySelectorAll(`[data-testid="${testId}"]`)]
        .filter((element) => {
          const style = getComputedStyle(element);
          return style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0;
        });
      if (matches.length !== 1) throw new Error(`${testId} tiene ${matches.length} proyecciones visibles`);
      return matches[0];
    };
    const rect = (value) => ({ left: value.left, top: value.top, right: value.right, bottom: value.bottom });
    const textFragments = (element) => {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      const fragments = [];
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!node.textContent.trim()) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        fragments.push(...[...range.getClientRects()].map(rect));
      }
      return fragments;
    };
    const contains = (box, fragment) => (
      fragment.left >= box.left - 1
      && fragment.right <= box.right + 1
      && fragment.top >= box.top - 1
      && fragment.bottom <= box.bottom + 1
    );
    const intersects = (first, second) => (
      first.left < second.right
      && first.right > second.left
      && first.top < second.bottom
      && first.bottom > second.top
    );

    const validity = visible('hosting-validity-101');
    const cycles = visible('hosting-open-cycles-101');
    const validityBox = rect(validity.getBoundingClientRect());
    const cyclesBox = rect(cycles.getBoundingClientRect());
    const validityFragments = textFragments(validity);
    const cycleFragments = textFragments(cycles);
    const root = document.documentElement;

    return {
      validityFragments: validityFragments.length,
      cycleFragments: cycleFragments.length,
      validityContained: validityFragments.every((fragment) => contains(validityBox, fragment)),
      cyclesContained: cycleFragments.every((fragment) => contains(cyclesBox, fragment)),
      intersects: validityFragments.some((validityFragment) => cycleFragments.some((cycleFragment) => intersects(validityFragment, cycleFragment))),
      noPageOverflow: root.scrollWidth <= root.clientWidth + 1,
      validityBox,
      cyclesBox,
      fragments: { validity: validityFragments, cycles: cycleFragments },
      widths: { scroll: root.scrollWidth, client: root.clientWidth },
    };
  });

  expect(geometry.validityFragments, `No se midieron fragmentos de texto de vigencia: ${JSON.stringify(geometry)}`).toBeGreaterThan(0);
  expect(geometry.cycleFragments, `No se midieron fragmentos de texto de ciclos: ${JSON.stringify(geometry)}`).toBeGreaterThan(0);
  expect(geometry.validityContained, `La vigencia salió de su contenedor: ${JSON.stringify(geometry)}`).toBe(true);
  expect(geometry.cyclesContained, `El conteo salió de su contenedor: ${JSON.stringify(geometry)}`).toBe(true);
  expect(geometry.intersects, `Vigencia y ciclos se superponen: ${JSON.stringify(geometry)}`).toBe(false);
  expect(geometry.noPageOverflow, `La página desborda horizontalmente: ${JSON.stringify(geometry)}`).toBe(true);
}

for (const profile of PROFILES) {
  test.describe(`accounting hostings validity · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('keeps hosting validity readable beside cycle counts', {
      tag: [
        '@flow:admin-accounting-hostings',
        '@outcome:display',
        '@responsive:accounting',
        '@responsive-batch:accounting-special-3',
        `@viewport:${profile}`,
      ],
    }, async ({ page }) => {
      // quality: allow-deep-link (the setup opens the accounting hub; this display behavior reaches Hostings through its actual subnavigation)
      // quality: allow-duplicate (per-viewport contract: admin-accounting-hostings validates the same user-visible range at every canonical width)
      await mockHostingValidityApi(page);
      await page.goto('/en-us/panel/accounting', { waitUntil: 'domcontentloaded' });
      await waitForNuxtApp(page);
      await expect(page.getByRole('heading', { name: 'Resumen', level: 1 })).toHaveText('Resumen');

      await subnavActionByProfile[profile](page);

      await expect(page).toHaveURL(/\/en-us\/panel\/accounting\/hostings$/);
      await expect(page.getByRole('heading', { name: 'Hostings', level: 1 })).toHaveText('Hostings');
      await expect(visibleTestId(page, 'accounting-row-101')).toHaveCount(1);

      await expect(visibleTestId(page, 'hosting-valid-from-101')).toHaveText('2026-01-15');
      await expect(visibleTestId(page, 'hosting-valid-to-101')).toHaveText('→ 2027-12-31');
      await expect(visibleTestId(page, 'hosting-open-cycles-101')).toHaveText('1234');
      await expect(visibleTestId(page, 'hosting-valid-from-102')).toHaveText('—');
      await expect(visibleTestId(page, 'hosting-valid-to-102')).toHaveText('→ 2027-12-31');
      await expect(visibleTestId(page, 'hosting-valid-from-103')).toHaveText('2026-01-15');
      await expect(visibleTestId(page, 'hosting-valid-to-103')).toHaveText('→ —');
      await expect(visibleTestId(page, 'hosting-validity-104')).toHaveText('—');
      await expectValidityGeometry(page);

      await visibleTestId(page, 'hosting-open-cycles-101').click();
      await expect(page).toHaveURL(/\/en-us\/panel\/accounting\/hostings\?hosting=101$/);
      await expect(
        page.getByRole('heading', { name: 'Ciclos de pago — Cliente Vigente — Proyecto Vigente', level: 3 }),
      ).toHaveText('Ciclos de pago — Cliente Vigente — Proyecto Vigente');
    });
  });
}
