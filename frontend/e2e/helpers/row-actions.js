import { expect } from './test.js';

/**
 * Row actions live behind each row's three-dot button, in a modal menu.
 *
 * `chooseRowAction` waits until the menu has left the DOM: its 200ms fade
 * briefly overlaps the dialog the entry opens, and a role or text lookup in
 * that window would match both.
 */
export async function openRowMenu(page, { kebab, menu }) {
  await page.getByTestId(kebab).click();
  await expect(page.getByTestId(menu)).toBeVisible();
}

export async function chooseRowAction(page, { kebab, menu, action }) {
  await openRowMenu(page, { kebab, menu });
  await page.getByTestId(menu).getByTestId(action).click();
  await expect(page.getByTestId(menu)).toHaveCount(0);
}
