import { execSync } from 'child_process';
import { chromium } from '@playwright/test';
import { mockApi } from './helpers/api.js';
import { waitForNuxtApp } from './helpers/navigation.js';
import { getResponsiveBatch, getResponsiveScenario } from './responsive/catalog-scenarios.js';

const WARMUP_UUID = '11111111-1111-4111-8111-111111111111';
const RESPONSIVE_WARMUP_ROUTES = Object.freeze({
  'frontend/pages/panel/documents/index.vue': ['/en-us/panel/documents'],
  'frontend/pages/panel/documents/create.vue': [
    '/en-us/panel/documents',
    '/en-us/panel/documents/create',
  ],
  'frontend/pages/panel/documents/[id]/edit.vue': [
    '/en-us/panel/documents',
    '/en-us/panel/documents/1/edit',
  ],
  'frontend/pages/panel/documents/statuses.vue': [
    '/en-us/panel/documents',
    '/en-us/panel/documents/statuses',
  ],
  'frontend/pages/platform/projects/[id]/ideas.vue': [
    '/es-co/platform/projects',
    '/es-co/platform/projects/1',
    '/es-co/platform/projects/1/ideas',
  ],
  'frontend/pages/panel/projects/[id]/ideas.vue': [
    '/en-us/panel/projects',
    '/en-us/panel/projects/1/ideas',
  ],
  'frontend/pages/portfolio-works/[slug].vue': [
    '/en-us/portfolio-works',
    '/en-us/portfolio-works/responsive-fixture',
  ],
  'frontend/pages/proposal/[uuid]/index.vue': [`/en-us/proposal/${WARMUP_UUID}`],
  'frontend/pages/diagnostic/[uuid]/index.vue': [`/en-us/diagnostic/${WARMUP_UUID}`],
});
const RESPONSIVE_SPECIAL_WARMUP_ROUTES = Object.freeze({
  'accounting-special': [
    '/en-us/panel/accounting/pocket',
    '/en-us/panel/accounting/collections',
    '/en-us/panel/accounting/incomes',
  ],
  'accounting-special-2': [
    '/en-us/panel/accounting/collections',
    '/en-us/panel/accounting/incomes',
  ],
  'accounting-special-3': [
    '/en-us/panel/accounting/hostings',
    '/en-us/panel/accounting/statements',
  ],
  'accounting-special-4': ['/en-us/panel/accounting'],
  'canvas-special': ['/en-us/panel/documents/1/edit'],
  'clients-special': ['/en-us/panel/clients'],
  'clients-special-2': [
    '/es-co/platform/projects',
    '/es-co/platform/projects/1',
    '/es-co/platform/projects/1/access',
  ],
  'commercial-special': ['/en-us/panel/proposals'],
  'communications-special': ['/en-us/panel/communications'],
  'documents-special': ['/en-us/panel/documents'],
  'emails-special': ['/en-us/panel/emails'],
  'mcp-special': ['/en-us/panel/mcps'],
  'projects-special': ['/en-us/panel/projects'],
  'public-special': [`/en-us/proposal/${WARMUP_UUID}`],
});
const json = (body) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const warmupModule = {
  slug: 'warmup-module',
  icon: '◫',
  name: 'Warmup module',
  summary: 'Deterministic browser warmup fixture.',
  what_is: 'Warmup fixture.',
  purpose: 'Compile and hydrate the public route.',
  problems_solved: [],
  integrations: [],
  implementation_requirements: [],
};
const warmupCatalog = {
  language: 'en',
  total_modules: 1,
  categories: [{ slug: 'warmup', name: 'Warmup', modules: [warmupModule] }],
};
const warmupProposal = {
  id: 1,
  uuid: WARMUP_UUID,
  title: 'Warmup proposal',
  client_name: 'Warmup client',
  status: 'sent',
  language: 'en',
  total_investment: '0',
  currency: 'COP',
  requirement_groups: [],
  sections: [],
};
const warmupDiagnostic = {
  uuid: WARMUP_UUID,
  title: 'Warmup diagnostic',
  client_name: 'Warmup client',
  status: 'sent',
  language: 'en',
  sections: [],
  render_context: { client_name: 'Warmup client', currency: 'COP' },
};
const warmupAdminCategory = { id: 1, slug: 'warmup', name_es: 'Calentamiento', name_en: 'Warmup', is_active: true, order: 1 };
const warmupAdminModule = { id: 1, category: 1, slug: 'warmup-module', name_es: 'Módulo de calentamiento', name_en: 'Warmup module', summary_es: 'Fixture determinista.', summary_en: 'Deterministic fixture.', is_active: true, order: 1 };
const warmupProposalDefaults = { id: 1, language: 'es', sections_json: [], default_slug_pattern: '{client_name}', default_expiration_days: 21, default_reminder_days: 7, default_urgency_reminder_days: 14, created_at: null, updated_at: null };
const warmupDocument = { id: 1, title: 'Warmup document', status: 'draft', content_markdown: '# Warmup', client: null, project: null, language: 'es', template_style: 'professional', created_at: '2026-01-01T00:00:00Z' };

