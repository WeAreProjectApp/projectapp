"""Serializers for the accounting module (panel, superuser-only).

Write serializers apply the default 50/50 partner split when neither
partner amount is supplied on create, and accept month periods as
"YYYY-MM" (normalized to the first day of the month).
"""
import re
from decimal import Decimal, ROUND_DOWN

from django.db.models import Max, Sum
from rest_framework import serializers

from accounts.models import Project, UserProfile
from content.utils import SPANISH_MONTHS, format_bogota_date, today_bogota
from content.models import (
    AccountingChangeLog,
    AccountingSettings,
    AdsSpendRecord,
    CardBalanceSnapshot,
    CreditCard,
    Document,
    EmailLog,
    EmailLogTarget,
    ExpenseRecord,
    HostingCycle,
    HostingRecord,
    IncomeRecord,
    Ledger,
    NotificationRecipient,
    PocketMovement,
    RecurringCategory,
    RecurringPayment,
)

from content.serializers.accounting_vat import VatReadMixin, VatWriteMixin

PERSONAL_LEDGER_OWNER = {
    Ledger.GUSTAVO: ('gustavo_amount', 'carlos_amount'),
    Ledger.CARLOS: ('carlos_amount', 'gustavo_amount'),
}

MONTH_PERIOD_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')

TWO_PLACES = Decimal('0.01')


def money_str(value):
    """Canonical API money string: two decimal places, no separators."""
    return str(Decimal(value).quantize(TWO_PLACES))


def month_period(date_value):
    """Return the 'YYYY-MM' representation of a date."""
    return date_value.strftime('%Y-%m') if date_value else None


def month_label(date_value):
    """Return the Spanish 'Mes YYYY' label of a date.

    A day other than 1 marks an exact payment date (see
    FlexiblePeriodField) and is included: '17 Julio 2026'.
    """
    if not date_value:
        return ''
    month_year = f'{SPANISH_MONTHS[date_value.month].capitalize()} {date_value.year}'
    if date_value.day != 1:
        return f'{date_value.day} {month_year}'
    return month_year


def split_half(total):
    """50/50 split in whole pesos; the odd peso and any cent stay with ProjectApp.

    Same rule as the panel's PartnerSplitInput, so a record saved without a
    split matches the one the operator sees on screen.
    """
    half = (total / 2).to_integral_value(rounding=ROUND_DOWN).quantize(TWO_PLACES)
    return half, half


class MonthPeriodField(serializers.DateField):
    """DateField accepting 'YYYY-MM' too; always normalized to day 1."""

    def to_internal_value(self, value):
        if isinstance(value, str) and MONTH_PERIOD_RE.match(value.strip()):
            value = f'{value.strip()}-01'
        date_value = super().to_internal_value(value)
        return date_value.replace(day=1)


class FlexiblePeriodField(serializers.DateField):
    """DateField accepting 'YYYY-MM' (→ day 1) or a full date (keeps the day).

    Income/expense periods are month-grained by default, but a full date
    records the exact payment day when it is known. Statements keep the
    strict MonthPeriodField: they are matched by exact day-1 equality.
    """

    def to_internal_value(self, value):
        if isinstance(value, str) and MONTH_PERIOD_RE.match(value.strip()):
            value = f'{value.strip()}-01'
        return super().to_internal_value(value)


class PeriodReadMixin(serializers.Serializer):
    period = serializers.SerializerMethodField()
    period_label = serializers.SerializerMethodField()

    def get_period(self, obj):
        return month_period(obj.period_date)

    def get_period_label(self, obj):
        return month_label(obj.period_date)


class PartnerSplitWriteMixin(serializers.Serializer):
    """Split fields + validation shared by income/expense write serializers.

    Company records keep the 50/50 default split. Personal-ledger records
    always belong 100% to their owner: any split sent by the client is
    normalized instead of rejected.
    """

    total_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
    )
    gustavo_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
        required=False,
    )
    carlos_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
        required=False,
    )
    ledger = serializers.ChoiceField(choices=Ledger.choices, required=False)

    def validate(self, data):
        data = super().validate(data)

        def effective(field, default=None):
            if field in data:
                return data[field]
            if self.instance is not None:
                return getattr(self.instance, field)
            return default

        total = effective('total_amount')
        ledger = effective('ledger', Ledger.COMPANY)

        if ledger in PERSONAL_LEDGER_OWNER:
            if total is not None:
                owner_field, other_field = PERSONAL_LEDGER_OWNER[ledger]
                data[owner_field] = total
                data[other_field] = Decimal('0')
            return data

        split_provided = 'gustavo_amount' in data or 'carlos_amount' in data
        if self.instance is None and not split_provided and total is not None:
            gustavo, carlos = split_half(total)
            data['gustavo_amount'] = gustavo
            data['carlos_amount'] = carlos

        gustavo = effective('gustavo_amount', Decimal('0')) or Decimal('0')
        carlos = effective('carlos_amount', Decimal('0')) or Decimal('0')
        if total is not None and gustavo + carlos > total:
            raise serializers.ValidationError(
                'La suma de los montos de los socios no puede superar el monto total.'
            )
        return data


# ── Income ──

PAYMENT_STATUS_LABELS = {
    'paid': 'Pagado',
    'partial': 'Parcial',
    'pending': 'Pendiente',
}


