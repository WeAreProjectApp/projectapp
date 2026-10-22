"""VAT drafts for settlements; preview never changes the source income."""
from decimal import Decimal

from content.models import Document, ExpenseRecord, IncomeRecord
from content.services.accounting_vat import vat_breakdown

ISSUED_REASON = 'Anula la cuenta emitida antes de cambiar el importe o el IVA del ingreso.'
PAID_REASON = 'El IVA no puede cambiar después de registrar pagos o deducciones.'


def vat_editability(parents):
    """Read the existing financial guards in three queries, even for a group."""
    ids = [parent.pk for parent in parents]
    issued = set(Document.objects.filter(income_record_id__in=ids).exclude(
        commercial_status__in=('draft', 'cancelled'),
    ).values_list('income_record_id', flat=True))
    paid = set(IncomeRecord.objects.filter(expected_income_id__in=ids).values_list('expected_income_id', flat=True))
    deducted = set(ExpenseRecord.objects.filter(source_income_id__in=ids).values_list('source_income_id', flat=True))
    return {pk: ISSUED_REASON if pk in issued else PAID_REASON if pk in paid or pk in deducted else '' for pk in ids}


def settlement_vat(parents, data, rows):
    """Validate changes and captured amounts against the actual cash allocation."""
    reasons = vat_editability(parents)
    parents_by_id = {parent.pk: parent for parent in parents}
    rows_by_id = {row['income_id']: row for row in rows}
    updates = data.get('vat_updates', [])
    ids = [entry['income_id'] for entry in updates]
    if len(ids) != len(set(ids)) or set(ids) - parents_by_id.keys():
        raise ValueError('Indica un solo IVA por ingreso seleccionado.')
    effective = {parent.pk: parent.vat_rate for parent in parents}
    for entry in updates:
        pk = entry['income_id']
        rate = entry['vat_rate']
        # Service callers and MCP share the same monetary validation as REST.
        vat_breakdown(Decimal('0'), rate)
        if rate != parents_by_id[pk].vat_rate and reasons[pk]:
            raise ValueError(f'{parents_by_id[pk].concept}: {reasons[pk]}')
        effective[pk] = rate
        if 'amount_mode' in entry and 'amount' not in entry:
            raise ValueError('Escribe el importe para el modo de IVA seleccionado.')
        if 'amount' in entry:
            total = vat_breakdown(entry['amount'], rate, entry.get('amount_mode', 'vat_included'))[2]
            if total != rows_by_id[pk]['amount']:
                raise ValueError(f'El importe con IVA de "{parents_by_id[pk].concept}" no coincide con su dinero imputado.')
    return effective, reasons
