"""
MCP tools for the credit-card statement sub-module (extractos).

Registered into ACCOUNTING_TOOLS (slug `accounting`), so the same connector
token exposes them. The chat workflow lives in `get_statement_instructions`
— the repo's template-tool idiom (this custom MCP server has no `prompts`
primitive), versioned with the code so every future chat picks up changes.

All writes route through accounting_statement_service with mcp_actor() as
the user: audit rows fire identically to the panel (statement-level changes
email; transaction/alias changes are silent).
"""
from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError
from content.mcp.schema_policy import close_root_schemas
from content.models import (
    CreditCardStatement,
    CreditCardTransaction,
    MerchantAlias,
    TransactionCategory,
)
from content.serializers.accounting_statement import (
    CreditCardStatementDetailSerializer,
    CreditCardStatementSerializer,
    CreditCardStatementWriteSerializer,
    CreditCardTransactionSerializer,
    CreditCardTransactionWriteSerializer,
    MerchantAliasSerializer,
    MerchantAliasWriteSerializer,
)
from content.services import accounting_statement_service
from content.utils import today_bogota

WORKFLOW_VERSION = 3

_INSTRUCTIONS = """\
Flujo para procesar un extracto de tarjeta de crédito. Sigue las fases EN ORDEN.

CONTEXTO: este submódulo es un libro ANALÍTICO separado. Nunca crea gastos ni
movimientos de bolsillo — el abono a la tarjeta se registra aparte como
siempre (módulo contable principal). Tu trabajo es trasladar el extracto tal
cual a este libro.

FASE 1 — VERIFICAR: llama `get_statement_status` con el año (y `card_name`
si la conoces). Si el mes del extracto ya está `processed`, avísale al
usuario y DETENTE salvo que él ordene reprocesar (en ese caso: si hay
borrador usa `delete_statement` y vuelve a crear; si está procesado, primero
`reopen_statement`). Si hay un `draft` de ese mes, ofrécele continuar sobre
él o reemplazarlo.

FASE 2 — EXTRAER DEL PDF: identifica tarjeta (usa los nombres de `cards` del
status — vienen del catálogo de tarjetas del panel; usa el que coincida),
período de corte (`YYYY-MM`),
totales del extracto (compras, pagos/abonos, intereses y comisiones, saldo
anterior, saldo de cierre, pago mínimo, fecha límite) y cada línea de
consumo: fecha, DESCRIPCIÓN CRUDA EXACTA como aparece impresa, y valor COP
facturado. Reglas:
- `amount` es el valor con el que el movimiento aparece y SUMA en "Compras
  del mes" del extracto. Para compras nuevas en cuotas eso es el valor
  TOTAL de la compra (así lo suma el banco);
  `installment_number`/`installments_total` registran el plan de cuotas
  como dato informativo. NUNCA uses el valor de la cuota mensual como
  `amount`: la validación de cierre cuadra contra "Compras del mes".
- Compras internacionales: `amount` es el COP facturado;
  `original_amount`/`original_currency` guardan la referencia (p. ej. USD).
- Reversiones/devoluciones: el banco las clasifica como ABONOS, no como
  compras negativas. Registra el cargo original normal y la reversión como
  una transacción de monto NEGATIVO, misma categoría del cargo y
  `is_reversal=true`. Así el breakdown por categoría se neutraliza, la
  reversión no entra en la suma de cierre, y `payments_total` se registra
  tal como lo imprime el banco (incluyendo la reversión).
- NO incluyas pagos/abonos ni intereses/comisiones como transacciones: van
  en `payments_total` / `interest_and_fees` del encabezado.

FASE 3 — RESOLVER COMERCIOS: llama `resolve_merchants` con TODAS las
descripciones crudas. Las resueltas ya tienen comercio y categoría
aprendidos. Las `gateway_hints` son pasarelas de pago conocidas (EBANX,
MERCADOPAGO, DLOCAL...): el comercio real puede variar entre compras, así
que verifica cada una (recibo, correo del comercio) partiendo del
`last_known_merchant` sugerido. Para las NO resueltas cuyo nombre sea opaco
(razones sociales, holdings, códigos), investiga con búsqueda web a qué
comercio corresponden.
Presenta al usuario una tabla descripción → comercio propuesto + categoría y
ESPERA SU APROBACIÓN EXPLÍCITA. NUNCA guardes alias sin aprobación.
Al proponer el texto del alias, quita códigos de reserva/transacción
alfanuméricos del descriptor (p. ej. de "EASYJET AKCN435H" el alias es
"EASYJET"): un alias con código de un solo uso nunca vuelve a matchear.
Si el descriptor es una pasarela de pago, guarda el alias con
`is_gateway=true`: el conocimiento queda para el próximo mes como pista,
sin auto-clasificar compras futuras que pueden ser de otro comercio.

FASE 4 — GUARDAR: llama `create_statement` UNA sola vez con el encabezado y
todas las transacciones. Las dudosas van con `is_identified=false` y
categoría `other`; las resueltas por alias se completan solas.

FASE 5 — APRENDER: tras la aprobación del usuario, llama
`save_merchant_aliases` con los mapeos aprobados y el `statement_id` para
que se apliquen al borrador. Los alias quedan guardados para los próximos
extractos. Hazlo ANTES de consolidar: sobre un extracto ya procesado los
alias se guardan igual pero no se aplican (revisa el campo `warning` de la
respuesta).

FASE 6 — CONSOLIDAR: llama `finalize_statement`. Si la suma no cuadra con
`purchases_total`, muestra la diferencia al usuario, corrige con
`update_statement_transaction` / `update_statement`, o pide su confirmación
explícita para cerrar con `force=true`.

FASE 7 — CIERRE: resume totales, breakdown por categoría y cuotas activas.
Recuérdale al usuario que el abono de la tarjeta se registra como siempre en
el módulo contable principal, y que suba el PDF del extracto como
documentación en el panel (Contable → Extractos → mes correspondiente).

FORMATOS: fechas `YYYY-MM-DD`; período `YYYY-MM`; montos numéricos sin
separadores de miles (punto decimal).
"""


