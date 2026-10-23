/**
 * Converts URLs in plain text into clickable <a> tags.
 * Detects both full URLs (https://...) and bare domains (example.com).
 * Safe for admin-authored proposal content rendered with v-html.
 *
 * Usage:
 *   import { linkify } from '~/composables/useLinkify';
 *   <p v-html="linkify(text)" />
 */

import { escapeHtml } from '~/utils/escapeHtml';
import { sourceToHtml } from '~/utils/editorialFormat';

// Full URLs: https://example.com/path
const FULL_URL_RE = /https?:\/\/[^\s),]+/g;

// Bare domains: example.com, example.co/path (must have known TLD)
const BARE_DOMAIN_RE = /(?<![\/\w@])([a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.(?:com|co|net|org|io|dev|app|at|de|es|fr|uk|us|me|info|biz|tv|cc)(?:\/[^\s),]*)?)(?![\/\w])/g;

/**
 * Replace URLs in text with anchor tags that open in a new tab.
 * HTML in the input is escaped before linkifying, so admin-authored content
 * never injects raw markup. <b>/<strong> tags traditionally embedded in
 * content_json are preserved by re-allowing them after escape.
 * @param {string} text - Plain text that may contain URLs and limited inline HTML.
 * @returns {string} HTML string with URLs wrapped in <a> tags.
 */
export function linkify(text, format = 'plain') {
  if (!text || typeof text !== 'string') return '';
  if (format !== 'plain' && typeof document !== 'undefined') {
    try { return `<div class="editorial-rendered">${sourceToHtml(text, format === 'whatsapp_v1' ? 'whatsapp' : 'document', { strict: false })}</div>`; }
    catch { return escapeHtml(text); }
  }

  // Escape all HTML first to prevent XSS, then re-allow a small whitelist
  // of inline tags that admin copy historically uses (<b>, <strong>, <i>,
  // <em>, <br>). Anything else stays escaped.
  let safe = escapeHtml(text)
    .replace(/&lt;(\/?)(b|strong|i|em|br)\s*&gt;/gi, '<$1$2>');

  // Step 1: replace full URLs first
  let result = safe.replace(FULL_URL_RE, (url) => {
    const display = formatDisplay(url);
    return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="linkify-link">${display}</a>`;
  });

  // Step 2: replace bare domains (that weren't already linkified)
  result = result.replace(BARE_DOMAIN_RE, (match) => {
    // Skip if already inside an <a> tag (already linkified)
    const before = result.substring(0, result.indexOf(match));
    if (before.lastIndexOf('<a ') > before.lastIndexOf('</a>')) return match;
    const display = match.replace(/^www\./, '');
    return `<a href="https://${match}" target="_blank" rel="noopener noreferrer" class="linkify-link">${display}</a>`;
  });

  return result;
}

function formatDisplay(url) {
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, '') + (u.pathname !== '/' ? u.pathname.replace(/\/$/, '') : '');
  } catch {
    return url;
  }
}

export function useLinkify() {
  return { linkify };
}
