// Geometry contract of the compact panel form modals ("Field widths" in
// components/base/README.md): the panel stays within the `form` width, the
// body never scrolls sideways, and each line of fields shares one row from the
// portrait breakpoint up and stacks in reading order below it.
//
// Every rect is read in ONE evaluate so related boxes share a frame: the admin
// <main> animates for 300 ms after a viewport change, and boxes read one by one
// can straddle two frames.
import { expect } from './test.js';
import { PANEL_BREAKPOINTS } from '../../config/responsive.js';

export const FORM_MODAL_MAX_WIDTH = 672;
const DEFAULT_FIELD_MAX_WIDTH = 320;

/**
 * @param dialog Locator of the `role="dialog"` overlay.
 * @param lines  `[{ fields: [Locator, …], maxWidth? }]`, each line one row.
 */
export async function readModalLayout(dialog, lines = []) {
  const fieldHandles = [];
  for (const line of lines) {
    fieldHandles.push(await Promise.all(line.fields.map((field) => field.elementHandle())));
  }
  // quality: allow-fragile-selector (BaseModal publishes these stable geometry hooks for its panel and scrolling body)
  const layout = await dialog.locator('[data-modal-kind]').evaluate((panel, rows) => {
    const box = (element) => {
      const rect = element.getBoundingClientRect();
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
    };
    const body = panel.querySelector('[data-modal-body]') || panel;
    return {
      panel: box(panel),
      body: { width: body.clientWidth, content: body.scrollWidth, height: body.scrollHeight },
      lines: rows.map((row) => row.map(box)),
    };
  }, fieldHandles);
  await Promise.all(fieldHandles.flat().map((handle) => handle.dispose()));
  return layout;
}

export function modalLayoutViolations(layout, viewport, {
  maxPanel = FORM_MODAL_MAX_WIDTH, lines = [], maxBodyHeight,
} = {}) {
  const violations = [];
  const stacked = viewport.width < PANEL_BREAKPOINTS.portrait;
  const panelLimit = Math.min(viewport.width, maxPanel);
  if (layout.panel.width > panelLimit + 0.5) {
    violations.push(`panel ${Math.round(layout.panel.width)}px > ${panelLimit}px`);
  }
  if (layout.body.content > layout.body.width + 1) {
    violations.push(`body scrolls sideways (${layout.body.content} > ${layout.body.width})`);
  }
  if (!stacked && maxBodyHeight && layout.body.height > maxBodyHeight) {
    violations.push(`body ${layout.body.height}px > ${maxBodyHeight}px`);
  }
  layout.lines.forEach((boxes, lineIndex) => {
    const maxWidth = lines[lineIndex]?.maxWidth ?? DEFAULT_FIELD_MAX_WIDTH;
    boxes.forEach((field, fieldIndex) => {
      const where = `line ${lineIndex + 1} field ${fieldIndex + 1}`;
      if (stacked) {
        const previous = boxes[fieldIndex - 1];
        if (previous && field.y < previous.y + previous.height - 1) {
          violations.push(`${where} is not below the previous field`);
        }
        return;
      }
      if (Math.abs(field.y - boxes[0].y) > 1) violations.push(`${where} left the row`);
      if (field.width > maxWidth) {
        violations.push(`${where} ${Math.round(field.width)}px > ${maxWidth}px`);
      }
    });
  });
  return violations;
}

/** Waits until the open modal honours the compact geometry contract. */
export async function expectCompactModal(dialog, viewport, options = {}) {
  await expect.poll(
    async () => modalLayoutViolations(
      await readModalLayout(dialog, options.lines), viewport, options,
    ),
    { message: 'compact modal geometry' },
  ).toEqual([]);
}
