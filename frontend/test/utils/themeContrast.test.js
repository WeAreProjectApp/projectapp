import { contrastRatio, readableBrand, readableForeground } from '../../utils/themeContrast';

describe('theme text contrast', () => {
  it('measures the WCAG black-to-white reference', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBe(21);
  });

  it('rejects middle gray on white for normal text', () => {
    expect(contrastRatio('#777777', '#ffffff')).toBeCloseTo(4.478, 3);
  });

  it.each(['#e6efef', '#001713', '#2874f3', '#ffee58', '#7b1fa2', '#777777'])(
    'chooses readable button copy on %s', (background) => {
      const foreground = readableForeground(background);

      expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it('keeps the brand readable on a selected light surface', () => {
    const shades = ['#e6efef', '#ccdedd', '#99bdbc', '#669c9a', '#337b79', '#002921'];

    const foreground = readableBrand('#e6efef', shades, ['#ffffff', '#e6efef'], false);

    expect(contrastRatio(foreground, '#e6efef')).toBeGreaterThanOrEqual(4.5);
  });

  it('keeps a dark chosen color readable on the dark surface', () => {
    const shades = ['#e6efef', '#99bdbc', '#337b79', '#002921', '#001713'];

    const foreground = readableBrand('#001713', shades, ['#002921', '#183e24'], true);

    expect(contrastRatio(foreground, '#183e24')).toBeGreaterThanOrEqual(4.5);
  });
});
