"""One evidence-based reading of a project's hosting periods for both accounting screens."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q

from accounts.models import HostingEvidence, HostingSubscription, Payment, ProjectHosting
from content.models import Document, HostingCycle, HostingIncomePeriod, HostingRecord, IncomeRecord
from content.utils import today_bogota


class PeriodConflict(ValueError):
    pass


EMPTY_PERIOD = 'No hay un período pendiente acreditado. Revisa los ingresos, pagos y ciclos del servicio.'
MISSING_OWNER = 'Completa el cliente y el proyecto y concilia el origen operativo del hosting.'
UNLINKED_CASH = 'Selecciona el pago ya registrado y concilia las evidencias del ciclo antes de acreditar dinero.'
AMBIGUOUS = 'Las evidencias del período discrepan. Revisa las fechas, los importes y los vínculos en Conciliar hosting.'
STALE = 'El período cambió desde la revisión. Actualiza los datos antes de confirmar.'


def fingerprint(data):
    encoded = json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True).encode()
    return sha256(encoded).hexdigest()


@dataclass
class Window:
    start: date
    end: date
    payment: Payment | None = None
    income: IncomeRecord | None = None
    cycles: list = field(default_factory=list)
    documents: list = field(default_factory=list)
    conflict: str = ''

    @property
    def total(self):
        if self.payment:
            return self.payment.amount
        return self.income.total_amount if self.income else Decimal('0')

    @property
    def liquids(self):
        return list(self.income.liquid_records.all()) if self.income else []

    @property
    def deductions(self):
        return sum((row.total_amount for row in self.income.deduction_records.all() if row.deduction_type), Decimal('0')) if self.income else Decimal('0')

    @property
    def received(self):
        # Linked cycles and liquid children describe the very same allocation.
        cash = sum((row.total_amount for row in self.liquids if row.kind == 'liquid'), Decimal('0'))
        cycles = sum((cycle.amount for cycle in self.cycles if not hasattr(cycle, 'receipt_allocation')), Decimal('0'))
        if self.payment and self.payment.status == 'paid' and not self.liquids:
            return self.total
        return cash + cycles

    @property
    def balance(self):
        return max(Decimal('0'), self.total - self.received - self.deductions)

    @property
    def state(self):
        if self.conflict:
            return 'conflict'
        if self.payment and self.payment.status in ('processing', 'failed'):
            return self.payment.status
        if not self.balance:
            return 'paid'
        if self.received or self.deductions:
            return 'partial'
        return self.payment.status if self.payment else 'pending'

    def summary(self, book, *, paid_allocation=None):
        documents = self.documents
        if paid_allocation:
            # A paid account documenting a different partial receipt covers only its own cash.
            documents = [doc for doc in documents if not (
                doc.commercial_status == 'paid' and doc.income_record_id != paid_allocation.liquid_id
                and getattr(doc.income_record, 'hosting_allocation', None)
            )]
        source = 'subscription' if self.payment else 'expected_income'
        result = {
            'project_id': book.hosting.project_id, 'project_hosting_id': book.hosting.pk,
            'hosting_record_id': book.record.pk if book.record else None,
            'client_id': book.client_id, 'source': source,
            'hosting_payment_id': self.payment.pk if self.payment else None,
            'income_id': self.income.pk if self.income else None,
            'cycle_ids': [cycle.pk for cycle in self.cycles],
            'period_start': self.start.isoformat(), 'period_end': self.end.isoformat(),
            'currency': 'COP', 'amount': str(self.total), 'received': str(self.received),
            'balance': str(self.balance), 'state': self.state,
            'documents': [{'id': doc.pk, 'number': doc.public_number or '', 'state': doc.commercial_status}
                          for doc in documents],
            'blocker': self.conflict,
        }
        if not result['blocker']:
            if documents:
                result['blocker'] = 'El período ya tiene cuenta. Consulta su referencia antes de enviar otra.'
            elif self.state not in ('pending', 'overdue', 'partial'):
                result['blocker'] = 'El período está cubierto o su cobro requiere conciliación.'
        # Linking the draft to its obligation increments the global hosting revision.
        # Only the service and economic facts presented to the operator version this review.
        result['version'] = fingerprint([
            result, book.hosting.subscription_id, self.income.vat_rate if self.income else None,
            book.record.vat_rate if book.record else None,
            [(row.pk, row.total_amount, row.period_date) for row in self.liquids],
        ])
        return result


class HostingPeriods:
    """Dates index obligations; they never identify two receipts as the same money."""

    def __init__(self, project_id, *, record_id=None, exclude_document_id=None):
        self.exclude_document_id = exclude_document_id
        self.hosting = ProjectHosting.objects.select_related(
            'project', 'project__client__profile', 'subscription',
            'operational_accounting_source__hosting_record__client',
        ).filter(project_id=project_id, project_id__isnull=False).first()
        if not self.hosting:
            raise PeriodConflict(MISSING_OWNER)
        source = self.hosting.operational_accounting_source
        self.record = source.hosting_record if source else None
        if record_id and (not self.record or self.record.pk != record_id):
            raise PeriodConflict(MISSING_OWNER)
        if self.record and (source.hosting_id != self.hosting.pk or self.record.project_id != project_id
                            or not self.record.client_id or self.record.client.user_id != self.hosting.project.client_id):
            raise PeriodConflict(MISSING_OWNER)
        profile = getattr(self.hosting.project.client, 'profile', None)
        if not profile:
            raise PeriodConflict(MISSING_OWNER)
        self.client_id = profile.pk
        if self.hosting.subscription_id and self.hosting.subscription.project_id != project_id:
            raise PeriodConflict(MISSING_OWNER)
        if HostingSubscription.objects.filter(project_id=project_id).exclude(pk=self.hosting.subscription_id).exists():
            raise PeriodConflict('Concilia la suscripción pendiente de asociar al proyecto.')
        records = HostingRecord.objects.filter(project_id=project_id)
        if records.exclude(billing_source__hosting=self.hosting).exists() or (not source and records.exists()):
            raise PeriodConflict('Hay orígenes contables pendientes de asociar. Concilia el hosting operativo.')
        self.unassigned_cash = False
        self.windows = {}
        self.unlinked_incomes = []
        self._read_obligations()
        self._read_evidence()
        self._check_overlaps()

    def _window(self, start, end):
        if not start or not end or start > end:
            raise PeriodConflict('El calendario del servicio requiere una ventana con inicio y fin válidos.')
        return self.windows.setdefault((start, end), Window(start, end))

    def _read_obligations(self):
        for payment in Payment.objects.filter(subscription_id=self.hosting.subscription_id, is_archived=False).exclude(status='voided'):
            window = self._window(payment.billing_period_start, payment.billing_period_end)
            if window.payment:
                window.conflict = AMBIGUOUS
            window.payment = payment
        incomes = IncomeRecord.objects.select_related('hosting_period').prefetch_related(
            'liquid_records__hosting_allocation__receipt', 'deduction_records',
        ).filter(
            Q(hosting_period__hosting=self.hosting)
            | Q(project_id=self.hosting.project_id, client_id=self.client_id, origin='hosting', kind='expected', ledger='company'),
        ).order_by('pk')
        document_income_ids = set(Document.objects.filter(
            billing_context__hosting=self.hosting, income_record_id__isnull=False,
        ).values_list('income_record_id', flat=True))
        sole_service = self.record and not self.hosting.accounting_sources.exclude(hosting_record=self.record).exists()
        for income in incomes:
            link = getattr(income, 'hosting_period', None)
            if link and (link.hosting_id != self.hosting.pk or income.project_id != self.hosting.project_id
                         or income.client_id != self.client_id or income.origin != 'hosting' or income.kind != 'expected'
                         or (link.start, link.end) != (income.period_start, income.period_end)):
                raise PeriodConflict('El esperado vinculado cambió de servicio, estado o fechas. Revisa la conciliación.')
            if not income.period_start or not income.period_end:
                if any(row.kind == 'liquid' for row in income.liquid_records.all()):
                    self.unassigned_cash = True
                continue
            key = income.period_start, income.period_end
            if not link and income.pk not in document_income_ids and not (sole_service and key in self.windows):
                self.unlinked_incomes.append(income)
                continue
            window = self._window(*key)
            if window.income or (window.payment and window.payment.amount != income.total_amount):
                window.conflict = AMBIGUOUS
            window.income = income

    def _read_evidence(self):
        # An administrative group may explicitly reconcile differing historical dates.
        group_dates = {}
        for pair in HostingEvidence.objects.filter(group__hosting=self.hosting, payment__isnull=False).values_list(
            'group_id', 'payment__billing_period_start', 'payment__billing_period_end',
        ):
            group, start, end = pair
            if group in group_dates and group_dates[group] != (start, end):
                raise PeriodConflict('Un grupo de evidencias comprende varias obligaciones. Revisa la conciliación.')
            group_dates[group] = (start, end)
        cycles = HostingCycle.objects.filter(hosting_record__billing_source__hosting=self.hosting).select_related(
            'receipt_allocation__period', 'receipt_allocation__receipt', 'billing_evidence',
        ).order_by('pk')
        self.cycles = list(cycles)
        for cycle in self.cycles:
            allocation = getattr(cycle, 'receipt_allocation', None)
            evidence = getattr(cycle, 'billing_evidence', None)
            key = group_dates.get(evidence.group_id) if evidence else None
            if allocation:
                key = allocation.period.start, allocation.period.end
            window = self.windows.get(key or (cycle.period_from, cycle.period_to))
            if window:
                window.cycles.append(cycle)
                if cycle.cycles_represented != 1:
                    window.conflict = AMBIGUOUS
                elif not allocation and not key and window.payment and window.payment.status != 'paid':
                    window.conflict = window.conflict or UNLINKED_CASH
            elif not key:
                for candidate in self.windows.values():
                    if (not cycle.period_from or not cycle.period_to or
                            (cycle.period_from <= candidate.end and cycle.period_to >= candidate.start)):
                        candidate.conflict = AMBIGUOUS
        incomes = [i.pk for window in self.windows.values() if window.income for i in [window.income, *window.liquids]]
        documents = Document.objects.filter(
            Q(billing_context__hosting=self.hosting) | Q(hosting_record__billing_source__hosting=self.hosting)
            | Q(income_record_id__in=incomes),
            document_type__code='collection_account',
        ).exclude(pk=self.exclude_document_id).exclude(commercial_status='cancelled').select_related('hosting_evidence', 'income_record__hosting_allocation').prefetch_related('items').order_by('pk')
        for doc in documents:
            evidence = getattr(doc, 'hosting_evidence', None)
            key = group_dates.get(evidence.group_id) if evidence else None
            dates = {(item.period_start, item.period_end) for item in doc.items.all() if item.period_start and item.period_end}
            if key:
                dates.add(key)
            if not dates:
                dates = {k for k, w in self.windows.items() if w.income and doc.income_record_id in {w.income.pk, *(i.pk for i in w.liquids)}}
            if not dates:
                raise PeriodConflict(f'Concilia el período de la cuenta #{doc.pk} antes de emitir otra.')
            for window in self.windows.values():
                linked_income = window.income and doc.income_record_id in {window.income.pk, *(row.pk for row in window.liquids)}
                exact = (window.start, window.end) in dates
                overlap = any(start <= window.end and end >= window.start for start, end in dates)
                if exact or linked_income or overlap:
                    window.documents.append(doc)
                    if not exact or len(dates) > 1:
                        window.conflict = AMBIGUOUS

    def _check_overlaps(self):
        ordered = sorted(self.windows.values(), key=lambda w: w.start)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.end >= current.start:
                previous.conflict = current.conflict = AMBIGUOUS
        for w in ordered:
            if self.unassigned_cash:
                w.conflict = AMBIGUOUS
            if w.income and w.cycles and any(not hasattr(c, 'receipt_allocation') for c in w.cycles) and w.liquids:
                w.conflict = w.conflict or UNLINKED_CASH
            if w.payment and w.payment.status == 'paid' and w.income and w.liquids:
                if sum((row.total_amount for row in w.liquids), Decimal('0')) + w.deductions != w.total:
                    w.conflict = AMBIGUOUS
            if w.total <= 0 or w.received + w.deductions > w.total:
                w.conflict = w.conflict or AMBIGUOUS
            if any(i.period_start <= w.end and i.period_end >= w.start for i in self.unlinked_incomes):
                w.conflict = AMBIGUOUS

    def require_active_service(self):
        subscription = self.hosting.subscription
        if subscription and (subscription.is_archived or subscription.status == 'cancelled'):
            raise PeriodConflict('La suscripción está archivada o cancelada. Revisa el servicio antes de continuar.')
        if self.record and not self.record.is_active:
            raise PeriodConflict('El servicio de hosting está inactivo. Revisa su estado antes de emitir.')

    def current(self):
        self.require_active_service()
        windows = sorted(self.windows.values(), key=lambda w: w.start, reverse=True)
        for w in windows:
            if w.conflict:
                raise PeriodConflict(w.conflict)
        for w in windows:
            if w.start <= today_bogota() and w.state != 'paid':
                return w
        raise PeriodConflict(EMPTY_PERIOD)

    def for_income(self, income):
        window = self.windows.get((income.period_start, income.period_end))
        if not window or not window.income or window.income.pk != income.pk:
            raise PeriodConflict('Concilia el ingreso esperado con el período del mismo servicio.')
        return window

    def settlement_window(self, income):
        # The operator names an existing expected income and the operating service.
        # A project with multiple accounting sources requires an explicit prior link.
        if self.unassigned_cash:
            raise PeriodConflict(AMBIGUOUS)
        if (not self.hosting.subscription_id and self.record and
                not self.hosting.accounting_sources.exclude(hosting_record=self.record).exists() and
                any(i.pk == income.pk for i in self.unlinked_incomes)):
            start, end = income.period_start, income.period_end
            others = [i for i in self.unlinked_incomes if i.pk != income.pk and i.period_start <= end and i.period_end >= start]
            if others or any(w.start <= end and w.end >= start for w in self.windows.values()):
                raise PeriodConflict(AMBIGUOUS)
            window = Window(start, end, income=next(i for i in self.unlinked_incomes if i.pk == income.pk))
            for cycle in self.cycles:
                if (cycle.period_from, cycle.period_to) == (start, end) and cycle.cycles_represented == 1:
                    window.cycles.append(cycle)
                elif not cycle.period_from or not cycle.period_to or (cycle.period_from <= end and cycle.period_to >= start):
                    raise PeriodConflict(AMBIGUOUS)
            return window
        return self.for_income(income)

    def reference_window(self, income_id=None):
        if income_id:
            window = next((w for w in self.windows.values() if w.income and w.income.pk == income_id), None)
        else:
            # A forecast created here does not move the reference calendar forward
            # on a second confirmation or when reopening a late payment.
            candidates = [w for w in self.windows.values() if w.start <= today_bogota()]
            anchored = [w for w in candidates if w.payment or w.cycles or w.liquids or w.documents]
            window = max(anchored, key=lambda w: w.start, default=None)
            if not window:
                window = min(candidates, key=lambda w: w.start, default=None)
        if not window or window.conflict:
            raise PeriodConflict(window.conflict if window else EMPTY_PERIOD)
        return window


def current_summary(project_id):
    try:
        book = HostingPeriods(project_id)
        return book.current().summary(book)
    except PeriodConflict as exc:
        return {'blocker': str(exc), 'state': 'blocked'}


def reviewed_period(book, data, *, paid_allocation=None):
    if paid_allocation:
        period = paid_allocation.period
        if period.hosting_id != book.hosting.pk:
            raise PeriodConflict(MISSING_OWNER)
        window = book.for_income(period.income)
    else:
        window = book.current()
    summary = window.summary(book, paid_allocation=paid_allocation)
    if window.conflict or summary['documents'] or (not paid_allocation and summary['blocker']):
        raise PeriodConflict(summary['blocker'])
    if data.get('period_version') != summary['version']:
        raise PeriodConflict(STALE)
    if data.get('hosting_payment_id') != summary['hosting_payment_id']:
        raise PeriodConflict('La obligación revisada cambió. Consulta de nuevo el período.')
    return window


def validate_reviewed_document(document, review):
    """Re-read the original obligation before issuing an editable/reviewed draft."""
    from content.models import HostingReceiptAllocation

    book = HostingPeriods(document.project_id, record_id=document.hosting_record_id, exclude_document_id=document.pk)
    allocation = None
    if review.get('receipt_allocation_id'):
        allocation = HostingReceiptAllocation.objects.select_related('period__income', 'liquid').filter(
            pk=review['receipt_allocation_id'], liquid_id=document.income_record_id, period__hosting=book.hosting,
        ).first()
        if not allocation:
            raise PeriodConflict(MISSING_OWNER)
    window = reviewed_period(book, review, paid_allocation=allocation)
    lines = list(document.items.all())
    amount = allocation.liquid.total_amount if allocation else window.balance
    if (not lines or document.currency != 'COP' or any(
            (item.period_start, item.period_end) != (window.start, window.end) for item in lines)
            or sum((item.line_total for item in lines), Decimal('0')) != amount):
        raise PeriodConflict(STALE)
