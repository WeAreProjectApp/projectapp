import { hasNote, leadingRowActions } from '~/utils/accountingRowActions';

describe('accountingRowActions', () => {
  it('offers the note only when the record carries real text', () => {
    expect(hasNote({ notes: 'Renovar en octubre' })).toBe(true);
    expect(hasNote({ notes: '   \n' })).toBe(false);
    expect(hasNote({ notes: null })).toBe(false);
    expect(hasNote(null)).toBe(false);
  });

  it('opens every row menu with its detail, then its note', () => {
    expect(leadingRowActions({ notes: 'Renovar' }).map((entry) => entry.label))
      .toEqual(['Detalle e historial', 'Ver nota']);
    expect(leadingRowActions({ notes: '' }).map((entry) => entry.id)).toEqual(['history']);
  });
});