def paid_total_for_income(income):
    """Money already credited against one expected income."""
    liquid = income.liquid_records.filter(
        kind=IncomeRecord.Kind.LIQUID,
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    deducted = income.deduction_records.exclude(
        deduction_type='',
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    return liquid + deducted


def payment_status_for(paid, total):
    """Collection state ('pending'/'partial'/'paid') from a paid total.

    Single owner of the boundary rule: the row serializer and the export
    column both call it, while the SQL filter in views.accounting mirrors
    it in Q algebra ("keep both sides in sync"). None passes through —
    non-expected rows carry no collection state. A zero-total expected
    (fully moved out by a residual-only settlement) is closed, not pending.
    """
    if paid is None:
        return None
    if paid >= total and (paid > 0 or total == 0):
        return 'paid'
    return 'pending' if paid <= 0 else 'partial'


class IncomeRecordSerializer(VatReadMixin, PeriodReadMixin, serializers.ModelSerializer):
    kind_label = serializers.CharField(source='get_kind_display', read_only=True)
    destination_label = serializers.CharField(
        source='get_destination_display', read_only=True,
    )
    ledger_label = serializers.CharField(
        source='get_ledger_display', read_only=True,
    )
    company_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    paid_amount = serializers.SerializerMethodField()
    pending_amount = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_status_label = serializers.SerializerMethodField()
    has_collection_account = serializers.SerializerMethodField()
    collection_account_id = serializers.SerializerMethodField()
    collection_account_number = serializers.SerializerMethodField()
    collection_account_status = serializers.SerializerMethodField()
    can_settle = serializers.SerializerMethodField()
    settlement_blocked_reason = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    # None, not '': "sin proyecto" has to stay distinguishable from a blank
    # name, same convention get_client_name follows.
    project_name = serializers.CharField(
        source='project.name', read_only=True, default=None,
    )
    origin_label = serializers.CharField(
        source='get_origin_display', read_only=True,
    )
    collection_confidence_label = serializers.SerializerMethodField()
    # '' → None: "sin periodicidad" should read as an absence, not a blank.
    period_cadence_label = serializers.SerializerMethodField()

    def get_period_cadence_label(self, obj):
        return obj.get_period_cadence_display() if obj.period_cadence else None

    def get_collection_confidence_label(self, obj):
        if not obj.collection_confidence:
            return None
        return obj.get_collection_confidence_display()

    class Meta:
        model = IncomeRecord
        fields = (
            'vat_rate', 'base_amount', 'vat_amount',
            'id', 'concept', 'kind', 'kind_label',
            'period', 'period_label', 'period_date',
            'period_start', 'period_end',
            'period_cadence', 'period_cadence_label',
            'destination', 'destination_label', 'ledger', 'ledger_label',
            'client', 'client_name', 'project', 'project_name',
            'origin', 'origin_label',
            'is_receivable_candidate', 'collection_confidence',
            'collection_confidence_label',
            'total_amount', 'gustavo_amount', 'carlos_amount', 'company_amount',
            'expected_income', 'pocket_movement',
            'paid_amount', 'pending_amount',
            'payment_status', 'payment_status_label',
            'has_collection_account', 'collection_account_id',
            'collection_account_number',
            'collection_account_status', 'can_settle', 'settlement_blocked_reason',
            'reminders_muted', 'reminders_muted_until',
            'reminder_last_sent_at', 'reminder_count',
            'notes', 'created_at', 'updated_at',
        )
        # Muting is written only by the mute endpoint, never by a generic
        # PATCH: that path emails both partners on every change, which is the
        # noise the payment calendar exists to remove.
        read_only_fields = (
            'reminders_muted', 'reminders_muted_until',
            'reminder_last_sent_at', 'reminder_count',
        )

    def get_client_name(self, obj):
        """Display name of the linked client; None keeps 'sin cliente' distinct."""
        if not obj.client_id:
            return None
        from accounts.services.proposal_client_service import (
            build_client_display_name,
        )

        return build_client_display_name(obj.client)

    def _paid(self, obj):
        """Liquid total fulfilling this record; None for non-expected rows.

        `None` (not '0.00') lets the UI tell "not applicable" from
        "nothing paid yet". The list and export endpoints annotate the
        queryset; the retrieve/create/update ones serialize a bare
        instance, so fall back to a per-object aggregate there — memoized
        on the instance, since all four payment fields call this.
        """
        if obj.kind != IncomeRecord.Kind.EXPECTED:
            return None
        if not hasattr(obj, '_paid_total'):
            value = getattr(obj, 'paid_amount', None)
            if value is None:
                value = paid_total_for_income(obj)
            obj._paid_total = Decimal(value)
        return obj._paid_total

    def get_paid_amount(self, obj):
        paid = self._paid(obj)
        return None if paid is None else money_str(paid)

    def get_pending_amount(self, obj):
        paid = self._paid(obj)
        if paid is None:
            return None
        return money_str(max(obj.total_amount - paid, Decimal('0')))

    def get_payment_status(self, obj):
        return payment_status_for(self._paid(obj), obj.total_amount)

    def get_payment_status_label(self, obj):
        return PAYMENT_STATUS_LABELS.get(self.get_payment_status(obj))

    def _collection_account(self, obj):
        """(id, public_number) of the non-cancelled cuenta linked to this row.

        The list/export querysets carry the collection_account_subqueries
        annotations; NULL is a legitimate annotated value there (most rows
        have no cuenta), so annotation presence is detected via __dict__,
        not getattr — falling back to one memoized query only when the
        instance was never annotated (retrieve/create/update paths).
        """
        if not hasattr(obj, '_collection_account_ref'):
            if 'collection_account_id' in obj.__dict__:
                obj._collection_account_ref = (
                    obj.__dict__['collection_account_id'],
                    obj.__dict__.get('collection_account_number') or '',
                    obj.__dict__.get('collection_account_status'),
                )
            else:
                row = (
                    obj.collection_documents
                    .filter(document_type__code='collection_account')
                    .exclude(commercial_status=Document.CommercialStatus.CANCELLED)
                    .order_by('-created_at')
                    .values_list('id', 'public_number', 'commercial_status')
                    .first()
                )
                obj._collection_account_ref = row or (None, '', None)
        return obj._collection_account_ref

    def get_has_collection_account(self, obj):
        return self._collection_account(obj)[0] is not None

    def get_collection_account_id(self, obj):
        return self._collection_account(obj)[0]

    def get_collection_account_number(self, obj):
        return self._collection_account(obj)[1] or None

    def get_collection_account_status(self, obj):
        return self._collection_account(obj)[2]

    def get_settlement_blocked_reason(self, obj):
        from content.services.income_settlement_policy import settlement_blocked_reason
        account_status = self.get_collection_account_status(obj)
        if obj.client_id:
            eligible_account = obj.__dict__.get('has_issued_collection_account')
            if eligible_account is None:
                eligible_account = obj.collection_documents.filter(
                    document_type__code='collection_account',
                    commercial_status__in=('issued', 'paid'),
                    client_user_id=obj.client.user_id, project_id=obj.project_id,
                ).exists()
            if not eligible_account:
                account_status = None
        return settlement_blocked_reason(
            kind=obj.kind,
            pending=max(obj.total_amount - (self._paid(obj) or 0), Decimal('0')),
            client_id=obj.client_id,
            account_status=account_status,
        )

    def get_can_settle(self, obj):
        return not self.get_settlement_blocked_reason(obj)


def validate_project_client_match(project, client):
    """A record's project must belong to the record's own client.

    The two relations disagree on what they point at: `Project.client` is a
    FK to the User, while every accounting record's `client` is a
    UserProfile. `UserProfile.user` is a OneToOne, so `client.user_id` is a
    plain column and the check costs no extra query.

    Raises a field-scoped error so the panel and the MCP both render it on
    the project input.
    """
    if project is None:
        return
    if client is None:
        raise serializers.ValidationError({
            'project': 'Asigna primero el cliente: el proyecto debe ser suyo.',
        })
    if project.client_id != client.user_id:
        raise serializers.ValidationError({
            'project': (
                f'El proyecto "{project.name}" pertenece a otro cliente.'
            ),
        })


class IncomeRecordCreateUpdateSerializer(
    VatWriteMixin, PartnerSplitWriteMixin, serializers.ModelSerializer,
):
    vat_default = Decimal('19')
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False)
    # The window says WHAT the charge covers; period_date says WHEN the money
    # is expected. Hosting creates default it to the start only when omitted;
    # every other origin still has to send it (checked in validate()).
    period_date = FlexiblePeriodField(required=False)
    # Same month-shorthand as period_date: the form's exact-day toggle applies
    # to the start of the covered window.
    period_start = FlexiblePeriodField(required=False, allow_null=True)
    period_end = serializers.DateField(required=False, allow_null=True)
    expected_income = serializers.PrimaryKeyRelatedField(
        queryset=IncomeRecord.objects.filter(kind=IncomeRecord.Kind.EXPECTED),
        required=False,
        allow_null=True,
    )
    client = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(),
        required=False,
        allow_null=True,
    )
    # Not scoped by client here on purpose: a field-level queryset cannot see
    # its sibling's value, so the ownership rule lives in validate().
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = IncomeRecord
        fields = (
            'vat_rate', 'amount', 'amount_mode',
            'concept', 'kind', 'period_date', 'destination', 'ledger',
            'client', 'project', 'origin',
            'is_receivable_candidate', 'collection_confidence',
            'period_start', 'period_end', 'period_cadence',
            'total_amount', 'gustavo_amount', 'carlos_amount',
            'expected_income', 'notes',
        )

    def validate(self, data):
        data = super().validate(data)

        def effective(field, default=None):
            if field in data:
                return data[field]
            if self.instance is not None:
                return getattr(self.instance, field)
            return default

        kind = effective('kind')
        destination = effective('destination')
        ledger = effective('ledger', Ledger.COMPANY)

        # --- Manual receivable forecast --------------------------------
        # Confidence and shortlist membership are independent operator
        # decisions. Changing either one must preserve the other; a plain
        # deselection keeps the colour so the team's last judgement remains
        # visible when the record is inspected later.
        candidate_was_selected = data.get('is_receivable_candidate') is True
        confidence_was_assigned = bool(data.get('collection_confidence'))
        receivable_shape = (
            kind == IncomeRecord.Kind.EXPECTED and ledger == Ledger.COMPANY
        )
        if (candidate_was_selected or confidence_was_assigned) and not receivable_shape:
            raise serializers.ValidationError({
                'is_receivable_candidate': (
                    'Solo un ingreso esperado de la contabilidad de empresa '
                    'puede seleccionarse como pendiente por cobrar.'
                ),
            })
        if not receivable_shape:
            # Kind/ledger transitions close the active forecast but preserve
            # collection_confidence as historical context.
            data['is_receivable_candidate'] = False

        candidate = effective('is_receivable_candidate', False)
        # A colour is only meaningful while the receivable is open, even when
        # the independent inclusion switch stays off. Existing active rows
        # still close automatically when another edit makes them fully paid.
        if receivable_shape and (candidate or confidence_was_assigned):
            paid = (
                paid_total_for_income(self.instance)
                if self.instance is not None
                else Decimal('0')
            )
            if payment_status_for(paid, effective('total_amount')) == 'paid':
                if candidate_was_selected or confidence_was_assigned:
                    raise serializers.ValidationError({
                        'is_receivable_candidate': (
                            'Un ingreso completamente pagado no puede '
                            'seleccionarse como pendiente por cobrar.'
                        ),
                    })
                data['is_receivable_candidate'] = False
        if (
            destination == IncomeRecord.Destination.POCKET
            and kind != IncomeRecord.Kind.LIQUID
        ):
            raise serializers.ValidationError(
                'El destino Bolsillo ProjectApp solo aplica a ingresos líquidos.'
            )
        if (
            ledger != Ledger.COMPANY
            and destination == IncomeRecord.Destination.POCKET
        ):
            raise serializers.ValidationError(
                'Los movimientos personales no pueden ir al Bolsillo ProjectApp.'
            )
        # PocketMovement.amount requires >= 0.01 and the sync writer skips
        # model validators; a zero-amount liquid pocket income would mirror
        # an invalid movement.
        if (
            kind == IncomeRecord.Kind.LIQUID
            and destination == IncomeRecord.Destination.POCKET
            and effective('total_amount') == 0
        ):
            raise serializers.ValidationError({
                'total_amount': (
                    'Un ingreso registrado en el bolsillo debe tener un '
                    'monto mayor a cero.'
                ),
            })
        expected = effective('expected_income')
        if expected is not None and expected.ledger != ledger:
            raise serializers.ValidationError(
                'El ingreso esperado vinculado debe ser de la misma contabilidad.'
            )
        # Writing off an expected record that was partially collected would
        # drop its full amount out of `expected_total` while its liquid
        # children keep counting (received_pct can then exceed 100%), and it
        # would leave those children pointing at a non-expected parent, which
        # `expected_income`'s queryset rejects on any later PATCH.
        if (
            kind == IncomeRecord.Kind.LOST
            and self.instance is not None
            and self.instance.kind == IncomeRecord.Kind.EXPECTED
            and self.instance.liquid_records.filter(
                kind=IncomeRecord.Kind.LIQUID,
            ).exists()
        ):
            raise serializers.ValidationError(
                'Este ingreso esperado ya tiene liquidaciones. Reduce su monto '
                'y registra la diferencia como un ingreso perdido aparte.'
            )
        # An active (non-cancelled) cuenta de cobro freezes an EXISTING
        # client: the document went out in their name, and even a draft is a
        # cuenta in flight. The path for a mistake is anular y reemitir.
        # Completing a missing client stays allowed (the legacy backlog and
        # the issue-time adoption both do exactly that), and hostings stay
        # exempt on purpose — they accumulate issued cuentas for years and
        # each one carries its own frozen snapshot.
        if (
            'client' in data
            and self.instance is not None
            and self.instance.client_id is not None
            and data['client'] != self.instance.client
            and self.instance.collection_documents.exclude(
                commercial_status=Document.CommercialStatus.CANCELLED,
            ).exists()
        ):
            raise serializers.ValidationError({
                'client': (
                    'Este ingreso tiene una cuenta de cobro activa. Anúlala '
                    'y emite una nueva para reasignar el cliente.'
                ),
            })
        # Moving the record to another client orphans a project that belonged
        # to the previous one — not merely a stale value like the hosting
        # billing snapshot, but a record pointing at someone else's project.
        # Clearing is the only safe default; the operator re-picks explicitly.
        if (
            'client' in data
            and self.instance is not None
            and data['client'] != self.instance.client
            and 'project' not in data
        ):
            data['project'] = None
        project = effective('project')
        validate_project_client_match(project, effective('client'))
        creates_expected = (
            kind == IncomeRecord.Kind.EXPECTED
            and (
                self.instance is None
                or self.instance.kind != IncomeRecord.Kind.EXPECTED
                or ('project' in data and project != self.instance.project)
            )
        )
        if creates_expected and project is not None:
            from content.services.project_state_service import (
                project_allows_billing,
            )
            if not project_allows_billing(project):
                raise serializers.ValidationError({
                    'project': (
                        'El estado actual del proyecto no permite crear '
                        'ingresos esperados.'
                    ),
                })

        # --- Business line -----------------------------------------------
        # The origin is not one more field: it decides whether the record
        # covers a window or a single date, and duplicating an income can only
        # carry a line of business the original recorded — an unclassified
        # original opens its copy unclassified, which is how a faithful copy
        # came to read as a broken one. So anything a person writes has to say
        # it: always on create, and on update whenever the field is being
        # written. The panel form always sends it, so editing a legacy record
        # classifies it — the same gradual backfill the period block below
        # relies on — while a partial PATCH that does not touch it leaves the
        # record as unclassified as it already was.
        #
        # Every creation path a person drives is included, the MCP tool
        # `create_income` among them — creating from the chat classifies a new
        # record exactly like the panel form does, and its schema declares
        # `origin` required so the caller is told rather than refused.
        #
        # Settling is the one exemption: its children copy the parent's origin
        # instead of classifying anything, and the parent may well predate the
        # field. Same escape `deduction_type` takes on the expense side.
        if not self.context.get('settlement'):
            if (self.instance is None or 'origin' in data) and not data.get('origin'):
                raise serializers.ValidationError({
                    'origin': 'Elige la línea de negocio del ingreso.',
                })

        # --- Covered period (hosting only) -------------------------------
        # A hosting income records both the service window the charge covers
        # and when the money is expected in period_date. Every other origin
        # keeps the single date. Legacy hosting rows predate the window fields:
        # a partial PATCH that touches neither origin nor the period stays
        # valid, while the panel form always sends `origin`, so editing one
        # from there completes its period (deliberate gradual backfill).
        #
        # Settling takes the same escape `origin` takes above, and for a
        # stronger reason: it does not describe a charge, it DERIVES records
        # from one already on the book. The window belongs to the expected
        # income — the record that says which service was billed — while its
        # children are the payment (a date, an amount, a destination) and the
        # balance rescheduled for later. Demanding it of them would refuse
        # every hosting settlement, the ones whose parent has a complete
        # window included, since the child is new and inherits nothing but the
        # origin. Giving them the parent's window would also attribute the
        # billed service to every payment and rescheduled balance instead of
        # keeping it on the original charge.
        origin = effective('origin', '')
        period_fields = ('origin', 'period_start', 'period_end', 'period_cadence')
        touches_period = any(field in data for field in period_fields)
        if origin == IncomeRecord.Origin.HOSTING:
            if (
                (self.instance is None or touches_period)
                and not self.context.get('settlement')
            ):
                if not effective('period_start'):
                    raise serializers.ValidationError({
                        'period_start': (
                            'Indica el período que cubre el ingreso de hosting.'
                        ),
                    })
                if not effective('period_end'):
                    raise serializers.ValidationError({
                        'period_end': (
                            'Indica el fin del período que cubre el ingreso.'
                        ),
                    })
                if not effective('period_cadence'):
                    raise serializers.ValidationError({
                        'period_cadence': 'Elige la periodicidad del período.',
                    })
                # An explicit expected-payment date always wins, including
                # when the service validates this data a second time. Without
                # one, creates default to the start; updates follow a new
                # start only if the stored date already followed it. An
                # independent date, including a legacy row without a start,
                # stays unchanged when its window is completed or edited.
                if 'period_date' not in data and (
                    self.instance is None
                    or (
                        self.instance.period_start is not None
                        and self.instance.period_date == self.instance.period_start
                    )
                ):
                    data['period_date'] = effective('period_start')
        else:
            # Switching a record away from hosting would otherwise leave an
            # orphaned window attached to a point payment.
            data['period_start'] = None
            data['period_end'] = None
            data['period_cadence'] = ''
        start = effective('period_start')
        end = effective('period_end')
        if start and end and end <= start:
            raise serializers.ValidationError({
                'period_end': (
                    'La fecha fin debe ser posterior a la fecha de inicio.'
                ),
            })
        if effective('period_date') is None:
            raise serializers.ValidationError({
                'period_date': 'Indica la fecha del ingreso.',
            })
        return data


