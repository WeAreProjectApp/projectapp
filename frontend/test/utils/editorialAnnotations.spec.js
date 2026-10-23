import { resolveEditorialContent, normalizeEditorialFeatures, setFieldFormat, withoutEditorialPrefix } from '../../utils/editorialMetadata.js';

// Root MCP maps and local UI maps must select the same rendering profile.
it('resolves nested pointer metadata without mutating the stored JSON', () => {
  const source = { groups: [{ bullets: ['**A**', 'B'] }] };

  const result = resolveEditorialContent(source, { '/content_json/groups/0/bullets/0': 'markdown_html_v1' }, '/content_json');

  expect(result.groups[0].text_formats).toEqual({ '/bullets/0': 'markdown_html_v1' });
  expect(source.groups[0]).toEqual({ bullets: ['**A**', 'B'] });
});

// Removing an empty feature must not assign its successor's format to another item.
it('remaps annotations after empty email features are removed', () => {
  const payload = { email_features: ['', '**A**', 'B'], text_formats: { '/email_features/1': 'markdown_html_v1', '/email_features/2': 'plain', '/email_intro': 'plain' } };

  normalizeEditorialFeatures(payload);

  expect(payload.email_features).toEqual(['**A**', 'B']);
  expect(payload.text_formats).toEqual({ '/email_features/0': 'markdown_html_v1', '/email_features/1': 'plain', '/email_intro': 'plain' });
});

// The local JSON map can also target a descendant array element.
it('resolves local descendant pointer metadata for rendering', () => {
  const source = { groups: [{ body: '**A**' }], text_formats: { '/groups/0/body': 'markdown_html_v1' } };

  const result = resolveEditorialContent(source);

  expect(result).toEqual({ groups: [{ body: '**A**', text_formats: { '/body': 'markdown_html_v1' } }] });
  expect(source).toEqual({ groups: [{ body: '**A**' }], text_formats: { '/groups/0/body': 'markdown_html_v1' } });
});

// Editing a canonical local annotation must not leave an older MCP alias behind.
it.each(['plain', 'markdown'])('keeps local edits free of competing %s aliases', (format) => {
  const source = {
    title: 'Resumen',
    groups: [{ body: 'Texto inicial', text_formats: { '/body': format } }],
    text_formats: { '/groups/0/body': format, '/title': 'plain' },
  };
  const formats = { '/content_json/groups/0/body': format, '/email_intro': 'plain' };

  const result = resolveEditorialContent(source, formats, '/content_json');
  result.groups[0].body = '**Texto editado**';
  setFieldFormat(result.groups[0], '/body', 'markdown_html_v1');

  expect(result).toEqual({
    title: 'Resumen',
    groups: [{ body: '**Texto editado**', text_formats: { '/body': 'markdown_html_v1' } }],
    text_formats: { '/title': 'plain' },
  });
  expect(source).toEqual({
    title: 'Resumen',
    groups: [{ body: 'Texto inicial', text_formats: { '/body': format } }],
    text_formats: { '/groups/0/body': format, '/title': 'plain' },
  });
  expect(formats).toEqual({ '/content_json/groups/0/body': format, '/email_intro': 'plain' });
});

// Direct fields already belong to the right owner and must keep their declarations.
it('preserves direct field declarations', () => {
  const source = { title: 'Resumen', body: '**Texto**', text_formats: { '/title': 'plain', '/body': 'markdown' } };

  const result = resolveEditorialContent(source);

  expect(result).toEqual({ title: 'Resumen', body: '**Texto**', text_formats: { '/title': 'plain', '/body': 'markdown' } });
});

// Arrays of strings cannot own persisted metadata; their parent object must keep it.
it('preserves primitive array declarations on the parent object', () => {
  const source = { bullets: ['Primero', '**Segundo**'], text_formats: { '/bullets/1': 'markdown' } };

  const result = resolveEditorialContent(source);

  expect(result).toEqual({ bullets: ['Primero', '**Segundo**'], text_formats: { '/bullets/1': 'markdown' } });
});

