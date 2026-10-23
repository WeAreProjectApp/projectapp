import { sourceToHtml, editorialPlainText } from '~/utils/editorialFormat';

describe('editorial source validation', () => {
  // Catches source-mode imports removing unsafe or unrepresentable content before the user can repair it.
  it.each([
    ['script', '<script>alert(1)</script>', 'unsupported-tag:script'],
    ['image', '![Hidden](https://example.com/image.png)', 'unsupported-tag:img'],
    ['event handler', '<p onclick="alert(1)">Text</p>', 'unsupported-attribute:onclick'],
    ['unsafe Markdown link', '[Open](javascript:alert(1))', 'unsafe-link'],
    ['encoded unsafe link', '<a href="java&#x73;cript:alert(1)">Open</a>', 'unsafe-link'],
    ['CSS URL', '<span style="color: url(https://example.com)">Text</span>', 'unsupported-style:color'],
    ['unknown style', '<p style="position: fixed">Text</p>', 'unsupported-style:position'],
    ['duplicate property', '<span style="color: red; color: blue">Text</span>', 'unsupported-style:color'],
    ['out of range RGB', '<span style="color: rgb(999, 0, 0)">Text</span>', 'unsupported-style:color'],
    ['misplaced color', '<p style="color: red">Text</p>', 'unsupported-style:color'],
    ['misplaced background', '<span style="background-color: yellow">Text</span>', 'unsupported-style:background-color'],
    ['misplaced title', '<p title="Hidden">Text</p>', 'unsupported-title'],
    ['misplaced callout', '<p data-callout="NOTE">Text</p>', 'unsupported-callout'],
    ['misplaced start', '<ul start="7"><li>Text</li></ul>', 'unsupported-number'],
    ['comment', '<p>Text</p><!-- instruction -->', 'unsupported-comment'],
    ['non-marker TOC content', '<div data-editor-block="toc">Lost text</div>', 'unsupported-toc-content'],
  ])('rejects %s without sanitizing the draft', (_name, source, reason) => {
    expect(() => sourceToHtml(source)).toThrow(reason);
  });

  // Catches sanitization allowing supported attributes to become a vector for executing CSS.
  it('reduces pasted styles to the permitted presentation vocabulary', () => {
    // quality: allow-fragile-selector (The sanitization contract is the allowed HTML tags and their presentation attributes.)
    const host = document.createElement('div');

    host.innerHTML = sourceToHtml('<p onclick="alert(1)" style="position: fixed; text-align: center"><span style="color: red; background: url(https://example.com)">Text</span></p>', 'document', { strict: false });

    expect(host.querySelector('p').getAttribute('style')).toBe('text-align: center');
    expect(host.querySelector('p').getAttribute('onclick')).toBe(null);
    expect(host.querySelector('span').getAttribute('style')).toBe('color: red');
    expect(host.textContent).toBe('Text');
  });

  // Catches table clipboard exports concatenating separate cells into an unreadable word.
  it('separates plain-text table cells', () => {
    expect(editorialPlainText('| Name | Value |\n| --- | --- |\n| First | Second |')).toBe('Name\tValue\nFirst\tSecond');
  });

  // Catches copying a nested list merging its parent label with its first child.
  it('separates nested list labels in plain text', () => {
    expect(editorialPlainText('- Parent\n  - Child\n    1. Nested')).toBe('Parent\nChild\nNested');
  });

  // Catches separate paragraphs in a table cell becoming a single word in the clipboard fallback.
  it('separates paragraphs inside a plain-text table cell', () => {
    expect(editorialPlainText('<table><tr><td><p>First</p><p>Second</p></td></tr></table>')).toBe('First\nSecond');
  });
});