class SettlementDeductionSerializer(serializers.Serializer):
    """One slice of the shortfall that will never be collected."""

    type = serializers.ChoiceField(choices=ExpenseRecord.DeductionType.choices)
    detail = serializers.CharField(
        required=False, allow_blank=True, max_length=200,
    )
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
    )

    def validate(self, data):
        if (
            data['type'] == ExpenseRecord.DeductionType.OTHER
            and not data.get('detail', '').strip()
        ):
            raise serializers.ValidationError({
                'detail': 'Describe el concepto del gasto.',
            })
        return data


class SettlementFollowUpSerializer(serializers.Serializer):
    """A slice that WILL be collected later, rescheduled as its own income."""

    concept = serializers.CharField(max_length=255)
    period_date = FlexiblePeriodField()
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
    )


class SettlementPeriodSerializer(serializers.Serializer):
    """The window a hosting charge covers, completed while settling it.

    Optional as a block and complete inside it: the modal either fills the
    three fields or sends nothing, so a half-answered window never reaches the
    book. It describes the PARENT — the expected income is what says which
    service was billed — and the service applies it there, never to the
    children the settlement derives.
    """

    period_start = FlexiblePeriodField()
    period_end = serializers.DateField()
    period_cadence = serializers.ChoiceField(
        choices=RecurringPayment.Frequency.choices,
    )


