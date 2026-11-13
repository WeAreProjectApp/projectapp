import { viewCatalogSections } from '../config/viewCatalog.js';
import { flattenCapabilityCatalog } from '../config/viewCapabilityCatalog.js';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

// Export product-owned descriptions; no credentials, requests or business data.
const features = flattenCapabilityCatalog().filter((node) => node.kind === 'feature');
const surfaces = viewCatalogSections.flatMap((section) => section.views
  .filter((view) => view.url.startsWith('/panel') || view.url.startsWith('/platform'))
  .map((view) => ({
    id: view.url,
    surface: view.url.startsWith('/panel') ? 'Panel' : 'Plataforma',
    module: section.label,
    view: view.label,
    file: view.file,
    audience: view.audience,
    view_type: view.viewType,
    description: view.notes,
    features: features.filter((feature) => feature.viewUrls?.includes(view.url))
      .map(({ id, label, summary }) => ({ id, label, summary })),
  })));

const sources = Object.fromEntries(['viewCatalog.js', 'viewCapabilityCatalog.js'].map((name) => [
  `frontend/config/${name}`,
  createHash('sha256').update(readFileSync(new URL(`../config/${name}`, import.meta.url))).digest('hex'),
]));
process.stdout.write(`${JSON.stringify({ schema: 1, sources, surfaces }, null, 2)}\n`);
