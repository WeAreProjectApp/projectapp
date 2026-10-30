/** Normalized text plus original UTF-16 offsets for safe, accent-blind marks. */
function indexedName(value) {
  const original = String(value ?? '');
  let text = '';
  const offsets = [];
  let position = 0;
  for (const character of original) {
    const start = position;
    position += character.length;
    const normalized = character.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
    if (!normalized && offsets.length) offsets.at(-1).end = position;
    for (const letter of normalized) {
      const next = /[_\p{White_Space}\uFEFF]/u.test(letter) ? ' ' : letter;
      if (next === ' ' && (!text || text.endsWith(' '))) {
        if (text) offsets.at(-1).end = position;
        continue;
      }
      text += next;
      for (let index = 0; index < next.length; index += 1) {
        offsets.push({ start, end: position });
      }
    }
  }
  if (text.endsWith(' ')) { text = text.slice(0, -1); offsets.pop(); }
  // Whole-string lowercase retains contextual rules (for example final sigma).
  // Its offsets have the same lengths as the per-character lowercase map above.
  return { original, text: normalizeContractSource(original), offsets };
}

export function normalizeContractSource(value) {
  return String(value ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
    .replace(/[_\p{White_Space}\uFEFF]+/gu, ' ').replace(/^ +| +$/g, '');
}

export function contractSourceParts(title, query) {
  const { original, text, offsets } = indexedName(title);
  const needle = normalizeContractSource(query);
  if (!needle) return [{ text: original, match: false }];
  const parts = [];
  let cursor = 0;
  let found = text.indexOf(needle);
  while (found !== -1) {
    const start = offsets[found].start;
    const end = offsets[found + needle.length - 1].end;
    if (start > cursor) parts.push({ text: original.slice(cursor, start), match: false });
    parts.push({ text: original.slice(start, end), match: true });
    cursor = end;
    found = text.indexOf(needle, found + needle.length);
  }
  if (cursor < original.length) parts.push({ text: original.slice(cursor), match: false });
  return parts;
}

export const contractSourceKey = (source) => `${source.source_type}:${source.id}`;
