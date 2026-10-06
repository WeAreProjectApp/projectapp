/**
 * E2E coverage for grouped proposal-editor navigation.
 * Catches lifecycle-gated groups, legacy bookmarks, and unmounted panels that
 * become unreachable or discard work after the editor tabs are regrouped.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_EDIT } from '../helpers/flow-tags.js';
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

async function setupApi(page, { status = 'draft', calls = null } = {}) {
  const currentProposal = proposal(status);
  await mockApi(page, async ({ apiPath, method }) => {
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
    await selectProposalDestination(page, 'project');
    await expect(page.getByTestId('proposal-secondary-navigation')).toHaveCount(0);
    await expect(page.getByText(/Cronograma del proyecto$/)).toHaveCount(1);
  }
}

async function assertDestinationContent(page, section) {
  if (section === 'general') return expect(page.getByTestId('edit-client-name')).toHaveValue('Cliente de navegación');
  if (section === 'schedule') return expect(page.getByText(/Cronograma del proyecto$/)).toHaveCount(1);
  if (section === 'development') return expect(page.getByText('Checklist de desarrollo', { exact: true })).toHaveCount(1);
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
    { status: 'draft', visible: ['General', 'Propuesta', 'Comunicación', 'Documentos', 'Seguimiento'], absent: ['Proyecto'] },
    { status: 'sent', visible: ['General', 'Propuesta', 'Comunicación', 'Documentos', 'Seguimiento'], absent: ['Proyecto'] },
    { status: 'accepted', visible: ['General', 'Propuesta', 'Comunicación', 'Documentos', 'Proyecto', 'Seguimiento'], absent: [], destination: 'development' },
    { status: 'finished', visible: ['General', 'Propuesta', 'Comunicación', 'Documentos', 'Proyecto', 'Seguimiento'], absent: [], destination: 'schedule' },
  ]) {
    test(`${scenario.status} exposes only its available grouped destinations`, {
      tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      await setupApi(page, { status: scenario.status });
      // quality: allow-deep-link (proposal list is the entry point; the editor under test is reached through its real row link)
      await openEditorFromProposalList(page);
      await expect(page.getByText('Propuesta de navegación E2E', { exact: true })).toHaveCount(1);
      await assertLifecycleNavigation(page, scenario);
    });
  }

  // Catches legacy bookmarks losing unrelated URL state while converting to groups.
  for (const destination of [
    { name: 'legacy emails', input: 'tab=emails', tab: 'communication', querySection: 'emails', section: 'emails', status: 'accepted' },
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
    await selectProposalDestination(page, 'communication', 'resources');
    await page.getByLabel('Archivo de video').setInputFiles(CLIP_FILE);
    await expect(page.getByTestId('video-resource-manager')).toContainText('Video personalizado de esta propuesta');
    await selectProposalDestination(page, 'proposal', 'sections');
    await expect(page.getByTestId('section-header-greeting')).toContainText('Saludo');
    await selectProposalDestination(page, 'communication', 'resources');
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
    // Seguimiento opens Actividad on first entry, then revisiting it refreshes again.
    await expect.poll(() => calls.detail).toBe(3);

    await selectProposalDestination(page, 'tracking', 'history');
    await expect(page.getByTestId('entity-history')).toContainText('Historial');
  });

  // Catches an Activity background refresh tearing down a visited resource panel and its selected file.
  test('keeps a selected video file after visiting Activity', {
    tag: [...ADMIN_PROPOSAL_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'communication', 'resources');
    await page.getByLabel('Archivo de video').setInputFiles(CLIP_FILE);
    await selectProposalDestination(page, 'tracking', 'activity');
    await expect(page.getByText('Registrar actividad', { exact: true })).toHaveCount(1);
    await selectProposalDestination(page, 'communication', 'resources');
    await expect(page.getByLabel('Archivo de video')).toHaveValue(/navigation\.mp4$/);
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
