/**
 * E2E tests for the public contact form submission.
 *
 * Covers: form render, successful submission, and the API-failure error path
 * (localized message rendered, no redirect).
 */
import { test, expect } from '../helpers/test.js';
import { fillContactForm } from '../helpers/contact-form.js';
import { mockApi } from '../helpers/api.js';
import { PUBLIC_CONTACT_SUBMIT } from '../helpers/flow-tags.js';

const CONTACT_DISPLAY = [...PUBLIC_CONTACT_SUBMIT, '@role:guest', '@outcome:display'];

test.describe('Contact Form Submit', () => {
  test.setTimeout(60_000);

  test('keeps the form in Spanish after switching locale', {
    tag: CONTACT_DISPLAY,
  }, async ({ page }) => {
    await page.goto('/en-us/contact', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { level: 1, name: /Need a professional website/ })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Full name' })).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en-US');
    await page.getByRole('button', { name: 'Switch to Spanish', exact: true }).filter({ visible: true }).click();
    await expect(page).toHaveURL('/es-co/contact');
    const heading = page.getByRole('heading', { level: 1, name: /¿Necesitas un sitio web profesional\?/ });
    await expect(heading).toBeVisible();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(heading).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('lang', 'es-CO');
    const form = page.getByTestId('contact-form');
    await expect(form.getByRole('textbox', { name: 'Nombre completo' })).toBeVisible();
    await expect(form.getByRole('textbox', { name: 'Número de teléfono' })).toBeVisible();
    await expect(form.getByRole('textbox', { name: 'Tu correo electrónico' })).toBeVisible();
    await expect(form.getByRole('textbox', { name: 'Cuéntanos sobre tu proyecto web' })).toBeVisible();
    await expect(form.getByText('Presupuesto estimado (USD)', { exact: true })).toBeVisible();
    await expect(form.getByRole('button', { name: 'Enviar mensaje', exact: true })).toBeEnabled();
  });

  test('localizes the confirmation on direct entry', {
    tag: CONTACT_DISPLAY,
  }, async ({ page }) => {
    // quality: allow-deep-link (contact confirmation is also reachable by direct URL)
    await page.goto('/en-us/contact-success', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { level: 1, name: /Thank you for contacting us!/ })).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en-US');

    await page.getByRole('button', { name: 'Switch to Spanish', exact: true }).filter({ visible: true }).click();
    await expect(page).toHaveURL('/es-co/contact-success');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { level: 1, name: /¡Gracias por contactarnos!/ })).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('lang', 'es-CO');
    await expect(page.getByRole('link', { name: 'Ver nuestro portafolio' })).toHaveAttribute('href', '/es-co/portfolio-works');
  });

  test('reaches English confirmation after one submission', {
    tag: [...PUBLIC_CONTACT_SUBMIT, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    const contactPosts = [];
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'new-contact/' && method === 'POST') {
        contactPosts.push(route.request().postDataJSON());
        return {
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            email: 'test@example.com',
            subject: 'Test User',
          }),
        };
      }
      return null;
    });

    await page.goto('/en-us/contact', { waitUntil: 'domcontentloaded' });
    const form = page.getByTestId('contact-form');
    await fillContactForm(form);
    await form.getByRole('button', { name: 'Send message', exact: true }).click();

    await expect(page).toHaveURL('/en-us/contact-success');
    await expect(page.getByRole('heading', { level: 1, name: /Thank you for contacting us!/ })).toHaveCSS('opacity', '1');
    await expect(form).toHaveCount(0);
    expect(contactPosts).toEqual([{
      email: 'test@example.com',
      phone_number: '+573001234567',
      subject: 'Test User',
      message: 'E2E contact project description',
      budget: '500-5K',
    }]);
  });

  test('keeps an accepted contact from being submitted again after a route failure', {
    tag: [...PUBLIC_CONTACT_SUBMIT, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    let contactPosts = 0;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'new-contact/' && method === 'POST') {
        contactPosts += 1;
        return { status: 201, contentType: 'application/json', body: JSON.stringify({ id: 1 }) };
      }
      return null;
    });
    await page.goto('/en-us/contact', { waitUntil: 'domcontentloaded' });
    const form = page.getByTestId('contact-form');
    await fillContactForm(form);
    await page.evaluate(() => {
      const router = document.getElementById('__nuxt').__vue_app__.config.globalProperties.$router;
      router.beforeEach((to) => {
        if (to.path !== '/en-us/contact-success') return;
        window.contactConfirmationBlocked = true;
        return false;
      });
    });

    const submit = form.getByRole('button', { name: 'Send message', exact: true });
    await submit.click();
    await expect.poll(() => page.evaluate(() => window.contactConfirmationBlocked)).toBe(true);
    await expect(submit).toBeDisabled();
    await form.getByRole('textbox', { name: 'Full name', exact: true }).press('Enter');
    expect(contactPosts).toBe(1);
  });

  test('shows the Spanish submission error on the form', {
    tag: [...PUBLIC_CONTACT_SUBMIT, '@role:guest', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'new-contact/' && method === 'POST') {
        return {
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal error' }),
        };
      }
      return null;
    });

    await page.goto('/es-co/contact', { waitUntil: 'domcontentloaded' });
    const form = page.getByTestId('contact-form');
    await fillContactForm(form, 'es');
    const submit = form.getByRole('button', { name: 'Enviar mensaje', exact: true });
    await submit.click();

    const alert = page.getByTestId('contact-submit-error');
    await expect(alert).toBeVisible({ timeout: 10000 });
    await expect(alert).toHaveText('No pudimos enviar tu mensaje. Por favor inténtalo de nuevo.');
    await expect(page).toHaveURL('/es-co/contact');
    await expect(submit).toBeEnabled();
  });
});
