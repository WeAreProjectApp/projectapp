"""Expected-income plans and guarded writes through the panel's accounting pipeline."""
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Q
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from accounts.retention import READ_ONLY_MESSAGE
from accounts.services.billing_locks import lock_billing_rows
from content.models import Document, ExpenseRecord, IncomeRecord, Ledger, RecurringPayment
from content.serializers.accounting import (
    FlexiblePeriodField,
    IncomeRecordCreateUpdateSerializer,
    MONTH_PERIOD_RE,
    money_str,
    payment_status_for,
    split_half,
)
from content.services import accounting_income_duplicate_service as duplicate_service
from content.services import accounting_service
from content.services.accounting_income_detail_service import income_detail_queryset
from content.services.accounting_vat import vat_breakdown

INCOME_FIELDS = (
    'concept', 'total_amount', 'base_amount', 'vat_rate', 'vat_amount',
    'gustavo_amount', 'carlos_amount', 'company_amount', 'destination', 'ledger',
    'period', 'period_date', 'period_start', 'period_end', 'period_cadence',
    'origin', 'client', 'project', 'collection_confidence', 'notes',
)
STATE_FIELDS = (
    'concept', 'kind', 'ledger', 'client', 'project', 'origin',
    'is_receivable_candidate', 'collection_confidence', 'period_date',
    'period_start', 'period_end', 'period_cadence', 'destination', 'total_amount',
    'vat_rate', 'gustavo_amount', 'carlos_amount', 'expected_income', 'notes',
    'retention_context',
)
MONEY_FIELDS = frozenset({
    'total_amount', 'base_amount', 'vat_amount', 'vat_rate',
    'gustavo_amount', 'carlos_amount', 'company_amount',
})
SPLIT_FIELDS = frozenset({'gustavo_amount', 'carlos_amount', 'company_amount'})
CONFIRMATION_FIELDS = (
    'total_amount', 'vat_rate', 'gustavo_amount', 'carlos_amount',
    'company_amount', 'ledger', 'client', 'project',
)
FINANCIAL_FIELDS = tuple(sorted(MONEY_FIELDS | {'ledger', 'client', 'project'}))
LABELS = {
    **dict(accounting_service.TRACKED_FIELDS[accounting_service.EntityType.INCOME]),
    'company_amount': 'Monto empresa', 'base_amount': 'Base antes de IVA',
    'vat_amount': 'Monto IVA', 'retention_context': 'Datos conservados',
}


class ExpectedIncomeError(Exception):
    def __init__(self, message, *, code, details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def json_safe(value):
    """Return canonical values suitable for previews and confirmation JSONFields."""
    if isinstance(value, Decimal):
        return money_str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, 'pk'):
        return value.pk
    return value


def _invalid(reason, message, **details):
    raise ExpectedIncomeError(
        message, code='VALIDATION_ERROR',
        details=json_safe({'reason': reason, **details}),
    )


def with_income_relations(queryset):
    """Batch relation reads for editability without a query per list row."""
    return queryset.prefetch_related(
        Prefetch('liquid_records', queryset=IncomeRecord.objects.filter(kind='liquid')
                 .only('pk', 'expected_income_id', 'total_amount'), to_attr='_expected_payments'),
        Prefetch('deduction_records', queryset=ExpenseRecord.objects
                 .only('pk', 'source_income_id', 'total_amount', 'deduction_type'), to_attr='_expected_deductions'),
        Prefetch('collection_documents', queryset=Document.objects.exclude(commercial_status='cancelled')
                 .only('pk', 'income_record_id', 'commercial_status', 'total'), to_attr='_expected_documents'),
    )


def load_expected_income(income_id):
    try:
        income = with_income_relations(income_detail_queryset()).get(pk=income_id)
    except IncomeRecord.DoesNotExist as exc:
        raise ExpectedIncomeError(
            'No existe ese ingreso esperado.', code='NOT_FOUND', details={'income_id': income_id},
        ) from exc
    if income.kind != IncomeRecord.Kind.EXPECTED:
        raise ExpectedIncomeError(
            'El registro no es un ingreso esperado.', code='NOT_EXPECTED_INCOME',
            details={'income_id': income.pk, 'kind': income.kind,
                     'expected_income_id': income.expected_income_id},
        )
    return income


def _stored_state(income):
    state = {}
    for field in STATE_FIELDS:
        model_field = income._meta.get_field(field)
        state[field] = getattr(income, model_field.attname)
    return state


