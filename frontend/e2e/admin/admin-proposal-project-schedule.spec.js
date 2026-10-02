/**
 * E2E tests for the admin proposal Cronograma (project schedule) tab.
 *
 * @flow:admin-proposal-project-schedule
 * Covers: tab visibility (only for accepted/finished proposals),
 *         render of two stage cards (Diseño + Desarrollo),
 *         saving start/end dates via PUT, validation error,
 *         marking a stage as completed via POST.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_PROJECT_SCHEDULE } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;
const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

function buildAcceptedProposal(overrides = {}) {
  return {
    id: PROPOSAL_ID,
    uuid: '11111111-1111-1111-1111-111111111111',
    title: 'Cronograma Test',
    client_name: 'Acme Corp',
    client_email: 'acme@example.com',
    language: 'es',
    status: 'accepted',
    total_investment: '15000000',
    currency: 'COP',
    view_count: 5,
    sent_at: '2026-03-20T10:00:00Z',
    sections: [
      { id: 1, section_type: 'greeting', title: 'Saludo', order: 0, is_enabled: true, content_json: {} },
    ],
    requirement_groups: [],
    proposal_documents: [],
    project_stages: [
      {
        id: 1, stage_key: 'design', stage_label: 'Diseño', order: 0,
        start_date: null, end_date: null, completed_at: null,
        warning_sent_at: null, last_overdue_reminder_at: null,
      },
      {
        id: 2, stage_key: 'development', stage_label: 'Desarrollo', order: 1,
        start_date: null, end_date: null, completed_at: null,
        warning_sent_at: null, last_overdue_reminder_at: null,
      },
    ],
    ...overrides,
  };
}

function buildApiHandler({ proposal, onUpdate, onComplete } = {}) {
  const data = proposal || buildAcceptedProposal();
  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(data),
      };
    }
    const updateMatch = apiPath.match(
      new RegExp(`^proposals/${PROPOSAL_ID}/stages/(design|development)/$`),
    );
    if (updateMatch && method === 'PUT') {
      const stageKey = updateMatch[1];
      const rawBody = route.request().postData();
      const body = rawBody ? JSON.parse(rawBody) : {};
      if (typeof onUpdate === 'function') onUpdate(stageKey, body);
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: stageKey === 'design' ? 1 : 2,
          stage_key: stageKey,
          stage_label: stageKey === 'design' ? 'Diseño' : 'Desarrollo',
          order: stageKey === 'design' ? 0 : 1,
          start_date: body.start_date || null,
          end_date: body.end_date || null,
          completed_at: null,
          warning_sent_at: null,
          last_overdue_reminder_at: null,
        }),
      };
    }
    const completeMatch = apiPath.match(
      new RegExp(`^proposals/${PROPOSAL_ID}/stages/(design|development)/complete/$`),
    );
    if (completeMatch && method === 'POST') {
      const stageKey = completeMatch[1];
      if (typeof onComplete === 'function') onComplete(stageKey);
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: stageKey === 'design' ? 1 : 2,
          stage_key: stageKey,
          stage_label: stageKey === 'design' ? 'Diseño' : 'Desarrollo',
          order: stageKey === 'design' ? 0 : 1,
          start_date: '2026-04-01',
          end_date: '2026-04-10',
          completed_at: '2026-04-10T12:00:00Z',
          warning_sent_at: null,
          last_overdue_reminder_at: null,
        }),
      };
    }
    return null;
  };
}

test.describe('Admin Proposal Project Schedule (Cronograma)', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 8800, role: 'admin', is_staff: true },
    });
  });

  test('Cronograma tab is visible for accepted proposals', {
    tag: [...ADMIN_PROPOSAL_PROJECT_SCHEDULE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildApiHandler());
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit?tab=schedule`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByText('Cronograma del proyecto')).toBeVisible();
  });

  test('renders both stage cards (Diseño and Desarrollo)', {
    tag: [...ADMIN_PROPOSAL_PROJECT_SCHEDULE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildApiHandler());
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit?tab=schedule`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.locator('[data-testid="stage-card-design"]')).toBeVisible();
    await expect(page.locator('[data-testid="stage-card-development"]')).toBeVisible();
  });

  test('saving stage dates calls the update endpoint', {
    tag: [...ADMIN_PROPOSAL_PROJECT_SCHEDULE, '@role:admin'],
  }, async ({ page }) => {
    let received = null;
    await mockApi(page, buildApiHandler({
      onUpdate: (stageKey, body) => {
        received = { stageKey, body };
      },
    }));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit?tab=schedule`);
    await page.waitForLoadState('domcontentloaded');

    await page.locator('[data-testid="stage-start-design"]').fill('2026-04-01');
    await page.locator('[data-testid="stage-end-design"]').fill('2026-04-15');
    await page.locator('[data-testid="stage-save-design"]').click();

    await expect(() => expect(received).not.toBeNull()).toPass({ timeout: 5000 });
    expect(received.stageKey).toBe('design');
    expect(received.body.start_date).toBe('2026-04-01');
    expect(received.body.end_date).toBe('2026-04-15');
  });

  test('shows inline error when start_date is after end_date', {
    tag: ['@outcome:error', ...ADMIN_PROPOSAL_PROJECT_SCHEDULE, '@role:admin'],
  }, async ({ page }) => {
    let updateCalled = false;
    await mockApi(page, buildApiHandler({
      onUpdate: () => { updateCalled = true; },
    }));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit?tab=schedule`);
    await page.waitForLoadState('domcontentloaded');

    await page.locator('[data-testid="stage-start-design"]').fill('2026-04-20');
    await page.locator('[data-testid="stage-end-design"]').fill('2026-04-10');
    await page.locator('[data-testid="stage-save-design"]').click();

    await expect(page.locator('[data-testid="stage-error-design"]')).toBeVisible();
    expect(updateCalled).toBe(false);
  });

  test('marking a stage as completed calls the complete endpoint and shows the badge', {
    tag: [...ADMIN_PROPOSAL_PROJECT_SCHEDULE, '@role:admin'],
  }, async ({ page }) => {
    let completedKey = null;
    const proposal = buildAcceptedProposal();
    proposal.project_stages[0].start_date = '2026-04-01';
    proposal.project_stages[0].end_date = '2026-04-10';

    await mockApi(page, buildApiHandler({
      proposal,
      onComplete: (stageKey) => { completedKey = stageKey; },
    }));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit?tab=schedule`);
    await page.waitForLoadState('domcontentloaded');

    await page.locator('[data-testid="stage-complete-design"]').click();

    await expect(() => expect(completedKey).toBe('design')).toPass({ timeout: 5000 });
    await expect(page.locator('[data-testid="stage-status-design"]')).toContainText('Completada');
  });

  test('Cronograma tab is hidden for negotiating proposals', {
    tag: [...ADMIN_PROPOSAL_PROJECT_SCHEDULE, '@role:admin'],
  }, async ({ page }) => {
    const negotiating = buildAcceptedProposal({ status: 'negotiating' });
    await mockApi(page, buildApiHandler({ proposal: negotiating }));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await page.waitForLoadState('domcontentloaded');

    // The Project group is unavailable before acceptance.
    await expect(page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Proyecto', exact: true })).toHaveCount(0);
  });
});
