const formatters = new Map();

function formatterFor(decimals) {
  if (!formatters.has(decimals)) {
    formatters.set(decimals, new Intl.NumberFormat('es-CO', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }));
  }
  return formatters.get(decimals);
}

/**
 * Money for display. Whole pesos by default, which is what COP amounts want.
 *
 * `decimals` exists for prorated values: a USD subscription billed yearly can
 * come out below $1/month, and rounding that to zero decimals would erase the
 * figure instead of showing it. `decimals: 'auto'` preserves cents while
 * keeping whole amounts compact; callers opt in explicitly.
 */
export function formatMoney(amount, currency = '', { decimals = 0 } = {}) {
  if (amount === null || amount === undefined) return '';
  const n = Number(amount);
  if (!Number.isFinite(n)) return '';
  // Choose precision only for display; never round the value used by callers.
  const precision = decimals === 'auto' ? (Number.isInteger(n) ? 0 : 2) : decimals;
  const formatted = formatterFor(precision).format(n);
  return currency ? `$${formatted} ${currency}` : `$${formatted}`;
}

const compactFormatter = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 });

/**
 * Short money for chart axes: 1234567 -> "$1,2M", -850000 -> "-$850K".
 * Tooltips and KPIs keep the full formatMoney value.
 */
export function formatCompactMoney(amount) {
  if (amount === null || amount === undefined) return '';
  const n = Number(amount);
  if (!Number.isFinite(n)) return '';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1_000_000) return `${sign}$${compactFormatter.format(abs / 1_000_000)}M`;
  if (abs >= 1_000) return `${sign}$${compactFormatter.format(abs / 1_000)}K`;
  return `${sign}$${compactFormatter.format(abs)}`;
}