def _categories_vocab():
    return [
        {'value': value, 'label': label}
        for value, label in TransactionCategory.choices
    ]


def _serializer_errors_to_message(errors):
    import json
    return 'Datos inválidos: ' + json.dumps(
        errors, ensure_ascii=False, default=str,
    )


def _get_statement_or_error(statement_id):
    try:
        return CreditCardStatement.objects.get(pk=int(statement_id))
    except (CreditCardStatement.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe un extracto con id={statement_id}.')


# ── Handlers ──

def get_statement_instructions(arguments):
    return {
        'workflow_version': WORKFLOW_VERSION,
        'instructions': _INSTRUCTIONS,
        'categories': _categories_vocab(),
    }


def get_statement_status(arguments):
    year = arguments.get('year') or today_bogota().year
    try:
        year = int(year)
    except (TypeError, ValueError):
        raise ToolError("El parámetro 'year' debe ser un año válido.")
    return accounting_statement_service.statement_month_status(
        year, arguments.get('card_name') or None,
    )


def create_statement(arguments):
    transactions_data = arguments.get('transactions') or []
    if not isinstance(transactions_data, list) or not transactions_data:
        raise ToolError(
            "El campo 'transactions' debe ser una lista con al menos una "
            'transacción (extraídas del extracto).'
        )
    header = {
        key: value for key, value in arguments.items()
        if key != 'transactions'
    }
    statement_serializer = CreditCardStatementWriteSerializer(data=header)
    if not statement_serializer.is_valid():
        errors = statement_serializer.errors
        duplicate = 'Ya existe un extracto' in str(errors)
        if duplicate:
            existing = CreditCardStatement.objects.filter(
                card_name=header.get('card_name'),
            ).order_by('-period_date').first()
            hint = ''
            if existing is not None:
                hint = (
                    f' Extracto existente: id={existing.pk}, '
                    f'estado={existing.status}.'
                )
            raise ToolError(
                'Ya existe un extracto de esa tarjeta para ese mes.' + hint
            )
        raise ToolError(_serializer_errors_to_message(errors))
    transactions_serializer = CreditCardTransactionWriteSerializer(
        data=transactions_data, many=True,
    )
    if not transactions_serializer.is_valid():
        raise ToolError(
            _serializer_errors_to_message(transactions_serializer.errors),
        )
    try:
        statement = accounting_statement_service.create_statement_with_transactions(
            statement_serializer, transactions_serializer, mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc))
    return CreditCardStatementDetailSerializer(statement).data


