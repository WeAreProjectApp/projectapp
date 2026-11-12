const DEFAULT_EXPIRY_DAYS = 21;
const DAY_MS = 24 * 60 * 60 * 1000;
const pad = (value) => String(value).padStart(2, '0');
const datePart = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const timePart = (date) => `${pad(date.getHours())}:${pad(date.getMinutes())}`;
const calendarDay = (date) => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / DAY_MS;

/** Convert an API timestamp to the browser-local datetime-local value. */
export function toLocalDatetime(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : `${datePart(date)}T${timePart(date)}`;
}

/** Calendar dates are compared without rounding their time-of-day difference. */
export function getExpiryDays(datetimeStr, now = new Date()) {
  if (!datetimeStr) return DEFAULT_EXPIRY_DAYS;
  const expiry = new Date(datetimeStr);
  if (Number.isNaN(expiry.getTime())) return DEFAULT_EXPIRY_DAYS;
  return Math.max(1, calendarDay(expiry) - calendarDay(now));
}

/** Only a user edit of Days writes a new expiry; reading never changes it. */
export function expiryFromDays(days, currentExpiry, now = new Date()) {
  const safeDays = Number.isInteger(days) && days > 0 ? days : DEFAULT_EXPIRY_DAYS;
  // Noon avoids crossing daylight-saving transitions while adding dates.
  const expiry = new Date(now.getFullYear(), now.getMonth(), now.getDate() + safeDays, 12);
  const current = new Date(currentExpiry);
  const time = currentExpiry && !Number.isNaN(current.getTime())
    ? timePart(current)
    : timePart(now);
  return `${datePart(expiry)}T${time}`;
}