class IncomeSettlementSerializer(serializers.Serializer):
    """Liquidating an expected income plus how its shortfall is resolved.

    The liquidation fields mirror what the modal already sent to the plain
    create endpoint; `deductions` and `expected_incomes` are the new part.
    Cross-field validation against the parent's pending balance lives in
    ``accounting_settlement_service`` — it needs the record.
    """

    concept = serializers.CharField(max_length=255)
    period_date = FlexiblePeriodField()
    destination = serializers.ChoiceField(
        choices=IncomeRecord.Destination.choices,
        default=IncomeRecord.Destination.PARTNERS,
    )
    total_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
    )
    gustavo_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    carlos_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    deductions = SettlementDeductionSerializer(many=True, required=False)
    expected_incomes = SettlementFollowUpSerializer(many=True, required=False)
    # Completing the parent's window from here is a courtesy, never a
    # condition: a hosting income with no period settles exactly the same
    # without it. Resolving the gap where it shows up beats sending the
    # operator to another screen, and the money is never held for it.
    period = SettlementPeriodSerializer(required=False, allow_null=True)
    # Opt-in client email, sent by the settle view after the commit. Off by
    # default: MCP and `resolve_income_residual` share this serializer.
    send_payment_confirmation = serializers.BooleanField(
        required=False, default=False,
    )

    def validate(self, data):
        # FlexiblePeriodField stores a month-only period as day 1, which an
        # exact payment on the 1st also is. The confirmation email needs to
        # know which one the operator meant, and only the raw input says so.
        raw = self.initial_data.get('period_date')
        month_only = isinstance(raw, str) and MONTH_PERIOD_RE.match(raw.strip())
        data['period_date_precision'] = 'month' if month_only else 'day'
        return data


class SettlementAllocationSerializer(serializers.Serializer):
    """How much of one abono lands on one expected income."""

    income_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
    )


class IncomeBulkSettlementSerializer(serializers.Serializer):
    """One client payment distributed across several expected incomes.

    The panel computes the distribution (oldest first, hand-adjustable) and
    the backend only validates it — hidden re-computation here would betray
    the reparto the operator just confirmed on screen. Anything that needs
    the records themselves (pendings, ledgers, the excess owner) lives in
    ``accounting_settlement_service.bulk_settle_expected_incomes``.
    """

    allocations = SettlementAllocationSerializer(many=True, allow_empty=False)
    total_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
    )
    period_date = FlexiblePeriodField()
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        ids = [entry['income_id'] for entry in data['allocations']]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({
                'allocations': 'Hay ingresos repetidos en la distribución.',
            })
        allocated = sum(
            (entry['amount'] for entry in data['allocations']), Decimal('0'),
        )
        # Less than the total is legal: the difference becomes the client's
        # saldo a favor (a parentless liquid child on the same movement).
        if allocated > data['total_amount']:
            raise serializers.ValidationError({
                'total_amount': (
                    'La suma de la distribución no puede superar el monto '
                    'recibido.'
                ),
            })
        return data


class IncomeClientBulkAssignSerializer(serializers.Serializer):
    """Assign one client to several incomes; ``client: null`` unlinks them."""

    income_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False,
    )
    client = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(),
        required=False,
        allow_null=True,
    )


class IncomeProjectBulkAssignSerializer(serializers.Serializer):
    """Assign one project to several incomes; ``project: null`` unlinks them."""

    income_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False,
    )
    # Unscoped on purpose, like the single-record field: the ownership rule
    # (every record's client must own the project) needs the records in
    # hand, so it lives in the view's pre-checks.
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
    )


class IncomeReminderMuteSerializer(serializers.Serializer):
    """Silence an expected income's notices, optionally until a given date."""

    muted = serializers.BooleanField()
    until = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        data = super().validate(data)
        if data.get('muted') and data.get('until'):
            if data['until'] <= today_bogota():
                # Silencing "until today" would end the moment it began.
                raise serializers.ValidationError({
                    'until': 'La fecha de reanudación debe ser posterior a hoy.',
                })
        return data


class HostingClientBulkAssignSerializer(serializers.Serializer):
    """Assign one client to several hostings; ``client: null`` unlinks them."""

    hosting_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False,
    )
    client = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(),
        required=False,
        allow_null=True,
    )


class HostingProjectBulkAssignSerializer(serializers.Serializer):
    """Assign one project to several hostings; ``project: null`` unlinks them."""

    hosting_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False,
    )
    # Unscoped for the same reason as the income flavour: ownership is a
    # cross-record rule, checked in the view against the loaded rows.
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
    )


# ── Expense ──

