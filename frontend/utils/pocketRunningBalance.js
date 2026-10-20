/**
 * Running balance of the pocket ledger.
 *
 * Pure on purpose: the page accumulates over the rows the filters LEFT, so the
 * Saldo column always adds up to what is on screen. Over the unfiltered set it
 * returns exactly what the old `pocketWithRunningBalance` store getter did.
 *
 * Chronological by `movement_date`, ties broken by `created_at`: two movements
 * dated the same day only have an order because one was written first.
 */
export function withRunningBalance(movements) {
  const sorted = [...movements].sort((a, b) => (
    a.movement_date === b.movement_date
      ? (String(a.created_at).localeCompare(String(b.created_at)) || Number(a.id) - Number(b.id))
      : String(a.movement_date).localeCompare(String(b.movement_date))
  ));
  let running = 0;
  return sorted.map((movement) => {
    const amount = Number(movement.amount) || 0;
    running += movement.direction === 'in' ? amount : -amount;
    return { ...movement, running_balance: running };
  });
}
