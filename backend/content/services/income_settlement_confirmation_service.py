"""Per-income client confirmations, with one common financial operation."""
from content.services import income_payment_confirmation_service as confirmations


def confirm_operation(result, data, *, schedule=False):
    if result.get('replayed'):
        return []
    selected = data.get('confirmation_income_ids')
    results = []
    for income in result['incomes']:
        liquid = next((row for row in result['liquids'] if row.expected_income_id == income.pk), None)
        requested = bool(data.get('send_payment_confirmation')) and (selected is None or income.pk in selected)
        method = confirmations.schedule_confirmation if schedule else confirmations.confirm_settlement
        confirmation = method({'income': income, 'liquid': liquid}, {**data, 'send_payment_confirmation': requested})
        results.append({'income_id': income.pk, **confirmation})
    return results
