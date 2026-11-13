import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

import { resolveBuildCommit, writeBuildVersion } from '../../utils/buildIdentity.js';

const commit = 'a'.repeat(40);
const otherCommit = 'b'.repeat(40);
const fleet = { FLEET_INTEGRITY_TARGET_PROJECT: 'projectapp', FLEET_INTEGRITY_TARGET_COMMIT: commit };

function directory(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'projectapp-build-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

function git(root, ...args) {
  return execFileSync('git', ['-C', root, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}

function checkout(t) {
  const root = directory(t);
  git(root, 'init', '--quiet');
  fs.writeFileSync(path.join(root, 'source.txt'), 'source\n');
  git(root, 'add', '.');
  git(root, '-c', 'user.name=Build Test', '-c', 'user.email=build@example.test', 'commit', '--quiet', '-m', 'fixture');
  return root;
}

test('uses the Integrity target in a stage without Git metadata', (t) => {
  const root = directory(t);
  assert.equal(resolveBuildCommit(root, fleet), commit);
});

test('accepts an explicit commit for an exported source tree', (t) => {
  const root = directory(t);
  assert.equal(resolveBuildCommit(root, { PROJECTAPP_BUILD_COMMIT: commit }), commit);
});

test('rejects a target belonging to another project', (t) => {
  const root = directory(t);
  assert.throws(() => resolveBuildCommit(root, { ...fleet, FLEET_INTEGRITY_TARGET_PROJECT: 'other' }), /belong to projectapp/);
});

test('rejects conflicting explicit identity', (t) => {
  const root = directory(t);
  assert.throws(() => resolveBuildCommit(root, { ...fleet, PROJECTAPP_BUILD_COMMIT: otherCommit }), /differs from the Integrity target/);
});

for (const [label, invalid] of [
  ['abbreviated', 'abc123'], ['uppercase', 'A'.repeat(40)],
  ['nonhex', 'z'.repeat(40)], ['newline-terminated', `${commit}\n`],
]) {
  test(`rejects a ${label} commit`, (t) => {
    const root = directory(t);
    assert.throws(() => resolveBuildCommit(root, { PROJECTAPP_BUILD_COMMIT: invalid }), /full lowercase/);
  });
}

test('rejects an incomplete Integrity identity', (t) => {
  const root = directory(t);
  assert.throws(() => resolveBuildCommit(root, { FLEET_INTEGRITY_TARGET_PROJECT: 'projectapp' }), /full lowercase/);
});

test('uses the source checkout commit during a build', (t) => {
  const root = checkout(t);
  assert.equal(resolveBuildCommit(root, {}), git(root, 'rev-parse', 'HEAD'));
});

test('rejects tracked source changes without a commit', (t) => {
  const root = checkout(t);
  fs.writeFileSync(path.join(root, 'source.txt'), 'changed\n');
  assert.throws(() => resolveBuildCommit(root, {}), /clean checkout/);
});

test('rejects a supplied commit that differs from the source checkout', (t) => {
  const root = checkout(t);
  assert.throws(() => resolveBuildCommit(root, { PROJECTAPP_BUILD_COMMIT: commit }), /differs from the checked-out source/);
});

test('does not inherit the enclosing repository identity', (t) => {
  const root = checkout(t);
  const stage = path.join(root, 'stage');
  fs.mkdirSync(stage);
  assert.throws(() => resolveBuildCommit(stage, {}), /requires an explicit build commit/);
});

test('writes the public version contract into generated output', (t) => {
  const root = directory(t);
  writeBuildVersion(root, commit);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(root, 'version.json'), 'utf8')), {
    schema_version: 1, project: 'projectapp', commit,
  });
});

test('preserves the published identity when generation fails', (t) => {
  const root = directory(t);
  const frontend = path.join(root, 'frontend');
  fs.mkdirSync(path.join(frontend, 'utils'), { recursive: true });
  for (const relative of ['update-django-template.js', 'utils/buildIdentity.js', 'utils/spaFallback.js']) {
    fs.copyFileSync(fileURLToPath(new URL(`../../${relative}`, import.meta.url)), path.join(frontend, relative));
  }
  fs.writeFileSync(path.join(frontend, 'package.json'), '{"type":"module"}');
  const published = path.join(root, 'backend/static/frontend');
  fs.mkdirSync(published, { recursive: true });
  writeBuildVersion(published, otherCommit);
  const bin = path.join(root, 'bin');
  fs.mkdirSync(bin);
  fs.writeFileSync(path.join(bin, 'npx'), '#!/bin/sh\nexit 19\n', { mode: 0o755 });
  const env = { ...process.env, ...fleet, PROJECTAPP_BUILD_COMMIT: commit, PATH: `${bin}:${process.env.PATH}` };

  const result = spawnSync(process.execPath, [path.join(frontend, 'update-django-template.js')], { env, encoding: 'utf8' });

  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /Running nuxt generate/);
  assert.equal(JSON.parse(fs.readFileSync(path.join(published, 'version.json'), 'utf8')).commit, otherCommit);
});
