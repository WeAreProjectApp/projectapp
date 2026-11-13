import { documentFieldGroups } from '~/utils/documentHistoryFields';

const t = (key, values = {}) => `${key}${values.number || ''}`;
const options = { t, labels: { title: 'Título', folder: 'Carpeta' } };

describe('document history fields', () => {
  it('groups a folder change under organization', () => {
    const groups = documentFieldGroups({ folder: { id: 1, label: 'Original' } }, { folder: { id: 2, label: 'Nueva' } }, options);

    expect(groups[0].key).toBe('organization');
    expect(groups[0].values[0].old.value.label).toBe('Original');
    expect(groups[0].values[0].next.value.label).toBe('Nueva');
  });

  it('omits unchanged metadata from a comparison', () => {
    const common = { title: 'Contrato', metadata: { source: 'historical' } };

    expect(documentFieldGroups(common, { ...common, content_markdown: 'Cuerpo' }, options)).toEqual([]);
  });

  it('associates format declarations with the affected note', () => {
    const groups = documentFieldGroups({ client_custom_notes: '**Nota**', text_formats: { '/client_custom_notes': 'plain' } }, { client_custom_notes: '**Nota**', text_formats: { '/client_custom_notes': 'markdown_html_v1' } }, options);

    expect(groups[0].key).toBe('notes');
    expect(groups[0].values).toHaveLength(1);
    expect(groups[0].values[0].formatOnly).toBe(true);
  });

  it('honours a nested note format declaration', () => {
    const after = { document_notes: { 7: { title: 'Revisión', content: '*literal*', text_formats: { '/content': 'plain' } } } };

    const groups = documentFieldGroups({}, after, options);

    expect(groups[0].values.find((field) => field.key.endsWith('.content')).next.format).toBe('plain');
  });

  it('hides internal file storage names from the reading value', () => {
    const groups = documentFieldGroups({ generated_file: 'old/private.pdf' }, { generated_file: 'new/private.pdf' }, options);

    expect(groups[0].key).toBe('technical');
    expect(groups[0].values[0].next.value).toBe('documentHistory.storedFile');
  });

  it('keeps historical metadata absent from top-level fields', () => {
    const groups = documentFieldGroups({}, { title: 'Contrato', content_json: { meta: { title: 'Duplicado', subtitle: 'Detalle histórico' }, blocks: [] } }, { ...options, full: true });

    expect(groups[0].values.map((field) => field.value)).toEqual(['Contrato', 'Detalle histórico']);
  });
});
