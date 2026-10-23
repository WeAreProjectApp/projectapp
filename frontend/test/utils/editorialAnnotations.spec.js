import { resolveEditorialContent, normalizeEditorialFeatures } from '../../utils/editorialMetadata.js';

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

  expect(result.groups[0].text_formats).toEqual({ '/body': 'markdown_html_v1' });
});
