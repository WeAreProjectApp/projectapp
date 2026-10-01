/**
 * The executable responsive matrix is deliberately derived from the same
 * catalog used by the product. `catalogKey` is the canonical page source path:
 * it is unique, stable across translated URLs, and lets the contract detect a
 * missing or duplicate view without inventing a second slug namespace.
 */
import { viewCatalogSections } from '../../config/viewCatalog.js';
import { responsiveOwnerForView } from '../../config/responsiveAcceptance.js';

export const RESPONSIVE_PROFILES = Object.freeze([
  'compact',
  'portrait',
  'landscape',
  'desktop',
  'wide',
]);

export const RESPONSIVE_SCENARIO_KINDS = Object.freeze(['visual', 'redirect']);

const OWNER_FLOW = Object.freeze({
  foundation: 'admin-view-map',
  accounting: 'admin-accounting-dashboard',
  documents: 'admin-document-list',
  clients: 'platform-project-list',
  projects: 'admin-project-change-client',
  communications: 'admin-client-communications',
  canvas: 'admin-document-edit',
  commercial: 'admin-proposal-list',
  emails: 'admin-email-deliverability',
  dashboard: 'admin-dashboard',
  content: 'admin-blog-list',
  mcp: 'admin-mcps',
  public: 'public-additional-modules-catalog',
});

const REDIRECT_DESTINATIONS = Object.freeze({
  '/panel/financing': '/panel/partnership-program',
  '/panel/financing/new': '/panel/partnership-program/new',
  '/panel/financing/:id': '/panel/partnership-program/1',
  '/panel/proposals/email-templates': '/panel/defaults?mode=proposal&tab=emails',
  '/panel/proposals/defaults': '/panel/defaults?mode=proposal',
  '/panel/diagnostics/defaults': '/panel/defaults?mode=diagnostic',
  '/platform/dashboard': '/platform/projects',
  '/platform/board': '/platform/projects',
  '/platform/projects/:id/board': '/platform/projects/1/delivery',
  '/platform/bugs': '/platform/projects',
  '/platform/changes': '/platform/projects',
  '/platform/deliverables': '/platform/projects',
  '/platform/payments': '/platform/projects',
  '/platform/access': '/platform/projects',
  '/platform/collection-accounts': '/platform/projects',
  '/platform/collection-accounts/:id': '/platform/projects',
  '/platform': '/platform/projects',
  '/platform/projects/:id/deliverables/:deliverableId': '/platform/projects/1/deliverables',
  '/platform/admin-login': '/platform/login',
});

/**
 * Redirects prove compatibility behavior, not the destination screen's user
 * flow. Keep this mapping explicit so a newly cataloged alias cannot silently
 * inherit an unrelated owner-level flow and inflate functional coverage.
 */
const REDIRECT_FLOW_BY_URL = Object.freeze({
  '/panel/financing': 'admin-partnership-legacy-redirects',
  '/panel/financing/new': 'admin-partnership-legacy-redirects',
  '/panel/financing/:id': 'admin-partnership-legacy-redirects',
  '/panel/proposals/email-templates': 'admin-defaults-unified',
  '/panel/proposals/defaults': 'admin-defaults-unified',
  '/panel/diagnostics/defaults': 'admin-defaults-unified',
  '/platform/dashboard': 'platform-legacy-route-redirects',
  '/platform/board': 'platform-legacy-route-redirects',
  '/platform/projects/:id/board': 'platform-legacy-route-redirects',
  '/platform/bugs': 'platform-legacy-route-redirects',
  '/platform/changes': 'platform-legacy-route-redirects',
  '/platform/deliverables': 'platform-legacy-route-redirects',
  '/platform/payments': 'platform-legacy-route-redirects',
  '/platform/access': 'platform-legacy-route-redirects',
  '/platform/collection-accounts': 'platform-legacy-route-redirects',
  '/platform/collection-accounts/:id': 'platform-legacy-route-redirects',
  '/platform': 'platform-legacy-route-redirects',
  '/platform/projects/:id/deliverables/:deliverableId': 'platform-deliverable-detail',
  '/platform/admin-login': 'admin-impersonate-user',
});

const REDIRECT_OUTCOME_BY_URL = Object.freeze({
  '/platform/admin-login': 'error',
});

const PROJECT_COLLABORATION_FLOW_BY_URL = Object.freeze({
  '/platform/projects/:id/ideas': 'platform-project-ideas',
  '/panel/projects/:id/ideas': 'admin-project-idea-collection',
});

