import { expect } from './test.js';

/**
 * Asserts that a leading-kebab table fills its own width: the header cells the
 * current viewport shows add up to the table, the last one reaches its right
 * edge, and the actions track keeps its fixed 56px.
 *
 * A fixed-layout table once handed the columns a narrow profile hides their
 * desktop share, so the visible ones stopped short and left a blank band.
 * Checking for horizontal overflow alone cannot see that: nothing overflows.
 */
export async function expectNoBlankBand(table) {
  const geometry = await table.evaluate((node) => {
    const shown = [...node.querySelectorAll('thead th')]
      .filter((header) => getComputedStyle(header).display !== 'none');
    const box = node.getBoundingClientRect();
    const actions = node.querySelector('thead th[aria-label="Acciones"]');
    return {
      tableWidth: box.width,
      tableRight: box.right,
      headersWidth: shown.reduce((sum, header) => sum + header.getBoundingClientRect().width, 0),
      lastRight: shown.at(-1)?.getBoundingClientRect().right ?? box.left,
      actionsWidth: actions?.getBoundingClientRect().width ?? 0,
    };
  });

  expect(Math.abs(geometry.tableWidth - geometry.headersWidth)).toBeLessThanOrEqual(1);
  expect(Math.abs(geometry.tableRight - geometry.lastRight)).toBeLessThanOrEqual(1);
  expect(Math.abs(geometry.actionsWidth - 56)).toBeLessThanOrEqual(1);
}
