import {
  HANDLE_TRACK,
  ROW_ACTION_MENU_TRACK,
  TABLE_DENSITY,
  actionsWidthFor,
  alignClass,
  hideClass,
  isVisibleAt,
  minWidthFor,
  profileWidthVars,
  resolveColumns,
  responsivePolicyFor,
  textPolicyClass,
  textPolicyFor,
  trackListFor,
} from '~/utils/tableLayout';

describe('tableLayout — size inference', () => {
  it('sizes a column from its format when no size is declared', () => {
    const [, money, date, badge] = resolveColumns([
      { key: 'name' },
      { key: 'total', format: 'money' },
      { key: 'day', format: 'date' },
      { key: 'state', format: 'badge' },
    ]);

    expect(money.size).toBe('money');
    expect(date.size).toBe('date');
    expect(badge.size).toBe('badge');
  });

  it('gives a centre-aligned column the narrowest track', () => {
    const [day] = resolveColumns([
      { key: 'billing_day', align: 'center' },
      { key: 'name' },
    ]);

    // "Día" shows one or two characters; it must not claim a full column.
    expect(day.size).toBe('tiny');
    expect(day.track).toBe('minmax(max-content, 2.75fr)');
  });

  it('honours an explicit size over the inferred one', () => {
    // Tipo/Estado render badges through slots, so `format` cannot reveal them.
    const [name, type] = resolveColumns([
      { key: 'name', size: 'name' },
      { key: 'cost_type_label', size: 'badge' },
    ]);

    expect(name.size).toBe('name');
    expect(type.size).toBe('badge');
  });
});

describe('tableLayout — proportional slack', () => {
  it('leaves no column absorbing the slack on its own', () => {
    // The old rule promoted one column to width:100%, which piled every spare
    // pixel into the gap next to it instead of removing the dead space.
    const resolved = resolveColumns([
      { key: 'concept', size: 'name' },
      { key: 'note' },
      { key: 'total', format: 'money' },
    ]);

    expect(resolved.map((col) => col.width)).not.toContain('100%');
    expect(resolved.every((col) => col.track.includes('fr'))).toBe(true);
  });

  it('splits the whole width across the columns and the actions slot', () => {
    const resolved = resolveColumns([
      { key: 'concept', size: 'name' },
      { key: 'total', format: 'money' },
    ]);
    const declared = resolved.reduce((sum, col) => sum + parseFloat(col.width), 0);

    // name 10 + money 7 + actions 5.25 = 22.25 → the columns claim all but the
    // actions share, which the table appends itself.
    expect(declared).toBeCloseTo((17 / 22.25) * 100, 1);
    expect(parseFloat(actionsWidthFor(resolved))).toBeCloseTo((5.25 / 22.25) * 100, 1);
    expect(declared + parseFloat(actionsWidthFor(resolved))).toBeCloseTo(100, 1);
  });

  it('keeps menu-start outside the proportional data split', () => {
    const resolved = resolveColumns([
      { key: 'concept', size: 'name' },
      { key: 'total', format: 'money' },
    ], { hasActions: true, rowActionsLayout: 'menu-start' });

    const declared = resolved.reduce((sum, col) => sum + parseFloat(col.width), 0);
    expect(declared).toBeCloseTo(100, 1);
  });

  it('hands a wider column a bigger share than a narrow one', () => {
    const [name, day, total] = resolveColumns([
      { key: 'concept', size: 'name' },
      { key: 'billing_day', align: 'center' },
      { key: 'total', format: 'money' },
    ]);

    // Proportional to content: "Día" must not fatten up to an amount's width.
    expect(parseFloat(name.width)).toBeGreaterThan(parseFloat(total.width));
    expect(parseFloat(total.width)).toBeGreaterThan(parseFloat(day.width));
  });

  it('gives every column a content floor so no value is truncated', () => {
    const resolved = resolveColumns([
      { key: 'concept', size: 'name' },
      { key: 'total', format: 'money' },
    ]);

    // max-content as the track minimum: the share only ever adds width on top.
    expect(resolved.every((col) => col.track.startsWith('minmax(max-content,'))).toBe(true);
  });

  it('contains every variable text column with intrinsic-safe wrapping', () => {
    const [name, note] = resolveColumns([
      { key: 'concept', size: 'name' },
      { key: 'note' },
    ]);

    expect(name.contentClass).toContain('[overflow-wrap:anywhere]');
    expect(name.nowrapClass).toBe('');
    expect(note.contentClass).toContain('[overflow-wrap:anywhere]');
    expect(note.nowrapClass).toBe('');
  });

  it('keeps bounded values atomic', () => {
    const [money, date] = resolveColumns([
      { key: 'total', format: 'money' },
      { key: 'created_at', format: 'date' },
    ]);

    expect(money.textPolicy).toBe('atomic');
    expect(date.nowrapClass).toBe('whitespace-nowrap');
  });

  it('honours an explicit truncation policy', () => {
    const column = { key: 'reference', textPolicy: 'truncate' };

    expect(textPolicyFor(column)).toBe('truncate');
    expect(textPolicyClass(column)).toContain('truncate');
  });

  it('returns an empty list for no columns', () => {
    expect(resolveColumns([])).toEqual([]);
  });
});

