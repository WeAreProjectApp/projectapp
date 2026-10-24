/**
 * E2E tests for admin blog post creation.
 *
 * Covers: Manual mode (full fields, minimal fields), JSON import mode
 * (paste valid JSON, invalid JSON, template download button, submit),
 * tab switching between modes.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_BLOG_CREATE, ADMIN_BLOG_CREATE_FROM_JSON } from '../helpers/flow-tags.js';
import { fillRichTextSource } from '../helpers/editorial.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
const createdPost = { id: 99, title_es: 'Nuevo Post', title_en: 'New Post', slug: 'nuevo-post', is_published: false, category: 'ai', read_time_minutes: 5 };
const jsonTemplate = {
  title_es: 'Plantilla', title_en: 'Template',
  content_json_es: { intro: 'I', sections: [{ heading: 'H' }] },
  content_json_en: { intro: 'I', sections: [{ heading: 'H' }] },
  _available_categories: [
    { slug: 'ai', label: 'AI' },
    { slug: 'design', label: 'Design' },
    { slug: 'technology', label: 'Technology' },
  ],
};

function setupMock(page, { createResponse = createdPost, onCreate = () => {} } = {}) {
  return mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'blog/admin/create/' && route.request().method() === 'POST') {
      onCreate(route.request().postDataJSON());
      return { status: 201, contentType: 'application/json', body: JSON.stringify(createResponse) };
    }
    if (apiPath === 'blog/admin/create-from-json/' && route.request().method() === 'POST') {
      return { status: 201, contentType: 'application/json', body: JSON.stringify(createResponse) };
    }
    if (apiPath === 'blog/admin/json-template/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(jsonTemplate) };
    }
    return null;
  });
}

test.describe('Admin Blog Create', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8800, role: 'admin', is_staff: true } });
  });

  test('renders form with Manual/JSON tabs', {
    tag: [...ADMIN_BLOG_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the create form renders its Manual/JSON tabs and language fieldsets; the create interactions are covered below)
    await setupMock(page);
    await page.goto('/panel/blog/create');

    await expect(page.getByRole('button', { name: 'Manual' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Importar JSON' })).toBeVisible();
    await expect(page.locator('legend').filter({ hasText: 'Español' })).toBeVisible();
    await expect(page.locator('legend').filter({ hasText: 'English' })).toBeVisible();
  });

  test('manual mode: fills all fields and submits successfully', {
    tag: [...ADMIN_BLOG_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let postBody = null;
    await setupMock(page, { onCreate: body => { postBody = body; } });
    await page.goto('/panel/blog/create');

    await page.getByLabel('Título (ES)').fill('Nuevo Post ES');
    await page.getByLabel('Title (EN)').fill('New Post EN');
    await fillRichTextSource(page.locator('#excerpt_es-source').locator('..'), 'Resumen corto.');
    await fillRichTextSource(page.locator('#excerpt_en-source').locator('..'), 'Short excerpt.');
    await fillRichTextSource(page.locator('#content_es-source').locator('..'), '<p>Contenido</p>');
    await fillRichTextSource(page.locator('#content_en-source').locator('..'), '<p>Content</p>');
    await page.getByLabel('Categoría').selectOption('ai');
    await page.getByLabel('Tiempo lectura (min)').fill('8');
    await page.getByLabel('Imagen de portada (URL)').fill('https://example.com/img.jpg');

    await page.getByRole('button', { name: 'Crear Post' }).click();

    // a successful create navigates away from the create form
    await expect(page).not.toHaveURL(/\/create/);
    expect(postBody).toMatchObject({
      excerpt_es: 'Resumen corto.', excerpt_en: 'Short excerpt.',
      content_es: '<p>Contenido</p>', content_en: '<p>Content</p>',
      text_formats: {
        '/excerpt_es': 'markdown_html_v1', '/excerpt_en': 'markdown_html_v1',
        '/content_es': 'markdown_html_v1', '/content_en': 'markdown_html_v1',
      },
    });
  });

  test('manual mode: submits with only required fields (no category, no readTime)', {
    tag: [...ADMIN_BLOG_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let postBody = null;
    await setupMock(page, { onCreate: body => { postBody = body; } });
    await page.goto('/panel/blog/create');

    await page.getByLabel('Título (ES)').fill('Post Mínimo');
    await page.getByLabel('Title (EN)').fill('Minimal Post');
    await fillRichTextSource(page.locator('#excerpt_es-source').locator('..'), 'Extracto.');
    await fillRichTextSource(page.locator('#excerpt_en-source').locator('..'), 'Excerpt.');

    await page.getByRole('button', { name: 'Crear Post' }).click();

    // a successful create navigates away from the create form
    await expect(page).not.toHaveURL(/\/create/);
    expect(postBody).toMatchObject({
      title_es: 'Post Mínimo', title_en: 'Minimal Post',
      excerpt_es: 'Extracto.', excerpt_en: 'Excerpt.',
      text_formats: { '/excerpt_es': 'markdown_html_v1', '/excerpt_en': 'markdown_html_v1' },
    });
  });

  test('switches to JSON import tab and shows template download', {
    tag: [...ADMIN_BLOG_CREATE_FROM_JSON, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/blog/create');

    await page.getByRole('button', { name: 'Importar JSON' }).click();

    await expect(page.getByText('Plantilla JSON')).toContainText('Plantilla JSON');
    await expect(page.getByText('Pegar o subir JSON')).toBeVisible();
    await expect(page.getByRole('button', { name: /Descargar Plantilla/ })).toBeVisible();
  });

  test('JSON mode: paste valid JSON shows preview and metadata form', {
    tag: [...ADMIN_BLOG_CREATE_FROM_JSON, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/blog/create');

    await page.getByRole('button', { name: 'Importar JSON' }).click();

    const validJson = JSON.stringify({
      title_es: 'Post desde JSON',
      title_en: 'Post from JSON',
      excerpt_es: 'Resumen.',
      excerpt_en: 'Excerpt.',
      content_json_es: { intro: 'Intro.', sections: [{ heading: 'S1' }] },
      category: 'technology',
    });
    const jsonTextarea = page.getByPlaceholder(/title_es/);
    await jsonTextarea.fill(validJson);
    await jsonTextarea.dispatchEvent('input');

    await expect(page.getByText('Post desde JSON')).toContainText('Post desde JSON');
    await expect(page.getByText('Opciones de publicación')).toBeVisible();
    await expect(page.getByRole('button', { name: /Crear desde JSON/ })).toBeVisible();
  });

  test('JSON mode: paste invalid JSON shows error', {
    tag: [...ADMIN_BLOG_CREATE_FROM_JSON, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/blog/create');

    await page.getByRole('button', { name: 'Importar JSON' }).click();
    const jsonTextarea = page.getByPlaceholder(/title_es/);
    await jsonTextarea.fill('{ invalid json }');
    await jsonTextarea.dispatchEvent('input');

    await expect(page.getByText('JSON inválido')).toContainText('JSON inválido');
  });

  test('JSON mode: paste JSON missing required fields shows error', {
    tag: [...ADMIN_BLOG_CREATE_FROM_JSON, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/blog/create');

    await page.getByRole('button', { name: 'Importar JSON' }).click();
    const incompleteJson = JSON.stringify({ title_es: 'Solo título' });
    const jsonTextarea = page.getByPlaceholder(/title_es/);
    await jsonTextarea.fill(incompleteJson);
    await jsonTextarea.dispatchEvent('input');

    await expect(page.getByText(/title_en/)).toContainText(/title_en/);
  });

  test('JSON mode: submit valid JSON creates post', {
    tag: [...ADMIN_BLOG_CREATE_FROM_JSON, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/blog/create');

    await page.getByRole('button', { name: 'Importar JSON' }).click();

    const fullJson = JSON.stringify({
      title_es: 'Post JSON Completo',
      title_en: 'Full JSON Post',
      excerpt_es: 'Resumen.',
      excerpt_en: 'Excerpt.',
      content_json_es: { intro: 'Intro.', sections: [{ heading: 'H1' }], conclusion: 'Fin.', cta: 'CTA.' },
    });
    const jsonTextarea = page.getByPlaceholder(/title_es/);
    await jsonTextarea.fill(fullJson);
    await jsonTextarea.dispatchEvent('input');

    await page.getByRole('button', { name: /Crear desde JSON/ }).click();

    // a successful create navigates away from the create form
    await expect(page).not.toHaveURL(/\/create/);
  });
});
