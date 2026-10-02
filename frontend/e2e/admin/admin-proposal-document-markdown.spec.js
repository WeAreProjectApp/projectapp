/**
 * E2E coverage for Markdown export controls in a proposal's Documents tab.
 *
 * Catches document controls that call another document's endpoint, offer
 * unsupported extraction, or become unreachable after the action row wraps.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';

const PROPOSAL_ID = 964;
const IMAGE_URL = 'https://e2e.example/uploads/arquitectura.png';
const ORIGINAL_ATTACHMENT_BYTES = Buffer.from('original-docx-bytes', 'utf8');

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const attachments = [
  {
    id: 801,
    title: 'Anexo de arquitectura',
    document_type: 'legal_annex',
    document_type_display: 'Anexo legal',
    file: '/media/attachments/arquitectura.docx',
    is_generated: false,
    created_at: '2026-09-24T10:00:00Z',
  },
  {
    id: 802,
    title: 'Diagrama de arquitectura',
    document_type: 'client_document',
    document_type_display: 'Documento del cliente',
    file: IMAGE_URL,
    is_generated: false,
    created_at: '2026-09-24T10:00:00Z',
  },
  {
    id: 803,
    title: 'Anexo legado',
    document_type: 'legal_annex',
    document_type_display: 'Anexo legal',
    file: '/media/attachments/anexo-legado.doc',
    is_generated: false,
    created_at: '2026-09-24T10:00:00Z',
  },
  {
    id: 804,
    title: 'Contrato escaneado',
    document_type: 'client_document',
    document_type_display: 'Documento del cliente',
    file: '/media/attachments/contrato-escaneado.pdf',
    is_generated: false,
    created_at: '2026-09-24T10:00:00Z',
  },
];

function buildProposal(status = 'negotiating') {
  return {
    id: PROPOSAL_ID,
    uuid: 'c2d5e4f9-9d33-45b5-8a13-ef9640000001',
    slug: 'markdown-documents-e2e',
    title: 'Propuesta Markdown E2E',
    client_name: 'Cliente Markdown',
    client_email: 'cliente.markdown@example.com',
    status,
    language: 'es',
    total_investment: '12000000',
    currency: 'COP',
    sections: [],
    requirement_groups: [],
    change_logs: [],
    contract_params: { contract_source: 'default' },
    proposal_documents: [
      {
        id: 700,
        title: 'Contrato de desarrollo',
        document_type: 'contract',
        document_type_display: 'Contrato',
        file: '/media/contracts/contrato-desarrollo.pdf',
        is_generated: true,
        created_at: '2026-09-24T09:00:00Z',
      },
      ...attachments,
    ],
  };
}

const markdownByEndpoint = {
  [`proposals/${PROPOSAL_ID}/contract/markdown/`]: '# Contrato de desarrollo\n\nCláusula de alcance.',
  [`proposals/${PROPOSAL_ID}/formalization/markdown/commercial/`]: '# Propuesta comercial formal\n\nInversión: COP 12.000.000.',
  [`proposals/${PROPOSAL_ID}/formalization/markdown/technical/`]: '# Detalle técnico formal\n\n## Integraciones',
  [`proposals/${PROPOSAL_ID}/documents/801/markdown/`]: '# Anexo de arquitectura\n\n| Sistema | Estado |\n| --- | --- |\n| API \\| proxy | \\*sin formato\\* |',
  [`proposals/${PROPOSAL_ID}/documents/804/markdown/`]: '',
};

async function seedAdmin(page) {
  await setAuthLocalStorage(page, {
    token: 'e2e-markdown-admin-token',
    userAuth: { id: 9640, role: 'admin', is_staff: true },
  });
}

function proposalHandler({ status = 'negotiating', markdownResponses = {}, requests = {} } = {}) {
  const proposal = buildProposal(status);
  return async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'proposals/dashboard/') return json({ total: 1, conversion_rate: 100 });
    if (apiPath === 'proposals/alerts/') return json([]);
    if (apiPath === 'proposals/' && method === 'GET') return json([proposal]);
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return json(proposal);
    if (apiPath === `proposals/${PROPOSAL_ID}/documents/801/download/` && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers: { 'content-disposition': 'attachment; filename="arquitectura-original.docx"' },
        body: ORIGINAL_ATTACHMENT_BYTES,
      };
    }
    if (apiPath in markdownByEndpoint && method === 'GET') {
      requests[apiPath] = (requests[apiPath] || 0) + 1;
      const response = markdownResponses[apiPath]?.(requests[apiPath]) || json({
        markdown: markdownByEndpoint[apiPath],
        warnings: apiPath.endsWith('/801/markdown/') ? ['Tablas reconstruidas desde DOCX.'] : [],
      });
      return response;
    }
    return null;
  };
}

async function openDocumentsFromPanel(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Propuestas', exact: true }).click();
  await expect(page).toHaveURL(/\/panel\/proposals$/);
  await page.getByTestId(`proposal-open-${PROPOSAL_ID}`).click();
  await expect(page).toHaveURL(new RegExp(`/panel/proposals/${PROPOSAL_ID}/edit`));
  await selectProposalDestination(page, 'documents', 'documents');
  await expect(page.getByText('Documentos adjuntos')).toHaveCount(1);
}

async function openDocumentsFromCompactPanel(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Abrir menú' }).click();
  await page.getByRole('dialog', { name: 'Menú principal' }).getByRole('link', { name: 'Propuestas', exact: true }).click();
  await page.getByTestId(`proposal-open-${PROPOSAL_ID}`).click();
  await selectProposalDestination(page, 'documents', 'documents');
  await expect(page.getByText('Documentos adjuntos')).toHaveCount(1);
}

async function readDownloadedBytes(download) {
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  return Buffer.concat(chunks);
}

async function compactActionGeometry(action) {
  await action.scrollIntoViewIfNeeded();
  const box = await action.boundingBox();
  return {
    width: box?.width || 0,
    height: box?.height || 0,
    right: (box?.x || 0) + (box?.width || 0),
  };
}

test.describe('Admin proposal document Markdown exports', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await seedAdmin(page);
  });

  test.describe('copies the selected document instead of another document', () => {
    for (const documentCase of [
      { id: 'proposal-copy-contract', endpoint: `proposals/${PROPOSAL_ID}/contract/markdown/` },
      { id: 'proposal-copy-commercial', endpoint: `proposals/${PROPOSAL_ID}/formalization/markdown/commercial/` },
      { id: 'proposal-copy-technical', endpoint: `proposals/${PROPOSAL_ID}/formalization/markdown/technical/` },
      { id: 'proposal-copy-attachment-801', endpoint: `proposals/${PROPOSAL_ID}/documents/801/markdown/` },
    ]) {
      test(`copies Markdown from ${documentCase.id}`, {
        tag: ['@flow:admin-proposal-document-markdown', '@outcome:success', '@role:admin'],
      }, async ({ page, context }) => {
        const requests = {};
        await context.grantPermissions(['clipboard-read', 'clipboard-write']);
        await mockApi(page, proposalHandler({ requests }));

        await openDocumentsFromPanel(page);
        await page.getByTestId(documentCase.id).click();

        await expect.poll(() => page.evaluate(() => navigator.clipboard.readText()))
          .toBe(markdownByEndpoint[documentCase.endpoint]);
        await expect(page.getByTestId(documentCase.id)).toHaveAttribute('data-action-status', 'success');
        expect(requests[documentCase.endpoint]).toBe(1);
      });
    }
  });

  test('renders DOCX Markdown and its extraction warning in the attachment preview', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, proposalHandler());

    await openDocumentsFromPanel(page);
    const docxRow = page.getByTestId('proposal-attachment-801');
    await docxRow.getByRole('button', { name: 'Vista previa de Anexo de arquitectura' }).click();
    const modal = page.getByTestId('markdown-preview-modal-panel');
    await expect(modal.getByRole('heading', { name: 'Anexo de arquitectura', level: 1 })).toHaveText('Anexo de arquitectura');
    await expect(modal.getByText('Tablas reconstruidas desde DOCX.')).toHaveText('Tablas reconstruidas desde DOCX.');
    await expect(modal.getByRole('columnheader', { name: 'Sistema' })).toHaveText('Sistema');
    await expect(modal.getByRole('cell', { name: 'API | proxy' })).toHaveText('API | proxy');
    await expect(modal.getByRole('cell', { name: '*sin formato*' })).toHaveText('*sin formato*');
  });

  test('keeps image preview available while explaining that OCR is required for copy', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await page.route(IMAGE_URL, (route) => route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('png') }));
    await mockApi(page, proposalHandler());

    await openDocumentsFromPanel(page);
    const imageRow = page.getByTestId('proposal-attachment-802');
    await imageRow.getByRole('button', { name: 'Vista previa de Diagrama de arquitectura' }).click();
    await expect(page.getByAltText('Diagrama de arquitectura')).toHaveAttribute('alt', 'Diagrama de arquitectura');
    await page.getByRole('button', { name: 'Cerrar vista previa' }).click();
    const copyButton = imageRow.getByTestId('proposal-copy-attachment-802');
    await expect(copyButton).toBeDisabled();
    await imageRow.locator('[data-disabled-action-proxy]')
      .filter({ has: page.getByTestId('proposal-copy-attachment-802') })
      .hover();
    await expect(page.getByRole('tooltip')).toHaveText('La imagen no tiene texto extraíble. Se requiere reconocimiento de texto.');
    await expect(imageRow.getByRole('button', { name: 'Descargar Diagrama de arquitectura' })).toBeEnabled();
  });

  test('does not offer preview or Markdown copy for legacy Office attachments', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, proposalHandler());

    await openDocumentsFromPanel(page);
    const legacyRow = page.getByTestId('proposal-attachment-803');
    const copyButton = legacyRow.getByTestId('proposal-copy-attachment-803');
    await expect(copyButton).toBeDisabled();
    await legacyRow.locator('[data-disabled-action-proxy]')
      .filter({ has: page.getByTestId('proposal-copy-attachment-803') })
      .hover();
    await expect(page.getByRole('tooltip')).toHaveText('Convierte el archivo a DOCX o XLSX para visualizar y copiar su contenido.');
    await expect(legacyRow.getByRole('button', { name: 'Vista previa de Anexo legado' })).toBeDisabled();
    await expect(legacyRow.getByRole('button', { name: 'Descargar Anexo legado' })).toBeEnabled();
  });

  test('downloads the original DOCX bytes with its server filename', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, proposalHandler());

    await openDocumentsFromPanel(page);
    const docxRow = page.getByTestId('proposal-attachment-801');
    const downloadPromise = page.waitForEvent('download');
    await docxRow.getByRole('button', { name: 'Descargar Anexo de arquitectura' }).click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('arquitectura-original.docx');
    expect(await readDownloadedBytes(download)).toEqual(ORIGINAL_ATTACHMENT_BYTES);
  });

  test('recovers from a Markdown export server failure instead of leaving copy stuck', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:failure', '@role:admin'],
  }, async ({ page, context }) => {
    const endpoint = `proposals/${PROPOSAL_ID}/formalization/markdown/commercial/`;
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await mockApi(page, proposalHandler({
      markdownResponses: {
        [endpoint]: (requestNumber) => (
          requestNumber === 1
            ? json({ error: 'No se pudo generar el documento.' }, 500)
            : json({ markdown: markdownByEndpoint[endpoint], warnings: [] })
        ),
      },
    }));

    await openDocumentsFromPanel(page);
    const copyButton = page.getByTestId('proposal-copy-commercial');
    await copyButton.click();
    await expect(page.getByRole('alert')).toContainText('No se pudo generar el documento.');
    await expect(copyButton).toBeEnabled();

    await copyButton.click();
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toBe(markdownByEndpoint[endpoint]);
    await expect(copyButton).toHaveAttribute('data-action-status', 'success');
  });

  test('recovers from a rejected clipboard write instead of claiming Markdown was copied', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:failure', '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, proposalHandler());
    await page.addInitScript(() => {
      let writeAttempts = 0;
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: {
          writeText: (text) => {
            writeAttempts += 1;
            return writeAttempts === 1
              ? Promise.reject(new DOMException('Clipboard blocked', 'NotAllowedError'))
              : Promise.resolve(text);
          },
        },
      });
    });

    await openDocumentsFromPanel(page);
    const copyButton = page.getByTestId('proposal-copy-contract');
    await copyButton.click();
    await expect(page.getByRole('alert')).toContainText('No se pudo copiar. Revisa el permiso del portapapeles y vuelve a intentarlo.');
    await expect(copyButton).toHaveAttribute('data-action-status', 'danger');
    await expect(copyButton).toBeEnabled();

    await copyButton.click();
    await expect(copyButton).toHaveAttribute('data-action-status', 'success');
  });

  test('shows the scanned-PDF extraction error without overwriting the clipboard', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:error', '@role:admin'],
  }, async ({ page, context }) => {
    const endpoint = `proposals/${PROPOSAL_ID}/documents/804/markdown/`;
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await mockApi(page, proposalHandler({
      markdownResponses: {
        [endpoint]: () => json({ error: 'El PDF escaneado requiere reconocimiento de texto antes de copiarse.' }, 422),
      },
    }));

    await openDocumentsFromPanel(page);
    await page.evaluate(() => navigator.clipboard.writeText('portapapeles intacto'));
    const copyButton = page.getByTestId('proposal-copy-attachment-804');
    await copyButton.click();

    await expect(page.getByRole('alert')).toContainText('El PDF escaneado requiere reconocimiento de texto antes de copiarse.');
    await expect(copyButton).toBeEnabled();
    await expect(copyButton).not.toHaveAttribute('data-action-status', 'success');
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe('portapapeles intacto');
  });
});

test.describe('Admin proposal document Markdown actions on compact screens', () => {
  test.use(viewportUse('compact'));
  test.setTimeout(60_000);

  test('keeps the Documents page free from horizontal overflow', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:display', '@role:admin', '@viewport:compact'],
  }, async ({ page }) => {
    await seedAdmin(page);
    await mockApi(page, proposalHandler({ status: 'accepted' }));

    await openDocumentsFromCompactPanel(page);
    const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test('keeps DOCX attachment controls reachable at 412px', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:display', '@role:admin', '@viewport:compact'],
  }, async ({ page }) => {
    await seedAdmin(page);
    await mockApi(page, proposalHandler());

    await openDocumentsFromCompactPanel(page);
    const row = page.getByTestId('proposal-attachment-801');
    const controls = [
      await compactActionGeometry(row.getByTestId('proposal-copy-attachment-801')),
      await compactActionGeometry(row.getByRole('button', { name: 'Vista previa de Anexo de arquitectura' })),
      await compactActionGeometry(row.getByRole('button', { name: 'Descargar Anexo de arquitectura' })),
    ];
    expect(controls.map(({ width, height, right }) => width > 0 && height > 0 && right <= 412)).toEqual([true, true, true]);
  });

  test('keeps image attachment controls reachable at 412px', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:display', '@role:admin', '@viewport:compact'],
  }, async ({ page }) => {
    await seedAdmin(page);
    await mockApi(page, proposalHandler());

    await openDocumentsFromCompactPanel(page);
    const row = page.getByTestId('proposal-attachment-802');
    const controls = [
      await compactActionGeometry(row.getByRole('button', { name: 'Vista previa de Diagrama de arquitectura' })),
      await compactActionGeometry(row.getByRole('button', { name: 'Descargar Diagrama de arquitectura' })),
    ];
    expect(controls.map(({ width, height, right }) => width > 0 && height > 0 && right <= 412)).toEqual([true, true]);
  });

  test('keeps the legacy attachment download reachable at 412px', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:display', '@role:admin', '@viewport:compact'],
  }, async ({ page }) => {
    await seedAdmin(page);
    await mockApi(page, proposalHandler());

    await openDocumentsFromCompactPanel(page);
    const download = await compactActionGeometry(page.getByTestId('proposal-attachment-803').getByRole('button', { name: 'Descargar Anexo legado' }));
    expect(download.width).toBeGreaterThan(0);
    expect(download.height).toBeGreaterThan(0);
    expect(download.right).toBeLessThanOrEqual(412);
  });

  test('keeps scanned-PDF attachment controls reachable at 412px', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:display', '@role:admin', '@viewport:compact'],
  }, async ({ page }) => {
    await seedAdmin(page);
    await mockApi(page, proposalHandler());

    await openDocumentsFromCompactPanel(page);
    const row = page.getByTestId('proposal-attachment-804');
    const controls = [
      await compactActionGeometry(row.getByTestId('proposal-copy-attachment-804')),
      await compactActionGeometry(row.getByRole('button', { name: 'Vista previa de Contrato escaneado' })),
      await compactActionGeometry(row.getByRole('button', { name: 'Descargar Contrato escaneado' })),
    ];
    expect(controls.map(({ width, height, right }) => width > 0 && height > 0 && right <= 412)).toEqual([true, true, true]);
  });

  test('keeps sent contract parameters locked at 412px', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:display', '@role:admin', '@viewport:compact'],
  }, async ({ page }) => {
    await seedAdmin(page);
    await mockApi(page, proposalHandler({ status: 'sent' }));

    await openDocumentsFromCompactPanel(page);
    await expect(page.getByRole('button', { name: 'Editar parámetros' })).toBeDisabled();
  });

  test('keeps contract Markdown copy actionable for sent proposals at 412px', {
    tag: ['@flow:admin-proposal-document-markdown', '@outcome:success', '@role:admin', '@viewport:compact'],
  }, async ({ page, context }) => {
    await seedAdmin(page);
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await mockApi(page, proposalHandler({ status: 'sent' }));

    await openDocumentsFromCompactPanel(page);
    const contractCopy = page.getByTestId('proposal-copy-contract');
    await contractCopy.click();
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toBe(markdownByEndpoint[`proposals/${PROPOSAL_ID}/contract/markdown/`]);
    await expect(contractCopy).toHaveAttribute('data-action-status', 'success');
  });
});
