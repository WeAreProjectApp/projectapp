/**
 * E2E tests for admin proposal section editing via FORM mode.
 *
 * Covers: editing each major section type using structured form fields,
 * verifying the save payload contains correct content_json structure,
 * and that data persists correctly via the API.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_PROPOSAL_SECTION_EDIT_FORM,
} from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;
const userId = 7100;

function _buildSection(id, type, title, order, contentJson = {}) {
  return {
    id,
    section_type: type,
    title,
    order,
    is_enabled: true,
    is_wide_panel: type === 'functional_requirements',
    content_json: contentJson,
  };
}

const mockProposal = {
  id: PROPOSAL_ID,
  uuid: '11111111-1111-1111-1111-111111111111',
  title: 'E2E Section Form Test',
  client_name: 'Form Client',
  client_email: 'form@test.com',
  language: 'es',
  status: 'draft',
  total_investment: '5000000',
  currency: 'COP',
  view_count: 0,
  sent_at: null,
  expires_at: null,
  sections: [
    _buildSection(101, 'greeting', 'Greeting', 0, { clientName: '', inspirationalQuote: '' }),
    _buildSection(102, 'executive_summary', '🧾 Resumen ejecutivo', 1, {
      index: '1', title: 'Resumen ejecutivo', paragraphs: [], highlightsTitle: 'Incluye', highlights: [],
    }),
    _buildSection(103, 'context_diagnostic', '🧩 Contexto', 2, {
      index: '2', title: 'Contexto', paragraphs: [], issuesTitle: 'Desafíos', issues: [],
      opportunityTitle: 'Oportunidad', opportunity: '',
    }),
    _buildSection(104, 'conversion_strategy', '🚀 Estrategia', 3, {
      index: '3', title: 'Estrategia', intro: '', steps: [], resultTitle: '', result: '',
    }),
    _buildSection(105, 'design_ux', '🎨 Diseño UX', 4, {
      index: '4', title: 'Diseño UX', paragraphs: [], focusTitle: '', focusItems: [],
      objectiveTitle: '', objective: '',
    }),
    _buildSection(106, 'creative_support', '🤝 Acompañamiento', 5, {
      index: '5', title: 'Acompañamiento', paragraphs: [], includesTitle: '', includes: [], closing: '',
    }),
    _buildSection(107, 'development_stages', '📌 Etapas', 6, { stages: [] }),
    _buildSection(108, 'functional_requirements', '🧩 Requerimientos', 7, {
      index: '7', title: 'Requerimientos', intro: '',
      groups: [{ id: 'views', icon: '🖥️', title: 'Vistas', description: '', items: [] }],
      additionalModules: [],
    }),
    _buildSection(109, 'timeline', '⏳ Cronograma', 8, {
      index: '8', title: 'Cronograma', introText: '', totalDuration: '', phases: [],
    }),
    _buildSection(110, 'investment', '💰 Inversión', 9, {
      index: '9', title: 'Inversión', introText: '', totalInvestment: '', currency: 'COP',
      whatsIncluded: [], paymentOptions: [], paymentMethods: [], valueReasons: [],
    }),
    _buildSection(111, 'final_note', '📝 Nota Final', 10, {
      index: '10', title: 'Nota Final', message: '', personalNote: '', teamName: '', teamRole: '',
      contactEmail: '', commitmentBadges: [], validityMessage: '', thankYouMessage: '',
    }),
    _buildSection(112, 'next_steps', '✅ Próximos pasos', 11, {
      index: '11', title: 'Próximos pasos', introMessage: '', steps: [], ctaMessage: '',
      primaryCTA: { text: '', link: '' }, secondaryCTA: { text: '', link: '' },
      contactMethods: [], validityMessage: '', thankYouMessage: '',
    }),
  ],
  requirement_groups: [],
};

function buildMockHandler(capturedUpdates) {
  return async ({ route, apiPath }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
      };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockProposal),
      };
    }
    const sectionMatch = apiPath.match(/^proposals\/sections\/(\d+)\/update\/$/);
    if (sectionMatch) {
      const sectionId = parseInt(sectionMatch[1]);
      const body = route.request().postDataJSON();
      if (capturedUpdates) {
        capturedUpdates.push({ sectionId, body });
      }
      const section = mockProposal.sections.find(s => s.id === sectionId);
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...section, ...body, content_json: body.content_json || section?.content_json || {} }),
      };
    }
    return null;
  };
}

/**
 * Helper: navigate to edit page, switch to Secciones tab, expand a section,
 * and return the section editor container.
 */