def income_etag(income):
    """Hash the row and current dependencies, even if updated_at stayed unchanged."""
    state = _stored_state(income)
    for field in ('client', 'project', 'expected_income', 'retention_context'):
        state[f'{field}_id'] = state.pop(field)
    payload = {
        'id': income.pk, **state,
        'payments': list(income.liquid_records.filter(kind='liquid').order_by('pk')
                         .values('pk', 'total_amount')),
        'deductions': list(income.deduction_records.order_by('pk').values('pk', 'total_amount')),
        'collection_documents': list(income.collection_documents.exclude(commercial_status='cancelled')
                                     .order_by('pk').values('pk', 'commercial_status', 'total')),
    }
    encoded = json.dumps(json_safe(payload), sort_keys=True, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def check_etag(income, expected):
    current = income_etag(income)
    if expected is not None and expected != current:
        raise ExpectedIncomeError(
            'El ingreso esperado cambió desde la lectura o la vista previa.', code='STALE_VERSION',
            details={'income_id': income.pk, 'expected': expected, 'current': current},
        )
    return current


def _relations(income, attribute, fallback):
    return getattr(income, attribute) if hasattr(income, attribute) else list(fallback())


def income_editability(income):
    payments = _relations(income, '_expected_payments',
                          lambda: income.liquid_records.filter(kind='liquid'))
    deductions = _relations(income, '_expected_deductions', lambda: income.deduction_records.all())
    documents = _relations(income, '_expected_documents',
                           lambda: income.collection_documents.exclude(commercial_status='cancelled'))
    paid = sum((row.total_amount for row in payments), Decimal('0'))
    deducted = sum((row.total_amount for row in deductions if row.deduction_type), Decimal('0'))
    blockers = []
    if income.retention_context_id:
        blockers.append({'code': 'retained_data', 'message': READ_ONLY_MESSAGE,
                         'locks': sorted(set(INCOME_FIELDS) | set(STATE_FIELDS) | MONEY_FIELDS)})
    for code, message, condition in (
        ('payments', 'El ingreso esperado ya tiene pagos registrados.', paid > 0),
        ('deductions', 'El ingreso esperado ya tiene deducciones registradas.', deducted > 0),
        ('settled', 'El ingreso esperado ya está completamente pagado.',
         payment_status_for(paid + deducted, income.total_amount) == 'paid'),
        ('issued_collection_account', 'El ingreso esperado tiene una cuenta de cobro emitida o pagada.',
         any(row.commercial_status in ('issued', 'paid') for row in documents)),
    ):
        if condition:
            blockers.append({'code': code, 'message': message, 'locks': list(FINANCIAL_FIELDS)})
    return {
        'blockers': blockers,
        'locked_fields': sorted({field for blocker in blockers for field in blocker['locks']}),
        'confirmation_fields': list(CONFIRMATION_FIELDS),
    }


def _normalize_fields(fields):
    normalized = dict(fields)
    unknown = set(normalized) - set(INCOME_FIELDS)
    if unknown:
        raise serializers.ValidationError({
            key: ErrorDetail('Campo desconocido para esta herramienta.', code='unknown_field')
            for key in sorted(unknown)
        })
    for key in MONEY_FIELDS & normalized.keys():
        if key == 'vat_rate':
            field = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'),
                                             max_value=Decimal('100'), allow_null=True)
        else:
            field = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
        try:
            normalized[key] = field.run_validation(normalized[key])
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({key: exc.detail}) from exc
    for key in ('period_date', 'period_start', 'period_end'):
        if key in normalized:
            field = (serializers.DateField(allow_null=True) if key == 'period_end'
                     else FlexiblePeriodField(allow_null=key != 'period_date'))
            try:
                normalized[key] = field.run_validation(normalized[key])
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({key: exc.detail}) from exc
    if 'period' in normalized:
        period = normalized.pop('period')
        if not isinstance(period, str) or not MONTH_PERIOD_RE.fullmatch(period):
            # Validate the alias separately: it represents a month, never an exact day.
            _invalid('invalid_period', 'El período debe tener formato AAAA-MM.')
        period_date = FlexiblePeriodField().run_validation(period)
        if 'period_date' in normalized and normalized['period_date'].replace(day=1) != period_date:
            _invalid('period_mismatch', 'El período y la fecha de cobro deben pertenecer al mismo mes.')
        normalized.setdefault('period_date', period_date)
    if 'destination' in normalized and normalized['destination'] != 'partners':
        _invalid('invalid_destination', 'Un ingreso esperado sólo puede tener destino Socios.')
    return normalized


