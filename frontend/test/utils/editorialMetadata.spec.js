import { buildFormFromJson, formToJson } from '../../components/BusinessProposal/admin/sectionEditorUtils.js';
import { fieldFormat, setFieldFormat, withEditorialFormats } from '../../utils/editorialMetadata.js';

describe('editorialMetadata', () => {
  // Catches a projection replacing the format map rather than preserving a scalar field's saved representation.
  it('copies scalar format metadata onto a projected form without sharing the source map', () => {
    const source = { quote: 'Approved', text_formats: { '/quote': 'markdown_html_v1' } };
    const target = { quote: 'Approved' };

    const projected = withEditorialFormats(source, target);
    setFieldFormat(projected, '/quote', 'whatsapp_v1');

    expect(projected.text_formats).toEqual({ '/quote': 'whatsapp_v1' });
    expect(source.text_formats).toEqual({ '/quote': 'markdown_html_v1' });
    expect(fieldFormat(projected, '/missing')).toBe('plain');
  });

  // Catches text_formats on array members disappearing when a form adapter rebuilds each object.
  it('copies metadata recursively into objects contained in an array', () => {
    const source = {
      steps: [{ title: 'Review', text_formats: { '/title': 'markdown_html_v1' } }],
    };
    const target = { steps: [{ title: 'Review' }] };

    expect(withEditorialFormats(source, target)).toEqual({
      steps: [{ title: 'Review', text_formats: { '/title': 'markdown_html_v1' } }],
    });
  });

  // Catches the scalar proposal section converter losing a persisted rich-text format after JSON → form → JSON.
  it('round-trips scalar section metadata through greeting form conversion', () => {
    const stored = {
      proposalTitle: 'Plan',
      clientName: 'Ana',
      inspirationalQuote: '**Approved**',
      text_formats: { '/inspirationalQuote': 'markdown_html_v1' },
    };

    const form = buildFormFromJson(stored, 'greeting');
    const result = formToJson(form, 'greeting');

    expect(result.text_formats).toEqual({ '/inspirationalQuote': 'markdown_html_v1' });
    expect(result.inspirationalQuote).toBe('**Approved**');
  });

  // Catches nested list entry metadata being dropped by both halves of the conversion contract.
  it('round-trips array entry metadata through conversion strategy form conversion', () => {
    const stored = {
      index: '3', title: 'Strategy', intro: 'Start', resultTitle: 'Result', result: 'Done',
      steps: [{ title: 'Discovery', bullets: ['**Audit**', 'Table'], text_formats: { '/bullets/0': 'markdown_html_v1' } }],
    };

    const result = formToJson(buildFormFromJson(stored, 'conversion_strategy'), 'conversion_strategy');

    expect(result.steps[0].text_formats).toEqual({ '/bullets/0': 'markdown_html_v1' });
    expect(result.steps[0].bullets).toEqual(['**Audit**', 'Table']);
  });
});
