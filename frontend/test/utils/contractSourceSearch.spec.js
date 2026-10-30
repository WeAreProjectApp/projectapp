import { contractSourceParts, normalizeContractSource } from '../../utils/contractSourceSearch';
import cases from '../fixtures/contract-source-search.json';

describe('contract source search', () => {
  it.each(cases)('matches and marks the shared Unicode case $title', ({ title, query, normalized, highlight }) => {
    expect(normalizeContractSource(title)).toBe(normalized);
    const parts = contractSourceParts(title, query);
    expect(parts.filter(part => part.match).map(part => part.text)).toEqual([highlight]);
    expect(parts.map(part => part.text).join('')).toBe(title);
  });
  it('normalizes accents, case and underscore runs for substring matching', () => {
    expect(normalizeContractSource('  Revisión__CONTRATO_Final  ')).toBe('revision contrato final');
  });

  it('marks every match at the original offsets including accents and underscores', () => {
    expect(contractSourceParts('Revisión_Contrato y revisión_contrato', 'VISION CONTRATO')).toEqual([
      { text: 'Re', match: false }, { text: 'visión_Contrato', match: true },
      { text: ' y re', match: false }, { text: 'visión_contrato', match: true },
    ]);
  });

  it('preserves decomposed accents and astral characters around a match', () => {
    expect(contractSourceParts('📄 Revisio\u0301n__Base', 'revision base')).toEqual([
      { text: '📄 ', match: false }, { text: 'Revisio\u0301n__Base', match: true },
    ]);
  });

  it('returns unmodified text for an empty or absent match', () => {
    expect(contractSourceParts('<Contrato>', '')).toEqual([{ text: '<Contrato>', match: false }]);
    expect(contractSourceParts('<Contrato>', 'nada')).toEqual([{ text: '<Contrato>', match: false }]);
  });

  it('merges overlapping original ranges from decomposed syllables', () => {
    const title = '가가가';

    const parts = contractSourceParts(title, 'ᅡᄀ');

    expect(parts).toEqual([{ text: title, match: true }]);
    expect(parts.map(part => part.text).join('')).toBe(title);
  });

  it('preserves surrounding text around merged Unicode matches', () => {
    const title = '📄 가가가 <final>';

    const parts = contractSourceParts(title, 'ᅡᄀ');

    expect(parts).toEqual([
      { text: '📄 ', match: false }, { text: '가가가', match: true }, { text: ' <final>', match: false },
    ]);
    expect(parts.map(part => part.text).join('')).toBe(title);
  });
});
