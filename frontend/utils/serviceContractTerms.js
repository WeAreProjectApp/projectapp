// The template is Spanish; UI translations must never translate contract values.
const SMALL = ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete', 'dieciocho', 'diecinueve', 'veinte', 'veintiuno', 'veintidós', 'veintitrés', 'veinticuatro', 'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho', 'veintinueve'];
const TENS = ['', '', '', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta', 'ochenta', 'noventa'];
const HUNDREDS = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 'quinientos', 'seiscientos', 'setecientos', 'ochocientos', 'novecientos'];

export function serviceTermNumber(value) {
  if (typeof value !== 'number' && (typeof value !== 'string' || !/^\d+$/.test(value))) return null;
  const number = Number(value);
  return Number.isInteger(number) && number >= 1 && number <= 999 ? number : null;
}

function words(number) {
  if (number < 30) return SMALL[number];
  if (number < 100) return TENS[Math.floor(number / 10)] + (number % 10 ? ` y ${SMALL[number % 10]}` : '');
  if (number === 100) return 'cien';
  return HUNDREDS[Math.floor(number / 100)] + (number % 100 ? ` ${words(number % 100)}` : '');
}

export function formatServiceTerm(value, duration = false) {
  const number = serviceTermNumber(value);
  if (number === null) return '';
  const text = words(number).replace(/veintiuno$/, 'veintiún').replace(/uno$/, 'un');
  return `${text} (${number})${duration ? (number === 1 ? ' mes' : ' meses') : ''}`;
}

export function savedServiceTermNumber(value, duration = false) {
  if (typeof value === 'number') return serviceTermNumber(value);
  if (typeof value !== 'string') return null;
  const match = value.match(/\((\d{1,3})\)/);
  const number = match ? serviceTermNumber(match[1]) : null;
  return number !== null && formatServiceTerm(number, duration) === value ? number : null;
}

export function validServiceContractSettings(settings) {
  if (!settings) return false;
  const validList = list => Array.isArray(list) && list.length > 0
    && list.every(n => typeof n === 'number' && serviceTermNumber(n) !== null)
    && new Set(list).size === list.length;
  return validList(settings.duration_options) && validList(settings.notice_options)
    && settings.duration_options.includes(settings.default_duration)
    && settings.notice_options.includes(settings.default_renewal_notice)
    && settings.notice_options.includes(settings.default_termination_notice);
}