def _normalize_vat(fields, income, write):
    if income is None and 'vat_rate' not in fields:
        _invalid('vat_rate_required', 'Indica vat_rate; usa null si el IVA no está registrado.')
    rate = fields.get('vat_rate', income.vat_rate if income else None)
    if rate is None and {'base_amount', 'vat_amount'} & fields.keys():
        _invalid('vat_rate_required', 'Define el IVA antes de enviar la base o el monto de IVA.')
    if 'total_amount' in fields:
        amount, mode = fields['total_amount'], 'vat_included'
    elif 'base_amount' in fields:
        amount, mode = fields['base_amount'], 'before_vat'
    elif 'vat_amount' in fields or income is None:
        _invalid('needs_base_or_total', 'Envía total_amount o base_amount para calcular el ingreso esperado.')
    else:
        amount, mode = income.total_amount, 'vat_included'
    try:
        base, vat, total = vat_breakdown(amount, rate, mode)
    except ValueError as exc:
        _invalid('invalid_vat', str(exc))
    expected = {'vat_rate': rate, 'base_amount': base, 'vat_amount': vat, 'total_amount': total}
    mismatch = any(key in fields and fields[key] != expected[key] for key in ('base_amount', 'vat_amount'))
    if all(key in fields for key in ('base_amount', 'vat_amount', 'total_amount')):
        mismatch |= fields['base_amount'] + fields['vat_amount'] != fields['total_amount']
    if mismatch:
        _invalid('vat_mismatch', 'La base, el IVA y el total no coinciden.', expected=expected)
    if {'total_amount', 'base_amount'} & fields.keys():
        write['total_amount'] = total
    write.pop('base_amount', None)
    write.pop('vat_amount', None)
    return total


def _split_suggestion(total):
    gustavo, carlos = split_half(total)
    return {'gustavo_amount': gustavo, 'carlos_amount': carlos, 'company_amount': total - gustavo - carlos}


def _normalize_split(fields, income, write, total):
    sent = SPLIT_FIELDS & fields.keys()
    ledger = fields.get('ledger', income.ledger if income else Ledger.COMPANY)
    stored = (income.gustavo_amount, income.carlos_amount) if income else (Decimal('0'), Decimal('0'))
    notices, warnings, message = [], [], ''
    if ledger in (Ledger.GUSTAVO, Ledger.CARLOS):
        gustavo, carlos = (total, Decimal('0')) if ledger == Ledger.GUSTAVO else (Decimal('0'), total)
        expected = {'gustavo_amount': gustavo, 'carlos_amount': carlos, 'company_amount': Decimal('0')}
        if any(fields[key] != expected[key] for key in sent):
            _invalid('personal_ledger_split', 'Un ingreso personal debe asignarse al 100 % a su dueño.',
                     expected=expected)
        write.update(gustavo_amount=gustavo, carlos_amount=carlos)
        rule = 'personal_ledger'
    elif sent:
        if sent == {'company_amount'}:
            _invalid('needs_partner_amount', 'Indica el monto de al menos un socio junto al monto de empresa.')
        gustavo, carlos = fields.get('gustavo_amount', stored[0]), fields.get('carlos_amount', stored[1])
        if 'company_amount' in sent:
            company = fields['company_amount']
            if sent == SPLIT_FIELDS and gustavo + carlos + company != total:
                _invalid('split_mismatch', 'El reparto debe sumar exactamente el monto total.',
                         total=total, sum=gustavo + carlos + company)
            if 'gustavo_amount' not in sent:
                gustavo = total - company - carlos
            elif 'carlos_amount' not in sent:
                carlos = total - company - gustavo
            if gustavo < 0 or carlos < 0:
                _invalid('split_mismatch', 'El reparto produciría un monto negativo.', total=total,
                         sum=fields.get('gustavo_amount', Decimal('0'))
                         + fields.get('carlos_amount', Decimal('0')) + company)
        elif income is None and sent != {'gustavo_amount', 'carlos_amount'}:
            _invalid('partner_amount_missing', 'Al crear, indica los montos de ambos socios.')
        write.update(gustavo_amount=gustavo, carlos_amount=carlos)
        rule = 'explicit'
    elif income is None or total != income.total_amount or ledger != income.ledger:
        if (
            income is None
            or (ledger == Ledger.COMPANY and income.ledger in (Ledger.GUSTAVO, Ledger.CARLOS))
            or stored == split_half(income.total_amount)
        ):
            gustavo, carlos = split_half(total)
            company = total - gustavo - carlos
            rule = 'panel_auto'
            prefix = 'Reparto calculado' if income is None else 'Reparto recalculado'
            message = (f'{prefix} con la regla del Panel: Gustavo {money_str(gustavo)}, '
                       f'Carlos {money_str(carlos)}, empresa {money_str(company)}.')
            notices.append({'code': 'panel_auto', 'message': message})
            write.update(gustavo_amount=gustavo, carlos_amount=carlos)
        else:
            gustavo, carlos = stored
            rule = 'kept_custom'
            message = 'Se conserva el reparto personalizado del Panel.'
            warnings.append({'code': 'custom_split_kept', 'message': message,
                             'company_amount': money_str(total - gustavo - carlos)})
    else:
        gustavo, carlos = stored
        rule = 'unchanged'
    if gustavo + carlos > total:
        _invalid('split_exceeds_total', 'Los montos de los socios superan el nuevo total.',
                 total=total, sum=gustavo + carlos, suggestion=_split_suggestion(total))
    write.pop('company_amount', None)
    return {'rule': rule, 'gustavo': money_str(gustavo), 'carlos': money_str(carlos),
            'company': money_str(total - gustavo - carlos), 'message': message}, notices, warnings


