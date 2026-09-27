/**
 * E2E coverage for the formalization package prepared from a proposal.
 *
 * Catches the regression where the Documents tab sends public-sales PDFs,
 * ignores the operator's selected manifest, or lets a failed delivery send
 * the same contract package a second time.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_FORMALIZATION_DELIVERY } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 451;
const PREPARATION_ID = '11111111-2222-3333-4444-555555555555';

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const proposal = {
  id: PROPOSAL_ID,
  uuid: '6bcf511f-66e6-4705-9810-893d1dd09c20',
  title: 'Portal de formalización',
  client_name: 'Cliente Formalización',
  client_email: 'cliente.formalizacion@example.com',
  status: 'accepted',
  language: 'es',
  total_investment: '12000000',
  currency: 'COP',
  is_active: true,
  created_at: '2026-09-19T10:00:00Z',
  sections: [],
  requirement_groups: [],
  change_logs: [],
  proposal_documents: [
    {
      id: 700,
      title: 'Contrato final firmado',
      document_type: 'contract',
      created_at: '2026-09-18T10:00:00Z',
      file: '/media/contracts/final.pdf',
      is_generated: true,
    },
    {
      id: 801,
      title: 'Anexo de seguridad',
      document_type: 'legal_annex',
      document_type_display: 'Anexo legal',
      file: '/media/annexes/security.pdf',
      is_generated: false,
    },
  ],
};

const baseOptions = {
  documents: [
    { key: 'contract', label: 'Contrato de desarrollo', description: 'Contrato final guardado.', available: true, error: '' },
    { key: 'commercial', label: 'Propuesta comercial formal', description: 'Alcance y condiciones curados.', available: true, error: '' },
    { key: 'technical', label: 'Detalle técnico formal', description: 'Requerimientos técnicos curados.', available: true, error: '' },
  ],
  defaults: {
    subject: 'Documentación para formalizar Portal de formalización',
    greeting: 'Hola Cliente Formalización,',
    body: 'Adjuntamos la documentación para formalizar el proyecto.',
    footer: 'Quedamos atentos a la firma.',
  },
};

function preparedPackage(status = 'prepared', error = '') {
  return {
    id: PREPARATION_ID,
    status,
    error,
    recipient_emails: ['cliente.formalizacion@example.com'],
    cc_emails: [],
    subject: 'Documentación para formalizar Portal de formalización',
    html_preview: '<p>Correo formal preparado para firma.</p>',
    files: [
      { key: 'contract', filename: 'Contrato final.pdf', mime_type: 'application/pdf', url: `/api/proposals/${PROPOSAL_ID}/formalization/preparations/${PREPARATION_ID}/files/1/` },
      { key: 'commercial', filename: 'Propuesta comercial formal.pdf', mime_type: 'application/pdf', url: `/api/proposals/${PROPOSAL_ID}/formalization/preparations/${PREPARATION_ID}/files/2/` },
      { key: 'additional:801', filename: 'Anexo de seguridad.pdf', mime_type: 'application/pdf', url: `/api/proposals/${PROPOSAL_ID}/formalization/preparations/${PREPARATION_ID}/files/3/` },
    ],
  };
}

async function seedAdmin(page) {
  await setAuthLocalStorage(page, {
    token: 'e2e-formalization-token',
    userAuth: { id: 4510, role: 'admin', is_staff: true },
  });
}

async function openDocumentsFromProposalList(page, { compact = false } = {}) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  if (compact) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
    await page.getByRole('dialog', { name: 'Menú principal' }).getByRole('link', { name: 'Propuestas', exact: true }).click();
  } else {
    await page.getByRole('link', { name: 'Propuestas', exact: true }).click();
  }
  await expect(page).toHaveURL(/\/panel\/proposals$/);
  await expect(page.getByTestId(`proposal-open-${PROPOSAL_ID}`)).toBeVisible({ timeout: 15_000 });
  await page.getByTestId(`proposal-open-${PROPOSAL_ID}`).click();
  await expect(page).toHaveURL(new RegExp(`/panel/proposals/${PROPOSAL_ID}/edit`));
  if (compact) {
    await page.getByRole('combobox', { name: 'Secciones' }).selectOption('documents');
  } else {
    await page.getByRole('tab', { name: 'Documentos' }).click();
  }
  await expect(page.getByTestId('proposal-formalization-open')).toBeVisible();
}

function proposalPageHandler({ options = baseOptions, prepare, send, detail, requests }) {
  return async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'proposals/dashboard/') return json({ total: 1, conversion_rate: 100 });
    if (apiPath === 'proposals/alerts/') return json([]);
    if (apiPath === 'proposals/' && method === 'GET') return json([proposal]);
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return json(proposal);
    if (apiPath === `proposals/${PROPOSAL_ID}/formalization/` && method === 'GET') return json(options);
    if (apiPath === `proposals/${PROPOSAL_ID}/formalization/prepare/` && method === 'POST') {
      requests.prepare += 1;
      requests.payload = route.request().postDataJSON();
      return prepare();
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/formalization/preparations/${PREPARATION_ID}/send/` && method === 'POST') {
      requests.send += 1;
      return send();
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/formalization/preparations/${PREPARATION_ID}/` && method === 'GET') {
      requests.detail += 1;
      return detail();
    }
    return null;
  };
}

async function assertNoHorizontalOverflow(page) {
  const geometry = await page.evaluate(() => ({
    scrollWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(geometry.scrollWidth, `El modal de formalización desborda ${geometry.scrollWidth - geometry.clientWidth}px`).toBeLessThanOrEqual(geometry.clientWidth);
}

test.describe('Admin proposal formalization delivery', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await seedAdmin(page);
  });

  test('prepares the chosen files, shows the frozen review, and sends it once', {
    tag: ['@outcome:success', '@outcome:display', ...ADMIN_PROPOSAL_FORMALIZATION_DELIVERY, '@role:admin', '@responsive:formalization-review-desktop'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const requests = { prepare: 0, send: 0, detail: 0, payload: null };
    await mockApi(page, proposalPageHandler({
      requests,
      prepare: () => json(preparedPackage()),
      send: () => json(preparedPackage('sent')),
      detail: () => json(preparedPackage()),
    }));

    await openDocumentsFromProposalList(page);

    const commercialDocument = page.getByRole('listitem').filter({ hasText: 'Propuesta comercial formal' });
    await expect(commercialDocument.getByRole('link', { name: 'Descargar PDF' })).toHaveAttribute(
      'href',
      `/api/proposals/${PROPOSAL_ID}/formalization/pdf/commercial/`,
    );
    const technicalDocument = page.getByRole('listitem').filter({ hasText: 'Detalle técnico formal' });
    await expect(technicalDocument.getByRole('link', { name: 'Descargar PDF' })).toHaveAttribute(
      'href',
      `/api/proposals/${PROPOSAL_ID}/formalization/pdf/technical/`,
    );

    await page.getByTestId('proposal-formalization-open').click();
    const modal = page.getByTestId('formalization-modal');
    await expect(modal.getByTestId('formalization-subject')).toHaveValue('Documentación para formalizar Portal de formalización');
    await modal.getByTestId('formalization-select-technical').uncheck();
    await modal.getByLabel('Anexo de seguridad').check();
    await modal.getByTestId('formalization-prepare').click();

    await expect.poll(() => requests.prepare).toBe(1);
    expect(requests.payload.documents).toEqual(['contract', 'commercial']);
    expect(requests.payload.additional_doc_ids).toEqual([801]);
    await expect(modal.getByTestId('formalization-email-preview')).toHaveAttribute('title', 'Correo de formalización');
    await expect(modal.getByRole('listitem')).toHaveCount(3);
    await expect(modal.getByText('Contrato final.pdf')).toBeVisible();
    await assertNoHorizontalOverflow(page);

    await modal.getByTestId('formalization-send').click();
    await expect.poll(() => requests.send).toBe(1);
    await expect(modal.getByRole('status')).toHaveText(/Correo enviado/);
    await expect(modal.getByTestId('formalization-send')).toHaveCount(0);
  });

  test('blocks a selected unavailable document until the operator deselects it', {
    tag: ['@outcome:error', ...ADMIN_PROPOSAL_FORMALIZATION_DELIVERY, '@role:admin'],
  }, async ({ page }) => {
    const requests = { prepare: 0, send: 0, detail: 0, payload: null };
    const options = {
      ...baseOptions,
      documents: baseOptions.documents.map((document) => (
        document.key === 'technical'
          ? { ...document, available: false, error: 'Falta definir los requerimientos técnicos.' }
          : document
      )),
    };
    await mockApi(page, proposalPageHandler({
      options,
      requests,
      prepare: () => json(preparedPackage()),
      send: () => json(preparedPackage('sent')),
      detail: () => json(preparedPackage()),
    }));

    await openDocumentsFromProposalList(page);
    await page.getByTestId('proposal-formalization-open').click();
    const modal = page.getByTestId('formalization-modal');
    const prepareButton = modal.getByTestId('formalization-prepare');
    await expect(modal.getByText('Falta definir los requerimientos técnicos.')).toHaveText('Falta definir los requerimientos técnicos. Puedes corregirlo en la propuesta o desmarcar este adjunto.');
    await expect(prepareButton).toBeDisabled();

    await modal.getByTestId('formalization-select-technical').uncheck();
    await expect(prepareButton).toBeEnabled();
    expect(requests.prepare).toBe(0);
  });

  test('restores the editable draft when the reviewed package becomes stale', {
    tag: ['@outcome:error', ...ADMIN_PROPOSAL_FORMALIZATION_DELIVERY, '@role:admin'],
  }, async ({ page }) => {
    const requests = { prepare: 0, send: 0, detail: 0, payload: null };
    await mockApi(page, proposalPageHandler({
      requests,
      prepare: () => json(preparedPackage()),
      send: () => json({ error: 'La propuesta cambió; prepara una nueva revisión.', code: 'stale_preparation' }, 409),
      detail: () => json(preparedPackage()),
    }));

    await openDocumentsFromProposalList(page);
    await page.getByTestId('proposal-formalization-open').click();
    const modal = page.getByTestId('formalization-modal');
    await modal.getByTestId('formalization-subject').fill('Versión renovada para firma');
    await modal.getByTestId('formalization-prepare').click();
    await expect(modal.getByTestId('formalization-send')).toBeEnabled();

    await modal.getByTestId('formalization-send').click();
    await expect.poll(() => requests.send).toBe(1);
    await expect(modal.getByRole('alert')).toHaveText('La propuesta cambió; prepara una nueva revisión.');
    await expect(modal.getByTestId('formalization-subject')).toHaveValue('Versión renovada para firma');
    await expect(modal.getByTestId('formalization-prepare')).toBeEnabled();
  });

  test('reconciles an uncertain send without offering a duplicate send on mobile', {
    tag: ['@outcome:failure', ...ADMIN_PROPOSAL_FORMALIZATION_DELIVERY, '@role:admin', '@responsive:formalization-review-mobile'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    const requests = { prepare: 0, send: 0, detail: 0, payload: null };
    await mockApi(page, proposalPageHandler({
      requests,
      prepare: () => json(preparedPackage()),
      send: () => json({ error: 'No se pudo confirmar la entrega.' }, 500),
      detail: () => json(preparedPackage('unknown', 'La entrega está pendiente de confirmación.')),
    }));

    await openDocumentsFromProposalList(page, { compact: true });
    await page.getByTestId('proposal-formalization-open').click();
    const modal = page.getByTestId('formalization-modal');
    await modal.getByTestId('formalization-prepare').click();
    await expect(modal.getByTestId('formalization-email-preview')).toHaveAttribute('title', 'Correo de formalización');

    await modal.getByTestId('formalization-send').click();
    await expect.poll(() => requests.send).toBe(1);
    await expect.poll(() => requests.detail).toBe(1);
    await expect(modal.getByRole('status')).toHaveText('La entrega está pendiente de confirmación.');
    await expect(modal.getByTestId('formalization-send')).toHaveCount(0);
    await assertNoHorizontalOverflow(page);
  });
});