class ExpenseRecordSerializer(VatReadMixin, PeriodReadMixin, serializers.ModelSerializer):
    category_label = serializers.CharField(
        source='get_category_display', read_only=True,
    )
    ledger_label = serializers.CharField(
        source='get_ledger_display', read_only=True,
    )
    company_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    deduction_type_label = serializers.CharField(
        source='get_deduction_type_display', read_only=True,
    )
    source_income_concept = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseRecord
        fields = (
            'vat_rate', 'base_amount', 'vat_amount',
            'id', 'concept',
            'period', 'period_label', 'period_date',
            'category', 'category_label',
            'ledger', 'ledger_label',
            'deduction_type', 'deduction_type_label',
            'source_income', 'source_income_concept',
            'total_amount', 'gustavo_amount', 'carlos_amount', 'company_amount',
            'pocket_movement',
            'notes', 'created_at', 'updated_at',
        )

    def get_source_income_concept(self, obj):
        # List/export annotate the queryset; single-object paths fall back
        # to the relation (deduction rows are few).
        value = getattr(obj, 'source_income_concept', None)
        if value is not None:
            return value
        if obj.source_income_id is None:
            return None
        return obj.source_income.concept


class ExpenseRecordCreateUpdateSerializer(
    VatWriteMixin, PartnerSplitWriteMixin, serializers.ModelSerializer,
):
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False)
    period_date = FlexiblePeriodField()
    # Not a model field: the service pops it. Checked by default — unchecked
    # covers paper adjustments and personal expenses that never touched the
    # company pocket. On update it can also link/unlink the mirror movement.
    register_in_pocket = serializers.BooleanField(
        required=False, default=True, write_only=True,
    )

    class Meta:
        model = ExpenseRecord
        fields = (
            'vat_rate', 'amount', 'amount_mode',
            'concept', 'period_date', 'category', 'ledger',
            'deduction_type',
            'total_amount', 'gustavo_amount', 'carlos_amount', 'notes',
            'register_in_pocket',
        )

    def validate(self, data):
        data = super().validate(data)

        def effective(field, default=None):
            if field in data:
                return data[field]
            if self.instance is not None:
                return getattr(self.instance, field)
            return default

        # Deductions are born in the settlement flow only: it is the one
        # place where the pocket rule, the source_income link and the paid
        # credit stay consistent. Manual writes may neither set nor clear
        # the type.
        if not self.context.get('settlement') and 'deduction_type' in data:
            current = self.instance.deduction_type if self.instance else ''
            if data['deduction_type'] != current:
                raise serializers.ValidationError({
                    'deduction_type': (
                        'Las deducciones se crean desde la liquidación '
                        'del ingreso.'
                    ),
                })
        if effective('deduction_type', ''):
            # That money never entered the pocket — discounted at origin.
            data['register_in_pocket'] = False

        wants_pocket = data.get('register_in_pocket')
        if wants_pocket is None:
            wants_pocket = (
                self.instance is not None
                and self.instance.pocket_movement_id is not None
            )
        total = effective('total_amount')
        # PocketMovement.amount requires >= 0.01 and the sync writer skips
        # model validators; zero stays valid only for expenses that never
        # touch the pocket (paper adjustments).
        if wants_pocket and total == 0:
            raise serializers.ValidationError({
                'total_amount': (
                    'Un gasto registrado en el bolsillo debe tener un '
                    'monto mayor a cero.'
                ),
            })

        ledger = effective('ledger', Ledger.COMPANY)
        if ledger not in PERSONAL_LEDGER_OWNER:
            return data
        if not wants_pocket or total is None:
            return data
        # A personal expense paid from the pocket is a partner draw:
        # company money fully assigned to that partner. Keeping it on the
        # personal ledger would drain the pocket without reducing the
        # company utility (pocket == liquid income − expenses).
        owner_field, other_field = PERSONAL_LEDGER_OWNER[ledger]
        data['ledger'] = Ledger.COMPANY
        data[owner_field] = total
        data[other_field] = Decimal('0')
        return data


# ── Hosting ──

class HostingRecordSerializer(VatReadMixin, serializers.ModelSerializer):
    payment_modality_label = serializers.CharField(
        read_only=True,
    )
    client_display_name = serializers.SerializerMethodField()
    # The `Marca` half of the old `Persona - Marca` label, now its own field.
    project_name = serializers.CharField(
        source='project.name', read_only=True, default=None,
    )
    billing_email = serializers.CharField(read_only=True)
    # Both halves rejoined, so the screens that need to name a whole hosting
    # (confirmations, modal headers) do not re-join them in JS.
    display_label = serializers.CharField(read_only=True)

    class Meta:
        model = HostingRecord
        fields = (
            'vat_rate', 'base_amount', 'vat_amount',
            'id', 'client', 'client_display_name', 'billing_email',
            'project', 'project_name', 'display_label',
            'client_name', 'client_email', 'client_contact_name',
            'client_identification', 'domain_url', 'monthly_value',
            'payment_modality', 'payment_modality_label', 'benefit',
            'valid_from', 'valid_to', 'cycles_count',
            'payment_per_cycle', 'total_paid', 'is_active',
            'expiry_notice_last_sent_at', 'billing_requested_at',
            'notes', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'expiry_notice_last_sent_at', 'billing_requested_at',
        )

    def get_client_display_name(self, obj):
        """Linked client's display name; None keeps 'sin cliente' distinct
        from the free-text `client_name` snapshot."""
        if not obj.client_id:
            return None
        from accounts.services.proposal_client_service import (
            build_client_display_name,
        )

        return build_client_display_name(obj.client)


class HostingRecordCreateUpdateSerializer(VatWriteMixin, serializers.ModelSerializer):
    vat_total_field = 'payment_per_cycle'
    vat_default = Decimal('19')
    monthly_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
    )
    client = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(),
        required=False,
        allow_null=True,
    )
    # See the note on the income serializer: the ownership rule needs both
    # values, so it lives in validate() rather than in a scoped queryset.
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
    )
    payment_modality = serializers.CharField(required=False)

    class Meta:
        model = HostingRecord
        # cycles_count/total_paid are deliberately NOT writable: cycle
        # history (HostingCycle) is the source of truth and the service
        # recalculates the denormalized columns.
        fields = (
            'vat_rate', 'amount', 'amount_mode',
            'client', 'project', 'client_name', 'client_email',
            'client_contact_name',
            'client_identification', 'domain_url', 'monthly_value',
            'payment_modality', 'benefit', 'valid_from', 'valid_to',
            'payment_per_cycle', 'is_active', 'notes',
        )
        extra_kwargs = {
            # Required on create only, alongside `client`: both are filled
            # from the picker. Legacy records keep saving without either.
            'client_name': {'required': False},
        }

    def validate(self, data):
        data = super().validate(data)

        modality = data.get('payment_modality')
        if modality is not None:
            offered = set(HostingRecord.Modality.values)
            legacy_unchanged = bool(
                self.instance
                and modality == self.instance.payment_modality
                and modality in {
                    HostingRecord.LEGACY_MONTHLY,
                    HostingRecord.LEGACY_ANNUAL,
                }
            )
            if modality not in offered and not legacy_unchanged:
                raise serializers.ValidationError({
                    'payment_modality': (
                        'Periodicidad inválida. Opciones: quarterly, '
                        'semiannual, nine_month.'
                    ),
                })

        def effective(field):
            if field in data:
                return data[field]
            return getattr(self.instance, field, None)

        # Every hosting belongs to a client, so new ones must say who —
        # but an existing record with no client must stay editable while it
        # is completed (it would be unsavable otherwise).
        if self.instance is None and not data.get('client'):
            raise serializers.ValidationError({
                'client': 'Todo hosting nuevo debe tener un cliente asignado.',
            })

        client = effective('client')
        # Swapping the FK makes the stored snapshot the PREVIOUS client's
        # contact data — and billing_email prefers the override, so a stale
        # client_email would route the cuenta de cobro to the wrong inbox.
        client_changed = (
            self.instance is not None
            and 'client' in data
            and getattr(data['client'], 'pk', None) != self.instance.client_id
        )
        if client is not None:
            # Fill the billing snapshot from the profile when the form left
            # it empty; whatever the operator typed IN THIS REQUEST wins.
            from content.services.collection_account_create_service import (
                customer_snapshot_defaults,
            )

            defaults = customer_snapshot_defaults(client)
            snapshot = {
                'client_name': defaults['name'],
                'client_email': defaults['email'],
                'client_contact_name': defaults['contact_name'],
                'client_identification': defaults['identification'],
            }
            for field, fallback in snapshot.items():
                if field in data:
                    continue
                if client_changed:
                    # On reassignment the old values are the other client's:
                    # refresh everything not explicitly overridden here.
                    data[field] = fallback or ''
                elif not effective(field) and fallback:
                    data[field] = fallback

        # Same rule as on incomes: a reassigned hosting cannot keep pointing
        # at the previous client's project. Unlike the billing snapshot above
        # this is not a staleness problem but an ownership one, so it clears
        # instead of refreshing.
        if client_changed and 'project' not in data:
            data['project'] = None
        validate_project_client_match(effective('project'), client)

        if self.instance is None and not effective('client_name'):
            raise serializers.ValidationError({
                'client_name': 'El nombre del cliente es obligatorio.',
            })

        valid_from = effective('valid_from')
        valid_to = effective('valid_to')
        if valid_from and valid_to and valid_to < valid_from:
            raise serializers.ValidationError(
                'La fecha de fin de vigencia no puede ser anterior al inicio.'
            )

        # Default the per-cycle payment from the modality on create.
        if self.instance is None and 'payment_per_cycle' not in data:
            monthly = data.get('monthly_value')
            modality = data.get(
                'payment_modality', HostingRecord.Modality.QUARTERLY,
            )
            if monthly is not None:
                months = HostingRecord.MODALITY_MONTHS.get(modality, 1)
                data['payment_per_cycle'] = (monthly * months).quantize(
                    TWO_PLACES,
                )
        return data


