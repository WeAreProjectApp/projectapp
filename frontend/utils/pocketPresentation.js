import { formatMoney } from './formatMoney';

export function pocketAttributionLabel(ledger, t) {
  const key = ['company', 'gustavo', 'carlos'].includes(ledger) ? ledger : 'unlinked';
  return t(`accountingPocket.${key}`);
}

export function signedPocketAmount(row) {
  return `${row?.direction === 'out' ? '-' : ''}${formatMoney(row?.amount)}`;
}