function warmupApiFixture({ apiPath, method }) {
  if (apiPath === 'auth/check/' && method === 'GET') {
    return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
  }
  if (apiPath === 'accounts/me/' && method === 'GET') {
    return json({
      id: 9001,
      user_id: 9001,
      email: 'admin@e2e-test.com',
      role: 'admin',
      is_onboarded: true,
      profile_completed: true,
    });
  }
  if (apiPath === 'accounts/projects/' && method === 'GET') {
    return json([]);
  }
  if (apiPath === 'projects/' && method === 'GET') {
    // The panel endpoint returns an envelope; an array leaves records undefined
    // and can prevent the required warmup page from mounting.
    return json({ results: [], meta: {
      total: 0, by_state: [], review_required: 0,
      clients_without_projects: 0, records_without_project: 0,
    } });
  }
  if (apiPath === 'accounts/projects/1/' && method === 'GET') {
    return json({ id: 1, name: 'Warmup project', status_label: 'Activo', current_state: { color: 'emerald', operational_effect: 'operating' } });
  }
  if (/^(?:accounts\/)?projects\/1\/(?:ideas|idea-collections)\/$/.test(apiPath) && method === 'GET') {
    return json({ results: [], count: 0, page: 1, page_size: 20, total_pages: 1 });
  }
  if (apiPath === 'accounts/projects/1/access/' && method === 'GET') {
    return json({
      project: { id: 1, name: 'Warmup project', client_name: 'Warmup client' },
      repository_url: '', legacy_access: null, notes: [],
      environments: ['production', 'staging'].map((environment) => ({
        environment, label: environment, site_url: '', admin_url: '',
        admin_username: '', has_password: false, updated_at: null, updated_by: '',
      })),
    });
  }
  if (apiPath === 'accounts/projects/1/access/client-policy/' && method === 'GET') {
    const permissions = Object.fromEntries(['production', 'staging'].map((environment) => (
      [environment, { site_url: false, admin_url: false, admin_username: false, admin_password: false }]
    )));
    return json({ project_id: 1, version: 0, permissions, effective_permissions: permissions,
      available_fields: permissions, source_token: 'warmup' });
  }
  if (/^accounts\/projects\/1\/(?:phases|requirements|bug-reports|change-requests|collection-accounts|data-model-entities|deliverables)\/$/.test(apiPath) && method === 'GET') {
    return json([]);
  }
  if (apiPath === 'accounts/projects/1/subscription/' && method === 'GET') {
    return json({ id: 1, plan: 'quarterly', plan_display: 'Trimestral', status: 'active', status_display: 'Activa', start_date: '2026-01-01', next_billing_date: '2026-04-01', billing_amount: '0', payments: [] });
  }
  if (apiPath === 'accounts/documents/' && method === 'GET') {
    return json({ documents: [], email: 'warmup@e2e.test', email_verified: true });
  }
  if (/^accounts\/(?:notifications|clients)\/$/.test(apiPath) && method === 'GET') {
    return json([]);
  }
  if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
    return json({ unread_count: 0 });
  }
  if (apiPath === 'additional-modules/public/' && method === 'GET') {
    return json(warmupCatalog);
  }
  if (apiPath === 'additional-modules/admin/' && method === 'GET') {
    return json({ categories: [warmupAdminCategory], modules: [warmupAdminModule], revision: 'warmup' });
  }
  if (apiPath === 'additional-modules/admin/shares/' && method === 'GET') {
    return json([]);
  }
  if (/^additional-modules\/public\/shares\/[^/]+\/$/.test(apiPath) && method === 'GET') {
    return json({ ...warmupCatalog, is_shared: true });
  }
  if (/^additional-modules\/public\/shares\/[^/]+\/track\/$/.test(apiPath) && method === 'POST') {
    return json({ status: 'recorded' });
  }
  if (apiPath === 'proposals/' && method === 'GET') {
    return json([warmupProposal]);
  }
  if (apiPath === 'proposals/alerts/' && method === 'GET') {
    return json([]);
  }
  if (apiPath === 'proposals/defaults/' && method === 'GET') {
    return json(warmupProposalDefaults);
  }
  if (apiPath === 'email-templates/' && method === 'GET') {
    return json([]);
  }
  if (apiPath.startsWith('proposals/client-profiles/') && method === 'GET') {
    return json([]);
  }
  if (apiPath === 'diagnostics/' && method === 'GET') {
    return json([{ id: 1, ...warmupDiagnostic, status: 'draft' }]);
  }
  if ((apiPath === 'diagnostics/1/' || apiPath === 'diagnostics/1/detail/') && method === 'GET') {
    return json({ id: 1, ...warmupDiagnostic, status: 'draft' });
  }
  if (apiPath === 'diagnostics/defaults/' && method === 'GET') {
    return json({ language: 'es', default_currency: 'COP', default_slug_pattern: '{client_name}', payment_initial_pct: 50, payment_final_pct: 50 });
  }
  if (apiPath.startsWith('accounts/saved-filter-tabs') && method === 'GET') {
    return json([]);
  }
  if (apiPath === 'documents/' && method === 'GET') {
    return json([warmupDocument]);
  }
  if (apiPath === 'documents/1/detail/' && method === 'GET') {
    return json(warmupDocument);
  }
  if (/^document-(?:folders|tags|states|state-groups)\/$/.test(apiPath) && method === 'GET') {
    return json([]);
  }
  if (apiPath.startsWith('accounting/projects/') && method === 'GET') {
    return json({ results: [] });
  }
  if (apiPath === 'emails/defaults/' && method === 'GET') {
    return json({ greeting: 'Hello', footer: 'ProjectApp', config: { greeting: 'Hello {client_name}', footer: 'ProjectApp', signer: 'projectapp' }, defaults: {}, available_signers: [] });
  }
  if (apiPath === 'emails/history/' && method === 'GET') {
    return json({ results: [], total: 0, page: 1, has_next: false });
  }
  if (apiPath === 'email-deliverability/' && method === 'GET') {
    return json({ total_emails_30d: 0, success_rate: 0, sent_count: 0, failed_count: 0, by_template: [], daily_trend: [], recent_failures: [] });
  }
  if (/^proposals\/(?:by-slug\/)?[^/]+\/$/.test(apiPath) && method === 'GET') {
    return json(warmupProposal);
  }
  if (/^diagnostics\/public\/(?:by-slug\/)?[^/]+\/$/.test(apiPath) && method === 'GET') {
    return json(warmupDiagnostic);
  }
  if (/^diagnostics\/public\/[^/]+\/track(?:-section)?\/$/.test(apiPath) && method === 'POST') {
    return json({ ok: true, view_count: 1 });
  }
  return null;
}

