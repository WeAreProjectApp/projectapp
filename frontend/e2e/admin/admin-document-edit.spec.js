/**
 * E2E tests for admin document edit flow.
 *
 * @flow:admin-document-edit
 * Covers: edit form pre-filled with existing document data, save updates document,
 *         client messages and normalized observations (including read-only copy), responsive header,
 *         back link navigation, download PDF action, copy/paste markdown content
 *         toolbar buttons, template style switch (Amigable/Profesional) toggling
 *         the preview theme, and the dual-style PDF download dropdown.
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

      test('wide editor constrains short previews to document proportions', {
        tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display', '@responsive:canvas'],
      }, async ({ page }) => {
        // quality: allow-duplicate (wide-only geometry contract for preview surfaces)
        // quality: allow-deep-link (the editor preview is the documented display surface)
        await mockResponsiveHeaderApi(page);
        await page.goto('/en-us/panel/documents/1/edit', { waitUntil: 'domcontentloaded' });
        await expect(page.getByTestId('doc-markdown-preview-pane')).toBeVisible();

        const inlineLayout = await page.evaluate(() => {
          const preview = document.querySelector('[data-testid="doc-markdown-preview-pane"]')
            .getBoundingClientRect();
          const textarea = document.querySelector('#edit-markdown').getBoundingClientRect();
          return {
            previewWidth: preview.width,
            previewHeight: preview.height,
            textareaHeight: textarea.height,
          };
        });
        expect(inlineLayout.previewWidth).toBeLessThanOrEqual(896);
        expect(inlineLayout.previewHeight).toBeLessThan(inlineLayout.textareaHeight);

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

  test('the live contract window previews it and exports Markdown without editing', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the module entry; from
    // there this test follows the real list → contract window interaction)
    const contractWindow = {
      ...mockDocument,
      title: 'Contrato de prestación de servicios — borrador vigente',
      slug: 'contrato-vigente',
      is_contract_mirror: true,
      content_markdown: '# CONTRATO DE PRESTACIÓN DE SERVICIOS\n\n## CLÁUSULA PRIMERA — OBJETO DEL CONTRATO\n',
      active_states: [],
      notes: [],
    };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([contractWindow]) };
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
        return { status: 200, contentType: 'application/json', body: JSON.stringify(contractWindow) };
      }
      if (apiPath === 'documents/1/pdf/') {
        return { status: 200, contentType: 'application/pdf', body: '%PDF-1.4 live contract' };
      }
      return null;
    });
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText(contractWindow.title, { exact: true }).first())
      .toBeVisible({ timeout: 30000 });
    await page.getByTestId('document-open-1').click();

    await expect(page.getByTestId('doc-contract-mirror-alert'))
      .toContainText('Contrato vigente, en solo lectura');
    await expect(page.getByTestId('doc-generated-pdf-frame')).toBeVisible();
    await expect(page.getByTestId('doc-markdown-editor-panel')).toHaveCount(0);
    await expect(page.getByTestId('doc-save')).toBeDisabled();

    const download = page.waitForEvent('download');
    await page.getByTestId('doc-contract-markdown-download').click();
    expect((await download).suggestedFilename()).toBe('contrato-vigente.md');
  });

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
