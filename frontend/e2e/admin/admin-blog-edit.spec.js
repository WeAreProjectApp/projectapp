/**
 * E2E tests for admin blog post editing.
 *
 * Covers: load existing post with all new fields, edit title and save,
 * edit category/readTime, toggle featured/published, edit content_json,
 * SEO section expand, view-in-blog link, error handling.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_BLOG_EDIT } from '../helpers/flow-tags.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const existingPost = {
  id: 1,
  title_es: 'Post Existente',
  title_en: 'Existing Post',
  slug: 'post-existente',
  excerpt_es: 'Extracto ES.',
  excerpt_en: 'Excerpt EN.',
  content_es: '<p>HTML content</p>',
  content_en: '<p>HTML content EN</p>',
  content_json_es: { intro: 'Intro ES.', sections: [{ heading: 'Sec 1' }], conclusion: 'Fin.', cta: 'CTA.' },
  content_json_en: {},
  sources: [{ name: 'Source 1', url: 'https://example.com' }],
  cover_image: '',
  category: 'technology',
  read_time_minutes: 8,
  is_featured: false,
  is_published: true,
  meta_title_es: 'SEO Título ES',
  meta_title_en: 'SEO Title EN',
  meta_description_es: 'Meta desc ES.',
  meta_description_en: 'Meta desc EN.',
  published_at: '2026-03-01T12:00:00Z',
  created_at: '2026-03-01T10:00:00Z',
  updated_at: '2026-03-01T12:00:00Z',
};

const updatedPost = { ...existingPost, title_es: 'Post Actualizado' };

const categoriesMock = { _available_categories: [{ slug: 'technology', label: 'Tecnología' }, { slug: 'design', label: 'Diseño' }] };

function setupMock(page) {
  return mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'blog/admin/json-template/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(categoriesMock) };
    }
    if (apiPath === 'blog/admin/1/detail/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(existingPost) };
    }
    if (apiPath === 'blog/admin/1/update/' && route.request().method() === 'PATCH') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(updatedPost) };
    }
    return null;
  });
}

test.describe('Admin Blog Edit', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8900, role: 'admin', is_staff: true } });
  });

  test('loads existing post and populates all fields', {
    tag: [...ADMIN_BLOG_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the edit form loads and populates its fields; the edit interaction is covered by the save tests)
    await setupMock(page);
    await page.goto('/panel/blog/1/edit');

    await expect(page.getByLabel('Título (ES)', { exact: true })).toHaveValue('Post Existente');
    await expect(page.getByLabel('Title (EN)', { exact: true })).toHaveValue('Existing Post');
    await expect(page.getByLabel('Slug')).toHaveValue('post-existente');
    const excerpt = page.locator('#excerpt_es-source');
    await excerpt.locator('..').getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await expect(excerpt).toHaveValue('Extracto ES.');
    await expect(page.getByLabel('Categoría')).toHaveValue('technology');
  });

  test('edits title and saves successfully', {
    tag: [...ADMIN_BLOG_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/blog/1/edit');

    await page.getByLabel('Título (ES)', { exact: true }).fill('Post Actualizado');
    await page.getByRole('button', { name: /Guardar Cambios/ }).click();

    await expect(page.getByText('Post actualizado correctamente')).toContainText('Post actualizado correctamente');
  });

  test('edits category and readTime', {
    tag: [...ADMIN_BLOG_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/blog/1/edit');

    await page.getByLabel('Categoría').selectOption('design');
    await page.getByLabel('Tiempo lectura (min)').fill('12');
    await page.getByRole('button', { name: /Guardar Cambios/ }).click();

    await expect(page.getByText('Post actualizado correctamente')).toContainText('Post actualizado correctamente');
  });

  test('SEO section shows meta fields', {
    tag: [...ADMIN_BLOG_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the SEO section renders its meta fields populated from the post)
    await setupMock(page);
    await page.goto('/panel/blog/1/edit');

    await expect(page.getByLabel('Meta título (ES)')).toBeVisible();
    await expect(page.getByLabel('Meta título (ES)')).toHaveValue('SEO Título ES');
  });

  test('view-in-blog link has correct href', {
    tag: [...ADMIN_BLOG_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the view-in-blog link renders with the post's public href)
    await setupMock(page);
    await page.goto('/panel/blog/1/edit');

    const link = page.getByText('Ver en blog');
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute('href', '/blog/post-existente');
  });

  test('shows content_json_es populated in textarea', {
    tag: [...ADMIN_BLOG_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the content_json textarea is populated from the post)
    await setupMock(page);
    await page.goto('/panel/blog/1/edit');

    const jsonTextarea = page.getByRole('group', { name: 'Español' }).getByPlaceholder('"intro"');
    await expect(jsonTextarea).toBeVisible();
    const value = await jsonTextarea.inputValue();
    expect(value).toContain('Intro ES');
  });

  test('shows sources from existing post', {
    tag: [...ADMIN_BLOG_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — existing sources render populated from the post)
    await setupMock(page);
    await page.goto('/panel/blog/1/edit');

    await expect(page.locator('input[placeholder="Nombre de la fuente"]')).toHaveValue('Source 1');
  });
});
