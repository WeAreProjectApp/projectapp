/**
 * Shared layout rules for the accounting module tables.
 *
 * Why this exists: every table used to size its columns by splitting the
 * available width between them, so a one-character "Día" got as much room as a
 * name. Widths now come from what a column actually shows, the slack is shared
 * out in proportion to that, and the density is one standard instead of
 * per-component guesswork.
 *
 * Consumed by BaseResponsiveTable/AccountingTable (real <table> elements) and
 * the grouped accounting tables (ARIA grids of divs), which is why every size
 * carries BOTH a grid track and a table width — the two layout engines need
 * different units for the same intent.
 *
 * NOTE: the Tailwind classes below only survive the JIT purge because
 * tailwind.config.js scans ./utils/**. Keep them as plain literals; a class
 * assembled from string concatenation is invisible to the scanner.
 */

/** Row height standard for the module: 2.25rem = 36px. */
export const ROW_MIN_HEIGHT = 'min-h-9';

export const TABLE_DENSITY = {
  /**
   * Header and body share one horizontal rhythm so a column's label always sits
   * over its values. The edge overrides keep the content clear of the card
   * border without paying that padding between every pair of columns.
   */
  headerCell: 'px-2.5 py-2 first:pl-4 last:pr-4',
  cell: 'px-2.5 py-1.5 first:pl-4 last:pr-4',
  row: ROW_MIN_HEIGHT,
  /** Action icons drive the row height, so they shrink with it. */
  actionButton: 'p-1.5',
  actionIcon: 'w-4 h-4',
};

/**
 * Text containment is semantic, not a side effect of the column width.
 *
 * `wrap` is the safe default for data-owned strings: `anywhere` contributes
 * soft opportunities to the intrinsic minimum, so an identifier without
 * spaces cannot make a flex/grid/table track wider than its container.
 * `truncate` is opt-in for values that expose the complete text elsewhere.
 * `atomic` is reserved for genuinely bounded values (money, dates, numbers).
 */
export const TEXT_POLICY_CLASSES = Object.freeze({
  wrap: 'block min-w-0 w-full max-w-[22rem] whitespace-normal [overflow-wrap:anywhere]',
  truncate: 'block min-w-0 max-w-full truncate',
  atomic: 'whitespace-nowrap',
});

const ATOMIC_SIZES = new Set(['tiny', 'icons', 'money', 'date', 'percent']);

export function textPolicyFor(column = {}) {
  if (Object.hasOwn(TEXT_POLICY_CLASSES, column.textPolicy)) return column.textPolicy;
  const size = column.size || inferSize(column);
  return ATOMIC_SIZES.has(size) ? 'atomic' : 'wrap';
}

export function textPolicyClass(column = {}) {
  return TEXT_POLICY_CLASSES[textPolicyFor(column)];
}

/**
 * Page ceiling: past 1400px a wider page is not a more readable one. It lives
 * on each accounting page's root — not on the table — so on a wide monitor the
 * whole page (KPIs, filters, table) centres as one column and the slack reads
 * as page margin, never as empty bands inside the table's card.
 */
export const PAGE_MAX_WIDTH = 'max-w-[87.5rem] mx-auto';

/**
 * Width vocabulary.
 *
 * `track` feeds grid-template-columns as `minmax(max-content, <weight>fr)`: the
 * content is the floor, so nothing is ever clipped, and the flexible max shares
 * the leftover width out in proportion to `weight`. `width` is the same intent
 * for the <col>-less table, resolved in resolveColumns() to a percentage of the
 * total weight — auto layout honours that proportion but still grows a column
 * whose content overflows, which is why tables default to auto layout: a
 * clipped "$1.200.000…" defeats the point of the table. `menu-start` is the
 * exception from landscape up: with percentage data columns, auto layout hands
 * the slack to the fixed 56px kebab track, so those profiles go fixed and
 * re-share the width among the columns they show (profileWidthVars).
 *
 * `weight` doubles as `rem`, the floor minWidthFor() sums before the wrapper
 * starts scrolling: a column's share of the slack tracks how much room its
 * content needs, which is why "Día" stays narrow while an amount does not.
 */
