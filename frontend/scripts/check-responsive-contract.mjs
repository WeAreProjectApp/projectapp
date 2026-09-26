import { readdir, readFile } from 'node:fs/promises';
import { join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  RESPONSIVE_MODULES,
  RESPONSIVE_MODULE_NAMES,
  RESPONSIVE_VIEWPORT_NAMES,
  responsiveOwnerForView,
} from '../config/responsiveAcceptance.js';
import { PANEL_VIEWPORTS } from '../config/responsive.js';
import { viewCatalogSections } from '../config/viewCatalog.js';
import {
  RESPONSIVE_PROFILES,
  RESPONSIVE_SCENARIO_KINDS,
  getResponsiveMatrixRows,
  responsiveBatches,
  responsiveCatalogScenarios,
} from '../e2e/responsive/catalog-scenarios.js';

const frontendRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const repoRoot = resolve(frontendRoot, '..');
const responsiveSpecRoot = join(frontendRoot, 'e2e', 'responsive');

async function walkVueFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return walkVueFiles(path);
    return entry.isFile() && entry.name.endsWith('.vue') ? [path] : [];
  }));
  return files.flat();
}

function reportDifference(label, values) {
  if (!values.length) return;
  throw new Error(`${label}:\n- ${values.join('\n- ')}`);
}

const pages = (await walkVueFiles(join(frontendRoot, 'pages')))
  .map((path) => relative(repoRoot, path).replaceAll('\\', '/'))
  .sort();
const catalogEntries = viewCatalogSections.flatMap((section) => (
  section.views.map((view) => ({ sectionId: section.id, ...view }))
));
const catalogFiles = catalogEntries.map((view) => view.file).sort();

reportDifference('Páginas ausentes del catálogo', pages.filter((file) => !catalogFiles.includes(file)));
reportDifference('Entradas obsoletas del catálogo', catalogFiles.filter((file) => !pages.includes(file)));

const duplicates = [...new Set(catalogFiles.filter((file, index) => catalogFiles.indexOf(file) !== index))];
reportDifference('Páginas duplicadas en el catálogo', duplicates);

