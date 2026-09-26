import { appendFile } from 'node:fs/promises';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  RESPONSIVE_MODULE_NAMES,
  modulesForChangedFiles,
} from '../config/responsiveAcceptance.js';
import { responsiveBatches } from '../e2e/responsive/catalog-scenarios.js';

const frontendRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const repoRoot = resolve(frontendRoot, '..');
const rawArgs = process.argv.slice(2);
const args = new Set(rawArgs);

const responsiveSpecRoot = resolve(frontendRoot, 'e2e/responsive');
const responsiveSpecSources = readdirSync(responsiveSpecRoot, { withFileTypes: true })
  .filter((entry) => entry.isFile() && entry.name.endsWith('.spec.js'))
  .map((entry) => readFileSync(resolve(responsiveSpecRoot, entry.name), 'utf8'));
const responsiveSpecialBatches = RESPONSIVE_MODULE_NAMES.flatMap((owner) => {
  const ownerSources = responsiveSpecSources.filter((source) => source.includes(`@responsive-special:${owner}`));
  if (ownerSources.length === 0) return [];

  const numberedTags = [...new Map(ownerSources.flatMap((source) => (
    [...source.matchAll(new RegExp(`@responsive-batch:(${owner}-special-(\\d+))`, 'g'))]
      .map((match) => ({ tag: match[1], number: Number(match[2]) }))
  )).map((entry) => [entry.tag, entry])).values()]
    .sort((left, right) => left.number - right.number);

  if (numberedTags.length === 0) {
    return [{ id: `${owner}-special`, owner, kind: 'special', scenarioKeys: [], grepTag: null }];
  }

  return numberedTags.map(({ tag, number }) => ({
    id: number === 1 ? `${owner}-special` : tag,
    owner,
    kind: 'special',
    scenarioKeys: [],
    grepTag: tag,
  }));
});
const executableBatches = [
  ...responsiveBatches.map((batch) => ({ ...batch, kind: batch.kind || 'matrix' })),
  ...responsiveSpecialBatches,
];

function optionValue(prefix) {
  return rawArgs.find((argument) => argument.startsWith(`${prefix}=`))?.slice(prefix.length + 1);
}

function git(...command) {
  const result = spawnSync('git', command, { cwd: repoRoot, encoding: 'utf8' });
  if (result.status !== 0) throw new Error(result.stderr.trim() || `git ${command.join(' ')} falló`);
  return result.stdout.trim();
}

function resolveChangedFiles() {
  if (process.env.RESPONSIVE_ALL === '1' || args.has('--all')) return null;
  const base = process.env.RESPONSIVE_BASE_SHA
    || git('merge-base', 'HEAD', process.env.RESPONSIVE_BASE_REF || 'origin/main');
  const diffArgs = ['diff', '--name-only', '--diff-filter=ACMR', base];
  if (process.env.RESPONSIVE_HEAD_SHA) diffArgs.push(process.env.RESPONSIVE_HEAD_SHA);
  const output = git(...diffArgs);
  return output ? output.split('\n') : [];
}

function resolveModules() {
  const explicitModule = optionValue('--module');
  if (explicitModule) {
    if (!RESPONSIVE_MODULE_NAMES.includes(explicitModule)) {
      throw new Error(`Módulo responsivo desconocido: ${explicitModule}`);
    }
    return [explicitModule];
  }
  const changedFiles = resolveChangedFiles();
  return changedFiles === null
    ? [...RESPONSIVE_MODULE_NAMES]
    : modulesForChangedFiles(changedFiles);
}

const explicitBatch = optionValue('--batch');
const modules = explicitBatch
  ? [...new Set(executableBatches.filter((batch) => batch.id === explicitBatch).map((batch) => batch.owner))]
  : resolveModules();
const batches = executableBatches.filter((batch) => (
  explicitBatch ? batch.id === explicitBatch : modules.includes(batch.owner)
));

if (explicitBatch && batches.length !== 1) {
  throw new Error(`Batch responsivo desconocido: ${explicitBatch}`);
}

const githubMatrix = {
  include: batches.map((batch) => ({
    module: batch.owner,
    batch: batch.id,
    scenarios: batch.kind === 'special' ? 'special' : batch.scenarioKeys.length,
    tests: batch.kind === 'special' ? '1-20' : batch.scenarioKeys.length * 5,
  })),
};

if (args.has('--github-output')) {
  if (!process.env.GITHUB_OUTPUT) throw new Error('GITHUB_OUTPUT no está definido');
  await appendFile(process.env.GITHUB_OUTPUT, `batches=${JSON.stringify(githubMatrix)}\n`);
}

