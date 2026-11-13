import { historyHunks, historySequence } from '~/utils/historySequence';

const blocks = (values) => values.map((value) => ({ key: value, text: value }));

describe('history sequence', () => {
  it('keeps an insertion between its unchanged neighbours', () => {
    const { operations } = historySequence(blocks(['A', 'C']), blocks(['A', 'B', 'C']));

    expect(operations.map(({ kind, item }) => [kind, item.key])).toEqual([['context', 'A'], ['added', 'B'], ['context', 'C']]);
  });

  it('keeps the old block before its replacement', () => {
    const { operations } = historySequence(blocks(['Antes']), blocks(['Después']));

    expect(operations.map(({ kind }) => kind)).toEqual(['removed', 'added']);
  });

  it('separates distant changes into readable hunks', () => {
    const { operations } = historySequence(blocks(['A', 'B', 'C', 'D', 'E', 'F', 'G']), blocks(['X', 'B', 'C', 'D', 'E', 'F', 'Y']));

    expect(historyHunks(operations)).toHaveLength(2);
  });

  it('retains every changed block when alignment exceeds its budget', () => {
    const before = blocks(Array.from({ length: 600 }, (_, index) => `old ${index}`));
    const after = blocks(Array.from({ length: 600 }, (_, index) => `new ${index}`));
    const result = historySequence(before, after);

    expect(result.simplified).toBe(true);
    expect(result.operations.filter(({ kind }) => kind === 'removed')).toHaveLength(600);
    expect(result.operations.filter(({ kind }) => kind === 'added')).toHaveLength(600);
    expect(result.operations[result.operations.length - 1].item.text).toBe('new 599');
  });

  it('avoids fallback for a small edit in a long document', () => {
    const before = blocks(Array.from({ length: 2000 }, (_, index) => `Paragraph ${index}`));
    const after = [...before];
    after[1000] = { key: 'Changed', text: 'Changed' };

    expect(historySequence(before, after).simplified).toBe(false);
  });
});
