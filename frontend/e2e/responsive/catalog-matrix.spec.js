/**
 * Compatibility matrix for catalog redirects.
 *
 * R-catalog-redirect-01: a legacy route can silently lose its destination or
 * query while representative layout specs remain green. Redirects deliberately
 * do not claim visual responsive coverage; they only prove compatibility.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { setPlatformAuth } from '../helpers/platform-auth.js';
import { viewportUse } from '../helpers/viewports.js';
import {
  ADMIN_DEFAULTS_UNIFIED,
  ADMIN_IMPERSONATE_USER,
  PLATFORM_DELIVERABLE_DETAIL,
  PLATFORM_LEGACY_ROUTE_REDIRECTS,
} from '../helpers/flow-tags.js';
import {
  RESPONSIVE_PROFILES,
  batchForScenario,
  responsiveCatalogScenarios,
} from './catalog-scenarios.js';

const requestedBatch = process.env.E2E_RESPONSIVE_BATCH;
const redirectByUrl = new Map(
  responsiveCatalogScenarios
    .filter((scenario) => scenario.kind === 'redirect')
    .map((scenario) => [scenario.url, scenario]),
);

function redirectScenario(url) {
  const scenario = redirectByUrl.get(url);
  if (!scenario) throw new Error(`Falta el redirect catalogado para ${url}`);
  return scenario;
}

const legacyPlatformRedirects = Object.freeze([
  redirectScenario('/platform'),
  redirectScenario('/platform/dashboard'),
  redirectScenario('/platform/board'),
  redirectScenario('/platform/bugs'),
  redirectScenario('/platform/changes'),
  redirectScenario('/platform/deliverables'),
  redirectScenario('/platform/access'),
]);
const proposalEmailTemplatesRedirect = redirectScenario('/panel/proposals/email-templates');
const proposalDefaultsRedirect = redirectScenario('/panel/proposals/defaults');
const diagnosticDefaultsRedirect = redirectScenario('/panel/diagnostics/defaults');
const deliverableRedirect = redirectScenario('/platform/projects/:id/deliverables/:deliverableId');
const adminLoginRedirect = redirectScenario('/platform/admin-login');
const projectBoardRedirect = redirectScenario('/platform/projects/:id/board');
const partnershipRedirects = [
  '/panel/financing', '/panel/financing/new', '/panel/financing/:id',
].map(redirectScenario);

function belongsToRequestedBatch(scenario) {
  return !requestedBatch || batchForScenario(scenario.catalogKey) === requestedBatch;
}

function redirectTags(scenario, profile) {
  return [
    `@responsive:${scenario.owner}`,
    `@responsive-scenario:${scenario.catalogKey}`,
    '@responsive-redirect',
    `@responsive-batch:${batchForScenario(scenario.catalogKey)}`,
    `@viewport:${profile}`,
  ];
}

async function setSessionForRedirect(page, scenario) {
  if (scenario.url === '/platform/admin-login') {
    return;
  }

  if (scenario.url === '/platform' || scenario.url.startsWith('/platform/')) {
    await setPlatformAuth(page);
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'accounts/me/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 9001, role: 'admin', is_onboarded: true, profile_completed: true }),
        };
      }
      return null;
    });
    return;
  }

  await setAuthLocalStorage(page, {
    token: 'responsive-admin-token',
    userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
  });
  await mockApi(page, async ({ apiPath }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { username: 'responsive-admin', is_staff: true, is_superuser: true } }),
      };
    }
    return null;
  });
}

async function navigateCompatibilityRedirect(page, scenario) {
  // quality: allow-deep-link (a compatibility redirect starts from a legacy bookmark/link, not a panel control)
  // quality: allow-no-interaction (browser navigation invokes this route-only compatibility behavior)
  await setSessionForRedirect(page, scenario);
  await page.goto(scenario.resolvedUrl, { waitUntil: 'domcontentloaded' });
  const finalUrl = new URL(page.url());
  return `${finalUrl.pathname}${finalUrl.search}`;
}

function redirectUrlPattern(scenario) {
  return new RegExp(`${scenario.expected.url.replace(/[?]/g, '\\?')}$`);
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`catalog redirect compatibility · ${profile}`, {
    tag: [`@viewport:${profile}`],
  }, () => {
    test.use(viewportUse(profile));

    if (belongsToRequestedBatch(projectBoardRedirect)) {
      test('the former project board opens its delivery workspace', {
        tag: [...PLATFORM_LEGACY_ROUTE_REDIRECTS, '@outcome:success', ...redirectTags(projectBoardRedirect, profile)],
      }, async ({ page }) => {
        // quality: allow-no-interaction (an old project bookmark invokes the compatibility redirect)
        await navigateCompatibilityRedirect(page, projectBoardRedirect);
        await expect(page).toHaveURL(redirectUrlPattern(projectBoardRedirect));
      });
    }

    for (const scenario of partnershipRedirects.filter(belongsToRequestedBatch)) {
      test(`partnership alias ${scenario.url} retains its destination`, {
        tag: ['@flow:admin-partnership-legacy-redirects', '@outcome:success', ...redirectTags(scenario, profile)],
      }, async ({ page }) => {
        // quality: allow-no-interaction (opening a legacy bookmark invokes the compatibility redirect)
        await navigateCompatibilityRedirect(page, scenario);
        await expect(page).toHaveURL(redirectUrlPattern(scenario));
      });
    }

    test.describe('platform legacy aliases', () => {
      if (belongsToRequestedBatch(legacyPlatformRedirects[0])) {
        test('platform root retains the projects destination', { tag: [...PLATFORM_LEGACY_ROUTE_REDIRECTS, '@outcome:success', ...redirectTags(legacyPlatformRedirects[0], profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, legacyPlatformRedirects[0]);
          await expect(page).toHaveURL(redirectUrlPattern(legacyPlatformRedirects[0]));
        });
      }
      if (belongsToRequestedBatch(legacyPlatformRedirects[1])) {
        test('platform dashboard retains the projects destination', { tag: [...PLATFORM_LEGACY_ROUTE_REDIRECTS, '@outcome:success', ...redirectTags(legacyPlatformRedirects[1], profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, legacyPlatformRedirects[1]);
          await expect(page).toHaveURL(redirectUrlPattern(legacyPlatformRedirects[1]));
        });
      }
      if (belongsToRequestedBatch(legacyPlatformRedirects[2])) {
        test('platform board retains the projects destination', { tag: [...PLATFORM_LEGACY_ROUTE_REDIRECTS, '@outcome:success', ...redirectTags(legacyPlatformRedirects[2], profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, legacyPlatformRedirects[2]);
          await expect(page).toHaveURL(redirectUrlPattern(legacyPlatformRedirects[2]));
        });
      }
      if (belongsToRequestedBatch(legacyPlatformRedirects[3])) {
        test('platform bugs retains the projects destination', { tag: [...PLATFORM_LEGACY_ROUTE_REDIRECTS, '@outcome:success', ...redirectTags(legacyPlatformRedirects[3], profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, legacyPlatformRedirects[3]);
          await expect(page).toHaveURL(redirectUrlPattern(legacyPlatformRedirects[3]));
        });
      }
      if (belongsToRequestedBatch(legacyPlatformRedirects[4])) {
        test('platform changes retains the projects destination', { tag: [...PLATFORM_LEGACY_ROUTE_REDIRECTS, '@outcome:success', ...redirectTags(legacyPlatformRedirects[4], profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, legacyPlatformRedirects[4]);
          await expect(page).toHaveURL(redirectUrlPattern(legacyPlatformRedirects[4]));
        });
      }
      if (belongsToRequestedBatch(legacyPlatformRedirects[5])) {
        test('platform deliverables retains the projects destination', { tag: [...PLATFORM_LEGACY_ROUTE_REDIRECTS, '@outcome:success', ...redirectTags(legacyPlatformRedirects[5], profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, legacyPlatformRedirects[5]);
          await expect(page).toHaveURL(redirectUrlPattern(legacyPlatformRedirects[5]));
        });
      }
      if (belongsToRequestedBatch(legacyPlatformRedirects[6])) {
        test('platform access retains the projects destination', { tag: [...PLATFORM_LEGACY_ROUTE_REDIRECTS, '@outcome:success', ...redirectTags(legacyPlatformRedirects[6], profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, legacyPlatformRedirects[6]);
          await expect(page).toHaveURL(redirectUrlPattern(legacyPlatformRedirects[6]));
        });
      }
    });

    test.describe('unified defaults aliases', () => {
      if (belongsToRequestedBatch(proposalEmailTemplatesRedirect)) {
        test('proposal email templates retains its defaults query', { tag: [...ADMIN_DEFAULTS_UNIFIED, '@outcome:success', ...redirectTags(proposalEmailTemplatesRedirect, profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, proposalEmailTemplatesRedirect);
          await expect(page).toHaveURL(redirectUrlPattern(proposalEmailTemplatesRedirect));
        });
      }
      if (belongsToRequestedBatch(proposalDefaultsRedirect)) {
        test('proposal defaults retains its mode query', { tag: [...ADMIN_DEFAULTS_UNIFIED, '@outcome:success', ...redirectTags(proposalDefaultsRedirect, profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, proposalDefaultsRedirect);
          await expect(page).toHaveURL(redirectUrlPattern(proposalDefaultsRedirect));
        });
      }
      if (belongsToRequestedBatch(diagnosticDefaultsRedirect)) {
        test('diagnostic defaults retains its mode query', { tag: [...ADMIN_DEFAULTS_UNIFIED, '@outcome:success', ...redirectTags(diagnosticDefaultsRedirect, profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, diagnosticDefaultsRedirect);
          await expect(page).toHaveURL(redirectUrlPattern(diagnosticDefaultsRedirect));
        });
      }
    });

    test.describe('deliverable compatibility alias', () => {
      if (belongsToRequestedBatch(deliverableRedirect)) {
        test('deliverable detail retains the project resources destination', { tag: [...PLATFORM_DELIVERABLE_DETAIL, '@outcome:success', ...redirectTags(deliverableRedirect, profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (a legacy bookmark invokes a route-only compatibility redirect)
          await navigateCompatibilityRedirect(page, deliverableRedirect);
          await expect(page).toHaveURL(redirectUrlPattern(deliverableRedirect));
        });
      }
    });

    test.describe('admin login compatibility alias', () => {
      if (belongsToRequestedBatch(adminLoginRedirect)) {
        test('admin login without an exchange code reports its login error', { tag: [...ADMIN_IMPERSONATE_USER, '@outcome:error', ...redirectTags(adminLoginRedirect, profile)] }, async ({ page }) => {
          // quality: allow-no-interaction (the callback error renders after a route-only compatibility entry)
          await navigateCompatibilityRedirect(page, adminLoginRedirect);
          await expect(page).toHaveURL(redirectUrlPattern(adminLoginRedirect));
        });
      }
    });
  });
}
