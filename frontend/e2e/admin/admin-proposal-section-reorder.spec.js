/**
 * E2E tests for admin proposal section reordering via drag & drop.
 *
 * The section list in the Secciones tab is a vuedraggable bound to the
 * commercial sections; dropping an item POSTs the permuted order slots to
 * proposals/:id/reorder-sections/ and snaps back on failure.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_SECTION_REORDER } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;

function buildProposal() {
  return {
    id: PROPOSAL_ID,
    uuid: '11111111-1111-1111-1111-111111111111',
    title: 'Reorder Test',
    client_name: 'Client',
    client_email: 'client@test.com',
    language: 'es',
    status: 'draft',
    total_investment: '1000000',
    currency: 'COP',
    sections: [
      { id: 1, section_type: 'greeting', title: 'Saludo', order: 0, is_enabled: true, is_wide_panel: false, content_json: {} },
      { id: 2, section_type: 'executive_summary', title: 'Resumen', order: 1, is_enabled: true, is_wide_panel: false, content_json: {} },
      { id: 3, section_type: 'timeline', title: 'Cronograma', order: 2, is_enabled: true, is_wide_panel: false, content_json: {} },
    ],
    requirement_groups: [],
    change_logs: [],
  };
}

function buildHandler({ reorderStatus = 200, capturedReorders = null } = {}) {
  return async ({ route, apiPath }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { id: 8600, username: 'admin', is_staff: true } }),
      };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(buildProposal()) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/reorder-sections/`) {
      if (capturedReorders) capturedReorders.push(route.request().postDataJSON());
      if (reorderStatus !== 200) {
        return { status: reorderStatus, contentType: 'application/json', body: JSON.stringify({ error: 'boom' }) };
      }
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ reordered: 3 }) };
    }
    return null;
  };
}

/** Manual mouse drag — sortablejs does not react to Playwright's dragTo. */
async function dragHandleOnto(page, fromType, toType) {
  const source = page.getByTestId(`section-drag-handle-${fromType}`);
  const target = page.getByTestId(`section-header-${toType}`);
  const sourceBox = await source.boundingBox();
  const targetBox = await target.boundingBox();
  await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2, { steps: 12 });
  await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height + 5, { steps: 6 });
  await page.mouse.up();
}

async function openSectionsTab(page) {
  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
  await selectProposalDestination(page, 'proposal', 'sections');
  await page.getByTestId('section-header-greeting').waitFor({ state: 'visible' });
}

test.describe('Admin Proposal Section Reorder', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8600, role: 'admin', is_staff: true } });
  });

  test('dragging a section posts the permuted order slots', {
    tag: [...ADMIN_PROPOSAL_SECTION_REORDER, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await mockApi(page, buildHandler({ capturedReorders: captured }));
    await openSectionsTab(page);

    await dragHandleOnto(page, 'greeting', 'executive_summary');

    await expect.poll(() => captured.length, { timeout: 10_000 }).toBeGreaterThan(0);
    const payload = captured[0];
    expect(Array.isArray(payload.sections)).toBe(true);
    const byId = Object.fromEntries(payload.sections.map((s) => [s.id, s.order]));
    // greeting (id 1) moved below executive_summary (id 2): slots swap.
    expect(byId[1]).toBe(1);
    expect(byId[2]).toBe(0);
    expect(byId[3]).toBe(2);
  });

  test('failed reorder snaps the list back and notifies', {
    tag: ['@outcome:failure', ...ADMIN_PROPOSAL_SECTION_REORDER, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await mockApi(page, buildHandler({ reorderStatus: 500, capturedReorders: captured }));
    await openSectionsTab(page);

    await dragHandleOnto(page, 'greeting', 'executive_summary');
    await expect.poll(() => captured.length, { timeout: 10_000 }).toBeGreaterThan(0);

    await expect(page.getByText('No se pudo reordenar las secciones')).toBeVisible();
    // Snap-back: greeting is first again.
    const headers = page.locator('[data-testid^="section-header-"]');
    await expect(headers.first()).toHaveAttribute('data-testid', 'section-header-greeting');
  });
});
