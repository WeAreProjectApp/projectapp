/**
 * E2E tests for admin proposal section editing via PASTE CONTENT mode.
 *
 * Covers: toggling paste mode, typing/pasting text into the paste textarea,
 * verifying _editMode and rawText in the save payload, toggling back to form,
 * and edge cases like empty paste text.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_PROPOSAL_SECTION_EDIT_PASTE,
} from '../helpers/flow-tags.js';

const PROPOSAL_ID = 2;
const userId = 7200;

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
  uuid: '22222222-2222-2222-2222-222222222222',
  title: 'E2E Paste Content Test',
  client_name: 'Paste Client',
  client_email: 'paste@test.com',
  language: 'es',
  status: 'draft',
  total_investment: '3000000',
  currency: 'COP',
  view_count: 0,
  sent_at: null,
  expires_at: null,
  sections: [
    _buildSection(201, 'greeting', 'Greeting', 0, { clientName: 'Test Client', inspirationalQuote: 'Think different.' }),
    _buildSection(202, 'executive_summary', '🧾 Resumen ejecutivo', 1, {
      index: '1', title: 'Resumen', paragraphs: ['Párrafo uno.'], highlightsTitle: 'Incluye', highlights: ['Diseño'],
    }),
    _buildSection(203, 'context_diagnostic', '🧩 Contexto', 2, {
      index: '2', title: 'Contexto', paragraphs: ['Párrafo.'], issuesTitle: 'Desafíos', issues: ['Problema 1'],
      opportunityTitle: 'Oportunidad', opportunity: 'Oportunidad test.',
    }),
    _buildSection(204, 'conversion_strategy', '🚀 Estrategia', 3, {
      index: '3', title: 'Estrategia', intro: 'Intro.', steps: [], resultTitle: '', result: '',
    }),
    _buildSection(205, 'design_ux', '🎨 Diseño UX', 4, {
      index: '4', title: 'Diseño', paragraphs: [], focusTitle: '', focusItems: [],
      objectiveTitle: '', objective: '',
    }),
    _buildSection(206, 'creative_support', '🤝 Acompañamiento', 5, {
      index: '5', title: 'Acompañamiento', paragraphs: [], includesTitle: '', includes: [], closing: '',
    }),
    _buildSection(207, 'development_stages', '📌 Etapas', 6, { stages: [] }),
    _buildSection(208, 'functional_requirements', '🧩 Requerimientos', 7, {
      index: '7', title: 'Requerimientos', intro: '',
      groups: [{ id: 'views', icon: '🖥️', title: 'Vistas', description: '', items: [] }],
      additionalModules: [],
    }),
    _buildSection(209, 'timeline', '⏳ Cronograma', 8, {
      index: '8', title: 'Cronograma', introText: '', totalDuration: '', phases: [],
    }),
    _buildSection(210, 'investment', '💰 Inversión', 9, {
      index: '9', title: 'Inversión', introText: '', totalInvestment: '', currency: 'COP',
      whatsIncluded: [], paymentOptions: [], paymentMethods: [], valueReasons: [],
    }),
    _buildSection(211, 'final_note', '📝 Nota Final', 10, {
      index: '10', title: 'Nota Final', message: '', personalNote: '', teamName: '', teamRole: '',
      contactEmail: '', commitmentBadges: [], validityMessage: '', thankYouMessage: '',
    }),
    _buildSection(212, 'next_steps', '✅ Próximos pasos', 11, {
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
        body: JSON.stringify({
          ...section,
          ...body,
          content_json: body.content_json || section?.content_json || {},
        }),
      };
    }
    return null;
  };
}

/**
 * Helper: navigate to edit page, switch to Secciones tab, expand a section.
 */
async function openSectionEditor(page, capturedUpdates, sectionType) {
  await mockApi(page, buildMockHandler(capturedUpdates));
  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
  await page.waitForLoadState('domcontentloaded');

  await selectProposalDestination(page, 'proposal', 'sections');

  await page.getByTestId(`section-header-${sectionType}`).click();
  await page.getByTestId('section-editor').waitFor({ state: 'visible' });
}

