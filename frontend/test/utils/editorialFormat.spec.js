import { Editor } from '@tiptap/core';
import { editorialExtensions } from '~/utils/editorialExtensions';
import { sourceToHtml, htmlToSource, editorialPlainText } from '~/utils/editorialFormat';

const specimens = [
  ['emphasis', '**Bold** and *italic* with ~~strike~~'],
  ['ordered list', '7. First\n8. Second'],
  ['nested list', '- Parent\n  - Child\n    1. Nested'],
  ['styled paragraph', '<p style="text-align: justify"><span style="color: #ff0000"><strong>Red</strong></span> text</p>'],
  ['highlight', '<p><mark style="background-color: #ffff00">Highlighted</mark> <u>underlined</u></p>'],
  ['table', '| Name | Value |\n| --- | --- |\n| A | **B** |'],
  ['column-aligned table', '| Left | Center | Right |\n| :--- | :---: | ---: |\n| A | B | C |'],
  ['styled table', '<table><tbody><tr><th><p>Header</p></th></tr><tr><td><p style="text-align: right"><span style="color: blue">Cell</span></p></td></tr></tbody></table>'],
  ['multiple paragraphs in a cell', '<table><tbody><tr><td><p>First</p><p>Second</p></td></tr></tbody></table>'],
  ['literal punctuation', 'Literal \\*star\\* and \\_under\\_ and \\| pipe'],
  ['code', '```js\nconst tag = "<script>";\n```'],
  ['reference blocks', '[TOC]\n\n> [!NOTE]\n> Important **text**'],
  ['bilingual text', '# Contrato\n\nHola 👋 {client_name}.\n\n## Agreement\n\nHello **world**.'],
];

function alternateModes(editor, profile = 'document') {
  // The repeated transition is the behavior under test, not a loop over inputs.
  for (let turn = 0; turn < 20; turn++) {
    const serialized = htmlToSource(editor.getHTML(), profile);
    editor.commands.setContent(sourceToHtml(serialized, profile));
  }
}

describe('editorial format round trips', () => {
  // Catches lost nodes, numbering, marks or attributes after a mode switch.
  it.each(specimens)('preserves the semantic document for %s', (_name, source) => {
    const editor = new Editor({ extensions: editorialExtensions(), content: sourceToHtml(source) });
    const expected = editor.state.doc.toJSON();
    alternateModes(editor);
    expect(editor.state.doc.toJSON()).toEqual(expected);
    editor.destroy();
  });

  // Catches converters that agree with themselves while losing source content.
  it('retains independent expected ordered-list values', () => {
    // quality: allow-fragile-selector (HTML tags are the public serialization contract, not incidental UI selectors.)
    const host = document.createElement('div');
    host.innerHTML = sourceToHtml(htmlToSource('<ol start="7"><li><p>First</p></li><li><p>Second</p></li></ol>'));
    expect(host.querySelector('ol').getAttribute('start')).toBe('7');
    expect([...host.querySelectorAll('li')].map((li) => li.textContent)).toEqual(['First', 'Second']);
  });

  // Catches color conversion that preserves wording while dropping the style.
  it('retains an independently specified color', () => {
    // quality: allow-fragile-selector (The span and paragraph presentation are the converter's public output.)
    const host = document.createElement('div');
    host.innerHTML = sourceToHtml(htmlToSource('<p style="text-align: center"><span style="color: #ff0000">Red</span></p>'));
    expect(host.querySelector('p').style.textAlign).toBe('center');
    expect(host.querySelector('span').style.color).toBe('rgb(255, 0, 0)');
  });

  // Catches accidental HTML delivery to a plain-text destination.
  it('extracts readable text for clipboard fallback', () => {
    expect(editorialPlainText('**Hello**\n\n- One\n- Two')).toBe('Hello\n\nOne\nTwo');
  });

  // Catches the Markdown renderer emitting forbidden legacy align attributes or losing column alignment.
  it('retains independently specified Markdown table alignment', () => {
    // quality: allow-fragile-selector (Table header presentation is the declared Markdown conversion contract.)
    const editor = new Editor({ extensions: editorialExtensions(), content: sourceToHtml('| Left | Center | Right |\n| :--- | :---: | ---: |\n| A | B | C |') });

    alternateModes(editor);
    const host = document.createElement('div'); host.innerHTML = editor.getHTML();

    expect([...host.querySelectorAll('th')].map((cell) => cell.style.textAlign)).toEqual(['left', 'center', 'right']);
    expect([...host.querySelectorAll('td')].map((cell) => cell.style.textAlign)).toEqual(['left', 'center', 'right']);
    editor.destroy();
  });
});
