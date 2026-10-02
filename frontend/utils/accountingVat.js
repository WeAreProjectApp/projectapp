/** Cent-based arithmetic for previews; the server independently validates capture. */
function units(value) {
  const text = String(value ?? '')
  if (!/^\d+(?:\.\d{0,2})?$/.test(text)) return null
  const [whole, fraction = ''] = text.split('.')
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))
}
function money(value) {
  return `${value / 100n}.${String(value % 100n).padStart(2, '0')}`
}
function roundedDivision(numerator, denominator) {
  return (numerator + denominator / 2n) / denominator
}
export function vatBreakdown(amount, rate, mode = 'vat_included') {
  const cents = units(amount)
  if (cents === null || cents > 99999999999999n || !['before_vat', 'vat_included'].includes(mode)) return null
  if (rate === null || rate === undefined || rate === '') {
    return mode === 'vat_included' ? { base: null, vat: null, total: money(cents) } : null
  }
  const percentage = units(rate)
  if (percentage === null || percentage > 10000n) return null
  const base = mode === 'before_vat' ? cents : roundedDivision(cents * 10000n, 10000n + percentage)
  const vat = mode === 'before_vat' ? roundedDivision(base * percentage, 10000n) : cents - base
  const total = base + vat
  if (total > 99999999999999n) return null
  return { base: money(base), vat: money(vat), total: money(total) }
}
