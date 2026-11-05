/** Responsive contract for the calculator editor at every panel viewport. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { calculatorDefinition, generalCalculator, json } from '../helpers/requirement-calculator.js';
import { ADMIN_REQUIREMENT_CALCULATOR_DEFINITION } from '../helpers/flow-tags.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

async function arrange(page) {
  await setAuthLocalStorage(page, { token: 'calculator-responsive-e2e', userAuth: { id: 713, role: 'admin', is_staff: true } });
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'requirement-calculator/' && method === 'GET') return json(generalCalculator(calculatorDefinition()));
    if (apiPath === 'requirement-calculator/revisions/?limit=20&offset=0' && method === 'GET') return json({ count: 0, results: [] });
    return null;
  });
}

for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
  test.describe(`requirement calculator at ${profile}`, () => {
    test.use(viewportUse(profile));

    test('opens classifier signals without horizontal overflow', {
      tag: [...ADMIN_REQUIREMENT_CALCULATOR_DEFINITION, '@role:admin', '@outcome:display', '@responsive:requirement-calculator', `@viewport:${profile}`],
    }, async ({ page }) => {
      // Catches the bug where calculator controls overflow or the classifier catalogue cannot be reached at this panel width.
      await arrange(page);
      // quality: allow-deep-link (this viewport contract exercises the editor control; sidebar navigation is covered by the calculator flow).
      await page.goto('/es-co/panel/requirement-calculator', { waitUntil: 'domcontentloaded' });
      await page.getByText('Señales de clasificación (1)', { exact: true }).click();
      await expect(page.getByText('Formulario', { exact: true })).toHaveText('Formulario');
      await expect(page.getByTestId('calculator-XS-points')).toHaveValue('1');
      const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth);
      expect(overflow, `El editor desborda ${overflow}px en ${profile}`).toBeLessThanOrEqual(1);
      const control = await page.getByTestId('calculator-XS-points').boundingBox();
      expect(control, `El control XS no es medible en ${profile}`).not.toBeNull();
      expect(control.width, `El control XS perdió tamaño utilizable en ${profile}`).toBeGreaterThan(43);
      expect(control.height, `El control XS perdió altura utilizable en ${profile}`).toBeGreaterThan(30);
    });
  });
}
