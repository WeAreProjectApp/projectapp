"""
Tool registry for the Accounting MCP connector (módulo contable).

Exposes the personal-ledger accounting panel (/panel/accounting) over MCP:
per-ledger CRUD for the 7 record types, plus the dashboard summary, the audit
change-log, and settings.

This module is table-driven in the panel by `_ENTITIES` + `_apply_filters`
(content/views/accounting.py). The MCP reuses those exact structures and always
routes writes through `accounting_service.create_record/update_record/
delete_record` so the audit trail, notifications and pocket side-effects fire
identically to the panel.

Guardrails (mirror the panel):
- Every accounting endpoint is superuser-only; writes are attributed to the MCP
  actor (see content.mcp.actor), which must be an active superuser.
- Auto-managed pocket movements (income/expense-backed) are not editable or
  deletable — the service raises, and we surface it as ToolError.
- Split invariants are validated by the write serializer + model.
- This is sensitive financial data with a partner split; keep the connector
  inactive until you deliberately issue a token.

Each entry: {'name', 'description', 'input_schema', 'handler'}.
"""
from accounts.models import Project
from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError
from content.mcp.schema_policy import closed_object, close_root_schemas
from content.models import (
    AccountingChangeLog,
    AccountingSettings,
    ExpenseRecord,
    IncomeRecord,
)
from content.serializers.accounting import (
    AccountingChangeLogSerializer,
    AccountingSettingsSerializer,
    ExpenseRecordSerializer,
    IncomeBulkSettlementSerializer,
    IncomeRecordSerializer,
    IncomeSettlementSerializer,
    PocketMovementSerializer,
    RecurringBulkActionSerializer,
    RecurringPaymentSerializer,
    RecurringReminderMuteSerializer,
    RecurringStateSerializer,
)
from content.services import (
    accounting_income_detail_service,
    accounting_recurring_service,
    accounting_service,
    accounting_settlement_service,
    income_payment_confirmation_service,
)
from content.utils import today_bogota
from content.views.accounting import (
    EntityType,
    _ENTITIES,
    _apply_filters,
    _parse_date,
    base_queryset,
)


def _serializer_errors_to_message(errors):
    import json
    return 'Datos inválidos: ' + json.dumps(errors, ensure_ascii=False, default=str)


def _str_params(arguments):
    """Coerce MCP arguments to the string form `_apply_filters` expects.

    The panel filters read query-string params: numbers arrive as strings and
    booleans as the literals 'true'/'false'. Normalize accordingly and drop
    None so unspecified filters are skipped.
    """
    params = {}
    for key, value in arguments.items():
        if value is None:
            continue
        if isinstance(value, bool):
            params[key] = 'true' if value else 'false'
        else:
            params[key] = str(value)
    return params


