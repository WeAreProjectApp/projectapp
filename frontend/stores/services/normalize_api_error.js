/**
 * Normalize a caught axios error into a consistent shape the panel UI can render.
 *
 * The backend is inconsistent about error payloads:
 *   - { error: "message", code?, hint? }   (proposal/content endpoints)
 *   - { detail: "message" }                (DRF default / permission errors)
 *   - { field: ["err1", "err2"], ... }     (serializer field errors)
 *   - { non_field_errors: [...] }          (serializer object-level errors)
 *   - a bare string
 *
 * @param {*} error - The value thrown by an awaited HTTP call (usually an axios error).
 * @param {string} [fallback] - Message to use when nothing usable is found.
 * @returns {{ message: string, code: string|null, hint: string|null, fieldErrors: Object|null, status: number|null }}
 */
export function normalizeApiError(error, fallback = 'Ocurrió un error. Inténtalo de nuevo.') {
  const data = error?.response?.data;
  const status = error?.response?.status ?? null;
  const headers = error?.response?.headers;
  const contentType = headers?.get?.('content-type') || headers?.['content-type'] || '';

  if (data == null || /\btext\/html\b|\bapplication\/xhtml\+xml\b/i.test(contentType)) {
    return { message: fallback, code: null, hint: null, fieldErrors: null, status };
  }

  if (typeof data === 'string') {
    return { message: firstString(data) || fallback, code: null, hint: null, fieldErrors: null, status };
  }

  const code = typeof data.code === 'string' ? data.code : null;
  const hint = firstString(data.hint);

  // Explicit human message keys, in priority order.
  const direct = firstString(data.error) || firstString(data.detail) || firstString(data.message);
  if (direct) {
    return { message: direct, code, hint, fieldErrors: collectFieldErrors(data), status };
  }

  // Serializer field errors: pick the first readable message, keep the map.
  const fieldErrors = collectFieldErrors(data);
  if (fieldErrors) {
    const firstKey = Object.keys(fieldErrors)[0];
    return { message: fieldErrors[firstKey], code, hint, fieldErrors, status };
  }

  return { message: fallback, code, hint, fieldErrors: null, status };
}

/**
 * Same as `normalizeApiError`, but for calls made with `responseType: 'blob'`.
 *
 * Axios honours the requested response type even when the request fails, so a
 * JSON error body arrives as a `Blob` and every key lookup on it returns
 * undefined — the caller ends up showing the generic fallback while the
 * backend's explanation sits unread inside the blob. This reads it first.
 *
 * @param {*} error - The value thrown by an awaited HTTP call.
 * @param {string} [fallback] - Message to use when nothing usable is found.
 * @returns {Promise<ReturnType<typeof normalizeApiError>>}
 */
export async function normalizeBlobApiError(error, fallback) {
  const data = error?.response?.data;
  if (typeof Blob === 'undefined' || !(data instanceof Blob)) {
    return normalizeApiError(error, fallback);
  }

  let parsed = null;
  try {
    parsed = JSON.parse(await readBlobText(data));
  } catch {
    // Not JSON (an HTML error page, a truncated PDF): the fallback is the
    // best we can say, and it beats throwing while handling an error.
    return normalizeApiError({ ...error, response: { ...error.response, data: null } }, fallback);
  }

  return normalizeApiError({ ...error, response: { ...error.response, data: parsed } }, fallback);
}

/**
 * Read a Blob as text. Browsers have `Blob.text()`; jsdom does not, so the
 * FileReader path keeps this readable under unit tests too.
 *
 * @param {Blob} blob
 * @returns {Promise<string>}
 */
function readBlobText(blob) {
  if (typeof blob.text === 'function') return blob.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

/**
 * Numeric ids an error payload carries under `key` (default `missing_ids`).
 *
 * Read apart from `normalizeApiError` on purpose: `collectFieldErrors` keeps
 * only strings, because it feeds human-facing per-field messages for every
 * store in the app. Widening it to preserve numbers would change how errors
 * render everywhere for the sake of one pair of endpoints, so the machine
 * payload gets its own reader.
 *
 * @returns {number[]} Empty when the key is absent, not an array, or holds
 *   nothing numeric.
 */
export function numericIdsFromError(error, key = 'missing_ids') {
  const value = error?.response?.data?.[key];
  if (!Array.isArray(value)) return [];
  // Strings are coerced (a JSON id may arrive quoted) but nothing else is:
  // a blanket Number() turns null into 0, which would drop a real row from
  // the selection.
  return value
    .map((id) => (typeof id === 'string' ? Number(id) : id))
    .filter((id) => typeof id === 'number' && Number.isFinite(id));
}

/** Return `value` as a trimmed string if it's a non-empty string, else null. */
function firstString(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  // Django/proxy/login HTML is never a user-facing API explanation. Do not
  // strip tags: the remaining text could still expose a server traceback.
  if (/<!doctype\b|<\/?[a-z][^>]*>/i.test(value)) return null;
  return value.trim();
}

/**
 * Build a { field: "first message" } map from serializer-style field errors,
 * skipping the reserved meta keys. Returns null when there are none.
 */
function collectFieldErrors(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
  const reserved = new Set(['error', 'detail', 'message', 'code', 'hint']);
  const result = {};
  for (const [key, value] of Object.entries(data)) {
    if (reserved.has(key)) continue;
    const msg = Array.isArray(value) ? firstString(value[0]) : firstString(value);
    if (msg) result[key] = msg;
  }
  return Object.keys(result).length ? result : null;
}
