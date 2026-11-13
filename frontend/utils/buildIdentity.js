import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const commitPattern = /^[0-9a-f]{40}$/;

function validateCommit(commit) {
  if (typeof commit !== 'string' || !commitPattern.test(commit)) {
    throw new Error('Build identity requires a full lowercase 40-character commit SHA.');
  }
  return commit;
}

export function resolveBuildCommit(repoRoot, env = process.env) {
  const fleetCommit = env.FLEET_INTEGRITY_TARGET_COMMIT;
  const fleetProject = env.FLEET_INTEGRITY_TARGET_PROJECT;
  const explicitCommit = env.PROJECTAPP_BUILD_COMMIT;
  if (fleetCommit !== undefined || fleetProject !== undefined) {
    if (fleetProject !== 'projectapp') {
      throw new Error('Integrity build identity must belong to projectapp.');
    }
    validateCommit(fleetCommit);
  }
  if (explicitCommit !== undefined) validateCommit(explicitCommit);
  if (fleetCommit !== undefined && explicitCommit !== undefined && fleetCommit !== explicitCommit) {
    throw new Error('The explicit build commit differs from the Integrity target.');
  }
  const suppliedCommit = fleetCommit ?? explicitCommit;

  // The toolkit's checkout-index stage intentionally has no .git. Do not
  // discover a parent repository or read the deployed clone's moving HEAD.
  if (!fs.existsSync(path.join(repoRoot, '.git'))) {
    if (suppliedCommit === undefined) {
      throw new Error('A build outside a Git checkout requires an explicit build commit.');
    }
    return suppliedCommit;
  }

  const git = (...args) => execFileSync('git', ['-C', repoRoot, ...args], {
    encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();
  let head;
  try {
    if (fs.realpathSync(git('rev-parse', '--show-toplevel')) !== fs.realpathSync(repoRoot)) {
      throw new Error('Unexpected repository root.');
    }
    head = validateCommit(git('rev-parse', '--verify', 'HEAD'));
    if (git('status', '--porcelain', '--untracked-files=no')) {
      throw new Error('Tracked source changes have no commit identity.');
    }
  } catch {
    throw new Error('Build identity requires a clean checkout at its declared repository root.');
  }
  if (suppliedCommit !== undefined && suppliedCommit !== head) {
    throw new Error('The supplied build commit differs from the checked-out source.');
  }
  return head;
}

export function writeBuildVersion(outputDir, commit) {
  const document = { schema_version: 1, project: 'projectapp', commit: validateCommit(commit) };
  const target = path.join(outputDir, 'version.json');
  fs.writeFileSync(`${target}.tmp`, `${JSON.stringify(document)}\n`, 'utf8');
  fs.renameSync(`${target}.tmp`, target);
}
