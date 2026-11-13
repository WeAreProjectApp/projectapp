/**
 * Contract documents shared by Building with Us and Células.
 *
 * Bug caught: editing a program contract from Document Manager could save a
 * stale or partial document, discard an unsaved source after a failed save,
 * or leave the module showing a different contract revision.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { fillRichTextSource } from '../helpers/editorial.js';
import {
  ADMIN_BUILDING_ON_DEMAND_CONTRACT,
  ADMIN_BUILDING_WITH_US_CONTRACT,
  ADMIN_DOCUMENT_EDIT,
  ADMIN_PROGRAM_CONTRACT_EDIT,
} from '../helpers/flow-tags.js';
import {
  buildingOnDemandApiFixture,
  buildingOnDemandContractFixture,
  buildingOnDemandOverviewFixture,
} from '../helpers/building-on-demand-fixture.js';
import {
  buildingWithUsApiFixture,
  buildingWithUsContractFixture,
  buildingWithUsOverviewFixture,
} from '../helpers/building-with-us-fixture.js';

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const contractVariants = [
  {
    label: 'Building with Us',
    variant: 'building_with_us',
    documentId: 731,
    documentTitle: 'Contrato Building with Us',
    modulePath: '/es-co/panel/building-with-us',
    moduleContractPath: '/es-co/panel/building-with-us?tab=contract',
    moduleTab: (page) => page.getByTestId('building-with-us-tab-contract'),
    moduleLink: (page) => page.getByTestId('building-with-us-mirror-link'),
    moduleVersion: (page) => page.getByTestId('building-with-us-contract-version'),
    moduleBody: (page) => page.getByTestId('building-with-us-contract-body'),
    contractApiPath: 'building-with-us/admin/contract/',
    contractPdfApiPath: 'building-with-us/admin/contract/pdf/',
    tags: ADMIN_BUILDING_WITH_US_CONTRACT,
    initialMarkdown: '# Contrato Building with Us\n\nAporte inicial verificable.',
  },
  {
    label: 'Células',
    variant: 'building_on_demand',
    documentId: 732,
    documentTitle: 'Contrato de célula Scrum',
    modulePath: '/es-co/panel/cells',
    moduleContractPath: '/es-co/panel/cells?tab=contract',
    moduleTab: (page) => page.getByRole('tab', { name: 'Contrato', exact: true }),
    moduleLink: (page) => page.getByTestId('building-on-demand-admin-mirror-link'),
    moduleVersion: (page) => page.getByTestId('building-on-demand-admin-contract-version'),
    moduleBody: (page) => page.getByTestId('building-on-demand-admin-contract-body'),
    contractApiPath: 'building-on-demand/admin/contract/',
    contractPdfApiPath: 'building-on-demand/admin/contract/pdf/',
    tags: ADMIN_BUILDING_ON_DEMAND_CONTRACT,
    initialMarkdown: '# Contrato de célula Scrum\n\nBolsa mensual de horas.',
  },
];

function createState(contract) {
  return {
    saveMode: 'success',
    requestPayload: null,
    document: {
      id: contract.documentId,
      title: contract.documentTitle,
      slug: contract.variant,
      status: 'draft',
      folder: 701,
      folder_name: 'Contratos',
      is_client_visible: false,
      content_markdown: contract.initialMarkdown,
      text_formats: { '/content_markdown': 'markdown_html_v1' },
      template_style: 'professional',
      include_portada: true,
      include_subportada: true,
      include_contraportada: true,
      is_contract_mirror: true,
      contract_variant: contract.variant,
      content_editable: true,
      contract_version: 21,
      contract_synced_at: '2026-11-12T10:00:00Z',
      etag: `${contract.variant}-v21`,
      active_states: [],
      notes: [],
    },
  };
}

function mirrorFor(state) {
  return {
    status: 'synchronized',
    document_id: state.document.id,
    title: state.document.title,
    folder_path: 'ProjectApp › Contratos',
    version: state.document.contract_version,
    last_synced_at: state.document.contract_synced_at,
  };
}

function moduleContract(contract, state) {
  const fixture = contract.variant === 'building_with_us'
    ? buildingWithUsContractFixture()
    : buildingOnDemandContractFixture();
  return {
    ...fixture,
    version: state.document.contract_version,
    etag: state.document.etag,
    change_note: state.document.change_note || fixture.change_note,
    markdown: state.document.content_markdown,
    mirror: mirrorFor(state),
  };
}

function moduleOverview(contract, state) {
  const fixture = contract.variant === 'building_with_us'
    ? buildingWithUsOverviewFixture()
    : buildingOnDemandOverviewFixture();
  return {
    ...fixture,
    contract: {
      ...fixture.contract,
      version: state.document.contract_version,
      mirror: mirrorFor(state),
    },
  };
}

function contractPdf(contract, route) {
  const inline = new URL(route.request().url()).searchParams.get('inline') === '1';
  const filename = contract.variant === 'building_with_us'
    ? 'building-with-us-contract.pdf'
    : 'building-on-demand-contract.pdf';
  return {
    status: 200,
    contentType: 'application/pdf',
    headers: { 'Content-Disposition': `${inline ? 'inline' : 'attachment'}; filename="${filename}"` },
    body: '%PDF-1.4 shared module contract\n%%EOF',
  };
}

async function installContractApi(page, contract, state) {
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'proposals/' || apiPath === 'proposals/alerts/') return json([]);
    if (apiPath === 'proposals/dashboard/') return json({ total: 0, by_status: {} });
    if (apiPath === contract.contractPdfApiPath) return contractPdf(contract, route);
    if (apiPath === contract.contractApiPath) return json(moduleContract(contract, state));
    if (apiPath === (contract.variant === 'building_with_us' ? 'building-with-us/admin/' : 'building-on-demand/admin/')) {
      return json(moduleOverview(contract, state));
    }
    if (apiPath === `documents/${contract.documentId}/detail/`) return json(state.document);
    if (apiPath === `documents/${contract.documentId}/update/` && method === 'PATCH') {
      state.requestPayload = route.request().postDataJSON();
      if (state.saveMode === 'conflict') return json({ code: 'STALE_VERSION', detail: 'La revisión cambió.' }, 409);
      if (state.saveMode === 'unavailable') return json({ code: 'UNAVAILABLE', detail: 'No se pudo guardar.' }, 503);
      state.document = {
        ...state.document,
        content_markdown: state.requestPayload.content_markdown,
        text_formats: state.requestPayload.text_formats,
        template_style: state.requestPayload.template_style,
        include_portada: state.requestPayload.include_portada,
        include_subportada: state.requestPayload.include_subportada,
        include_contraportada: state.requestPayload.include_contraportada,
        change_note: state.requestPayload.change_note,
        contract_version: 22,
        contract_synced_at: '2026-11-12T11:00:00Z',
        etag: `${contract.variant}-v22`,
      };
      return json(state.document);
    }
    if (apiPath === `documents/${contract.documentId}/pdf/`) return contractPdf(contract, route);
    if (
      apiPath === `documents/${contract.documentId}/communications/`
      || apiPath === `documents/${contract.documentId}/email-usage/`
    ) return json({ count: 0, results: [] });
    if (
      apiPath === 'document-folders/'
      || apiPath === 'document-tags/'
      || apiPath === 'document-states/'
      || apiPath === 'document-state-groups/'
      || apiPath === 'accounting/projects/'
    ) return json([]);
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    return contract.variant === 'building_with_us'
      ? buildingWithUsApiFixture({ apiPath, method, route })
      : buildingOnDemandApiFixture({ apiPath, method, route });
  });
}

async function openModuleContract(page, contract) {
  // quality: allow-deep-link (the module page is setup; the contract is reached by its visible tab and mirror link)
  await page.goto(contract.modulePath, { waitUntil: 'domcontentloaded' });
  await contract.moduleTab(page).click();
  await expect(page).toHaveURL(new RegExp(`${contract.moduleContractPath.replace(/[?]/g, '\\?')}$`));
}

async function openDocumentEditor(page, contract) {
  await openModuleContract(page, contract);
  await expect(contract.moduleLink(page)).toHaveAttribute('href', `/es-co/panel/documents/${contract.documentId}/edit`);
  await contract.moduleLink(page).click();
  await expect(page).toHaveURL(new RegExp(`/es-co/panel/documents/${contract.documentId}/edit$`));
  await expect(page.getByTestId('doc-markdown-editor-panel')).toBeVisible();
}

async function fillContractSource(page, content) {
  const editor = page.getByTestId('doc-markdown-editor');
  return fillRichTextSource(editor, content);
}

test.describe('Admin shared module contract documents', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-shared-module-contract',
      userAuth: { id: 731, role: 'admin', is_staff: true, is_superuser: true },
    });
  });

  for (const contract of contractVariants) {
    test(`saves ${contract.label} contract source through Document Manager`, {
      tag: [...contract.tags, ...ADMIN_DOCUMENT_EDIT, ...ADMIN_PROGRAM_CONTRACT_EDIT, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const state = createState(contract);
      const revisedSource = `${contract.initialMarkdown}\n\n## Revisión aprobada\n\nCláusula sincronizada desde el Gestor.`;
      await installContractApi(page, contract, state);
      await openDocumentEditor(page, contract);
      await fillContractSource(page, revisedSource);
      await page.getByTestId('doc-contract-change-note').fill('Aclara los hitos acordados.');
      const requestPromise = page.waitForRequest((request) => (
        request.url().includes(`/api/documents/${contract.documentId}/update/`) && request.method() === 'PATCH'
      ));
      await page.getByTestId('doc-save').click();
      const request = await requestPromise;
      const payload = request.postDataJSON();

      expect(payload).toEqual({
        content_markdown: revisedSource,
        if_match: `${contract.variant}-v21`,
        change_note: 'Aclara los hitos acordados.',
        include_portada: true,
        include_subportada: true,
        include_contraportada: true,
        template_style: 'professional',
        text_formats: { '/content_markdown': 'markdown_html_v1' },
      });
      await expect(page.getByTestId('doc-unsaved-notice')).toHaveCount(0);
      await page.getByTestId('doc-module-contract-link').click();
      await expect(contract.moduleVersion(page)).toContainText('Versión 22');
      await expect(contract.moduleBody(page)).toContainText('Cláusula sincronizada desde el Gestor.');
    });

    test(`requires a change reason for ${contract.label} contract source`, {
      tag: [...contract.tags, ...ADMIN_DOCUMENT_EDIT, ...ADMIN_PROGRAM_CONTRACT_EDIT, '@role:admin', '@outcome:error'],
    }, async ({ page }) => {
      const state = createState(contract);
      await installContractApi(page, contract, state);
      await openDocumentEditor(page, contract);

      await fillContractSource(page, `${contract.initialMarkdown}\n\nCambio pendiente.`);

      await expect(page.getByTestId('doc-save')).toBeDisabled();
    });

    test(`preserves ${contract.label} source after a stale revision conflict`, {
      tag: [...contract.tags, ...ADMIN_DOCUMENT_EDIT, ...ADMIN_PROGRAM_CONTRACT_EDIT, '@role:admin', '@outcome:failure'],
    }, async ({ page }) => {
      const state = createState(contract);
      state.saveMode = 'conflict';
      const revisedSource = `${contract.initialMarkdown}\n\nCambio en conflicto.`;
      await installContractApi(page, contract, state);
      await openDocumentEditor(page, contract);

      const source = await fillContractSource(page, revisedSource);
      await page.getByTestId('doc-contract-change-note').fill('Ajuste pendiente de conciliación.');
      await page.getByTestId('doc-save').click();

      await expect(page.getByTestId('doc-contract-conflict')).toContainText('Tu texto sigue aquí sin guardar.');
      await expect(source).toHaveValue(revisedSource);
      expect(state.document.contract_version).toBe(21);
    });

    test(`preserves ${contract.label} source when the contract service is unavailable`, {
      tag: [...contract.tags, ...ADMIN_DOCUMENT_EDIT, ...ADMIN_PROGRAM_CONTRACT_EDIT, '@role:admin', '@outcome:failure'],
    }, async ({ page }) => {
      const state = createState(contract);
      state.saveMode = 'unavailable';
      const revisedSource = `${contract.initialMarkdown}\n\nCambio pendiente por reintentar.`;
      await installContractApi(page, contract, state);
      await openDocumentEditor(page, contract);

      const source = await fillContractSource(page, revisedSource);
      await page.getByTestId('doc-contract-change-note').fill('Ajuste que debe conservarse.');
      const responsePromise = page.waitForResponse((response) => (
        response.url().includes(`/api/documents/${contract.documentId}/update/`) && response.request().method() === 'PATCH'
      ));
      await page.getByTestId('doc-save').click();

      expect((await responsePromise).status()).toBe(503);
      await expect(source).toHaveValue(revisedSource);
      await expect(page.getByTestId('doc-contract-conflict')).toHaveCount(0);
      expect(state.document.contract_version).toBe(21);
    });
  }
});
