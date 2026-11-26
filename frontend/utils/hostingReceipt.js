export const requestUuid = () => globalThis.crypto?.randomUUID?.()
  ?? 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const value = Math.floor(Math.random() * 16);
    return (c === 'x' ? value : (value & 3) | 8).toString(16);
  });

export function emptyReceipt() {
  return { issuer: '', reference: '', entries: [] }
}

export function receiptPayload(form, periods) {
  if (!periods.length) return null
  const entries = periods.map(period => ({
    ...form.entries.find(row => row.income_id === period.income_id),
    income_id: period.income_id, hosting_record_id: period.hosting_record_id,
  }))
  const issuer = form.issuer.trim()
  const reference = form.reference.trim()
  if (issuer && reference) return { issuer, reference, entries }
  if (!issuer && !reference && entries.some(row => row.cycle_id || row.liquid_id)) return { entries }
  return null
}