async function openSectionEditor(page, capturedUpdates, sectionType) {
  await mockApi(page, buildMockHandler(capturedUpdates));
  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

  // Switch to Secciones tab
  await selectProposalDestination(page, 'proposal', 'sections');

  // Find section header and expand it
  await page.getByTestId(`section-header-${sectionType}`).click();

  await page.getByTestId('section-editor').waitFor({ state: 'visible' });
}

test.describe('Proposal Section Edit — Form Mode', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: userId, role: 'admin', is_staff: true },
    });
  });

  test('loads proposal edit page with sections tab showing all 12 sections', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler(null));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    // Switch to sections tab
    await selectProposalDestination(page, 'proposal', 'sections');

    // Verify all section titles are visible
    await expect(page.getByText('Greeting', { exact: true })).toBeVisible();
    await expect(page.getByText('🧾 Resumen ejecutivo')).toBeVisible();
    await expect(page.getByText('🧩 Contexto')).toBeVisible();
  });

  test('greeting: fills clientName and inspirationalQuote, saves correct payload', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'greeting');

    // Fill greeting fields — find the section editor area
    const editor = page.getByTestId('section-editor');

    await editor.getByLabel('Nombre del cliente').fill('María García');
    await editor.getByLabel('Frase inspiracional').fill('Design is how it works.');

    // Click save
    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    // Verify captured payload
    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.sectionId).toBe(101);
    expect(last.body.content_json.clientName).toBe('María García');
    expect(last.body.content_json.inspirationalQuote).toBe('Design is how it works.');
    expect(last.body.content_json._editMode).toBe('form');
  });

  test('executive_summary: fills paragraphs and highlights, saves arrays', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'executive_summary');

    const editor = page.getByTestId('section-editor');

    await editor.getByLabel('Párrafos').fill('Primer párrafo.\nSegundo párrafo.');
    await editor.getByLabel('Highlights / Incluye').fill('Diseño personalizado\nDesarrollo responsivo');

    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.body.content_json._editMode).toBe('form');
    expect(last.body.content_json.paragraphs).toEqual(['Primer párrafo.', 'Segundo párrafo.']);
    expect(last.body.content_json.highlights).toEqual(['Diseño personalizado', 'Desarrollo responsivo']);
  });

  test('context_diagnostic: fills issues and opportunity, saves correctly', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'context_diagnostic');

    const editor = page.getByTestId('section-editor');

    await editor.getByLabel('Párrafos').fill('Contexto del proyecto.');
    await editor.getByRole('textbox', { name: /^Problemas/ }).fill('Falta de web\nSin presencia digital');
    await editor.getByRole('textbox', { name: 'Oportunidad', exact: true }).fill('Crear plataforma de confianza.');

    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.body.content_json.paragraphs).toEqual(['Contexto del proyecto.']);
    expect(last.body.content_json.issues).toEqual(['Falta de web', 'Sin presencia digital']);
    expect(last.body.content_json.opportunity).toBe('Crear plataforma de confianza.');
  });

  test('save button auto-collapses the section editor on success', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    await openSectionEditor(page, [], 'greeting');

    const editor = page.getByTestId('section-editor');
    await editor.getByRole('button', { name: 'Guardar Sección' }).click();

    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);
  });

  test('save failure keeps the editor open and shows an error notification', {
    tag: ['@outcome:error', ...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const baseHandler = buildMockHandler(null);
    await mockApi(page, (ctx) => {
      if (/^proposals\/sections\/\d+\/update\/$/.test(ctx.apiPath)) {
        return {
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'La sección no pudo guardarse.' }),
        };
      }
      return baseHandler(ctx);
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await selectProposalDestination(page, 'proposal', 'sections');
    await page.getByTestId('section-header-greeting').click();
    const editor = page.getByTestId('section-editor');
    await editor.waitFor({ state: 'visible' });

    await editor.getByRole('button', { name: 'Guardar Sección' }).click();

    // The failure surfaces as a panel notification and the editor stays open.
    await expect(page.getByText('La sección no pudo guardarse.')).toBeVisible();
    await expect(editor).toBeVisible();
  });

  test('section title change is included in save payload', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'greeting');

    const editor = page.getByTestId('section-editor');

    await editor.getByLabel('Título de la sección').fill('Custom Greeting Title');

    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.body.title).toBe('Custom Greeting Title');
  });

  test('greeting with empty fields saves empty strings', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'greeting');

    const editor = page.getByTestId('section-editor');

    // Leave all fields empty, just click save
    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.body.content_json._editMode).toBe('form');
    expect(last.body.content_json).not.toHaveProperty('rawText');
  });

  test('executive_summary with empty textareas saves empty arrays', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'executive_summary');

    const editor = page.getByTestId('section-editor');
    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.body.content_json.paragraphs).toEqual([]);
    expect(last.body.content_json.highlights).toEqual([]);
  });

  test('investment: save blocked when optional module has no price', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    // Build a proposal with an investment section that has an optional module without price
    const proposalWithInvestment = JSON.parse(JSON.stringify(mockProposal));
    proposalWithInvestment.sections[9].content_json = {
      index: '9', title: 'Inversión', introText: '', totalInvestment: '5000000', currency: 'COP',
      modules: [
        { id: 'mod1', name: 'Módulo Base', price: 3000000, included: true, is_required: true },
        { id: 'mod2', name: 'Módulo Premium', price: 0, included: true, is_required: false },
      ],
      whatsIncluded: [], paymentOptions: [], paymentMethods: [], valueReasons: [],
    };

    const captured = [];
    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return { status: 200, contentType: 'application/json', body: JSON.stringify(proposalWithInvestment) };
      const sectionMatch = apiPath.match(/^proposals\/sections\/(\d+)\/update\/$/);
      if (sectionMatch) {
        captured.push({ sectionId: parseInt(sectionMatch[1]), body: route.request().postDataJSON() });
        const section = proposalWithInvestment.sections.find(s => s.id === parseInt(sectionMatch[1]));
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...section }) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await selectProposalDestination(page, 'proposal', 'sections');

    await page.getByTestId('section-header-investment').click();
    await page.getByTestId('section-editor').waitFor({ state: 'visible' });

    const editor = page.getByTestId('section-editor');
    await editor.getByRole('button', { name: 'Guardar Sección' }).click();

    // Save should be blocked — validation error shown
    await expect(editor.getByText('No se puede guardar')).toBeVisible();
    await expect(editor.getByText('Módulo Premium')).toBeVisible();

    // No API call should have been made
    expect(captured.length).toBe(0);
  });

  test('commercial_conditions: the section editor owns the texts and hands the pricing back untouched', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const proposalWithConditions = JSON.parse(JSON.stringify(mockProposal));
    proposalWithConditions.sections.push(_buildSection(113, 'commercial_conditions', '📋 Condiciones comerciales', 12, {
      index: '12', title: 'Condiciones comerciales', packagesTitle: 'Paquetes de horas',
      packagesIntro: '', hourlyRate: 30000, currency: 'COP',
      hourPackagesMode: 'manual', manualHourlyRate: 45000, manualCurrency: 'COP',
      manualPackageRates: [{ packageId: 7, hourlyRate: 52000 }],
      packages: [{ id: 7, name: 'Ágil', hours: 20, discountPercent: 10, note: '', hourlyRate: 35000 }],
      effortBadge: '', scopeTitle: 'Alcance', scopeParagraphs: ['p1'],
    }));

    const captured = [];
    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return { status: 200, contentType: 'application/json', body: JSON.stringify(proposalWithConditions) };
      const sectionMatch = apiPath.match(/^proposals\/sections\/(\d+)\/update\/$/);
      if (sectionMatch) {
        captured.push({ sectionId: parseInt(sectionMatch[1]), body: route.request().postDataJSON() });
        const section = proposalWithConditions.sections.find(s => s.id === parseInt(sectionMatch[1]));
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...section }) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await selectProposalDestination(page, 'proposal', 'sections');

    await page.getByTestId('section-header-commercial_conditions').click();
    await page.getByTestId('section-editor').waitFor({ state: 'visible' });
    const editor = page.getByTestId('section-editor');

    // The per-section form is a lazily-loaded chunk, so wait for a field that
    // must be present before asserting other fields are absent — otherwise the
    // toHaveCount(0) checks below can pass simply because the form has not
    // rendered yet, and the fill() that follows races the chunk.
    await expect(editor.getByLabel('Título de los paquetes')).toBeVisible();

    // Rates and packages moved to the «Tarifa por hora» tab; this editor only
    // points at them.
    await expect(editor.getByTestId('hour-rate-tab-hint')).toContainText('Tarifa por hora');
    await expect(editor.getByTestId('hour-packages-mode-manual')).toHaveCount(0);
    await expect(editor.getByTestId('apply-base-rate-all')).toHaveCount(0);
    await expect(editor.getByLabel('Tarifa base por hora')).toHaveCount(0);

    await editor.getByLabel('Título de los paquetes').fill('Paquetes editados');
    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    await expect(editor).toHaveCount(0);

    // Saving the texts must not disturb the pricing this form no longer edits.
    expect(captured).toHaveLength(1);
    const cj = captured[0].body.content_json;
    expect(cj.packagesTitle).toBe('Paquetes editados');
    expect(cj.hourPackagesMode).toBe('manual');
    expect(cj.manualHourlyRate).toBe(45000);
    expect(cj.manualCurrency).toBe('COP');
    expect(cj.manualPackageRates).toEqual([{ packageId: 7, hourlyRate: 52000 }]);
    expect(cj.packages[0]).toMatchObject({ id: 7, name: 'Ágil', hours: 20, hourlyRate: 35000 });
    expect(cj._editMode).toBe('form');
  });

  test('form mode payload never includes rawText', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'context_diagnostic');

    const editor = page.getByTestId('section-editor');
    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.body.content_json._editMode).toBe('form');
    expect(last.body.content_json).not.toHaveProperty('rawText');
  });

  test('conversion_strategy: fills intro and result, saves correct payload', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'conversion_strategy');

    const editor = page.getByTestId('section-editor');

    await editor.getByLabel('Introducción').fill('Nuestra estrategia digital.', { timeout: 5000 });
    await editor.getByLabel('Resultado esperado').fill('Incremento del 30% en conversiones.', { timeout: 5000 });

    await editor.getByRole('button', { name: 'Guardar Sección' }).click({ timeout: 5000 });
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.sectionId).toBe(104);
    expect(last.body.content_json.intro).toBe('Nuestra estrategia digital.');
    expect(last.body.content_json.result).toBe('Incremento del 30% en conversiones.');
    expect(last.body.content_json._editMode).toBe('form');
  });

  test('timeline: fills introText and totalDuration, saves correct payload', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'timeline');

    const editor = page.getByTestId('section-editor');

    await editor.getByLabel('Texto introductorio').fill('Fases del proyecto.');
    await editor.getByLabel('Duración total').fill('3 meses');

    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.sectionId).toBe(109);
    expect(last.body.content_json.introText).toBe('Fases del proyecto.');
    expect(last.body.content_json.totalDuration).toBe('3 meses');
    expect(last.body.content_json._editMode).toBe('form');
  });

  test('investment: fills introText and totalInvestment, saves correct payload', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'investment');

    const editor = page.getByTestId('section-editor');

    await editor.getByLabel('Texto introductorio').fill('Tu inversión incluye todo el desarrollo.', { timeout: 5000 });
    // Note: totalInvestment is displayed as read-only info box in the investment section editor
    // (editable only from the General tab), so we only fill introText here.

    await editor.getByRole('button', { name: 'Guardar Sección' }).click({ timeout: 5000 });
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.sectionId).toBe(110);
    expect(last.body.content_json.introText).toBe('Tu inversión incluye todo el desarrollo.');
    expect(last.body.content_json._editMode).toBe('form');
  });

  test('design_ux: fills paragraphs and focusItems, saves correct payload', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_FORM, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'design_ux');

    const editor = page.getByTestId('section-editor');

    await editor.getByLabel('Párrafos').fill('Diseño centrado en el usuario.', { timeout: 5000 });
    await editor.getByLabel('Items de enfoque').fill('Usabilidad\nAccesibilidad', { timeout: 5000 });

    await editor.getByRole('button', { name: 'Guardar Sección' }).click({ timeout: 5000 });
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.sectionId).toBe(105);
    expect(last.body.content_json.paragraphs).toEqual(['Diseño centrado en el usuario.']);
    expect(last.body.content_json.focusItems).toEqual(['Usabilidad', 'Accesibilidad']);
    expect(last.body.content_json._editMode).toBe('form');
  });
});
