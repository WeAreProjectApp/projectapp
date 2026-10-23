import DOMPurify from 'dompurify';
import { Marked } from 'marked';

/** The versioned wire format is Markdown + this finite HTML vocabulary. */
export const EDITORIAL_FORMAT = 'markdown_html_v1';
export const EDITORIAL_TAGS = ['p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'em', 'i', 'u', 's', 'del', 'strike', 'span', 'mark', 'a', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'hr', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'div'];
const ATTRS = ['href', 'title', 'target', 'rel', 'start', 'colspan', 'rowspan', 'style', 'data-callout', 'data-editor-block', 'class'];
const ALIGNMENTS = ['left', 'center', 'right', 'justify'];
const NAMED_COLORS = { black: [0, 0, 0], white: [255, 255, 255], red: [255, 0, 0], green: [0, 128, 0], blue: [0, 0, 255], yellow: [255, 255, 0], orange: [255, 165, 0], purple: [128, 0, 128], gray: [128, 128, 128], grey: [128, 128, 128] };
const STYLE_TAGS = { color: ['span'], 'background-color': ['mark'], 'text-align': ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td', 'th'] };

export function normalizeEditorialColor(input) {
  const value = String(input || '').trim().toLowerCase();
  if (value === 'transparent') return value;
  let channels = Object.prototype.hasOwnProperty.call(NAMED_COLORS, value) ? NAMED_COLORS[value] : null;
  if (/^#[\da-f]{3}(?:[\da-f]{3})?$/.test(value)) {
    const hex = value.length === 4 ? value.slice(1).split('').map((digit) => digit + digit).join('') : value.slice(1);
    channels = [0, 2, 4].map((index) => parseInt(hex.slice(index, index + 2), 16));
  }
  const rgb = /^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/.exec(value);
  if (rgb) channels = rgb.slice(1).map(Number);
  return channels?.every((channel) => channel <= 255) ? `rgb(${channels.join(', ')})` : null;
}
const parser = new Marked({ gfm: true, breaks: false, renderer: {
  tablecell(cell) {
    const tag = cell.header ? 'th' : 'td';
    const style = cell.align ? ` style="text-align: ${cell.align}"` : '';
    return `<${tag}${style}>${this.parser.parseInline(cell.tokens)}</${tag}>\n`;
  },
}, extensions: [{
  name: 'editorialToc', level: 'block',
  start: (source) => source.indexOf('[TOC]'),
  tokenizer(source) {
    const match = /^\[TOC\][ \t]*(?:\n|$)/.exec(source);
    return match ? { type: 'editorialToc', raw: match[0] } : undefined;
  },
  renderer: () => '<div data-editor-block="toc">[TOC]</div>\n',
}] });

export class EditorialFormatError extends Error {
  constructor(reason) { super(reason); this.name = 'EditorialFormatError'; }
}

export const escapeHtml = (text) => String(text ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const fragment = (html) => {
  const template = document.createElement('template');
  template.innerHTML = html;
  return template.content;
};
const safeHref = (href) => {
  const compact = href.replace(/[\s\u0000-\u001f\u007f]/g, '');
  return !/^[a-z][a-z\d+.-]*:/i.test(compact) || /^(https?:|mailto:|tel:)/i.test(compact);
};

/** Validate BEFORE sanitizing: a mode change must never silently remove data. */
export function validateEditorialHtml(html, profile = 'document') {
  const root = fragment(html);
  const comments = document.createTreeWalker(root, NodeFilter.SHOW_COMMENT);
  if (comments.nextNode()) throw new EditorialFormatError('unsupported-comment');
  for (const element of root.querySelectorAll('*')) {
    const tag = element.localName;
    if (!EDITORIAL_TAGS.includes(tag)) throw new EditorialFormatError(`unsupported-tag:${tag}`);
    for (const attribute of element.attributes) {
      const { name, value } = attribute;
      if (!ATTRS.includes(name)) throw new EditorialFormatError(`unsupported-attribute:${name}`);
      if (name === 'href' && (tag !== 'a' || !safeHref(value))) throw new EditorialFormatError('unsafe-link');
      if (name === 'title' && tag !== 'a') throw new EditorialFormatError('unsupported-title');
      if (name === 'target' && (tag !== 'a' || !['_blank', '_self'].includes(value))) throw new EditorialFormatError('unsupported-target');
      if (name === 'rel' && (tag !== 'a' || !value.split(/\s+/).every((token) => ['noopener', 'noreferrer', 'nofollow', ''].includes(token)))) throw new EditorialFormatError('unsupported-rel');
      if (name === 'class' && !(tag === 'code' && /^language-[\w-]+$/.test(value))) throw new EditorialFormatError('unsupported-class');
      if (name === 'data-editor-block' && !(tag === 'div' && value === 'toc')) throw new EditorialFormatError('unsupported-block');
      if (name === 'data-callout' && (tag !== 'blockquote' || !/^(NOTE|TIP|IMPORTANT|WARNING|CAUTION)$/.test(value))) throw new EditorialFormatError('unsupported-callout');
      if (name === 'start' && (tag !== 'ol' || !/^\d{1,4}$/.test(value))) throw new EditorialFormatError('unsupported-number');
      if (['colspan', 'rowspan'].includes(name) && (!['td', 'th'].includes(tag) || !/^[1-9]\d{0,3}$/.test(value))) throw new EditorialFormatError('unsupported-number');
      if (name === 'style') {
        const declarations = value.split(';').filter((part) => part.trim());
        const used = new Set();
        for (const declaration of declarations) {
          const colon = declaration.indexOf(':');
          const key = declaration.slice(0, colon).trim().toLowerCase();
          const val = declaration.slice(colon + 1).trim();
          const valid = ['color', 'background-color'].includes(key) ? normalizeEditorialColor(val) !== null
            : key === 'text-align' && ALIGNMENTS.includes(val);
          if (colon < 1 || !valid || !STYLE_TAGS[key]?.includes(tag) || used.has(key)) throw new EditorialFormatError(`unsupported-style:${key}`);
          used.add(key);
        }
      }
    }
    if (profile === 'whatsapp' && !['p', 'br', 'strong', 'b', 'em', 'i', 's', 'del', 'strike', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code'].includes(tag)) {
      throw new EditorialFormatError(`unsupported-whatsapp:${tag}`);
    }
    if (profile === 'whatsapp' && [...element.attributes].some((attribute) => attribute.name !== 'start')) throw new EditorialFormatError('unsupported-whatsapp:attribute');
    if (tag === 'div' && element.dataset.editorBlock !== 'toc') throw new EditorialFormatError('unsupported-block');
    if (tag === 'div' && (element.children.length || element.textContent !== '[TOC]')) throw new EditorialFormatError('unsupported-toc-content');
    if (tag === 'a' && !element.getAttribute('href')) throw new EditorialFormatError('unsupported-link');
  }
  return root;
}

// WhatsApp has its own source syntax. Disabling Markdown-only tokenizers keeps
// literal headings, URLs, HTML and Markdown delimiters from changing meaning.
const whatsappParser = new Marked({
  gfm: true, breaks: true,
  renderer: { code: ({ text }) => `<pre><code>${escapeHtml(text)}</code></pre>\n` },
  tokenizer: {
    heading() {}, hr() {}, lheading() {}, table() {}, html() {}, tag() {},
    link() {}, reflink() {}, autolink() {}, url() {}, def() {}, code() {}, del() {}, escape() {},
    emStrong(source) {
      const marker = source[0];
      if (!['*', '_', '~'].includes(marker) || source[1] === marker || /\s/.test(source[1] || '')) return;
      const closing = source.indexOf(marker, 1);
      if (closing < 1 || source[closing + 1] === marker || /\s/.test(source[closing - 1]) || source.slice(1, closing).includes('\n')) return;
      const text = source.slice(1, closing);
      return { type: { '*': 'strong', '_': 'em', '~': 'del' }[marker], raw: source.slice(0, closing + 1), text, tokens: this.lexer.inlineTokens(text) };
    },
    fences(source) {
      const match = /^```\n([\s\S]*?)\n```(?:\n|$)/.exec(source);
      return match ? { type: 'code', raw: match[0], text: match[1] } : undefined;
    },
  },
});

export function sourceToHtml(source = '', profile = 'document', { strict = true, inputHtml = false } = {}) {
  let html = inputHtml ? source : (profile === 'whatsapp' ? whatsappParser : parser).parse(source);
  const root = fragment(html);
  for (const quote of profile === 'whatsapp' ? [] : root.querySelectorAll('blockquote')) {
    const first = quote.firstElementChild;
    const marker = first?.textContent?.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](?:\s|$)/);
    if (marker) {
      quote.setAttribute('data-callout', marker[1]);
      first.innerHTML = first.innerHTML.replace(/^\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/, '');
      if (!first.textContent && !first.children.length) first.remove();
    }
  }
  const container = document.createElement('div');
  container.append(root);
  html = container.innerHTML;
  if (strict) validateEditorialHtml(html, profile);
  const tags = profile === 'whatsapp' ? ['p', 'br', 'strong', 'b', 'em', 'i', 's', 'del', 'strike', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code'] : EDITORIAL_TAGS;
  const safe = DOMPurify.sanitize(html, { ALLOWED_TAGS: tags, ALLOWED_ATTR: profile === 'whatsapp' ? ['start'] : ATTRS, ALLOW_DATA_ATTR: false });
  // Sanitize CSS separately: DOMPurify deliberately does not validate CSS values.
  if (!strict) {
    const sanitized = fragment(safe);
    for (const el of sanitized.querySelectorAll('[style]')) {
      const keep = [];
      for (const key of ['color', 'background-color', 'text-align']) {
        const value = el.style.getPropertyValue(key).trim();
        if (STYLE_TAGS[key]?.includes(el.localName) && (key === 'text-align' ? ALIGNMENTS.includes(value) : normalizeEditorialColor(value))) keep.push(`${key}: ${value}`);
      }
      if (keep.length) el.setAttribute('style', keep.join('; ')); else el.removeAttribute('style');
    }
    const wrapper = document.createElement('div'); wrapper.append(sanitized);
    return wrapper.innerHTML;
  }
  return safe;
}

const escapeMarkdown = (text) => text.replace(/([!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~])/g, '\\$1');
const childNodes = (node) => [...node.childNodes];
const needsHtml = (node) => node.nodeType === 1 && (node.matches('[style],u,mark') || node.querySelector('[style],u,mark'));

// A Markdown representation is used only when it renders the same semantic
// tree. This is deliberately independent of the editor schema: parsing both
// sides through a schema could hide something that schema already discarded.
function semanticHtml(html) {
  const root = fragment(html);
  for (const element of [...root.querySelectorAll('b,i,del,strike')]) {
    const replacement = document.createElement({ b: 'strong', i: 'em', del: 's', strike: 's' }[element.localName]);
    for (const attribute of element.attributes) replacement.setAttribute(attribute.name, attribute.value);
    replacement.append(...element.childNodes);
    element.replaceWith(replacement);
  }
  for (const group of root.querySelectorAll('thead,tbody,tfoot')) group.replaceWith(...group.childNodes);
  for (const container of root.querySelectorAll('li,td,th')) {
    const paragraphs = [...container.children].filter((child) => child.localName === 'p');
    if (paragraphs.length === 1 && !paragraphs[0].attributes.length) paragraphs[0].replaceWith(...paragraphs[0].childNodes);
  }
  for (const element of root.querySelectorAll('*')) {
    for (const key of ['color', 'background-color']) {
      const normalized = normalizeEditorialColor(element.style.getPropertyValue(key));
      if (normalized) element.style.setProperty(key, normalized);
    }
    for (const name of ['start', 'colspan', 'rowspan']) if (element.getAttribute(name) === '1') element.removeAttribute(name);
    if (element.hasAttribute('style')) {
      const styles = Array.from(element.style).sort().map((name) => `${name}: ${element.style.getPropertyValue(name)}`).join('; ');
      if (styles) element.setAttribute('style', styles); else element.removeAttribute('style');
    }
    const attributes = [...element.attributes].map(({ name, value }) => [name, value]).sort(([left], [right]) => left.localeCompare(right));
    for (const { name } of [...element.attributes]) element.removeAttribute(name);
    for (const [name, value] of attributes) element.setAttribute(name, value);
  }
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode);
  for (const node of textNodes) {
    if (node.parentElement?.closest('pre,code')) continue;
    const parent = node.parentElement;
    const blockWhitespace = !parent || parent.matches('ul,ol,table,tr,blockquote') || [...parent.children].some((child) => child.matches('p,ul,ol,blockquote,table,h1,h2,h3,h4,h5,h6,pre'));
    if (!node.textContent.trim() && blockWhitespace) node.remove();
    else node.textContent = node.textContent.replace(/[\t\r\n ]+/g, ' ');
  }
  const wrapper = document.createElement('div'); wrapper.append(root); wrapper.normalize();
  return wrapper.innerHTML;
}

function serializeNode(node, profile) {
  if (node.nodeType === 3) return profile === 'whatsapp' ? node.textContent : escapeMarkdown(node.textContent);
  if (node.nodeType !== 1) return '';
  const tag = node.localName;
  const children = () => childNodes(node).map((child) => serializeNode(child, profile)).join('');
  if (profile !== 'whatsapp' && needsHtml(node) && ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'blockquote', 'table'].includes(tag)) return `${node.outerHTML}\n\n`;
  if (tag === 'div' && node.dataset.editorBlock === 'toc') return '[TOC]\n\n';
  if (tag === 'p') return `${children() || '<p></p>'}\n\n`;
  if (/^h[1-6]$/.test(tag)) return `${'#'.repeat(Number(tag[1]))} ${children()}\n\n`;
  if (tag === 'br') return profile === 'whatsapp' ? '\n' : '  \n';
  if (['strong', 'b'].includes(tag)) return `${profile === 'whatsapp' ? '*' : '**'}${children()}${profile === 'whatsapp' ? '*' : '**'}`;
  if (['em', 'i'].includes(tag)) return `${profile === 'whatsapp' ? '_' : '*'}${children()}${profile === 'whatsapp' ? '_' : '*'}`;
  if (['s', 'del', 'strike'].includes(tag)) return `${profile === 'whatsapp' ? '~' : '~~'}${children()}${profile === 'whatsapp' ? '~' : '~~'}`;
  if (tag === 'code' && node.parentElement?.localName !== 'pre') {
    const ticks = '`'.repeat(Math.max(1, ...[...node.textContent.matchAll(/`+/g)].map((m) => m[0].length + 1)));
    const pad = /(^`|`$|^ .* $)/.test(node.textContent) ? ' ' : '';
    return `${ticks}${pad}${node.textContent}${pad}${ticks}`;
  }
  if (tag === 'pre') {
    const code = node.querySelector('code');
    const text = code?.textContent ?? node.textContent;
    const ticks = '`'.repeat(Math.max(3, ...[...text.matchAll(/`+/g)].map((m) => m[0].length + 1)));
    const language = code?.className?.replace(/^language-/, '') || '';
    return `${ticks}${language}\n${profile === 'whatsapp' ? text : text.replace(/\n$/, '')}\n${ticks}\n\n`;
  }
  if (tag === 'a') return `[${children()}](${node.getAttribute('href').replace(/[()\s]/g, (char) => encodeURIComponent(char))}${node.title ? ` "${node.title.replace(/"/g, '&quot;')}"` : ''})`;
  if (['ul', 'ol'].includes(tag)) {
    const start = Number(node.getAttribute('start') || 1);
    const items = [...node.children].map((item, index) => {
      const prefix = tag === 'ol' ? `${start + index}. ` : '- ';
      const content = childNodes(item).map((child) => serializeNode(child, profile)).join('').trimEnd();
      return prefix + content.replace(/\n/g, `\n${' '.repeat(prefix.length)}`);
    });
    return `${items.join('\n')}\n\n`;
  }
  if (tag === 'blockquote') {
    const marker = node.dataset.callout ? `[!${node.dataset.callout}]\n` : '';
    return `${(marker + children().trimEnd()).split('\n').map((line) => `> ${line}`).join('\n')}\n\n`;
  }
  if (tag === 'table') {
    const rows = [...node.querySelectorAll('tr')];
    const complex = node.querySelector('[colspan]:not([colspan="1"]),[rowspan]:not([rowspan="1"]),td > ul,td > ol,td > p + p,th > p + p,br,pre,blockquote');
    if (!rows.length) return '';
    if (complex || !rows[0].querySelector('th')) return `${node.outerHTML}\n\n`;
    const cells = (row) => [...row.children].map((cell) => childNodes(cell).map((child) => serializeNode(child, profile)).join('').trim());
    const lines = rows.map((row) => `| ${cells(row).join(' | ')} |`);
    lines.splice(1, 0, `| ${cells(rows[0]).map(() => '---').join(' | ')} |`);
    return `${lines.join('\n')}\n\n`;
  }
  if (tag === 'hr') return '---\n\n';
  return children();
}

export function htmlToSource(html, profile = 'document') {
  const root = validateEditorialHtml(html, profile);
  const source = childNodes(root).map((node) => serializeNode(node, profile)).join('').trimEnd();
  const restored = sourceToHtml(source, profile);
  if (semanticHtml(html) === semanticHtml(restored)) return source;
  if (profile === 'whatsapp') throw new EditorialFormatError('unsupported-whatsapp:representation');
  // Extended Markdown explicitly allows complete HTML blocks. Falling back to
  // one preserves edge whitespace, adjacent marks and complex table content.
  const wrapper = document.createElement('div'); wrapper.append(root);
  return wrapper.innerHTML;
}

export function editorialPlainText(source, profile = 'document') {
  const root = fragment(sourceToHtml(source, profile, { strict: false }));
  const text = (node) => {
    if (node.nodeType === 3) {
      const parent = node.parentElement;
      const blockWhitespace = !parent || parent.matches('ul,ol,table,thead,tbody,tfoot,tr,blockquote') || [...parent.children].some((child) => child.matches('p,ul,ol,blockquote,table,h1,h2,h3,h4,h5,h6,pre'));
      return /^\s*$/.test(node.textContent) && blockWhitespace ? '' : node.textContent;
    }
    if (node.nodeType !== 1 && node.nodeType !== 11) return '';
    if (node.localName === 'br') return '\n';
    if (node.localName === 'pre') return `${node.textContent.trimEnd()}\n\n`;
    if (node.localName === 'tr') return `${[...node.children].map((cell) => text(cell).trim()).join('\t')}\n`;
    const contents = childNodes(node).reduce((result, child) => {
      const separator = child.nodeType === 1 && child.matches('p,ul,ol,table,blockquote,pre') && result && !result.endsWith('\n') ? '\n' : '';
      return result + separator + text(child);
    }, '');
    if (node.localName === 'li') return `${contents.trimEnd()}\n`;
    if (node.localName === 'p' && ['li', 'td', 'th'].includes(node.parentElement?.localName)) return node.parentElement.children.length > 1 ? `${contents}\n` : contents;
    if (node.matches?.('p,h1,h2,h3,h4,h5,h6,blockquote,ul,ol,table')) return `${contents.trimEnd()}\n\n`;
    return contents;
  };
  return text(root).replace(/\n{3,}/g, '\n\n').trim();
}

export async function copyEditorialContent(source, profile = 'document') {
  const html = sourceToHtml(source, profile);
  const text = profile === 'whatsapp' ? source : editorialPlainText(source, profile);
  if (profile !== 'whatsapp' && typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
    await navigator.clipboard.write([new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([text], { type: 'text/plain' }) })]);
  } else await navigator.clipboard.writeText(text);
}
