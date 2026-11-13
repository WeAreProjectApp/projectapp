import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

import { checkDeploymentEvents, deploymentEventConsumers } from '../check-deployment-events.mjs';

for (const event of ['deployment', 'deployment_status']) {
  for (const [form, source] of [
    ['scalar', `on: ${event}\njobs: {}`],
    ['sequence', `on: [push, ${event}]\njobs: {}`],
    ['mapping', `on:\n  ${event}: {}\njobs: {}`],
  ]) {
    test(`detects ${event} in ${form} triggers`, () => {
      assert.deepEqual(deploymentEventConsumers(source), [event]);
    });
  }
}

test('accepts workflows triggered independently of deployment notices', () => {
  assert.deepEqual(deploymentEventConsumers('on: [push, pull_request, workflow_dispatch, workflow_call]\njobs: {}'), []);
});

test('rejects duplicate event mappings instead of silently ignoring one', () => {
  assert.throws(() => deploymentEventConsumers('on: push\non: deployment\njobs: {}'), /unique|duplicate/i);
});

test('rejects a workflow file consuming deployment status events', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'deployment-events-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(path.join(root, 'consumer.yaml'), 'on: [deployment_status]\njobs: {}');
  assert.throws(() => checkDeploymentEvents(root), /consumer.yaml: deployment_status/);
});

test('accepts the repository workflow inventory', () => {
  checkDeploymentEvents(fileURLToPath(new URL('../../../.github/workflows/', import.meta.url)));
});