const SIZES = {
  name: { rem: 10 },
  tiny: { rem: 2.75, nowrap: true },
  badge: { rem: 6, nowrap: true },
  // Wide enough for two 28px icon buttons AND the word "Acciones" at text-xs
  // with tracking — at 4rem the header clipped.
  icons: { rem: 5.25, nowrap: true },
  money: { rem: 7, nowrap: true },
  date: { rem: 6, nowrap: true },
  text: { rem: 5 },
  // Fits "100%" plus the one-character "%" header; tiny (2.75) clips it.
  percent: { rem: 3.5, nowrap: true },
};

for (const spec of Object.values(SIZES)) {
  spec.weight = spec.rem;
  spec.track = `minmax(max-content, ${spec.rem}fr)`;
}

/** Grid track for the drag handle column, which is not part of `columns`. */
export const HANDLE_TRACK = '1.75rem';
export const HANDLE_PAD = 'pl-4 pr-1 py-1.5';

/**
 * Grid track for the selection checkbox column — same width as the `w-10` cell
 * the classic table gives it, so the two views line up. Like the handle it is
 * not part of `columns`, and taking the first position it inherits the job of
 * the `first:pl-4` in TABLE_DENSITY: the padding lives here instead.
 */
export const SELECT_TRACK = '2.5rem';
export const SELECT_PAD = 'pl-4 pr-1 py-1.5';

/**
 * A kebab is a control track, not a data column. 3.5rem leaves the canonical
 * 44px coarse-pointer target plus 6px of breathing room on either side, while
 * staying completely outside the proportional data-column split.
 */
export const ROW_ACTION_MENU_TRACK = '3.5rem';
export const ROW_ACTION_MENU_WIDTH_REM = 3.5;

export const ROW_ACTION_LAYOUTS = Object.freeze({
  INLINE_END: 'inline-end',
  MENU_START: 'menu-start',
});

export const SIZE_NAMES = Object.keys(SIZES);

/**
 * Infer a size when the column does not declare one, so the nine consuming
 * pages only annotate what the format cannot already tell us.
 */
function inferSize(col) {
  if (col.size && SIZES[col.size]) return col.size;
  if (col.format === 'money') return 'money';
  if (col.format === 'percent') return 'percent';
  if (col.format === 'date') return 'date';
  if (col.format === 'badge') return 'badge';
  if (col.align === 'center') return 'tiny';
  return 'text';
}

export function alignClass(col) {
  const align = col.align
    || (col.format === 'money' || col.format === 'percent' ? 'right' : 'left');
  if (align === 'right') return 'text-right';
  if (align === 'center') return 'text-center';
  return 'text-left';
}

/**
 * Responsive class maps. Two variants because a <td> that is un-hidden must go
 * back to `display: table-cell`, while a grid item must go back to `block`.
 */
const HIDE_TABLE = {
  md: 'hidden md:table-cell',
  lg: 'hidden lg:table-cell',
};

const HIDE_GRID = {
  md: 'hidden md:block',
  lg: 'hidden lg:block',
};

export function hideClass(col, mode = 'table') {
  if (!col.hideBelow) return '';
  const map = mode === 'grid' ? HIDE_GRID : HIDE_TABLE;
  return map[col.hideBelow] || '';
}

/** Breakpoints a column can survive to, widest-first. */
export const BREAKPOINTS = ['base', 'md', 'lg'];

const VISIBLE_AT = {
  base: (col) => !col.hideBelow,
  md: (col) => col.hideBelow !== 'lg',
  lg: () => true,
};

export function isVisibleAt(col, breakpoint) {
  return (VISIBLE_AT[breakpoint] || VISIBLE_AT.lg)(col);
}

