/**
 * E2E tests for the public portfolio case study detail page.
 *
 * Covers: renders case study with content sections, back navigation,
 * 404 for nonexistent slug, share button, visit site link, CTA section.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PUBLIC_PORTFOLIO_DETAIL } from '../helpers/flow-tags.js';

const mockWork = {
  id: 1,
  title: 'E-Commerce Platform Redesign',
  slug: 'ecommerce-redesign',
  excerpt: 'A complete redesign of the e-commerce experience.',
  cover_image: 'https://example.com/cover.jpg',
  project_url: 'https://example-client.com',
  content_json: {
    problem: {
      title: 'The Challenge',
      description: 'The existing platform had poor UX and slow load times.',
      highlights: ['High bounce rate', 'Low conversion'],
    },
    solution: {
      title: 'Our Solution',
      description: 'We rebuilt the platform with modern technologies.',
      highlights: ['Nuxt 3 frontend', 'Django REST backend'],
    },
    results: {
      title: 'The Results',
      description: 'Conversion rate increased by 45%.',
      highlights: ['45% more conversions', '2x faster load time'],
    },
  },
  meta_title: 'E-Commerce Redesign — Project App',
  meta_description: 'Case study of a full e-commerce redesign.',
  is_published: true,
  published_at: '2026-03-01T12:00:00Z',
};

const mockWorks = [mockWork];
const mockWorkEs = {
  ...mockWork,
  title: 'Rediseño de una plataforma de comercio electrónico',
  meta_title: 'Rediseño de comercio electrónico — Project App',
  meta_description: 'Caso de estudio de un rediseño de comercio electrónico.',
};

function setupMock(page) {
  return mockApi(page, async ({ route, apiPath }) => {
    if (apiPath.startsWith('portfolio/')) {
      const slugMatch = apiPath.match(/^portfolio\/([^/?]+)\//);
      if (slugMatch) {
        const slug = slugMatch[1];
        if (slug === mockWork.slug) {
          const { searchParams } = new URL(route.request().url());
          const work = searchParams.get('lang') === 'es' ? mockWorkEs : mockWork;
          return { status: 200, contentType: 'application/json', body: JSON.stringify(work) };
        }
        return { status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not found.' }) };
      }
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockWorks) };
    }
    return null;
  });
}

async function expectDocumentMetadata(page, work, lang) {
  await expect(page.getByRole('heading', { level: 1, name: work.title, exact: true })).toBeVisible();
  await expect(page).toHaveTitle(work.title);
  await expect(page.locator('html')).toHaveAttribute('lang', lang);
  await expect(page.locator('head meta[name="description"]')).toHaveAttribute('content', work.meta_description);
  await expect(page.locator('head meta[property="og:title"]')).toHaveAttribute('content', work.meta_title);
  await expect(page.locator('head meta[property="og:description"]')).toHaveAttribute('content', work.meta_description);
  await expect(page.locator('head meta[property="og:image"]')).toHaveAttribute('content', work.cover_image);
  await expect(page.locator('head link[rel="canonical"]')).toHaveAttribute('href', 'https://projectapp.co/portfolio-works/ecommerce-redesign');
  await expect(page.locator('head meta[name="robots"][content*="noindex"]')).toHaveCount(0);
}

test.describe('Portfolio Case Study Detail', () => {
  test.setTimeout(60_000);

  test('updates the detail metadata after switching language', {
    tag: [...PUBLIC_PORTFOLIO_DETAIL, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the metadata contract covers opening a shared case study URL)
    await setupMock(page);
    await page.goto('/en-us/portfolio-works/ecommerce-redesign', { waitUntil: 'domcontentloaded' });
    await expectDocumentMetadata(page, mockWork, 'en-US');

    await page.getByRole('button', { name: 'Switch to Spanish', exact: true }).filter({ visible: true }).click();
    await expect(page).toHaveURL('/es-co/portfolio-works/ecommerce-redesign');
    await expectDocumentMetadata(page, mockWorkEs, 'es-CO');

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expectDocumentMetadata(page, mockWorkEs, 'es-CO');
  });
  test('renders case study with title, excerpt, and content sections', {
    tag: ['@outcome:display', ...PUBLIC_PORTFOLIO_DETAIL, '@role:guest'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display flow — the case-study page renders content from the fetched work; the detail's interaction is covered by the back-link test)
    await setupMock(page);
    await page.goto('/en-us/portfolio-works/ecommerce-redesign');

    await expect(page.getByRole('heading', { name: 'E-Commerce Platform Redesign' })).toBeVisible();
    await expect(page.getByText('A complete redesign of the e-commerce experience.')).toBeVisible();
    await expect(page.getByText('The Challenge')).toBeVisible();
    await expect(page.getByText('The existing platform had poor UX and slow load times.')).toBeVisible();
    await expect(page.getByText('Our Solution')).toBeVisible();
    await expect(page.getByText('The Results')).toBeVisible();
  });

  test('the back link returns from the case study to the portfolio listing', {
    tag: ['@outcome:display', ...PUBLIC_PORTFOLIO_DETAIL, '@role:guest'],
  }, async ({ page }) => {
    // Fails if the "All projects" back link stops navigating away from the case study.
    await setupMock(page);
    await page.goto('/en-us/portfolio-works/ecommerce-redesign');

    await page.getByText('All projects').click();

    await expect(page).not.toHaveURL(/ecommerce-redesign/);
  });

  test('shows visit site link when project_url exists', {
    tag: ['@outcome:display', ...PUBLIC_PORTFOLIO_DETAIL, '@role:guest'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display flow — the external "Visit Site" link is asserted by its href)
    await setupMock(page);
    await page.goto('/en-us/portfolio-works/ecommerce-redesign');

    const visitLink = page.getByRole('article').getByRole('link', { name: /Visit Site/ });
    await expect(visitLink).toBeVisible();
    await expect(visitLink).toHaveAttribute('href', 'https://example-client.com');
  });

  test('shows 404 for nonexistent slug', {
    tag: ['@outcome:failure', ...PUBLIC_PORTFOLIO_DETAIL, '@role:guest'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (deep-link entry — asserts the not-found state renders for an unknown slug)
    await setupMock(page);
    await page.goto('/en-us/portfolio-works/nonexistent-project');

    await expect(page.getByText('Project not found')).toBeVisible();
    await expect(page.getByRole('link', { name: /Back to portfolio/ })).toBeVisible();
  });

  test('CTA section is visible', {
    tag: ['@outcome:display', ...PUBLIC_PORTFOLIO_DETAIL, '@role:guest'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display flow — asserts the closing CTA renders with its quote link)
    await setupMock(page);
    await page.goto('/en-us/portfolio-works/ecommerce-redesign');

    await expect(page.getByText('Ready to Build Something Like This?')).toBeVisible();
    await expect(page.getByRole('link', { name: /Get a Quote/ })).toBeVisible();
  });
});
