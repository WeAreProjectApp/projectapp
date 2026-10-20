"""Pure, cent-exact proposals shared by settlement preview and persistence."""
from decimal import Decimal, ROUND_DOWN

CENT = Decimal('0.01')
ZERO = Decimal('0.00')


def money(value):
    return Decimal(str(value or 0)).quantize(CENT)


def apportion(amount, weights, capacities=None):
    """Largest remainders with stable input-order ties and optional row caps.

    Work in cents, so distributing partner columns or deduction lines never
    manufactures money. Capped rows leave the remaining amount to other rows.
    """
    amount = money(amount)
    weights = [money(value) for value in weights]
    caps = [money(value) for value in capacities] if capacities is not None else [amount] * len(weights)
    result = [ZERO] * len(weights)
    remaining = amount
    while remaining > 0:
        active = [i for i, weight in enumerate(weights) if weight > 0 and caps[i] > result[i]]
        if not active or sum((caps[i] - result[i] for i in active), ZERO) < remaining:
            raise ValueError('El reparto supera el saldo disponible. Recalcula la distribución.')
        total_weight = sum((weights[i] for i in active), ZERO)
        quotas = {i: remaining * weights[i] / total_weight for i in active}
        rounded = {i: min(quotas[i].quantize(CENT, rounding=ROUND_DOWN), caps[i] - result[i]) for i in active}
        for i, value in rounded.items():
            result[i] += value
            remaining -= value
        if remaining <= 0:
            break
        # At most one cent per row on a pass; if a cap was hit, the next
        # pass recomputes the quota over only the rows with room.
        for i in sorted(active, key=lambda i: (-(quotas[i] - rounded[i]), i)):
            if remaining > 0 and caps[i] - result[i] >= CENT:
                result[i] += CENT
                remaining -= CENT
    return result


def oldest_first(pendings, amount):
    remaining = money(amount)
    result = []
    for pending in pendings:
        value = min(money(pending), remaining)
        result.append(value)
        remaining -= value
    return result


def allocation_plan(parents, pendings, data):
    """Rows ordered by expected date/id, each conserving its open balance."""
    received = money(data['total_amount'])
    deduction_lines = data.get('deductions') or []
    deducted = sum((money(line['amount']) for line in deduction_lines), ZERO)
    pending_values = [money(pendings[parent.pk]) for parent in parents]
    explicit = data.get('allocations')
    if explicit is not None:
        amounts = {entry['income_id']: money(entry['amount']) for entry in explicit}
        cash = [amounts.get(parent.pk, ZERO) for parent in parents]
        if sum(cash, ZERO) > received:
            raise ValueError('La suma de la distribución no puede superar el monto recibido.')
        weights = cash
        if deducted and not sum(weights, ZERO):
            weights = oldest_first(pending_values, deducted)
        deduction_totals = apportion(deducted, weights) if deducted else [ZERO] * len(parents)
    else:
        coverage = oldest_first(pending_values, min(received + deducted, sum(pending_values, ZERO)))
        if deducted > sum(coverage, ZERO):
            raise ValueError('Las deducciones superan el saldo pendiente.')
        deduction_totals = apportion(deducted, coverage) if deducted else [ZERO] * len(parents)
        cash = [gross - fee for gross, fee in zip(coverage, deduction_totals)]

    rows = []
    available_deductions = list(deduction_totals)
    portions = [[] for _ in parents]
    for line in deduction_lines:
        values = apportion(line['amount'], available_deductions, available_deductions)
        for index, value in enumerate(values):
            available_deductions[index] -= value
            if value:
                portions[index].append({**line, 'amount': value})
    for index, parent in enumerate(parents):
        follow_ups = [entry for entry in data.get('expected_incomes', []) if entry['income_id'] == parent.pk]
        reexpected = sum((money(entry['amount']) for entry in follow_ups), ZERO)
        remaining = pending_values[index] - cash[index] - deduction_totals[index] - reexpected
        if remaining < 0:
            raise ValueError(
                f'La imputación a "{parent.concept}" supera su saldo pendiente '
                f'(${pending_values[index]:,.2f}). Recalcula el reparto o revisa los ajustes.'
            )
        rows.append({
            'income_id': parent.pk, 'amount': cash[index],
            'deductions': portions[index], 'deducted': deduction_totals[index],
            'expected_incomes': follow_ups, 'reexpected': reexpected,
            'pending_before': pending_values[index], 'pending_after': remaining,
        })
    credit = received - sum(cash, ZERO)
    if credit > 0 and len({parent.client_id for parent in parents}) > 1:
        raise ValueError('Con clientes mezclados el excedente no se puede asignar como saldo a favor: ajusta el valor.')

    ledger = parents[0].ledger
    gustavo = money(data.get('gustavo_amount', (received / 2).to_integral_value(rounding=ROUND_DOWN)))
    carlos = money(data.get('carlos_amount', (received / 2).to_integral_value(rounding=ROUND_DOWN)))
    if ledger != 'company':
        gustavo = received if ledger == 'gustavo' else ZERO
        carlos = received if ledger == 'carlos' else ZERO
    if gustavo < 0 or carlos < 0 or gustavo + carlos > received:
        raise ValueError('La suma de los montos de los socios no puede superar el monto total.')
    liquid_amounts = [*cash, credit]
    gustavo_parts = apportion(gustavo, liquid_amounts, liquid_amounts) if gustavo else [ZERO] * len(liquid_amounts)
    capacities = [value - part for value, part in zip(liquid_amounts, gustavo_parts)]
    carlos_parts = apportion(carlos, liquid_amounts, capacities) if carlos else [ZERO] * len(liquid_amounts)
    for index, row in enumerate(rows):
        row.update(gustavo_amount=gustavo_parts[index], carlos_amount=carlos_parts[index])
    return {
        'rows': rows, 'total_amount': received, 'deducted': deducted,
        'credit_amount': credit, 'gustavo_amount': gustavo, 'carlos_amount': carlos,
        'credit_gustavo': gustavo_parts[-1], 'credit_carlos': carlos_parts[-1],
        'pending_before': sum(pending_values, ZERO),
        'pending_after': sum((row['pending_after'] for row in rows), ZERO),
    }
