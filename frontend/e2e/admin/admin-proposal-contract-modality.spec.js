/**
 * Admin chooses how a negotiated deal closes: one contract, or a product
 * contract plus a hosting, maintenance and support contract.
 *
 * @flow:admin-proposal-contract-modality
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_CONTRACT_MODALITY } from '../helpers/flow-tags.js';

import { PROPOSAL_ID, CONTRACT_PARAMS, COMBINED, PRODUCT, SERVICE, buildProposal, json, buildHandler, openDocuments, openDocumentsFromPanel } from '../helpers/contract-modals.js';

test.describe('Admin proposal contract modality', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(60_000);
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8110, role: 'admin', is_staff: true },
    });
  });

  test('switching to product and service shows both separate contracts', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { proposal: buildProposal() };
    let modalityPayload = null;
    await mockApi(page, buildHandler(state, { onModality: payload => { modalityPayload = payload; } }));
    await openDocuments(page);
    await expect(page.getByTestId('proposal-contract-row-combined')).toBeVisible();

    await page.getByTestId('proposal-contract-modality-split').click();

    await expect(page.getByText('El negocio se cierra con contrato de producto y contrato de servicio.')).toBeVisible({ timeout: 10_000 });
    expect(modalityPayload).toEqual({ contract_modality: 'split' });
    await expect(page.getByTestId('proposal-contract-modality-split')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-row-combined')).toHaveCount(0);
    const product = page.getByTestId('proposal-contract-row-product');
    await expect(product.getByRole('link', { name: /Descargar PDF|Download PDF/ })).toHaveAttribute('href', `/api/proposals/${PROPOSAL_ID}/contract/pdf/?variant=product`);
    await expect(page.getByTestId('proposal-contract-row-service')).toContainText('PDF · No generado');
  });

  test('configured defaults generate numeric service terms', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = {
      proposal: buildProposal({
        contract_modality: 'split',
        proposal_documents: [COMBINED, PRODUCT],
        hosting_percent: 12,
        hosting_discount_nine_month: 40,
        hosting_discount_semiannual: 20,
        hosting_discount_quarterly: 10,
        sections: [{
          id: 9111,
          section_type: 'investment',
          content_json: { hostingPlan: { title: 'Hosting administrado', coverageNote: 'Cobertura 24/7' } },
        }],
      }),
    };
    let updatePayload = null;
    await mockApi(page, buildHandler(state, { onUpdate: payload => { updatePayload = payload; } }));
    await openDocuments(page);

    await page.getByTestId('proposal-generate-contract-service').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByTestId('contract-service-conditions-note')).toHaveText('Al generar el contrato se incorporan automáticamente la infraestructura, cobertura, cortesías, precios, descuentos y renovación configurados en la propuesta, también si usas un texto personalizado.');
    await expect(dialog.getByRole('combobox', { name: 'Duración inicial' })).toHaveText('nueve (9) meses');
    await expect(dialog.getByRole('combobox', { name: 'Preaviso para no renovar (días calendario)' })).toHaveText('sesenta (60)');
    await expect(dialog.getByRole('combobox', { name: 'Preaviso de terminación del cliente (días calendario)' })).toHaveText('sesenta (60)');
    await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();

    await expect(page.getByTestId('proposal-contract-row-service')).toContainText('Generado el', { timeout: 10_000 });
    expect(updatePayload.variant).toBe('service');
    expect(updatePayload.contract_params).toMatchObject({
      service_contract_source: 'default',
      service_initial_term: 9,
      service_renewal_notice_days: 60,
      service_termination_notice_days: 60,
    });
  });

  test('a stale service contract regenerates through the service dialog', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Falla si el aviso de condiciones desactualizadas abre el contrato de producto.
    const staleService = { ...SERVICE, needs_regeneration: true };
    const state = {
      proposal: buildProposal({
        contract_modality: 'split',
        proposal_documents: [PRODUCT, staleService],
      }),
    };
    let updatePayload = null;
    await mockApi(page, buildHandler(state, { onUpdate: payload => { updatePayload = payload; } }));
    await openDocuments(page);

    const serviceRow = page.getByTestId('proposal-contract-row-service');
    await expect(serviceRow.getByTestId('proposal-service-contract-stale')).toHaveText('Las condiciones del servicio cambiaron. Regenera y revisa el contrato antes de enviarlo.');
    await expect(page.getByTestId('proposal-contract-row-product').getByTestId('proposal-service-contract-stale')).toHaveCount(0);

    await serviceRow.getByRole('button', { name: 'Regenerar contrato' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Editar contrato de servicio' })).toBeVisible();
    await dialog.getByRole('button', { name: 'Actualizar contrato', exact: true }).click();

    await expect(dialog).toHaveCount(0);
    expect(updatePayload.variant).toBe('service');
  });

  test('custom service wording survives reloading the proposal', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Falla si guardar cualquiera de los tres textos pierde la redacción al reabrir.
    const state = { proposal: buildProposal({ contract_modality: 'split', proposal_documents: [COMBINED, PRODUCT] }) };
    let updatePayload = null;
    await mockApi(page, buildHandler(state, { onUpdate: payload => { updatePayload = payload; } }));
    await openDocuments(page);

    await page.getByTestId('proposal-generate-contract-service').click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox', { name: 'Duración inicial' }).click();
    await dialog.getByRole('option', { name: 'Personalizar', exact: true }).click();
    await dialog.getByLabel('Duración inicial: valor personalizado').fill('dieciocho meses iniciales');
    await dialog.getByRole('combobox', { name: 'Preaviso para no renovar (días calendario)' }).click();
    await dialog.getByRole('option', { name: 'Personalizar', exact: true }).click();
    await dialog.getByLabel('Preaviso para no renovar (días calendario): valor personalizado').fill('cuarenta y cinco (45)');
    await dialog.getByRole('combobox', { name: 'Preaviso de terminación del cliente (días calendario)' }).click();
    await dialog.getByRole('option', { name: 'Personalizar', exact: true }).click();
    await dialog.getByLabel('Preaviso de terminación del cliente (días calendario): valor personalizado').fill('setenta y cinco (75)');
    await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();

    await expect(page.getByTestId('proposal-contract-row-service')).toContainText('Generado el', { timeout: 10_000 });
    expect(updatePayload.contract_params).toMatchObject({
      service_initial_term: 'dieciocho meses iniciales',
      service_renewal_notice_days: 'cuarenta y cinco (45)',
      service_termination_notice_days: 'setenta y cinco (75)',
    });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.getByTestId('proposal-contract-row-service').getByRole('button', { name: 'Editar parámetros' }).click();
    await expect(dialog.getByLabel('Duración inicial: valor personalizado')).toHaveValue('dieciocho meses iniciales');
    await expect(dialog.getByLabel('Preaviso para no renovar (días calendario): valor personalizado')).toHaveValue('cuarenta y cinco (45)');
    await expect(dialog.getByLabel('Preaviso de terminación del cliente (días calendario): valor personalizado')).toHaveValue('setenta y cinco (75)');
  });

  test('editing a historical service term preserves its literal wording', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Falla si abrir un contrato antiguo reemplaza una condición negociada que el catálogo no reconoce.
    const historicalTerm = 'plazo comercial especial acordado';
    const state = {
      proposal: buildProposal({
        contract_modality: 'split',
        proposal_documents: [COMBINED, PRODUCT, SERVICE],
        contract_params: {
          ...CONTRACT_PARAMS,
          service_contract_source: 'default',
          service_initial_term: historicalTerm,
          service_renewal_notice_days: 'sesenta (60)',
          service_termination_notice_days: 'sesenta (60)',
        },
      }),
    };
    let updatePayload = null;
    await mockApi(page, buildHandler(state, { onUpdate: payload => { updatePayload = payload; } }));
    await openDocuments(page);

    await page.getByTestId('proposal-contract-row-service').getByRole('button', { name: 'Editar parámetros' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('combobox', { name: 'Duración inicial' })).toHaveText('Personalizar');
    await expect(dialog.getByLabel('Duración inicial: valor personalizado')).toHaveValue(historicalTerm);
    await dialog.getByRole('button', { name: 'Actualizar contrato', exact: true }).click();
    await expect(dialog).toHaveCount(0);

    await expect(page.getByTestId('proposal-contract-row-service')).toContainText('Generado el', { timeout: 10_000 });
    expect(updatePayload.contract_params.service_initial_term).toBe(historicalTerm);
  });

  test('a refused service save keeps the draft available for correction', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Falla si un error de validación cierra el modal o borra lo escrito.
    const state = { proposal: buildProposal({ contract_modality: 'split', proposal_documents: [COMBINED, PRODUCT] }) };
    await mockApi(page, buildHandler(state, {
      updateResponses: [json(400, { service_initial_term: ['Revisa la duración acordada.'] })],
    }));
    await openDocuments(page);
    await page.getByTestId('proposal-generate-contract-service').click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox', { name: 'Duración inicial' }).click();
    await dialog.getByRole('option', { name: 'Personalizar', exact: true }).click();
    const input = dialog.getByLabel('Duración inicial: valor personalizado');
    await input.fill('un año inicial');
    await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();

    await expect(input).toHaveAttribute('aria-invalid', 'true');
    await expect(input).toHaveValue('un año inicial');
    await expect(dialog.getByRole('alert').last()).toHaveText('Revisa la duración acordada.');
    await input.fill('doce (12) meses iniciales');
    await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();

    await expect(dialog).toHaveCount(0);
    await page.getByTestId('proposal-contract-row-service').getByRole('button', { name: 'Editar parámetros' }).click();
    await expect(dialog.getByLabel('Duración inicial: valor personalizado')).toHaveValue('doce (12) meses iniciales');
  });

  test('a server failure retains the service wording for retry', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Falla si el servidor no responde y el operador pierde la redacción.
    const state = { proposal: buildProposal({ contract_modality: 'split', proposal_documents: [COMBINED, PRODUCT] }) };
    await mockApi(page, buildHandler(state, { updateResponses: [json(503, { detail: 'Servicio temporalmente no disponible.' })] }));
    await openDocuments(page);
    await page.getByTestId('proposal-generate-contract-service').click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox', { name: 'Duración inicial' }).click();
    await dialog.getByRole('option', { name: 'Personalizar', exact: true }).click();
    await dialog.getByLabel('Duración inicial: valor personalizado').fill('plazo anual renovable');
    await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();

    await expect(dialog.getByRole('alert')).toHaveText('Servicio temporalmente no disponible.');
    await expect(dialog.getByLabel('Duración inicial: valor personalizado')).toHaveValue('plazo anual renovable');
    await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByTestId('proposal-contract-row-service')).toContainText('Generado el');
  });

  test('pending generation blocks repeated submissions', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Falla si el operador puede reenviar o cerrar un contrato durante el guardado.
    const state = { proposal: buildProposal({ contract_modality: 'split', proposal_documents: [COMBINED, PRODUCT] }) };
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    let requests = 0;
    await mockApi(page, buildHandler(state, { onUpdate: () => { requests += 1; }, beforeUpdate: () => pending }));
    await openDocuments(page);
    await page.getByTestId('proposal-generate-contract-service').click();
    const dialog = page.getByRole('dialog');
    try {
      await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();
      await expect(dialog.getByRole('button', { name: 'Generando...' })).toBeDisabled();
      await expect(dialog.getByRole('button', { name: 'Cancelar' })).toBeDisabled();
      await page.keyboard.press('Enter');
      await page.keyboard.press('Escape');
      await expect(dialog).toBeVisible();
    } finally {
      release();
    }
    await expect(dialog).toHaveCount(0);
    expect(requests).toBe(1);
  });

  test('mobile keyboard selection opens an editable custom duration', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Falla si el campo o los botones quedan inaccesibles dentro del modal móvil.
    await page.setViewportSize({ width: 390, height: 844 });
    const state = { proposal: buildProposal({ contract_modality: 'split', proposal_documents: [COMBINED, PRODUCT] }) };
    await mockApi(page, buildHandler(state));
    await openDocuments(page);
    await page.getByTestId('proposal-generate-contract-service').click();
    const dialog = page.getByRole('dialog');
    const dropdown = dialog.getByRole('combobox', { name: 'Duración inicial' });
    await dropdown.focus();
    await dropdown.press('End');
    await dropdown.press('Enter');
    const input = dialog.getByLabel('Duración inicial: valor personalizado');
    await expect(input).toBeFocused();
    await input.fill('un año de servicio');
    await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();

    await expect(dialog).toHaveCount(0);
    await page.getByTestId('proposal-contract-row-service').getByRole('button', { name: 'Editar parámetros' }).click();
    await expect(dialog.getByLabel('Duración inicial: valor personalizado')).toHaveValue('un año de servicio');
  });

  test('a settings load failure blocks service generation until retry succeeds', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Falla si el contrato se puede generar sin una configuración de términos validada.
    const state = { proposal: buildProposal({ contract_modality: 'split', proposal_documents: [COMBINED, PRODUCT] }) };
    await mockApi(page, buildHandler(state, { companySettingsStatuses: [503] }));
    await openDocuments(page);

    await page.getByTestId('proposal-generate-contract-service').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('alert')).toHaveText('No se pudo cargar la configuración del servicio. Reintenta para continuar.');
    await expect(dialog.getByRole('button', { name: 'Generar contrato', exact: true })).toBeDisabled();

    await dialog.getByRole('button', { name: 'Reintentar', exact: true }).click();

    await expect(dialog.getByRole('combobox', { name: 'Duración inicial' })).toHaveText('nueve (9) meses');
    await expect(dialog.getByRole('combobox', { name: 'Preaviso para no renovar (días calendario)' })).toHaveText('sesenta (60)');
    await expect(dialog.getByRole('button', { name: 'Generar contrato', exact: true })).toBeEnabled();
  });

  test('a refused separation keeps the single contract and explains why', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const state = { proposal: buildProposal() };
    await mockApi(page, buildHandler(state, { modalityStatus: 409 }));
    await openDocuments(page);

    await page.getByTestId('proposal-contract-modality-split').click();

    await expect(page.getByText('El contrato por defecto no se puede separar en producto y servicio.', { exact: false })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('proposal-contract-modality-single')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-row-combined')).toBeVisible();
  });

  test('an accepted proposal shows its modality without letting it change', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (localized panel entry is followed by visible Propuestas, proposal, and Documentos navigation)
    const state = { proposal: buildProposal({ status: 'accepted', contract_modality: 'split', proposal_documents: [COMBINED, PRODUCT, SERVICE] }) };
    await mockApi(page, buildHandler(state));
    await openDocumentsFromPanel(page);

    await expect(page.getByTestId('proposal-contract-modality-split')).toHaveAttribute('aria-selected', 'true', { timeout: 20_000 });
    await expect(page.getByTestId('proposal-contract-modality-single')).toBeDisabled();
    await expect(page.getByTestId('proposal-contract-row-product')).toContainText('Desarrollo e implementación del software');
    await expect(page.getByTestId('proposal-contract-row-service').getByRole('link', { name: /Descargar PDF|Download PDF/ }))
      .toHaveAttribute('href', `/api/proposals/${PROPOSAL_ID}/contract/pdf/?variant=service`);
    await expect(page.getByTestId('proposal-contract-row-combined')).toHaveCount(0);
  });

  test('the switch stays hidden before the negotiation', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (localized panel entry is followed by visible Propuestas, proposal, and Documentos navigation)
    const state = { proposal: buildProposal({ status: 'sent', proposal_documents: [] }) };
    await mockApi(page, buildHandler(state));
    await openDocumentsFromPanel(page);

    await expect(page.getByTestId('proposal-contract-row-combined')).toContainText('PDF · No generado', { timeout: 20_000 });
    await expect(page.getByTestId('proposal-contract-modality')).toHaveCount(0);
    await expect(page.getByTestId('proposal-generate-contract-combined')).toHaveCount(0);
  });
});
