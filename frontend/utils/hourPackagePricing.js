// Pricing math + money formatting shared by the hour-packages view modes
// (table, cards, compare). COP shows no decimals (es-CO), USD keeps cents.

export function effectiveRate(pkg) {
  return Number(pkg.hourly_rate) * (1 - Number(pkg.discount_percent || 0) / 100);
}

export function totalPrice(pkg) {
  if (pkg.pricing_model === 'requirements') return Number(pkg.total_price);
  return Number(pkg.hours) * effectiveRate(pkg);
}

export function formatPackageMoney(value, currency) {
  const num = Number(value) || 0;
  const formatted = num.toLocaleString(currency === 'COP' ? 'es-CO' : 'en-US', {
    maximumFractionDigits: currency === 'COP' ? 0 : 2,
  });
  return `$${formatted} ${currency}`;
}

// Package to highlight in the compare mode: the active package with the
// lowest effective rate, only when it actually beats the base rate.
export function bestValuePackageId(packages) {
  const active = packages.filter((p) => p.is_active && Number(p.discount_percent) > 0);
  if (active.length === 0) return null;
  if (active.some((p) => p.pricing_model === 'requirements')) {
    return active.reduce((best, p) => Number(p.discount_percent) > Number(best.discount_percent) ? p : best).id;
  }
  return active.reduce((best, p) => (effectiveRate(p) < effectiveRate(best) ? p : best)).id;
}

export function composition(pkg) {
  return `${pkg.xs_count ?? 0} XS · ${pkg.s_count ?? 0} S · ${pkg.m_count ?? 0} M`;
}
