import { addMonths, nextPeriodEnd, previousDay, sameDay } from '~/utils/periodDates';

describe('sameDay', () => {
  it('treats a month as its first day', () => {
    expect(sameDay('2026-11', '2026-11-01')).toBe(true);
  });

  it('distinguishes different days of the same month', () => {
    expect(sameDay('2026-11-01', '2026-11-02')).toBe(false);
  });
});

describe('addMonths', () => {
  it('advances by whole months keeping the day', () => {
    expect(addMonths('2026-03-15', 1)).toBe('2026-04-15');
    expect(addMonths('2026-03-15', 12)).toBe('2027-03-15');
  });

  it('clamps the day like the backend does — Jan 31 + 1 month is Feb 28', () => {
    // Mirrors content/utils.add_months: overflowing into March would desync
    // the form's proposal from what the server computes.
    expect(addMonths('2026-01-31', 1)).toBe('2026-02-28');
    expect(addMonths('2024-01-31', 1)).toBe('2024-02-29');
    expect(addMonths('2026-08-31', 1)).toBe('2026-09-30');
  });

  it('crosses year boundaries', () => {
    expect(addMonths('2026-11-15', 3)).toBe('2027-02-15');
  });

  it('reads the YYYY-MM shorthand as day 1', () => {
    expect(addMonths('2026-08', 1)).toBe('2026-09-01');
  });

  it('returns empty for unparseable input instead of guessing', () => {
    expect(addMonths('', 1)).toBe('');
    expect(addMonths('mañana', 1)).toBe('');
  });
});

describe('previousDay', () => {
  it('steps back across month and year edges', () => {
    expect(previousDay('2026-03-01')).toBe('2026-02-28');
    expect(previousDay('2026-01-01')).toBe('2025-12-31');
  });
});

describe('nextPeriodEnd', () => {
  it('proposes the inclusive end: start + cadence − 1 day', () => {
    expect(nextPeriodEnd('2026-08-15', 'monthly')).toBe('2026-09-14');
    expect(nextPeriodEnd('2026-08-15', 'annual')).toBe('2027-08-14');
    expect(nextPeriodEnd('2026-08-15', 'quarterly')).toBe('2026-11-14');
  });

  it('proposes nothing for custom or unknown cadences', () => {
    expect(nextPeriodEnd('2026-08-15', 'custom')).toBe('');
    expect(nextPeriodEnd('2026-08-15', '')).toBe('');
  });
});
