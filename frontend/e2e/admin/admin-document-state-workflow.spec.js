/**
 * E2E coverage for document state episodes, linked observations and filters.
 *
 * @flow:admin-document-state-workflow
 * @flow:admin-document-state-filters
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { fillRichTextSource } from '../helpers/editorial.js';
import {
  ADMIN_DOCUMENT_STATE_FILTERS,
  ADMIN_DOCUMENT_STATE_WORKFLOW,
} from '../helpers/flow-tags.js';

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const authCheck = json({ user: { username: 'admin', is_staff: true } });
const groups = [
  { id: 1, name: 'Ciclo', selection_mode: 'exclusive', order: 0, is_active: true, state_count: 4 },
  { id: 2, name: 'Señales', selection_mode: 'additive', order: 1, is_active: true, state_count: 2 },
];

function state(id, name, group, systemKey, color, order) {
  const owner = groups.find((item) => item.id === group);
  return {
    id,
    name,
    slug: name.toLowerCase().replaceAll(' ', '-'),
    color,
    system_key: systemKey,
    order,
    group,
    group_id: group,
    group_name: owner.name,
    group_mode: owner.selection_mode,
    group_order: owner.order,
    is_active: true,
    merged_into: null,
    incompatibility_ids: [],
    active_document_count: 0,
    historical_episode_count: 0,
  };
}

const states = [
  state(10, 'Borrador', 1, 'draft', 'gray', 0),
  state(11, 'Enviado', 1, 'sent', 'blue', 1),
  state(12, 'En revisión', 1, 'in_review', 'yellow', 2),
  state(13, 'Cerrado', 1, 'closed', 'emerald', 3),
  state(20, 'Solucionar bug', 2, 'needs_fix', 'red', 0),
  state(21, 'Bug atendido', 2, 'bug_resolved', 'emerald', 1),
];

function episode(id, stateId, durationSeconds, overrides = {}) {
  return {
    id,
    document: 1,
    state: states.find((item) => item.id === stateId),
    opened_at: '2026-08-20T15:00:00Z',
    closed_at: null,
    opening_time_known: true,
    duration_seconds: durationSeconds,
    opened_by: 8700,
    opened_by_name: 'Admin QA',
    closed_by: null,
    closed_by_name: null,
    outcome: '',
    close_note: '',
    origin: 'manual',
    events: [],
    notes: [],
    ...overrides,
  };
}

function makeDocument(activeStates = [episode(100, 10, 432000)], notes = []) {
  return {
    id: 1,
    title: 'Contrato de soporte',
    status: 'draft',
    content_markdown: '# Contrato\n\nContenido.',
    client_name: 'ACME',
    client_display_name: 'ACME',
    client: null,
    project: null,
    language: 'es',
    include_portada: true,
    include_subportada: true,
    include_contraportada: true,
    is_client_visible: false,
    is_archived: false,
    folder: null,
    template_style: 'professional',
    document_type_code: 'markdown',
    active_states: activeStates,
    notes,
    client_custom_notes: [],
    created_at: '2026-08-20T15:00:00Z',
  };
}

function listDocument(document) {
  return {
    id: document.id,
    title: document.title,
    status: document.status,
    is_archived: document.is_archived,
    document_type_code: document.document_type_code,
    client_display_name: document.client_display_name,
    project_name: '',
    active_states: document.active_states,
    created_at: document.created_at,
  };
}

function baseRoutes(apiPath, document, history = []) {
  if (apiPath === 'auth/check/') return authCheck;
  if (apiPath === 'documents/') return json([listDocument(document)]);
  if (apiPath === 'documents/counts/') {
    return json({
      documents: { active: 1, archived: 0, unfiled_active: 1, unfiled_archived: 0 },
      folders: { active: 0, archived: 0 },
    });
  }
  if (apiPath === 'document-folders/') return json([]);
  if (apiPath === 'document-states/') return json(states);
  if (apiPath === 'document-state-groups/') return json(groups);
  if (apiPath === 'documents/1/detail/') return json(document);
  if (apiPath === 'documents/1/state-history/') return json(history);
  return null;
}

async function openEditor(page) {
  await page.goto('/en-us/panel/documents', { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('document-open-1')).toBeVisible();
  await page.getByTestId('document-open-1').click();
  await expect(page.getByTestId('document-state-selector')).toBeVisible();
}

test.describe('Admin Document State Workflow', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 8700, role: 'admin', is_staff: true },
    });
  });

  test('renders a complete episode timeline', {
    tag: [...ADMIN_DOCUMENT_STATE_WORKFLOW, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the documented module entry; this test exercises the episode timeline after opening a document through the list)
    const note = {
      id: 50,
      document: 1,
      episode: 101,
      title: 'Ajustar total',
      content: 'El total no coincide con la propuesta.',
      status: 'open',
      resolution_note: '',
    };
    const activeStates = [
      episode(100, 11, 432000),
      episode(101, 20, 259200, { origin: 'note', notes: [note] }),
    ];
    const document = makeDocument(activeStates, [note]);
    const history = [
      {
        ...activeStates[1],
        events: [{
          id: 900,
          event_type: 'opened',
          effective_at: '2026-08-20T15:00:00Z',
          recorded_at: '2026-08-21T13:00:00Z',
          actor_name: 'Admin QA',
          details: {},
        }],
      },
      activeStates[0],
    ];
    await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath, document, history));
    await openEditor(page);

    await expect(page.getByTestId('document-state-needs-fix').first()).toContainText('3 días');
    await page.getByTestId('document-state-history-open').click();

    const timeline = page.getByTestId('document-state-history');
    await expect(timeline).toContainText('Solucionar bug');
    await expect(timeline).toContainText('Jue, 20 ago 2026, 10:00');
    await expect(timeline).toContainText('El total no coincide con la propuesta.');
    await timeline.getByText('Movimientos (1)').click();
    await expect(timeline).toContainText('Registrado: Vie, 21 ago 2026, 08:00');
  });

  test('moves the exclusive cycle to a newly selected state', {
    tag: [...ADMIN_DOCUMENT_STATE_WORKFLOW, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const document = makeDocument();
    let openBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'documents/1/state-episodes/' && method === 'POST') {
        openBody = route.request().postDataJSON();
        const sentEpisode = episode(102, 11, 0);
        document.active_states = [sentEpisode];
        return json(sentEpisode, 201);
      }
      return baseRoutes(apiPath, document);
    });
    await openEditor(page);

    await page.getByTestId('document-state-add-select').selectOption('11');
    await page.getByTestId('document-state-add').click();

    await expect.poll(() => openBody).not.toBeNull();
    expect(openBody).toMatchObject({ state_id: 11, origin: 'manual' });
    await expect(page.getByTestId('document-state-11').first()).toContainText('Enviado');
    await expect(page.getByTestId('document-state-10')).toHaveCount(0);
  });

  test('reuses a similar state suggested by the catalog', {
    tag: [...ADMIN_DOCUMENT_STATE_WORKFLOW, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const document = makeDocument();
    let openBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'document-states/suggestions/' && method === 'GET') {
        return json([{ ...states.find((item) => item.id === 20), similarity: 0.84 }]);
      }
      if (apiPath === 'documents/1/state-episodes/' && method === 'POST') {
        openBody = route.request().postDataJSON();
        const needsFix = episode(103, 20, 0, { origin: 'manual' });
        document.active_states.push(needsFix);
        return json(needsFix, 201);
      }
      return baseRoutes(apiPath, document);
    });
    await openEditor(page);

    await page.getByTestId('document-state-inline-name').fill('Solucion bug');
    await expect(page.getByTestId('document-state-suggestions')).toBeVisible();
    await page.getByRole('button', { name: '¿Solucionar bug?' }).click();

    await expect.poll(() => openBody).not.toBeNull();
    expect(openBody.state_id).toBe(20);
    await expect(page.getByTestId('document-state-needs-fix').first()).toBeVisible();
  });

  test('links a new observation to the needs-fix episode', {
    tag: [...ADMIN_DOCUMENT_STATE_WORKFLOW, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const document = makeDocument();
    let noteBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'documents/1/notes/' && method === 'POST') {
        noteBody = route.request().postDataJSON();
        const needsFix = episode(104, 20, 0, { origin: 'note' });
        const note = {
          id: 51,
          document: 1,
          episode: 104,
          title: noteBody.title,
          content: noteBody.content,
          status: 'open',
          resolution_note: '',
        };
        document.active_states.push(needsFix);
        document.notes.push(note);
        return json(note, 201);
      }
      return baseRoutes(apiPath, document);
    });
    await openEditor(page);

    await page.getByTestId('doc-client-note-open').click();
    await page.getByTestId('document-observation-title').fill('Corregir subtotal');
    await fillRichTextSource(page.getByTestId('document-observation-content'), 'El subtotal está duplicado.');
    await page.getByTestId('document-observation-add').click();

    await expect.poll(() => noteBody).not.toBeNull();
    expect(noteBody).toEqual({
      title: 'Corregir subtotal',
      content: 'El subtotal está duplicado.',
      text_formats: { '/content': 'markdown_html_v1' },
      mark_needs_fix: true,
    });
    await expect(page.getByTestId('document-observation-list')).toContainText('El subtotal está duplicado.');
    await expect(page.getByTestId('document-state-needs-fix').first()).toBeVisible();
  });

  test('rejects an incompatible active-state combination', {
    tag: [...ADMIN_DOCUMENT_STATE_WORKFLOW, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const document = makeDocument([
      episode(100, 11, 432000),
      episode(101, 20, 259200),
    ]);
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'documents/1/state-episodes/' && method === 'POST') {
        return json({
          detail: 'Cerrado no se puede combinar con Solucionar bug.',
          code: 'incompatible_state',
        }, 400);
      }
      return baseRoutes(apiPath, document);
    });
    await openEditor(page);

    await page.getByTestId('document-state-add-select').selectOption('13');
    await page.getByTestId('document-state-add').click();

    await expect(page.getByTestId('document-state-error')).toContainText('no se puede combinar');
    await expect(page.getByTestId('document-state-needs-fix').first()).toBeVisible();
    await expect(page.getByTestId('document-state-11').first()).toBeVisible();
  });

  test('preserves an episode after a failed close', {
    tag: [...ADMIN_DOCUMENT_STATE_WORKFLOW, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const document = makeDocument([
      episode(100, 11, 432000),
      episode(101, 20, 259200),
    ]);
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'documents/1/state-episodes/101/close/' && method === 'POST') {
        return json({ detail: 'No se pudo registrar el cierre.' }, 503);
      }
      return baseRoutes(apiPath, document);
    });
    await openEditor(page);

    await page.getByTestId('document-state-close-101').click();
    await expect(page.getByRole('dialog')).toContainText('Cerrar estado');
    await page.getByTestId('document-state-finish-note').fill('Se corrigió el cálculo.');
    await page.getByTestId('document-state-finish-confirm').click();

    await expect(page.getByTestId('document-state-error')).toContainText('No se pudo registrar el cierre');
    await expect(page.getByTestId('document-state-needs-fix').first()).toBeVisible();
  });
});

test.describe('Admin Document State Filters', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 8700, role: 'admin', is_staff: true },
    });
  });

  test('renders the actionable-state age in the list', {
    tag: [...ADMIN_DOCUMENT_STATE_FILTERS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the documented module entry and the behavior under test is rendered directly in its list)
    const document = makeDocument([
      episode(100, 11, 1036800),
      episode(101, 20, 259200),
    ]);
    await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath, document));

    await page.goto('/en-us/panel/documents', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('document-state-needs-fix').first()).toContainText('3 días');
    await page.getByTestId('document-state-filter-20').click();
    await expect(page.getByTestId('document-state-filter-20')).toHaveClass(/bg-primary-soft/);
  });

  test('keeps the needs-fix filter pill on one line in the compact layout', {
    tag: [...ADMIN_DOCUMENT_STATE_FILTERS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 412, height: 915 });
    const document = makeDocument();
    await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath, document));

    // quality: allow-no-interaction (responsive display contract is observable on initial render)
    // quality: allow-deep-link (/panel/documents is the documented module entry and renders the filter directly)
    await page.goto('/en-us/panel/documents', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Gestor Documental' })).toBeVisible();
    await expect(page.getByTestId('document-state-filters')).toBeVisible();

    const needsFixPill = page.getByTestId('document-state-filter-20');
    await expect(needsFixPill).toContainText('Solucionar bug');
    await expect.poll(() => needsFixPill.evaluate((element) => {
      const style = window.getComputedStyle(element);
      return {
        display: style.display,
        flexShrink: style.flexShrink,
        flexWrap: style.flexWrap,
        whiteSpace: style.whiteSpace,
      };
    })).toEqual({
      display: 'flex',
      flexShrink: '0',
      flexWrap: 'nowrap',
      whiteSpace: 'nowrap',
    });

    const viewportOverflow = await page.evaluate(() => (
      Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
      - document.documentElement.clientWidth
    ));
    expect(viewportOverflow).toBeLessThanOrEqual(1);
  });

  test('encodes multi-state filter semantics', {
    tag: [...ADMIN_DOCUMENT_STATE_FILTERS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const document = makeDocument();
    const queries = [];
    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'documents/') {
        queries.push(new URL(route.request().url()).searchParams.toString());
      }
      return baseRoutes(apiPath, document);
    });
    await page.goto('/en-us/panel/documents', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('document-state-filter-11').click();
    await expect.poll(() => queries.at(-1)).toContain('states=11');
    await page.getByTestId('document-state-filter-20').click();
    await expect.poll(() => decodeURIComponent(queries.at(-1))).toContain('states=11,20');
    await expect(page).toHaveURL(/(?:\?|&)states=11(?:%2C|,)20(?:&|$)/);
    await page.getByTestId('document-state-without-13').click();
    await expect.poll(() => decodeURIComponent(queries.at(-1))).toContain('without_states=13');
    await expect(page).toHaveURL(/(?:\?|&)without_states=13(?:&|$)/);
    await page.getByTestId('document-state-preset-needs_fix').click();
    await expect.poll(() => queries.at(-1)).toContain('preset=needs_fix');
    await expect(page).toHaveURL(/(?:\?|&)preset=needs_fix(?:&|$)/);
    expect(queries.at(-1)).not.toContain('states=');
    expect(queries.at(-1)).not.toContain('without_states=');
  });

  test('renders a persistent filtered-request failure', {
    tag: [...ADMIN_DOCUMENT_STATE_FILTERS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const document = makeDocument();
    let documentRequests = 0;
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'documents/') {
        documentRequests += 1;
        if (documentRequests > 1) return json({ detail: 'El filtro no respondió.' }, 503);
      }
      return baseRoutes(apiPath, document);
    });
    await page.goto('/en-us/panel/documents', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('document-state-filter-20').click();

    await expect(page.getByRole('alert')).toContainText('No se pudieron cargar los documentos');
    await expect(page.getByRole('alert')).toContainText('El filtro no respondió');
  });
});