/**
 * Padding for a column given its position inside a `group`.
 *
 * Money columns are variants of one number; spacing them like unrelated columns
 * breaks that reading. Members sit close together and the group as a whole is
 * bracketed by a wider gap, which is also what stops a right-aligned amount
 * header from colliding with the left-aligned label that follows it.
 */
function padClassFor(col, prevCol, nextCol, base) {
  if (!col.group) return base;
  const vertical = base === TABLE_DENSITY.headerCell ? 'py-2' : 'py-1.5';
  const first = !prevCol || prevCol.group !== col.group;
  const last = !nextCol || nextCol.group !== col.group;
  if (first && last) return base;
  if (first) return `pl-6 pr-1.5 ${vertical}`;
  if (last) return `pl-2 pr-6 ${vertical}`;
  return `pl-2 pr-1.5 ${vertical}`;
}

/**
 * Resolve a page's column config into everything both table components need.
 *
 * Every column is sized by its own content and every column takes a share of
 * the slack, proportional to that content. The previous rule promoted a single
 * column to flexible, which did not remove the dead space — it piled all of it
 * into the gap between the name and its first value.
 *
 * `width` is that share as a percentage of the total weight, the actions column
 * included, so the percentages a table hands out add up to 100.
 */
export function resolveColumns(
  columns = [],
  { hasActions = true, rowActionsLayout = ROW_ACTION_LAYOUTS.INLINE_END } = {},
) {
  const sizes = columns.map(inferSize);
  const totalWeight = sizes.reduce((total, size) => total + SIZES[size].weight, 0)
    + (hasActions && rowActionsLayout === ROW_ACTION_LAYOUTS.INLINE_END
      ? SIZES.icons.weight
      : 0);

  return columns.map((col, index) => {
    const size = sizes[index];
    const spec = SIZES[size];
    const textPolicy = textPolicyFor({ ...col, size });
    return {
      ...col,
      size,
      textPolicy,
      track: spec.track,
      width: totalWeight ? `${((spec.weight / totalWeight) * 100).toFixed(2)}%` : 'auto',
      minRem: spec.rem,
      contentClass: TEXT_POLICY_CLASSES[textPolicy],
      alignClass: alignClass(col),
      nowrapClass: textPolicy === 'atomic' ? 'whitespace-nowrap' : '',
      headerPadClass: padClassFor(
        col,
        columns[index - 1],
        columns[index + 1],
        TABLE_DENSITY.headerCell,
      ),
      padClass: padClassFor(col, columns[index - 1], columns[index + 1], TABLE_DENSITY.cell),
      hideTableClass: hideClass(col, 'table'),
      hideGridClass: hideClass(col, 'grid'),
    };
  });
}

/**
 * Which cells a viewport profile shows: desktop shows every column, and the
 * narrower profiles follow each column's `responsive` policy — the same chain
 * BaseResponsiveTable uses to hide the cells.
 */
export function responsivePolicyFor(column, profile) {
  if (profile === 'desktop' || !column.responsive) return 'keep';
  if (column.responsive[profile]) return column.responsive[profile];
  if (profile === 'portrait') return column.responsive.compact || 'keep';
  return 'keep';
}

/**
 * Profiles where a `menu-start` table keeps its fixed layout. Below landscape
 * it switches to auto layout with auto-width data columns, so atomic values
 * keep their content width and the wrapping primary column takes the rest (the
 * grid tables' `minmax(max-content, …)` contract). Auto layout there is safe for
 * the kebab: with unconstrained data columns the slack goes to them, never to
 * the fixed control tracks.
 */
export const FIXED_LAYOUT_PROFILES = Object.freeze(['landscape', 'desktop']);

