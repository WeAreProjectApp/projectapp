import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parse } from 'yaml';

const forbiddenEvents = new Set(['deployment', 'deployment_status']);

export function deploymentEventConsumers(source) {
  const workflow = parse(source, { uniqueKeys: true });
  if (!workflow || typeof workflow !== 'object' || Array.isArray(workflow)) {
    throw new Error('Expected a workflow mapping.');
  }
  const triggers = workflow.on;
  const events = typeof triggers === 'string' ? [triggers]
    : Array.isArray(triggers) ? triggers : Object.keys(triggers ?? {});
  return events.filter((event) => forbiddenEvents.has(event));
}

export function checkDeploymentEvents(workflowDir) {
  const consumers = [];
  for (const filename of fs.readdirSync(workflowDir).filter((name) => /\.ya?ml$/.test(name))) {
    const events = deploymentEventConsumers(fs.readFileSync(path.join(workflowDir, filename), 'utf8'));
    consumers.push(...events.map((event) => `${filename}: ${event}`));
  }
  if (consumers.length) {
    throw new Error(`Deployment notices must not trigger workflows:\n${consumers.join('\n')}`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const workflowDir = process.argv[2] ?? fileURLToPath(new URL('../../.github/workflows/', import.meta.url));
  try {
    checkDeploymentEvents(workflowDir);
    process.stdout.write('Deployment event guard passed: no workflow consumes deployment notices.\n');
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}
