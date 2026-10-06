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

import { CONTRACT_PARAMS, COMBINED, PRODUCT, SERVICE, buildProposal, json, buildHandler, openDocuments, openDocumentsFromPanel } from '../helpers/contract-modals.js';

test.describe('Admin proposal contract modality', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(60_000);
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8110, role: 'admin', is_staff: true },
    });
  });

  test('an accepted custom contract changes to split only after reviewing and confirming the impact', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Falla si una propuesta cerrada omite la confirmación o muestra fuentes contractuales equivocadas después del cambio.
    const state = {
      proposal: buildProposal({
        status: 'accepted',
        contract_params: {
          ...CONTRACT_PARAMS,
          contract_source: 'custom',
          custom_contract_markdown: '# Contrato personalizado de Littigio',
        },
      }),
    };
    let previewPayload = null;
    let confirmationId = null;
    await mockApi(page, buildHandler(state, {
      onPreview: payload => { previewPayload = payload; },
      onConfirm: value => { confirmationId = value; },
    }));
    await openDocuments(page);
    await expect(page.getByTestId('proposal-contract-row-combined')).toBeVisible();

    await page.getByTestId('proposal-contract-modality-split').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Cambiar modalidad de contrato' })).toHaveText('Cambiar modalidad de contrato');
    await dialog.getByTestId('contract-change-note').fill('El cierre requiere contratos separados.');
    await dialog.getByTestId('contract-change-service_initial_term').fill('12');
    await dialog.getByTestId('contract-change-service_renewal_notice_days').fill('60');
    await dialog.getByTestId('contract-change-service_termination_notice_days').fill('30');
    await dialog.getByTestId('contract-change-preview').click();

    await expect(dialog.getByTestId('contract-change-impact')).toContainText('Contrato único → Producto y servicio');
    await expect(dialog.getByTestId('contract-change-impact')).toContainText('Contrato de producto: Trasladar sin cambiar el contenido · Personalizado');
    await expect(dialog.getByTestId('contract-change-impact')).toContainText('Contrato de servicio: Crear desde plantilla · Plantilla');
    await dialog.getByTestId('contract-change-confirm').click();

    expect(previewPayload).toEqual({
      contract_modality: 'split',
      change_note: 'El cierre requiere contratos separados.',
      contract_params: {
        service_initial_term: 12,
        service_renewal_notice_days: 60,
        service_termination_notice_days: 30,
      },
    });
    expect(confirmationId).toBe('contract-change-1');
    await expect(page.getByTestId('proposal-contract-modality-split')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-row-combined')).toHaveCount(0);
    const product = page.getByTestId('proposal-contract-row-product');
    await expect(product.getByTestId('proposal-contract-source-product')).toHaveText('Personalizado');
    await expect(page.getByTestId('proposal-contract-row-service').getByTestId('proposal-contract-source-service')).toHaveText('Plantilla');
    await expect(page.getByTestId('proposal-contract-row-service')).toContainText('PDF · Generado el');
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

  test('cancelling the reviewed change keeps the accepted proposal on its combined contract', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Falla si cancelar una vista previa ya modifica la modalidad comercial o archiva el contrato único.
    const state = { proposal: buildProposal({ status: 'accepted' }) };
    let cancelledConfirmation = null;
    let confirmRequests = 0;
    await mockApi(page, buildHandler(state, {
      onCancel: value => { cancelledConfirmation = value; },
      onConfirm: () => { confirmRequests += 1; },
    }));
    await openDocuments(page);

    await page.getByTestId('proposal-contract-modality-split').click();
    const dialog = page.getByRole('dialog');
    await dialog.getByTestId('contract-change-note').fill('Se evaluó la separación y se canceló.');
    await dialog.getByTestId('contract-change-service_initial_term').fill('12');
    await dialog.getByTestId('contract-change-service_renewal_notice_days').fill('60');
    await dialog.getByTestId('contract-change-service_termination_notice_days').fill('30');
    await dialog.getByTestId('contract-change-preview').click();
    await dialog.getByTestId('contract-change-cancel').click();

    expect(cancelledConfirmation).toBe('contract-change-1');
    expect(confirmRequests).toBe(0);
    await expect(page.getByTestId('proposal-contract-modality-single')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-row-combined')).toBeVisible();
    await expect(page.getByTestId('proposal-contract-row-product')).toHaveCount(0);
  });

  test('missing service terms keep the reviewed change open and never confirm it', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Falla si la validación de plazo cierra la revisión o envía una confirmación con un contrato de servicio incompleto.
    const state = { proposal: buildProposal({ status: 'accepted' }) };
    let confirmRequests = 0;
    await mockApi(page, buildHandler(state, {
      onConfirm: () => { confirmRequests += 1; },
      previewResponses: [json(422, {
        error: 'Faltan los plazos del contrato de servicio.',
        details: { service_initial_term: 'Indica este dato del contrato de servicio.' },
      })],
    }));
    await openDocuments(page);

    await page.getByTestId('proposal-contract-modality-split').click();
    const dialog = page.getByRole('dialog');
    await dialog.getByTestId('contract-change-note').fill('Separar al completar las condiciones de servicio.');
    await dialog.getByTestId('contract-change-service_renewal_notice_days').fill('60');
    await dialog.getByTestId('contract-change-service_termination_notice_days').fill('30');
    await dialog.getByTestId('contract-change-preview').click();

    await expect(dialog.getByRole('alert')).toHaveText('Faltan los plazos del contrato de servicio.');
    await expect(dialog.getByText('Indica este dato del contrato de servicio.')).toHaveText('Indica este dato del contrato de servicio.');
    await expect(dialog.getByTestId('contract-change-service_renewal_notice_days')).toHaveValue('60');
    expect(confirmRequests).toBe(0);
    await expect(page.getByTestId('proposal-contract-modality-single')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-row-combined')).toBeVisible();
  });

  test('an accepted proposal displays its split documents and active contract sources', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Falla si navegar por el panel deja de mostrar los contratos separados que pertenecen a una propuesta aceptada.
    // quality: allow-deep-link (admin dashboard is authenticated setup; the test clicks Propuestas, the proposal, then Documentos)
    const state = { proposal: buildProposal({
      status: 'accepted',
      contract_modality: 'split',
      contract_params: { ...CONTRACT_PARAMS, product_contract_source: 'custom', service_contract_source: 'default' },
      proposal_documents: [PRODUCT, SERVICE],
    }) };
    await mockApi(page, buildHandler(state));
    await openDocumentsFromPanel(page);

    await expect(page.getByTestId('proposal-contract-modality-split')).toHaveAttribute('aria-selected', 'true', { timeout: 20_000 });
    await expect(page.getByTestId('proposal-contract-modality-single')).toBeEnabled();
    await expect(page.getByTestId('proposal-contract-row-product')).toContainText('Desarrollo e implementación del software');
    await expect(page.getByTestId('proposal-contract-source-product')).toHaveText('Personalizado');
    await expect(page.getByTestId('proposal-contract-source-service')).toHaveText('Plantilla');
    await expect(page.getByTestId('proposal-contract-row-combined')).toHaveCount(0);
  });

  test('proposal history lets an administrator read the preserved custom contract snapshot', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Falla si el historial deja de mostrar el texto personalizado que protegió antes de cambiar la modalidad.
    // quality: allow-deep-link (admin dashboard is authenticated setup; the test clicks Propuestas, the proposal, Seguimiento and Historial)
    const snapshot = {
      snapshot_id: 701,
      created_at: '2026-10-06T12:00:00Z',
      actor: 'Admin E2E',
      source: 'panel',
      change_note: 'Separación aprobada con resguardo del contrato firmado.',
      from_modality: 'single',
      to_modality: 'split',
      restored_from_id: null,
    };
    const state = { proposal: buildProposal({ status: 'accepted' }) };
    await mockApi(page, buildHandler(state, {
      contractSnapshots: [snapshot],
      contractSnapshotDetails: {
        701: {
          ...snapshot,
          payload: {
            documents: [{
              document_id: COMBINED.id,
              title: 'Contrato único firmado',
              source: 'custom',
              markdown: '# Contrato firmado el 30 de septiembre de 2026',
            }],
          },
        },
      },
    }));
    await openDocumentsFromPanel(page);
    await page.getByRole('tab', { name: 'Seguimiento', exact: true }).click();
    await page.getByRole('tab', { name: 'Historial', exact: true }).click();

    const snapshots = page.getByTestId('contract-snapshots');
    await snapshots.getByTestId('contract-snapshots-load').click();
    await expect(snapshots).toContainText('Contrato único → Producto y servicio');
    await expect(snapshots).toContainText('Admin E2E');
    await expect(snapshots).toContainText('Separación aprobada con resguardo del contrato firmado.');
    await snapshots.getByTestId('contract-snapshot-read-701').click();

    const snapshotDialog = page.getByRole('dialog');
    await expect(snapshotDialog.getByRole('heading', { name: 'Instantánea de contratos 701' })).toHaveText('Instantánea de contratos 701');
    await expect(snapshotDialog).toContainText('Contrato único firmado · Personalizado');
    await expect(snapshotDialog).toContainText('Contrato firmado el 30 de septiembre de 2026');
  });

  test('restoring a contract snapshot preserves the custom single contract after reviewed confirmation', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Falla si restaurar omite la revisión, no recupera el contrato personalizado o no guarda la instantánea inversa.
    // quality: allow-deep-link (admin dashboard is authenticated setup; the test clicks Propuestas, the proposal, Seguimiento, Historial and Restaurar)
    const singleParams = {
      ...CONTRACT_PARAMS,
      contract_source: 'custom',
      custom_contract_markdown: '# Contrato firmado el 30 de septiembre de 2026',
    };
    const snapshot = {
      snapshot_id: 701,
      created_at: '2026-10-06T12:00:00Z',
      actor: 'Admin E2E',
      source: 'panel',
      change_note: 'Separación aprobada con resguardo del contrato firmado.',
      from_modality: 'single',
      to_modality: 'split',
      restored_from_id: null,
    };
    const state = { proposal: buildProposal({
      status: 'accepted',
      contract_modality: 'split',
      contract_params: {
        ...CONTRACT_PARAMS,
        product_contract_source: 'custom',
        product_custom_contract_markdown: singleParams.custom_contract_markdown,
        service_contract_source: 'default',
      },
      proposal_documents: [PRODUCT, SERVICE],
    }) };
    await mockApi(page, buildHandler(state, {
      contractSnapshots: [snapshot],
      contractSnapshotDetails: {
        701: {
          ...snapshot,
          payload: {
            contract_params: singleParams,
            documents: [{
              variant: 'combined',
              document_id: COMBINED.id,
              title: 'Contrato único firmado',
              source: 'custom',
              markdown: singleParams.custom_contract_markdown,
            }],
          },
        },
      },
    }));
    await openDocumentsFromPanel(page);
    await page.getByRole('tab', { name: 'Seguimiento', exact: true }).click();
    await page.getByRole('tab', { name: 'Historial', exact: true }).click();

    const snapshots = page.getByTestId('contract-snapshots');
    await snapshots.getByTestId('contract-snapshots-load').click();
    await snapshots.getByTestId('contract-snapshot-restore-701').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Restaurar contratos anteriores' })).toHaveText('Restaurar contratos anteriores');
    await dialog.getByTestId('contract-change-note').fill('Se restaura el contrato firmado antes de separar documentos.');
    await dialog.getByTestId('contract-change-preview').click();
    await expect(dialog.getByTestId('contract-change-impact')).toContainText('Producto y servicio → Contrato único');
    await expect(dialog.getByTestId('contract-change-impact')).toContainText('Contrato único: Restaurar copia guardada · Personalizado');
    await dialog.getByTestId('contract-change-confirm').click();

    await page.getByRole('tab', { name: 'Documentos', exact: true }).click();
    await expect(page.getByTestId('proposal-contract-modality-single')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-source-combined')).toHaveText('Personalizado');
    await expect(page.getByTestId('proposal-contract-row-product')).toHaveCount(0);
    await page.getByRole('tab', { name: 'Seguimiento', exact: true }).click();
    await page.getByRole('tab', { name: 'Historial', exact: true }).click();
    await expect(snapshots).toContainText('Producto y servicio → Contrato único');
    await expect(snapshots).toContainText('Se restaura el contrato firmado antes de separar documentos.');
  });

  test('a sent proposal still displays the single-contract control through panel navigation', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Falla si los estados previos a negociación vuelven a ocultar la modalidad que ahora puede cambiarse con confirmación.
    // quality: allow-deep-link (admin dashboard is authenticated setup; the test clicks Propuestas, the proposal, then Documentos)
    const state = { proposal: buildProposal({ status: 'sent', proposal_documents: [] }) };
    await mockApi(page, buildHandler(state));
    await openDocumentsFromPanel(page);

    await expect(page.getByTestId('proposal-contract-row-combined')).toContainText('PDF · No generado', { timeout: 20_000 });
    await expect(page.getByTestId('proposal-contract-modality')).toHaveCount(1);
    await expect(page.getByTestId('proposal-contract-modality-single')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-modality-split')).toBeEnabled();
  });
});
