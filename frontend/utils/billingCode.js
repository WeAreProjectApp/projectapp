/**
 * Client-side mirror of `accounts/services/billing_code.py`.
 *
 * Only the normalization lives here — validation stays on the backend, which is
 * the single source of truth and answers with the message the panel shows. This
 * exists so every surface sends the same shape (uppercase, trimmed, single
 * spaces) instead of each modal rolling its own.
 */
export const BILLING_CODE_MAX_LENGTH = 12;

/** Uppercase and trim, collapsing inner whitespace runs. */
export function normalizeBillingCode(value) {
  return String(value || '').trim().replace(/\s+/g, ' ').toUpperCase();
}

/**
 * The client form's own state, so no surface can drift from the rest.
 *
 * `is_archived` lives here but is NOT part of the payload below, and that is
 * deliberate: the update endpoint rejects it with
 * `client_archive_transition_required`, because archiving suspends the
 * client's projects and cancels their future billing. The modals act on it
 * through the archive endpoint instead.
 */
export function emptyClientForm() {
  return {
    name: '', email: '', phone: '', company: '', nit: '', cedula: '',
    identification_type: 'NIT', address: '', billing_code: '',
    is_archived: false,
  };
}

/**
 * Trimmed identity/contact payload. The selected document type decides which
 * identification is used; a personal cédula must never be saved as a NIT.
 *
 * Anything not listed here is dropped silently, so a new field that the API
 * must receive has to be added in BOTH functions. `is_archived` is the
 * exception that proves it: it is left out on purpose (see above).
 */
export function clientFormPayload(form) {
  return {
    name: (form.name || '').trim(),
    email: (form.email || '').trim(),
    phone: (form.phone || '').trim(),
    company: (form.company || '').trim(),
    nit: form.identification_type === 'CC' ? '' : (form.nit || '').trim(),
    cedula: (form.cedula || '').trim(),
    address: (form.address || '').trim(),
    billing_code: normalizeBillingCode(form.billing_code),
  };
}

/** Billing data comes from the same server projection used for the PDF. */
export function clientCustomerSnapshot(client) {
  if (client.billing_customer) return { ...client.billing_customer };
  // Older cached picker rows can still arrive without the projection.
  return {
    name: client.nit ? (client.company || client.name || '') : (client.name || client.company || ''),
    identification_type: client.nit ? 'NIT' : (client.cedula ? 'CC' : ''),
    identification: client.nit || client.cedula || '',
    email: client.is_email_placeholder ? '' : (client.email || ''),
    contact_name: client.name || '',
    address: client.address || '',
  };
}