class HostingCycleSerializer(serializers.ModelSerializer):
    modality_label = serializers.SerializerMethodField()
    is_backfill = serializers.SerializerMethodField()

    class Meta:
        model = HostingCycle
        fields = (
            'id', 'modality', 'modality_label', 'amount', 'paid_at',
            'period_from', 'period_to', 'cycles_represented',
            'is_backfill', 'notes', 'created_at',
        )

    def get_modality_label(self, obj):
        return HostingRecord.modality_label(obj.modality)

    def get_is_backfill(self, obj):
        return obj.source_ref.startswith('backfill:')


class HostingCycleCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
        required=False,
    )
    modality = serializers.ChoiceField(
        choices=HostingRecord.Modality.choices, required=False,
    )
    paid_at = serializers.DateField(required=False)
    period_from = serializers.DateField(required=False)
    period_to = serializers.DateField(required=False)
    notes = serializers.CharField(
        required=False, allow_blank=True, default='',
    )
    advance_validity = serializers.BooleanField(required=False, default=True)

    def validate(self, data):
        period_from = data.get('period_from')
        period_to = data.get('period_to')
        if period_from and period_to and period_to <= period_from:
            raise serializers.ValidationError(
                'El fin del período debe ser posterior al inicio.'
            )
        return data


# ── Pocket ──

def allocation_entries(movement):
    """Per-income breakdown of an abono: how much of this movement went where.

    One entry for ordinary linked movements, [] when unlinked, so the panel
    renders a single structure either way.

    Module-level and not a serializer method because two serializers render it
    — the pocket ledger row and the income detail's settlement history — and
    the panel's PocketMovementAllocationsModal reads the result verbatim from
    either side. One owner of the shape is what keeps them from drifting.

    Reads `income_children`, which memoizes and reuses the caller's prefetch.
    """
    return [
        {
            'income_id': child.pk,
            'expected_income_id': child.expected_income_id,
            'concept': child.concept,
            'amount': str(child.total_amount),
        }
        for child in movement.income_children
    ]


class PocketMovementSerializer(serializers.ModelSerializer):
    direction_label = serializers.CharField(
        source='get_direction_display', read_only=True,
    )
    is_auto_managed = serializers.ReadOnlyField()
    linked_income_id = serializers.SerializerMethodField()
    linked_expense_id = serializers.SerializerMethodField()
    linked_ledger = serializers.SerializerMethodField()
    allocations = serializers.SerializerMethodField()

    class Meta:
        model = PocketMovement
        fields = (
            'id', 'concept', 'movement_date',
            'direction', 'direction_label', 'amount', 'is_auto_managed',
            'linked_income_id', 'linked_expense_id', 'linked_ledger',
            'allocations',
            'notes', 'created_at', 'updated_at',
        )

    def get_linked_income_id(self, obj):
        """Pk of the single covered income; None for a shared abono movement.

        A shared movement is represented by `allocations` — a single id would
        pick one child arbitrarily and every consumer of this field assumes
        a 1:1 mirror.
        """
        children = obj.income_children
        return children[0].pk if len(children) == 1 else None

    def get_linked_expense_id(self, obj):
        expense = getattr(obj, 'expense_record', None)
        return expense.pk if expense else None

    def get_linked_ledger(self, obj):
        """Attribution shown by the pocket modal's Contabilidad control.

        Field name kept for API compatibility; the rule itself lives on the
        model so the `attribution` filter and the CSV export cannot drift from
        what this field reports.
        """
        return obj.attribution

    def get_allocations(self, obj):
        return allocation_entries(obj)


class SettlementMovementSerializer(serializers.ModelSerializer):
    """The pocket movement as the income detail needs to name it.

    Deliberately NOT `PocketMovementSerializer`: that one carries
    `linked_expense_id` and `linked_ledger`, which read the reverse OneToOne
    `expense_record` — a query per row, for a join that is structurally always
    NULL on an incoming movement. This one never touches it.

    The field names are chosen so the payload drops straight into the panel's
    PocketMovementAllocationsModal, which is what lets the income detail reuse
    that modal with no adapter and no second fetch.
    """

    # The model owns what makes a movement an abono; mirroring the rule here
    # would let the two answers drift.
    is_shared = serializers.ReadOnlyField()
    allocation_count = serializers.SerializerMethodField()
    allocations = serializers.SerializerMethodField()

    class Meta:
        model = PocketMovement
        fields = (
            'id', 'concept', 'movement_date', 'amount',
            'is_shared', 'allocation_count', 'allocations',
        )

    def get_allocation_count(self, obj):
        return len(obj.income_children)

    def get_allocations(self, obj):
        return allocation_entries(obj)


# ── Income ↔ Pocket bridge ──

class LiquidSettlementSerializer(IncomeRecordSerializer):
    """A liquid child plus the pocket movement that paid it.

    Only the income DETAIL endpoint uses this. `IncomeRecordSerializer` itself
    stays lean on purpose: it is shared with the paginated list, the
    create/update responses and the MCP get_income handler, none of which
    select_related the movement — nesting it there would cost two queries per
    liquid row on every list page to answer a question only the detail asks.
    """

    movement = SettlementMovementSerializer(source='pocket_movement', read_only=True)

    class Meta(IncomeRecordSerializer.Meta):
        fields = IncomeRecordSerializer.Meta.fields + ('movement',)


class PocketMovementCreateUpdateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
    )
    # Not a model field: the service pops it and applies it to the mirrored
    # income/expense record (accounting of Empresa / Gustavo / Carlos).
    ledger = serializers.ChoiceField(
        choices=Ledger.choices, required=False, write_only=True,
    )

    class Meta:
        model = PocketMovement
        fields = ('concept', 'movement_date', 'direction', 'amount', 'notes', 'ledger')

    def validate(self, data):
        data = super().validate(data)
        if 'direction' in data:
            direction = data['direction']
        elif self.instance is not None:
            direction = self.instance.direction
        else:
            direction = None
        ledger = data.get('ledger')
        if ledger is None and self.instance is not None:
            linked = self.instance.linked_record
            ledger = linked.ledger if linked else None
        if (
            direction == PocketMovement.Direction.IN
            and ledger not in (None, Ledger.COMPANY)
        ):
            raise serializers.ValidationError(
                'Los movimientos personales no pueden ir al Bolsillo ProjectApp.'
            )
        return data


