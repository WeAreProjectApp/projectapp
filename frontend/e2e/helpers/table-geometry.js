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

/**
 * Verifies the observable contract of content-sized ledger columns without
 * coupling an E2E test to Tailwind tracks or a fixed pixel width. The text in
 * a money cell ends at its right content edge, Tipo and Valor only reserve
 * room for the widest visible value in their columns, and the primary text
 * cell receives the remaining room.
 */
export async function expectContentSizedColumns(row, {
  primaryLabel = 'Concepto',
  typeLabel = null,
  valueLabel = 'Total',
} = {}) {
  const geometry = await row.evaluate((node, labels) => {
    const root = node.closest('table') || node.closest('[role="table"]');
    const headers = [...root.querySelectorAll('thead th, [role="columnheader"]')]
      .filter((header) => header.getClientRects().length > 0);
    const headerIndex = (label) => headers.findIndex((header) => header.textContent.trim() === label);
    const cells = [...node.querySelectorAll(':scope > td, :scope > [role="cell"]')]
      .filter((cell) => cell.getClientRects().length > 0);
    const textMeasure = (element) => {
      let content = element;
      while (content) {
        const visibleChildren = [...content.children]
          .filter((child) => child.getClientRects().length > 0);
        const hasDirectText = [...content.childNodes]
          .some((child) => child.nodeType === Node.TEXT_NODE && child.textContent.trim());
        if (hasDirectText || visibleChildren.length !== 1) break;
        const [child] = visibleChildren;
        if (getComputedStyle(child).display !== 'block') break;
        content = child;
      }
      const range = document.createRange();
      range.selectNodeContents(content);
      const text = range.getBoundingClientRect();
      const style = getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return {
        cellLeft: box.left,
        cellRight: box.right,
        cellWidth: box.width,
        contentLeft: content.getBoundingClientRect().left,
        padLeft: Number.parseFloat(style.paddingLeft),
        padRight: Number.parseFloat(style.paddingRight),
        textLeft: text.left,
        textRight: text.right,
        textWidth: text.width,
      };
    };
    const column = (label) => {
      const index = headerIndex(label);
      const bodyCells = [...root.querySelectorAll('tbody tr, [role="row"]')]
        .filter((tableRow) => tableRow.getClientRects().length > 0)
        .map((tableRow) => [...tableRow.querySelectorAll(':scope > td, :scope > [role="cell"]')]
          .filter((cell) => cell.getClientRects().length > 0)[index])
        .filter(Boolean);
      return [headers[index], ...bodyCells].map(textMeasure);
    };
    const measure = (label) => {
      const cell = cells[headerIndex(label)];
      return textMeasure(cell);
    };
    const columnBounds = (label) => {
      const measured = column(label);
      return {
        widestText: Math.max(...measured.map(({ textWidth }) => textWidth)),
        widestPadding: Math.max(...measured.map(({ padLeft, padRight }) => padLeft + padRight)),
      };
    };
    const interveningWidth = labels.typeLabel
      ? cells.slice(headerIndex(labels.typeLabel) + 1, headerIndex(labels.valueLabel))
        .reduce((width, cell) => width + cell.getBoundingClientRect().width, 0)
      : 0;
    return {
      primary: measure(labels.primaryLabel),
      type: labels.typeLabel ? measure(labels.typeLabel) : null,
      value: measure(labels.valueLabel),
      primaryBounds: columnBounds(labels.primaryLabel),
      typeBounds: labels.typeLabel ? columnBounds(labels.typeLabel) : null,
      valueBounds: columnBounds(labels.valueLabel),
      typeToValueGap: labels.typeLabel
        ? measure(labels.valueLabel).textLeft - measure(labels.typeLabel).textRight - interveningWidth
        : null,
    };
  }, { primaryLabel, typeLabel, valueLabel });

  const tolerance = 2;
  expect(Math.abs(geometry.value.textRight - (geometry.value.cellRight - geometry.value.padRight)))
    .toBeLessThanOrEqual(tolerance);
  expect(geometry.value.cellWidth)
    .toBeLessThanOrEqual(geometry.valueBounds.widestText + geometry.valueBounds.widestPadding + tolerance);
  expect(geometry.primary.cellWidth)
    .toBeGreaterThan(geometry.primaryBounds.widestText + geometry.primaryBounds.widestPadding + tolerance);
  if (geometry.type) {
    expect(Math.abs(geometry.type.contentLeft - (geometry.type.cellLeft + geometry.type.padLeft)))
      .toBeLessThanOrEqual(tolerance);
    expect(geometry.type.cellWidth)
      .toBeLessThanOrEqual(geometry.typeBounds.widestText + geometry.typeBounds.widestPadding + tolerance);
    expect(geometry.typeToValueGap)
      .toBeLessThanOrEqual(
        geometry.type.padRight
        + geometry.value.padLeft
        + (geometry.typeBounds.widestText - geometry.type.textWidth)
        + (geometry.valueBounds.widestText - geometry.value.textWidth)
        + tolerance,
      );
  }
}
