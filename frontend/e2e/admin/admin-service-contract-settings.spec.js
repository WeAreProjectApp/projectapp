/**
 * Admin configures the global service-contract catalogs used by future modals.
 *
 * @flow:admin-service-contract-settings
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_SERVICE_CONTRACT_SETTINGS } from '../helpers/flow-tags.js';
import { viewportUse } from '../helpers/viewports.js';

const PROPOSAL_ID = 924;
const SETTINGS = {
  duration_options: [3, 6, 9, 12],
  notice_options: [30, 60, 90],
  default_duration: 9,
  default_renewal_notice: 60,
  default_termination_notice: 60,
};
const CONTRACT_PARAMS = {
  contract_source: 'default',
  contractor_full_name: 'Project App S.A.S.',
  contractor_nit: '900.123.456-7',
  contractor_email: 'contratos@example.com',
  bank_name: 'Banco de Pruebas',
  bank_account_type: 'Ahorros',
  bank_account_number: '000-000000-00',
  contract_city: 'Medellín',
  client_full_name: 'Cliente Configuración',
  client_cedula: '1.020.304.050',
  client_email: 'cliente@example.com',
  contract_date: '2026-09-27',
};

function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

function contractDoc(id, documentType, title) {
  return {
    id,
    document_type: documentType,
    document_type_display: title,
    title,
    file: `/media/proposal_documents/${documentType}.pdf`,
    is_generated: true,
    created_at: '2026-09-27T10:00:00Z',
    updated_at: '2026-09-27T10:00:00Z',
  };
}

function buildProposal() {
  return {
    id: PROPOSAL_ID,
    uuid: 'ed924111-1111-1111-1111-111111111111',
    title: 'Configuración de términos E2E',
    client_name: 'Cliente Configuración',
    client_email: 'cliente@example.com',
    language: 'es',
    status: 'negotiating',
    total_investment: '12000000',
    currency: 'COP',
    contract_modality: 'split',
    contract_params: CONTRACT_PARAMS,
    proposal_documents: [
      contractDoc(521, 'contract', 'Contrato de desarrollo de software'),
      contractDoc(522, 'contract_product', 'Contrato de producto'),
    ],
    sections: [],
    requirement_groups: [],
  };
}

async function setupApi(page, scenario = {}) {
  scenario.settings ??= structuredClone(SETTINGS);
  scenario.proposal ??= buildProposal();
  scenario.patchCount ??= 0;
  scenario.settingsLoads ??= 0;
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return json(200, { user: { username: 'admin', is_staff: true } });
    if (apiPath === 'proposals/dashboard/') return json(200, { total: 1, conversion_rate: 100 });
    if (apiPath === 'proposals/alerts/') return json(200, []);
    if (apiPath === 'accounts/saved-filter-tabs/' && method === 'GET') return json(200, []);
    if (apiPath === 'proposals/' && method === 'GET') return json(200, [scenario.proposal]);
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return json(200, scenario.proposal);
    if (apiPath === 'proposals/company-settings/' && method === 'GET') {
      scenario.settingsLoads += 1;
      if (scenario.settingsUnavailable && scenario.settingsLoads === 1) {
        return json(503, { detail: 'Configuración no disponible.' });
      }
      return json(200, { service_contract_settings: scenario.settings });
    }
    if (apiPath === 'proposals/company-settings/' && method === 'PATCH') {
      scenario.patchCount += 1;
      scenario.patchPayload = route.request().postDataJSON();
      if (scenario.patchError) {
        return json(400, { service_contract_settings: scenario.patchError });
      }
      scenario.settings = scenario.patchPayload.service_contract_settings;
      return json(200, { service_contract_settings: scenario.settings });
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/contract/update/` && method === 'PATCH') {
      scenario.contractPayload = route.request().postDataJSON();
      const serviceDoc = contractDoc(523, 'contract_service', 'Contrato de servicio');
      scenario.proposal = {
        ...scenario.proposal,
        contract_params: { ...scenario.proposal.contract_params, ...scenario.contractPayload.contract_params },
        proposal_documents: [...scenario.proposal.proposal_documents, serviceDoc],
      };
      return json(200, scenario.proposal);
    }
    return null;
  });
}

async function openSettingsFromPanel(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Propuestas', exact: true }).click({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/es-co\/panel\/proposals$/);
  await page.getByTestId('filter-tabs-config').click();
  await expect(page.getByTestId('service-contract-settings')).toBeVisible();
}

async function openServiceModalAfterSettings(page) {
  await page.getByTestId('filter-tabs-all').click();
  await page.getByTestId(`proposal-open-${PROPOSAL_ID}`).click({ timeout: 15_000 });
  await expect(page).toHaveURL(new RegExp(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`));
  await page.getByRole('tab', { name: 'Documentos' }).click();
  await page.getByTestId('proposal-generate-contract-service').click();
  return page.getByRole('dialog');
}

test.describe('Admin service-contract settings', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8124, role: 'admin', is_staff: true },
    });
  });

  test('navigating to Configuraciones displays the configured service catalogs', {
    tag: [...ADMIN_SERVICE_CONTRACT_SETTINGS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (localized panel entry is followed by the visible Propuestas link and Configuraciones control)
    // Falla si Configuraciones deja de llevar al catálogo que usa el contrato de servicio.
    await setupApi(page);
    await openSettingsFromPanel(page);

    await expect(page.getByRole('heading', { name: 'Datos del contrato de servicio' })).toBeVisible();
    await expect(page.getByLabel('Duración (meses): opción 1')).toHaveValue('3');
    await expect(page.getByLabel('Preavisos (días calendario): opción 3')).toHaveValue('90');
  });

  test('saving a new duration default updates the next service modal', {
    tag: [...ADMIN_SERVICE_CONTRACT_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Falla si Guardar confirma cambios locales pero los próximos contratos conservan los defaults viejos.
    const scenario = {};
    await setupApi(page, scenario);
    await openSettingsFromPanel(page);

    await page.getByLabel('Duración (meses): opción 4').fill('18');
    await page.getByLabel('Duración inicial: preselección').selectOption('18');
    await page.getByRole('button', { name: 'Guardar', exact: true }).click();

    await expect(page.getByText('Configuración guardada.', { exact: true })).toBeVisible();
    expect(scenario.patchPayload).toEqual({
      service_contract_settings: {
        duration_options: [3, 6, 9, 18],
        notice_options: [30, 60, 90],
        default_duration: 18,
        default_renewal_notice: 60,
        default_termination_notice: 60,
      },
    });

    const dialog = await openServiceModalAfterSettings(page);
    await expect(dialog.getByLabel('Duración inicial')).toHaveValue('18');
    await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();
    await expect(page.getByTestId('proposal-contract-row-service')).toContainText('Generado el');
    expect(scenario.contractPayload.contract_params.service_initial_term).toBe(18);
  });

  test('duplicate catalog values are explained without saving', {
    tag: [...ADMIN_SERVICE_CONTRACT_SETTINGS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Falla si opciones repetidas llegan a persistirse aunque el administrador pueda corregirlas en pantalla.
    const scenario = {};
    await setupApi(page, scenario);
    await openSettingsFromPanel(page);

    await page.getByLabel('Duración (meses): opción 4').fill('9');
    await page.getByRole('button', { name: 'Guardar', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Las opciones no pueden repetirse.');
    expect(scenario.patchCount).toBe(0);
  });

  test('a default removed from its catalog is explained without saving', {
    tag: [...ADMIN_SERVICE_CONTRACT_SETTINGS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Falla si una preselección que ya no está en su catálogo se envía al backend.
    const scenario = {};
    await setupApi(page, scenario);
    await openSettingsFromPanel(page);

    await page.getByLabel('Duración (meses): opción 3').fill('18');
    await page.getByRole('button', { name: 'Guardar', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Selecciona un valor incluido en las opciones.');
    expect(scenario.patchCount).toBe(0);
  });

  test('a rejected settings save keeps the edited catalog visible', {
    tag: [...ADMIN_SERVICE_CONTRACT_SETTINGS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Falla si una respuesta de validación del servidor descarta las modificaciones aún no guardadas.
    const scenario = { patchError: { duration_options: ['El catálogo supera el límite permitido.'] } };
    await setupApi(page, scenario);
    await openSettingsFromPanel(page);

    await page.getByLabel('Duración (meses): opción 4').fill('18');
    await page.getByLabel('Duración inicial: preselección').selectOption('18');
    await page.getByRole('button', { name: 'Guardar', exact: true }).click();

    await expect(page.getByText('No se pudo guardar la configuración. Revisa los valores e inténtalo de nuevo.', { exact: true })).toBeVisible();
    await expect(page.getByText('El catálogo supera el límite permitido.')).toBeVisible();
    await expect(page.getByLabel('Duración (meses): opción 4')).toHaveValue('18');
    expect(scenario.patchCount).toBe(1);
  });

  test('a failed settings load can be retried without leaving Configuraciones', {
    tag: [...ADMIN_SERVICE_CONTRACT_SETTINGS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Falla si un fallo transitorio obliga a abandonar la vista en vez de recuperar el formulario.
    await setupApi(page, { settingsUnavailable: true });
    await openSettingsFromPanel(page);

    await expect(page.getByRole('alert')).toHaveText('No se pudo cargar la configuración del servicio. Reintenta para continuar.');
    await page.getByRole('button', { name: 'Reintentar', exact: true }).click();

    await expect(page.getByLabel('Duración (meses): opción 1')).toHaveValue('3');
    await expect(page.getByLabel('Preavisos (días calendario): opción 3')).toHaveValue('90');
  });
});

test.describe('Admin service-contract settings on compact screens', () => {
  test.use(viewportUse('compact'));
  test.setTimeout(60_000);

  test('the compact filter selector opens the configured service catalogs', {
    tag: [...ADMIN_SERVICE_CONTRACT_SETTINGS, '@role:admin', '@outcome:display', '@viewport:compact'],
  }, async ({ page }) => {
    // quality: allow-duplicate (per-viewport contract: admin-service-contract-settings @ 412px uses the mobile filter selector)
    // quality: allow-deep-link (localized panel entry opens the real mobile drawer, then Propuestas and its mobile configuration selector)
    // Falla si el catálogo queda inaccesible desde el selector que reemplaza las pestañas en móvil.
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8124, role: 'admin', is_staff: true },
    });
    await setupApi(page);
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Abrir menú', exact: true }).click();
    await page.getByRole('link', { name: 'Propuestas', exact: true }).click();
    await page.getByTestId('filter-tabs-select').selectOption('__config__');

    await expect(page.getByRole('heading', { name: 'Datos del contrato de servicio' })).toBeVisible();
    await expect(page.getByLabel('Duración (meses): opción 1')).toHaveValue('3');
  });
});
