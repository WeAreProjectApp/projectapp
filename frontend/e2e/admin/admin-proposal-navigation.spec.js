/**
 * E2E coverage for grouped proposal-editor navigation.
 * Catches lifecycle-gated groups, legacy bookmarks, and unmounted panels that
 * become unreachable or discard work after the editor tabs are regrouped.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_EDIT, ADMIN_PROPOSAL_ACTIVITY_LOG } from '../helpers/flow-tags.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { viewportUse } from '../helpers/viewports.js';

const PROPOSAL_ID = 9901;
const CLIP_FILE = { name: 'navigation.mp4', mimeType: 'video/mp4', buffer: Buffer.from('e2e-video') };

function proposal(status = 'draft') {
  return {
    id: PROPOSAL_ID,
    uuid: '99010000-1111-4111-8111-111111111111',
    title: 'Propuesta de navegación E2E',
    client_name: 'Cliente de navegación', client_email: 'navigation@example.com',
    language: 'es', status, is_active: true, total_investment: '5000000', currency: 'COP',
    view_count: 3, sent_at: status === 'draft' ? null : '2026-09-01T10:00:00Z',
    sections: [{
      id: 991, section_type: 'greeting', title: 'Saludo', order: 0, is_enabled: true,
      is_wide_panel: false,
      content_json: { proposalTitle: 'Propuesta de navegación E2E', clientName: 'Cliente de navegación', inspirationalQuote: '' },
    }],
    requirement_groups: [], change_logs: [], proposal_documents: [],
  };
}

const analytics = {
  total_views: 3, unique_sessions: 2, section_views: [], daily_views: [], funnel: [], share_links: [],
  skipped_sections: [], device_breakdown: { desktop: 3 }, activity_log: [], sections: [], sessions: [], timeline: [],
};

function json(body, status = 200) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

async function setupApi(page, {
  status = 'draft', calls = null, activityHandler = null, updateHandler = null,
  proposalOverrides = {}, projectRows = [], reassignmentHandler = null,
} = {}) {
  const currentProposal = { ...proposal(status), ...proposalOverrides };
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { id: 9901, username: 'e2e-admin', is_staff: true } });
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/` && method === 'GET') {
      calls && (calls.detail += 1);
      return json(currentProposal);
    }
    if (apiPath === 'proposals/' && method === 'GET') return json([currentProposal]);
    if (apiPath === 'proposals/dashboard/' || apiPath === 'proposals/alerts/' || apiPath === 'proposals/client-profiles/') return json([]);
    if (apiPath === `proposals/${PROPOSAL_ID}/analytics/` && method === 'GET') {
      calls && (calls.analytics += 1);
      return json(analytics);
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/activity/` && method === 'GET') {
      return activityHandler ? activityHandler(route) : json({ results: [], next_cursor: null, has_more: false });
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/update/` && method === 'PATCH') {
      return updateHandler ? updateHandler(route, currentProposal) : json(currentProposal);
    }
    if (apiPath === 'projects/' && method === 'GET') return json({ results: projectRows });
    if (apiPath === `proposals/${PROPOSAL_ID}/project-reassignment/`) {
      return reassignmentHandler ? reassignmentHandler(route, method, currentProposal) : json({ detail: 'No configurado' }, 404);
    }
    if (apiPath.startsWith(`entity-history/proposal/${PROPOSAL_ID}/`) && method === 'GET') {
      return json({ results: [], count: 0, page: 1, page_size: 25, total_pages: 1 });
    }
    if (apiPath === `video-resources/admin/proposals/${PROPOSAL_ID}/` && method === 'GET') {
      return json({ key: `proposal:${PROPOSAL_ID}`, module: 'proposal', language: 'es', mode: 'none', revision: 0, filename: null, size: 0, video: null });
    }
    if (apiPath === `proposals/sections/991/update/` && method === 'PATCH') return json(currentProposal.sections[0]);
    return null;
  });
}

async function authenticate(page) {
  await setAuthLocalStorage(page, { token: 'e2e-admin', userAuth: { id: 9901, role: 'admin', is_staff: true } });
}

async function openEditorFromProposalList(page) {
  await page.goto('/es-co/panel/proposals', { waitUntil: 'domcontentloaded' });
  await page.getByTestId(`proposal-open-${PROPOSAL_ID}`).click();
  await expect(page.getByText('Propuesta de navegación E2E', { exact: true })).toBeVisible();
}

async function assertLifecycleNavigation(page, scenario) {
  const primary = page.getByTestId('proposal-primary-navigation');
  for (const label of scenario.visible) await expect(primary.getByRole('tab', { name: label, exact: true })).toHaveCount(1);
  for (const label of scenario.absent) await expect(primary.getByRole('tab', { name: label, exact: true })).toHaveCount(0);
  if (scenario.destination === 'development') {
    await selectProposalDestination(page, 'project', 'development');
    await expect(page.getByTestId('proposal-secondary-navigation').getByRole('tab', { name: 'Desarrollo', exact: true })).toHaveCount(1);
  }
  if (scenario.destination === 'schedule') {
    await selectProposalDestination(page, 'project', 'schedule');
    await expect(page.getByText(/Cronograma del proyecto$/)).toHaveCount(1);
  }
  if (scenario.destination === 'project-data') {
    await selectProposalDestination(page, 'project', 'project-data');
    await expect(page.getByTestId('proposal-project-data')).toContainText('Cliente y datos de contacto');
  }
}

async function assertDestinationContent(page, section) {
  if (section === 'general') return expect(page.getByRole('heading', { name: 'Propuesta de navegación E2E' })).toHaveCount(1);
  if (section === 'project-data') return expect(page.getByTestId('proposal-project-data')).toContainText('Cliente y datos de contacto');
  if (section === 'schedule') return expect(page.getByText(/Cronograma del proyecto$/)).toHaveCount(1);
  if (section === 'development') return expect(page.getByText('Checklist de desarrollo', { exact: true })).toHaveCount(1);
  if (section === 'resources') return expect(page.getByTestId('video-resource-manager')).toContainText('Video personalizado de esta propuesta');
  return expect(page.getByText('Secciones del correo', { exact: true })).toHaveCount(1);
}

async function assertResponsiveNavigation(page, profile) {
  const compact = ['compact', 'portrait'].includes(profile);
  const primary = page.getByTestId('proposal-primary-navigation');
  if (compact) return expect(primary.getByRole('combobox', { name: 'Áreas de la propuesta' })).toHaveValue('general');
  return expect(primary.getByRole('tab', { name: 'General', exact: true })).toHaveCount(1);
}

async function assertResponsiveSecondaryNavigation(page, profile) {
  const compact = ['compact', 'portrait'].includes(profile);
  const secondary = page.getByTestId('proposal-secondary-navigation');
  if (compact) return expect(secondary.getByRole('combobox')).toHaveValue('sections');
  return expect(secondary.getByRole('tab', { name: 'Secciones', exact: true })).toHaveCount(1);
}

test.describe('Admin proposal grouped navigation', () => {
  test.setTimeout(60_000);
  test.beforeEach(async ({ page }) => authenticate(page));

  // Catches status-gated areas remaining available after the proposal lifecycle changes.
  for (const scenario of [
    { status: 'draft', visible: ['General', 'Propuesta', 'Comunicación', 'Documentos', 'Proyecto', 'Seguimiento'], absent: [], destination: 'project-data' },
    { status: 'sent', visible: ['General', 'Propuesta', 'Comunicación', 'Documentos', 'Proyecto', 'Seguimiento'], absent: [], destination: 'project-data' },
    { status: 'accepted', visible: ['General', 'Propuesta', 'Comunicación', 'Documentos', 'Proyecto', 'Seguimiento'], absent: [], destination: 'development' },
    { status: 'finished', visible: ['General', 'Propuesta', 'Comunicación', 'Documentos', 'Proyecto', 'Seguimiento'], absent: [], destination: 'schedule' },
  ]) {
    test(`${scenario.status} exposes only its available grouped destinations`, {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      await setupApi(page, { status: scenario.status });
      // quality: allow-deep-link (proposal list is the entry point; the editor under test is reached through its real row link)
      await openEditorFromProposalList(page);
      await expect(page.getByRole('heading', { name: 'Propuesta de navegación E2E', exact: true })).toHaveCount(1);
      await assertLifecycleNavigation(page, scenario);
    });
  }

  // Catches legacy bookmarks losing unrelated URL state while converting to groups.
  for (const destination of [
    { name: 'legacy emails', input: 'tab=emails', tab: 'communication', querySection: null, section: 'emails', status: 'accepted' },
    { name: 'legacy resources', input: 'tab=communication&section=resources', tab: 'proposal', querySection: 'resources', section: 'resources', status: 'draft' },
    { name: 'legacy schedule', input: 'tab=schedule', tab: 'project', querySection: 'schedule', section: 'schedule', status: 'accepted' },
    { name: 'canonical development', input: 'tab=project&section=development', tab: 'project', querySection: 'development', section: 'development', status: 'accepted' },
    { name: 'unknown destination', input: 'tab=missing', tab: null, querySection: null, section: 'general', status: 'accepted' },
    { name: 'finished development', input: 'tab=project&section=development', tab: null, querySection: null, section: 'general', status: 'finished' },
  ]) {
    test(`normalizes ${destination.name} without dropping shared link state`, {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      // quality: allow-no-interaction (bookmark URL normalization occurs on document entry and has no in-page action)
      await setupApi(page, { status: destination.status });
      await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit?${destination.input}&source=bookmark#notes`, { waitUntil: 'domcontentloaded' });

      await expect(page.getByText('Propuesta de navegación E2E', { exact: true })).toHaveCount(1);
      await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe(destination.tab);
      await expect.poll(() => new URL(page.url()).searchParams.get('section')).toBe(destination.querySection);
      await expect.poll(() => new URL(page.url()).searchParams.get('source')).toBe('bookmark');
      await expect.poll(() => new URL(page.url()).hash).toBe('#notes');
      await assertDestinationContent(page, destination.section);
      if (destination.section === 'resources') {
        await selectProposalDestination(page, 'communication', 'emails');
        await expect(page.getByTestId('proposal-email-settings')).toContainText('Configuración del correo');
        await selectProposalDestination(page, 'project', 'project-data');
        await expect(page.getByTestId('proposal-project-data')).toContainText('Cliente y datos de contacto');
        await expect(page.getByTestId('proposal-linked-project')).toHaveText('Sin proyecto vinculado');
      }
    });
  }

  // Catches a group switch remounting a section editor and losing unsaved work.
  test('keeps an edited section after changing proposal groups', {
    tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });

    await selectProposalDestination(page, 'proposal', 'sections');
    await page.getByTestId('section-header-greeting').click();
    const field = page.getByTestId('section-editor').locator('input[type="text"]').first();
    await field.fill('Saludo que no debe perderse');
    await expect(page.getByTestId('proposal-unsaved-notice')).toContainText('Secciones sin guardar');

    await selectProposalDestination(page, 'communication', 'emails');
    await expect(page.getByRole('heading', { name: 'Mensaje personalizado del correo de envío' })).toBeVisible();

    await selectProposalDestination(page, 'proposal', 'sections');
    await expect(field).toHaveValue('Saludo que no debe perderse');
    await expect(page.getByTestId('proposal-unsaved-notice')).toContainText('Secciones sin guardar');

  });

  // Catches eager video-resource mounting or a group switch discarding a selected file.
  test('preserves the lazily mounted video resource panel across group changes', {
    tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('video-resource-manager')).toHaveCount(0);
    await selectProposalDestination(page, 'proposal', 'resources');
    await page.getByLabel('Archivo de video').setInputFiles(CLIP_FILE);
    await expect(page.getByTestId('video-resource-manager')).toContainText('Video personalizado de esta propuesta');
    await selectProposalDestination(page, 'proposal', 'sections');
    await expect(page.getByTestId('section-header-greeting')).toContainText('Saludo');
    await selectProposalDestination(page, 'proposal', 'resources');
    await expect(page.getByLabel('Archivo de video')).toHaveValue(/navigation\.mp4$/);
  });

  // Catches Tracking selections becoming inert or refreshing activity while an edit is pending.
  test('tracking selections activate their requested tools', {
    tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = { detail: 0, analytics: 0 };
    await setupApi(page, { calls });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Propuesta de navegación E2E' })).toBeVisible({ timeout: 40_000 });
    await expect.poll(() => calls.detail).toBe(1);

    await selectProposalDestination(page, 'tracking', 'analytics');
    await expect.poll(() => calls.analytics).toBe(1);

    await selectProposalDestination(page, 'tracking', 'activity');
    // Actividad now loads its own paged endpoint and must not refetch the draft detail.
    await expect.poll(() => calls.detail).toBe(1);

    await selectProposalDestination(page, 'tracking', 'history');
    await expect(page.getByTestId('entity-history')).toContainText('Historial');
  });

  // Catches an Activity background refresh tearing down a visited resource panel and its selected file.
  test('keeps a selected video file after visiting Activity', {
    tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'proposal', 'resources');
    await page.getByLabel('Archivo de video').setInputFiles(CLIP_FILE);
    await selectProposalDestination(page, 'tracking', 'activity');
    await expect(page.getByText('Registrar actividad', { exact: true })).toHaveCount(1);
    await selectProposalDestination(page, 'proposal', 'resources');
    await expect(page.getByLabel('Archivo de video')).toHaveValue(/navigation\.mp4$/);
  });

  // Bug caught: cursor paging stopped after 50 logs or replaced already read activity.
  test('activity loads every cursor page beyond fifty entries', {
    tag: [...ADMIN_PROPOSAL_EDIT, ...ADMIN_PROPOSAL_ACTIVITY_LOG, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const pageOf = (start, nextCursor) => json({
      results: Array.from({ length: 20 }, (_, index) => ({
        id: start + index,
        change_type: 'note',
        description: `Registro ${start + index}`,
        created_at: `2026-09-${String(28 - index).padStart(2, '0')}T10:00:00Z`,
      })),
      next_cursor: nextCursor,
      has_more: Boolean(nextCursor),
    });
    await setupApi(page, {
      activityHandler(route) {
        const cursor = new URL(route.request().url()).searchParams.get('cursor');
        if (!cursor) return pageOf(1, 'page-2');
        if (cursor === 'page-2') return pageOf(21, 'page-3');
        if (cursor === 'page-3') return pageOf(41, 'page-4');
        return pageOf(61, null);
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'tracking', 'activity');
    await expect(page.getByText('Registro 1', { exact: true })).toHaveCount(1);

    await page.getByTestId('proposal-activity-load-more').click();
    await expect(page.getByText('Registro 21', { exact: true })).toHaveCount(1);
    await page.getByTestId('proposal-activity-load-more').click();
    await expect(page.getByText('Registro 51', { exact: true })).toHaveCount(1);
    await page.getByTestId('proposal-activity-load-more').click();
    await expect(page.getByText('Registro 61', { exact: true })).toHaveCount(1);
    await expect(page.getByText('Registro 1', { exact: true })).toHaveCount(1);
  });

  // Bug caught: a transient next-page failure cleared the timeline instead of retaining loaded entries for retry.
  test('activity retry preserves loaded records after a next-page failure', {
    tag: [...ADMIN_PROPOSAL_EDIT, ...ADMIN_PROPOSAL_ACTIVITY_LOG, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    let retry = false;
    await setupApi(page, {
      activityHandler(route) {
        const cursor = new URL(route.request().url()).searchParams.get('cursor');
        if (!cursor) return json({ results: [{ id: 1, change_type: 'note', description: 'Registro conservado', created_at: '2026-09-28T10:00:00Z' }], next_cursor: 'retry-page', has_more: true });
        if (!retry) return json({ detail: 'Servicio temporalmente no disponible' }, 500);
        return json({ results: [{ id: 21, change_type: 'note', description: 'Registro recuperado', created_at: '2026-09-27T10:00:00Z' }], next_cursor: null, has_more: false });
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'tracking', 'activity');
    await expect(page.getByText('Registro conservado', { exact: true })).toHaveCount(1);

    await page.getByTestId('proposal-activity-load-more').click();
    await expect(page.getByRole('alert')).toContainText('No se pudo cargar la actividad');
    await expect(page.getByText('Registro conservado', { exact: true })).toHaveCount(1);
    retry = true;
    await page.getByRole('button', { name: 'Reintentar', exact: true }).click();
    await expect(page.getByText('Registro recuperado', { exact: true })).toHaveCount(1);
    await expect(page.getByText('Registro conservado', { exact: true })).toHaveCount(1);
  });

  // Bug caught: a late initial activity response overwrote a note the operator had just submitted.
  test('a delayed initial activity response keeps a newly submitted note', {
    tag: [...ADMIN_PROPOSAL_EDIT, ...ADMIN_PROPOSAL_ACTIVITY_LOG, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let releaseInitial;
    const initialResponse = new Promise((resolve) => { releaseInitial = resolve; });
    await setupApi(page, {
      async activityHandler() {
        await initialResponse;
        return json({ results: [{ id: 1, change_type: 'note', description: 'Registro del servidor', created_at: '2026-09-28T10:00:00Z' }], next_cursor: null, has_more: false });
      },
    });
    await page.route('**/api/proposals/9901/log-activity/', async (route) => route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ id: 99, change_type: 'note', description: 'Nota recién guardada', created_at: '2026-09-29T10:00:00Z' }),
    }));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'tracking', 'activity');
    await page.getByPlaceholder(/Descripción de la actividad/i).fill('Nota recién guardada');
    await page.getByRole('button', { name: 'Agregar', exact: true }).click();
    await expect(page.getByText('Nota recién guardada', { exact: true })).toHaveCount(1);
    releaseInitial();
    await expect(page.getByText('Registro del servidor', { exact: true })).toHaveCount(1);
    await expect(page.getByText('Nota recién guardada', { exact: true })).toHaveCount(1);
  });

  // Bug caught: saving Cliente persisted unrelated General edits or dismissed their draft warning.
  test('saving client fields keeps a pending general draft isolated', {
    tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const patches = [];
    await setupApi(page, {
      updateHandler(route, currentProposal) {
        const payload = route.request().postDataJSON();
        patches.push(payload);
        return json({ ...currentProposal, ...payload });
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('general-finance-general-discount').fill('8');
    await expect(page.getByTestId('proposal-unsaved-notice')).toContainText('Datos de la propuesta sin guardar');

    await selectProposalDestination(page, 'project', 'project-data');
    await page.getByTestId('edit-client-name').fill('Cliente corregido');
    await page.getByRole('button', { name: 'Guardar cliente', exact: true }).click();
    await expect.poll(() => patches.length).toBe(1);
    expect(Object.keys(patches[0]).sort()).toEqual(['client_company', 'client_email', 'client_id', 'client_name', 'client_phone', 'create_new_client', 'propagate_client_updates']);
    expect(patches[0].discount_percent).toBeUndefined();
    await expect(page.getByTestId('proposal-unsaved-notice')).toContainText('Datos de la propuesta sin guardar');

  });

  // Bug caught: saving Correos persisted unrelated General edits or dismissed their draft warning.
  test('saving email settings keeps a pending general draft isolated', {
    tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const patches = [];
    await setupApi(page, {
      updateHandler(route, currentProposal) {
        const payload = route.request().postDataJSON();
        patches.push(payload);
        return json({ ...currentProposal, ...payload });
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('general-finance-general-discount').fill('8');
    await selectProposalDestination(page, 'communication', 'emails');
    await page.getByTestId('edit-add-feature').click();
    await page.getByPlaceholder(/Dashboard en tiempo real/i).fill('Acceso al tablero');
    await page.getByRole('button', { name: 'Guardar configuración del correo', exact: true }).click();
    await expect.poll(() => patches.length).toBe(1);
    expect(Object.keys(patches[0]).sort()).toEqual(['email_features', 'email_method_phases', 'email_signed_by']);
    expect(patches[0].discount_percent).toBeUndefined();
    await expect(page.getByTestId('proposal-unsaved-notice')).toContainText('Datos de la propuesta sin guardar');
  });

  // Bug caught: a rejected partial save hid the unsaved General draft and made the operator think it was persisted.
  test('failed client save leaves the general draft visible and reports the error', {
    tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, {
      updateHandler() {
        return json({ detail: 'El cliente no se pudo actualizar.' }, 500);
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('general-finance-general-discount').fill('8');
    await selectProposalDestination(page, 'project', 'project-data');
    await page.getByTestId('edit-client-name').fill('Cliente aún pendiente');
    await page.getByRole('button', { name: 'Guardar cliente', exact: true }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'No se pudieron guardar los cambios.' })).toBeVisible();
    await expect(page.getByTestId('edit-client-name')).toHaveValue('Cliente aún pendiente');
    await expect(page.getByTestId('proposal-unsaved-notice')).toContainText('Datos de la propuesta sin guardar');
  });

  // Bug caught: a reviewed reassignment preview could not confirm its exact target, reason and preserved relationship.
  test('proposal project data previews and confirms a same-client reassignment', {
    tag: ['@flow:admin-proposal-project-reassignment', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let confirmPayload = null;
    const impact = {
      source_project: { id: 123, name: 'Proyecto origen' },
      target_project: { id: 456, name: 'Proyecto destino' },
      deliverable_ids: [30], phase_ids: [40], approval_file_ids: [50], document_ids: [60],
      blockers: [], impact_hash: 'a'.repeat(64),
    };
    await setupApi(page, {
      status: 'accepted',
      proposalOverrides: {
        client: { id: 77 },
        linked_project: { id: 123, name: 'Proyecto origen' },
      },
      projectRows: [{ id: 456, name: 'Proyecto destino', client: { profile_id: 77 }, status: 'active' }],
      reassignmentHandler(route, method, currentProposal) {
        if (method === 'GET') return json(impact);
        confirmPayload = route.request().postDataJSON();
        return json({ proposal: { ...currentProposal, linked_project: { id: 456, name: 'Proyecto destino' } }, impact, idempotent: false });
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'project', 'project-data');
    await page.getByTestId('proposal-reassignment-project').selectOption('456');
    await page.getByTestId('proposal-reassignment-reason').fill('Corregir la propuesta que quedó en el proyecto automático.');
    await page.getByTestId('proposal-reassignment-preview').click();
    await expect(page.getByTestId('proposal-reassignment-impact')).toContainText('Proyecto origen → Proyecto destino');
    await page.getByTestId('proposal-reassignment-confirm').click();
    await expect.poll(() => confirmPayload?.target_project_id).toBe(456);
    expect(confirmPayload.reason).toBe('Corregir la propuesta que quedó en el proyecto automático.');
    expect(confirmPayload.expected_impact_hash).toBe('a'.repeat(64));
    await expect(page.getByTestId('proposal-linked-project')).toHaveText('Proyecto destino');
  });

  // Bug caught: a stale reassignment preview could still move proposal resources after its source changed.
  test('proposal project data explains a stale reassignment preview without moving it', {
    tag: ['@flow:admin-proposal-project-reassignment', '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    let confirmed = false;
    const impact = {
      source_project: { id: 123, name: 'Proyecto origen' },
      target_project: { id: 456, name: 'Proyecto destino' },
      deliverable_ids: [30], phase_ids: [40], approval_file_ids: [50], document_ids: [],
      blockers: [], impact_hash: 'b'.repeat(64),
    };
    await setupApi(page, {
      status: 'accepted',
      proposalOverrides: { client: { id: 77 }, linked_project: { id: 123, name: 'Proyecto origen' } },
      projectRows: [{ id: 456, name: 'Proyecto destino', client: { profile_id: 77 }, status: 'active' }],
      reassignmentHandler(route, method) {
        if (method === 'GET') return json(impact);
        confirmed = true;
        return json({ detail: 'La propuesta o sus relaciones cambiaron. Revisa nuevamente el impacto.', code: 'stale_impact' }, 409);
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'project', 'project-data');
    await page.getByTestId('proposal-reassignment-project').selectOption('456');
    await page.getByTestId('proposal-reassignment-reason').fill('La revisión debe renovarse antes de mover relaciones.');
    await page.getByTestId('proposal-reassignment-preview').click();
    await page.getByTestId('proposal-reassignment-confirm').click();
    await expect(page.getByRole('alert')).toContainText('La propuesta o sus relaciones cambiaron. Revisa nuevamente el impacto.');
    expect(confirmed).toBe(true);
    await expect(page.getByTestId('proposal-linked-project')).toHaveText('Proyecto origen');
  });

  // Bug caught: a temporary server failure discarded the reviewed operation and sent the retry with a different request id.
  test('proposal project data retries a failed reassignment with the reviewed request id', {
    tag: ['@flow:admin-proposal-project-reassignment', '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const requestIds = [];
    const impact = {
      source_project: { id: 123, name: 'Proyecto origen' },
      target_project: { id: 456, name: 'Proyecto destino' },
      deliverable_ids: [30], phase_ids: [40], approval_file_ids: [50], document_ids: [],
      blockers: [], impact_hash: 'c'.repeat(64),
    };
    await setupApi(page, {
      status: 'accepted',
      proposalOverrides: { client: { id: 77 }, linked_project: { id: 123, name: 'Proyecto origen' } },
      projectRows: [{ id: 456, name: 'Proyecto destino', client: { profile_id: 77 }, status: 'active' }],
      reassignmentHandler(route, method, currentProposal) {
        if (method === 'GET') return json(impact);
        requestIds.push(route.request().postDataJSON().request_id);
        if (requestIds.length === 1) return json({ detail: 'No se pudo aplicar la reasignación. Inténtalo de nuevo.' }, 500);
        return json({ proposal: { ...currentProposal, linked_project: { id: 456, name: 'Proyecto destino' } }, impact, idempotent: false });
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'project', 'project-data');
    await page.getByTestId('proposal-reassignment-project').selectOption('456');
    await page.getByTestId('proposal-reassignment-reason').fill('Reintentar la corrección conservando la revisión.');
    await page.getByTestId('proposal-reassignment-preview').click();
    await page.getByTestId('proposal-reassignment-confirm').click();
    await expect(page.getByRole('alert')).toContainText('No se pudo aplicar la reasignación. Inténtalo de nuevo.');
    await page.getByTestId('proposal-reassignment-confirm').click();
    await expect.poll(() => requestIds.length).toBe(2);
    expect(requestIds[1]).toBe(requestIds[0]);
    await expect(page.getByTestId('proposal-linked-project')).toHaveText('Proyecto destino');
  });

  for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
    test(`${profile} reaches proposal sections through both navigation levels`, {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:display', '@responsive:proposal-groups', `@viewport:${profile}`],
    }, async ({ page }) => {
      // quality: allow-duplicate (per-viewport contract: grouped proposal navigation)
      await page.setViewportSize(viewportUse(profile).viewport);
      await setupApi(page);
      // quality: allow-deep-link (proposal list is the entry point; the editor under test is reached through its real row link)
      await openEditorFromProposalList(page);
      await assertResponsiveNavigation(page, profile);
      await selectProposalDestination(page, 'proposal', 'sections');
      await expect(page.getByTestId('section-header-greeting')).toContainText('Saludo');
      await assertResponsiveSecondaryNavigation(page, profile);
    });
  }
});