function resolveCatalogUrl(url) {
  return url
    .replace(':deliverableId', '1')
    .replace(':id', '1')
    .replace(':uuid', '11111111-1111-4111-8111-111111111111')
    .replace(':handle', 'responsive-fixture')
    .replace(':slug*', 'responsive-not-found')
    .replace(':slug', 'responsive-fixture');
}

function defaultCapabilities(view, owner) {
  const text = `${view.group} ${view.reference} ${view.label}`.toLowerCase();
  return {
    panelShell: view.url.startsWith('/panel') && view.viewType !== 'auth',
    table: view.viewType === 'list',
    tabs: owner === 'accounting' || owner === 'clients' || owner === 'documents',
    filters: view.viewType === 'list',
    modal: owner === 'accounting' || owner === 'projects' || owner === 'commercial',
    selection: owner === 'commercial' || owner === 'documents',
    touch: /acciones|crear|editar|gestion|catalogo|listado/.test(text),
  };
}

const rawScenarios = viewCatalogSections.flatMap((section) => section.views.map((view) => {
  const owner = responsiveOwnerForView(section.id, view);
  const kind = view.viewType === 'redirect' ? 'redirect' : 'visual';
  const url = resolveCatalogUrl(view.url);
  const redirectUrl = REDIRECT_DESTINATIONS[view.url];

  return {
    // Do not replace this with the URL: parameterized URLs are not unique test identities.
    catalogKey: view.file,
    sectionId: section.id,
    owner,
    kind,
    url: view.url,
    resolvedUrl: url,
    audience: view.audience,
    viewType: view.viewType,
    label: view.label,
    reference: view.reference,
    flowId: kind === 'redirect' ? REDIRECT_FLOW_BY_URL[view.url]
      : PROJECT_COLLABORATION_FLOW_BY_URL[view.url]
        ?? (view.url === '/platform/projects/:id/delivery' ? 'platform-delivery-review' : OWNER_FLOW[owner]),
    outcome: kind === 'redirect' ? (REDIRECT_OUTCOME_BY_URL[view.url] ?? 'success') : 'display',
    profiles: RESPONSIVE_PROFILES,
    quality: kind === 'redirect' ? 'allow-deep-link' : 'allow-deep-link',
    expected: kind === 'redirect'
      ? Object.freeze({ url: redirectUrl })
      : Object.freeze({ text: view.reference }),
    capabilities: defaultCapabilities(view, owner),
  };
}));

/** Batches are deliberately ≤4 scenarios so a profile matrix is ≤20 tests. */
export const responsiveBatches = Object.freeze(
  Object.entries(rawScenarios.reduce((byOwnerKind, scenario) => {
    const key = `${scenario.owner}:${scenario.kind}`;
    byOwnerKind[key] ??= [];
    byOwnerKind[key].push(scenario);
    return byOwnerKind;
  }, {})).flatMap(([ownerAndKind, scenarios]) => (
    Array.from({ length: Math.ceil(scenarios.length / 4) }, (_, index) => {
      const [owner, kind] = ownerAndKind.split(':');
      const scenarioKeys = scenarios.slice(index * 4, (index + 1) * 4).map(({ catalogKey }) => catalogKey);
      return Object.freeze({ id: `${owner}-${kind}-${index + 1}`, owner, kind, scenarioKeys });
    })
  )),
);

const batchByScenarioKey = new Map(
  responsiveBatches.flatMap((batch) => batch.scenarioKeys.map((catalogKey) => [catalogKey, batch.id])),
);

export const responsiveCatalogScenarios = Object.freeze(rawScenarios.map((scenario) => Object.freeze({
  ...scenario,
  batch: batchByScenarioKey.get(scenario.catalogKey),
})));

const scenarioByKey = new Map(responsiveCatalogScenarios.map((scenario) => [scenario.catalogKey, scenario]));

export function getResponsiveScenario(catalogKey) {
  return scenarioByKey.get(catalogKey) ?? null;
}

export function getResponsiveBatch(batchId) {
  return responsiveBatches.find((batch) => batch.id === batchId) ?? null;
}

export function getResponsiveMatrixRows() {
  return responsiveCatalogScenarios.flatMap((scenario) => scenario.profiles.map((profile) => Object.freeze({
    catalogKey: scenario.catalogKey,
    sectionId: scenario.sectionId,
    owner: scenario.owner,
    kind: scenario.kind,
    profile,
    batch: batchByScenarioKey.get(scenario.catalogKey),
  })));
}

export function batchForScenario(catalogKey) {
  return batchByScenarioKey.get(catalogKey) ?? null;
}