def resolve_merchants(arguments):
    raw_descriptions = arguments.get('raw_descriptions')
    if not isinstance(raw_descriptions, list) or not raw_descriptions:
        raise ToolError(
            "El campo 'raw_descriptions' debe ser una lista de textos."
        )
    return accounting_statement_service.resolve_merchants(raw_descriptions)


def save_merchant_aliases(arguments):
    aliases = arguments.get('aliases')
    if not isinstance(aliases, list) or not aliases:
        raise ToolError(
            "El campo 'aliases' debe ser una lista de mapeos aprobados por "
            'el usuario.'
        )
    valid_categories = set(TransactionCategory.values)
    for item in aliases:
        category = item.get('category')
        if category and category not in valid_categories:
            raise ToolError(
                f"Categoría inválida: {category}. Usa una de: "
                f"{sorted(valid_categories)}."
            )
    try:
        result = accounting_statement_service.save_merchant_aliases(
            aliases, mcp_actor(), statement_id=arguments.get('statement_id'),
        )
    except ValueError as exc:
        raise ToolError(str(exc))
    return {
        'aliases': MerchantAliasSerializer(result['aliases'], many=True).data,
        'updated_transactions': result['updated_transactions'],
        'warning': result['warning'],
    }


def update_statement(arguments):
    statement = _get_statement_or_error(arguments.get('statement_id'))
    data = {
        key: value for key, value in arguments.items()
        if key != 'statement_id'
    }
    serializer = CreditCardStatementWriteSerializer(
        statement, data=data, partial=True,
    )
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    from content.services import accounting_service
    from content.views.accounting import EntityType

    try:
        statement = accounting_service.update_record(
            EntityType.STATEMENT, statement, serializer, mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc))
    return CreditCardStatementSerializer(statement).data


def update_statement_transaction(arguments):
    tx_id = arguments.get('transaction_id')
    try:
        tx = CreditCardTransaction.objects.get(pk=int(tx_id))
    except (CreditCardTransaction.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe una transacción con id={tx_id}.')
    data = {
        key: value for key, value in arguments.items()
        if key != 'transaction_id'
    }
    serializer = CreditCardTransactionWriteSerializer(
        tx, data=data, partial=True,
    )
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    try:
        tx = accounting_statement_service.update_transaction(
            tx, serializer, mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc))
    return CreditCardTransactionSerializer(tx).data


def finalize_statement(arguments):
    statement = _get_statement_or_error(arguments.get('statement_id'))
    try:
        statement = accounting_statement_service.finalize_statement(
            statement, mcp_actor(), force=bool(arguments.get('force')),
        )
    except ValueError as exc:
        raise ToolError(str(exc))
    return {
        'statement': CreditCardStatementSerializer(statement).data,
        'category_totals': accounting_statement_service
        .statement_category_totals(statement),
    }


def reopen_statement(arguments):
    statement = _get_statement_or_error(arguments.get('statement_id'))
    try:
        statement = accounting_statement_service.reopen_statement(
            statement, mcp_actor(),
        )
    except ValueError as exc:
        raise ToolError(str(exc))
    return CreditCardStatementSerializer(statement).data