test.describe('Proposal Section Edit — Paste Content Mode', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: userId, role: 'admin', is_staff: true },
    });
  });

  test('toggle to paste mode shows textarea with pre-filled content', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    await openSectionEditor(page, [], 'greeting');

    const editor = page.getByTestId('section-editor');

    // Click "Pegar contenido" button to switch to paste mode
    await editor.getByRole('button', { name: 'Pegar contenido' }).click();

    // A large textarea should appear
    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();

    // It should be pre-filled with formToReadableText output
    const value = await pasteTextarea.inputValue();
    expect(value).toContain('Test Client');
  });

  test('executive_summary paste: saves _editMode paste and rawText in payload', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'executive_summary');

    const editor = page.getByTestId('section-editor');

    // Switch to paste mode
    await editor.getByRole('button', { name: 'Pegar contenido' }).click();

    // Type custom content in the paste textarea
    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();
    await pasteTextarea.fill('Custom pasted executive summary content.\n\nWith multiple paragraphs.');

    // Save
    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    // Verify payload
    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.sectionId).toBe(202);
    expect(last.body.content_json._editMode).toBe('paste');
    expect(last.body.content_json.rawText).toBe('Custom pasted executive summary content.\n\nWith multiple paragraphs.');
  });

  test('context_diagnostic paste: saves rawText alongside structured data', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'context_diagnostic');

    const editor = page.getByTestId('section-editor');

    // Switch to paste mode
    await editor.getByRole('button', { name: 'Pegar contenido' }).click();

    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();
    await pasteTextarea.fill('Contexto pegado directamente.');

    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.body.content_json._editMode).toBe('paste');
    expect(last.body.content_json.rawText).toBe('Contexto pegado directamente.');
    // Structured data is still present (from the original form state)
    expect(last.body.content_json).toHaveProperty('paragraphs');
  });

  test('a failed paste-mode save shows the first field error and keeps the editor open', {
    // Bug this catches: a save failure that still collapses/discards the open
    // editor, losing the unsaved paste content the admin just typed.
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      if (apiPath === 'proposals/sections/202/update/' && method === 'PATCH') {
        return {
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ rawText: ['El contenido pegado supera el límite permitido.'] }),
        };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await page.waitForLoadState('domcontentloaded');
    await selectProposalDestination(page, 'proposal', 'sections');
    await page.getByTestId('section-header-executive_summary').click();

    const editor = page.getByTestId('section-editor');
    await editor.waitFor({ state: 'visible' });

    await editor.getByRole('button', { name: 'Pegar contenido' }).click();
    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();
    await pasteTextarea.fill('Contenido pegado que fallará al guardar.');

    await editor.getByRole('button', { name: 'Guardar Sección' }).click();

    // Toast shows the FIRST field error, not a generic fallback string.
    const toast = page.getByRole('alert').filter({ hasText: 'El contenido pegado supera el límite permitido.' });
    await expect(toast).toBeVisible({ timeout: 10_000 });
    // The editor stays mounted — the failed save did not auto-collapse it.
    await expect(editor).toBeVisible();
    await expect(pasteTextarea).toHaveValue('Contenido pegado que fallará al guardar.');
  });

  test('toggle back to form mode: saves _editMode form without rawText', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'executive_summary');

    const editor = page.getByTestId('section-editor');

    // Switch to paste, then back to form
    await editor.getByRole('button', { name: 'Pegar contenido' }).click();
    await expect(editor.getByTestId('paste-textarea')).toBeVisible();
    await editor.getByRole('button', { name: 'Formulario' }).click();
    await expect(editor.getByTestId('paste-textarea')).not.toBeVisible();

    // Save in form mode
    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.body.content_json._editMode).toBe('form');
    expect(last.body.content_json).not.toHaveProperty('rawText');
  });

  test('empty paste text saves rawText as empty string', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'design_ux');

    const editor = page.getByTestId('section-editor');

    // Switch to paste mode
    await editor.getByRole('button', { name: 'Pegar contenido' }).click();

    // Clear the textarea completely
    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();
    await pasteTextarea.fill('');

    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.body.content_json._editMode).toBe('paste');
    expect(last.body.content_json.rawText).toBe('');
  });

  test('paste mode toggle is available on greeting section', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    await openSectionEditor(page, [], 'greeting');

    const editor = page.getByTestId('section-editor');

    // hasPasteSupport is always true — both buttons should exist
    await expect(editor.getByRole('button', { name: 'Formulario' })).toBeVisible();
    await expect(editor.getByRole('button', { name: 'Pegar contenido' })).toBeVisible();
  });

  test('paste mode pre-fills from form data for executive_summary', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    await openSectionEditor(page, [], 'executive_summary');

    const editor = page.getByTestId('section-editor');

    // Toggle to paste
    await editor.getByRole('button', { name: 'Pegar contenido' }).click();

    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();
    const value = await pasteTextarea.inputValue();

    // Should contain data from the mockProposal section content_json
    expect(value).toContain('Párrafo uno.');
    expect(value).toContain('Incluye');
    expect(value).toContain('Diseño');
  });

  test('paste mode on context_diagnostic pre-fills issues as bullets', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    await openSectionEditor(page, [], 'context_diagnostic');

    const editor = page.getByTestId('section-editor');
    await editor.getByRole('button', { name: 'Pegar contenido' }).click();

    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();
    const value = await pasteTextarea.inputValue();

    expect(value).toContain('Desafíos');
    expect(value).toContain('- Problema 1');
    expect(value).toContain('Oportunidad test.');
  });

  test('paste textarea shows markdown instruction text', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    await openSectionEditor(page, [], 'executive_summary');

    const editor = page.getByTestId('section-editor');
    await editor.getByRole('button', { name: 'Pegar contenido' }).click();
    await expect(editor.getByTestId('paste-textarea')).toBeVisible();

    // Verify instructional text is visible
    await expect(editor.getByText('Puedes usar formato Markdown')).toBeVisible();
  });

  test('section saved in paste mode opens in paste mode on reopen', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    // Use a mock proposal where executive_summary was saved with _editMode: 'paste'
    const pasteProposal = JSON.parse(JSON.stringify(mockProposal));
    pasteProposal.sections[1].content_json = {
      ...pasteProposal.sections[1].content_json,
      _editMode: 'paste',
      rawText: 'Previously saved paste content.',
    };

    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(pasteProposal) };
      }
      const m = apiPath.match(/^proposals\/sections\/(\d+)\/update\/$/);
      if (m) {
        const section = pasteProposal.sections.find(s => s.id === parseInt(m[1]));
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...section, ...route.request().postDataJSON() }) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await page.waitForLoadState('domcontentloaded');
    await selectProposalDestination(page, 'proposal', 'sections');

    // Expand executive_summary section
    await page.getByTestId('section-header-executive_summary').click();
    await page.getByTestId('section-editor').waitFor({ state: 'visible' });

    const editor = page.getByTestId('section-editor');

    // The paste textarea should be visible immediately (no need to click "Pegar contenido")
    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();

    // And it should contain the previously saved rawText
    const value = await pasteTextarea.inputValue();
    expect(value).toBe('Previously saved paste content.');
  });

  test('section saved in form mode opens in form mode on reopen', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    // Default mockProposal sections have no _editMode (defaults to form)
    await openSectionEditor(page, [], 'executive_summary');

    const editor = page.getByTestId('section-editor');

    // The paste textarea should NOT be visible — we should see form fields
    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).not.toBeVisible();

    // Form textareas should be present (executive_summary has Párrafos field)
    await expect(editor.getByLabel('Párrafos')).toBeVisible();
  });

  test('conversion_strategy paste: saves rawText in payload', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await openSectionEditor(page, captured, 'conversion_strategy');

    const editor = page.getByTestId('section-editor');

    await editor.getByRole('button', { name: 'Pegar contenido' }).click();

    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();
    await pasteTextarea.fill('Estrategia de conversión pegada directamente.');

    await editor.getByRole('button', { name: 'Guardar Sección' }).click();
    // After successful save, the parent auto-collapses the section editor
    await expect(editor).toHaveCount(0);

    expect(captured.length).toBeGreaterThanOrEqual(1);
    const last = captured[captured.length - 1];
    expect(last.sectionId).toBe(204);
    expect(last.body.content_json._editMode).toBe('paste');
    expect(last.body.content_json.rawText).toBe('Estrategia de conversión pegada directamente.');
  });

  test('design_ux paste: pre-fills from form data', {
    tag: [...ADMIN_PROPOSAL_SECTION_EDIT_PASTE, '@role:admin'],
  }, async ({ page }) => {
    // Use a mock with filled design_ux content to verify pre-fill
    const filledProposal = JSON.parse(JSON.stringify(mockProposal));
    filledProposal.sections[4].content_json = {
      ...filledProposal.sections[4].content_json,
      paragraphs: ['Diseño centrado en el usuario.'],
      focusItems: ['Usabilidad', 'Accesibilidad'],
    };

    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(filledProposal) };
      }
      const m = apiPath.match(/^proposals\/sections\/(\d+)\/update\/$/);
      if (m) {
        const section = filledProposal.sections.find(s => s.id === parseInt(m[1]));
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...section, ...route.request().postDataJSON() }) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await page.waitForLoadState('domcontentloaded');
    await selectProposalDestination(page, 'proposal', 'sections');
    await page.getByText('🎨 Diseño UX').click();
    await page.getByTestId('section-editor').waitFor({ state: 'visible' });

    const editor = page.getByTestId('section-editor');
    await editor.getByRole('button', { name: 'Pegar contenido' }).click();

    const pasteTextarea = editor.getByTestId('paste-textarea');
    await expect(pasteTextarea).toBeVisible();
    const value = await pasteTextarea.inputValue();

    expect(value).toContain('Diseño centrado en el usuario.');
    expect(value).toContain('Usabilidad');
  });
});
