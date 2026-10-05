/**
 * E2E tests for admin document edit flow.
 *
 * @flow:admin-document-edit
 * Covers: edit form pre-filled with existing document data, save updates document,
 *         client messages and normalized observations (including read-only copy), responsive header,
 *         back link navigation, download PDF action, copy/paste markdown content
 *         toolbar buttons, the Editar/Vista previa switch, template style switch
 *         (Amigable/Profesional) toggling the preview theme, the fixed notes save
 *         bar, the dual-style PDF download dropdown, and moving the document
 *         with the searchable folder picker.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_DOCUMENT_EDIT,
  ADMIN_DOCUMENT_EMAIL_HISTORY,
} from '../helpers/flow-tags.js';
import { viewportUse } from '../helpers/viewports.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const mockDocument = {
  id: 1, title: 'Contrato de Servicios', status: 'draft',
  content_markdown: '# Contrato\n\nEste es el contenido del contrato.',
  client_name: 'ACME Corp', created_at: '2026-03-01T10:00:00Z',
};

const legalHeaderTitle = 'Carta jurídica dirigida a la Superintendencia de Industria y Comercio sobre la respuesta al requerimiento de información del expediente 2026-004817';
const legalHeaderClient = 'Grupo Empresarial de Soluciones Jurídicas y Administrativas del Caribe S.A.S.';
const longHeaderDocument = {
  ...mockDocument,
  title: legalHeaderTitle,
  client: 57,
  client_display_name: legalHeaderClient,
};

const issuedCollectionAccount = {
  ...mockDocument,
  document_type_code: 'collection_account',
  commercial_status: 'issued',
  is_generated_snapshot: true,
  public_number: 'PA-ACME-001',
  issue_date: '2026-03-01',
  due_date: '2026-03-09',
  currency: 'COP',
  total: '1490000.00',
  billing_notes: 'Pagar por transferencia.',
  collection_account_observations: 'Emitida desde el ingreso mensual.',
  folder: 30,
  folder_name: '08 - Agosto',
  client_email_subject: 'Cuenta emitida',
  client_custom_notes: [
    { title: 'Conciliación', content: 'Pago pendiente de confirmar.' },
  ],
  notes: [
    { id: 21, title: 'Conciliación', content: 'Pago pendiente de confirmar.', status: 'open', order: 0 },
  ],
};

const documentFolderTree = [
  { id: 10, name: 'Acme', parent: null, is_archived: false },
  { id: 20, name: 'Portal', parent: 10, is_archived: false },
  { id: 30, name: '08 - Agosto', parent: 20, is_archived: false },
];

const duplicateFolderName = 'Entregables de revisión contractual integral';
const duplicateFolderOne = {
  id: 81, name: duplicateFolderName, parent: 80, is_archived: false,
  project_name: 'Renovación operativa Boreal', client_display_name: 'Cliente Boreal',
};
const duplicateFolderTwo = {
  id: 91, name: duplicateFolderName, parent: 90, is_archived: false,
  project_name: 'Conciliación documental Boreal', client_display_name: 'Cliente Boreal',
};
const duplicateFolderTree = [
  { id: 80, name: 'Renovación anual Cliente Boreal', parent: null, is_archived: false },
  duplicateFolderOne,
  { id: 90, name: 'Conciliación trimestral Cliente Boreal', parent: null, is_archived: false },
  duplicateFolderTwo,
];

const generatedProposalSnapshot = {
  ...mockDocument,
  title: '2026-08-14 · Propuesta comercial · Portal Nube · v02',
  document_type_code: 'commercial_proposal',
  is_generated_snapshot: true,
  source_proposal_id: 77,
  source_version: 2,
  folder: 45,
  folder_name: '08 - Agosto',
  client_email_subject: 'Propuesta enviada',
  active_states: [],
  notes: [
    { id: 31, title: 'Seguimiento', content: 'Confirmar recepción.', status: 'open', order: 0 },
  ],
};

async function mockResponsiveHeaderApi(page) {
  await mockApi(page, async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'documents/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([longHeaderDocument]) };
    }
    if (apiPath === 'documents/1/detail/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(longHeaderDocument) };
    }
    if (
      apiPath === 'document-folders/'
      || apiPath === 'document-tags/'
      || apiPath === 'document-states/'
      || apiPath === 'document-state-groups/'
      || apiPath === 'accounting/projects/'
    ) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    if (apiPath === 'proposals/client-profiles/status-counts/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ all: 0, active: 0, orphans: 0, archived: 0 }) };
    }
    if (apiPath === 'proposals/client-profiles/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    return null;
  });
}

async function readResponsiveHeaderLayout(page) {
  await mockResponsiveHeaderApi(page);
  await page.goto('/en-us/panel/documents/1/edit', { waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/\/en-us\/panel\/documents\/1\/edit$/);

  const title = page.getByTestId('doc-editor-title');
  const metadata = page.getByTestId('doc-editor-metadata');
  const actions = page.getByTestId('doc-header-actions');
  const actionTrigger = page.getByTestId('doc-document-actions-trigger');
  const cancel = page.getByTestId('doc-cancel');
  const save = page.getByTestId('doc-save');

  await expect(title).toBeVisible();
  await expect(title).toHaveText(legalHeaderTitle);
  await expect(title).toHaveAttribute('title', legalHeaderTitle);
  await expect(metadata.getByTitle(legalHeaderClient)).toHaveCount(1);
  await expect(actionTrigger).toContainText('Acciones');

  // This click catches the regression where the action group was visually
  // present but squeezed enough that the document-output choices were unusable.
  await actionTrigger.click();
  await expect(page.getByRole('menuitem', { name: 'Descargar PDF · Amigable', exact: true })).toHaveText('Descargar PDF · Amigable');
  await expect(page.getByRole('menuitem', { name: 'Descargar PDF · Profesional', exact: true })).toHaveText('Descargar PDF · Profesional');

  const layout = await page.evaluate(() => {
    const getBox = (testId) => {
      const element = document.querySelector(`[data-testid="${testId}"]`);
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        x: box.x,
        y: box.y,
        right: box.right,
        bottom: box.bottom,
        width: box.width,
        height: box.height,
        whiteSpace: style.whiteSpace,
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      };
    };
    const titleElement = document.querySelector('[data-testid="doc-editor-title"]');
    const titleStyle = getComputedStyle(titleElement);
    const titleBox = titleElement.getBoundingClientRect();
    return {
      pageScrollWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
      title: {
        ...getBox('doc-editor-title'),
        lineClamp: titleStyle.webkitLineClamp,
        lineHeight: Number.parseFloat(titleStyle.lineHeight),
        lineCount: Math.round(titleBox.height / Number.parseFloat(titleStyle.lineHeight)),
      },
      metadata: getBox('doc-editor-metadata'),
      actions: getBox('doc-header-actions'),
      actionTrigger: getBox('doc-document-actions-trigger'),
      cancel: getBox('doc-cancel'),
      save: getBox('doc-save'),
    };
  });

  expect(layout.pageScrollWidth).toBeLessThanOrEqual(layout.viewportWidth);
  expect(layout.title.lineClamp).toBe('2');
  expect(layout.title.lineCount).toBeLessThanOrEqual(2);
  expect(layout.actionTrigger.scrollWidth).toBeLessThanOrEqual(layout.actionTrigger.clientWidth);
  expect(layout.cancel.whiteSpace).toBe('nowrap');
  expect(layout.save.whiteSpace).toBe('nowrap');
  expect(layout.cancel.scrollWidth).toBeLessThanOrEqual(layout.cancel.clientWidth);
  expect(layout.save.scrollWidth).toBeLessThanOrEqual(layout.save.clientWidth);
  expect(layout.actions.right).toBeLessThanOrEqual(layout.viewportWidth);

  return layout;
}

test.describe('Admin Document Edit', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  test.describe('responsive document header', () => {
    test.describe('compact', { tag: ['@viewport:compact'] }, () => {
      test.use(viewportUse('compact'));

      // R-canvas-01: a long legal title pushed the output and edit controls past a phone viewport.
      test('compact header prevents a legal title from overflowing action controls', {
        tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display', '@responsive:canvas'],
      }, async ({ page }) => {
        // quality: allow-duplicate (per-viewport contract: admin-document-edit @ 412px)
        // quality: allow-deep-link (the editor header is the documented display surface; route navigation is covered separately)
        const layout = await readResponsiveHeaderLayout(page);

        expect(layout.actions.y).toBeGreaterThanOrEqual(layout.metadata.bottom);
      });
    });

    test.describe('portrait', { tag: ['@viewport:portrait'] }, () => {
      test.use(viewportUse('portrait'));

      // R-canvas-02: a tablet portrait layout let the action labels wrap under a long title.
      test('portrait header prevents a legal title from overflowing action controls', {
        tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display', '@responsive:canvas'],
      }, async ({ page }) => {
        // quality: allow-duplicate (per-viewport contract: admin-document-edit @ 835px)
        // quality: allow-deep-link (the editor header is the documented display surface; route navigation is covered separately)
        const layout = await readResponsiveHeaderLayout(page);

        expect(layout.actions.y).toBeGreaterThanOrEqual(layout.metadata.bottom);
      });
    });

    test.describe('landscape', { tag: ['@viewport:landscape'] }, () => {
      test.use(viewportUse('landscape'));

      // R-canvas-03: a wide editor gave the title all available width and squeezed the action group.
      test('landscape header reserves an action track beside a legal title', {
        tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display', '@responsive:canvas'],
      }, async ({ page }) => {
        // quality: allow-duplicate (per-viewport contract: admin-document-edit @ 1195px)
        // quality: allow-deep-link (the editor header is the documented display surface; route navigation is covered separately)
        const layout = await readResponsiveHeaderLayout(page);

        expect(layout.title.right).toBeLessThanOrEqual(layout.actions.x);
        expect(layout.actions.right).toBeGreaterThan(layout.actions.x);
      });
    });

    test.describe('desktop', { tag: ['@viewport:desktop'] }, () => {
      test.use(viewportUse('desktop'));

      // R-canvas-04: desktop action controls lost their own width when a legal title grew.
      test('desktop header reserves an action track beside a legal title', {
        tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display', '@responsive:canvas'],
      }, async ({ page }) => {
        // quality: allow-duplicate (per-viewport contract: admin-document-edit @ 1440px)
        // quality: allow-deep-link (the editor header is the documented display surface; route navigation is covered separately)
        const layout = await readResponsiveHeaderLayout(page);

        expect(layout.title.right).toBeLessThanOrEqual(layout.actions.x);
        expect(layout.actions.right).toBeGreaterThan(layout.actions.x);
      });
    });

    test.describe('wide', { tag: ['@viewport:wide'] }, () => {
      test.use(viewportUse('wide'));

      // R-canvas-05: an ultra-wide editor regressed to an unconstrained title despite available space.
      test('wide header keeps a legal title clamped beside its action track', {
        tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display', '@responsive:canvas'],
      }, async ({ page }) => {
        // quality: allow-duplicate (per-viewport contract: admin-document-edit @ 2560px)
        // quality: allow-deep-link (the editor header is the documented display surface; route navigation is covered separately)
        const layout = await readResponsiveHeaderLayout(page);

        expect(layout.title.right).toBeLessThanOrEqual(layout.actions.x);
        expect(layout.actions.right).toBeGreaterThan(layout.actions.x);
      });

      test('wide editor previews a short document in its own box at document proportions', {
        tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display', '@responsive:canvas'],
      }, async ({ page }) => {
        // quality: allow-duplicate (wide-only geometry contract for preview surfaces)
        // quality: allow-deep-link (the editor preview is the documented display surface)
        await mockResponsiveHeaderApi(page);
        await page.goto('/en-us/panel/documents/1/edit', { waitUntil: 'domcontentloaded' });
        const markdown = page.getByRole('textbox', { name: 'Contenido Markdown' });
        await expect(markdown).toHaveValue(mockDocument.content_markdown);
        const editorBox = await markdown.boundingBox();

        await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();
        const preview = page.getByTestId('doc-markdown-preview-pane');
        await expect(preview.getByRole('heading', { name: 'Contrato', level: 1 })).toHaveText('Contrato');
        await expect(markdown).toBeHidden();

        const inlineLayout = await preview.evaluate((pane) => {
          const paneBox = pane.getBoundingClientRect();
          const contentBox = pane.querySelector('.markdown-preview').getBoundingClientRect();
          return { paneWidth: paneBox.width, paneHeight: paneBox.height, contentWidth: contentBox.width };
        });
        // The preview takes the editor's own box, so switching never moves the
        // page, while the document keeps its reading width inside it.
        expect(inlineLayout.paneWidth).toBeCloseTo(editorBox.width, 0);
        expect(inlineLayout.paneHeight).toBeCloseTo(editorBox.height, 0);
        expect(inlineLayout.contentWidth).toBeLessThanOrEqual(768);

        await page.getByRole('button', { name: 'Vista completa' }).click();
        const modalLayout = await page.getByTestId('markdown-preview-modal-panel')
          .evaluate((panel) => {
            const panelBox = panel.getBoundingClientRect();
            const contentBox = panel.querySelector('.markdown-preview').getBoundingClientRect();
            return { panelWidth: panelBox.width, contentWidth: contentBox.width };
          });
        expect(modalLayout.panelWidth).toBeLessThanOrEqual(896);
        expect(modalLayout.contentWidth).toBeLessThanOrEqual(768);
      });
    });
  });

  test('renders edit form pre-filled with existing document data', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the module entry; this test
    // follows the real list -> editor interaction before asserting hydration)
    const documentWithNote = {
      ...mockDocument,
      client_email_subject: 'Contrato listo para revisión',
      client_email_body: 'Hola Ana,\n\nEl contrato está listo para tu revisión.',
      client_whatsapp_message: 'Hola Ana, te envié el contrato para revisión.',
      client_custom_notes: [
        { title: 'Seguimiento', content: 'Confirmar recepción el viernes.' },
      ],
      notes: [
        { id: 11, title: 'Seguimiento', content: 'Confirmar recepción el viernes.', status: 'open', order: 0 },
      ],
    };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([mockDocument]) };
      }
      if (
        apiPath === 'document-folders/'
        || apiPath === 'document-tags/'
        || apiPath === 'document-states/'
        || apiPath === 'document-state-groups/'
      ) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(documentWithNote) };
      }
      return null;
    });
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText(mockDocument.title, { exact: true }).first())
      .toBeVisible({ timeout: 30000 });
    await page.getByTestId('document-open-1').click();

    await expect(page.getByRole('textbox', { name: /^Título$/i })).toHaveValue('Contrato de Servicios');
    const noteButton = page.getByTestId('doc-client-note-open');
    await expect(noteButton).toHaveAccessibleName('Editar notas');
    await noteButton.click();
    await expect(page.getByTestId('client-note-subject')).toHaveValue('Contrato listo para revisión');
    await expect(page.getByTestId('client-note-email')).toHaveValue('Hola Ana,\n\nEl contrato está listo para tu revisión.');
    await expect(page.getByTestId('client-note-whatsapp')).toHaveValue('Hola Ana, te envié el contrato para revisión.');
    const observation = page.getByTestId('document-observation-11');
    await expect(observation).toContainText('Seguimiento');
    await expect(observation).toContainText('Confirmar recepción el viernes.');
  });

  test('opens the exact email history row that used this document', {
    tag: [...ADMIN_DOCUMENT_EMAIL_HISTORY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the authenticated module entry;
    // from there this test follows the real list → editor → email history path)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([mockDocument]) };
      }
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockDocument) };
      }
      if (apiPath === 'documents/1/email-usage/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({
          count: 1,
          results: [{
            email_log_id: 41,
            recipient: 'cliente@example.com',
            subject: 'Contrato para firma',
            sent_at: '2026-08-28T10:00:00Z',
            attachments: [{ id: 71, filename: 'contrato.pdf', size_bytes: 1024 }],
          }],
        }) };
      }
      if (apiPath === 'documents/1/communications/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ count: 0, results: [] }) };
      }
      if (
        apiPath === 'document-folders/'
        || apiPath === 'document-tags/'
        || apiPath === 'document-states/'
        || apiPath === 'document-state-groups/'
      ) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      if (apiPath === 'emails/defaults/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({
          greeting: 'Hola', footer: 'Saludos', available_signers: [], available_variables: [],
        }) };
      }
      if (apiPath === 'emails/copy-recipients/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({
          results: [], families: [], copy_mode: 'bcc',
        }) };
      }
      if (apiPath.startsWith('emails/history')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({
          results: [{
            id: 41,
            subject: 'Contrato para firma',
            recipient: 'cliente@example.com',
            status: 'sent',
            sent_at: '2026-08-28T10:00:00Z',
            template_label: 'Correo personalizado',
            family_label: 'Documentos y comunicaciones',
            audience_label: 'Al cliente',
            has_body: true,
            metadata: {},
            copies: [],
            snapshot_state: 'captured',
            snapshot_notice: '',
            has_attachments: true,
            attachment_count: 1,
            message_size_bytes: 2048,
            attachment_size_bytes: 1024,
            can_resend: true,
            attachments: [{
              id: 71,
              filename: 'contrato.pdf',
              format_label: 'PDF',
              business_kind_label: 'Contrato',
              size_bytes: 1024,
              exact_available: true,
              source_document: { id: 1, title: 'Contrato de Servicios' },
              download_url: '/api/emails/history/41/attachments/71/',
              preview_url: '/api/emails/history/41/attachments/71/?inline=1',
            }],
            links: { content: [], template: [] },
          }],
          total: 1,
          page: 1,
          has_next: false,
          attachment_type_options: [],
        }) };
      }
      return null;
    });
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('document-open-1').click();
    await expect(page.getByTestId('document-email-usage')).toContainText('Contrato para firma');

    await page.getByTestId('document-email-41').click();

    await expect(page).toHaveURL(/\/panel\/emails\?.*email=41/);
    await expect(page.getByTestId('email-history-attachments-41'))
      .toContainText('contrato.pdf');
  });

  const contractMirrors = [
      {
        ...mockDocument,
        id: 104,
        title: 'Contrato unificado de producto y servicio',
        slug: 'contrato-unificado-producto-servicio',
        contract_variant: 'combined',
        contract_version: 8,
        contract_synced_at: '2026-10-05T15:00:00Z',
        synced_label: 'Lun, 5 oct 2026',
      },
      {
        ...mockDocument,
        id: 206,
        title: 'Contrato de producto — desarrollo e implementación de software',
        slug: 'contrato-producto',
        contract_variant: 'product',
        contract_version: 3,
        contract_synced_at: '2026-10-04T15:00:00Z',
        synced_label: 'Dom, 4 oct 2026',
      },
      {
        ...mockDocument,
        id: 205,
        title: 'Contrato de servicio — hosting, mantenimiento y soporte',
        slug: 'contrato-servicio',
        contract_variant: 'service',
        contract_version: 5,
        contract_synced_at: '2026-10-03T15:00:00Z',
        synced_label: 'Sáb, 3 oct 2026',
      },
    ].map((mirror) => ({
      ...mirror,
      folder: 121,
      folder_id: 121,
      folder_name: 'Contratos',
      is_contract_mirror: true,
      content_markdown: `# ${mirror.title}\n\n## CLÁUSULA PRIMERA — OBJETO DEL CONTRATO\n`,
      active_states: [],
      notes: [],
    }));
  for (const mirror of contractMirrors) {
    test(`the ${mirror.contract_variant} contract mirror opens from Contratos in read-only mode`, {
      tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // Falla si un espejo admite edición o deja de mostrar su versión vigente.
      await mockApi(page, async ({ apiPath }) => {
        if (apiPath === 'auth/check/') return authCheck;
        if (apiPath === 'documents/') {
          return { status: 200, contentType: 'application/json', body: JSON.stringify(contractMirrors) };
        }
        if (
          apiPath === 'document-folders/'
          || apiPath === 'document-tags/'
          || apiPath === 'document-states/'
          || apiPath === 'document-state-groups/'
        ) {
          return { status: 200, contentType: 'application/json', body: JSON.stringify([
            { id: 121, name: 'Contratos', slug: 'contratos', parent: null, is_archived: false },
          ]) };
        }
        const detailId = /^documents\/(\d+)\/detail\/$/.exec(apiPath)?.[1];
        const mirror = contractMirrors.find((item) => item.id === Number(detailId));
        if (mirror) {
          return { status: 200, contentType: 'application/json', body: JSON.stringify(mirror) };
        }
        if (/^documents\/\d+\/pdf\/$/.test(apiPath)) {
          return { status: 200, contentType: 'application/pdf', body: '%PDF-1.4 live contract' };
        }
        return null;
      });
      // quality: allow-deep-link (the panel is the entry; Documents and each mirror are reached through UI links)
      await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
      await page.getByRole('link', { name: 'Gestor Documental', exact: true }).click();
      await page.waitForURL('**/en-us/panel/documents');

      const row = page.getByTestId(`document-row-${mirror.id}`);
      await expect(row).toContainText(mirror.title);
      await expect(row).toContainText('Contratos');
      await expect(row).toHaveAttribute('draggable', 'false');

      await row.getByRole('button', { name: `Acciones de ${mirror.title}`, exact: true }).click();
      const actions = page.getByTestId('document-actions-list');
      await expect(actions).toContainText('Ver contrato vigente');
      await expect(actions).not.toContainText(/Editar contenido|Renombrar|Mover a carpeta|Duplicar|Archivar|Eliminar/);
      await actions.getByRole('button', { name: /^Ver contrato vigente/ }).click();
      await expect(page).toHaveURL(new RegExp(`/panel/documents/${mirror.id}/edit(?:\\?|$)`));

      await expect(page.getByTestId('doc-contract-mirror-alert'))
        .toContainText('Contrato vigente, en solo lectura');
      await expect(page.getByTestId('doc-generated-pdf-frame')).toHaveAttribute(
        'src', new RegExp(`/api/documents/${mirror.id}/pdf/`),
      );
      await expect(page.getByTestId('doc-contract-version')).toContainText(new RegExp(`Versión\\s*${mirror.contract_version}\\b`));
      await expect(page.getByTestId('doc-contract-version')).toContainText(mirror.synced_label);
      await expect(page.getByTestId('doc-markdown-editor-panel')).toHaveCount(0);
      await expect(page.getByTestId('doc-save')).toHaveCount(0);

      const download = page.waitForEvent('download');
      await page.getByTestId('doc-contract-markdown-download').click();
      expect((await download).suggestedFilename()).toBe(`${mirror.slug}.md`);

      await page.getByTestId('doc-cancel').click();
      await page.waitForURL(/\/en-us\/panel\/documents(?:\?|$)/);
    });
  }

  test('a stored collection account previews its PDF with editable observations', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the module entry; from
    // there this test follows the real list → editor → note interaction)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([issuedCollectionAccount]) };
      }
      if (
        apiPath === 'document-tags/'
        || apiPath === 'document-states/'
        || apiPath === 'document-state-groups/'
      ) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      if (apiPath === 'document-folders/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(documentFolderTree),
        };
      }
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(issuedCollectionAccount) };
      }
      if (apiPath === 'documents/1/pdf/') {
        return { status: 200, contentType: 'application/pdf', body: '%PDF-1.4 stored account' };
      }
      return null;
    });
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText(issuedCollectionAccount.title, { exact: true }).first())
      .toBeVisible({ timeout: 30000 });
    await page.getByTestId('document-open-1').click();

    await expect(page.getByTestId('doc-generated-snapshot-alert'))
      .toContainText('Cuenta de cobro archivada como PDF inmutable');
    await expect(page.getByTestId('doc-collection-account-facts'))
      .toContainText('PA-ACME-001');
    await expect(page.getByTestId('doc-collection-account-facts'))
      .toContainText('$1.490.000 COP');
    await expect(page.getByTestId('doc-generated-pdf-frame')).toBeVisible();
    const generatedPreview = await page.getByTestId('doc-generated-snapshot-panel')
      .evaluate((panel) => {
        const panelBox = panel.getBoundingClientRect();
        const frameBox = panel.querySelector('[data-testid="doc-generated-pdf-frame"]')
          .getBoundingClientRect();
        return { panelWidth: panelBox.width, frameHeight: frameBox.height };
      });
    expect(generatedPreview.panelWidth).toBeLessThanOrEqual(896);
    expect(generatedPreview.frameHeight).toBeLessThanOrEqual(544);
    const noteButton = page.getByTestId('doc-client-note-open');
    await expect(noteButton).toHaveAccessibleName('Gestionar observaciones privadas');
    await noteButton.click();
    await expect(page.getByTestId('client-note-subject')).toHaveValue('Cuenta emitida');
    await expect(page.getByTestId('client-note-subject')).toBeDisabled();
    await expect(page.getByTestId('document-observation-21')).toContainText('Pago pendiente de confirmar.');
    await expect(page.getByTestId('document-observation-delete-21')).toBeVisible();
    await expect(page.getByTestId('document-observation-edit-21')).toBeVisible();
    await expect(page.getByTestId('client-note-submit')).toHaveCount(0);
    await expect(page.getByTestId('client-note-add-custom')).toHaveCount(0);
  });

  test('a legacy issued account previews as PDF before backfill', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the module entry; from
    // there this test follows the real list → editor interaction)
    const legacyAccount = {
      ...issuedCollectionAccount,
      is_generated_snapshot: false,
    };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([legacyAccount]) };
      }
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(legacyAccount) };
      }
      if (apiPath === 'document-folders/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(documentFolderTree) };
      }
      if (
        apiPath === 'document-tags/'
        || apiPath === 'document-states/'
        || apiPath === 'document-state-groups/'
      ) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      if (apiPath === 'documents/1/pdf/') {
        return { status: 200, contentType: 'application/pdf', body: '%PDF-1.4 legacy fallback' };
      }
      return null;
    });
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('document-open-1').click();

    await expect(page.getByTestId('doc-generated-snapshot-panel'))
      .toContainText('mientras se completa su archivado definitivo');
    await expect(page.getByTestId('doc-generated-pdf-frame')).toBeVisible();
    await expect(page.getByTestId('doc-markdown-editor-panel')).toHaveCount(0);
    await expect(page.getByTestId('doc-client-note-open'))
      .toHaveAccessibleName('Gestionar observaciones privadas');
  });

  test('the folder path navigates to an ancestor', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const locatedDocument = {
      ...mockDocument,
      folder: 30,
      folder_name: '08 - Agosto',
    };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([locatedDocument]) };
      }
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(locatedDocument) };
      }
      if (apiPath === 'document-folders/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(documentFolderTree) };
      }
      if (
        apiPath === 'document-tags/'
        || apiPath === 'document-states/'
        || apiPath === 'document-state-groups/'
      ) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('document-open-1').click();

    await expect(page.getByTestId('doc-location-path'))
      .toHaveAttribute('title', 'Documentos / Acme / Portal / 08 - Agosto');
    await expect(page.getByTestId('doc-location-segment-0'))
      .toHaveAttribute('href', /folder=root/);
    const projectFolder = page.getByTestId('doc-location-segment-2');
    await expect(projectFolder).toHaveAttribute('href', /folder=20/);
    await expect.poll(() => projectFolder.evaluate(
      (element) => getComputedStyle(element).cursor,
    )).toBe('pointer');
    await projectFolder.click();

    await expect(page).toHaveURL(/\/panel\/documents\?.*folder=20/);
  });

  test('a generated proposal version is immutable while observations remain editable', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the module entry; this test
    // follows the real list → generated snapshot editor interaction)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') return { status: 200, contentType: 'application/json', body: JSON.stringify([generatedProposalSnapshot]) };
      if (apiPath === 'documents/1/detail/') return { status: 200, contentType: 'application/json', body: JSON.stringify(generatedProposalSnapshot) };
      if (
        apiPath === 'document-folders/' || apiPath === 'document-tags/'
        || apiPath === 'document-states/' || apiPath === 'document-state-groups/'
      ) return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      return null;
    });
    await page.goto('/panel/documents');
    await page.getByTestId('document-open-1').click();

    await expect(page.getByTestId('doc-generated-snapshot-alert')).toContainText('Versión 2');
    await expect(page.getByTestId('doc-generated-snapshot-panel')).toBeVisible();
    await expect(page.getByRole('textbox', { name: /^Título$/i })).toHaveAttribute('readonly');
    await page.getByTestId('doc-document-actions-trigger').click();
    await expect(page.getByRole('menuitem', { name: /Descargar/ })).toHaveCount(1);
    await page.getByTestId('doc-client-note-open').click();
    await expect(page.getByTestId('client-note-subject')).toBeDisabled();
    await expect(page.getByTestId('document-observation-edit-31')).toBeVisible();
  });

  test('copies an observation from an issued collection account', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([issuedCollectionAccount]) };
      }
      if (
        apiPath === 'document-folders/'
        || apiPath === 'document-tags/'
        || apiPath === 'document-states/'
        || apiPath === 'document-state-groups/'
      ) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(issuedCollectionAccount) };
      }
      return null;
    });
    await page.goto('/panel/documents');
    await page.getByTestId('document-open-1').click();
    await page.getByTestId('doc-client-note-open').click();

    const copyButton = page.getByTestId('document-observation-copy-21');
    await expect(copyButton).toHaveAttribute('data-panel-action', 'copy');
    await expect(copyButton).toHaveAccessibleName('Copiar Conciliación');
    await copyButton.click();
    await expect(copyButton).toHaveAccessibleName('Observación copiada');
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toBe('Pago pendiente de confirmar.');
  });

  test('back link navigates to documents list', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the behavior under test starts inside the editor
    // and follows its visible back link to the document list)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') return { status: 200, contentType: 'application/json', body: JSON.stringify(mockDocument) };
      return null;
    });
    await page.goto('/panel/documents/1/edit');

    const backLink = page.getByRole('link', { name: /Volver a documentos/i });
    await expect(backLink).toBeVisible();
    await expect(backLink).toHaveAttribute('href', /\/panel\/documents/);
    await backLink.click();
    await expect(page).toHaveURL(/\/panel\/documents\/?$/);
  });

  test('saving changes shows success feedback after the PATCH response', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') return { status: 200, contentType: 'application/json', body: JSON.stringify(mockDocument) };
      if (apiPath === 'documents/1/update/' && method === 'PATCH') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...mockDocument, title: 'Contrato Actualizado' }) };
      }
      return null;
    });
    await page.goto('/panel/documents/1/edit');

    const titleInput = page.getByRole('textbox', { name: /^Título$/i });
    await titleInput.fill('Contrato Actualizado');
    const requestPromise = page.waitForRequest(
      (request) => request.url().includes('/api/documents/1/update/')
        && request.method() === 'PATCH',
    );
    // Por testid: el aviso de cambios sin guardar aporta su propio "Guardar
    // ahora", así que un match por rol dejó de identificar un solo botón.
    await page.getByTestId('doc-save').click();
    const request = await requestPromise;

    expect(request.postDataJSON().title).toBe('Contrato Actualizado');
    await expect(page.getByText('Documento guardado', { exact: true })).toBeVisible();
  });

  test('picking another folder in the picker saves its id', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const filedDocument = { ...mockDocument, folder: 30, folder_name: '08 - Agosto' };
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') return { status: 200, contentType: 'application/json', body: JSON.stringify(filedDocument) };
      if (apiPath === 'document-folders/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(documentFolderTree) };
      }
      if (apiPath === 'documents/1/update/' && method === 'PATCH') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...filedDocument, folder: 20 }) };
      }
      return null;
    });
    await page.goto('/panel/documents/1/edit');

    const folderPicker = page.getByTestId('doc-folder-select');
    await expect(folderPicker).toHaveValue('Acme / Portal / 08 - Agosto');
    await folderPicker.fill('portal');
    await page.getByTestId('doc-folder-select-option-20').click();
    await expect(folderPicker).toHaveValue('Acme / Portal');
    const requestPromise = page.waitForRequest(
      (request) => request.url().includes('/api/documents/1/update/')
        && request.method() === 'PATCH',
    );
    await page.getByTestId('doc-save').click();

    expect((await requestPromise).postDataJSON().folder_id).toBe(20);
  });

  for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
    test.describe(`folder picker long identities — ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
      test.use(viewportUse(profile));

      test(`saves the exact long duplicate folder identity at ${profile}`, {
        // Bug this catches: clipped folder names or context make same-named
        // destinations indistinguishable and save the wrong folder id.
        tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success', '@responsive:documents'],
      }, async ({ page }) => {
        // quality: allow-duplicate (per-viewport contract: folder picker identity)
        const filedDocument = { ...mockDocument, folder: null, folder_name: null };
        let savedPayload = null;
        await mockApi(page, async ({ apiPath, method, route }) => {
          if (apiPath === 'auth/check/') return authCheck;
          if (apiPath === 'documents/1/detail/') return { status: 200, contentType: 'application/json', body: JSON.stringify(filedDocument) };
          if (apiPath === 'document-folders/') return { status: 200, contentType: 'application/json', body: JSON.stringify(duplicateFolderTree) };
          if (apiPath === 'documents/1/update/' && method === 'PATCH') {
            savedPayload = route.request().postDataJSON();
            return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...filedDocument, ...savedPayload }) };
          }
          return null;
        });

        await page.goto('/panel/documents/1/edit', { waitUntil: 'domcontentloaded' });
        const picker = page.getByTestId('doc-folder-select');
        await picker.click();
        const firstOption = page.getByTestId(`doc-folder-select-option-${duplicateFolderOne.id}`);
        const secondOption = page.getByTestId(`doc-folder-select-option-${duplicateFolderTwo.id}`);
        const firstDetail = page.getByTestId(`doc-folder-select-detail-${duplicateFolderOne.id}`);
        const secondDetail = page.getByTestId(`doc-folder-select-detail-${duplicateFolderTwo.id}`);
        await expect(firstOption.getByText(duplicateFolderName, { exact: true })).toHaveText(duplicateFolderName);
        await expect(firstDetail).toHaveText('Renovación anual Cliente Boreal · Renovación operativa Boreal · Cliente Boreal');
        await expect(secondOption.getByText(duplicateFolderName, { exact: true })).toHaveText(duplicateFolderName);
        await expect(secondDetail).toHaveText('Conciliación trimestral Cliente Boreal · Conciliación documental Boreal · Cliente Boreal');
        const geometry = await Promise.all([
          firstOption.getByText(duplicateFolderName, { exact: true }), firstDetail,
          secondOption.getByText(duplicateFolderName, { exact: true }), secondDetail,
        ].map((option) => option.evaluate((element) => ({
          scrollWidth: element.scrollWidth, clientWidth: element.clientWidth,
        }))));
        expect(geometry.every((row) => row.scrollWidth <= row.clientWidth)).toBe(true);

        await secondOption.click();
        await page.getByTestId('doc-save').click();
        await expect.poll(() => savedPayload?.folder_id).toBe(duplicateFolderTwo.id);
      });
    });
  }

  test('edits a saved observation', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const documentWithNote = {
      ...mockDocument,
      content_markdown: '# Contrato\n\nEste es el contenido del contrato.',
      client_email_subject: 'Contrato listo',
      client_email_body: 'Hola Ana,\n\nEl contrato está listo.',
      client_whatsapp_message: 'Hola Ana, revisa el contrato en tu correo.',
      client_custom_notes: [
        { title: 'Seguimiento', content: 'Llamar el viernes.' },
      ],
      notes: [
        { id: 11, title: 'Seguimiento', content: 'Llamar el viernes.', status: 'open', order: 0 },
      ],
    };
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(documentWithNote) };
      }
      if (apiPath === 'documents/1/notes/11/' && method === 'PATCH') {
        const body = route.request().postDataJSON();
        Object.assign(documentWithNote.notes[0], body);
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(documentWithNote.notes[0]),
        };
      }
      return null;
    });
    await page.goto('/panel/documents/1/edit');

    await page.getByTestId('doc-client-note-open').click();
    await expect(page.getByTestId('client-note-subject')).toHaveValue('Contrato listo');
    await page.getByTestId('document-observation-edit-11').click();
    await page.getByLabel('Contenido de la observación').fill('Llamar el lunes.');
    const requestPromise = page.waitForRequest(
      (request) => request.url().includes('/api/documents/1/notes/11/')
        && request.method() === 'PATCH',
    );
    await page.getByTestId('document-observation-edit-form').getByRole('button', { name: 'Guardar cambios' }).click();
    const request = await requestPromise;

    expect(request.postDataJSON()).toEqual({
      title: 'Seguimiento',
      content: 'Llamar el lunes.',
    });
    await expect(page.getByTestId('document-observation-11')).toContainText('Llamar el lunes.');
  });

  test('keeps unrelated document edits pending after saving notes', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockDocument) };
      }
      if (apiPath === 'documents/1/update/' && method === 'PATCH') {
        const body = route.request().postDataJSON();
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...mockDocument, ...body }),
        };
      }
      return null;
    });
    await page.goto('/panel/documents/1/edit');
    await page.getByLabel(/T[ií]tulo/i).fill('Título todavía pendiente');
    await page.getByTestId('doc-client-note-open').click();
    await page.getByTestId('client-note-subject').fill('Notas ya persistidas');

    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/documents/1/update/'),
    );
    await page.getByTestId('client-note-submit').click();
    await responsePromise;

    await expect(page.getByLabel(/T[ií]tulo/i)).toHaveValue('Título todavía pendiente');
    await expect(page.getByTestId('doc-unsaved-notice')).toContainText('Título sin guardar');
    await expect(page.getByTestId('doc-save')).toBeEnabled();
  });

  /**
   * Regression: a long note could leave the save bar below the viewport, or
   * visually fixed while disconnected from the document update action.
   */
  for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
    test.describe(`fixed notes bar · ${profile}`, () => {
      test.use(viewportUse(profile));

      test('saves a long client note from the visible footer after scrolling', {
        tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success', `@viewport:${profile}`],
      }, async ({ page }) => {
        const longEmail = Array.from(
          { length: 24 },
          (_, index) => `Párrafo ${index + 1} del correo con el detalle de la entrega.`,
        ).join('\n\n');
        const documentWithLongEmail = {
          ...mockDocument,
          client_email_subject: 'Contrato listo',
          client_email_body: longEmail,
          client_whatsapp_message: 'Hola Ana, revisa tu correo.',
          notes: [],
        };
        await mockApi(page, async ({ route, apiPath, method }) => {
          if (apiPath === 'auth/check/') return authCheck;
          if (apiPath === 'documents/1/detail/') {
            return { status: 200, contentType: 'application/json', body: JSON.stringify(documentWithLongEmail) };
          }
          if (apiPath === 'documents/1/update/' && method === 'PATCH') {
            const body = route.request().postDataJSON();
            return {
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({ ...documentWithLongEmail, ...body }),
            };
          }
          return null;
        });
        await page.goto('/panel/documents/1/edit', { waitUntil: 'domcontentloaded' });
        await page.getByTestId('doc-client-note-open').click();

        // The whole email reads without scrolling inside its own field.
        const email = page.getByTestId('client-note-email');
        await expect(email).toHaveValue(longEmail);
        const hiddenEmailHeight = await email.evaluate((field) => field.scrollHeight - field.clientHeight);
        expect(hiddenEmailHeight).toBeLessThanOrEqual(1);

        const modalBody = page.getByTestId('document-client-note-modal');
        const footer = page.locator('[data-modal-footer]');
        const save = footer.getByTestId('client-note-submit');
        await expect(save).toBeDisabled();
        await expect(save).toHaveAttribute('title', 'No hay cambios por guardar.');

        await page.getByTestId('client-note-subject').fill('Contrato listo para firma');

        // Scroll the actual document-note body. Measuring before clicking is
        // essential: Playwright would otherwise scroll the action into view.
        await modalBody.hover();
        await page.mouse.wheel(0, 10_000);
        await expect.poll(() => modalBody.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);

        const viewport = page.viewportSize();
        const dialog = page.getByRole('dialog');
        const [footerBox, saveBox] = await Promise.all([footer.boundingBox(), save.boundingBox()]);
        expect(footerBox, `No se pudo medir el pie fijo en ${profile}`).not.toBeNull();
        expect(saveBox, `No se pudo medir Guardar cambios en ${profile}`).not.toBeNull();
        expect(footerBox.y).toBeGreaterThanOrEqual(0);
        expect(footerBox.y + footerBox.height).toBeLessThanOrEqual(viewport.height + 1);
        expect(saveBox.y + saveBox.height).toBeLessThanOrEqual(viewport.height + 1);
        expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
        await expect(save).toHaveText('Guardar cambios');
        await expect(save).toBeEnabled();
        await expect(page.getByTestId('client-note-unsaved')).toHaveText('Cambios sin guardar');

        const requestPromise = page.waitForRequest(
          (request) => request.url().includes('/api/documents/1/update/') && request.method() === 'PATCH',
        );
        await save.click();
        const request = await requestPromise;

        expect(request.postDataJSON()).toMatchObject({
          client_email_subject: 'Contrato listo para firma',
          client_email_body: longEmail,
        });
        await expect(page.getByText('Notas guardadas', { exact: true })).toBeVisible();
      });
    });
  }

  test('deletes an observation from the saved document', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const documentWithCustomNote = {
      ...mockDocument,
      content_markdown: '# Contrato',
      client_custom_notes: [
        { title: 'Temporal', content: 'Eliminar después de revisar.' },
      ],
      notes: [
        { id: 11, title: 'Temporal', content: 'Eliminar después de revisar.', status: 'open', order: 0 },
      ],
    };
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(documentWithCustomNote) };
      }
      if (apiPath === 'documents/1/notes/11/' && method === 'DELETE') {
        documentWithCustomNote.notes = [];
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ deleted_note_ids: [11], closed_episode_ids: [], state_closed: false }),
        };
      }
      return null;
    });
    await page.goto('/panel/documents/1/edit');
    await page.getByTestId('doc-client-note-open').click();
    await page.getByTestId('document-observation-delete-11').click();
    await expect(page.getByTestId('document-observation-delete-confirmation'))
      .toContainText('Eliminar después de revisar.');
    const requestPromise = page.waitForRequest(
      (request) => request.url().includes('/api/documents/1/notes/11/')
        && request.method() === 'DELETE',
    );
    await page.getByTestId('document-observation-confirm-delete').click();
    const request = await requestPromise;

    expect(request.method()).toBe('DELETE');
    await expect(page.getByTestId('document-observation-11')).toHaveCount(0);
  });

  test('rejected notes keep the modal draft', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const documentWithMarkdown = {
      ...mockDocument,
      content_markdown: '# Contrato\n\nContenido.',
    };
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(documentWithMarkdown) };
      }
      if (apiPath === 'documents/1/update/' && method === 'PATCH') {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ client_email_subject: ['Revisa el asunto.'] }),
        };
      }
      return null;
    });
    await page.goto('/panel/documents/1/edit');
    await page.getByTestId('doc-client-note-open').click();
    await page.getByTestId('client-note-subject').fill('Asunto rechazado');
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/documents/1/update/'),
    );
    await page.getByTestId('client-note-submit').click();
    await responsePromise;

    await expect(page.getByText('client_email_subject: Revisa el asunto.')).toBeVisible();
    await expect(page.getByTestId('client-note-subject')).toHaveValue('Asunto rechazado');
    await expect(page.getByTestId('document-client-note-modal')).toBeVisible();
  });

  test('a server failure preserves the edited notes', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const documentWithMarkdown = {
      ...mockDocument,
      content_markdown: '# Contrato\n\nContenido.',
    };
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(documentWithMarkdown) };
      }
      if (apiPath === 'documents/1/update/' && method === 'PATCH') {
        return {
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Servicio temporalmente no disponible.' }),
        };
      }
      return null;
    });
    await page.goto('/panel/documents/1/edit');
    await page.getByTestId('doc-client-note-open').click();
    await page.getByTestId('client-note-whatsapp').fill('Mensaje que debe sobrevivir.');
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/documents/1/update/'),
    );
    await page.getByTestId('client-note-submit').click();
    await responsePromise;

    await expect(page.getByTestId('client-note-whatsapp'))
      .toHaveValue('Mensaje que debe sobrevivir.');
  });

  test('copies the markdown content to the clipboard', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const documentWithMarkdown = { ...mockDocument, content_markdown: '# Contrato\n\nEste es el contenido del contrato.' };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') return { status: 200, contentType: 'application/json', body: JSON.stringify(documentWithMarkdown) };
      return null;
    });
    await page.goto('/panel/documents/1/edit');

    await page.getByRole('button', { name: /^Copiar$/i }).click();

    await expect(page.getByRole('button', { name: /^Copiado$/i })).toBeVisible({ timeout: 5000 });
    const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    expect(clipboardText).toBe(documentWithMarkdown.content_markdown);
  });

  test('selecting professional style applies its preview heading color', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin'],
  }, async ({ page }) => {
    const documentWithMarkdown = {
      ...mockDocument,
      content_markdown: '# Contrato\n\nEste es el contenido del contrato.',
      template_style: 'friendly',
    };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') return { status: 200, contentType: 'application/json', body: JSON.stringify(documentWithMarkdown) };
      return null;
    });
    await page.goto('/panel/documents/1/edit');

    await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();
    const previewHeading = page.getByRole('heading', { name: 'Contrato', level: 1, exact: true });
    await expect(previewHeading).toBeVisible();
    await page.getByTestId('doc-style-professional').click();
    await expect(previewHeading).toHaveCSS('color', 'rgb(0, 41, 33)');
  });

  test('pastes clipboard content into the markdown textarea', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const documentWithMarkdown = { ...mockDocument, content_markdown: '# Contrato\n\nEste es el contenido del contrato.' };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') return { status: 200, contentType: 'application/json', body: JSON.stringify(documentWithMarkdown) };
      return null;
    });
    await page.goto('/panel/documents/1/edit');

    const textarea = page.getByLabel('Contenido Markdown');
    await textarea.click();
    await page.keyboard.press('Control+End');
    await page.evaluate((text) => navigator.clipboard.writeText(text), '\n\nTexto pegado desde el portapapeles.');

    await page.getByRole('button', { name: /^Pegar$/i }).click();

    await expect(page.getByRole('button', { name: /^Pegado$/i })).toBeVisible({ timeout: 5000 });
    await expect(textarea).toHaveValue(`${documentWithMarkdown.content_markdown}\n\nTexto pegado desde el portapapeles.`);
  });

  test('the saved association links back to its client and project', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the editor is reached by URL across this whole
    // spec; the subject is the association block it renders after loading)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/1/detail/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...mockDocument,
            client: 7, client_display_name: 'Kore SAS',
            project: 11, project_name: 'Kore - Diseño',
          }),
        };
      }
      // El proyecto 11 tiene que estar en la lista de SU cliente: el backend
      // valida esa pertenencia al escribir, así que un par ya persistido
      // siempre aparece acá. Con la lista vacía el picker lo daba por ajeno y
      // lo soltaba, y el documento quedaba con un cambio pendiente que nadie
      // pidió — algo que ahora el aviso de cambios sin guardar hace visible.
      if (apiPath === 'accounting/projects/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            results: [{
              id: 11, name: 'Kore - Diseño', status: 'active', status_label: 'Activo',
              client_profile_id: 7, client_display_name: 'Kore SAS',
            }],
          }),
        };
      }
      if (apiPath === 'document-folders/' || apiPath === 'document-tags/') return { status: 200, contentType: 'application/json', body: '[]' };
      if (apiPath.startsWith('accounts/saved-filter-tabs')) return { status: 200, contentType: 'application/json', body: '[]' };
      if (apiPath === 'proposals/client-profiles/status-counts/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ all: 0, active: 0, orphans: 0, archived: 0 }) };
      }
      if (apiPath === 'proposals/client-profiles/') return { status: 200, contentType: 'application/json', body: '[]' };
      return null;
    });
    await page.goto('/panel/documents/1/edit');

    // La relación sirve en las dos direcciones: del documento a su cliente
    // (ficha expandida vía ?highlight=) y a su proyecto.
    await expect(page.getByTestId('doc-client-autocomplete')).toHaveValue('Kore SAS');
    await expect(page.getByTestId('document-project-link'))
      .toHaveAttribute('href', /\/panel\/projects\?highlight=11/);

    // Seguir el enlace prueba la vuelta: aterriza en /panel/clients con el
    // ?highlight= que expande la ficha de ese cliente.
    await page.getByTestId('document-client-link').click();
    await expect(page).toHaveURL(/\/panel\/clients/, { timeout: 30_000 });
  });
});
