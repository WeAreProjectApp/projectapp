import { Editor } from '@tiptap/core';
import { editorialExtensions } from '~/utils/editorialExtensions';
import { htmlToSource, sourceToHtml } from '~/utils/editorialFormat';

const editors = [];
const createEditor = (content) => {
  const editor = new Editor({ extensions: editorialExtensions(), content });
  editors.push(editor);
  return editor;
};
const alternateModes = (editor) => {
  for (let turn = 0; turn < 20; turn++) editor.commands.setContent(sourceToHtml(htmlToSource(editor.getHTML())));
  const host = document.createElement('div'); host.innerHTML = editor.getHTML();
  return host;
};
afterEach(() => { editors.splice(0).forEach((editor) => editor.destroy()); });

describe('visual source equivalence', () => {
  // Catches a serializer that makes literal punctuation or edge whitespace into competing Markdown syntax.
  it.each([
    ['leading heading punctuation', '<p># Invoice</p>', 'p', ['# Invoice']],
    ['leading bullet punctuation', '<p>- Invoice</p>', 'p', ['- Invoice']],
    ['leading numbered punctuation', '<p>1. Invoice</p>', 'p', ['1. Invoice']],
    ['entity-shaped text', '<p>&amp;copy; &amp;lt;value&amp;gt;</p>', 'p', ['&copy; &lt;value&gt;']],
    ['edge whitespace in bold', '<p><strong> padded </strong>end</p>', 'strong', [' padded ']],
    ['adjacent marks', '<p><strong>A</strong><em>B</em><strong>C</strong></p>', 'strong,em', ['A', 'B', 'C']],
    ['empty paragraph', '<p>First</p><p></p><p>Last</p>', 'p', ['First', '', 'Last']],
    ['multiple paragraphs in list', '<ul><li><p>First</p><p>Second</p></li></ul>', 'li p', ['First', 'Second']],
    ['inline code with a pipe in a table', '<table><tr><th><p>Header</p></th></tr><tr><td><p><code>A | B</code></p></td></tr></table>', 'code', ['A | B']],
    ['nested mixed lists', '<ol start="7"><li><p>Parent</p><ul><li><p>Bullet</p><ol start="3"><li><p>Child</p></li></ol></li></ul></li></ol>', 'li p', ['Parent', 'Bullet', 'Child']],
    ['paragraph containing only spaces', '<p><code>  code  </code></p>', 'code', ['  code  ']],
  ])('preserves %s through twenty mode changes', (_name, html, selector, expected) => {
    // quality: allow-fragile-selector (These semantic HTML tags define the formatting conversion contract.)
    const editor = createEditor(html);

    const host = alternateModes(editor);

    expect([...host.querySelectorAll(selector)].map((node) => node.textContent)).toEqual(expected);
  });

  // Catches start=0 being mistaken for a missing ordered-list offset.
  it('preserves zero as the starting list number', () => {
    // quality: allow-fragile-selector (Ordered-list HTML is the observable source-format contract.)
    const editor = createEditor('<ol start="0"><li><p>Zero</p></li><li><p>One</p></li></ol>');

    const host = alternateModes(editor);

    expect(host.querySelector('ol').getAttribute('start')).toBe('0');
    expect([...host.querySelectorAll('li')].map((node) => node.textContent)).toEqual(['Zero', 'One']);
  });

  // Catches Markdown conversion silently dropping link metadata that has no Markdown equivalent.
  it('preserves link attributes after source serialization', () => {
    // quality: allow-fragile-selector (The anchor attributes are the document's persisted link semantics.)
    const editor = createEditor('<p><a href="https://example.com/path" title="Details" target="_blank" rel="noopener noreferrer">Read</a></p>');

    const host = alternateModes(editor);

    expect(Object.fromEntries([...host.querySelector('a').attributes].map((attribute) => [attribute.name, attribute.value]))).toEqual({
      href: 'https://example.com/path', target: '_blank', rel: 'noopener noreferrer', title: 'Details',
    });
  });

  // Catches hexadecimal toolbar colors changing schema attributes on the next mode switch.
  it('normalizes a color applied from the toolbar', () => {
    // quality: allow-fragile-selector (The colored span is the formatter's public output, not an incidental wrapper.)
    const editor = createEditor('<p>Red</p>');
    editor.commands.selectAll(); editor.commands.setColor('#ff0000');
    const edited = editor.state.doc.toJSON();

    const host = alternateModes(editor);

    expect(host.querySelector('span').style.color).toBe('rgb(255, 0, 0)');
    expect(editor.state.doc.toJSON()).toEqual(edited);
  });

  // Catches the standard highlight extension emitting unsupported data attributes or color:inherit.
  it('preserves a highlight applied from the toolbar', () => {
    // quality: allow-fragile-selector (The mark element is the defined highlight output in the versioned grammar.)
    const editor = createEditor('<p>Yellow</p>');
    editor.commands.selectAll(); editor.commands.setHighlight({ color: '#ffff00' });
    const edited = editor.state.doc.toJSON();

    const host = alternateModes(editor);

    expect(host.querySelector('mark').style.backgroundColor).toBe('rgb(255, 255, 0)');
    expect([...host.querySelector('mark').attributes].map((attribute) => attribute.name)).toEqual(['style']);
    expect(editor.state.doc.toJSON()).toEqual(edited);
  });

  // Catches alignment being represented by two independent table attributes that disagree after an edit.
  it('preserves justified table cells', () => {
    // quality: allow-fragile-selector (Cell elements and alignment are the table document contract.)
    const editor = createEditor('<table><tr><th style="text-align: right"><p>Header</p></th></tr><tr><td style="text-align: justify"><p>Cell</p></td></tr></table>');

    const host = alternateModes(editor);

    expect(host.querySelector('th').style.textAlign).toBe('right');
    expect(host.querySelector('td').style.textAlign).toBe('justify');
    expect(host.querySelector('td').textContent).toBe('Cell');
  });

  // Catches combinations that preserve wording but flatten one of the independently applied marks.
  it('preserves combined colored highlighted underlined bold text', () => {
    // quality: allow-fragile-selector (Semantic formatting tags are the observable result this converter must preserve.)
    const editor = createEditor('<p>Combined</p>');
    editor.commands.selectAll();
    editor.chain().setColor('#123456').setHighlight({ color: '#ffeedd' }).setUnderline().setBold().run();

    const host = alternateModes(editor);

    expect(host.querySelector('span').style.color).toBe('rgb(18, 52, 86)');
    expect(host.querySelector('mark').style.backgroundColor).toBe('rgb(255, 238, 221)');
    expect(host.querySelector('strong u, u strong').textContent).toBe('Combined');
  });
});