def list_statements(arguments):
    queryset = CreditCardStatement.objects.all()
    year = arguments.get('year')
    if year:
        try:
            queryset = queryset.filter(period_date__year=int(year))
        except (TypeError, ValueError):
            raise ToolError("El parámetro 'year' debe ser un año válido.")
    if arguments.get('card_name'):
        queryset = queryset.filter(card_name=arguments['card_name'])
    if arguments.get('status'):
        queryset = queryset.filter(status=arguments['status'])
    data = CreditCardStatementSerializer(queryset, many=True).data
    return {'count': len(data), 'results': data}


def get_statement(arguments):
    statement = _get_statement_or_error(arguments.get('statement_id'))
    return CreditCardStatementDetailSerializer(statement).data


def delete_statement(arguments):
    statement = _get_statement_or_error(arguments.get('statement_id'))
    if statement.status != CreditCardStatement.Status.DRAFT:
        raise ToolError(
            'Solo se pueden borrar extractos en borrador desde el chat. '
            'Usa reopen_statement primero, o el panel.'
        )
    from content.services import accounting_service
    from content.views.accounting import EntityType

    accounting_service.delete_record(
        EntityType.STATEMENT, statement, mcp_actor(),
    )
    return {'deleted': True}


def list_merchant_aliases(arguments):
    queryset = MerchantAlias.objects.all()
    if arguments.get('q'):
        from django.db.models import Q

        term = arguments['q']
        queryset = queryset.filter(
            Q(match_text__icontains=term) | Q(merchant_name__icontains=term),
        )
    data = MerchantAliasSerializer(queryset, many=True).data
    return {'count': len(data), 'results': data}


