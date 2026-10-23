import { defineEventHandler, setResponseHeader } from 'h3';

const BASE = 'https://projectapp.co';

interface DynamicEntry {
  slug: string;
  updated_at: string;
}

/**
 * Static pages with their exact priorities and change frequencies.
 * Each entry produces TWO <url> blocks (en-us + es-co) with hreflang alternates.
 */
const STATIC_BILINGUAL_PAGES: Array<{
  path: string;
  changefreq: string;
  priority: string;
  comment?: string;
}> = [
  { path: '', changefreq: 'weekly', priority: '1.0', comment: 'Home' },
  { path: '/landing-web-design', changefreq: 'weekly', priority: '0.9', comment: 'Landing Web Design' },
  { path: '/about-us', changefreq: 'monthly', priority: '0.9', comment: 'About Us' },
  { path: '/portfolio-works', changefreq: 'weekly', priority: '0.9', comment: 'Portfolio Works' },
  { path: '/consulting', changefreq: 'monthly', priority: '0.8', comment: 'Consulting and advisory' },
  { path: '/contact', changefreq: 'monthly', priority: '0.6', comment: 'Contact' },
];

function bilingualUrlBlock(path: string, changefreq: string, priority: string): string {
  const enUrl = `${BASE}/en-us${path}`;
  const esUrl = `${BASE}/es-co${path}`;

  return `  <url>
    <loc>${enUrl}</loc>
    <xhtml:link rel="alternate" hreflang="en-us" href="${enUrl}" />
    <xhtml:link rel="alternate" hreflang="es-co" href="${esUrl}" />
    <changefreq>${changefreq}</changefreq>
    <priority>${priority}</priority>
  </url>
  <url>
    <loc>${esUrl}</loc>
    <xhtml:link rel="alternate" hreflang="en-us" href="${enUrl}" />
    <xhtml:link rel="alternate" hreflang="es-co" href="${esUrl}" />
    <changefreq>${changefreq}</changefreq>
    <priority>${priority}</priority>
  </url>`;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toISOString().split('T')[0]; // YYYY-MM-DD
}

export default defineEventHandler(async (event) => {
  setResponseHeader(event, 'Content-Type', 'application/xml; charset=utf-8');
  setResponseHeader(event, 'Cache-Control', 'public, max-age=3600, s-maxage=3600');

  // Determine API base URL for fetching dynamic data
  const apiBase = process.env.NUXT_API_BASE || 'http://127.0.0.1:8000';

  // Fetch dynamic data in parallel
  let blogEntries: DynamicEntry[] = [];
  let portfolioEntries: DynamicEntry[] = [];

  try {
    const [blogRes, portfolioRes] = await Promise.all([
      fetch(`${apiBase}/api/blog/sitemap-data/`).then((r) => r.ok ? r.json() : []).catch(() => []),
      fetch(`${apiBase}/api/portfolio/sitemap-data/`).then((r) => r.ok ? r.json() : []).catch(() => []),
    ]);
    blogEntries = blogRes || [];
    portfolioEntries = portfolioRes || [];
  } catch {
    // Silently continue with empty arrays — static pages always appear
  }

  // Build XML
  const lines: string[] = [];

  lines.push('<?xml version="1.0" encoding="UTF-8"?>');
  lines.push('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"');
  lines.push('        xmlns:xhtml="http://www.w3.org/1999/xhtml">');
  lines.push('');

  // Static bilingual pages
  for (const page of STATIC_BILINGUAL_PAGES) {
    if (page.comment) lines.push(`  <!-- ${page.comment} -->`);
    lines.push(bilingualUrlBlock(page.path, page.changefreq, page.priority));
    lines.push('');
  }

  // Blog index
  lines.push('  <!-- Blog -->');
  lines.push(`  <url>
    <loc>${BASE}/blog</loc>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>`);
  lines.push('');

  // Blog posts (dynamic)
  if (blogEntries.length > 0) {
    lines.push('  <!-- Blog Posts -->');
    for (const entry of blogEntries) {
      const lastmod = formatDate(entry.updated_at);
      lines.push(`  <url>
    <loc>${BASE}/blog/${entry.slug}</loc>${lastmod ? `\n    <lastmod>${lastmod}</lastmod>` : ''}
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>`);
    }
    lines.push('');
  }

  // Portfolio works (dynamic, bilingual)
  if (portfolioEntries.length > 0) {
    lines.push('  <!-- Portfolio Works -->');
    for (const entry of portfolioEntries) {
      const lastmod = formatDate(entry.updated_at);
      const enUrl = `${BASE}/en-us/portfolio-works/${entry.slug}`;
      const esUrl = `${BASE}/es-co/portfolio-works/${entry.slug}`;
      const lastmodTag = lastmod ? `\n    <lastmod>${lastmod}</lastmod>` : '';

      lines.push(`  <url>
    <loc>${enUrl}</loc>
    <xhtml:link rel="alternate" hreflang="en-us" href="${enUrl}" />
    <xhtml:link rel="alternate" hreflang="es-co" href="${esUrl}" />${lastmodTag}
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>${esUrl}</loc>
    <xhtml:link rel="alternate" hreflang="en-us" href="${enUrl}" />
    <xhtml:link rel="alternate" hreflang="es-co" href="${esUrl}" />${lastmodTag}
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
    }
    lines.push('');
  }

  lines.push('</urlset>');

  return lines.join('\n');
});
