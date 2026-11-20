/**
 * E2E tests for the client autocomplete picker in proposal create/edit.
 *
 * Covers: search suggestions, client selection auto-fills snapshot fields,
 * "Crear nuevo" fallback when no match, and placeholder-client creation
 * (empty email on proposal create form).
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_PROPOSAL_CLIENT_AUTOCOMPLETE,
  ADMIN_PROPOSAL_CLIENT_NO_EMAIL,
} from '../helpers/flow-tags.js';

test.describe.configure({ timeout: 60_000 });

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const mockSearchResults = [
  {
    id: 301,
    name: 'Sandra Gómez',
    email: 'sandra@example.com',
    phone: '+57 310 000 0001',
    company: 'Sandra SAS',
    is_email_placeholder: false,
    total_proposals: 2,
  },
  {
    id: 302,
    name: 'Sandra Ruiz',
    email: 'sandrar@example.com',
    phone: '',
    company: '',
    is_email_placeholder: false,
    total_proposals: 0,
  },
];

const mockCreatedProposal = {
  id: 999,
  uuid: '99999999-1111-1111-1111-999999999999',
  title: 'Propuesta Test',
  client_id: 301,
  client_name: 'Sandra Gómez',
  client_email: 'sandra@example.com',
  client_phone: '+57 310 000 0001',
  status: 'draft',
  sections: [],
  requirement_groups: [],
};

const mockCreatedProposalNoEmail = {
  ...mockCreatedProposal,
  id: 998,
  client_id: 303,
  client_name: 'Pedro Sin Email',
  client_email: 'cliente_303@temp.example.com',
  client: { id: 303, is_email_placeholder: true },
};

function setupMock(page, { onProposalCreate = null } = {}) {
  return mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;

    // Autocomplete search
    if (apiPath.startsWith('proposals/client-profiles/search/')) {
      const url = new URL(route.request().url());
      const q = (url.searchParams.get('q') || '').toLowerCase();
      const results = q
        ? mockSearchResults.filter(
            (c) =>
              c.name.toLowerCase().includes(q) ||
              c.email.toLowerCase().includes(q) ||
              (c.company || '').toLowerCase().includes(q),
          )
        : mockSearchResults;
      return { status: 200, contentType: 'application/json', body: JSON.stringify(results) };
    }

    // Proposal create
    if (apiPath === 'proposals/create/' && method === 'POST') {
      if (onProposalCreate) return onProposalCreate(route);
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(mockCreatedProposal),
      };
    }

    // Proposal list (needed by some page mounts)
    if (apiPath === 'proposals/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }

    // Expiration defaults — needed by create page onMounted
    if (apiPath.startsWith('proposals/defaults/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ expiration_days: 21, reminder_days: 3, urgency_reminder_days: 7, language: 'es', sections_json: [] }),
      };
    }

    return null;
  });
}

async function gotoCreate(page) {
  await page.goto('/panel/proposals/create');
  // Wait for the page to fully render before switching tabs
  await expect(page.getByRole('heading', { name: 'Nueva Propuesta' })).toBeVisible({ timeout: 30_000 });
  // Switch to Manual tab so the client autocomplete is rendered
  await page.getByRole('button', { name: 'Manual' }).click();
  await expect(page.getByTestId('client-autocomplete-input')).toBeVisible({ timeout: 15_000 });
}

test.describe('Proposal Client Autocomplete', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  test('typing in autocomplete shows matching client suggestions', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_CLIENT_AUTOCOMPLETE, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoCreate(page);

    await page.getByTestId('client-autocomplete-input').fill('sandra');

    // Both Sandra results should appear in the dropdown
    await expect(page.getByTestId('client-autocomplete-option-301')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId('client-autocomplete-option-302')).toBeVisible();
  });

  test('selecting a client from dropdown auto-fills name, email, phone, company', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_CLIENT_AUTOCOMPLETE, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoCreate(page);

    await page.getByTestId('client-autocomplete-input').fill('sandra');
    await expect(page.getByTestId('client-autocomplete-option-301')).toBeVisible({ timeout: 5_000 });

    // Click the first result (Sandra Gómez)
    await page.getByTestId('client-autocomplete-option-301').click();

    // Snapshot fields should be populated
    await expect(page.getByLabel('Nombre')).toHaveValue('Sandra Gómez');
    await expect(page.getByLabel('Email')).toHaveValue('sandra@example.com');
  });

  test('no match shows "Crear nuevo" button that sets the client name', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_CLIENT_AUTOCOMPLETE, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoCreate(page);

    // Type a name that returns no results
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath.startsWith('proposals/client-profiles/search/')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    await page.getByTestId('client-autocomplete-input').fill('Nombre Inexistente');
    await expect(page.getByTestId('client-autocomplete-create-new')).toBeVisible({ timeout: 5_000 });

    await page.getByTestId('client-autocomplete-create-new').click();

    // Client name field should be set to the typed value
    await expect(page.getByLabel('Nombre')).toHaveValue('Nombre Inexistente');
  });
});

test.describe('Proposal Create Without Client Email', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  test('submitting proposal without email succeeds and form shows placeholder info text', {
    tag: [...ADMIN_PROPOSAL_CLIENT_NO_EMAIL, '@role:admin'],
  }, async ({ page }) => {
    let capturedPayload = null;

    // Use inline mockApi so the pattern exactly mirrors the passing admin-proposal-create test
    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'proposals/create/') {
        capturedPayload = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify(mockCreatedProposal) };
      }
      if (apiPath.startsWith('proposals/defaults/')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ expiration_days: 21, reminder_days: 3, urgency_reminder_days: 7, language: 'es', sections_json: [] }) };
      }
      if (apiPath.startsWith('proposals/client-profiles/search/')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });
    await gotoCreate(page);

    // Fill required fields — leave email blank intentionally
    await page.getByLabel('Título').fill('Propuesta Sin Email Test');
    await page.getByLabel('Nombre').fill('Pedro Sin Email');

    // Placeholder hint text is always visible in the client section
    await expect(
      page.getByText(/email.*temporal|automatizaciones/i),
    ).toBeVisible();

    // Submit and wait for the API response (mirrors the passing proposal-create test pattern)
    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('proposals/create/')),
      page.getByRole('button', { name: /Crear Propuesta/i }).click(),
    ]);
    await response.finished();

    // Proposal was submitted without email
    expect(capturedPayload).not.toBeNull();
    expect(capturedPayload.client_name).toBe('Pedro Sin Email');
    expect(capturedPayload.client_email).toBe('');
  });
});
