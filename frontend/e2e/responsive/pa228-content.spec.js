/** PA-228 / RESP-R019: all three source actions remain reachable beside editable long URLs. */
import { test, expect } from '../helpers/test.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES } from './catalog-scenarios.js';
import { openPa228, sources, resizeFromDesktop, expectFitsHorizontally, expectPageFits } from '../helpers/pa228-responsive.js';

test.setTimeout(60_000);

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`PA-228 blog · ${profile}`, {
    tag: ['@responsive:content', '@responsive-special:content', '@responsive-batch:content-special-1', `@viewport:${profile}`],
  }, () => {
    test.use(viewportUse(profile));

    test('long source URLs retain their remove actions', {
      tag: ['@flow:admin-blog-edit', '@outcome:success'],
    }, async ({ page }) => {
      // quality: allow-deep-link (PA-228 requires loading the fixture editor directly at each viewport)
      await openPa228(page, '/panel/blog/1/edit');
      const rows = page.getByTestId('blog-source-row');
      await expect(rows).toHaveCount(3);
      await expectFitsHorizontally(rows.getByRole('button', { name: 'Quitar fuente', exact: true }));
      await expectFitsHorizontally(rows.getByRole('textbox'));
      await expectPageFits(page);

      await resizeFromDesktop(page, profile);
      await expectFitsHorizontally(rows.getByRole('button', { name: 'Quitar fuente', exact: true }));
      const url = page.getByRole('textbox', { name: 'URL de la fuente 2', exact: true });
      await url.fill('https://example.test/fuente-editada');
      await expect(url).toHaveValue('https://example.test/fuente-editada');
      await rows.nth(1).getByRole('button', { name: 'Quitar fuente', exact: true }).click();
      await expect(rows).toHaveCount(2);
      await expect(page.getByRole('textbox', { name: 'URL de la fuente 2', exact: true })).toHaveValue(sources[2].url);
      await expectPageFits(page);
    });
  });
}
