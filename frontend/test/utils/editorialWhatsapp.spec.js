import { Editor } from '@tiptap/core';
import { editorialExtensions } from '~/utils/editorialExtensions';
import { EditorialFormatError, htmlToSource, sourceToHtml } from '~/utils/editorialFormat';

const editors = [];
const renderTwentyTransitions = (source) => {
  const editor = new Editor({ extensions: editorialExtensions('whatsapp'), content: sourceToHtml(source, 'whatsapp') });
  editors.push(editor);
  for (let turn = 0; turn < 20; turn++) editor.commands.setContent(sourceToHtml(htmlToSource(editor.getHTML(), 'whatsapp'), 'whatsapp'));
  const host = document.createElement('div'); host.innerHTML = editor.getHTML();
  return host;
};
afterEach(() => { editors.splice(0).forEach((editor) => editor.destroy()); });

describe('WhatsApp channel syntax', () => {
  // Catches a Markdown parser misreading channel delimiters or interpreting them inside protected code.
  it.each([
    ['bold', '*Bold*', 'strong', ['Bold']],
    ['italic', '_Italic_', 'em', ['Italic']],
    ['strike', '~Removed~', 's', ['Removed']],
    ['mixed marks', '*Bold _Italic_*', 'strong em', ['Italic']],
    ['literal delimiters inside code', '`*word* _value_ ~value~`', 'code', ['*word* _value_ ~value~']],
    ['fenced code', '```\nconst a = "*word*";\n```', 'pre code', ['const a = "*word*";']],
    ['bullet list', '- First\n- Second', 'li', ['First', 'Second']],
    ['numbered list', '7. First\n8. Second', 'li', ['First', 'Second']],
    ['quote', '> Quoted *text*', 'blockquote', ['Quoted text']],
    ['plain heading punctuation', '# Header', 'p', ['# Header']],
    ['HTML-shaped text', '<b>Literal</b>', 'p', ['<b>Literal</b>']],
    ['callout-shaped text', '> [!NOTE]\n> A note', 'blockquote', ['[!NOTE]A note']],
  ])('preserves %s through twenty transitions', (_name, source, selector, expected) => {
    // quality: allow-fragile-selector (Semantic tags expose the channel syntax result without mocking the real editor.)
    const host = renderTwentyTransitions(source);

    expect([...host.querySelectorAll(selector)].map((node) => node.textContent)).toEqual(expected);
  });

  // Catches URL/email auto-linking that makes otherwise valid channel text fail strict profile validation.
  it('keeps URLs as channel text', () => {
    // quality: allow-fragile-selector (An anchor would be a forbidden transformation of literal channel text.)
    const host = renderTwentyTransitions('https://example.com and hello@example.com');

    expect(host.textContent).toBe('https://example.com and hello@example.com');
    expect(host.querySelectorAll('a').length).toBe(0);
  });

  // Catches a Markdown soft-line break collapsing two distinct WhatsApp lines.
  it('preserves single channel line breaks', () => {
    // quality: allow-fragile-selector (The br elements are the exact persisted channel-line-break semantics.)
    const host = renderTwentyTransitions('First\nSecond');

    expect(host.querySelectorAll('br').length).toBe(1);
    expect([...host.querySelector('p').childNodes].map((node) => node.nodeType === Node.TEXT_NODE ? node.textContent : node.localName)).toEqual(['First', 'br', 'Second']);
  });

  // Catches document-only presentation being silently discarded for a text-only delivery channel.
  it.each([
    ['color', '<p><span style="color: red">Red</span></p>'],
    ['underline', '<p><u>Line</u></p>'],
    ['table', '<table><tr><td>Cell</td></tr></table>'],
  ])('rejects visual %s for the channel', (_name, html) => {
    expect(() => htmlToSource(html, 'whatsapp')).toThrow(EditorialFormatError);
  });
});
