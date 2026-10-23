import fixtures from '../../../docs/fixtures/editorial-format.json';
import { editorialPlainText, sourceToHtml } from '~/utils/editorialFormat';

describe('shared editorial fixtures', () => {
  // Catches frontend/backend grammar drift against independently specified content and presentation examples.
  it.each(fixtures.map((fixture) => [fixture.name, fixture]))('renders the shared %s specimen', (_name, fixture) => {
    const html = sourceToHtml(fixture.source, fixture.profile);

    expect(editorialPlainText(fixture.source, fixture.profile)).toBe(fixture.expected_text);
    expect(fixture.expected_fragments.filter((fragment) => html.includes(fragment))).toEqual(fixture.expected_fragments);
  });
});
