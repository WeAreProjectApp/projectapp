/**
 * E2E tests for the per-proposal hourly rate tab («Tarifa por hora»).
 *
 * Covers: reading the catalog in automatic mode, owning and inline-editing the
 * package list in manual, adding and removing rows, restoring the catalog
 * values, and the toggle that keeps the block out of the PDF.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { ADMIN_PROPOSAL_HOUR_RATE } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;

const CATALOG = [
  {
    id: 7, nationality: 'COL', currency: 'COP', name_es: 'Pro', name_en: 'Pro',
    note_es: '', note_en: '', hours: 60, hourly_rate: '30000',
    discount_percent: 10, is_active: true, order: 1,
  },
  {
    id: 8, nationality: 'COL', currency: 'COP', name_es: 'Ágil', name_en: 'Agile',
    note_es: 'nota', note_en: 'note', hours: 20, hourly_rate: '45000',
    discount_percent: 0, is_active: true, order: 2,
  },
];

const STORED_PACKAGES = [
  { id: 7, name: 'Pro', note: '', hours: 60, discountPercent: 10, hourlyRate: 30000 },
  { id: 8, name: 'Ágil', note: 'nota', hours: 20, discountPercent: 0, hourlyRate: 45000 },
];

function buildProposal(conditionsContent = {}) {
  return {
    id: PROPOSAL_ID,
    uuid: '11111111-1111-1111-1111-111111111111',
    title: 'E2E Hour Rate',
    client_name: 'Rate Client',
    client_email: 'rate@test.com',
    language: 'es',
    nationality: 'COL',
    status: 'draft',
    total_investment: '5000000',
    currency: 'COP',
    view_count: 0,
    sent_at: null,
    expires_at: null,
    sections: [{
      id: 113,
      section_type: 'commercial_conditions',
      title: '📋 Condiciones comerciales',
      order: 12,
      is_enabled: true,
      is_wide_panel: false,
      content_json: {
        index: '12',
        title: 'Condiciones comerciales',
        packagesTitle: 'Paquetes de horas',
        hourlyRate: 30000,
        currency: 'COP',
        packages: STORED_PACKAGES,
        effortBadge: '',
        scopeTitle: 'Alcance',
        scopeParagraphs: ['p1'],
        ...conditionsContent,
      },
    }],
  };
}

const MANUAL = { hourPackagesMode: 'manual', manualCurrency: 'COP' };

async function openTab(page, { proposal, captured = [] } = {}) {
  const data = proposal || buildProposal();
  await mockApi(page, async ({ route, apiPath }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
      };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(data) };
    }
    if (apiPath.startsWith('hour-packages/admin/')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(CATALOG) };
    }
    const sectionMatch = apiPath.match(/^proposals\/sections\/(\d+)\/update\/$/);
    if (sectionMatch) {
      captured.push(route.request().postDataJSON());
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ section: { ...data.sections[0] } }),
      };
    }
    return null;
  });

  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, {
    waitUntil: 'domcontentloaded',
  });
  // Reach the tab the way an admin does, so the tab itself stays covered.
  await selectProposalDestination(page, 'proposal', 'hour-rate');
  await page.getByTestId('hour-rate-preview').waitFor({ state: 'visible' });
  return { captured, data };
}

async function editCell(page, field, idx, value) {
  const cell = page.getByTestId(`hour-package-cell-${field}-${idx}`);
  await cell.getByTestId('inline-cell-display').click();
  const input = cell.locator('input');
  await input.fill(value);
  await input.press('Enter');
}

test.describe('Admin — proposal hourly rate', () => {
  test.setTimeout(60_000);

  test('automatic mode prices the packages from the catalog and is read-only', {
    tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (openTab enters through the proposal edit page
    // and clicks the tab; only /edit itself is a direct goto, and navigating
    // to that page is covered by admin-proposal-edit)
    await openTab(page);

    await expect(page.getByTestId('hour-rate-mode-hint')).toContainText('catálogo');
    // Pro: 30.000 with 10% off → 27.000/h over 60h → 1.620.000
    await expect(page.getByTestId('hour-rate-rate-7')).toContainText('27.000');
    await expect(page.getByTestId('hour-rate-total-7')).toContainText('1.620.000');
    // Ágil charges its own catalog rate, not Pro's.
    await expect(page.getByTestId('hour-rate-rate-8')).toContainText('45.000');
    // Nothing is editable and no row can be dropped.
    await expect(page.getByTestId('hour-packages-add')).toHaveCount(0);
    await expect(page.getByTestId('hour-package-delete-0')).toHaveCount(0);
  });

  test('manual mode edits the package list inline and saves it verbatim', {
    tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const { captured } = await openTab(page, {
      proposal: buildProposal(MANUAL),
    });

    await editCell(page, 'name', 0, 'Pro a medida');
    await editCell(page, 'hours', 0, '80');
    await editCell(page, 'discount', 0, '25');
    await editCell(page, 'rate', 0, '40.000');

    // Live: 40.000 with 25% off → 30.000/h over 80h → 2.400.000
    await expect(page.getByTestId('hour-rate-rate-7')).toContainText('30.000');
    await expect(page.getByTestId('hour-rate-total-7')).toContainText('2.400.000');

    await page.getByTestId('hour-rate-save').click();
    await expect(page.getByTestId('hour-rate-save')).toBeDisabled();

    const cj = captured[0].content_json;
    expect(cj.hourPackagesMode).toBe('manual');
    expect(cj.packages[0]).toMatchObject({
      name: 'Pro a medida', hours: 80, discountPercent: 25, hourlyRate: 40000,
    });
    // Fields this tab does not own survive untouched.
    expect(cj.scopeTitle).toBe('Alcance');
  });

  test('the base rate only reaches the table through «Aplicar a todos»', {
    tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const { captured } = await openTab(page, { proposal: buildProposal(MANUAL) });

    await page.getByTestId('hour-rate-manual-input').fill('90.000');
    // Typing alone must not move anything: every package owns its rate.
    await expect(page.getByTestId('hour-rate-rate-7')).toContainText('27.000');
    await expect(page.getByTestId('hour-rate-rate-8')).toContainText('45.000');

    await page.getByTestId('hour-rate-apply-base-all').click();

    // Now every row charges 90.000, each keeping its own discount on top.
    await expect(page.getByTestId('hour-rate-rate-7')).toContainText('81.000');
    await expect(page.getByTestId('hour-rate-rate-8')).toContainText('90.000');
    // Nothing left to apply.
    await expect(page.getByTestId('hour-rate-apply-base-all')).toBeDisabled();

    await page.getByTestId('hour-rate-save').click();
    await expect(page.getByTestId('hour-rate-save')).toBeDisabled();

    expect(captured[0].content_json.packages.map((p) => p.hourlyRate)).toEqual([90000, 90000]);
  });

  test('packages can be added and removed, never below one', {
    tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openTab(page, { proposal: buildProposal(MANUAL) });

    await page.getByTestId('hour-packages-add').click();
    await expect(page.getByTestId('hour-package-row-2')).toBeVisible();

    await page.getByTestId('hour-package-delete-2').click();
    await page.getByTestId('hour-package-delete-1').click();
    await expect(page.getByTestId('hour-package-row-1')).toHaveCount(0);

    // The PDF section makes no sense empty, so the last row is protected.
    await expect(page.getByTestId('hour-package-delete-0')).toBeDisabled();
  });

  test('restoring brings the whole list back from the catalog', {
    tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openTab(page, { proposal: buildProposal(MANUAL) });

    await editCell(page, 'name', 0, 'Renombrado');
    await page.getByTestId('hour-package-delete-1').click();
    await expect(page.getByTestId('hour-package-row-1')).toHaveCount(0);

    await page.getByTestId('hour-rate-reset-catalog').click();

    await expect(page.getByTestId('hour-package-row-1')).toBeVisible();
    await expect(page.getByTestId('hour-package-cell-name-0')).toContainText('Pro');
    // Each package keeps its own catalog rate rather than being flattened.
    await expect(page.getByTestId('hour-rate-rate-7')).toContainText('27.000');
    await expect(page.getByTestId('hour-rate-rate-8')).toContainText('45.000');
    await expect(page.getByTestId('hour-rate-reset-catalog')).toBeDisabled();
  });

  test('the print toggle keeps the packages out of the PDF', {
    tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const { captured } = await openTab(page);
    await expect(page.getByTestId('hour-rate-print-label')).toContainText('se imprimen');

    await page.getByLabel('Incluir los paquetes por horas en el PDF').click();
    await expect(page.getByTestId('hour-rate-print-label')).toContainText('NO se imprimen');

    await page.getByTestId('hour-rate-save').click();
    await expect(page.getByTestId('hour-rate-save')).toBeDisabled();

    expect(captured[0].content_json.hourPackagesEnabled).toBe(false);
  });

  test('a proposal without the section is offered to create it', {
    tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const data = buildProposal();
    data.sections = [];
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
        };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(data) };
      }
      if (apiPath.startsWith('hour-packages/admin/')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(CATALOG) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, {
      waitUntil: 'domcontentloaded',
    });
    await selectProposalDestination(page, 'proposal', 'hour-rate');

    await expect(page.getByTestId('hour-rate-no-section'))
      .toContainText('todavía no tiene la sección');
    await expect(page.getByTestId('hour-rate-create-section')).toHaveText('Crear la sección');
    await expect(page.getByTestId('hour-rate-preview')).toHaveCount(0);
  });
});