describe('tableLayout — money grouping', () => {
  const resolved = resolveColumns([
    { key: 'name' },
    { key: 'price', align: 'right', group: 'money' },
    { key: 'monthly_price', align: 'right', group: 'money' },
    { key: 'monthly_cop_cost', format: 'money', group: 'money' },
    { key: 'frequency_label' },
  ]);
  const [, first, middle, last, after] = resolved;

  it('brackets the group with a wider gap and tightens the members', () => {
    expect(first.padClass).toContain('pl-6');
    expect(first.padClass).toContain('pr-1.5');
    expect(middle.padClass).toContain('pl-2');
    expect(middle.padClass).toContain('pr-1.5');
    expect(last.padClass).toContain('pr-6');
  });

  it('applies the same grouping to the header so labels sit over their values', () => {
    expect(last.headerPadClass).toContain('pr-6');
    expect(first.headerPadClass).toContain('pl-6');
  });

  it('keeps the right-aligned group clear of the left-aligned column after it', () => {
    // The gap that stops "EQUIV. COP MENSUAL" colliding with "FRECUENCIA".
    expect(last.alignClass).toBe('text-right');
    expect(after.alignClass).toBe('text-left');
    expect(last.padClass).toContain('pr-6');
  });

  it('leaves a lone grouped column on the default padding', () => {
    const [only] = resolveColumns([
      { key: 'total', format: 'money', group: 'money' },
      { key: 'name' },
    ]);

    expect(only.padClass).toBe(TABLE_DENSITY.cell);
  });

  it('does not group across a different group name', () => {
    const cols = resolveColumns([
      { key: 'name' },
      { key: 'a', group: 'money' },
      { key: 'b', group: 'other' },
    ]);

    expect(cols[1].padClass).toBe(TABLE_DENSITY.cell);
    expect(cols[2].padClass).toBe(TABLE_DENSITY.cell);
  });
});

describe('tableLayout — alignment', () => {
  it('defaults money to the right and everything else to the left', () => {
    expect(alignClass({ format: 'money' })).toBe('text-right');
    expect(alignClass({ key: 'name' })).toBe('text-left');
    expect(alignClass({ align: 'center' })).toBe('text-center');
  });

  it('lets an explicit align override the money default', () => {
    expect(alignClass({ format: 'money', align: 'left' })).toBe('text-left');
  });
});

describe('tableLayout — responsive', () => {
  it('emits table-cell classes for a table and block classes for a grid', () => {
    expect(hideClass({ hideBelow: 'md' }, 'table')).toBe('hidden md:table-cell');
    expect(hideClass({ hideBelow: 'lg' }, 'grid')).toBe('hidden lg:block');
    expect(hideClass({ key: 'name' }, 'table')).toBe('');
  });

  it('reports visibility per breakpoint', () => {
    const always = { key: 'name' };
    const mid = { key: 'price', hideBelow: 'md' };
    const wide = { key: 'method', hideBelow: 'lg' };

    expect(isVisibleAt(always, 'base')).toBe(true);
    expect(isVisibleAt(mid, 'base')).toBe(false);
    expect(isVisibleAt(mid, 'md')).toBe(true);
    expect(isVisibleAt(wide, 'md')).toBe(false);
    expect(isVisibleAt(wide, 'lg')).toBe(true);
  });

  it('drops hidden columns from the narrow track list but keeps them when wide', () => {
    const resolved = resolveColumns([
      { key: 'name' },
      { key: 'method', hideBelow: 'lg' },
      { key: 'total', format: 'money' },
    ]);

    const base = trackListFor(resolved, { breakpoint: 'base' });
    const lg = trackListFor(resolved, { breakpoint: 'lg' });

    // name + total + actions at base; the method track only appears at lg.
    expect(base.split(' ').length).toBeLessThan(lg.split(' ').length);
    expect(lg).toContain('max-content');
  });
});

