import { historicalTextKey } from './documentHistoryContent';

const ORGANIZATION = new Set(['folder', 'project', 'deliverable', 'client_user', 'tags', 'states', 'status', 'commercial_status', 'is_archived', 'archived_at', 'archived_via_folder', 'is_client_visible']);
const NOTES = new Set(['notes', 'document_notes', 'client_email_subject', 'client_email_body', 'client_whatsapp_message', 'client_custom_notes']);
const BILLING = new Set(['collection_account', 'billing_context', 'items', 'payment_methods', 'income_record', 'issuer', 'issue_date', 'due_date', 'city', 'currency', 'subtotal', 'discount_total', 'tax_total', 'total', 'terms_and_conditions']);
const TECHNICAL = new Set(['slug', 'template_version', 'source_version', 'metadata', 'generated_file', 'uploaded_pdf', 'pdf_size', 'pdf_sha256', 'pdf_version', 'pdf_text_status', 'content_format']);
const EDITORIAL = new Set(['notes', 'terms_and_conditions', 'client_email_body', 'client_custom_notes', 'content']);
const SKIP = new Set(['content_markdown', 'content_json', 'text_formats']);
export const DOCUMENT_HISTORY_GROUPS = ['document', 'organization', 'notes', 'billing', 'technical'];

const equal = (left, right) => {
  if (left === right) return true;
  if (left === null || right === null || typeof left !== 'object' || typeof right !== 'object') return false;
  const keys = Object.keys(left).sort();
  return keys.length === Object.keys(right).length && keys.every((key) => Object.hasOwn(right, key) && equal(left[key], right[key]));
};
const groupFor = (root) => ORGANIZATION.has(root) ? 'organization' : NOTES.has(root) ? 'notes' : BILLING.has(root) ? 'billing' : TECHNICAL.has(root) ? 'technical' : 'document';
const humanize = (value) => value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase());
const pointer = (parts) => '/' + parts.map((part) => String(part).replaceAll('~', '~0').replaceAll('/', '~1')).join('/');

/** Flatten only presentation data, never modify the stored snapshot. */
function fields(snapshot, labels, t, te) {
  const result = new Map();
  function visit(value, parts, context = [], owner = snapshot, localParts = parts) {
    const name = parts[parts.length - 1];
    const root = parts[0];
    if (name === 'text_formats') return;
    const labelKey = `documentHistory.fields.${name}`;
    const label = te(labelKey) ? t(labelKey) : labels[name] || humanize(name);
    if (value && typeof value === 'object' && !('id' in value && 'label' in value) && !value.protected) {
      const isArray = Array.isArray(value);
      const entries = Object.entries(value).filter(([key]) => key !== 'text_formats');
      // A historical FK's label is already a snapshot; do not resolve live IDs.
      for (const [key, item] of entries) {
        const childName = /^\d+$/.test(key) ? item?.title || item?.name || t('documentHistory.item', { number: isArray ? Number(key) + 1 : key }) : label;
        visit(item, [...parts, key], [...context, childName], value, [key]);
      }
      return;
    }
    const format = snapshot.text_formats?.[pointer(parts)] || owner?.text_formats?.[pointer(localParts)] || (EDITORIAL.has(name) ? 'markdown' : name === 'client_whatsapp_message' ? 'whatsapp_v1' : 'plain');
    const file = ['generated_file', 'uploaded_pdf'].includes(root);
    result.set(parts.join('.'), { key: parts.join('.'), label: [...context, label].join(' · '), value: file && value ? t('documentHistory.storedFile') : value, identity: file ? value : undefined, format, group: groupFor(root) });
  }
  for (const [name, value] of Object.entries(snapshot || {})) {
    if (!SKIP.has(name)) visit(value, [name]);
  }
  for (const [name, value] of Object.entries(snapshot.content_json?.meta || {})) {
    if (!(name in snapshot)) visit(value, [name]);
  }
  return result;
}

function comparable(field) {
  if (field?.identity !== undefined) return field.identity;
  const value = field?.value ?? null;
  if (value === '') return null;
  if (typeof value !== 'string' || !value || field.format === 'plain') return value;
  return historicalTextKey(value, field.format);
}

export function documentFieldGroups(before, after, { labels = {}, t, te = () => false, full = false } = {}) {
  const oldFields = fields(before || {}, labels, t, te);
  const newFields = fields(after || {}, labels, t, te);
  const groups = new Map(DOCUMENT_HISTORY_GROUPS.map((key) => [key, []]));
  for (const key of new Set([...oldFields.keys(), ...newFields.keys()])) {
    const old = oldFields.get(key);
    const next = newFields.get(key);
    if (!full && equal(comparable(old), comparable(next))) continue;
    const field = next || old;
    if (full && (field.value === null || field.value === undefined || field.value === '')) continue;
    groups.get(field.group).push({ ...field, old, next, formatOnly: Boolean(old && next && old.value === next.value && old.format !== next.format) });
  }
  return [...groups].filter(([, values]) => values.length).map(([key, values]) => ({ key, values }));
}