def _state_with_derived(state):
    result = dict(state)
    total = result['total_amount']
    result['company_amount'] = total - result['gustavo_amount'] - result['carlos_amount']
    base, vat, _ = vat_breakdown(total, result['vat_rate'])
    result.update(base_amount=base, vat_amount=vat)
    return json_safe(result)


def compact_state(state, *, income_id=None):
    result = {key: value for key, value in state.items()
              if key not in ('retention_context', 'expected_income')}
    result['id'] = income_id
    result['client_id'] = result.pop('client')
    result['project_id'] = result.pop('project')
    result['period'] = result['period_date'][:7] if result['period_date'] else None
    return result


def _check_blockers(income, before, after, *, financial_only=False):
    editability = income_editability(income)
    changed = {key for key in after if before.get(key) != after[key]}
    if financial_only:
        changed &= set(FINANCIAL_FIELDS)
    blocked = sorted(changed & set(editability['locked_fields']))
    if blocked:
        raise ExpectedIncomeError(
            'El ingreso esperado tiene datos bloqueados para este cambio.', code='INCOME_LOCKED',
            details={'income_id': income.pk, 'blockers': editability['blockers'], 'blocked_fields': blocked},
        )
    return editability


def _possible_duplicates(after):
    period = date.fromisoformat(after['period_date'])
    matching = Q(period_date__year=period.year, period_date__month=period.month)
    if after['period_start'] and after['period_end']:
        matching |= Q(period_start__lte=after['period_end'], period_end__gte=after['period_start'])
    return list(IncomeRecord.objects.filter(
        matching, kind='expected', client_id=after['client'], project_id=after['project'],
    ).order_by('pk').values_list('pk', flat=True)[:5])


def build_change_plan(fields, *, income=None, if_match=None):
    """Dry-run the panel serializer and expose its full, validated before/after."""
    etag = check_etag(income, if_match) if income is not None else None
    normalized = _normalize_fields(fields)
    write = dict(normalized)
    if income is None:
        write.update(kind='expected')
        write.setdefault('destination', 'partners')
        write.setdefault('ledger', 'company')
    total = _normalize_vat(normalized, income, write)
    split, notices, warnings = _normalize_split(normalized, income, write, total)
    previous = _stored_state(income) if income is not None else _stored_state(IncomeRecord())
    before = _state_with_derived(previous) if income is not None else None
    editability = None
    if income is not None:
        # Block domain changes before serializer guards can replace their error code.
        proposed = {**previous, **write}
        if 'client' in write and write['client'] != income.client_id and 'project' not in write:
            proposed['project'] = None
        editability = _check_blockers(income, before, _state_with_derived(proposed), financial_only=True)
    serializer = IncomeRecordCreateUpdateSerializer(instance=income, data=write, partial=income is not None)
    serializer.is_valid(raise_exception=True)
    effective = {**previous, **serializer.validated_data}
    effective = {key: json_safe(value) if hasattr(value, 'pk') else value for key, value in effective.items()}
    after = _state_with_derived(effective)
    if income is not None:
        editability = _check_blockers(income, before, after)
    changes = [
        {'field': key, 'label': LABELS.get(key, key), 'before': (before or {}).get(key), 'after': value}
        for key, value in after.items() if (before or {}).get(key) != value
    ]
    changed = {row['field'] for row in changes}
    if editability and editability['blockers'] and changes:
        warnings.append({'code': 'financial_fields_locked',
                         'message': 'Se permite el cambio descriptivo; los datos financieros permanecen bloqueados.',
                         'blockers': editability['blockers']})
    if income is not None and changed & MONEY_FIELDS:
        documents = _relations(income, '_expected_documents',
                               lambda: income.collection_documents.exclude(commercial_status='cancelled'))
        if any(row.commercial_status == 'draft' for row in documents):
            warnings.append({'code': 'draft_collection_account',
                             'message': 'Existe una cuenta de cobro en borrador; revisa sus importes antes de emitirla.'})
    if after['period_start'] and after['period_end'] and not (
        after['period_start'] <= after['period_date'] <= after['period_end']
    ):
        warnings.append({'code': 'billing_date_outside_window',
                         'message': 'La fecha de cobro está fuera del período de servicio cubierto.'})
    if income is None:
        duplicates = _possible_duplicates(after)
        if duplicates:
            warnings.append({'code': 'possible_duplicate', 'income_ids': duplicates,
                             'message': 'Ya hay ingresos esperados del mismo cliente y proyecto en ese período.'})
    return {
        'fields': json_safe(normalized), 'serializer': serializer, 'etag': etag,
        'before': compact_state(before, income_id=income.pk) if before else None,
        'after': compact_state(after, income_id=income.pk if income else None),
        'changes': changes, 'needs_confirmation': income is None or bool(changed & set(CONFIRMATION_FIELDS)),
        'requires_confirmation_because': sorted(changed & set(CONFIRMATION_FIELDS)),
        'split': split, 'vat': {key: after[key] for key in ('vat_rate', 'base_amount', 'vat_amount', 'total_amount')},
        'notices': notices, 'warnings': warnings,
    }