describe('tableLayout — track list and min width', () => {
  const resolved = resolveColumns([
    { key: 'name' },
    { key: 'total', format: 'money' },
  ]);

  it('prepends the drag handle track only when there is a handle', () => {
    expect(trackListFor(resolved, { hasHandle: true }).startsWith(HANDLE_TRACK)).toBe(true);
    expect(trackListFor(resolved, { hasHandle: false }).startsWith(HANDLE_TRACK)).toBe(false);
  });

  it('appends an actions track only when actions are shown', () => {
    // Two columns: name + total, so 2 tracks bare and 3 with the actions column.
    // Every track carries its own fr weight — that is the proportional split.
    expect(trackListFor(resolved, { hasActions: false })).toBe(
      'minmax(max-content, 5fr) minmax(max-content, 7fr)',
    );
    expect(trackListFor(resolved, { hasActions: true })).toBe(
      'minmax(max-content, 5fr) minmax(max-content, 7fr) minmax(max-content, 5.25fr)',
    );
  });

  it('puts a fixed menu-start track after selection and before data', () => {
    const tracks = trackListFor(resolved, {
      hasSelect: true,
      hasActions: true,
      rowActionsLayout: 'menu-start',
    });

    expect(tracks).toBe(
      `2.5rem ${ROW_ACTION_MENU_TRACK} minmax(max-content, 5fr) minmax(max-content, 7fr)`,
    );
    expect(minWidthFor(resolved, {
      hasSelect: true,
      hasActions: true,
      rowActionsLayout: 'menu-start',
    })).toBe('18.00rem');
  });

  it('derives a min width in rem that grows with the visible columns', () => {
    const narrow = minWidthFor(resolved, { breakpoint: 'base' });
    const wide = minWidthFor(
      resolveColumns([
        { key: 'name' },
        { key: 'total', format: 'money' },
        { key: 'other', format: 'money' },
      ]),
      { breakpoint: 'base' },
    );

    expect(narrow).toMatch(/rem$/);
    expect(parseFloat(wide)).toBeGreaterThan(parseFloat(narrow));
  });

  it('counts the drag handle in the min width', () => {
    const withHandle = minWidthFor(resolved, { hasHandle: true });
    const without = minWidthFor(resolved, { hasHandle: false });

    expect(parseFloat(withHandle)).toBeGreaterThan(parseFloat(without));
  });
});

describe('tableLayout — per-profile widths', () => {
  // From landscape up a menu-start table is fixed-layout: each profile must
  // share 100% among the columns it shows, or the hidden ones leave a blank
  // band behind. Below landscape it is auto-layout and takes no shares.
  const menuStart = resolveColumns([
    {
      key: 'name',
      size: 'name',
      responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
    },
    { key: 'date', format: 'date', responsive: { compact: 'group' } },
    {
      key: 'total',
      format: 'money',
      responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
    },
    { key: 'notes', responsive: { compact: 'group', portrait: 'group', landscape: 'group' } },
  ], { hasActions: true, rowActionsLayout: 'menu-start' });

  it('follows the compact policy at portrait when portrait is undeclared', () => {
    expect(responsivePolicyFor(menuStart[1], 'portrait')).toBe('group');
    expect(responsivePolicyFor(menuStart[1], 'landscape')).toBe('keep');
    expect(responsivePolicyFor(menuStart[3], 'desktop')).toBe('keep');
  });

  it('shares each profile among the columns it keeps', () => {
    const vars = profileWidthVars(menuStart);

    expect(vars.name['--col-w-landscape']).toBe('43.48%');
    expect(vars.date['--col-w-landscape']).toBe('26.09%');
    expect(vars.total['--col-w-landscape']).toBe('30.43%');
  });

  it('gives a column hidden in a profile no share there', () => {
    const vars = profileWidthVars(menuStart);

    expect(vars.notes['--col-w-landscape']).toBe('0.00%');
    expect(vars.notes['--col-w-desktop']).toBe('17.86%');
  });

  it('leaves the auto-layout profiles without a share', () => {
    const vars = profileWidthVars(menuStart);

    expect(vars.name['--col-w-compact']).toBeUndefined();
    expect(vars.name['--col-w-portrait']).toBeUndefined();
  });

  it('matches the proportional desktop width', () => {
    const vars = profileWidthVars(menuStart);

    expect(menuStart.map((col) => vars[col.key]['--col-w-desktop']))
      .toEqual(menuStart.map((col) => col.width));
  });
});
