"""Preview and confirm the next expected income against the same contract calendar."""
from datetime import timedelta

from django.db import transaction

from accounts.services.billing_locks import lock_billing_rows
from content.models import HostingIncomePeriod, HostingRecord, RecurringPayment
from content.services.accounting_expected_income_service import apply_create
from content.services.entity_history import historical_write
from content.services.hosting_periods import HostingPeriods, PeriodConflict, STALE, fingerprint
from content.utils import add_months


def next_income_plan(record, *, reference_income_id=None):
    book = HostingPeriods(record.project_id, record_id=record.pk)
    book.require_active_service()
    current = book.reference_window(reference_income_id)
    modality = record.payment_modality
    months = HostingRecord.MODALITY_MONTHS.get(modality)
    if not months:
        raise PeriodConflict('Completa la periodicidad del servicio antes de preparar el ingreso.')
    if not record.payment_per_cycle or record.payment_per_cycle <= 0:
        raise PeriodConflict('Configura la tarifa por ciclo del hosting antes de preparar el ingreso.')
    start = current.end + timedelta(days=1)
    # Preserve the contractual day after a clamped short month (e.g. Jan 31).
    anchor = book.hosting.subscription.start_date if book.hosting.subscription_id else (record.valid_from or current.start)
    month_offset = (start.year - anchor.year) * 12 + start.month - anchor.month
    documented = next((w for w in book.windows.values() if w.start == start), None)
    if documented:
        if documented.conflict:
            raise PeriodConflict(documented.conflict)
        if not documented.income and (documented.state in ('paid', 'processing', 'failed') or documented.documents):
            raise PeriodConflict('El siguiente período ya tiene un pago o documento. Concilia antes de crear el ingreso.')
        end = documented.end
    else:
        subscription = book.hosting.subscription
        cadence_disagrees = subscription and HostingRecord.MODALITY_MONTHS.get(subscription.plan) != months
        if cadence_disagrees or month_offset < 0 or month_offset % months or add_months(anchor, month_offset) != start:
            raise PeriodConflict('Concilia el fin del período actual con el calendario contractual.')
        end = add_months(anchor, month_offset + months) - timedelta(days=1)
    overlaps = [w for w in book.windows.values() if w.start <= end and w.end >= start and w is not documented]
    if overlaps or any(i.period_start <= end and i.period_end >= start for i in book.unlinked_incomes):
        raise PeriodConflict('Ya existe una ventana que se solapa. Concilia el ingreso antes de crear otro.')
    amount = documented.total if documented else record.payment_per_cycle
    if not record.is_active or not amount or amount <= 0:
        raise PeriodConflict('Revisa la vigencia del servicio y su tarifa antes de crear el ingreso.')
    fields = {
        'concept': f'Hosting {record.domain_url or record.project.name}', 'total_amount': str(amount),
        'vat_rate': record.vat_rate, 'origin': 'hosting', 'client': record.client_id,
        'project': record.project_id, 'period_date': start, 'period_start': start, 'period_end': end,
        'period_cadence': modality if modality in RecurringPayment.FREQUENCY_MONTHS else 'custom',
    }
    contract = {'hosting_record_id': record.pk, 'project_hosting_id': book.hosting.pk,
                'client_name': record.client_name, 'project_name': record.project.name,
                'service': record.domain_url or record.project.name, 'reference_start': current.start,
                'reference_end': current.end, 'fields': fields}
    return {**contract, 'version': fingerprint(contract),
            'existing_income_id': documented.income.pk if documented and documented.income else None}


@historical_write
@transaction.atomic
def confirm_next_income(record_id, data, *, actor):
    record = lock_billing_rows(hosting_ids=[record_id]).hostings[record_id]
    plan = next_income_plan(record, reference_income_id=data.get('reference_income_id'))
    if plan['version'] != data['version']:
        raise PeriodConflict(STALE)
    if plan['existing_income_id']:
        return plan, False
    income = apply_create(plan['fields'], actor=actor)
    HostingIncomePeriod.objects.create(hosting_id=plan['project_hosting_id'], income=income,
                                       start=income.period_start, end=income.period_end)
    return {**plan, 'existing_income_id': income.pk}, True
