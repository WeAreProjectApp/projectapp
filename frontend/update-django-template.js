import fs from 'fs';
import net from 'net';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync, spawn } from 'child_process';

import { assertValidSpaFallbackHtml } from './utils/spaFallback.js';
import { resolveBuildCommit, writeBuildVersion } from './utils/buildIdentity.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const buildCommit = resolveBuildCommit(path.resolve(__dirname, '..'));

const sourceDir = path.resolve(__dirname, '.output/public');
const targetDir = path.resolve(__dirname, '../backend/static/frontend');
const stagingDir = `${targetDir}.new`;
const retiredDir = `${targetDir}.old`;

const backendDir = path.resolve(__dirname, '../backend');
const venvPython = path.resolve(backendDir, 'venv/bin/python');
const managePy = path.resolve(backendDir, 'manage.py');

// ---------------------------------------------------------------------------
// Blog prerender against a throwaway local Django server.
//
// Blog post pages fetch their content from the API during prerender. Pointing
// that at the public domain routes every request through nginx, whose `api`
// rate-limit zone (5 r/s) trips 429s once there are more than a handful of
// posts — silently dropping most prerendered pages. Instead we spin up Django
// on loopback, prerender against it (no nginx, no rate limit, real DB data),
// and tear it down. This is the single chokepoint for every build path
// (deploy and the on-publish rebuild task), so the fix is global.
//
// If the backend (venv + manage.py) isn't present — e.g. a pure-frontend CI or
// dev build — we skip the local server and fall back to PRERENDER_API_ORIGIN
// from the environment (or no blog prerender), exactly as before.
// ---------------------------------------------------------------------------

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

async function waitForApi(origin, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  const url = `${origin}/api/blog/sitemap-data/`;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      // server not up yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

async function startLocalDjango() {
  const port = await findFreePort();
  const origin = `http://127.0.0.1:${port}`;
  const env = {
    ...process.env,
    // Dedicated build settings: production DB + data, but no HTTPS enforcement
    // (production's SECURE_SSL_REDIRECT would 301 the loopback prerender fetches
    // to https and break them). See backend/projectapp/settings_build.py.
    DJANGO_SETTINGS_MODULE: 'projectapp.settings_build',
    // Loopback-only server; allow the host it will actually be reached on.
    DJANGO_ALLOWED_HOSTS: '127.0.0.1,localhost',
  };
  console.log(`[blog-prerender] starting local Django on ${origin} (settings=${env.DJANGO_SETTINGS_MODULE})`);
  const proc = spawn(
    venvPython,
    ['manage.py', 'runserver', `127.0.0.1:${port}`, '--noreload', '--skip-checks'],
    { cwd: backendDir, env, stdio: ['ignore', 'inherit', 'inherit'] },
  );
  const ready = await waitForApi(origin);
  if (!ready) {
    try { proc.kill('SIGKILL'); } catch { /* noop */ }
    throw new Error(`local Django did not become ready on ${origin} within timeout`);
  }
  console.log(`[blog-prerender] local Django ready on ${origin}`);
  return { origin, proc };
}

// 1. Run nuxt generate with cdnURL set for Django static serving, prerendering
//    blog posts against a local backend when one is available.
const baseEnv = { ...process.env, NUXT_APP_CDN_URL: '/static/frontend/' };
let server = null;

const backendAvailable = fs.existsSync(venvPython) && fs.existsSync(managePy);
if (backendAvailable) {
  server = await startLocalDjango();
}

try {
  const generateEnv = { ...baseEnv, PRERENDER_BLOG: '1' };
  if (server) {
    generateEnv.PRERENDER_API_ORIGIN = server.origin;
    // The local server removes the rate-limit excuse: a dropped prerender is
    // now a real regression, so fail the build instead of shipping silently.
    generateEnv.PRERENDER_REQUIRE_BLOG = '1';
  }
  console.log('Running nuxt generate...');
  execSync('npx nuxi generate', { cwd: __dirname, stdio: 'inherit', env: generateEnv });
} finally {
  if (server) {
    console.log('[blog-prerender] stopping local Django');
    try { server.proc.kill('SIGTERM'); } catch { /* noop */ }
  }
}

// 2. Verify output exists
if (!fs.existsSync(sourceDir)) {
  console.error(`Nuxt generate output not found at: ${sourceDir}`);
  process.exit(1);
}

const fallbackPath = path.join(sourceDir, '200.html');
if (!fs.existsSync(fallbackPath)) {
  throw new Error(`Nuxt SPA fallback not found at: ${fallbackPath}`);
}

const fallbackHtml = fs.readFileSync(fallbackPath, 'utf8');
try {
  assertValidSpaFallbackHtml(fallbackHtml);
} catch (error) {
  throw new Error(`Invalid Nuxt SPA fallback at ${fallbackPath}: ${error.message}`, {
    cause: error,
  });
}
console.log(`Validated Nuxt SPA fallback: ${fallbackPath}`);

// Root PWA URLs must exist before atomically publishing the generated site.
const manifest = JSON.parse(fs.readFileSync(path.join(sourceDir, 'manifest.webmanifest'), 'utf8'));
if (manifest.start_url !== '/es-co/panel' || manifest.id !== '/panel') {
  throw new Error('PWA manifest must launch the internal panel');
}
for (const asset of ['sw.js', ...manifest.icons.map((icon) => icon.src.replace(/^\//, ''))]) {
  if (!fs.statSync(path.join(sourceDir, asset)).size) {
    throw new Error(`Empty PWA asset: ${asset}`);
  }
}

// Stamp only validated output. The manifest is copied and collected with the
// same artifacts; a failed generate never relabels the published frontend.
writeBuildVersion(sourceDir, buildCommit);

// 3. Copy output to a staging dir next to the live one, then swap with two
// renames. Gunicorn serves these files straight from disk on every request,
// so the live dir must never be empty or half-written.
function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

fs.rmSync(stagingDir, { recursive: true, force: true });
fs.rmSync(retiredDir, { recursive: true, force: true });

console.log(`Copying ${sourceDir} → ${stagingDir}...`);
copyDirSync(sourceDir, stagingDir);

console.log(`Swapping ${stagingDir} → ${targetDir}...`);
if (fs.existsSync(targetDir)) {
  fs.renameSync(targetDir, retiredDir);
}
fs.renameSync(stagingDir, targetDir);
fs.rmSync(retiredDir, { recursive: true, force: true });

console.log('Build complete! Files swapped into backend/static/frontend/');