# ── Recurring payments ──

class RecurringCategorySerializer(serializers.ModelSerializer):
    """User-editable grouping for the Recurrentes tab.

    `payment_count` comes from an annotation on the list view; it falls back
    to a direct count so the serializer also works on a plain instance
    (create/update responses).
    """

    payment_count = serializers.SerializerMethodField()

    class Meta:
        model = RecurringCategory
        fields = ('id', 'name', 'slug', 'order', 'payment_count')
        read_only_fields = ('slug',)

    def get_payment_count(self, obj):
        annotated = getattr(obj, 'payment_count_annotated', None)
        return annotated if annotated is not None else obj.payments.count()

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError('El nombre no puede estar vacío.')
        return name


class RecurringStateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class RecurringReminderMuteSerializer(serializers.Serializer):
    muted = serializers.BooleanField()
    until = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        data = super().validate(data)
        if data.get('muted') and data.get('until'):
            if data['until'] <= today_bogota():
                raise serializers.ValidationError({
                    'until': 'La fecha de reanudación debe ser posterior a hoy.',
                })
        return data


class RecurringBulkActionSerializer(serializers.Serializer):
    recurring_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=500,
    )
    action = serializers.ChoiceField(
        choices=('activate', 'deactivate', 'archive'),
    )

    def validate_recurring_ids(self, value):
        # A repeated checkbox id must not produce duplicate audit rows or make
        # the response count disagree with what changed.
        return list(dict.fromkeys(value))


class RecurringPaymentSerializer(serializers.ModelSerializer):
    payment_method_label = serializers.CharField(
        source='get_payment_method_display', read_only=True,
    )
    # `frequency_display` and not `get_frequency_display`: a custom cycle has
    # to read "Cada 5 meses", not a bare "Personalizada".
    frequency_label = serializers.CharField(
        source='frequency_display', read_only=True,
    )
    cost_type_label = serializers.CharField(
        source='get_cost_type_display', read_only=True,
    )
    category_name = serializers.CharField(
        source='category.name', read_only=True, allow_null=True,
    )
    monthly_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    monthly_cop_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    next_charge_date = serializers.SerializerMethodField()
    # Preformatted like `period_label` and `frequency_label`: the table renders
    # it as plain text in both view modes, so neither has to format a date.
    next_charge_label = serializers.SerializerMethodField()
    reminders_effectively_muted = serializers.SerializerMethodField()

    class Meta:
        model = RecurringPayment
        fields = (
            'id', 'name', 'price', 'currency', 'cop_equivalent',
            'payment_method', 'payment_method_label',
            'frequency', 'frequency_label', 'custom_months', 'billing_day',
            'cycle_anchor_date', 'next_charge_date', 'next_charge_label',
            'cost_type', 'cost_type_label',
            'category', 'category_name', 'order',
            'monthly_price', 'monthly_cop_cost',
            'is_active', 'is_archived', 'archived_at',
            'reminders_muted', 'reminders_muted_until',
            'reminders_effectively_muted',
            'notes', 'created_at', 'updated_at',
        )
        read_only_fields = ('order',)

    def _next_charge(self, obj):
        if not hasattr(obj, '_next_charge_cache'):
            from content.services.recurring_schedule import next_charge_date

            obj._next_charge_cache = next_charge_date(obj, today_bogota())
        return obj._next_charge_cache

    def get_next_charge_date(self, obj):
        value = self._next_charge(obj)
        return value.isoformat() if value else None

    def get_next_charge_label(self, obj):
        """"Jue, 30 sep 2026", or a dash when the cycle has no reference date.

        A dash rather than an empty cell: "sin fecha de cobro" is something to
        fill in — that payment generates no notices — not something missing.
        """
        value = self._next_charge(obj)
        return format_bogota_date(value) if value else '—'

    def get_reminders_effectively_muted(self, obj):
        if not obj.reminders_muted:
            return False
        return (
            obj.reminders_muted_until is None
            or obj.reminders_muted_until > today_bogota()
        )


class RecurringPaymentCreateUpdateSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=RecurringCategory.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = RecurringPayment
        # `order` is deliberately absent: the manual sort slot is owned by the
        # reorder endpoint, so an ordinary edit can never scramble the list.
        fields = (
            'name', 'price', 'currency', 'cop_equivalent',
            'payment_method', 'frequency', 'custom_months', 'billing_day',
            'cycle_anchor_date',
            'cost_type', 'category', 'is_active', 'notes',
        )
        # Kept in the accepted wire shape for rolling compatibility with old
        # panel/MCP clients, but any submitted value is ignored.  The model is
        # the single owner and derives it from price, currency and current rate.
        read_only_fields = ('cop_equivalent',)

    def validate(self, data):
        data = super().validate(data)
        self._validate_custom_months(data)
        if (
            self.instance is not None
            and self.instance.is_archived
            and data.get('is_active') is True
        ):
            raise serializers.ValidationError({
                'is_active': 'Restaura el pago recurrente antes de activarlo.',
            })
        return data

    def _validate_custom_months(self, data):
        """A custom frequency is meaningless without its cycle length.

        Both fields are resolved against the instance first so a partial PATCH
        that only flips the frequency still sees the months already stored (and
        the other way around).
        """
        frequency = self._resolved(data, 'frequency', RecurringPayment.Frequency.MONTHLY)
        if frequency != RecurringPayment.Frequency.CUSTOM:
            # Outside CUSTOM the field carries no meaning; the model clears it
            # on save, and dropping it here keeps the change log honest.
            data['custom_months'] = None
            return
        months = self._resolved(data, 'custom_months', None)
        if not months:
            raise serializers.ValidationError({
                'custom_months': (
                    'Indica cada cuántos meses se cobra la frecuencia personalizada.'
                )
            })
        data['custom_months'] = months

    def _resolved(self, data, field, default):
        if field in data:
            return data[field]
        if self.instance is not None:
            return getattr(self.instance, field)
        return default

    @staticmethod
    def _next_order(category):
        last = RecurringPayment.objects.filter(category=category).aggregate(
            last=Max('order'),
        )['last']
        return 0 if last is None else last + 1

    def create(self, validated_data):
        # New rows land at the end of their group instead of tying at 0.
        validated_data['order'] = self._next_order(validated_data.get('category'))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Moving to another category means the old slot is meaningless: send
        # the row to the end of its new group.
        if 'category' in validated_data:
            new_category = validated_data['category']
            if new_category != instance.category:
                validated_data['order'] = self._next_order(new_category)
        return super().update(instance, validated_data)


# ── Ads ──

class AdsSpendRecordSerializer(serializers.ModelSerializer):
    platform_label = serializers.CharField(
        source='get_platform_display', read_only=True,
    )
    accumulated = serializers.SerializerMethodField()

    class Meta:
        model = AdsSpendRecord
        fields = (
            'id', 'spend_date', 'platform', 'platform_label',
            'origin_card', 'amount', 'accumulated',
            'notes', 'created_at', 'updated_at',
        )

    def get_accumulated(self, obj):
        # Set by accounting_service.ads_with_accumulated; absent on writes.
        value = getattr(obj, 'accumulated', None)
        return str(value) if value is not None else None


class AdsSpendRecordCreateUpdateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
    )

    class Meta:
        model = AdsSpendRecord
        fields = ('spend_date', 'platform', 'origin_card', 'amount', 'notes')


# ── Credit-card catalog ──

class CreditCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditCard
        fields = (
            'id', 'name', 'credit_limit', 'is_active',
            'statements_since', 'notes', 'created_at', 'updated_at',
        )


