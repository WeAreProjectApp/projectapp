import { escapeHtml, normalizeEditorialColor, sourceToHtml } from './editorialFormat';
import { historyHunks, historySequence } from './historySequence';

const safeSource = (source, format = 'markdown') => format === 'plain'
  ? `<p>${escapeHtml(source).replace(/\n/g, '<br>')}</p>`
  : sourceToHtml(String(source ?? ''), format === 'whatsapp_v1' ? 'whatsapp' : 'document', { strict: false });

function legacyList(items = [], ordered = false) {
  const tag = ordered ? 'ol' : 'ul';
  return `<${tag}>${items.map((item) => `<li>${safeSource(typeof item === 'string' ? item : item?.text)}${item?.children?.length ? legacyList(item.children, ordered) : ''}</li>`).join('')}</${tag}>`;
}

/** Historical JSON blocks predate the Markdown source; never regenerate them. */
function legacyBlock(block) {
  if (!block || typeof block !== 'object') return `<pre>${escapeHtml(JSON.stringify(block))}</pre>`;
  switch (block.type) {
    case 'rich_html': return sourceToHtml(block.html || '', 'document', { strict: false, inputHtml: true });
    case 'heading': {
      const level = Math.min(6, Math.max(1, Number(block.level) || 2));
      return `<h${level}>${escapeHtml(block.text || '')}</h${level}>`;
    }
    case 'section_header': case 'sub_section': return `<h2>${escapeHtml([block.number ?? block.index, block.title].filter(Boolean).join(' '))}</h2>`;
    case 'paragraph': return safeSource(block.text || '');
    case 'list': return legacyList(block.items, block.ordered);
    case 'table': return `<table><thead><tr>${(block.headers || []).map((cell) => `<th>${safeSource(cell)}</th>`).join('')}</tr></thead><tbody>${(block.rows || []).map((row) => `<tr>${row.map((cell) => `<td>${safeSource(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    case 'blockquote': return `<blockquote>${safeSource(block.text || '')}</blockquote>`;
    case 'callout': return `<blockquote data-callout="${['note', 'tip', 'important', 'warning', 'caution'].includes(block.style) ? block.style.toUpperCase() : 'NOTE'}">${safeSource(block.text || '')}</blockquote>`;
    case 'code': return `<pre><code>${escapeHtml(block.content || '')}</code></pre>`;
    case 'separator': return '<hr>';
    case 'toc': return '<div data-editor-block="toc">[TOC]</div>';
    default: return `<pre>${escapeHtml(JSON.stringify(block, null, 2))}</pre>`;
  }
}

const KNOWN_BLOCKS = new Set(['rich_html', 'heading', 'section_header', 'sub_section', 'paragraph', 'list', 'table', 'blockquote', 'callout', 'code', 'separator', 'toc']);

// Align list items and table rows independently. A one-cell change must not
// duplicate an entire long table; the header remains context in each row view.
function comparisonBlocks(node) {
  if (node.localName === 'table') {
    return [...node.rows].map((row) => {
      const table = node.cloneNode(false);
      const header = row.parentElement.localName === 'thead';
      if (!header && node.tHead) table.append(node.tHead.cloneNode(true));
      const group = document.createElement(header ? 'thead' : 'tbody');
      group.append(row.cloneNode(true));
      table.append(group);
      return { node: table, key: canonicalSignature(row) };
    });
  }
  if (['ul', 'ol'].includes(node.localName)) {
    return [...node.children].map((item, index) => {
      const list = node.cloneNode(false);
      if (node.localName === 'ol') list.setAttribute('start', String((Number(node.getAttribute('start')) || 1) + index));
      list.append(item.cloneNode(true));
      return { node: list, key: JSON.stringify([node.localName, list.getAttribute('start'), canonicalSignature(item)]) };
    });
  }
  return [{ node, key: canonicalSignature(node) }];
}

// Compare semantic nodes, not serialized source. Retain meaningful styles,
// link destinations, table spans, list numbering and whitespace inside code.
function signature(node, inCode = false) {
  if (node.nodeType === 3) return inCode ? node.textContent : node.textContent.replace(/\s+/g, ' ');
  if (node.nodeType !== 1) return '';
  const tag = ({ b: 'strong', i: 'em', del: 's', strike: 's' })[node.localName] || node.localName;
  const preserve = inCode || ['pre', 'code'].includes(tag);
  const structural = ['table', 'thead', 'tbody', 'tfoot', 'tr', 'ul', 'ol'].includes(tag);
  const children = [...node.childNodes].map((child) => signature(child, preserve)).filter((child) => child !== '' && !(structural && child === ' '));
  const attributes = [...node.attributes].filter(({ name, value }) => !(name === 'class' && tag === 'code' ? !/^language-[\w-]+$/.test(value) : ['class', 'id', 'target', 'rel'].includes(name)) && !(['colspan', 'rowspan', 'start'].includes(name) && value === '1')).map(({ name, value }) => {
    if (name !== 'style') return [name, value];
    const styles = ['color', 'background-color', 'text-align'].map((property) => {
      const raw = node.style.getPropertyValue(property);
      return raw ? [property, normalizeEditorialColor(raw) || raw.trim()] : null;
    }).filter(Boolean);
    return ['style', styles];
  }).sort(([a], [b]) => a.localeCompare(b));
  if (tag === 'span' && !attributes.length) return children.join('');
  return JSON.stringify([tag, attributes, children]);
}

export function historicalContent(snapshot = {}) {
  const legacy = !snapshot.content_markdown && Array.isArray(snapshot.content_json?.blocks);
  const format = snapshot.text_formats?.['/content_markdown'] || 'markdown';
  const html = legacy ? snapshot.content_json.blocks.map(legacyBlock).join('') : snapshot.content_markdown ? safeSource(snapshot.content_markdown, format) : '';
  const host = document.createElement('div');
  // The final pass also covers generated legacy wrappers and historical input.
  host.innerHTML = sourceToHtml(html, 'document', { strict: false, inputHtml: true });
  let section = '';
  const blocks = [...host.childNodes].filter((node) => node.nodeType === 1 || node.textContent.trim()).flatMap((node) => {
    if (node.nodeType === 1 && /^h[1-6]$/.test(node.localName)) section = node.textContent.trim();
    return comparisonBlocks(node).map(({ node: block, key }) => ({ html: block.outerHTML || `<p>${escapeHtml(block.textContent)}</p>`, text: block.localName === 'pre' ? block.textContent : block.textContent.replace(/\s+/g, ' ').trim(), section, key }));
  });
  return {
    html: host.innerHTML, blocks,
    unsupported: legacy && snapshot.content_json.blocks.some((block) => !KNOWN_BLOCKS.has(block?.type)),
    pdf: ['pdf', 'uploaded_pdf'].includes(snapshot.content_format) || Boolean(snapshot.uploaded_pdf),
  };
}

function canonicalSignature(node) {
  const canonical = node.cloneNode(true);
  canonical.querySelectorAll?.('thead,tbody,tfoot').forEach((group) => group.replaceWith(...group.childNodes));
  canonical.querySelectorAll?.('li,td,th').forEach((container) => {
    if (container.children.length === 1 && container.firstElementChild.localName === 'p' && !container.firstElementChild.attributes.length) container.firstElementChild.replaceWith(...container.firstElementChild.childNodes);
  });
  return signature(canonical);
}

export function historicalTextKey(source, format) {
  const host = document.createElement('div');
  host.innerHTML = safeSource(source, format);
  return [...host.childNodes].filter((node) => node.nodeType === 1 || node.textContent.trim()).map(canonicalSignature).join('');
}

export function documentContentDiff(before, after) {
  const oldContent = historicalContent(before);
  const newContent = historicalContent(after);
  const { operations, simplified } = historySequence(oldContent.blocks, newContent.blocks);
  return { hunks: historyHunks(operations), simplified, unsupported: oldContent.unsupported || newContent.unsupported, pdf: oldContent.pdf || newContent.pdf };
}
