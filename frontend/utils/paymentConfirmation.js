// What the Liquidar modal tells before the client's payment confirmation
// leaves, and what the page tells after: the same facts the backend email
// states (content/services/income_payment_confirmation_service.py).
import { formatDate } from '~/utils/formatDate';
import { historySendsLink } from '~/utils/historyDeepLink';

const MONTH_NAMES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

/**
 * 'Jue, 16 jul 2026', or 'julio de 2026' when only the month is known.
 * A 'YYYY-MM' value never reaches formatDate: parsed as a Date it lands on
 * the last day of the previous month in Bogotá.
 */
export function formatPaymentDate(value, exact) {
  if (!value) return '';
  if (exact) return formatDate(value);
  const [year, month] = String(value).split('-');
  const name = MONTH_NAMES[Number(month) - 1];
  return name ? `${name} de ${year}` : String(value);
}

/**
 * What the client still owes once this payment lands. Received money and
 * deductions reduce it; follow-ups only move part of it into another
 * expected income, so `rescheduled` (follow-ups still open from earlier
 * settlements) is still owed too.
 */
export function clientPendingAfter({ pending, received, deductions, rescheduled }) {
  const left = Math.max(
    Number(pending || 0) - Number(received || 0) - Number(deductions || 0),
    0,
  );
  return Math.round((left + Number(rescheduled || 0)) * 100) / 100;
}

/** Detail line for the success toast, or '' when nothing went out. */
export function paymentConfirmationDetail(block) {
  if (block?.status !== 'sent') return '';
  return `Confirmación de pago enviada a ${block.recipient}.`;
}

/**
 * Warning toast for a confirmation that was asked for and did not go out,
 * or null. The settlement stands either way, so this never reads as an
 * error; a failed send points at the history, where it can be retried.
 */
export function paymentConfirmationWarning(block, incomeId) {
  if (!block?.requested) return null;
  if (block.status === 'failed') {
    return {
      title: 'La confirmación de pago no salió',
      detail: block.error || 'El correo no salió.',
      action: {
        label: 'Ver correos de este ingreso',
        to: historySendsLink('income', incomeId),
      },
    };
  }
  if (block.status === 'skipped') {
    return {
      title: 'No se envió la confirmación de pago',
      detail: block.error || '',
    };
  }
  return null;
}