def apply_update(income_id, fields, *, expected_etag, actor):
    """Re-plan under the panel's Project -> Income -> Document lock order."""
    try:
        with transaction.atomic():
            lock_billing_rows(income_ids=[income_id], project_ids=[fields.get('project')],
                              include_income_children=True, include_origin_documents=True)
            income = load_expected_income(income_id)
            plan = build_change_plan(fields, income=income, if_match=expected_etag)
            if not plan['changes']:
                return income
            return accounting_service.update_record(
                accounting_service.EntityType.INCOME, income, plan['serializer'], actor,
            )
    except ValueError as exc:
        _invalid(getattr(exc, 'code', None) or 'accounting_update_rejected', str(exc), reason_message=str(exc))


def apply_create(fields, *, actor):
    try:
        plan = build_change_plan(fields)
        return accounting_service.create_record(accounting_service.EntityType.INCOME, plan['serializer'], actor)
    except ValueError as exc:
        _invalid(getattr(exc, 'code', None) or 'accounting_create_rejected', str(exc), reason_message=str(exc))


def apply_duplicate(income_id, fields, *, expected_etag, actor):
    """Keep the confirmed source stable until the accounting create completes."""
    with transaction.atomic():
        lock_billing_rows(income_ids=[income_id], project_ids=[fields.get('project')],
                          include_income_children=True, include_origin_documents=True)
        check_etag(load_expected_income(income_id), expected_etag)
        return apply_create(fields, actor=actor)


def build_duplicate_fields(source, overrides):
    draft = duplicate_service.build_income_duplicate_draft(source)
    overrides = _normalize_fields(overrides)
    fields = {key: value for key, value in draft.items() if key in INCOME_FIELDS}
    if {'total_amount', 'base_amount', 'ledger'} & overrides.keys() and not SPLIT_FIELDS & overrides.keys():
        for key in SPLIT_FIELDS:
            fields.pop(key, None)
    if 'base_amount' in overrides and 'total_amount' not in overrides:
        fields.pop('total_amount', None)
    fields.update(overrides)
    start = FlexiblePeriodField(allow_null=True).run_validation(fields.get('period_start'))
    if 'period_start' in overrides and 'period_date' not in overrides and start:
        fields['period_date'] = duplicate_service.next_billing_date(source, start)
    if start and 'period_end' not in overrides:
        months = RecurringPayment.FREQUENCY_MONTHS.get(fields.get('period_cadence'))
        if months:
            fields['period_end'] = duplicate_service.add_months(start, months) - timedelta(days=1)
    if fields.get('origin') == 'hosting' and not (
        start and fields.get('period_end') and fields.get('period_date')
    ):
        _invalid('billing_window_required', 'Completa la ventana y la fecha de cobro del ingreso esperado de hosting.',
                 cycle_options=draft['cycle_options'], period_anchor=draft['period_anchor'])
    return json_safe(fields)
