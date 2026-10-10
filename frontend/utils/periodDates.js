import { FREQUENCY_MONTHS } from '~/utils/recurring'

// Local-time today: toISOString() would shift to tomorrow after 19:00
// in Bogotá (UTC-5).
export function todayISO() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// ── Covered-period arithmetic ('YYYY-MM-DD' strings in, strings out) ────────
// Every advance clamps the day — Jan 31 + 1 month is Feb 28, not Mar 3 —
// mirroring `content/utils.add_months` on the backend so the period the form
// proposes is the period the server would compute. (HostingCyclesModal's
// Date.UTC arithmetic predates this and overflows; do not copy it.)
const DATE_RE = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/

function parse(value) {
  const match = DATE_RE.exec(String(value ?? '').trim())
  if (!match) return null
  // 'YYYY-MM' means day 1, same shorthand FlexiblePeriodField accepts.
  return { year: +match[1], month: +match[2], day: match[3] ? +match[3] : 1 }
}

/** Compare calendar days, treating 'YYYY-MM' as the first of that month. */
export function sameDay(a, b) {
  const left = parse(a)
  const right = parse(b)
  return !!left && !!right
    && left.year === right.year
    && left.month === right.month
    && left.day === right.day
}

function lastDayOf(year, month) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate()
}

function toIso(year, month, day) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

/** 'YYYY-MM(-DD)' + n months, day clamped. Returns '' on unparseable input. */
export function addMonths(value, months) {
  const parts = parse(value)
  if (!parts) return ''
  const total = parts.year * 12 + (parts.month - 1) + months
  const year = Math.floor(total / 12)
  const month = (total % 12) + 1
  return toIso(year, month, Math.min(parts.day, lastDayOf(year, month)))
}

/** The day before, for inclusive period ends. */
export function previousDay(value) {
  const parts = parse(value)
  if (!parts) return ''
  const date = new Date(Date.UTC(parts.year, parts.month - 1, parts.day - 1))
  return toIso(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate())
}

/**
 * Inclusive end of a period: start + cadence − 1 day, so the next period
 * starts the day after it. '' for `custom` or an unknown cadence — those are
 * written by hand.
 */
export function nextPeriodEnd(start, cadence) {
  const months = FREQUENCY_MONTHS[cadence]
  if (!months) return ''
  return previousDay(addMonths(start, months))
}