class CreditCardCreateUpdateSerializer(serializers.ModelSerializer):
    credit_limit = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
    )
    statements_since = MonthPeriodField(required=False, allow_null=True)

    class Meta:
        model = CreditCard
        fields = (
            'name', 'credit_limit', 'is_active', 'statements_since', 'notes',
        )


# ── Card snapshots ──

class CardBalanceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardBalanceSnapshot
        fields = (
            'id', 'snapshot_date', 'card_name',
            'available_amount', 'debt_amount',
            'notes', 'created_at', 'updated_at',
        )


class CardBalanceSnapshotCreateUpdateSerializer(serializers.ModelSerializer):
    """Snapshot writes with server-computed debt.

    When the card exists in the catalog, ``debt_amount`` is authoritative
    on the server: cupo − disponible (any client-sent value is ignored).
    Cards outside the catalog (legacy names) keep the old contract: an
    explicit debt on create, and the stored value on partial updates.
    """

    available_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
    )
    debt_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
        required=False,
    )

    class Meta:
        model = CardBalanceSnapshot
        fields = (
            'snapshot_date', 'card_name',
            'available_amount', 'debt_amount', 'notes',
        )

    def validate(self, attrs):
        card_name = attrs.get('card_name') or getattr(
            self.instance, 'card_name', None,
        )
        available = attrs.get('available_amount', getattr(
            self.instance, 'available_amount', None,
        ))
        # Recompute only when the money-relevant inputs change: a notes-only
        # edit must not rewrite a historic debt with today's cupo.
        recompute = (
            self.instance is None
            or 'available_amount' in attrs
            or 'card_name' in attrs
        )
        card = CreditCard.objects.filter(name=card_name).first()
        if card is not None:
            if recompute and available is not None:
                if available > card.credit_limit:
                    raise serializers.ValidationError({
                        'available_amount': (
                            'El disponible no puede superar el cupo de la '
                            f'tarjeta (${card.credit_limit:,.0f}).'
                        ),
                    })
                attrs['debt_amount'] = card.credit_limit - available
            else:
                attrs.pop('debt_amount', None)
        elif self.instance is None and 'debt_amount' not in attrs:
            raise serializers.ValidationError({
                'debt_amount': (
                    'La tarjeta no está en el catálogo; la deuda debe '
                    'indicarse explícitamente.'
                ),
            })
        return attrs


# ── Notification recipients ──

class NotificationRecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationRecipient
        fields = (
            'id', 'email', 'is_active', 'notes', 'created_at', 'updated_at',
        )


class NotificationRecipientCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationRecipient
        fields = ('email', 'is_active', 'notes')
        # The model's unique=True would answer in English and only for an
        # exact match; validate_email owns the check instead.
        extra_kwargs = {'email': {'validators': []}}

    def validate_email(self, value):
        """Normalize the address and keep the list free of duplicates."""
        normalized = (value or '').strip().lower()
        queryset = NotificationRecipient.objects.filter(email__iexact=normalized)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('Ese correo ya está en la lista.')
        return normalized


# ── Email send log ──

# One label per automated email of the module, matching the section names
# used in the settings panel. The keys are the TEMPLATE_KEY constants of the
# services that emit them; a test pins them together so they cannot drift.
EMAIL_TEMPLATE_LABELS = {
    'accounting_change': 'Cambio contable',
    'accounting_card_reminder': 'Recordatorio de deuda de tarjetas',
    'accounting_statement_reminder': 'Recordatorio de extractos',
    'accounting_payment_calendar': 'Calendario de cobros y pagos',
    'collection_account_sent': 'Cuenta de cobro',
    'income_payment_received_client': 'Confirmación de pago',
    'payment_status_team': 'Pago de hosting',
}


# Notices tied to one record, which is what makes a retry reproducible: the
# rest are digests assembled from whatever was due that morning, so resending
# one would rebuild today's summary, not the one that failed.
RETRYABLE_TEMPLATE_KEYS = frozenset({
    'accounting_change',
    'collection_account_sent',
    'income_payment_received_client',
    'payment_status_team',
})
RETRY_BLOCKED_REASON = (
    'Este aviso resume varios registros del día en que salió: reenviarlo '
    'armaría el resumen de hoy, no el que falló.'
)


class EmailLogTargetSerializer(serializers.ModelSerializer):
    entity_type_label = serializers.CharField(
        source='get_entity_type_display', read_only=True,
    )

    class Meta:
        model = EmailLogTarget
        fields = ('entity_type', 'entity_type_label', 'object_id', 'object_repr')


class EmailLogSerializer(serializers.ModelSerializer):
    template_label = serializers.SerializerMethodField()
    status_label = serializers.CharField(
        source='get_status_display', read_only=True,
    )
    origin_action_label = serializers.CharField(
        source='get_origin_action_display', read_only=True, default='',
    )
    targets = EmailLogTargetSerializer(many=True, read_only=True)
    has_body = serializers.SerializerMethodField()
    is_retryable = serializers.SerializerMethodField()
    retry_blocked_reason = serializers.SerializerMethodField()
    copies = serializers.SerializerMethodField()

    class Meta:
        model = EmailLog
        fields = (
            'id', 'template_key', 'template_label', 'recipient', 'subject',
            'status', 'status_label', 'error_message', 'sent_at',
            'origin_action', 'origin_action_label', 'targets', 'has_body',
            'is_retryable', 'retry_blocked_reason', 'retry_of',
            'delivery_id', 'delivery_role', 'copies',
        )

    def get_template_label(self, obj):
        return EMAIL_TEMPLATE_LABELS.get(obj.template_key, obj.template_key)

    def get_has_body(self, obj):
        return obj.body_id is not None

    def get_is_retryable(self, obj):
        return (
            obj.delivery_role == EmailLog.DeliveryRole.PRIMARY
            and obj.status == EmailLog.Status.FAILED
            and obj.template_key in RETRYABLE_TEMPLATE_KEYS
        )

    def get_retry_blocked_reason(self, obj):
        # Delegated so the tooltip and the endpoint's 400 cannot disagree,
        # and so a proposal row gets its own sentence instead of the digest's.
        if obj.delivery_role == EmailLog.DeliveryRole.COPY:
            return 'Las copias internas no se reintentan.'
        from content.services.accounting_email_retry_service import (
            retry_blocked_reason,
        )
        return retry_blocked_reason(obj.template_key)

    def get_copies(self, obj):
        from content.services.email_log_service import delivery_copy_payloads

        return delivery_copy_payloads(obj)


# ── Change log & settings ──

class AccountingChangeLogSerializer(serializers.ModelSerializer):
    changes = serializers.SerializerMethodField()

    def get_changes(self, obj):
        from content.services.accounting_display import display_accounting_changes
        return display_accounting_changes(obj.changes)

    entity_type_label = serializers.CharField(
        source='get_entity_type_display', read_only=True,
    )
    action_label = serializers.CharField(
        source='get_action_display', read_only=True,
    )

    class Meta:
        model = AccountingChangeLog
        fields = (
            'id', 'entity_type', 'entity_type_label',
            'object_id', 'object_repr', 'action', 'action_label',
            'changes', 'actor', 'actor_username', 'created_at',
        )


class AccountingSettingsSerializer(serializers.ModelSerializer):
    usd_exchange_rate = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('1'),
        required=False,
    )

    class Meta:
        model = AccountingSettings
        fields = (
            'notifications_enabled',
            'card_reminder_enabled', 'statement_reminder_enabled',
            'hosting_expiry_reminder_enabled',
            'payment_calendar_enabled', 'overdue_reminder_frequency',
            'usd_exchange_rate', 'income_default_view_mode',
            'collection_accounts_view_mode',
            'collection_accounts_group_by', 'updated_at',
        )