console.log(`Módulos responsivos: ${modules.length ? modules.join(', ') : 'ninguno'}`);
console.log(`Lotes responsivos: ${batches.length ? batches.map((batch) => batch.id).join(', ') : 'ninguno'}`);

if (args.has('--list') || args.has('--github-output') || batches.length === 0) process.exit(0);

const aggregateRows = [];
const aggregateDuplicates = [];

function collectJsonTests(suites) {
  return suites.flatMap((suite) => [
    ...(suite.specs || []).flatMap((spec) => spec.tests || []),
    ...collectJsonTests(suite.suites || []),
  ]);
}

for (const batch of batches) {
  const isSpecial = batch.kind === 'special';
  const result = spawnSync(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    [
      'playwright',
      'test',
      'e2e/responsive',
      '--retries=0',
      '--grep',
      isSpecial
        ? (batch.grepTag ? `@responsive-batch:${batch.grepTag}` : `@responsive-special:${batch.owner}`)
        : `@responsive-batch:${batch.id}`,
    ],
    {
      cwd: frontendRoot,
      env: {
        ...process.env,
        E2E_RESPONSIVE: '1',
        E2E_RESPONSIVE_BATCH: isSpecial ? '' : batch.id,
        E2E_RESPONSIVE_SPECIAL_OWNER: isSpecial ? batch.owner : '',
        E2E_RESPONSIVE_SPECIAL_BATCH: isSpecial ? batch.id : '',
      },
      stdio: 'inherit',
    },
  );
  if (result.status !== 0) process.exit(result.status ?? 1);

  if (isSpecial) {
    const jsonReport = JSON.parse(readFileSync(resolve(frontendRoot, 'e2e-results/results.json'), 'utf8'));
    const selectedTests = collectJsonTests(jsonReport.suites || []);
    if (selectedTests.length === 0 || selectedTests.length > 20) {
      throw new Error(`${batch.id} debe ejecutar entre 1 y 20 especiales; recibidos ${selectedTests.length}`);
    }
    const unstable = selectedTests.filter((test) => test.status !== 'expected' || test.results?.length !== 1);
    if (unstable.length > 0) {
      throw new Error(`${batch.id} contiene ${unstable.length} especiales flaky o inesperados`);
    }
    console.log(`${batch.id}: ${selectedTests.length} especiales estables acreditados.`);
    continue;
  }

  const batchReport = JSON.parse(readFileSync(resolve(frontendRoot, 'e2e-results/responsive-matrix.json'), 'utf8'));
  const expectedTests = batch.scenarioKeys.length * 5;
  if (
    batchReport.summary.expected !== expectedTests
    || batchReport.summary.executed !== expectedTests
    || batchReport.summary.noCumple !== 0
    || batchReport.summary.flaky !== 0
    || batchReport.summary.duplicateOrUnknownCells !== 0
  ) {
    throw new Error(`${batch.id} no acreditó sus ${expectedTests} celdas únicas`);
  }
  aggregateRows.push(...batchReport.rows);
  aggregateDuplicates.push(...batchReport.duplicates);
}

if (batches.length > 1) {
  const matrixKeys = aggregateRows.map((row) => `${row.catalogKey}::${row.profile}`);
  const summary = {
    expected: aggregateRows.length,
    executed: aggregateRows.filter((row) => row.result !== null).length,
    cumple: aggregateRows.filter((row) => row.status === 'cumple').length,
    noCumple: aggregateRows.filter((row) => row.status === 'no cumple').length,
    cumpleDistinto: aggregateRows.filter((row) => row.status === 'cumple distinto').length,
    flaky: aggregateRows.filter((row) => row.result === 'passed' && row.hadFailure).length,
    visual: aggregateRows.filter((row) => row.kind === 'visual').length,
    redirect: aggregateRows.filter((row) => row.kind === 'redirect').length,
    duplicateOrUnknownCells: aggregateDuplicates.length,
  };
  if (new Set(matrixKeys).size !== aggregateRows.length) {
    throw new Error('La ejecución responsive agregada contiene celdas duplicadas');
  }
  if ((args.has('--all') || process.env.RESPONSIVE_ALL === '1') && aggregateRows.length !== 590) {
    throw new Error(`La ejecución completa debe producir 590 celdas; recibidas ${aggregateRows.length}`);
  }
  const report = {
    timestamp: new Date().toISOString(),
    summary,
    duplicates: aggregateDuplicates,
    rows: aggregateRows,
  };
  writeFileSync(resolve(frontendRoot, 'e2e-results/responsive-matrix.json'), JSON.stringify(report, null, 2));
  console.log(`Matriz agregada: ${summary.executed}/${summary.expected} celdas ejecutadas.`);
}
