// CI integration check, run after build:django and collectstatic.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const commit = execFileSync('git', ['-C', root, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
const expected = { schema_version: 1, project: 'projectapp', commit };
for (const artifact of [
  'frontend/.output/public/version.json',
  'backend/static/frontend/version.json',
  'backend/staticfiles/frontend/version.json',
]) {
  assert.deepEqual(JSON.parse(fs.readFileSync(new URL(`../../${artifact}`, import.meta.url), 'utf8')), expected);
}
process.stdout.write('Build version matches the checked-out commit in all published copies.\n');
