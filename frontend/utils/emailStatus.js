const EMAIL_STATUS_LABELS = {
  sent: 'Enviado',
  delivered: 'Entregado',
  bounced: 'Rebotado',
  failed: 'Fallido',
  skipped: 'Omitida',
};

/** Known transport values share the vocabulary of the panel email history. */
export function emailStatusLabel(status, fallback = '') {
  return EMAIL_STATUS_LABELS[status] || fallback || status || '';
}
