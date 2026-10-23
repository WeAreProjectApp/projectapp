import { Editor } from '@tiptap/core';
import { editorialExtensions } from '~/utils/editorialExtensions';
import { htmlToSource, sourceToHtml } from '~/utils/editorialFormat';

const formats = [
  { name: 'bold', command: 'setBold', selector: 'strong', expected: 'Paired content' },
  { name: 'italic', command: 'setItalic', selector: 'em', expected: 'Paired content' },
  { name: 'underline', command: 'setUnderline', selector: 'u', expected: 'Paired content' },
  { name: 'strike', command: 'setStrike', selector: 's', expected: 'Paired content' },
  { name: 'color', command: 'setColor', argument: '#123456', selector: 'span', style: 'color', expected: 'rgb(18, 52, 86)' },
  { name: 'highlight', command: 'setHighlight', argument: { color: '#ffeedd' }, selector: 'mark', style: 'backgroundColor', expected: 'rgb(255, 238, 221)' },
];
const pairs = formats.flatMap((left, index) => formats.slice(index + 1).map((right) => [`${left.name}/${right.name}`, left, right]));
const editors = [];
const alternateModes = (editor) => {
  for (let turn = 0; turn < 20; turn++) editor.commands.setContent(sourceToHtml(htmlToSource(editor.getHTML())));
  const host = document.createElement('div'); host.innerHTML = editor.getHTML();
  return host;
};
const observe = (host, format) => format.style ? host.querySelector(format.selector)?.style[format.style] : host.querySelector(format.selector)?.textContent;
afterEach(() => { editors.splice(0).forEach((editor) => editor.destroy()); });

describe('pairwise editorial formatting', () => {
  // Catches either formatting option replacing its paired option during serialization or reparsing.
  it.each(pairs)('preserves the %s combination through twenty transitions', (_name, first, second) => {
    const editor = new Editor({ extensions: editorialExtensions(), content: '<p>Paired content</p>' });
    editors.push(editor);
    editor.commands.selectAll();
    editor.commands[first.command](first.argument);
    editor.commands[second.command](second.argument);
    const edited = editor.state.doc.toJSON();

    const host = alternateModes(editor);

    expect([observe(host, first), observe(host, second)]).toEqual([first.expected, second.expected]);
    expect(editor.state.doc.toJSON()).toEqual(edited);
  });
});