def _get_instance_or_error(key, record_id):
    model = _ENTITIES[key]['model']
    try:
        return model.objects.get(pk=int(record_id))
    except (model.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe un registro {key} con id={record_id}.')


# ── Generic per-ledger handlers (bound to a key via closures) ────────────────

def _make_list(key):
    def handler(arguments):
        config = _ENTITIES[key]
        # base_queryset applies the entity's read annotations (e.g. income's
        # paid_amount) and its select/prefetch joins: without the annotations a
        # payment_status filter raises FieldError and the serializer falls back
        # to one aggregate per row.
        queryset = base_queryset(config)
        params = _str_params(arguments)
        try:
            queryset = _apply_filters(queryset, params, config)
            meta = config.get('meta', lambda qs, p: {})(queryset, params)
        except ValueError as exc:
            raise ToolError(str(exc))
        if config.get('with_accumulated'):
            records = accounting_service.ads_with_accumulated(queryset)
        else:
            records = queryset
        data = config['read'](records, many=True).data
        return {'count': len(data), 'results': data, 'meta': meta}
    return handler


def _make_get(key):
    def handler(arguments):
        instance = _get_instance_or_error(key, arguments.get('record_id'))
        return _ENTITIES[key]['read'](instance).data
    return handler


def _resolve_project_reference(key, data, instance=None):
    """Turn a ``project_name`` alias into the ``project`` FK, in place.

    ``project_name`` is read-only on the models (a property over the FK), so
    the write serializer would silently drop it — the bug that left MCP-created
    hostings with no project. The alias is resolved against the record's
    client and always removed from the payload; anything unresolvable is a
    loud ToolError, never a silent discard. An explicit ``project`` id wins
    over the alias (documented in the schema).
    """
    if key not in ('income', 'hosting'):
        return data
    raw_name = data.pop('project_name', None)
    name = (raw_name or '').strip() if isinstance(raw_name, str) else ''
    if not name or data.get('project') is not None:
        return data
    client_id = data.get('client')
    if client_id is None and instance is not None:
        client_id = instance.client_id
    if client_id is None:
        raise ToolError(
            "Para resolver 'project_name' se necesita el 'client' del "
            "registro: el proyecto pertenece a un cliente."
        )
    matches = list(
        Project.objects.filter(
            client__profile__id=client_id, name__iexact=name,
        )[:2],
    )
    if not matches:
        raise ToolError(
            f"Ese cliente no tiene un proyecto llamado '{name}'. "
            "Créalo primero o pasa 'project' (id)."
        )
    if len(matches) > 1:
        raise ToolError(
            f"Ese cliente tiene más de un proyecto llamado '{name}'; "
            "usa 'project' (id) para elegir uno."
        )
    data['project'] = matches[0].pk
    return data


def _make_create(key):
    def handler(arguments):
        config = _ENTITIES[key]
        data = {k: v for k, v in arguments.items() if k != 'record_id'}
        data = _resolve_project_reference(key, data)
        serializer = config['write'](data=data)
        if not serializer.is_valid():
            raise ToolError(_serializer_errors_to_message(serializer.errors))
        try:
            instance = accounting_service.create_record(
                config['entity_type'], serializer, mcp_actor(),
            )
        except ValueError as exc:
            raise ToolError(str(exc))
        return config['read'](instance).data
    return handler


def _make_update(key):
    def handler(arguments):
        config = _ENTITIES[key]
        instance = _get_instance_or_error(key, arguments.get('record_id'))
        data = {k: v for k, v in arguments.items() if k != 'record_id'}
        data = _resolve_project_reference(key, data, instance=instance)
        if not data:
            raise ToolError('No se indicó ningún campo para actualizar.')
        serializer = config['write'](instance, data=data, partial=True)
        if not serializer.is_valid():
            raise ToolError(_serializer_errors_to_message(serializer.errors))
        try:
            instance = accounting_service.update_record(
                config['entity_type'], instance, serializer, mcp_actor(),
            )
        except ValueError as exc:
            raise ToolError(str(exc))
        return config['read'](instance).data
    return handler


def _make_delete(key):
    def handler(arguments):
        config = _ENTITIES[key]
        instance = _get_instance_or_error(key, arguments.get('record_id'))
        record_id = instance.pk
        try:
            accounting_service.delete_record(
                config['entity_type'], instance, mcp_actor(),
            )
        except ValueError as exc:
            raise ToolError(str(exc))
        return {'deleted': True, 'id': record_id}
    return handler


# ── Non-CRUD handlers ────────────────────────────────────────────────────────

def get_dashboard(arguments):
    year_arg = arguments.get('year')
    try:
        year = int(year_arg) if year_arg else today_bogota().year
    except (TypeError, ValueError):
        raise ToolError("El parámetro 'year' debe ser un año válido.")
    return accounting_service.dashboard_summary(year)


def get_receivables(_arguments):
    queryset = accounting_service.receivable_queryset()
    return {
        'summary': accounting_service.receivables_summary(queryset),
        'results': IncomeRecordSerializer(queryset, many=True).data,
    }


def list_change_logs(arguments):
    logs = AccountingChangeLog.objects.select_related('actor').all()
    try:
        if arguments.get('entity_type'):
            logs = logs.filter(entity_type=arguments['entity_type'])
        if arguments.get('object_id'):
            logs = logs.filter(object_id=arguments['object_id'])
        if arguments.get('action'):
            logs = logs.filter(action=arguments['action'])
        if arguments.get('actor'):
            logs = logs.filter(actor_username__icontains=arguments['actor'])
        if arguments.get('date_from'):
            logs = logs.filter(created_at__date__gte=_parse_date(arguments['date_from'], 'date_from'))
        if arguments.get('date_to'):
            logs = logs.filter(created_at__date__lte=_parse_date(arguments['date_to'], 'date_to'))
    except ValueError as exc:
        raise ToolError(str(exc))

    total = logs.count()
    try:
        page = max(1, int(arguments.get('page', 1) or 1))
    except (TypeError, ValueError):
        page = 1
    page_size = 20
    offset = (page - 1) * page_size
    num_pages = max(1, -(-total // page_size))
    data = AccountingChangeLogSerializer(logs[offset:offset + page_size], many=True).data
    return {'results': data, 'count': total, 'page': page, 'num_pages': num_pages}


def mute_income(arguments):
    """Silence (or resume) the payment-calendar notices of an expected income."""
    from content.models import IncomeRecord
    from content.serializers.accounting import (
        IncomeRecordSerializer,
        IncomeReminderMuteSerializer,
    )
    from content.services import accounting_income_mute_service

    income = _get_instance_or_error('income', arguments.get('record_id'))
    if income.kind != IncomeRecord.Kind.EXPECTED:
        raise ToolError('Solo se pueden silenciar los avisos de un ingreso esperado.')
    serializer = IncomeReminderMuteSerializer(data=arguments)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    income = accounting_income_mute_service.set_income_reminder_mute(
        income,
        muted=serializer.validated_data['muted'],
        until=serializer.validated_data.get('until'),
        user=mcp_actor(),
    )
    return IncomeRecordSerializer(income).data


def get_recurring_duplicate_draft(arguments):
    payment = _get_instance_or_error('recurring', arguments.get('record_id'))
    return accounting_recurring_service.build_duplicate_draft(payment)


def set_recurring_active(arguments):
    payment = _get_instance_or_error('recurring', arguments.get('record_id'))
    serializer = RecurringStateSerializer(data=arguments)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    try:
        payment = accounting_recurring_service.set_active(
            payment,
            active=serializer.validated_data['is_active'],
            user=mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return RecurringPaymentSerializer(payment).data


def archive_recurring(arguments):
    payment = _get_instance_or_error('recurring', arguments.get('record_id'))
    payment = accounting_recurring_service.archive(payment, user=mcp_actor())
    return RecurringPaymentSerializer(payment).data


def restore_recurring(arguments):
    payment = _get_instance_or_error('recurring', arguments.get('record_id'))
    payment = accounting_recurring_service.restore(payment, user=mcp_actor())
    return RecurringPaymentSerializer(payment).data


def mute_recurring(arguments):
    payment = _get_instance_or_error('recurring', arguments.get('record_id'))
    serializer = RecurringReminderMuteSerializer(data=arguments)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    try:
        payment = accounting_recurring_service.set_reminder_mute(
            payment,
            muted=serializer.validated_data['muted'],
            until=serializer.validated_data.get('until'),
            user=mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return RecurringPaymentSerializer(payment).data


def bulk_action_recurring(arguments):
    serializer = RecurringBulkActionSerializer(data=arguments)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    try:
        updated = accounting_recurring_service.bulk_apply(
            serializer.validated_data['recurring_ids'],
            action=serializer.validated_data['action'],
            user=mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return {
        'updated': len(updated),
        'results': RecurringPaymentSerializer(updated, many=True).data,
    }


def get_income_detail(arguments):
    """Read payments, deductions and collection-account state for one income."""
    try:
        income = accounting_income_detail_service.income_detail_queryset().get(
            pk=int(arguments.get('record_id')),
        )
    except (IncomeRecord.DoesNotExist, TypeError, ValueError) as exc:
        raise ToolError(
            f'No existe un registro income con id={arguments.get("record_id")}.'
        ) from exc
    return accounting_income_detail_service.build_income_detail_payload(income)


def _validated_settlement(arguments):
    serializer = IncomeSettlementSerializer(data={
        key: value for key, value in arguments.items() if key != 'record_id'
    })
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    return serializer.validated_data


def _require_confirmed_client_email():
    """A client email leaves only after someone reviewed its preview.

    The ledger connector asks for confirm_action before running this tool,
    and runs it with the confirmation bypass set. The legacy connector runs
    it directly, so there the flag is refused before anything is written.
    """
    context = current_mcp_context()
    if not (context and context.confirmation_bypass):
        raise ToolError(
            'La confirmación de pago al cliente solo se envía después de '
            'revisar su vista previa: usa el conector del libro contable y '
            'confírmala con confirm_action.',
        )


def settle_income(arguments):
    """Register one payment through the same settlement flow as the panel."""
    income = _get_instance_or_error('income', arguments.get('record_id'))
    data = _validated_settlement(arguments)
    if data.get('send_payment_confirmation'):
        _require_confirmed_client_email()
    try:
        result = accounting_settlement_service.settle_expected_income(
            income, data, mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return {
        'income': IncomeRecordSerializer(result['income']).data,
        'liquid': (
            IncomeRecordSerializer(result['liquid']).data
            if result['liquid'] is not None else None
        ),
        'expenses': ExpenseRecordSerializer(result['expenses'], many=True).data,
        'expected_incomes': IncomeRecordSerializer(
            result['expected_incomes'], many=True,
        ).data,
        # The tool runs inside the MCP transaction: the email waits for its
        # commit, so the result can only say it was scheduled.
        'payment_confirmation': (
            income_payment_confirmation_service.schedule_confirmation(result, data)
        ),
    }


_SETTLE_INCOME_DESCRIPTION = (
    'Registra un abono a un ingreso esperado y resuelve el saldo entre '
    'deducciones y nuevos ingresos esperados. Puede completar el período '
    'de hosting. Crea los mismos registros, auditoría y efectos que el panel. '
    'Con send_payment_confirmation=true le envía al cliente la confirmación '
    'del pago después de registrarlo; la vista previa muestra el correo.'
)


def _settle_income_impact(arguments):
    """The default preview, plus the email the client would receive."""
    impact = {
        'summary': _SETTLE_INCOME_DESCRIPTION,
        'tool': 'settle_income',
        'arguments': arguments,
    }
    if not arguments.get('send_payment_confirmation'):
        return impact
    income = _get_instance_or_error('income', arguments.get('record_id'))
    impact['payment_confirmation'] = (
        income_payment_confirmation_service.preview_confirmation(
            income, _validated_settlement(arguments),
        )
    )
    return impact


def bulk_settle_incomes(arguments):
    """Distribute one real payment across several expected incomes."""
    serializer = IncomeBulkSettlementSerializer(data=arguments)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    try:
        result = accounting_settlement_service.bulk_settle_expected_incomes(
            serializer.validated_data, mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    parent_ids = [income.pk for income in result['incomes']]
    records = list(
        IncomeRecord.objects.filter(expected_income_id__in=parent_ids)
    ) + list(result['incomes'])
    if result['credit'] is not None:
        records.append(result['credit'])
    return {
        'updated': len(result['incomes']),
        'results': IncomeRecordSerializer(records, many=True).data,
        'movement': PocketMovementSerializer(result['movement']).data,
    }


def get_settings(arguments):
    return AccountingSettingsSerializer(AccountingSettings.load()).data


def update_settings(arguments):
    instance = AccountingSettings.load()
    serializer = AccountingSettingsSerializer(instance, data=arguments, partial=True)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    try:
        instance = accounting_service.update_record(
            EntityType.SETTINGS, instance, serializer, mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc))
    return AccountingSettingsSerializer(instance).data


# ── Per-entity schema metadata (create/update fields + list filters) ─────────

# Create/update field schemas per ledger. The write serializer is the source of
# truth for validation; these are documented for the model's benefit.
_LEDGER_ENUM = ['company', 'gustavo', 'carlos']

_ENTITY_FIELDS = {
    'income': {
        'props': {
            'concept': {'type': 'string'},
            'kind': {'type': 'string', 'enum': ['expected', 'liquid', 'lost']},
            'period_date': {
                'type': 'string',
                'description': (
                    'Fecha o mes del ingreso (YYYY-MM o YYYY-MM-DD). En hosting '
                    'es el mes de cobro esperado, independiente del período '
                    'cubierto: si no lo envías, al crear toma period_start y '
                    'al editar lo sigue sólo si coincidían.'
                ),
            },
            'total_amount': {'type': ['number', 'string'], 'description': 'Total con IVA incluido; alternativa a amount.'},
            'amount': {'type': ['number', 'string'], 'description': 'Importe de captura; no combinar con total_amount.'},
            'amount_mode': {'type': 'string', 'enum': ['before_vat', 'vat_included']},
            'vat_rate': {'type': ['number', 'string', 'null'], 'description': 'IVA entre 0 y 100; 0 = Sin IVA, null = sin registrar.'},
            'destination': {'type': 'string', 'enum': ['partners', 'pocket']},
            'ledger': {'type': 'string', 'enum': _LEDGER_ENUM},
            'is_receivable_candidate': {
                'type': 'boolean',
                'description': (
                    'Incluye este esperado empresarial en la previsión manual '
                    'de pendientes por cobrar.'
                ),
            },
            'collection_confidence': {
                'type': 'string',
                'enum': ['', 'high', 'medium', 'low'],
                'description': (
                    'Probabilidad manual de cobro. No cambia la inclusión en '
                    'la previsión; usa is_receivable_candidate explícitamente.'
                ),
            },
            'client': {
                'type': ['integer', 'null'],
                'description': 'ID del cliente (UserProfile con rol cliente).',
            },
            'project': {
                'type': ['integer', 'null'],
                'description': (
                    'ID del proyecto (accounts.Project). Debe pertenecer al '
                    'mismo cliente del registro.'
                ),
            },
            'project_name': {
                'type': 'string',
                'description': (
                    'Alias de conveniencia: nombre del proyecto del cliente, '
                    'resuelto a su id (falla si no existe o hay más de uno '
                    'con ese nombre). Se ignora si también pasas project.'
                ),
            },
            'origin': {
                'type': 'string',
                'enum': ['development', 'hosting', 'diagnostic', 'other'],
                'description': (
                    'Línea de negocio que origina el ingreso. Con hosting son '
                    'obligatorios period_start, period_end y period_cadence.'
                ),
            },
            'period_start': {
                'type': 'string',
                'description': (
                    'Inicio del período cubierto (YYYY-MM-DD o YYYY-MM). Solo '
                    'origin=hosting.'
                ),
            },
            'period_end': {
                'type': 'string',
                'description': (
                    'Fin INCLUSIVO del período cubierto (YYYY-MM-DD). Solo '
                    'origin=hosting.'
                ),
            },
            'period_cadence': {
                'type': 'string',
                'enum': [
                    'monthly', 'bimonthly', 'quarterly', 'four_monthly',
                    'semiannual', 'annual', 'biennial', 'triennial', 'custom',
                ],
                'description': (
                    'Periodicidad del período cubierto (catálogo de gastos '
                    'recurrentes). Solo origin=hosting.'
                ),
            },
            'gustavo_amount': {'type': ['number', 'string']},
            'carlos_amount': {'type': ['number', 'string']},
            'expected_income': {
                'type': ['integer', 'null'],
                'description': 'ID del ingreso esperado padre de un abono; null quita el vínculo.',
            },
            'notes': {'type': 'string'},
        },
        'required': ['concept', 'kind', 'origin'],
    },
    'expense': {
        'props': {
            'concept': {'type': 'string'},
            'period_date': {'type': 'string', 'description': 'Periodo YYYY-MM.'},
            'total_amount': {'type': ['number', 'string'], 'description': 'Total con IVA incluido; alternativa a amount.'},
            'amount': {'type': ['number', 'string'], 'description': 'Importe de captura; no combinar con total_amount.'},
            'amount_mode': {'type': 'string', 'enum': ['before_vat', 'vat_included']},
            'vat_rate': {'type': ['number', 'string', 'null'], 'description': 'IVA entre 0 y 100; 0 = Sin IVA, null = sin registrar.'},
            'category': {'type': 'string', 'enum': ['business', 'personal']},
            'deduction_type': {
                'type': 'string',
                'enum': ['', *ExpenseRecord.DeductionType.values],
                'description': 'Tipo de deducción existente; sólo la liquidación puede asignarlo o cambiarlo.',
            },
            'register_in_pocket': {
                'type': 'boolean',
                'description': 'Registra el gasto en el bolsillo de empresa; true por defecto.',
            },
            'ledger': {'type': 'string', 'enum': _LEDGER_ENUM},
            'gustavo_amount': {'type': ['number', 'string']},
            'carlos_amount': {'type': ['number', 'string']},
            'notes': {'type': 'string'},
        },
        'required': ['concept', 'period_date'],
    },
    'hosting': {
        'props': {
            'client': {
                'type': ['integer', 'null'],
                'description': 'ID del cliente (UserProfile con rol cliente).',
            },
            'project': {
                'type': ['integer', 'null'],
                'description': (
                    'ID del proyecto (accounts.Project). Debe pertenecer al '
                    'mismo cliente del registro.'
                ),
            },
            'client_name': {'type': 'string'},
            'client_email': {'type': 'string', 'description': 'Correo de facturación; si se omite se toma del cliente.'},
            'client_contact_name': {'type': 'string', 'description': 'Nombre de contacto para facturación.'},
            'client_identification': {'type': 'string', 'description': 'Identificación del cliente para facturación.'},
            'project_name': {
                'type': 'string',
                'description': (
                    'Alias de conveniencia: nombre del proyecto del cliente, '
                    'resuelto a su id (falla si no existe o hay más de uno '
                    'con ese nombre). Se ignora si también pasas project.'
                ),
            },
            'monthly_value': {'type': ['number', 'string']},
            'domain_url': {'type': 'string'},
            'payment_modality': {
                'type': 'string',
                'enum': ['quarterly', 'semiannual', 'nine_month'],
            },
            'benefit': {'type': 'string'},
            'valid_from': {'type': 'string', 'description': 'YYYY-MM-DD.'},
            'valid_to': {'type': 'string', 'description': 'YYYY-MM-DD.'},
            'cycles_count': {'type': 'integer'},
            'payment_per_cycle': {'type': ['number', 'string']},
            'vat_rate': {'type': ['number', 'string', 'null']},
            'amount': {'type': ['number', 'string'], 'description': 'Pago por ciclo; alternativa a payment_per_cycle.'},
            'amount_mode': {'type': 'string', 'enum': ['before_vat', 'vat_included']},
            'total_paid': {'type': ['number', 'string']},
            'is_active': {'type': 'boolean'},
            'notes': {'type': 'string'},
        },
        'required': ['client', 'monthly_value'],
    },
    'pocket': {
        'props': {
            'concept': {'type': 'string'},
            'movement_date': {'type': 'string', 'description': 'YYYY-MM-DD.'},
            'direction': {'type': 'string', 'enum': ['in', 'out']},
            'amount': {'type': ['number', 'string']},
            'ledger': {'type': 'string', 'enum': _LEDGER_ENUM, 'description': 'Libro contable del movimiento.'},
            'notes': {'type': 'string'},
        },
        'required': ['concept', 'movement_date', 'direction', 'amount'],
    },
    'recurring': {
        'props': {
            'name': {'type': 'string'},
            'price': {'type': ['number', 'string']},
            'currency': {'type': 'string', 'enum': ['COP', 'USD']},
            'payment_method': {'type': 'string', 'enum': ['cash', 'credit_card']},
            'frequency': {
                'type': 'string',
                'enum': [
                    'monthly', 'bimonthly', 'quarterly', 'four_monthly',
                    'semiannual', 'annual', 'biennial', 'triennial', 'custom',
                ],
            },
            'custom_months': {
                'type': ['integer', 'null'],
                'minimum': 1,
                'maximum': 600,
                'description': (
                    'Obligatorio con frequency="custom": cada cuántos meses se '
                    'cobra. Si coincide con una frecuencia del catálogo (2, 3, '
                    '4, 6, 12, 24, 36) se guarda como esa.'
                ),
            },
            'billing_day': {'type': 'integer', 'minimum': 1, 'maximum': 31},
            'cycle_anchor_date': {
                'type': ['string', 'null'],
                'description': (
                    'YYYY-MM-DD. Fecha de un cobro conocido: desde ella se '
                    'calcula el próximo cobro y sus avisos. Imprescindible '
                    'para las frecuencias que no son mensuales, porque el día '
                    'de cobro no dice en qué mes cae el ciclo.'
                ),
            },
            'cost_type': {'type': 'string', 'enum': ['fixed', 'variable']},
            'category': {
                'type': ['integer', 'null'],
                'description': 'ID de la categoría (ver list_recurring_categories).',
            },
            'is_active': {'type': 'boolean'},
            'notes': {'type': 'string'},
        },
        'required': ['name', 'price'],
    },
    'ads': {
        'props': {
            'spend_date': {'type': 'string', 'description': 'YYYY-MM-DD.'},
            'amount': {'type': ['number', 'string']},
            'platform': {'type': 'string', 'enum': ['facebook', 'google', 'other']},
            'origin_card': {'type': 'string'},
            'notes': {'type': 'string'},
        },
        'required': ['spend_date', 'amount'],
    },
    'card_snapshot': {
        'props': {
            'snapshot_date': {'type': 'string', 'description': 'YYYY-MM-DD.'},
            'card_name': {'type': 'string'},
            'available_amount': {'type': ['number', 'string']},
            'debt_amount': {
                'type': ['number', 'string'],
                'description': (
                    'Opcional: si la tarjeta está en el catálogo, la deuda '
                    'se calcula en el servidor como cupo − disponible y '
                    'este valor se ignora. Obligatorio sólo para tarjetas '
                    'fuera del catálogo.'
                ),
            },
            'notes': {'type': 'string'},
        },
        'required': ['snapshot_date', 'card_name', 'available_amount'],
    },
    'notification_recipient': {
        'props': {
            'email': {
                'type': 'string',
                'description': (
                    'Correo destinatario. Se normaliza a minúsculas y no '
                    'admite duplicados.'
                ),
            },
            'is_active': {
                'type': 'boolean',
                'description': (
                    'Si está en false el correo queda pausado: sigue en la '
                    'lista pero no recibe ningún envío del módulo.'
                ),
            },
            'notes': {'type': 'string'},
        },
        'required': ['email'],
    },
}

_ENTITY_LABELS = {
    'income': 'ingresos',
    'expense': 'gastos',
    'hosting': 'hostings',
    'pocket': 'movimientos de pocket',
    'recurring': 'gastos recurrentes',
    'ads': 'gasto en ads',
    'card_snapshot': 'snapshots de tarjeta',
    'notification_recipient': 'destinatarios de notificación',
}

_ENTITY_NOTES = {
    'income': (
        'kind: expected = ingreso esperado por cobrar (proyección), liquid = '
        'dinero recibido, lost = castigado (no se cobrará); cancelled sólo '
        'aparece en lecturas. Para editar ingresos esperados con vista previa, '
        'ETag y reparto del Panel usa list_expected_incomes, get_expected_income, '
        'update_expected_income, create_expected_income o duplicate_expected_income.'
    ),
    'recurring': (
        'Son gastos periódicos y suscripciones que la empresa paga '
        '(salidas de dinero), no ingresos.'
    ),
}


def _list_schema(key):
    config = _ENTITIES[key]
    props = {'q': {'type': 'string', 'description': 'Búsqueda de texto.'}}
    if config['date_field']:
        props.update({
            'year': {'type': 'integer'},
            'date_from': {'type': 'string', 'description': 'YYYY-MM-DD.'},
            'date_to': {'type': 'string', 'description': 'YYYY-MM-DD.'},
        })
    props.update({
        'amount_min': {'type': ['number', 'string']},
        'amount_max': {'type': ['number', 'string']},
    })
    for field in config.get('choice_filters', ()):
        model_field = config['model']._meta.get_field(field)
        choices = [str(value) for value, _ in model_field.flatchoices if value != '']
        if choices:
            values = ', '.join(choices)
        elif model_field.is_relation:
            values = 'IDs de categoría (list_recurring_categories)'
        else:
            values = 'nombres existentes en el catálogo de tarjetas'
        props[field] = {
            'type': 'string',
            'description': f"Uno o varios valores separados por coma: {values}. 'none' incluye los valores sin clasificar.",
        }
    for field in config.get('bool_filters', ()):
        props[field] = {'type': 'boolean'}
    if config.get('archive_scope'):
        props['archive_scope'] = {
            'type': 'string',
            'enum': ['current', 'archived', 'all'],
            'default': 'current',
            'description': 'Vigentes, archivados o ambos.',
        }
    for field in config.get('null_filters', ()):
        props[field] = {
            'type': 'string',
            'description': (
                "'none' para los registros sin asignar, 'all' para no "
                'filtrar, o uno o varios ids separados por coma.'
            ),
        }
    for field, conditions in config.get('q_filters', {}).items():
        # `string` rather than `boolean` even for the true/false tokens: the
        # knob parses comma-separated tokens uniformly, and `_str_params`
        # coerces a real boolean to 'true'/'false' anyway.
        props[field] = {
            'type': 'string',
            'description': (
                'Uno o varios valores separados por coma: '
                + ', '.join(sorted(conditions)) + '.'
            ),
        }
    # `string` rather than `enum` for both: they now take comma-separated
    # tokens like the q_filters above, and `_str_params` would stringify a real
    # list as "['a', 'b']".
    if config.get('has_split'):
        props['partner'] = {
            'type': 'string',
            'description': (
                'Uno o varios valores separados por coma: carlos, gustavo, '
                "projectapp. 'all' no filtra."
            ),
        }
    if config.get('payment_status_filter'):
        props['payment_status'] = {
            'type': 'string',
            'description': (
                'Estado de cobro de un esperado, uno o varios separados por '
                'coma: pending (sin pagos), partial (pago parcial) o paid '
                "(pagado). 'all' no filtra."
            ),
        }
    return closed_object(props)


_RECORD_ID_PROP = {'record_id': {'type': 'integer', 'description': 'ID del registro.'}}

_SETTLEMENT_PROPS = {
    **_RECORD_ID_PROP,
    'concept': {'type': 'string', 'description': 'Concepto del pago recibido.'},
    'period_date': {'type': 'string', 'description': 'Fecha o período del pago (YYYY-MM-DD o YYYY-MM).'},
    'destination': {'type': 'string', 'enum': ['partners', 'pocket'], 'default': 'partners'},
    'total_amount': {'type': ['number', 'string'], 'description': 'Monto efectivamente recibido; puede ser cero si todo se resuelve con deducciones o saldos futuros.'},
    'gustavo_amount': {'type': ['number', 'string']},
    'carlos_amount': {'type': ['number', 'string']},
    'notes': {'type': 'string'},
    'deductions': {
        'type': 'array',
        'description': 'Comisiones, retenciones u otros descuentos que no se cobrarán después.',
        'items': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'type': {'type': 'string', 'enum': [value for value, _ in ExpenseRecord.DeductionType.choices]},
                'detail': {'type': 'string', 'description': 'Obligatorio cuando type=other.'},
                'amount': {'type': ['number', 'string']},
            },
            'required': ['type', 'amount'],
        },
    },
    'expected_incomes': {
        'type': 'array',
        'description': 'Partes del saldo que sí se cobrarán después como nuevos ingresos esperados.',
        'items': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'concept': {'type': 'string'},
                'period_date': {'type': 'string'},
                'amount': {'type': ['number', 'string']},
            },
            'required': ['concept', 'period_date', 'amount'],
        },
    },
    'send_payment_confirmation': {
        'type': 'boolean',
        'default': False,
        'description': (
            'Envía al cliente la confirmación del pago, sin adjuntos, al correo '
            'de la cuenta de cobro emitida. Sale después de confirm_action y de '
            'registrarse la liquidación: el resultado informa scheduled y el '
            'envío queda en el historial de correos.'
        ),
    },
    'period': {
        'type': ['object', 'null'],
        'additionalProperties': False,
        'description': 'Período de hosting que completa el ingreso esperado padre.',
        'properties': {
            'period_start': {'type': 'string'},
            'period_end': {'type': 'string'},
            'period_cadence': {
                'type': 'string',
                'enum': [
                    'monthly', 'bimonthly', 'quarterly', 'four_monthly',
                    'semiannual', 'annual', 'biennial', 'triennial', 'custom',
                ],
            },
        },
        'required': ['period_start', 'period_end', 'period_cadence'],
    },
}


def _build_ledger_tools():
    tools = []
    areas = {
        'income': 'ledger', 'expense': 'ledger', 'pocket': 'ledger',
        'recurring': 'ledger', 'ads': 'ledger', 'hosting': 'billing',
        'notification_recipient': 'billing', 'card_snapshot': 'cards',
    }
    for key, fields in _ENTITY_FIELDS.items():
        label = _ENTITY_LABELS[key]
        tools.append({
            'name': f'list_{key}',
            'area': areas[key],
            'description': f'Lista {label} con filtros (fechas, montos, categorías, búsqueda q).',
            'input_schema': _list_schema(key),
            'handler': _make_list(key),
        })
        tools.append({
            'name': f'get_{key}',
            'area': areas[key],
            'description': (
                f'Abre un registro de {label} por ID con todos los campos '
                'vigentes de lectura del módulo contable.'
            ),
            'input_schema': closed_object(_RECORD_ID_PROP, ['record_id']),
            'handler': _make_get(key),
        })
        tools.append({
            'name': f'create_{key}',
            'area': areas[key],
            'description': (
                f'Crea un registro de {label} usando las mismas validaciones, '
                'auditoría y efectos secundarios que el formulario del panel.'
            ),
            'input_schema': closed_object(fields['props'], fields['required']),
            # Legacy create callers may send record_id; the handler drops it.
            'accepted_arguments_schema': closed_object(
                {**fields['props'], **_RECORD_ID_PROP}, fields['required'],
            ),
            'handler': _make_create(key),
        })
        tools.append({
            'name': f'update_{key}',
            'area': areas[key],
            'description': f'Actualiza (parcial) un registro de {label}. Envía record_id + campos.',
            'input_schema': closed_object({**_RECORD_ID_PROP, **fields['props']}, ['record_id']),
            'handler': _make_update(key),
        })
        tools.append({
            'name': f'delete_{key}',
            'area': areas[key],
            'description': f'Elimina un registro de {label}. Los movimientos de pocket auto-gestionados no se pueden borrar.',
            'input_schema': closed_object(_RECORD_ID_PROP, ['record_id']),
            'handler': _make_delete(key),
        })
    for tool in tools:
        key = tool['name'].split('_', 1)[1]
        if key in _ENTITY_NOTES:
            tool['description'] += ' ' + _ENTITY_NOTES[key]
    return tools


_NON_CRUD_TOOLS = close_root_schemas([
    {
        'name': 'get_dashboard',
        'area': 'ledger',
        'description': (
            'Resumen contable del año: totales, split de socios, breakdown '
            'mensual, balance de pocket, costo recurrente, ads, hostings y '
            'últimos snapshots de tarjeta, incluida la previsión manual global '
            'de pendientes por cobrar. Param opcional: year.'
        ),
        'input_schema': {'type': 'object', 'properties': {'year': {'type': 'integer'}}},
        'handler': get_dashboard,
    },
    {
        'name': 'get_receivables',
        'area': 'ledger',
        'description': (
            'Lista los ingresos esperados empresariales aún abiertos y '
            'resume la selección manual por probabilidad de cobro.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': get_receivables,
    },
    {
        'name': 'get_income_detail',
        'area': 'ledger',
        'description': (
            'Abre un ingreso con su estado de cobro, pagos parciales, '
            'deducciones, movimiento de bolsillo compartido y cuenta de cobro '
            'vigente. Úsala en lugar de get_income para auditar el historial.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _RECORD_ID_PROP,
            'required': ['record_id'],
        },
        'handler': get_income_detail,
    },
    {
        'name': 'settle_income',
        'area': 'ledger',
        'description': _SETTLE_INCOME_DESCRIPTION,
        'input_schema': {
            'type': 'object',
            'properties': _SETTLEMENT_PROPS,
            'required': ['record_id', 'concept', 'period_date', 'total_amount'],
        },
        'handler': settle_income,
        'impact_builder': _settle_income_impact,
    },
    {
        'name': 'bulk_settle_incomes',
        'area': 'ledger',
        'description': (
            'Distribuye un único abono real entre varios ingresos esperados. '
            'Crea un solo movimiento de bolsillo; cualquier excedente queda como '
            'saldo a favor cuando todos los ingresos pertenecen al mismo cliente.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'allocations': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'income_id': {'type': 'integer'},
                            'amount': {'type': ['number', 'string']},
                        },
                        'required': ['income_id', 'amount'],
                    },
                    'minItems': 1,
                },
                'total_amount': {'type': ['number', 'string']},
                'period_date': {'type': 'string', 'description': 'Fecha o período del abono.'},
                'notes': {'type': 'string'},
            },
            'required': ['allocations', 'total_amount', 'period_date'],
        },
        'handler': bulk_settle_incomes,
    },
    {
        'name': 'list_change_logs',
        'area': 'ledger',
        'description': (
            'Auditoría de cambios (paginada, 20/pág). Filtros: entity_type, '
            'object_id, action (created/updated/deleted), actor, date_from, '
            'date_to, page.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'entity_type': {'type': 'string'},
                'object_id': {'type': 'integer'},
                'action': {'type': 'string', 'enum': ['created', 'updated', 'deleted']},
                'actor': {'type': 'string'},
                'date_from': {'type': 'string'},
                'date_to': {'type': 'string'},
                'page': {'type': 'integer', 'default': 1},
            },
        },
        'handler': list_change_logs,
    },
    {
        'name': 'get_settings',
        'area': 'billing',
        'description': (
            'Devuelve la configuración contable (notificaciones, recordatorios, '
            'tasa USD, vista por defecto de ingresos).'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': get_settings,
    },
    {
        'name': 'mute_income',
        'area': 'ledger',
        'description': (
            'Silencia los avisos de cobro de un ingreso esperado, o los '
            'reactiva con muted=false. Sin `until` el silencio dura hasta que '
            'se levante a mano; con `until` los avisos se reanudan ese día.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'record_id': {'type': 'integer'},
                'muted': {'type': 'boolean'},
                'until': {
                    'type': ['string', 'null'],
                    'description': 'YYYY-MM-DD, posterior a hoy.',
                },
            },
            'required': ['record_id', 'muted'],
        },
        'handler': mute_income,
    },
    {
        'name': 'get_recurring_duplicate_draft',
        'area': 'ledger',
        'description': (
            'Construye, sin guardar, el borrador para duplicar un gasto '
            'recurrente. Recalcula la próxima fecha y limpia notas, archivo y avisos.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _RECORD_ID_PROP,
            'required': ['record_id'],
        },
        'handler': get_recurring_duplicate_draft,
    },
    {
        'name': 'set_recurring_active',
        'area': 'ledger',
        'description': (
            'Activa o desactiva un gasto recurrente. Los archivados deben '
            'restaurarse antes de activarse.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_RECORD_ID_PROP,
                'is_active': {'type': 'boolean'},
            },
            'required': ['record_id', 'is_active'],
        },
        'handler': set_recurring_active,
    },
    {
        'name': 'archive_recurring',
        'area': 'ledger',
        'description': 'Archiva y desactiva un gasto recurrente sin borrar sus datos.',
        'input_schema': {
            'type': 'object',
            'properties': _RECORD_ID_PROP,
            'required': ['record_id'],
        },
        'handler': archive_recurring,
    },
    {
        'name': 'restore_recurring',
        'area': 'ledger',
        'description': 'Restaura un gasto recurrente archivado y lo deja inactivo.',
        'input_schema': {
            'type': 'object',
            'properties': _RECORD_ID_PROP,
            'required': ['record_id'],
        },
        'handler': restore_recurring,
    },
    {
        'name': 'mute_recurring',
        'area': 'ledger',
        'description': (
            'Silencia o reactiva los avisos del próximo cobro de un gasto '
            'recurrente vigente; admite una fecha futura de reanudación.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_RECORD_ID_PROP,
                'muted': {'type': 'boolean'},
                'until': {
                    'type': ['string', 'null'],
                    'description': 'YYYY-MM-DD, posterior a hoy.',
                },
            },
            'required': ['record_id', 'muted'],
        },
        'handler': mute_recurring,
    },
    {
        'name': 'bulk_action_recurring',
        'area': 'ledger',
        'description': (
            'Activa, desactiva o archiva una selección completa de gastos '
            'recurrentes en una sola transacción.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'recurring_ids': {
                    'type': 'array',
                    'items': {'type': 'integer'},
                    'minItems': 1,
                    'maxItems': 500,
                },
                'action': {
                    'type': 'string',
                    'enum': ['activate', 'deactivate', 'archive'],
                },
            },
            'required': ['recurring_ids', 'action'],
        },
        'handler': bulk_action_recurring,
    },
    {
        'name': 'update_settings',
        'area': 'billing',
        'description': (
            'Actualiza (parcial) la configuración contable: '
            'notifications_enabled (interruptor maestro de TODO el correo '
            'automático del módulo), card_reminder_enabled, '
            'statement_reminder_enabled, hosting_expiry_reminder_enabled, '
            'payment_calendar_enabled, overdue_reminder_frequency '
            '(weekly|biweekly), usd_exchange_rate, income_default_view_mode '
            '(classic|grouped), collection_accounts_view_mode '
            '(classic|grouped) y collection_accounts_group_by '
            '(client|project). Los destinatarios ya no viven acá: se '
            'administran con las herramientas de notification_recipient.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'notifications_enabled': {'type': 'boolean'},
                'card_reminder_enabled': {'type': 'boolean'},
                'statement_reminder_enabled': {'type': 'boolean'},
                'hosting_expiry_reminder_enabled': {'type': 'boolean'},
                'payment_calendar_enabled': {'type': 'boolean'},
                'overdue_reminder_frequency': {
                    'type': 'string',
                    'enum': ['weekly', 'biweekly'],
                    'description': (
                        'Cada cuánto se recuerda un ingreso esperado que ya '
                        'pasó su fecha y sigue sin cobrarse.'
                    ),
                },
                'usd_exchange_rate': {'type': ['number', 'string']},
                'income_default_view_mode': {'type': 'string', 'enum': ['classic', 'grouped']},
                'collection_accounts_view_mode': {
                    'type': 'string', 'enum': ['classic', 'grouped'],
                },
                'collection_accounts_group_by': {
                    'type': 'string', 'enum': ['client', 'project'],
                },
            },
        },
        'handler': update_settings,
    },
])

from content.mcp.statement_tools import STATEMENT_TOOLS  # noqa: E402

ACCOUNTING_TOOLS = _build_ledger_tools() + _NON_CRUD_TOOLS + STATEMENT_TOOLS