def update_merchant_alias(arguments):
    alias_id = arguments.get('alias_id')
    try:
        alias = MerchantAlias.objects.get(pk=int(alias_id))
    except (MerchantAlias.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe un alias con id={alias_id}.')
    data = {key: value for key, value in arguments.items() if key != 'alias_id'}
    serializer = MerchantAliasWriteSerializer(alias, data=data, partial=True)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    alias = accounting_statement_service.update_merchant_alias(
        alias, serializer, mcp_actor(),
    )
    return MerchantAliasSerializer(alias).data


def delete_merchant_alias(arguments):
    alias_id = arguments.get('alias_id')
    try:
        alias = MerchantAlias.objects.get(pk=int(alias_id))
    except (MerchantAlias.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe un alias con id={alias_id}.')
    accounting_statement_service.delete_merchant_alias(alias, mcp_actor())
    return {'deleted': True}


# ── Schemas ──

_CATEGORY_ENUM = {'type': 'string', 'enum': list(TransactionCategory.values)}

_TX_PROPS = {
    'transaction_date': {'type': 'string', 'description': 'Fecha YYYY-MM-DD.'},
    'raw_description': {
        'type': 'string',
        'description': 'Descripción EXACTA como aparece en el extracto.',
    },
    'merchant_name': {'type': 'string'},
    'category': _CATEGORY_ENUM,
    'amount': {
        'type': 'number',
        'description': (
            'Valor COP con el que la línea suma en "Compras del mes" '
            '(compra nueva en cuotas: el valor TOTAL, no la cuota).'
        ),
    },
    'original_amount': {'type': 'number'},
    'original_currency': {'type': 'string', 'description': "P. ej. 'USD'."},
    'installment_number': {'type': 'integer'},
    'installments_total': {'type': 'integer'},
    'is_identified': {'type': 'boolean'},
    'is_reversal': {
        'type': 'boolean',
        'description': (
            'Reversión/devolución: monto negativo, misma categoría del '
            'cargo. No suma al cierre contra purchases_total.'
        ),
    },
    'notes': {'type': 'string'},
}

_STATEMENT_HEADER_PROPS = {
    'card_name': {'type': 'string'},
    'period_date': {
        'type': 'string',
        'description': "Mes de corte 'YYYY-MM'.",
    },
    'purchases_total': {
        'type': 'number',
        'description': 'Total de compras del extracto (ancla de validación).',
    },
    'previous_balance': {'type': 'number'},
    'payments_total': {'type': 'number'},
    'interest_and_fees': {'type': 'number'},
    'closing_balance': {'type': 'number'},
    'minimum_payment': {'type': 'number'},
    'due_date': {'type': 'string', 'description': 'Fecha YYYY-MM-DD.'},
    'notes': {'type': 'string'},
    'source_ref': {
        'type': 'string',
        'description': "Idempotencia opcional, p. ej. 'statement:<hash>'.",
    },
}

_STATEMENT_ID_PROP = {'statement_id': {'type': 'integer'}}


STATEMENT_TOOLS = close_root_schemas([
    {
        'name': 'get_statement_instructions',
        'area': 'cards',
        'description': (
            'LLAMA ESTA HERRAMIENTA PRIMERO antes de procesar cualquier '
            'extracto de tarjeta de crédito. Devuelve el flujo completo por '
            'fases (verificar mes, extraer, resolver comercios con '
            'aprobación del usuario, guardar, consolidar) y el vocabulario '
            'de categorías.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': get_statement_instructions,
    },
    {
        'name': 'get_statement_status',
        'area': 'cards',
        'description': (
            'Grilla de 12 meses del año: qué meses tienen extracto '
            'procesado/borrador/pendiente por tarjeta. Úsala para validar '
            'si un extracto ya fue procesado antes de crear uno.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'year': {'type': 'integer'},
                'card_name': {'type': 'string'},
            },
        },
        'handler': get_statement_status,
    },
    {
        'name': 'create_statement',
        'area': 'cards',
        'description': (
            'Crea un extracto en BORRADOR con todas sus transacciones en una '
            'sola llamada atómica. Los alias de comercio ya aprendidos se '
            'aplican automáticamente. Si ya existe extracto de esa tarjeta y '
            'mes, falla indicando el id existente.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_STATEMENT_HEADER_PROPS,
                'transactions': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': _TX_PROPS,
                        'required': [
                            'transaction_date', 'raw_description', 'amount',
                        ],
                    },
                },
            },
            'required': [
                'card_name', 'period_date', 'purchases_total', 'transactions',
            ],
        },
        'handler': create_statement,
    },
    {
        'name': 'resolve_merchants',
        'area': 'cards',
        'description': (
            'Busca descripciones crudas del extracto en los alias '
            'aprendidos. Devuelve resueltas (comercio + categoría), '
            'gateway_hints (pasarelas conocidas: verificar comercio real '
            'antes de asignar) y no resueltas (para investigar y proponer '
            'al usuario).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'raw_descriptions': {
                    'type': 'array', 'items': {'type': 'string'},
                },
            },
            'required': ['raw_descriptions'],
        },
        'handler': resolve_merchants,
    },
    {
        'name': 'save_merchant_aliases',
        'area': 'cards',
        'description': (
            'Guarda alias de comercio APROBADOS EXPLÍCITAMENTE por el '
            'usuario en el chat (nunca los guardes sin aprobación). Los '
            'alias son globales y se guardan siempre. Con statement_id, '
            'además los aplica a las transacciones no identificadas de ese '
            'borrador; si no se aplicó nada (extracto procesado, '
            'inexistente o sin coincidencias) la respuesta lo explica en '
            "'warning'."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'aliases': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'raw_description': {'type': 'string'},
                            'merchant_name': {'type': 'string'},
                            'category': _CATEGORY_ENUM,
                            'is_gateway': {
                                'type': 'boolean',
                                'description': (
                                    'Pasarela de pago (EBANX, MERCADOPAGO, '
                                    'DLOCAL...): nunca se auto-aplica, solo '
                                    'aparece como pista a verificar.'
                                ),
                            },
                        },
                        'required': ['raw_description', 'merchant_name'],
                    },
                },
                **_STATEMENT_ID_PROP,
            },
            'required': ['aliases'],
        },
        'handler': save_merchant_aliases,
    },
    {
        'name': 'update_statement',
        'area': 'cards',
        'description': 'Actualiza (parcial) el encabezado de un extracto.',
        'input_schema': {
            'type': 'object',
            'properties': {**_STATEMENT_ID_PROP, **_STATEMENT_HEADER_PROPS},
            'required': ['statement_id'],
        },
        'handler': update_statement,
    },
    {
        'name': 'update_statement_transaction',
        'area': 'cards',
        'description': (
            'Corrige una transacción de un extracto en borrador (comercio, '
            'categoría, valor, cuotas...).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'transaction_id': {'type': 'integer'},
                **_TX_PROPS,
            },
            'required': ['transaction_id'],
        },
        'handler': update_statement_transaction,
    },
    {
        'name': 'finalize_statement',
        'area': 'cards',
        'description': (
            'Consolida un extracto: valida que la suma de transacciones '
            'cuadre con purchases_total (tolerancia ±1 COP) y lo marca como '
            'procesado. Si no cuadra devuelve la diferencia; force=true '
            'cierra igual (requiere confirmación del usuario).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_STATEMENT_ID_PROP,
                'force': {'type': 'boolean', 'default': False},
            },
            'required': ['statement_id'],
        },
        'handler': finalize_statement,
    },
    {
        'name': 'reopen_statement',
        'area': 'cards',
        'description': 'Devuelve un extracto procesado a borrador para corregirlo.',
        'input_schema': {
            'type': 'object',
            'properties': _STATEMENT_ID_PROP,
            'required': ['statement_id'],
        },
        'handler': reopen_statement,
    },
    {
        'name': 'list_statements',
        'area': 'cards',
        'description': (
            'Lista extractos. Filtros: year, card_name, status '
            '(draft/processed).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'year': {'type': 'integer'},
                'card_name': {'type': 'string'},
                'status': {'type': 'string', 'enum': ['draft', 'processed']},
            },
        },
        'handler': list_statements,
    },
    {
        'name': 'get_statement',
        'area': 'cards',
        'description': (
            'Detalle completo de un extracto: encabezado, transacciones y '
            'totales por categoría.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _STATEMENT_ID_PROP,
            'required': ['statement_id'],
        },
        'handler': get_statement,
    },
    {
        'name': 'delete_statement',
        'area': 'cards',
        'description': (
            'Elimina un extracto EN BORRADOR con sus transacciones (para '
            'reprocesar). Los procesados requieren reopen_statement o el '
            'panel.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _STATEMENT_ID_PROP,
            'required': ['statement_id'],
        },
        'handler': delete_statement,
    },
    {
        'name': 'list_merchant_aliases',
        'area': 'cards',
        'description': 'Lista los alias de comercio aprendidos. Filtro: q.',
        'input_schema': {
            'type': 'object',
            'properties': {'q': {'type': 'string'}},
        },
        'handler': list_merchant_aliases,
    },
    {
        'name': 'update_merchant_alias',
        'area': 'cards',
        'description': (
            'Corrige un alias aprendido (comercio, categoría, texto, flag '
            'de pasarela). El texto se normaliza al guardar (mayúsculas, '
            'espacios colapsados, se eliminan tokens de 5+ dígitos).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'alias_id': {'type': 'integer'},
                'match_text': {'type': 'string'},
                'merchant_name': {'type': 'string'},
                'default_category': _CATEGORY_ENUM,
                'is_gateway': {'type': 'boolean'},
                'notes': {'type': 'string'},
            },
            'required': ['alias_id'],
        },
        'handler': update_merchant_alias,
    },
    {
        'name': 'delete_merchant_alias',
        'area': 'cards',
        'description': (
            'Elimina un alias global de comercio por ID. No reescribe '
            'transacciones históricas que ya fueron identificadas con él.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {'alias_id': {'type': 'integer'}},
            'required': ['alias_id'],
        },
        'handler': delete_merchant_alias,
    },
])
