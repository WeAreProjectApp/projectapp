"""API views for the accounting module (panel, superuser-only).

All endpoints require an authenticated superuser (IsSuperUser). Lists
return {'results': [...], 'meta': {...}} and are filtered server-side via
shared query params (date_from/date_to/year, amount_min/amount_max,
partner, q) plus per-entity choice filters; rich interactive filtering
happens client-side. The change log is the only paginated endpoint.
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from accounts.models import Project
from content.api_errors import error_response, error_response_from_exc
from content.models import (
    AccountingChangeLog,
    AccountingSettings,
    AdsSpendRecord,
    CardBalanceSnapshot,
    CreditCard,
    CreditCardStatement,
    Document,
    EmailLog,
    ExpenseRecord,
    HostingRecord,
    IncomeRecord,
    Ledger,
    MerchantAlias,
    NotificationRecipient,
    PocketMovement,
    RecurringCategory,
    RecurringPayment,
)
from content.permissions import IsSuperUser
from content.serializers.accounting import (
    TWO_PLACES,
    money_str,
    AccountingChangeLogSerializer,
    AccountingSettingsSerializer,
    AdsSpendRecordCreateUpdateSerializer,
    AdsSpendRecordSerializer,
    CardBalanceSnapshotCreateUpdateSerializer,
    CardBalanceSnapshotSerializer,
    CreditCardCreateUpdateSerializer,
    CreditCardSerializer,
    EMAIL_TEMPLATE_LABELS,
    EmailLogSerializer,
    ExpenseRecordCreateUpdateSerializer,
    ExpenseRecordSerializer,
    HostingCycleCreateSerializer,
    HostingCycleSerializer,
    HostingClientBulkAssignSerializer,
    HostingProjectBulkAssignSerializer,
    HostingRecordCreateUpdateSerializer,
    HostingRecordSerializer,
    IncomeRecordCreateUpdateSerializer,
    IncomeRecordSerializer,
    IncomeBulkSettlementSerializer,
    IncomeClientBulkAssignSerializer,
    IncomeProjectBulkAssignSerializer,
    IncomeReminderMuteSerializer,
    IncomeSettlementSerializer,
    NotificationRecipientCreateUpdateSerializer,
    NotificationRecipientSerializer,
    PocketMovementCreateUpdateSerializer,
    PocketMovementSerializer,
    RecurringPaymentCreateUpdateSerializer,
    RecurringBulkActionSerializer,
    RecurringReminderMuteSerializer,
    RecurringPaymentSerializer,
    RecurringStateSerializer,
)
from content.serializers.accounting_statement import (
    CreditCardStatementSerializer,
    CreditCardStatementWriteSerializer,
    MerchantAliasSerializer,
    MerchantAliasWriteSerializer,
)
from content.services import (
    accounting_email_retry_service,
    accounting_history_service,
    accounting_income_duplicate_service,
    accounting_income_detail_service,
    accounting_income_mute_service,
    accounting_recurring_service,
    accounting_service,
    accounting_settlement_service,
)
from content.services.email_log_service import attach_delivery_copies
from content.utils import today_bogota
from content.views.history_pagination import (
    email_body_response,
    paginated_history_response,
)

EntityType = AccountingChangeLog.EntityType


# The history service owns the parsing so its querysets and these views
# reject a malformed date with the same message.
_parse_date = accounting_history_service.parse_date_param

# Builtin presets plus the per-user ceiling of saved tabs, with room to spare.
MAX_TAB_COUNT_SPECS = 24

# Shared with the per-client email modal, which pages the same rows through a
# different scope. Re-exported under the old private names so the call sites
# in this module read as they always did.
_paginated_history_response = paginated_history_response


def _parse_decimal(value, param):
    try:
        return Decimal(value)
    except (TypeError, InvalidOperation):
        raise ValueError(f"El parámetro '{param}' debe ser un número.")


# The serializers module owns the canonical money-string format.
_money = money_str


def _top_record(queryset, concept_field='concept'):
    top = (
        queryset.order_by('-total_amount')
        .values(concept_field, 'total_amount')
        .first()
    )
    if not top:
        return None
    return {
        'concept': top[concept_field],
        'amount': _money(top['total_amount'] or 0),
    }


def _income_meta(queryset, params):
    today = today_bogota()
    year_qs = queryset.filter(period_date__year=today.year)
    totals = year_qs.aggregate(
        expected_total=Sum('total_amount', filter=Q(kind='expected')),
        liquid_total=Sum('total_amount', filter=Q(kind='liquid')),
        lost_total=Sum('total_amount', filter=Q(kind='lost')),
        month_liquid=Sum(
            'total_amount',
            filter=Q(kind='liquid', period_date__month=today.month),
        ),
    )
    expected = totals['expected_total'] or 0
    liquid = totals['liquid_total'] or 0
    received_pct = int(round(liquid / expected * 100)) if expected else None
    return {
        'expected_total': _money(expected),
        'liquid_total': _money(liquid),
        'lost_total': _money(totals['lost_total'] or 0),
        'received_pct': received_pct,
        'current_month_liquid': _money(totals['month_liquid'] or 0),
        'top_income': _top_record(year_qs.filter(kind='liquid')),
        # Completion debt of the client link over the whole filtered set —
        # legacy rows live in past years, so the year window would hide them.
        'without_client_count': queryset.filter(client__isnull=True).count(),
        # Same backlog definition as /panel/projects: only client-linked rows
        # can be proposed a project, so both counters compose without overlap.
        'without_project_count': queryset.filter(
            client__isnull=False, project__isnull=True,
        ).count(),
    }


def _expense_meta(queryset, params):
    today = today_bogota()
    year_qs = queryset.filter(period_date__year=today.year)
    totals = year_qs.aggregate(
        year_total=Sum('total_amount'),
        month_total=Sum(
            'total_amount', filter=Q(period_date__month=today.month),
        ),
        business_total=Sum('total_amount', filter=Q(category='business')),
        personal_total=Sum('total_amount', filter=Q(category='personal')),
    )
    month_total = totals['month_total'] or 0
    # Alert: current month >= 1.5x the average of the year's prior months.
    prior_months = (
        year_qs.filter(period_date__month__lt=today.month)
        .values_list('period_date__month')
        .annotate(total=Sum('total_amount'))
    )
    prior_totals = [row[1] for row in prior_months]
    alert = False
    if prior_totals:
        average = sum(prior_totals) / len(prior_totals)
        alert = average > 0 and month_total >= average * Decimal('1.5')
    deduction_rows = list(
        year_qs.exclude(deduction_type='')
        .values_list('deduction_type')
        .annotate(total=Sum('total_amount'))
    )
    deductions_by_type = {row[0]: _money(row[1] or 0) for row in deduction_rows}
    return {
        'year_total': _money(totals['year_total'] or 0),
        'current_month_total': _money(month_total),
        'business_total': _money(totals['business_total'] or 0),
        'personal_total': _money(totals['personal_total'] or 0),
        'current_month_alert': alert,
        'top_expense': _top_record(year_qs),
        # Year deductions, whole and by type: the answer to "cuánto se fue
        # en comisiones y cuánto acumuló la retención".
        'deductions_total': _money(
            sum((row[1] or 0 for row in deduction_rows), Decimal('0')),
        ),
        'deductions_by_type': deductions_by_type,
    }


def _hosting_meta(queryset, params):
    today = today_bogota()
    totals = queryset.aggregate(
        active_count=Count('id', filter=Q(is_active=True)),
        monthly_income=Sum('monthly_value', filter=Q(is_active=True)),
        total_paid=Sum('total_paid'),
        expiring_soon_count=Count(
            'id',
            filter=Q(
                is_active=True,
                valid_to__gte=today,
                valid_to__lte=today + timedelta(days=30),
            ),
        ),
        without_client_count=Count('id', filter=Q(client__isnull=True)),
        # Same backlog definition as /panel/projects: only client-linked rows
        # can be proposed a project, so both counters compose without overlap.
        without_project_count=Count(
            'id', filter=Q(client__isnull=False, project__isnull=True),
        ),
    )
    return {
        'active_count': totals['active_count'] or 0,
        'monthly_income': _money(totals['monthly_income'] or 0),
        'total_paid': _money(totals['total_paid'] or 0),
        'expiring_soon_count': totals['expiring_soon_count'] or 0,
        'without_client_count': totals['without_client_count'] or 0,
        'without_project_count': totals['without_project_count'] or 0,
    }


def _pocket_meta(queryset, params):
    as_of = None
    if params.get('date_to'):
        as_of = _parse_date(params['date_to'], 'date_to')
    return {'balance': _money(accounting_service.pocket_balance(as_of=as_of))}


def _recurring_meta(queryset, params):
    active = queryset.filter(is_active=True, is_archived=False)
    total = accounting_service.recurring_monthly_cost(active)
    rate = AccountingSettings.load().usd_exchange_rate or 0
    monthly_usd = (
        _money((Decimal(total) / rate).quantize(TWO_PLACES)) if rate else None
    )
    usd_native = active.filter(currency='USD').aggregate(
        total=Sum('price'),
    )['total']
    return {
        'monthly_cop_total': _money(total),
        'monthly_usd_total': monthly_usd,
        'usd_native_total': _money(usd_native or 0),
        'usd_exchange_rate': _money(rate) if rate else None,
    }


# ── Pocket linkage + attribution (mirror-derived, not columns) ──────────────
#
# `PocketMovement` has no ledger of its own: the panel's "Atribuir a" reads
# `PocketMovement.attribution`, a python property over the mirrored record.
# These Q objects restate that property in SQL so the CSV export and the MCP
# tool cut exactly the rows the table shows. Keep both sides in sync.
#
# Building them once at import time is safe: `filter()` combines copies of a Q
# and never mutates it (same rationale as the `annotations` entries below).


def _pocket_partner_draw_q(amount_field):
    """OUT rows whose mirrored company expense is 100% one partner's.

    The amount test in `PartnerSplitMixin.partner_attribution` only runs on
    company-ledger rows with a truthy total, so both guards are reproduced
    here. Without the ledger guard, a personal expense assigned to the other
    partner would leak into this branch.
    """
    return Q(**{
        'expense_record__ledger': Ledger.COMPANY,
        'expense_record__total_amount__gt': 0,
        f'expense_record__{amount_field}': F('expense_record__total_amount'),
    })


def _pocket_children_q(**child_filters):
    """EXISTS over the movement's income children matching the filters.

    Exists() rather than a `income_records__...` JOIN lookup on purpose: since
    the abono, income↔movement is a plural reverse FK, and a JOIN would fan a
    movement out once per child — duplicated rows in the table, the count and
    the CSV, and an inflated running balance client-side. (The header balance
    is immune either way: `_pocket_meta` re-aggregates from `objects.all()`.)
    EXISTS matches without multiplying, so no `.distinct()` is needed.
    """
    return Exists(
        IncomeRecord.objects.filter(
            pocket_movement=OuterRef('pk'), **child_filters,
        ),
    )


# Known divergences from the property, all only reachable by writing invalid
# rows straight through the ORM (the serializer and `clean()` reject them):
# a partner amount ABOVE the total matches no branch, a row with both partner
# amounts equal to the total matches gustavo and carlos at once, and a
# movement whose children mix ledgers matches one branch per child ledger
# while the property collapses the mix to COMPANY.
_POCKET_ATTRIBUTION_Q = {
    'gustavo': (
        Q(_pocket_children_q(ledger=Ledger.GUSTAVO))
        | Q(expense_record__ledger=Ledger.GUSTAVO)
        | _pocket_partner_draw_q('gustavo_amount')
    ),
    'carlos': (
        Q(_pocket_children_q(ledger=Ledger.CARLOS))
        | Q(expense_record__ledger=Ledger.CARLOS)
        | _pocket_partner_draw_q('carlos_amount')
    ),
    # Company is the property's fallthrough: a company-ledger mirror NOT fully
    # assigned to a single partner. Spelled `< total` rather than `!= total`
    # (the split validation caps each partner amount at the total) to keep the
    # condition positive; `lte=0` covers the zero-total row the property
    # short-circuits to COMPANY. The income side needs no cardinality test:
    # an abono's children are company-ledger by construction, so any company
    # child marks the movement company — same answer the property derives.
    'company': (
        Q(_pocket_children_q(ledger=Ledger.COMPANY))
        | (
            Q(expense_record__ledger=Ledger.COMPANY)
            & (
                Q(expense_record__total_amount__lte=0)
                | Q(
                    expense_record__gustavo_amount__lt=F(
                        'expense_record__total_amount',
                    ),
                    expense_record__carlos_amount__lt=F(
                        'expense_record__total_amount',
                    ),
                )
            )
        )
    ),
    # `attribution` is None when the movement mirrors nothing.
    'none': Q(expense_record__isnull=True) & ~Q(_pocket_children_q()),
}

_POCKET_LINKED_Q = {
    'true': Q(_pocket_children_q()) | Q(expense_record__isnull=False),
    # The expense side stays a positive isnull (a negated lookup over a
    # nullable reverse one-to-one is where this kind of filter goes wrong);
    # the income side is NOT EXISTS, which never joins and cannot fan out.
    'false': Q(expense_record__isnull=True) & ~Q(_pocket_children_q()),
}


# Mirrors `IncomeRecordSerializer.get_payment_status` over the `paid_amount`
# annotation: keep both sides in sync. Applied with `wrap=Q(kind=EXPECTED)`,
# which every branch relies on — `paid` alone would also match a liquid row,
# whose paid_amount and total_amount are both 0.
#
# `total_amount__gt=0` on `pending` is what reconciles this with
# `payment_status_for`, which calls a zero-total expected 'paid' (a settlement
# that closes a record at total 0 is collected, not uncollected).
_PAYMENT_STATUS_Q = {
    'pending': Q(paid_amount__lte=0) & Q(total_amount__gt=0),
    'partial': Q(paid_amount__gt=0) & Q(paid_amount__lt=F('total_amount')),
    'paid': Q(paid_amount__gte=F('total_amount')),
}


def _partner_conditions(config):
    """Token -> Q for the partner split.

    A factory rather than a constant because `projectapp` folds in the
    entity's own `pocket_filter`: an income can be pocket-bound, an expense
    cannot.
    """
    projectapp = Q(total_amount__gt=F('gustavo_amount') + F('carlos_amount'))
    pocket_q = config.get('pocket_filter')
    if pocket_q is not None:
        projectapp = pocket_q | projectapp
    return {
        'gustavo': Q(gustavo_amount__gt=0),
        'carlos': Q(carlos_amount__gt=0),
        'projectapp': projectapp,
    }


def _apply_token_filter(queryset, field, raw_value, conditions, wrap=None):
    """OR the Qs of the comma-separated tokens in `raw_value`.

    One parser for every filter whose values are not columns. Empty and the
    explicit `all` sentinel mean "no cut"; an unknown token is a 400 rather
    than a silent empty list, because a filter that quietly matches nothing is
    indistinguishable from data that does not exist.

    `wrap` is AND-ed around the whole OR, for a condition that qualifies every
    token instead of being one of them.
    """
    value = (raw_value or '').strip()
    if not value or value == 'all':
        return queryset
    tokens = [item for item in value.split(',') if item]
    if any(token not in conditions for token in tokens):
        raise ValueError(
            f"El parámetro '{field}' debe ser 'all' o uno o varios de: "
            + ', '.join(sorted(conditions)) + '.'
        )
    # Q() is the identity for `|`, so seeding the OR with it is safe.
    condition = Q()
    for token in tokens:
        condition |= conditions[token]
    if wrap is not None:
        condition = wrap & condition
    return queryset.filter(condition)


_ENTITIES = {
    'income': {
        'entity_type': EntityType.INCOME,
        'model': IncomeRecord,
        'read': IncomeRecordSerializer,
        'write': IncomeRecordCreateUpdateSerializer,
        'date_field': 'period_date',
        'amount_field': 'total_amount',
        'search_fields': (
            'concept', 'notes', 'client__company_name',
            'client__user__first_name', 'client__user__last_name',
            'project__name',
        ),
        'choice_filters': (
            'kind', 'destination', 'ledger', 'origin',
            'collection_confidence',
        ),
        'bool_filters': ('is_receivable_candidate',),
        # `expected_income` is here so the liquid children of one expected
        # record are finally queryable (?expected_income=<id>); nothing could
        # reach them from the panel before.
        'null_filters': ('client', 'project', 'expected_income'),
        'select_related': ('client', 'client__user', 'project'),
        'has_split': True,
        'pocket_filter': Q(destination=IncomeRecord.Destination.POCKET),
        'payment_status_filter': True,
        'meta': _income_meta,
        # Safe to share across requests: annotate() resolves a copy of the
        # expression, never the expression itself.
        'annotations': {
            'paid_amount': accounting_service.paid_amount_subquery(),
            **accounting_service.collection_account_subqueries(),
        },
    },
    'expense': {
        'entity_type': EntityType.EXPENSE,
        'model': ExpenseRecord,
        'read': ExpenseRecordSerializer,
        'write': ExpenseRecordCreateUpdateSerializer,
        'date_field': 'period_date',
        'amount_field': 'total_amount',
        'search_fields': ('concept', 'notes'),
        'choice_filters': ('category', 'ledger', 'deduction_type'),
        'has_split': True,
        'meta': _expense_meta,
        'annotations': {
            'source_income_concept':
                accounting_service.source_income_concept_subquery(),
        },
    },
    'hosting': {
        'entity_type': EntityType.HOSTING,
        'model': HostingRecord,
        'read': HostingRecordSerializer,
        'write': HostingRecordCreateUpdateSerializer,
        'date_field': 'valid_from',
        'amount_field': 'monthly_value',
        'search_fields': (
            'client_name', 'domain_url', 'notes',
            'client__company_name', 'client__user__first_name',
            'client__user__last_name', 'project__name',
        ),
        # No `project` choice filter: the project is a relation, so the
        # Proyecto multi-select narrows the loaded rows client-side and the
        # 'sin proyecto' sentinel rides `null_filters` below.
        'choice_filters': ('payment_modality',),
        'bool_filters': ('is_active',),
        'null_filters': ('client', 'project'),
        'select_related': ('client', 'client__user', 'project'),
        'meta': _hosting_meta,
    },
    'pocket': {
        'entity_type': EntityType.POCKET,
        'model': PocketMovement,
        'read': PocketMovementSerializer,
        'write': PocketMovementCreateUpdateSerializer,
        'date_field': 'movement_date',
        'amount_field': 'amount',
        'search_fields': ('concept', 'notes'),
        'choice_filters': ('direction',),
        'q_filters': {
            'attribution': _POCKET_ATTRIBUTION_Q,
            'linked': _POCKET_LINKED_Q,
        },
        'select_related': ('expense_record',),
        # Reverse FK since the abono (N liquid children per movement): one
        # extra query for the whole list instead of one per row.
        'prefetch_related': ('income_records',),
        'meta': _pocket_meta,
    },
    'recurring': {
        'entity_type': EntityType.RECURRING,
        'model': RecurringPayment,
        'read': RecurringPaymentSerializer,
        'write': RecurringPaymentCreateUpdateSerializer,
        'date_field': None,
        'amount_field': 'price',
        'search_fields': ('name', 'notes'),
        'choice_filters': (
            'frequency', 'cost_type', 'currency', 'payment_method', 'category',
        ),
        'bool_filters': ('is_active',),
        'archive_scope': True,
        'select_related': ('category',),
        'meta': _recurring_meta,
    },
    'ads': {
        'entity_type': EntityType.ADS,
        'model': AdsSpendRecord,
        'read': AdsSpendRecordSerializer,
        'write': AdsSpendRecordCreateUpdateSerializer,
        'date_field': 'spend_date',
        'amount_field': 'amount',
        'search_fields': ('origin_card', 'notes'),
        'choice_filters': ('platform', 'origin_card'),
        'with_accumulated': True,
    },
    'credit_card': {
        'entity_type': EntityType.CREDIT_CARD,
        'model': CreditCard,
        'read': CreditCardSerializer,
        'write': CreditCardCreateUpdateSerializer,
        'date_field': None,
        'amount_field': 'credit_limit',
        'search_fields': ('name', 'notes'),
        'bool_filters': ('is_active',),
    },
    'card_snapshot': {
        'entity_type': EntityType.CARD_SNAPSHOT,
        'model': CardBalanceSnapshot,
        'read': CardBalanceSnapshotSerializer,
        'write': CardBalanceSnapshotCreateUpdateSerializer,
        'date_field': 'snapshot_date',
        'amount_field': 'debt_amount',
        'search_fields': ('card_name', 'notes'),
        'choice_filters': ('card_name',),
    },
    'statement': {
        'entity_type': EntityType.STATEMENT,
        'model': CreditCardStatement,
        'read': CreditCardStatementSerializer,
        'write': CreditCardStatementWriteSerializer,
        'date_field': 'period_date',
        'amount_field': 'purchases_total',
        'search_fields': ('card_name', 'notes'),
        'choice_filters': ('status', 'card_name'),
    },
    'merchant_alias': {
        'entity_type': EntityType.MERCHANT_ALIAS,
        'model': MerchantAlias,
        'read': MerchantAliasSerializer,
        'write': MerchantAliasWriteSerializer,
        'date_field': None,
        'amount_field': None,
        'search_fields': ('match_text', 'merchant_name', 'notes'),
        'choice_filters': ('default_category',),
    },
    'notification_recipient': {
        'entity_type': EntityType.NOTIFICATION_RECIPIENT,
        'model': NotificationRecipient,
        'read': NotificationRecipientSerializer,
        'write': NotificationRecipientCreateUpdateSerializer,
        'date_field': None,
        'amount_field': None,
        'search_fields': ('email', 'notes'),
        'bool_filters': ('is_active',),
    },
}


def base_queryset(config):
    """Entity queryset with its read annotations and joins applied.

    Shared with the export views so a column computed for the table can
    never go missing from the CSV. `select_related` belongs here rather than
    in `_list_records`: the export columns read the same related rows, and
    left out of the export path it was a query per row.
    """
    queryset = config['model'].objects.all()
    annotations = config.get('annotations')
    if annotations:
        queryset = queryset.annotate(**annotations)
    if config.get('select_related'):
        queryset = queryset.select_related(*config['select_related'])
    if config.get('prefetch_related'):
        # Same export rationale as select_related — and doubly so for the
        # pocket: its "Atribución" column reads a property over the income
        # children, which with an abono's N rows would be a query per row.
        queryset = queryset.prefetch_related(*config['prefetch_related'])
    return queryset


def _apply_filters(queryset, params, config):
    if config.get('archive_scope'):
        archive_scope = (params.get('archive_scope') or 'current').strip()
        if archive_scope == 'current':
            queryset = queryset.filter(is_archived=False)
        elif archive_scope == 'archived':
            queryset = queryset.filter(is_archived=True)
        elif archive_scope != 'all':
            raise ValueError(
                "El parámetro 'archive_scope' debe ser current, archived o all."
            )

    date_field = config['date_field']
    if date_field:
        if params.get('year'):
            try:
                year = int(params['year'])
            except (TypeError, ValueError):
                raise ValueError("El parámetro 'year' debe ser un año válido.")
            queryset = queryset.filter(**{f'{date_field}__year': year})
        if params.get('date_from'):
            queryset = queryset.filter(**{
                f'{date_field}__gte': _parse_date(
                    params['date_from'], 'date_from',
                ),
            })
        if params.get('date_to'):
            queryset = queryset.filter(**{
                f'{date_field}__lte': _parse_date(
                    params['date_to'], 'date_to',
                ),
            })

    amount_field = config['amount_field']
    if amount_field and params.get('amount_min'):
        queryset = queryset.filter(**{
            f'{amount_field}__gte': _parse_decimal(
                params['amount_min'], 'amount_min',
            ),
        })
    if amount_field and params.get('amount_max'):
        queryset = queryset.filter(**{
            f'{amount_field}__lte': _parse_decimal(
                params['amount_max'], 'amount_max',
            ),
        })

    for field in config.get('choice_filters', ()):
        value = params.get(field)
        if value:
            # Comma-separated values filter as OR (multi-select filters).
            values = [item for item in value.split(',') if item]
            # 'none' isolates the rows whose choice was never set, so a
            # multi-select can mix real values with "sin clasificar". No
            # choice in the module uses 'none' as a real value.
            include_blank = 'none' in values
            values = [item for item in values if item != 'none']
            if include_blank:
                condition = Q(**{field: ''})
                if values:
                    condition |= Q(**{f'{field}__in': values})
                queryset = queryset.filter(condition)
            elif len(values) > 1:
                queryset = queryset.filter(**{f'{field}__in': values})
            elif values:
                queryset = queryset.filter(**{field: values[0]})

    for field in config.get('bool_filters', ()):
        # Now that the panel's boolean dimensions are checkable, "both marked"
        # serializes as `true,false` — which means no cut. That already fell
        # through the old exact-match test, but by accident; spelling it out
        # keeps it true when someone tightens this. Anything else stays
        # leniently ignored: this param has never validated, and turning it
        # into a 400 now would break every two-value export.
        value = (params.get(field) or '').strip()
        tokens = {item for item in value.split(',') if item}
        if tokens in ({'true'}, {'false'}):
            queryset = queryset.filter(**{field: tokens == {'true'}})

    # Nullable FK filters: 'none' isolates the unassigned rows as a group,
    # 'all'/empty means no filter, ids (comma-separated) filter as OR.
    # Same sentinel vocabulary as the documents `folder` param.
    for field in config.get('null_filters', ()):
        value = (params.get(field) or '').strip()
        if not value or value == 'all':
            continue
        tokens = [item for item in value.split(',') if item]
        include_null = 'none' in tokens
        try:
            ids = [int(item) for item in tokens if item != 'none']
        except ValueError:
            raise ValueError(
                f"El parámetro '{field}' debe ser 'none', 'all' o uno o "
                'varios ids separados por coma.'
            )
        condition = Q()
        if include_null:
            condition |= Q(**{f'{field}__isnull': True})
        if ids:
            condition |= Q(**{f'{field}__in': ids})
        if condition:
            queryset = queryset.filter(condition)

    # Filters whose values are not columns: each param maps a value token to a
    # ready-made Q, and comma-separated tokens filter as OR (same vocabulary as
    # `choice_filters`). This is how the pocket exposes linkage and attribution,
    # which live in the mirrored income/expense and not in PocketMovement.
    for field, conditions in config.get('q_filters', {}).items():
        # No .distinct() needed: every relation these Qs traverse is a reverse
        # OneToOne, which cannot fan a row out across the join.
        queryset = _apply_token_filter(
            queryset, field, params.get(field), conditions,
        )

    if config.get('has_split'):
        queryset = _apply_token_filter(
            queryset, 'partner', params.get('partner'),
            _partner_conditions(config),
        )

    if config.get('payment_status_filter'):
        # `expected` is factored OUT of the OR on purpose. Inside it, asking for
        # pending+paid would OR three unguarded predicates over the annotation
        # and drag in the liquid and lost rows, whose paid_amount is 0.
        queryset = _apply_token_filter(
            queryset, 'payment_status', params.get('payment_status'),
            _PAYMENT_STATUS_Q,
            wrap=Q(kind=IncomeRecord.Kind.EXPECTED),
        )

    search = (params.get('q') or '').strip()
    if search:
        search_q = Q()
        for field in config['search_fields']:
            search_q |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(search_q)

    return queryset


# ── Generic handlers ──

def _list_records(request, key):
    config = _ENTITIES[key]
    queryset = base_queryset(config)
    try:
        queryset = _apply_filters(queryset, request.query_params, config)
        meta = config.get('meta', lambda qs, params: {})(
            queryset, request.query_params,
        )
    except ValueError as exc:
        return error_response_from_exc(exc)
    if config.get('with_accumulated'):
        records = accounting_service.ads_with_accumulated(queryset)
    else:
        records = queryset
    serializer = config['read'](records, many=True)
    return Response({'results': serializer.data, 'meta': meta})


def _create_record(request, key):
    config = _ENTITIES[key]
    serializer = config['write'](data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        instance = accounting_service.create_record(
            config['entity_type'], serializer, request.user,
        )
    except ValueError as exc:
        return error_response_from_exc(exc)
    return Response(
        config['read'](instance).data, status=status.HTTP_201_CREATED,
    )


def _retrieve_record(request, key, record_id):
    config = _ENTITIES[key]
    instance = get_object_or_404(config['model'], pk=record_id)
    return Response(config['read'](instance).data)


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_income_detail(request, record_id):
    """One income with everything needed to inspect it without leaving the row.

    Its own endpoint rather than a fatter `read` serializer: `config['read']`
    is shared with the list, the create/update responses and the MCP
    get_income handler, so nesting three lists there would weigh down every
    one of them.

    The shape deliberately mirrors the settle endpoint's, so the UI renders
    one structure for both "just settled" and "opened the detail".

    Each liquid child carries the pocket movement that paid it, so the panel
    can name it — and, when the movement is a shared abono, open the same
    reparto the pocket ledger shows. Cost is +1 query, flat: select_related
    puts the movement on the children's own query, and the prefetch fills the
    `income_records` cache that `PocketMovement.income_children` reads (it
    sorts in Python precisely so it does not bypass that cache), so
    is_shared/allocation_count/allocations share one cache walk per row
    regardless of how many siblings an abono has.
    """
    income = get_object_or_404(
        accounting_income_detail_service.income_detail_queryset(),
        pk=record_id,
    )
    return Response(
        accounting_income_detail_service.build_income_detail_payload(income),
    )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_client_projects(request):
    """Projects to pick from, optionally scoped to one client.

    A panel endpoint of its own instead of reusing /api/accounts/projects/:
    that one speaks User ids while the accounting module speaks UserProfile
    ids everywhere, and its serializer runs several per-row aggregates that a
    dropdown has no use for.

    IsAdminUser y no IsSuperUser como el resto del módulo: el picker también
    alimenta el formulario de documentos (IsAdminUser) y sus filas no exponen
    nada que el listado de documentos no muestre ya. Cada fila lleva su dueño
    para que un caller sin cliente fijado (elegir proyecto PRIMERO) pueda
    autocompletar el cliente desde la selección.
    """
    from accounts.services.proposal_client_service import build_client_display_name

    qs = Project.objects.select_related(
        'client__profile', 'current_state',
    ).order_by('name')
    client_profile_id = request.query_params.get('client')
    if client_profile_id:
        # The picker is scoped by UserProfile, the project by User.
        qs = qs.filter(client__profile__id=client_profile_id)

    results = []
    for project in qs:
        profile = (
            getattr(project.client, 'profile', None)
            if project.client_id else None
        )
        results.append({
            'id': project.pk,
            'name': project.name,
            'status': (
                project.current_state.system_key or project.current_state.slug
                if project.current_state else None
            ),
            'status_label': project.status_display,
            'current_state': None if project.current_state is None else {
                'id': project.current_state_id,
                'name': project.current_state.name,
                'color': project.current_state.color,
                'operational_effect': (
                    project.current_state.operational_effect
                ),
            },
            'client_profile_id': profile.id if profile else None,
            'client_display_name': (
                build_client_display_name(profile) if profile else None
            ),
        })
    return Response({'results': results})


def _update_record(request, key, record_id):
    config = _ENTITIES[key]
    instance = get_object_or_404(config['model'], pk=record_id)
    serializer = config['write'](
        instance, data=request.data, partial=True,
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        instance = accounting_service.update_record(
            config['entity_type'], instance, serializer, request.user,
        )
    except ValueError as exc:
        return error_response_from_exc(exc)
    return Response(config['read'](instance).data)


def _delete_record(request, key, record_id):
    config = _ENTITIES[key]
    instance = get_object_or_404(config['model'], pk=record_id)
    try:
        accounting_service.delete_record(
            config['entity_type'], instance, request.user,
        )
    except ValueError as exc:
        return error_response_from_exc(exc)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── Dashboard ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def accounting_dashboard(request):
    """Aggregated summary feeding the accounting dashboard."""
    year_param = request.query_params.get('year') or ''
    try:
        year = int(year_param) if year_param else today_bogota().year
    except (TypeError, ValueError):
        return error_response("El parámetro 'year' debe ser un año válido.")
    return Response(accounting_service.dashboard_summary(year))


@api_view(['GET'])
@permission_classes([IsSuperUser])
def accounting_stats(request):
    """Descriptive statistics feeding the analytics modals."""
    year_param = request.query_params.get('year') or ''
    try:
        year = int(year_param) if year_param else today_bogota().year
    except (TypeError, ValueError):
        return error_response("El parámetro 'year' debe ser un año válido.")
    return Response(accounting_service.year_descriptive_stats(year))


@api_view(['GET'])
@permission_classes([IsSuperUser])
def accounting_receivables(request):
    """Open expected company incomes plus the operator-managed forecast."""
    queryset = accounting_service.receivable_queryset()
    return Response({
        'summary': accounting_service.receivables_summary(queryset),
        'results': IncomeRecordSerializer(queryset, many=True).data,
    })


# ── Incomes ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_income_records(request):
    return _list_records(request, 'income')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_income_record(request):
    return _create_record(request, 'income')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def settle_income_record(request, record_id):
    """Liquidate an expected income and resolve its shortfall in one step.

    With empty `deductions`/`expected_incomes` this behaves exactly like
    creating a liquid child through the plain create endpoint.
    """
    income = get_object_or_404(IncomeRecord, pk=record_id)
    serializer = IncomeSettlementSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = accounting_settlement_service.settle_expected_income(
            income, serializer.validated_data, request.user,
        )
    except ValueError as exc:
        return error_response_from_exc(exc)
    # Explicit None: DRF serializes a None instance as {} via get_initial().
    return Response({
        'income': IncomeRecordSerializer(result['income']).data,
        'liquid': (
            IncomeRecordSerializer(result['liquid']).data
            if result['liquid'] is not None else None
        ),
        'expenses': ExpenseRecordSerializer(result['expenses'], many=True).data,
        'expected_incomes': IncomeRecordSerializer(
            result['expected_incomes'], many=True,
        ).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def mute_income_reminders(request, record_id):
    """Silence (or resume) the payment-calendar notices of one expected income.

    For the cases where the delay is already known and the daily reminder is
    only noise. `until` schedules the resume, so nothing gets silenced and
    forgotten; without it the mute lasts until it is lifted by hand.
    """
    income = get_object_or_404(IncomeRecord, pk=record_id)
    if income.kind != IncomeRecord.Kind.EXPECTED:
        return error_response(
            'Solo se pueden silenciar los avisos de un ingreso esperado.',
        )
    serializer = IncomeReminderMuteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    income = accounting_income_mute_service.set_income_reminder_mute(
        income,
        muted=serializer.validated_data['muted'],
        until=serializer.validated_data.get('until'),
        user=request.user,
    )
    return Response(IncomeRecordSerializer(income).data)


@api_view(['GET'])
@permission_classes([IsSuperUser])
def duplicate_income_draft(request, record_id):
    """Prefill for duplicating an income, so the next period is one click.

    Persists nothing: the panel opens its form with this payload and the
    record is created through the ordinary create endpoint after the date and
    the amount are confirmed.
    """
    income = get_object_or_404(IncomeRecord, pk=record_id)
    return Response(
        accounting_income_duplicate_service.build_income_duplicate_draft(income),
    )


def _optional_id(request, name):
    """Query param as an id, or None — an unreadable one counts as absent.

    The form asks while it is being filled, so a half-written value is an
    ordinary state, not an error: it just means there is nothing to look the
    antecedent up from yet.
    """
    raw = request.query_params.get(name)
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


@api_view(['GET'])
@permission_classes([IsSuperUser])
def suggest_income_period(request):
    """Where a client's next hosting window starts, so the form can propose it.

    Persists nothing. Unlike the duplicate draft there is no record yet to
    count from, so the client (and the project, when the form already has one)
    arrive as query params.
    """
    previous_end, suggested_start = (
        accounting_income_duplicate_service.suggest_next_period_start(
            _optional_id(request, 'client'),
            _optional_id(request, 'project'),
        )
    )
    return Response({
        'previous_period_end': previous_end.isoformat() if previous_end else None,
        'suggested_start': suggested_start.isoformat(),
    })


def _missing_records_error(entity_type, record_ids, *, noun):
    """409 naming every id that vanished, or ``None`` when they all exist.

    A mass edit is confirmed against a named scope, so it runs on that scope
    or not at all: writing the surviving half of a batch the operator never
    agreed to is worse than asking them to look again. Runs BEFORE the
    service, so its atomic block never opens.

    The panel cannot close this window on its own — the confirmation dialog
    freezes the plan when it opens, and the list can be refetched (or another
    session can delete a row) while it sits there. `missing_ids` is what lets
    the UI drop exactly those ids instead of guessing.
    """
    missing = accounting_service.missing_record_ids(entity_type, record_ids)
    if not missing:
        return None
    count = len(missing)
    verb = 'existe' if count == 1 else 'existen'
    return error_response(
        f'{count} de los {noun} seleccionados ya no {verb}.',
        code='records_not_found',
        hint='La lista se actualizó. Revisa la selección y vuelve a intentarlo.',
        status=status.HTTP_409_CONFLICT,
        errors={'missing_ids': missing},
    )


def _collection_account_conflict_error(income_ids, client):
    """409 naming incomes whose EXISTING client is frozen by an active cuenta.

    The bulk mirror of the single-record serializer rule: an emitted (or
    in-flight) cuenta went out in a client's name, so that client only
    changes by anular y reemitir. Completing a missing client is not a
    change — the legacy backlog and the issue-time adoption (which calls
    the service directly) both stay untouched.
    """
    target_pk = client.pk if client else None
    conflicting = sorted(
        IncomeRecord.objects.filter(pk__in=income_ids)
        .exclude(client_id=None)
        .exclude(client_id=target_pk)
        .filter(collection_documents__isnull=False)
        .exclude(
            collection_documents__commercial_status=(
                Document.CommercialStatus.CANCELLED
            ),
        )
        .values_list('pk', flat=True)
        .distinct(),
    )
    if not conflicting:
        return None
    count = len(conflicting)
    noun = 'ingreso' if count == 1 else 'ingresos'
    verb = 'tiene' if count == 1 else 'tienen'
    return error_response(
        f'{count} de los {noun} seleccionados {verb} una cuenta de cobro '
        'activa y no pueden cambiar de cliente.',
        code='records_with_collection_account',
        hint='Anula sus cuentas de cobro y vuelve a emitirlas para '
             'reasignar el cliente.',
        status=status.HTTP_409_CONFLICT,
        errors={'conflicting_ids': conflicting},
    )


def _with_liquid_children(updated):
    """The updated incomes plus the liquid children their cascade rewrote.

    The client/project cascades touch children the operator never selected;
    without them in ``results`` the panel would map-replace the parents and
    keep stale child rows. Children that were already aligned ride along
    harmlessly — an identical replacement is a no-op.
    """
    expected_pks = [
        record.pk for record in updated
        if record.kind == IncomeRecord.Kind.EXPECTED
    ]
    return IncomeRecord.objects.filter(
        Q(pk__in=[record.pk for record in updated])
        | Q(expected_income_id__in=expected_pks),
    )


@api_view(['POST'])
@permission_classes([IsSuperUser])
def bulk_assign_income_client(request):
    """Assign one client to several incomes at once (or clear it with null).

    The completion tool for records created before the client link existed:
    filter by "sin cliente", select the rows and assign in one step.
    """
    serializer = IncomeClientBulkAssignSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    income_ids = serializer.validated_data['income_ids']
    # Before reading `client`, so unlinking is held to the same contract.
    vanished = _missing_records_error(
        EntityType.INCOME, income_ids, noun='ingresos',
    )
    if vanished:
        return vanished
    conflict = _collection_account_conflict_error(
        income_ids, serializer.validated_data.get('client'),
    )
    if conflict:
        return conflict
    updated = accounting_service.bulk_assign_client(
        EntityType.INCOME,
        income_ids,
        serializer.validated_data.get('client'),
        request.user,
        strict_ids=True,
    )
    return Response({
        'updated': len(updated),
        'results': IncomeRecordSerializer(
            _with_liquid_children(updated), many=True,
        ).data,
    })


@api_view(['POST'])
@permission_classes([IsSuperUser])
def bulk_settle_income_records(request):
    """Register one payment (abono) distributed across several expected incomes.

    One pocket movement for the money that entered, one liquid child per
    allocation sharing it. Whatever the allocations leave of the total
    becomes the client's saldo a favor on the same movement.
    """
    serializer = IncomeBulkSettlementSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    income_ids = [
        entry['income_id']
        for entry in serializer.validated_data['allocations']
    ]
    vanished = _missing_records_error(
        EntityType.INCOME, income_ids, noun='ingresos',
    )
    if vanished:
        return vanished
    try:
        result = accounting_settlement_service.bulk_settle_expected_incomes(
            serializer.validated_data, request.user,
        )
    except ValueError as exc:
        return error_response_from_exc(exc)
    results = list(_with_liquid_children(result['incomes']))
    if result['credit'] is not None:
        # Parentless, so _with_liquid_children can't pick it up.
        results.append(result['credit'])
    return Response({
        'updated': len(result['incomes']),
        'results': IncomeRecordSerializer(results, many=True).data,
        'movement': PocketMovementSerializer(result['movement']).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def bulk_assign_hosting_client(request):
    """Assign one client to several hostings at once (or clear it with null).

    Same completion path as incomes: filter by "sin cliente", select the
    rows and assign in one step.
    """
    serializer = HostingClientBulkAssignSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    hosting_ids = serializer.validated_data['hosting_ids']
    vanished = _missing_records_error(
        EntityType.HOSTING, hosting_ids, noun='hostings',
    )
    if vanished:
        return vanished
    updated = accounting_service.bulk_assign_client(
        EntityType.HOSTING,
        hosting_ids,
        serializer.validated_data.get('client'),
        request.user,
        strict_ids=True,
    )
    return Response({
        'updated': len(updated),
        'results': HostingRecordSerializer(updated, many=True).data,
    })


def _project_mismatch_error(model, record_ids, project, *, noun):
    """409 naming every id whose client does not own ``project``.

    Same stale-plan philosophy as `_missing_records_error`: the panel builds
    its plan from rows it already sees as the project's client's, so a
    mismatch here means the selection changed under the open dialog — asking
    the operator to look again beats writing a batch they never confirmed.
    Client-less rows mismatch by definition: without a client there is no
    ownership to satisfy (`validate_project_client_match` is the
    single-record mirror of this rule). Clearing (project=None) skips the
    check — removing a link needs no owner.
    """
    if project is None:
        return None
    mismatched = sorted(
        pk for pk, client_user_id in model.objects.filter(
            pk__in=record_ids,
        ).values_list('pk', 'client__user_id')
        if client_user_id != project.client_id
    )
    if not mismatched:
        return None
    count = len(mismatched)
    verb = 'pertenece' if count == 1 else 'pertenecen'
    return error_response(
        f'{count} de los {noun} seleccionados no {verb} al cliente del '
        'proyecto.',
        code='client_mismatch',
        hint='Asigna primero el cliente correcto: el proyecto debe ser suyo.',
        status=status.HTTP_409_CONFLICT,
        errors={'mismatched_ids': mismatched},
    )


@api_view(['POST'])
@permission_classes([IsSuperUser])
def bulk_assign_income_project(request):
    """Assign one project to several incomes at once (or clear it with null).

    The project-side completion tool (mirror of the client one): filter by
    "sin proyecto", select the rows and assign in one step without leaving
    the accounting list.
    """
    serializer = IncomeProjectBulkAssignSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    income_ids = serializer.validated_data['income_ids']
    project = serializer.validated_data.get('project')
    vanished = _missing_records_error(
        EntityType.INCOME, income_ids, noun='ingresos',
    )
    if vanished:
        return vanished
    mismatch = _project_mismatch_error(
        IncomeRecord, income_ids, project, noun='ingresos',
    )
    if mismatch:
        return mismatch
    updated = accounting_service.bulk_assign_project(
        EntityType.INCOME, income_ids, project, request.user,
    )
    return Response({
        'updated': len(updated),
        'results': IncomeRecordSerializer(
            _with_liquid_children(updated), many=True,
        ).data,
    })


@api_view(['POST'])
@permission_classes([IsSuperUser])
def bulk_assign_hosting_project(request):
    """Assign one project to several hostings at once (or clear it with null).

    Same completion path as incomes; hostings have no settlement children,
    so ``results`` is exactly the updated rows.
    """
    serializer = HostingProjectBulkAssignSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    hosting_ids = serializer.validated_data['hosting_ids']
    project = serializer.validated_data.get('project')
    vanished = _missing_records_error(
        EntityType.HOSTING, hosting_ids, noun='hostings',
    )
    if vanished:
        return vanished
    mismatch = _project_mismatch_error(
        HostingRecord, hosting_ids, project, noun='hostings',
    )
    if mismatch:
        return mismatch
    updated = accounting_service.bulk_assign_project(
        EntityType.HOSTING, hosting_ids, project, request.user,
    )
    return Response({
        'updated': len(updated),
        'results': HostingRecordSerializer(updated, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_income_record(request, record_id):
    return _retrieve_record(request, 'income', record_id)


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_income_record(request, record_id):
    return _update_record(request, 'income', record_id)


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_income_record(request, record_id):
    return _delete_record(request, 'income', record_id)


# ── Expenses ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_expense_records(request):
    return _list_records(request, 'expense')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_expense_record(request):
    return _create_record(request, 'expense')


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_expense_record(request, record_id):
    return _retrieve_record(request, 'expense', record_id)


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_expense_record(request, record_id):
    return _update_record(request, 'expense', record_id)


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_expense_record(request, record_id):
    return _delete_record(request, 'expense', record_id)


# ── Hostings ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_hosting_records(request):
    return _list_records(request, 'hosting')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_hosting_record(request):
    return _create_record(request, 'hosting')


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_hosting_record(request, record_id):
    return _retrieve_record(request, 'hosting', record_id)


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_hosting_record(request, record_id):
    return _update_record(request, 'hosting', record_id)


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_hosting_record(request, record_id):
    return _delete_record(request, 'hosting', record_id)


# ── Hosting cycles (payment history) ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_hosting_cycles(request, record_id):
    hosting = get_object_or_404(HostingRecord, pk=record_id)
    serializer = HostingCycleSerializer(hosting.cycles.all(), many=True)
    return Response({'results': serializer.data})


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_hosting_cycle(request, record_id):
    from content.services import hosting_cycle_service

    hosting = get_object_or_404(HostingRecord, pk=record_id)
    serializer = HostingCycleCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    cycle = hosting_cycle_service.register_cycle_payment(
        hosting, data=serializer.validated_data, user=request.user,
    )
    return Response(
        {
            'cycle': HostingCycleSerializer(cycle).data,
            'hosting': HostingRecordSerializer(hosting).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_hosting_cycle(request, record_id, cycle_id):
    from content.services import hosting_cycle_service

    hosting = get_object_or_404(HostingRecord, pk=record_id)
    cycle = get_object_or_404(hosting.cycles, pk=cycle_id)
    hosting_cycle_service.delete_cycle(hosting, cycle, user=request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── Pocket movements ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_pocket_movements(request):
    return _list_records(request, 'pocket')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_pocket_movement(request):
    return _create_record(request, 'pocket')


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_pocket_movement(request, record_id):
    return _retrieve_record(request, 'pocket', record_id)


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_pocket_movement(request, record_id):
    return _update_record(request, 'pocket', record_id)


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_pocket_movement(request, record_id):
    return _delete_record(request, 'pocket', record_id)


# ── Recurring payments ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_recurring_payments(request):
    return _list_records(request, 'recurring')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_recurring_payment(request):
    return _create_record(request, 'recurring')


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_recurring_payment(request, record_id):
    return _retrieve_record(request, 'recurring', record_id)


@api_view(['GET'])
@permission_classes([IsSuperUser])
def duplicate_recurring_payment_draft(request, record_id):
    payment = get_object_or_404(RecurringPayment, pk=record_id)
    return Response(
        accounting_recurring_service.build_duplicate_draft(payment),
    )


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_recurring_payment(request, record_id):
    return _update_record(request, 'recurring', record_id)


def _recurring_lifecycle_error(exc):
    errors = None
    if getattr(exc, 'record_ids', None):
        errors = {getattr(exc, 'field', 'conflicting_ids'): exc.record_ids}
    return error_response(
        str(exc),
        code=getattr(exc, 'code', None),
        hint=getattr(exc, 'hint', None),
        errors=errors,
        status=status.HTTP_409_CONFLICT,
    )


@api_view(['POST'])
@permission_classes([IsSuperUser])
def set_recurring_payment_state(request, record_id):
    payment = get_object_or_404(RecurringPayment, pk=record_id)
    serializer = RecurringStateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        payment = accounting_recurring_service.set_active(
            payment,
            active=serializer.validated_data['is_active'],
            user=request.user,
        )
    except accounting_recurring_service.RecurringLifecycleError as exc:
        return _recurring_lifecycle_error(exc)
    return Response(RecurringPaymentSerializer(payment).data)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def archive_recurring_payment(request, record_id):
    payment = get_object_or_404(RecurringPayment, pk=record_id)
    payment = accounting_recurring_service.archive(payment, user=request.user)
    return Response(RecurringPaymentSerializer(payment).data)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def restore_recurring_payment(request, record_id):
    payment = get_object_or_404(RecurringPayment, pk=record_id)
    payment = accounting_recurring_service.restore(payment, user=request.user)
    return Response(RecurringPaymentSerializer(payment).data)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def mute_recurring_payment_reminders(request, record_id):
    payment = get_object_or_404(RecurringPayment, pk=record_id)
    serializer = RecurringReminderMuteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        payment = accounting_recurring_service.set_reminder_mute(
            payment,
            muted=serializer.validated_data['muted'],
            until=serializer.validated_data.get('until'),
            user=request.user,
        )
    except accounting_recurring_service.RecurringLifecycleError as exc:
        return _recurring_lifecycle_error(exc)
    return Response(RecurringPaymentSerializer(payment).data)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def bulk_recurring_payment_action(request):
    serializer = RecurringBulkActionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        updated = accounting_recurring_service.bulk_apply(
            serializer.validated_data['recurring_ids'],
            action=serializer.validated_data['action'],
            user=request.user,
        )
    except accounting_recurring_service.RecurringLifecycleError as exc:
        return _recurring_lifecycle_error(exc)
    return Response({
        'updated': len(updated),
        'results': RecurringPaymentSerializer(updated, many=True).data,
    })


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_recurring_payment(request, record_id):
    payment = get_object_or_404(RecurringPayment, pk=record_id)
    if not payment.is_archived:
        return error_response(
            'Un pago recurrente vigente no se puede eliminar definitivamente.',
            code='recurring_archive_required',
            hint='Archívalo primero para conservar una recuperación segura.',
            status=status.HTTP_409_CONFLICT,
        )
    return _delete_record(request, 'recurring', record_id)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def reorder_recurring_payments(request):
    """Persist the manual order the operator dragged into place.

    Body: {"items": [{"id": 5, "category": 3, "order": 0}, ...]}

    Each item carries its category because a drag can move a row *between*
    groups, not just within one. Unknown ids are ignored so a stale tab
    cannot 404 the whole batch.

    Deliberately does not write an AccountingChangeLog entry: dragging rows
    around is presentation, and logging it would bury the real edits.
    """
    items = request.data.get('items', [])
    if not isinstance(items, list):
        return error_response(
            'Debe ser una lista.',
            code='invalid_reorder_payload',
            status=status.HTTP_400_BAD_REQUEST,
        )

    by_id = {}
    for item in items:
        if not isinstance(item, dict):
            return error_response(
                'Cada elemento debe ser un objeto con id, category y order.',
                code='invalid_reorder_payload',
                status=status.HTTP_400_BAD_REQUEST,
            )
        by_id[item.get('id')] = item

    payments = RecurringPayment.objects.filter(pk__in=[k for k in by_id if k is not None])
    valid_category_ids = set(
        RecurringCategory.objects.values_list('pk', flat=True)
    )

    updated = []
    for payment in payments:
        item = by_id[payment.pk]
        try:
            payment.order = int(item.get('order') or 0)
        except (TypeError, ValueError):
            return error_response(
                'El orden debe ser un número entero.',
                code='invalid_reorder_payload',
                status=status.HTTP_400_BAD_REQUEST,
            )
        if 'category' in item:
            category_id = item['category']
            if category_id is not None and category_id not in valid_category_ids:
                return error_response(
                    'La categoría indicada no existe.',
                    code='unknown_category',
                    status=status.HTTP_400_BAD_REQUEST,
                )
            payment.category_id = category_id
        updated.append(payment)

    with transaction.atomic():
        RecurringPayment.objects.bulk_update(updated, ['category', 'order'])

    return Response({'reordered': len(updated)})


# ── Ads spend ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_ads_spend_records(request):
    return _list_records(request, 'ads')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_ads_spend_record(request):
    return _create_record(request, 'ads')


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_ads_spend_record(request, record_id):
    return _retrieve_record(request, 'ads', record_id)


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_ads_spend_record(request, record_id):
    return _update_record(request, 'ads', record_id)


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_ads_spend_record(request, record_id):
    return _delete_record(request, 'ads', record_id)


# ── Credit-card catalog ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_credit_cards(request):
    return _list_records(request, 'credit_card')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_credit_card(request):
    return _create_record(request, 'credit_card')


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_credit_card(request, record_id):
    return _retrieve_record(request, 'credit_card', record_id)


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_credit_card(request, record_id):
    return _update_record(request, 'credit_card', record_id)


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_credit_card(request, record_id):
    """Delete a catalog card unless history references its name.

    Snapshots/statements keep plain-string card names; deleting a card
    they reference would orphan that history in the UI filters, so the
    card must be deactivated instead.
    """
    instance = get_object_or_404(CreditCard, pk=record_id)
    referenced = (
        CardBalanceSnapshot.objects.filter(card_name=instance.name).exists()
        or CreditCardStatement.objects.filter(card_name=instance.name).exists()
    )
    if referenced:
        return error_response(
            'La tarjeta tiene registros o extractos asociados; '
            'desactívala en lugar de eliminarla.',
            code='credit_card_referenced',
        )
    return _delete_record(request, 'credit_card', record_id)


# ── Card snapshots ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_card_snapshots(request):
    return _list_records(request, 'card_snapshot')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_card_snapshot(request):
    return _create_record(request, 'card_snapshot')


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_card_snapshot(request, record_id):
    return _retrieve_record(request, 'card_snapshot', record_id)


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_card_snapshot(request, record_id):
    return _update_record(request, 'card_snapshot', record_id)


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_card_snapshot(request, record_id):
    return _delete_record(request, 'card_snapshot', record_id)


# ── Change log (paginated) ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_accounting_change_logs(request):
    """Audit trail, paginated 20 per page (it grows unbounded)."""
    params = request.query_params
    try:
        logs = accounting_history_service.change_log_queryset(params)
    except ValueError as exc:
        return error_response_from_exc(exc)

    return _paginated_history_response(
        logs, params, AccountingChangeLogSerializer,
    )


# ── Notification recipients ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_notification_recipients(request):
    return _list_records(request, 'notification_recipient')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_notification_recipient(request):
    return _create_record(request, 'notification_recipient')


@api_view(['GET'])
@permission_classes([IsSuperUser])
def retrieve_notification_recipient(request, record_id):
    return _retrieve_record(request, 'notification_recipient', record_id)


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_notification_recipient(request, record_id):
    return _update_record(request, 'notification_recipient', record_id)


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def delete_notification_recipient(request, record_id):
    return _delete_record(request, 'notification_recipient', record_id)


# ── Email send log (paginated) ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_accounting_email_logs(request):
    """Which addresses each automated email of the module went out to.

    Scoped to the module's own template keys so the proposal traffic that
    shares the EmailLog table stays out. Paginated 20 per page like the
    change log — it grows unbounded.
    """
    params = request.query_params
    try:
        logs = accounting_history_service.email_log_queryset(params)
    except ValueError as exc:
        return error_response_from_exc(exc)

    return _paginated_history_response(
        logs.prefetch_related('targets'), params, EmailLogSerializer,
        row_enricher=attach_delivery_copies,
    )


@api_view(['GET'])
@permission_classes([IsSuperUser])
def accounting_email_log_body(request, log_id):
    """The message as it went out.

    The history exists to diagnose, and without the body it can only confirm
    that something was sent, not what. Scoped to the module's own notices so
    this never becomes a reader for the proposal traffic sharing the table.
    """
    log = get_object_or_404(
        EmailLog.objects.select_related('body'),
        id=log_id,
        template_key__in=EMAIL_TEMPLATE_LABELS,
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
    )
    return email_body_response(log)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def retry_accounting_email_log(request, log_id):
    """Re-send a failed notice to the address on the row, and only to it."""
    log = get_object_or_404(
        EmailLog,
        id=log_id,
        template_key__in=EMAIL_TEMPLATE_LABELS,
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
    )
    try:
        attempt = accounting_email_retry_service.retry_send(log)
    except accounting_email_retry_service.RetryError as exc:
        return error_response(str(exc))
    return Response(EmailLogSerializer(attempt).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def accounting_history_tab_counts(request):
    """How many rows each tab of the strip would show.

    The other accounting views count their tabs in the browser over the rows
    they already loaded; Historial is the one that paginates server-side, so
    an honest badge — including the (0) — has to be asked for.

    One COUNT per tab rather than a single conditional aggregate: the send
    log joins its targets, so a digest naming fifty records would fan the
    joined rowset out fifty times under a shared aggregate. Each count is an
    indexed lookup, and the specs are capped.
    """
    scope = request.data.get('scope')
    tabs = request.data.get('tabs')
    if not isinstance(tabs, list):
        return error_response("El parámetro 'tabs' debe ser una lista.")
    if len(tabs) > MAX_TAB_COUNT_SPECS:
        return error_response(
            f'Máximo {MAX_TAB_COUNT_SPECS} pestañas por consulta.',
        )

    counts = {}
    for spec in tabs:
        if not isinstance(spec, dict) or spec.get('id') in (None, ''):
            continue
        try:
            queryset = accounting_history_service.queryset_for(
                scope, spec.get('filters') or {},
            )
        except ValueError as exc:
            return error_response_from_exc(exc)
        counts[str(spec['id'])] = queryset.count()

    return Response({'counts': counts})


# ── Settings ──

@api_view(['GET'])
@permission_classes([IsSuperUser])
def get_accounting_settings(request):
    return Response(
        AccountingSettingsSerializer(AccountingSettings.load()).data,
    )


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_accounting_settings(request):
    instance = AccountingSettings.load()
    serializer = AccountingSettingsSerializer(
        instance, data=request.data, partial=True,
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        instance = accounting_service.update_record(
            EntityType.SETTINGS, instance, serializer, request.user,
        )
    except ValueError as exc:
        return error_response_from_exc(exc)
    return Response(AccountingSettingsSerializer(instance).data)