/**
 * Playwright globalSetup — ensures Chromium is installed before any test runs
 * and pre-warms the Nuxt dev server so first-visit compilation doesn't cause timeouts.
 *
 * SPA routes (ssr: false) need a real browser visit to trigger Vite on-demand
 * compilation — plain HTTP fetch only gets the HTML shell without compiling
 * the client-side route modules.
 */
export default async function globalSetup() {
  execSync('npx playwright install chromium', { stdio: 'inherit' });

  const PORT = process.env.E2E_PORT ? Number(process.env.E2E_PORT) : 3000;
  const baseURL = process.env.E2E_BASE_URL || `http://localhost:${PORT}`;

  // Routes to warm up — includes SSR and SPA routes.
  // A responsive batch warms only the at-most-four resolved catalog routes;
  // otherwise every small CI shard paid the cost of compiling the full app.
  const defaultWarmupRoutes = [
    '/',                                    // SSR — triggers initial Vite client build
    '/en-us/panel/projects',
    '/en-us/panel/accounting/hostings',
    '/en-us/panel/accounting/incomes',
    '/en-us/panel/accounting/collections',
    '/en-us/platform/login',
    '/en-us/platform/dashboard',
    '/en-us/platform/projects',
    '/en-us/platform/projects/1',
    '/en-us/platform/projects/1/board',
    '/panel/login',                         // SPA — admin panel login
    '/panel',                               // SPA — admin dashboard
    '/panel/admins',                        // SPA — admin management
    '/es-co/panel/additional-modules',      // SPA — reusable sales catalog
    '/panel/blog',                          // SPA — blog list
    '/panel/blog/create',                   // SPA — blog create
    '/panel/blog/1/edit',                   // SPA — blog edit (dynamic)
    '/panel/blog/calendar',                 // SPA — blog calendar
    '/panel/clients',                       // SPA — client list
    '/panel/communications',                // SPA — client communications registry
    '/panel/defaults',                      // SPA — defaults
    '/panel/diagnostics',                   // SPA — diagnostics list
    '/panel/diagnostics/create',            // SPA — diagnostic create
    '/panel/diagnostics/defaults',          // SPA — diagnostic defaults
    '/panel/diagnostics/7/edit',            // SPA — diagnostic edit (dynamic)
    '/panel/documents',                     // SPA — documents list
    '/panel/documents/create',              // SPA — document create
    '/panel/documents/1/edit',              // SPA — document edit (dynamic)
    '/panel/emails',                        // SPA — email templates
    '/panel/portfolio',                     // SPA — portfolio list
    '/panel/portfolio/create',              // SPA — portfolio create
    '/panel/portfolio/1/edit',              // SPA — portfolio edit (dynamic)
    '/es-co/panel/proposals',               // SPA — proposals list
    '/panel/proposals/create',              // SPA — create proposal
    '/panel/proposals/999/edit',            // SPA — edit proposal (dynamic)
    '/panel/proposals/defaults',            // SPA — proposal defaults
    '/panel/proposals/email-deliverability', // SPA — email deliverability
    '/panel/tasks',                         // SPA — task list
    '/panel/views',                         // SPA — admin view map
    '/proposal/warmup-prefetch',            // SPA — proposal viewer
    '/diagnostic/warmup-prefetch',          // SPA — diagnostic public viewer
    '/es-co/additional-modules',            // SSR — public additional modules catalog
    '/es-co/additional-modules/share/11111111-1111-4111-8111-111111111111', // SPA — shared catalog
    '/blog',                                // SSR — public blog list
    '/landing-apps',                        // SSR — landing apps page
    '/landing-software',                    // SSR — landing software page
    '/landing-web-design',                  // SSR — landing web design page
  ];

  const defaultRequiredWarmupRoutes = new Set([
    '/en-us/panel/projects',
    '/en-us/panel/accounting/hostings',
    '/en-us/panel/accounting/incomes',
    '/en-us/panel/accounting/collections',
    '/en-us/platform/login',
    '/en-us/platform/projects/1',
  ]);
  const responsiveBatchId = process.env.E2E_RESPONSIVE_BATCH;
  const responsiveSpecialOwner = process.env.E2E_RESPONSIVE_SPECIAL_OWNER;
  const responsiveSpecialBatchId = process.env.E2E_RESPONSIVE_SPECIAL_BATCH;
  const responsiveBatch = responsiveBatchId ? getResponsiveBatch(responsiveBatchId) : null;
  if (responsiveBatchId && !responsiveBatch) {
    throw new Error(`Unknown responsive batch: ${responsiveBatchId}`);
  }
  if (responsiveSpecialBatchId && !RESPONSIVE_SPECIAL_WARMUP_ROUTES[responsiveSpecialBatchId]) {
    throw new Error(`Unknown responsive special warmup batch: ${responsiveSpecialBatchId}`);
  }
  const warmupRoutes = responsiveBatch
    ? [...new Set(responsiveBatch.scenarioKeys.flatMap((key) => (
      RESPONSIVE_WARMUP_ROUTES[key]
        ?? [getResponsiveScenario(key)?.resolvedUrl].filter(Boolean)
    )))]
    : (responsiveSpecialOwner
      ? (RESPONSIVE_SPECIAL_WARMUP_ROUTES[responsiveSpecialBatchId] ?? ['/'])
      : defaultWarmupRoutes);
  const requiredWarmupRoutes = responsiveBatch || responsiveSpecialOwner
    ? new Set(warmupRoutes)
    : defaultRequiredWarmupRoutes;
  const warmupFailures = [];

  let browser;
  try {
    browser = await chromium.launch();
    const page = await browser.newPage();
    await page.addInitScript(() => {
      const admin = {
        id: 9001,
        user_id: 9001,
        email: 'admin@e2e-test.com',
        role: 'admin',
        is_staff: true,
        is_superuser: true,
        is_onboarded: true,
        profile_completed: true,
      };
      localStorage.setItem('access_token', 'e2e-warmup-panel-token');
      localStorage.setItem('refresh_token', 'e2e-warmup-panel-refresh');
      localStorage.setItem('user', JSON.stringify(admin));
      localStorage.setItem('platform_access_token', 'e2e-warmup-platform-token');
      localStorage.setItem('platform_refresh_token', 'e2e-warmup-platform-refresh');
      localStorage.setItem('platform_user', JSON.stringify(admin));
      localStorage.setItem('preferred_locale', 'en-us');
    });
    await mockApi(page, warmupApiFixture);
    for (const route of warmupRoutes) {
      const isRequired = requiredWarmupRoutes.has(route);
      try {
        const attempts = isRequired ? 2 : 1;
        let lastError;
        for (let attempt = 0; attempt < attempts; attempt += 1) {
          try {
            await page.goto(`${baseURL}${route}`, {
              timeout: isRequired ? 45_000 : 10_000,
              waitUntil: 'domcontentloaded',
            });
            if (isRequired) {
              await waitForNuxtApp(page, { timeout: attempt === 0 ? 15_000 : 45_000 });
            }
            lastError = null;
            break;
          } catch (error) {
            lastError = error;
          }
        }
        if (lastError) throw lastError;
      } catch (error) {
        if (isRequired) {
          const message = error instanceof Error ? error.message : String(error);
          warmupFailures.push(`${route}: ${message}`);
        }
      }
    }
    await page.close();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    warmupFailures.push(`browser: ${message}`);
  } finally {
    if (browser) await browser.close();
  }

  if (warmupFailures.length > 0) {
    throw new Error(`Required Nuxt warmup failed:\n${warmupFailures.join('\n')}`);
  }
}
