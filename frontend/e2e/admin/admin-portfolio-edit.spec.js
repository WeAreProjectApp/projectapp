/**
 * E2E tests for admin portfolio work editing.
 *
 * Covers: load existing work with all fields, edit title and save,
 * SEO section shows meta fields, view-in-public link, content_json populated.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PORTFOLIO_EDIT } from '../helpers/flow-tags.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const existingWork = {
  id: 1,
  title_es: 'Proyecto Existente',
  title_en: 'Existing Project',
  slug: 'proyecto-existente',
  excerpt_es: 'Tagline ES.',
  excerpt_en: 'Tagline EN.',
  project_url: 'https://existing-project.com',
  cover_image_url: '',
  cover_image_display: '',
  content_json_es: { problem: { title: 'El Desafío', description: 'Descripción del problema.' } },
  content_json_en: {},
  order: 1,
  is_published: true,
  meta_title_es: 'SEO Título ES',
  meta_title_en: 'SEO Title EN',
  meta_description_es: 'Meta desc ES.',
  meta_description_en: 'Meta desc EN.',
  meta_keywords_es: 'keyword1, keyword2',
  meta_keywords_en: 'keyword1, keyword2',
  published_at: '2026-03-01T12:00:00Z',
  created_at: '2026-03-01T10:00:00Z',
};

const updatedWork = { ...existingWork, title_es: 'Proyecto Actualizado' };

function setupMock(page, workId = 1) {
  return mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === `portfolio/admin/${workId}/detail/`) {
      const work = { ...existingWork, id: workId, is_published: workId !== 11 };
      return { status: 200, contentType: 'application/json', body: JSON.stringify(work) };
    }
    if (apiPath === 'portfolio/admin/1/update/' && route.request().method() === 'PATCH') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(updatedWork) };
    }
    return null;
  });
}

test.describe('Admin Portfolio Edit', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9400, role: 'admin', is_staff: true } });
  });

  test('loads existing work and populates all fields', {
    tag: [...ADMIN_PORTFOLIO_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the edit form loads and populates its fields from the API; the edit interaction is covered by the save test)
    await setupMock(page);
    await page.goto('/panel/portfolio/1/edit');

    const esGroup = page.getByRole('group', { name: 'Español' });
    await expect(esGroup.getByRole('textbox', { name: 'Título (ES)', exact: true })).toHaveValue('Proyecto Existente');
    await expect(esGroup.getByRole('textbox', { name: 'Tagline (ES)', exact: true })).toHaveValue('Tagline ES.');

    const enGroup = page.getByRole('group', { name: 'English' });
    await expect(enGroup.getByRole('textbox', { name: 'Title (EN)', exact: true })).toHaveValue('Existing Project');

    await expect(page.locator('label:has-text("Slug")').locator('..').locator('input')).toHaveValue('proyecto-existente');
  });

  for (const workId of [2, 11]) {
    test(`focuses each bilingual field through its label for work ${workId}`, {
      tag: [...ADMIN_PORTFOLIO_EDIT, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      await setupMock(page, workId);
      await page.goto(`/en-us/panel/portfolio/${workId}/edit`, { waitUntil: 'domcontentloaded' });

      for (const label of ['Título (ES)', 'Tagline (ES)', 'Title (EN)', 'Tagline (EN)']) {
        await page.getByText(label, { exact: true }).click();
        await expect(page.getByRole('textbox', { name: label, exact: true })).toBeFocused();
      }
      await page.getByRole('textbox', { name: 'Title (EN)', exact: true }).press('Tab');
      await expect(page.getByRole('textbox', { name: 'Tagline (EN)', exact: true })).toBeFocused();
    });
  }

  test('edits title and saves successfully', {
    tag: [...ADMIN_PORTFOLIO_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/portfolio/1/edit');

    const esGroup = page.getByRole('group', { name: 'Español' });
    await esGroup.getByRole('textbox', { name: 'Título (ES)', exact: true }).fill('Proyecto Actualizado');
    await page.getByRole('button', { name: /Guardar cambios/ }).click();

    await expect(page.getByText('Proyecto guardado correctamente')).toContainText('Proyecto guardado correctamente');
  });

  test('SEO section shows meta fields', {
    tag: [...ADMIN_PORTFOLIO_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the SEO section renders its meta fields populated from the work)
    await setupMock(page);
    await page.goto('/panel/portfolio/1/edit');

    const seoGroup = page.getByRole('group', { name: 'SEO' });
    await expect(seoGroup.locator('label:has-text("Meta título (ES)")').locator('..').locator('input')).toHaveValue('SEO Título ES');
    await expect(seoGroup.locator('label:has-text("Meta title (EN)")').locator('..').locator('input')).toHaveValue('SEO Title EN');
  });

  test('view-in-public link has correct href', {
    tag: [...ADMIN_PORTFOLIO_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the view-in-public link renders with the work's public href)
    await setupMock(page);
    await page.goto('/panel/portfolio/1/edit');

    const link = page.getByText('Ver en público');
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute('href', '/portfolio-works/proyecto-existente');
  });

  test('shows content_json_es populated in textarea', {
    tag: [...ADMIN_PORTFOLIO_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the content_json textarea is populated from the work)
    await setupMock(page);
    await page.goto('/panel/portfolio/1/edit');

    const jsonTextarea = page.getByRole('group', { name: 'Español' }).getByPlaceholder('"problem"');
    await expect(jsonTextarea).toBeVisible();
    const value = await jsonTextarea.inputValue();
    expect(value).toContain('El Desafío');
  });
});
