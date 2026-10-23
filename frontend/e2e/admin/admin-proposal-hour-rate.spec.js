/**
 * E2E coverage for proposal requirement-package snapshots.
 * These checks catch a proposal reverting to hourly rates or overwriting an
 * issued snapshot while the live catalog changes.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { ADMIN_PROPOSAL_HOUR_RATE } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;
const catalog = [
  { id: 7, nationality: 'COL', currency: 'COP', name_es: 'Ágil', name_en: 'Agile', note_es: 'Ajustes acotados.', note_en: 'Bounded adjustments.', xs_count: 30, s_count: 0, m_count: 0, validity_months: 12, reference_price: '1500000', discount_percent: 10, savings: '150000', total_price: '1350000', is_active: true, order: 1 },
  { id: 8, nationality: 'COL', currency: 'COP', name_es: 'Pro', name_en: 'Pro', note_es: 'Evolución continua.', note_en: 'Continuous evolution.', xs_count: 30, s_count: 20, m_count: 0, validity_months: 12, reference_price: '4000000', discount_percent: 15, savings: '600000', total_price: '3400000', is_active: true, order: 2 },
];
const stored = catalog.map((item) => ({
  id: item.id, name: item.name_es, note: item.note_es, xsCount: item.xs_count,
  sCount: item.s_count, mCount: item.m_count, validityMonths: item.validity_months,
  referencePrice: Number(item.reference_price), discountPercent: item.discount_percent,
  totalPrice: Number(item.total_price),
}));

function buildProposal(content = {}) {
  return {
    id: PROPOSAL_ID, uuid: '11111111-1111-1111-1111-111111111111', title: 'E2E Requirement Package',
    client_name: 'Requirement Client', client_email: 'requirement@test.com', language: 'es', nationality: 'COL',
    status: 'draft', total_investment: '5000000', currency: 'COP', view_count: 0, sent_at: null, expires_at: null,
    sections: [{ id: 113, section_type: 'commercial_conditions', title: 'Condiciones comerciales', order: 12, is_enabled: true, is_wide_panel: false,
      content_json: { index: '12', title: 'Condiciones comerciales', packagesTitle: 'Paquetes de requerimientos', currency: 'COP', packages: stored, scopeTitle: 'Alcance', scopeParagraphs: ['p1'], ...content } }],
  };
}

async function openTab(page, { proposal = buildProposal({ pricingModel: 'requirements' }), catalogStatus = 200, saveStatus = 200 } = {}) {
  const captured = [];
  await mockApi(page, async ({ route, apiPath }) => {
    if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
    if (apiPath.startsWith('hour-packages/admin/')) return { status: catalogStatus, contentType: 'application/json', body: JSON.stringify(catalog) };
    if (/^proposals\/sections\/\d+\/update\/$/.test(apiPath)) {
      captured.push(route.request().postDataJSON());
      return { status: saveStatus, contentType: 'application/json', body: JSON.stringify({ section: proposal.sections[0] }) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/sections/create/`) {
      captured.push(route.request().postDataJSON());
      return { status: 201, contentType: 'application/json', body: JSON.stringify({ section: { id: 114, section_type: 'commercial_conditions', is_enabled: true, content_json: { pricingModel: 'requirements', currency: 'COP', packages: stored, scopeTitle: 'Alcance' } } }) };
    }
    return null;
  });
  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
  await selectProposalDestination(page, 'proposal', 'hour-rate');
  return { captured };
}

test.describe('Admin proposal requirement packages', () => {
  test.setTimeout(60_000);

  test('automatic catalog renders Ágil composition', { tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // Bug caught: the proposal card falls back to retired hourly-rate data.
    // quality: allow-deep-link (proposal detail entry is owned by admin-proposal-edit; this flow clicks the nested package tab)
    await openTab(page);
    const agile = page.getByTestId('requirement-package-0');
    await expect(agile).toContainText('30 XS · 0 S · 0 M');
    await expect(agile).toContainText('12 meses desde el pago');
    await expect(agile).toContainText('$1.350.000 COP + IVA');
  });

  test('manual package edits persist requirement fields', { tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: manual saves omit composition and retain retired `hours`.
    const { captured } = await openTab(page, { proposal: buildProposal({ pricingModel: 'requirements', hourPackagesMode: 'manual' }) });
    await page.getByTestId('packages-mode').selectOption('manual');
    const agile = page.getByTestId('requirement-package-0');
    await agile.getByLabel('Nombre del paquete 1').fill('Ágil personalizado');
    await agile.getByLabel('Cupos XS del paquete 1').fill('40');
    await agile.getByLabel('Referencia del paquete 1').fill('1800000');
    await page.getByTestId('hour-rate-save').click();
    expect(captured[0].content_json).toMatchObject({ pricingModel: 'requirements', hourPackagesMode: 'manual' });
    expect(captured[0].content_json.packages[0]).toMatchObject({ name: 'Ágil personalizado', xsCount: 40, referencePrice: 1800000 });
    await expect(page.getByText('Paquetes guardados.')).toBeVisible();
  });

  test('legacy draft previews the catalog before adoption', { tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: viewing an older draft silently converts its historical hours.
    const { captured } = await openTab(page, { proposal: buildProposal() });
    await expect(page.getByTestId('packages-legacy-notice')).toContainText('No se convierten automáticamente');
    await page.getByTestId('packages-adopt').click();
    await expect(page.getByTestId('requirement-package-0')).toContainText('30 XS · 0 S · 0 M');
    expect(captured).toHaveLength(0);
    await page.getByTestId('hour-rate-save').click();
    expect(captured[0].content_json.pricingModel).toBe('requirements');
  });

  test('issued snapshot stays frozen until reset', { tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: a catalog refresh replaces the issued offer without consent.
    const frozen = buildProposal({ pricingModel: 'requirements', packagesFrozen: true, packages: [{ ...stored[0], name: 'Ágil emitido', xsCount: 31 }] });
    const { captured } = await openTab(page, { proposal: frozen });
    await expect(page.getByTestId('requirement-package-0')).toContainText('Ágil emitido');
    await page.getByTestId('packages-reset').click();
    await expect(page.getByTestId('requirement-package-0')).toContainText('30 XS · 0 S · 0 M');
    await page.getByTestId('hour-rate-save').click();
    expect(captured[0].content_json.packagesFrozen).toBe(false);
  });

  test('PDF toggle persists package visibility without losing scope', { tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: hiding the PDF block removes the commercial scope or leaves it printed.
    const { captured } = await openTab(page);
    await page.getByLabel('Incluir paquetes de requerimientos en el PDF').click();
    await page.getByTestId('packages-mode').selectOption('manual');
    await page.getByTestId('hour-rate-save').click();
    expect(captured[0].content_json).toMatchObject({ hourPackagesEnabled: false, scopeTitle: 'Alcance' });
    expect(captured[0].content_json.packages).toEqual(stored);
  });

  test('manual package removal keeps one package protected', { tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: manual package removal permits an empty commercial package block.
    await openTab(page, { proposal: buildProposal({ pricingModel: 'requirements', hourPackagesMode: 'manual' }) });
    await page.getByTestId('packages-mode').selectOption('manual');
    await page.getByTestId('packages-add').click();
    await expect(page.getByTestId('requirement-package-2')).toContainText('Paquete nuevo');
    await page.getByTestId('requirement-package-2').getByRole('button', { name: 'Quitar paquete' }).click();
    await page.getByTestId('requirement-package-1').getByRole('button', { name: 'Quitar paquete' }).click();
    await expect(page.getByTestId('requirement-package-1')).toHaveCount(0);
    await expect(page.getByTestId('requirement-package-0').getByRole('button', { name: 'Quitar paquete' })).toBeDisabled();
  });

  test('missing commercial section creates requirement packages', { tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: creating the missing section does not seed requirement packages.
    const proposal = buildProposal();
    proposal.sections = [];
    const { captured } = await openTab(page, { proposal });
    await expect(page.getByTestId('hour-rate-no-section')).toContainText('Crea las condiciones comerciales');
    await page.getByTestId('hour-rate-create-section').click();
    await expect(page.getByTestId('requirement-package-0')).toContainText('30 XS · 0 S · 0 M');
    expect(captured[0]).toMatchObject({ section_type: 'commercial_conditions' });
  });

  test('catalog failure disables automatic save', { tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
    // Bug caught: a failed catalog request reports an automatic package as saved.
    await openTab(page, { catalogStatus: 400 });
    await expect(page.getByRole('alert')).toContainText('No se pudo cargar el catálogo');
    await expect(page.getByTestId('hour-rate-save')).toBeDisabled();
  });

  test('section save failure reports the rejected package', { tag: [...ADMIN_PROPOSAL_HOUR_RATE, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
    // Bug caught: a rejected section update is presented as a persisted change.
    await openTab(page, { proposal: buildProposal({ pricingModel: 'requirements', hourPackagesMode: 'manual' }), saveStatus: 500 });
    await page.getByTestId('packages-mode').selectOption('manual');
    await page.getByTestId('requirement-package-0').getByLabel('Cupos XS del paquete 1').fill('31');
    await page.getByTestId('hour-rate-save').click();
    await expect(page.getByText('No se pudieron guardar los paquetes. Revisa cupos, vigencia, referencia y descuento.')).toBeVisible();
  });
});