// A nested primitive array's closest object owner must receive the relative pointer.
it('moves primitive array declarations to the nearest nested object', () => {
  const source = { groups: [{ bullets: ['**Primero**', 'Segundo'] }], text_formats: { '/groups/0/bullets/0': 'markdown' } };

  const result = resolveEditorialContent(source);

  expect(result).toEqual({ groups: [{ bullets: ['**Primero**', 'Segundo'], text_formats: { '/bullets/0': 'markdown' } }] });
  expect(source).toEqual({ groups: [{ bullets: ['**Primero**', 'Segundo'] }], text_formats: { '/groups/0/bullets/0': 'markdown' } });
});

// Escaped JSON Pointer tokens must still identify the same textual field after moving.
it('preserves escaped pointer tokens on the canonical owner', () => {
  const source = { 'intro/body': { 'text~value': '**Alcance**' }, text_formats: { '/intro~1body/text~0value': 'markdown' } };

  const result = resolveEditorialContent(source);

  expect(result).toEqual({ 'intro/body': { 'text~value': '**Alcance**', text_formats: { '/text~0value': 'markdown' } } });
  expect(source).toEqual({ 'intro/body': { 'text~value': '**Alcance**' }, text_formats: { '/intro~1body/text~0value': 'markdown' } });
});

// Invalid targets must remain present so normalization cannot hide a later server error.
it('preserves unresolved pointer declarations', () => {
  const source = { groups: [{ body: 'Texto' }], text_formats: { '/groups/8/body': 'markdown' } };

  const result = resolveEditorialContent(source);

  expect(result).toEqual({ groups: [{ body: 'Texto' }], text_formats: { '/groups/8/body': 'markdown' } });
});

// Reaching a string before the final token does not make the whole pointer valid.
it('preserves a pointer that continues past a textual leaf', () => {
  const source = { body: 'Texto', text_formats: { '/body/missing': 'markdown' } };

  const result = resolveEditorialContent(source);

  expect(result).toEqual({ body: 'Texto', text_formats: { '/body/missing': 'markdown' } });
});

// Existing incompatible declarations must reach backend validation without being overwritten.
it('preserves conflicting local declarations', () => {
  const source = { group: { body: '**Texto**', text_formats: { '/body': 'plain' } }, text_formats: { '/group/body': 'markdown' } };

  const result = resolveEditorialContent(source);

  expect(result).toEqual({ group: { body: '**Texto**', text_formats: { '/body': 'plain' } }, text_formats: { '/group/body': 'markdown' } });
});

// Removing the outer model map must not silently resolve an incompatible nested declaration.
it('retains an external conflicting alias inside the cloned JSON', () => {
  const source = { group: { body: '**Texto**', text_formats: { '/body': 'plain' } } };

  const result = resolveEditorialContent(source, { '/content_json/group/body': 'markdown' }, '/content_json');

  expect(result).toEqual({ group: { body: '**Texto**', text_formats: { '/body': 'plain' } }, text_formats: { '/group/body': 'markdown' } });
  expect(source).toEqual({ group: { body: '**Texto**', text_formats: { '/body': 'plain' } } });
});

// Removing one JSON root must preserve other roots even when their names share a prefix.
it('filters only the selected JSON pointer root', () => {
  const formats = {
    '/content_json': 'plain',
    '/content_json/groups/0/body': 'markdown',
    '/content_json_en/body': 'markdown',
    '/content_json_extra/body': 'plain',
    '/email_intro': 'markdown_html_v1',
  };

  const result = withoutEditorialPrefix(formats, '/content_json');

  expect(result).toEqual({ '/content_json_en/body': 'markdown', '/content_json_extra/body': 'plain', '/email_intro': 'markdown_html_v1' });
  expect(formats).toEqual({ '/content_json': 'plain', '/content_json/groups/0/body': 'markdown', '/content_json_en/body': 'markdown', '/content_json_extra/body': 'plain', '/email_intro': 'markdown_html_v1' });
});

// Reopening already canonical JSON must not add another alias or relocate metadata again.
it('keeps canonical annotations stable when reopened', () => {
  const source = { groups: [{ body: '**Texto**' }], text_formats: { '/groups/0/body': 'markdown' } };

  const result = resolveEditorialContent(resolveEditorialContent(source));

  expect(result).toEqual({ groups: [{ body: '**Texto**', text_formats: { '/body': 'markdown' } }] });
});