/**
 * Per-profile widths for the fixed-layout profiles of a `menu-start` table.
 *
 * `width` shares 100% among EVERY data column, which only holds where every
 * column shows. At landscape the hidden cells drop out of the layout but their
 * share did not: the visible columns kept their desktop percentages and the
 * rest of the row became a blank band. Each profile therefore re-shares 100%
 * among the columns it keeps, and a column the profile hides gets 0%. The
 * values feed `--col-w-<profile>` custom properties that a media query picks
 * from, as the grid tables do with their track lists.
 */
export function profileWidthVars(resolved = []) {
  const totals = Object.fromEntries(FIXED_LAYOUT_PROFILES.map((profile) => [
    profile,
    resolved
      .filter((col) => responsivePolicyFor(col, profile) === 'keep')
      .reduce((sum, col) => sum + SIZES[col.size].weight, 0),
  ]));
  return Object.fromEntries(resolved.map((col) => [
    col.key,
    Object.fromEntries(FIXED_LAYOUT_PROFILES.map((profile) => {
      const kept = responsivePolicyFor(col, profile) === 'keep';
      const share = kept && totals[profile]
        ? (SIZES[col.size].weight / totals[profile]) * 100
        : 0;
      return [`--col-w-${profile}`, `${share.toFixed(2)}%`];
    })),
  ]));
}

/**
 * Grid track list at a given breakpoint. Columns hidden at that width are
 * dropped entirely — CSS cannot remove a track, so each breakpoint gets its own
 * template and the component picks between them with a media query.
 */
export function trackListFor(
  resolved,
  {
    breakpoint = 'lg',
    hasHandle = false,
    hasSelect = false,
    hasActions = true,
    rowActionsLayout = ROW_ACTION_LAYOUTS.INLINE_END,
  } = {},
) {
  const tracks = resolved
    .filter((col) => isVisibleAt(col, breakpoint))
    .map((col) => col.track);
  const hasMenuStart = hasActions && rowActionsLayout === ROW_ACTION_LAYOUTS.MENU_START;
  return [
    ...(hasSelect ? [SELECT_TRACK] : []),
    ...(hasMenuStart ? [ROW_ACTION_MENU_TRACK] : []),
    ...(hasHandle ? [HANDLE_TRACK] : []),
    ...tracks,
    ...(hasActions && !hasMenuStart ? [SIZES.icons.track] : []),
  ].join(' ');
}

/**
 * Share of the table's width for the actions column, on the same scale as the
 * data columns so it neither hogs the slack nor gets starved of it. Kept out of
 * `columns` because no page declares it — both components append it themselves.
 */
export function actionsWidthFor(resolved) {
  const total = resolved.reduce((sum, col) => sum + SIZES[col.size].weight, 0)
    + SIZES.icons.weight;
  return `${((SIZES.icons.weight / total) * 100).toFixed(2)}%`;
}

/**
 * Minimum width before the wrapper starts scrolling horizontally: every column
 * at the floor its content needs. Replaces the hardcoded min-w-[600px] /
 * min-w-[1120px], which were guesses. Below this the proportional share would
 * squeeze a column past its content, so the wrapper scrolls instead.
 */
export function minWidthFor(
  resolved,
  {
    breakpoint = 'lg',
    hasHandle = false,
    hasSelect = false,
    hasActions = true,
    rowActionsLayout = ROW_ACTION_LAYOUTS.INLINE_END,
  } = {},
) {
  const columnsRem = resolved
    .filter((col) => isVisibleAt(col, breakpoint))
    .reduce((total, col) => total + col.minRem, 0);
  const extras = (hasHandle ? 1.75 : 0)
    + (hasSelect ? 2.5 : 0)
    + (hasActions
      ? (rowActionsLayout === ROW_ACTION_LAYOUTS.MENU_START
        ? ROW_ACTION_MENU_WIDTH_REM
        : SIZES.icons.rem)
      : 0);
  // No padding term: cell padding lives inside each track, so the floors above
  // already include it. Adding it again inflated the table past its container
  // and forced a horizontal scroll that clipped the last column.
  return `${(columnsRem + extras).toFixed(2)}rem`;
}