const panelPageSources = await Promise.all(
  pages
    .filter((file) => file.startsWith('frontend/pages/panel/'))
    .map(async (file) => ({ file, source: await readFile(join(repoRoot, file), 'utf8') })),
);
const localPanelBreakpoints = panelPageSources
  .filter(({ source }) => /window\.innerWidth|window\.matchMedia\s*\(/.test(source))
  .map(({ file }) => file);
reportDifference(
  'Páginas del panel con breakpoints JS locales; usar config/responsive.js y useIsMobile',
  localPanelBreakpoints,
);

const interactiveFiles = [
  ...await walkVueFiles(join(frontendRoot, 'components')),
  ...await walkVueFiles(join(frontendRoot, 'pages')),
];
const hoverOnlyControls = [];
for (const path of interactiveFiles) {
  const source = await readFile(path, 'utf8');
  for (const match of source.matchAll(/<(?:button|a)\b[\s\S]*?>/g)) {
    const openingTag = match[0];
    const hidesUntilHover = /opacity-0/.test(openingTag) && /group-hover(?:\/[^:]+)?:opacity-100/.test(openingTag);
    const hasAlternative = /touch-reveal|focus(?:-visible)?:opacity-100/.test(openingTag);
    if (hidesUntilHover && !hasAlternative) {
      const line = source.slice(0, match.index).split('\n').length;
      hoverOnlyControls.push(`${relative(repoRoot, path).replaceAll('\\', '/')}:${line}`);
    }
  }
}
reportDifference(
  'Controles ocultos hasta hover sin alternativa táctil o de foco',
  hoverOnlyControls,
);

const viewportWidths = RESPONSIVE_VIEWPORT_NAMES.map((name) => PANEL_VIEWPORTS[name].width);
const expectedWidths = [412, 835, 1195, 1440, 2560];
if (JSON.stringify(viewportWidths) !== JSON.stringify(expectedWidths)) {
  throw new Error(`Los viewports canónicos deben ser ${expectedWidths.join(', ')}; recibidos: ${viewportWidths.join(', ')}`);
}
const viewportHeights = RESPONSIVE_VIEWPORT_NAMES.map((name) => PANEL_VIEWPORTS[name].height);
const expectedHeights = [915, 1195, 835, 900, 1440];
if (JSON.stringify(viewportHeights) !== JSON.stringify(expectedHeights)) {
  throw new Error(`Las alturas canónicas deben ser ${expectedHeights.join(', ')}; recibidas: ${viewportHeights.join(', ')}`);
}

const withoutOwner = catalogEntries
  .filter((view) => !responsiveOwnerForView(view.sectionId, view))
  .map((view) => `${view.url} (${view.file})`);
reportDifference('Vistas sin dueño responsivo', withoutOwner);

for (const name of RESPONSIVE_MODULE_NAMES) {
  const entry = RESPONSIVE_MODULES[name];
  if (!entry.tag.startsWith('@responsive:') || entry.checklist.length < 3 || entry.paths.length === 0) {
    throw new Error(`Contrato incompleto para el módulo ${name}`);
  }
}

const scenarioByKey = new Map();
for (const scenario of responsiveCatalogScenarios) {
  if (scenarioByKey.has(scenario.catalogKey)) {
    throw new Error(`Escenario responsivo duplicado: ${scenario.catalogKey}`);
  }
  scenarioByKey.set(scenario.catalogKey, scenario);
}

reportDifference(
  'Vistas sin escenario responsivo',
  catalogEntries
    .filter((view) => !scenarioByKey.has(view.file))
    .map((view) => `${view.url} (${view.file})`),
);
reportDifference(
  'Escenarios responsivos obsoletos',
  responsiveCatalogScenarios
    .filter((scenario) => !catalogFiles.includes(scenario.catalogKey))
    .map((scenario) => scenario.catalogKey),
);

const expectedProfiles = [...RESPONSIVE_VIEWPORT_NAMES];
if (JSON.stringify(RESPONSIVE_PROFILES) !== JSON.stringify(expectedProfiles)) {
  throw new Error(`Los perfiles de escenarios deben ser ${expectedProfiles.join(', ')}`);
}
if (JSON.stringify(RESPONSIVE_SCENARIO_KINDS) !== JSON.stringify(['visual', 'redirect'])) {
  throw new Error('Los escenarios responsivos sólo admiten visual o redirect');
}

for (const view of catalogEntries) {
  const scenario = scenarioByKey.get(view.file);
  const expectedKind = view.viewType === 'redirect' ? 'redirect' : 'visual';
  const expectedOwner = responsiveOwnerForView(view.sectionId, view);
  if (scenario.kind !== expectedKind) {
    throw new Error(`${view.file} debe declarar kind=${expectedKind}`);
  }
  if (scenario.owner !== expectedOwner) {
    throw new Error(`${view.file} pertenece a ${expectedOwner}, no a ${scenario.owner}`);
  }
  if (scenario.sectionId !== view.sectionId || scenario.url !== view.url) {
    throw new Error(`${view.file} no conserva sectionId/url del catálogo`);
  }
  if (!scenario.resolvedUrl || scenario.resolvedUrl.includes(':')) {
    throw new Error(`${view.file} no resuelve sus parámetros dinámicos`);
  }
  if (JSON.stringify(scenario.profiles) !== JSON.stringify(expectedProfiles)) {
    throw new Error(`${view.file} no declara los cinco perfiles canónicos en orden`);
  }
  if (!scenario.flowId || !scenario.outcome) {
    throw new Error(`${view.file} debe declarar flowId y outcome`);
  }
  if (scenario.kind === 'redirect' && !scenario.expected?.url) {
    throw new Error(`${view.file} debe declarar el destino exacto del redirect`);
  }
  if (scenario.kind === 'visual' && !scenario.expected?.text) {
    throw new Error(`${view.file} debe declarar contenido observable concreto`);
  }
}

const batchMembership = new Map();
for (const batch of responsiveBatches) {
  if (!batch.id || !RESPONSIVE_MODULE_NAMES.includes(batch.owner)) {
    throw new Error(`Batch responsivo inválido: ${batch.id || '(sin id)'}`);
  }
  if (batch.scenarioKeys.length === 0 || batch.scenarioKeys.length > 4) {
    throw new Error(`${batch.id} debe contener entre 1 y 4 escenarios`);
  }
  for (const key of batch.scenarioKeys) {
    const scenario = scenarioByKey.get(key);
    if (!scenario) throw new Error(`${batch.id} referencia un escenario inexistente: ${key}`);
    if (scenario.owner !== batch.owner || scenario.batch !== batch.id) {
      throw new Error(`${key} no coincide con el dueño/batch ${batch.id}`);
    }
    batchMembership.set(key, (batchMembership.get(key) || 0) + 1);
  }
}
reportDifference(
  'Escenarios sin pertenencia exacta a un batch',
  responsiveCatalogScenarios
    .filter((scenario) => batchMembership.get(scenario.catalogKey) !== 1)
    .map((scenario) => scenario.catalogKey),
);

const responsiveSpecEntries = await readdir(responsiveSpecRoot, { withFileTypes: true });
const responsiveTagArrays = (
  await Promise.all(responsiveSpecEntries
    .filter((entry) => entry.isFile() && entry.name.endsWith('.spec.js'))
    .map(async (entry) => {
      const source = await readFile(join(responsiveSpecRoot, entry.name), 'utf8');
      return [...source.matchAll(/tag:\s*\[([\s\S]*?)\]/g)]
        .map((match) => ({ file: entry.name, tags: match[1] }));
    }))
).flat();

for (const { file, tags } of responsiveTagArrays) {
  const owner = tags.match(/@responsive-special:([a-z-]+)/)?.[1];
  const specialBatch = tags.match(/@responsive-batch:([a-z-]+-special-\d+)/)?.[1];
  if (!owner && specialBatch) {
    throw new Error(`${file} declara ${specialBatch} sin @responsive-special:<módulo>`);
  }
  if (!owner) continue;
  if (!RESPONSIVE_MODULE_NAMES.includes(owner)) {
    throw new Error(`${file} declara un dueño especial desconocido: ${owner}`);
  }
  if (!specialBatch || !specialBatch.startsWith(`${owner}-special-`)) {
    throw new Error(`${file} debe asignar cada especial de ${owner} a @responsive-batch:${owner}-special-N`);
  }
}

const matrixRows = getResponsiveMatrixRows();
const matrixKeys = matrixRows.map((row) => `${row.catalogKey}::${row.profile}`);
const uniqueMatrixKeys = new Set(matrixKeys);
const expectedMatrixSize = catalogEntries.length * expectedProfiles.length;
if (matrixRows.length !== expectedMatrixSize || uniqueMatrixKeys.size !== expectedMatrixSize) {
  throw new Error(`La matriz responsiva debe tener ${expectedMatrixSize} celdas únicas; recibidas ${matrixRows.length}/${uniqueMatrixKeys.size}`);
}

const visualCount = responsiveCatalogScenarios.filter((scenario) => scenario.kind === 'visual').length;
const redirectCount = responsiveCatalogScenarios.filter((scenario) => scenario.kind === 'redirect').length;
if (visualCount !== 100 || redirectCount !== 18) {
  throw new Error(`La matriz debe separar 100 vistas visuales y 18 redirects; recibidas ${visualCount}/${redirectCount}`);
}

console.log(`Contrato responsivo OK: ${pages.length} vistas (${visualCount} visuales + ${redirectCount} redirects), ${RESPONSIVE_MODULE_NAMES.length} módulos, ${RESPONSIVE_VIEWPORT_NAMES.length} perfiles, ${matrixRows.length} celdas.`);
