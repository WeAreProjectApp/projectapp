"""Business logic for the accounting module.

Every mutation goes through create_record/update_record/delete_record:
the same function mutates, writes the AccountingChangeLog row and
enqueues the email notification (the established convention — explicit
logging in services, not signals).

Pocket <-> income/expense sync invariant: exactly two one-way sync
writers exist. `_sync_pocket` (record -> movement) and `_sync_from_pocket`
(movement -> record) each write the other side with plain ORM
create()/save(update_fields=...) and never re-enter the service pipeline,
so ping-pong loops are impossible by construction.
"""
from content.services.entity_history import historical_write
import logging
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import (
    Avg, BigIntegerField, Count, DecimalField, Exists, F, Max, Min, OuterRef, Q, Subquery, Sum, Value,
)
from django.db.models.functions import Coalesce, Greatest

from accounts.models import Project, UserProfile
from content.api_errors import ProposalActionError
from content.utils import format_cop_email, today_bogota
from content.models import (
    AccountingChangeLog,
    AdsSpendRecord,
    CardBalanceSnapshot,
    CreditCard,
    CreditCardStatement,
    CreditCardTransaction,
    Document,
    ExpenseRecord,
    HostingRecord,
    IncomeRecord,
    Ledger,
    MerchantAlias,
    NotificationRecipient,
    PocketMovement,
    RecurringPayment,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.serializers.accounting import month_label, month_period, split_half

logger = logging.getLogger(__name__)

EntityType = AccountingChangeLog.EntityType
Action = AccountingChangeLog.Action

ENTITY_MODELS = {
    EntityType.INCOME: IncomeRecord,
    EntityType.EXPENSE: ExpenseRecord,
    EntityType.HOSTING: HostingRecord,
    EntityType.POCKET: PocketMovement,
    EntityType.RECURRING: RecurringPayment,
    EntityType.ADS: AdsSpendRecord,
    EntityType.CARD_SNAPSHOT: CardBalanceSnapshot,
    EntityType.CREDIT_CARD: CreditCard,
    EntityType.STATEMENT: CreditCardStatement,
    EntityType.STATEMENT_TX: CreditCardTransaction,
    EntityType.MERCHANT_ALIAS: MerchantAlias,
    EntityType.NOTIFICATION_RECIPIENT: NotificationRecipient,
}

TRACKED_FIELDS = {
    EntityType.INCOME: [
        ('concept', 'Concepto'),
        ('kind', 'Tipo'),
        ('ledger', 'Contabilidad'),
        ('client', 'Cliente'),
        ('project', 'Proyecto'),
        ('origin', 'Origen'),
        ('is_receivable_candidate', 'Pendiente por cobrar'),
        ('collection_confidence', 'Probabilidad de cobro'),
        ('period_date', 'Período'),
        ('period_start', 'Inicio del período cubierto'),
        ('period_end', 'Fin del período cubierto'),
        ('period_cadence', 'Periodicidad del período'),
        ('destination', 'Destino'),
        ('total_amount', 'Monto total'),
        ('vat_rate', 'IVA (%)'),
        ('gustavo_amount', 'Monto Gustavo'),
        ('carlos_amount', 'Monto Carlos'),
        ('expected_income', 'Ingreso esperado'),
        # Tracked but absent from the write serializer: muting is audited, and
        # only the mute endpoint can write it.
        ('reminders_muted', 'Avisos silenciados'),
        ('reminders_muted_until', 'Silenciado hasta'),
        ('notes', 'Notas'),
    ],
    EntityType.EXPENSE: [
        ('concept', 'Concepto'),
        ('ledger', 'Contabilidad'),
        ('period_date', 'Período'),
        ('category', 'Categoría'),
        ('total_amount', 'Monto total'),
        ('vat_rate', 'IVA (%)'),
        ('gustavo_amount', 'Monto Gustavo'),
        ('carlos_amount', 'Monto Carlos'),
        ('notes', 'Notas'),
    ],
    EntityType.HOSTING: [
        ('client', 'Cliente vinculado'),
        ('project', 'Proyecto'),
        ('client_name', 'Cliente'),
        ('client_email', 'Email del cliente'),
        ('client_contact_name', 'Contacto del cliente'),
        ('client_identification', 'Identificación del cliente'),
        ('domain_url', 'Dominio'),
        ('monthly_value', 'Valor mensual'),
        ('payment_modality', 'Modalidad de pago'),
        ('benefit', 'Beneficio'),
        ('valid_from', 'Vigente desde'),
        ('valid_to', 'Vigente hasta'),
        ('cycles_count', 'Ciclos'),
        ('payment_per_cycle', 'Pago por ciclo'),
        ('vat_rate', 'IVA (%)'),
        ('total_paid', 'Total pagado'),
        ('is_active', 'Activo'),
        ('notes', 'Notas'),
    ],
    EntityType.POCKET: [
        ('concept', 'Concepto'),
        ('movement_date', 'Fecha'),
        ('direction', 'Tipo'),
        ('amount', 'Valor'),
        ('notes', 'Notas'),
    ],
    # Not in ENTITY_MODELS on purpose: projects and cuentas never enter the
    # generic create/update/delete pipeline — only the coherence operations
    # (change-client, draft moves, lifecycle transitions) write these rows.
    EntityType.PROJECT: [
        ('name', 'Nombre'),
        ('description', 'Descripción'),
        ('status', 'Estado'),
        ('client', 'Cliente'),
    ],
    EntityType.COLLECTION_ACCOUNT: [
        ('title', 'Título'),
        ('client_user', 'Cliente'),
        ('project', 'Proyecto'),
        ('folder', 'Carpeta'),
        ('commercial_status', 'Estado comercial'),
        ('subtotal', 'Valor antes de IVA'),
        ('tax_total', 'IVA'),
        ('total', 'Total con IVA'),
    ],
    EntityType.DOCUMENT_FOLDER: [
        ('name', 'Nombre'),
        ('client_user', 'Cliente'),
        ('project', 'Proyecto'),
    ],
    EntityType.DOCUMENT: [
        ('title', 'Título'),
        ('client_user', 'Cliente'),
        ('project', 'Proyecto'),
        ('folder', 'Carpeta'),
    ],
    EntityType.RECURRING: [
        ('name', 'Nombre'),
        ('price', 'Precio'),
        ('currency', 'Moneda'),
        ('cop_equivalent', 'Equivalente COP'),
        ('payment_method', 'Método de pago'),
        ('frequency', 'Frecuencia'),
        ('custom_months', 'Meses del ciclo'),
        ('billing_day', 'Día de cobro'),
        ('cycle_anchor_date', 'Fecha de referencia del cobro'),
        ('cost_type', 'Tipo de costo'),
        ('category', 'Categoría'),
        ('is_active', 'Activo'),
        ('is_archived', 'Archivado'),
        ('archived_at', 'Archivado el'),
        ('reminders_muted', 'Avisos silenciados'),
        ('reminders_muted_until', 'Silenciado hasta'),
        ('notes', 'Notas'),
    ],
    EntityType.ADS: [
        ('spend_date', 'Fecha'),
        ('platform', 'Plataforma'),
        ('origin_card', 'Tarjeta origen'),
        ('amount', 'Valor'),
        ('notes', 'Notas'),
    ],
    EntityType.CARD_SNAPSHOT: [
        ('snapshot_date', 'Fecha'),
        ('card_name', 'Tarjeta'),
        ('available_amount', 'Disponible'),
        ('debt_amount', 'Deuda'),
        ('notes', 'Notas'),
    ],
    EntityType.CREDIT_CARD: [
        ('name', 'Nombre'),
        ('credit_limit', 'Cupo'),
        ('is_active', 'Activa'),
        ('statements_since', 'Extractos desde'),
        ('notes', 'Notas'),
    ],
    EntityType.STATEMENT: [
        ('card_name', 'Tarjeta'),
        ('period_date', 'Período'),
        ('status', 'Estado'),
        ('purchases_total', 'Total compras'),
        ('previous_balance', 'Saldo anterior'),
        ('payments_total', 'Pagos y abonos'),
        ('interest_and_fees', 'Intereses y comisiones'),
        ('closing_balance', 'Saldo de cierre'),
        ('minimum_payment', 'Pago mínimo'),
        ('due_date', 'Fecha límite de pago'),
        ('notes', 'Notas'),
    ],
    EntityType.STATEMENT_TX: [
        ('transaction_date', 'Fecha'),
        ('raw_description', 'Descripción'),
        ('merchant_name', 'Comercio'),
        ('category', 'Categoría'),
        ('amount', 'Valor'),
        ('original_amount', 'Valor original'),
        ('original_currency', 'Moneda original'),
        ('installment_number', 'Cuota'),
        ('installments_total', 'Total cuotas'),
        ('is_identified', 'Identificado'),
        ('notes', 'Notas'),
    ],
    EntityType.MERCHANT_ALIAS: [
        ('match_text', 'Texto de coincidencia'),
        ('merchant_name', 'Comercio'),
        ('default_category', 'Categoría por defecto'),
        ('notes', 'Notas'),
    ],
    EntityType.NOTIFICATION_RECIPIENT: [
        ('email', 'Correo'),
        ('is_active', 'Activo'),
        ('notes', 'Notas'),
    ],
    EntityType.SETTINGS: [
        ('notifications_enabled', 'Notificaciones activas'),
        ('card_reminder_enabled', 'Recordatorio de deuda de tarjetas'),
        ('statement_reminder_enabled', 'Recordatorio de extractos'),
        ('hosting_expiry_reminder_enabled', 'Avisos de vencimiento de hostings'),
        ('payment_calendar_enabled', 'Calendario de cobros y pagos'),
        ('overdue_reminder_frequency', 'Frecuencia de avisos vencidos'),
        ('usd_exchange_rate', 'Tasa de cambio USD'),
        ('income_default_view_mode', 'Vista por defecto de ingresos'),
        ('collection_accounts_view_mode', 'Vista de cuentas de cobro'),
        ('collection_accounts_group_by', 'Agrupación de cuentas de cobro'),
    ],
}


# ── Audit core ──

def display_value(instance, field_name):
    """Human-readable value of a field (choice display when available)."""
    display_getter = getattr(instance, f'get_{field_name}_display', None)
    if callable(display_getter):
        return str(display_getter())
    value = getattr(instance, field_name)
    if value is None:
        return ''
    if field_name == 'vat_rate':
        from content.services.accounting_display import format_percentage
        return format_percentage(value)
    if isinstance(value, bool):
        return 'Sí' if value else 'No'
    if isinstance(value, get_user_model()):
        # Project.client and Document.client_user point at the User, not the
        # profile; render the same display name the panel shows so both key
        # spaces read identically in the audit table.
        profile = getattr(value, 'profile', None)
        if profile is not None:
            from accounts.services.proposal_client_service import (
                build_client_display_name,
            )

            return build_client_display_name(profile)
        return value.get_full_name() or value.email or value.username
    if isinstance(value, UserProfile):
        # A client FK renders as "email (Client)" through __str__, which is
        # noise in the audit table and the notification email.
        from accounts.services.proposal_client_service import (
            build_client_display_name,
        )

        return build_client_display_name(value)
    if isinstance(value, Project):
        # Same reason: Project.__str__ is "{name} — {client.email}", so
        # without this every project change would put a client's address in
        # the audit table and in the mail both partners receive.
        return value.name
    if isinstance(value, list):
        return ', '.join(str(item) for item in value)
    if isinstance(value, Decimal):
        # Money field: audit rows and emails show COP formatting.
        return f'${format_cop_email(value)}'
    return str(value)


def snapshot_values(instance, entity_type):
    """Map of tracked field -> displayed value for diffing."""
    return {
        field: display_value(instance, field)
        for field, _label in TRACKED_FIELDS[entity_type]
    }


def compute_changes(entity_type, old_values, new_values):
    """Field-level diff as the JSON stored in AccountingChangeLog.changes."""
    return [
        {
            'field': field,
            'label': label,
            'old': old_values.get(field, ''),
            'new': new_values.get(field, ''),
        }
        for field, label in TRACKED_FIELDS[entity_type]
        if old_values.get(field, '') != new_values.get(field, '')
    ]


def object_repr(entity_type, instance):
    """Human-readable identity stored on the audit row."""
    if entity_type in (EntityType.INCOME, EntityType.EXPENSE, EntityType.POCKET):
        return instance.concept
    if entity_type == EntityType.HOSTING:
        # Both halves: the audit row has to stay recognisable years later,
        # and either one alone is ambiguous across a client's hostings.
        return instance.display_label
    if entity_type == EntityType.RECURRING:
        return instance.name
    if entity_type == EntityType.ADS:
        return f'{instance.get_platform_display()} — {instance.spend_date}'
    if entity_type == EntityType.CARD_SNAPSHOT:
        return f'{instance.card_name} — {instance.snapshot_date}'
    if entity_type == EntityType.CREDIT_CARD:
        return instance.name
    if entity_type == EntityType.STATEMENT:
        return f'{instance.card_name} — {month_label(instance.period_date)}'
    if entity_type == EntityType.STATEMENT_TX:
        return instance.merchant_name or instance.raw_description
    if entity_type == EntityType.MERCHANT_ALIAS:
        return instance.match_text
    if entity_type == EntityType.NOTIFICATION_RECIPIENT:
        return instance.email
    if entity_type == EntityType.PROJECT:
        return instance.name
    if entity_type == EntityType.COLLECTION_ACCOUNT:
        # The number survives the document; the title is the draft fallback.
        return instance.public_number or instance.title
    if entity_type == EntityType.DOCUMENT:
        return instance.title
    if entity_type == EntityType.DOCUMENT_FOLDER:
        return instance.name
    return 'Configuración contable'


def log_accounting_change(
    *,
    entity_type,
    object_id,
    object_repr,
    action,
    changes=None,
    actor=None,
    movement_direction=None,
):
    """Append an AccountingChangeLog row."""
    changes = changes or []
    if entity_type == EntityType.POCKET and movement_direction is None:
        movement_direction = _movement_direction_from_changes(changes, action)
    elif entity_type != EntityType.POCKET:
        movement_direction = None
    return AccountingChangeLog.objects.create(
        entity_type=entity_type,
        object_id=object_id,
        object_repr=object_repr[:255],
        action=action,
        movement_direction=movement_direction,
        changes=changes,
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        actor_username=getattr(actor, 'username', '') or '',
    )


def _movement_direction_from_changes(changes, action):
    """Recover direction from a complete historical Pocket diff when possible."""
    for change in changes:
        if change.get('field') != 'direction':
            continue
        value = (
            change.get('old')
            if action == Action.DELETED
            else change.get('new') or change.get('old')
        )
        normalized = str(value or '').strip().lower()
        return {
            'in': AccountingChangeLog.MovementDirection.IN,
            'ingreso': AccountingChangeLog.MovementDirection.IN,
            'out': AccountingChangeLog.MovementDirection.OUT,
            'egreso': AccountingChangeLog.MovementDirection.OUT,
        }.get(normalized)
    return None


def log_entity_diff(entity_type, instance, old_values, user):
    """One audit row for a tracked entity mutated OUTSIDE the generic
    pipeline (projects, cuentas de cobro): diff against ``old_values`` and
    log it. Never notifies — the coherence writers follow the bulk
    convention. Returns the changes list (empty = nothing written).
    """
    changes = compute_changes(
        entity_type, old_values, snapshot_values(instance, entity_type),
    )
    if changes:
        log_accounting_change(
            entity_type=entity_type,
            object_id=instance.pk,
            object_repr=object_repr(entity_type, instance),
            action=Action.UPDATED,
            changes=changes,
            actor=user,
        )
    return changes


def _notify(change_log):
    """Enqueue the change email; failures never break the mutation."""
    try:
        from content.tasks import send_accounting_change_email

        send_accounting_change_email(change_log.id)
    except Exception:
        logger.warning(
            'Could not enqueue accounting notification (change_log=%s)',
            change_log.id,
            exc_info=True,
        )


# ── Generic mutation pipeline ──

def _ensure_pocket_update_allowed(entity_type, instance, serializer):
    """Linked movements mirror an income/expense; their direction is fixed."""
    if entity_type != EntityType.POCKET or not instance.is_auto_managed:
        return
    new_direction = serializer.validated_data.get('direction')
    if new_direction and new_direction != instance.direction:
        raise ProposalActionError(
            'La dirección de un movimiento vinculado a un ingreso o gasto '
            'no se puede cambiar.',
            code='linked_direction_locked',
            hint='Elimina el movimiento y créalo de nuevo con la otra dirección.',
        )
    new_amount = serializer.validated_data.get('amount')
    if (
        instance.is_shared
        and new_amount is not None
        and new_amount != instance.amount
    ):
        # The invariant movement.amount == Σ children has no DB constraint;
        # this guard and the _sync_movement one are its only keepers.
        raise ProposalActionError(
            'El valor de un abono no se puede editar: es la suma de los '
            'ingresos que cubre.',
            code='abono_amount_locked',
            hint='Desde el MCP usa update_income_abono para corregir el monto '
                 'y el reparto juntos, o elimina el movimiento completo.',
        )


def _ensure_shared_child_update_allowed(entity_type, instance, serializer):
    """A liquid child of an abono keeps its money fields frozen.

    Its total_amount is one slice of the shared movement's amount: resizing
    it (or flipping destination/kind, which would detach the movement) breaks
    movement.amount == Σ children silently. Concept, notes, dates, split and
    expected_income stay editable — re-pointing expected_income is on purpose
    the correction tool for a mis-imputed allocation and the way a saldo a
    favor gets applied to a future expected income.
    """
    if entity_type != EntityType.INCOME:
        return
    movement = instance.pocket_movement
    if movement is None or not movement.is_shared:
        return
    data = serializer.validated_data
    changed = (
        ('total_amount' in data and data['total_amount'] != instance.total_amount)
        or ('destination' in data and data['destination'] != instance.destination)
        or ('kind' in data and data['kind'] != instance.kind)
    )
    if changed:
        raise ProposalActionError(
            'Este ingreso hace parte de un abono: su monto, destino y tipo '
            'no se pueden editar.',
            code='abono_child_locked',
            hint='Elimina el movimiento del bolsillo para deshacer el abono '
                 'completo.',
        )


def _pop_mirror_ledger(entity_type, serializer):
    """Extract the write-only pocket `ledger` field (not a model field)."""
    if entity_type != EntityType.POCKET:
        return None
    return serializer.validated_data.pop('ledger', None)


def _pop_register_in_pocket(entity_type, serializer):
    """Extract the write-only expense `register_in_pocket` flag."""
    if entity_type != EntityType.EXPENSE:
        return None
    return serializer.validated_data.pop('register_in_pocket', None)


@historical_write
def create_record(entity_type, serializer, user, notify=True, *,
                  shared_pocket_movement=None):
    """Persist a validated write serializer, audit it and notify.

    ``notify=False`` still writes the audit row but skips the email. It exists
    for flows that compose several records in one user action (an income
    settlement creates the liquid child plus its deductions and follow-up
    expected incomes) and should read as a single event in the inbox.

    ``shared_pocket_movement`` attaches the record to a movement the abono
    flow already created and audited. The per-record pocket sync is skipped
    entirely on purpose: letting it run would either spawn a second movement
    or mirror the shared one down to a single child's amount and concept.
    """
    mirror_ledger = _pop_mirror_ledger(entity_type, serializer)
    register_in_pocket = _pop_register_in_pocket(entity_type, serializer)
    expected = None
    was_paid = False
    with transaction.atomic():
        if entity_type in (EntityType.HOSTING, EntityType.INCOME):
            from accounts.services.billing_locks import lock_billing_rows
            from content.serializers.accounting import validate_project_client_match
            proposed_project = serializer.validated_data.get('project')
            expected = serializer.validated_data.get('expected_income') if entity_type == EntityType.INCOME else None
            locked = lock_billing_rows(project_ids=[proposed_project.pk if proposed_project else None],
                                       income_ids=[expected.pk] if expected else [],
                                       include_origin_documents=bool(expected))
            if proposed_project:
                serializer.validated_data['project'] = locked.projects[proposed_project.pk]
                validate_project_client_match(locked.projects[proposed_project.pk], serializer.validated_data.get('client'))
            if expected:
                if expected.pk not in locked.incomes:
                    from accounts.services.billing_access import BillingConflict
                    raise BillingConflict()
                expected = locked.incomes[expected.pk]
                serializer.validated_data['expected_income'] = expected
                from accounts.services.billing_locks import current_income_paid_total
                was_paid = current_income_paid_total(expected) >= expected.total_amount
            serializer._validated_data = serializer.validate(dict(serializer.validated_data))
        if shared_pocket_movement is not None:
            instance = serializer.save(
                created_by=user, pocket_movement=shared_pocket_movement,
            )
        else:
            instance = serializer.save(created_by=user)
            _sync_pocket(
                entity_type, instance, user,
                register_in_pocket=register_in_pocket,
            )
            if entity_type == EntityType.POCKET:
                _sync_from_pocket(instance, mirror_ledger, user, is_create=True)
        if expected and instance.kind == IncomeRecord.Kind.LIQUID and not serializer.context.get('settlement'):
            _complete_linked_income(expected, was_paid, user)
        if entity_type == EntityType.HOSTING:
            from accounts.services.hosting_context import register_new_hosting_origin
            register_new_hosting_origin(instance, user)
    new_values = snapshot_values(instance, entity_type)
    changes = compute_changes(entity_type, {}, new_values)
    change_log = log_accounting_change(
        entity_type=entity_type,
        object_id=instance.pk,
        object_repr=object_repr(entity_type, instance),
        action=Action.CREATED,
        changes=changes,
        actor=user,
        movement_direction=(
            instance.direction if entity_type == EntityType.POCKET else None
        ),
    )
    if notify:
        _notify(change_log)
    return instance


@historical_write
def update_record(entity_type, instance, serializer, user, notify=True):
    """Apply a validated partial update, audit the diff and notify.

    See ``create_record`` for why ``notify=False`` exists.
    """
    expected = None
    was_paid = False
    previous_expected = None
    pocket_parents = []
    with transaction.atomic():
        if entity_type == EntityType.POCKET:
            from accounts.services.billing_locks import current_income_paid_total, lock_billing_rows
            from accounts.services.billing_access import BillingConflict

            discovered = list(IncomeRecord.objects.filter(pocket_movement=instance)
                              .values_list('pk', 'expected_income_id'))
            parent_ids = {parent_id for _, parent_id in discovered if parent_id}
            locked = lock_billing_rows(
                income_ids=[*parent_ids, *(pk for pk, _ in discovered)],
                include_income_children=True, include_origin_documents=True,
            )
            instance = PocketMovement.objects.select_for_update().get(pk=instance.pk)
            if sorted(discovered) != list(IncomeRecord.objects.filter(pocket_movement=instance)
                                         .order_by('pk').values_list('pk', 'expected_income_id')):
                raise BillingConflict()
            serializer.instance = instance
            serializer._validated_data = serializer.validate(dict(serializer.validated_data))
            pocket_parents = [(locked.incomes[pk], current_income_paid_total(locked.incomes[pk])
                               >= locked.incomes[pk].total_amount) for pk in sorted(parent_ids)]
            if len(discovered) == 1 and parent_ids and 'amount' in serializer.validated_data:
                parent = locked.incomes[next(iter(parent_ids))]
                child = locked.incomes[discovered[0][0]]
                available = parent.total_amount - current_income_paid_total(parent) + child.total_amount
                if serializer.validated_data['amount'] > available:
                    raise ValueError('El valor del abono supera el saldo disponible del ingreso.')
        if entity_type in (EntityType.HOSTING, EntityType.INCOME):
            from accounts.services.billing_locks import lock_billing_rows
            from accounts.services.billing_reassignment import validate_financial_reassignment
            target = serializer.validated_data.get('project')
            expected = None
            if entity_type == EntityType.INCOME:
                expected = (serializer.validated_data['expected_income']
                            if 'expected_income' in serializer.validated_data else instance.expected_income)
            locked = lock_billing_rows(
                income_ids=([instance.pk] + ([expected.pk] if expected else [])
                            + ([instance.expected_income_id] if instance.expected_income_id else [])
                            if entity_type == EntityType.INCOME else []),
                hosting_ids=[instance.pk] if entity_type == EntityType.HOSTING else [],
                project_ids=[target.pk if target else None],
                include_income_children=True, include_origin_documents=True,
            )
            instance = (locked.incomes if entity_type == EntityType.INCOME else locked.hostings)[instance.pk]
            serializer.instance = instance
            if entity_type == EntityType.INCOME and instance.expected_income_id:
                previous_expected = locked.incomes.get(instance.expected_income_id)
                if previous_expected is None:
                    from accounts.services.billing_access import BillingConflict
                    raise BillingConflict()
            if (entity_type == EntityType.INCOME and 'expected_income' not in serializer.validated_data
                    and instance.expected_income_id != (expected.pk if expected else None)):
                from accounts.services.billing_access import BillingConflict
                raise BillingConflict()
            if expected:
                from accounts.services.billing_locks import current_income_paid_total
                expected = locked.incomes[expected.pk]
                was_paid = current_income_paid_total(expected) >= expected.total_amount
                if 'expected_income' in serializer.validated_data:
                    serializer.validated_data['expected_income'] = expected
            if target:
                serializer.validated_data['project'] = locked.projects[target.pk]
            serializer._validated_data = serializer.validate(dict(serializer.validated_data))
            validate_financial_reassignment(instance, serializer.validated_data)
        if (
            entity_type == EntityType.INCOME
            and {'total_amount', 'vat_rate'} & serializer.validated_data.keys()
        ):
            from content.serializers.accounting_vat import validate_income_vat_change
            validate_income_vat_change(
                instance, serializer.validated_data,
                serializer.context.get('settlement'),
            )
        _ensure_pocket_update_allowed(entity_type, instance, serializer)
        _ensure_shared_child_update_allowed(entity_type, instance, serializer)
        mirror_ledger = _pop_mirror_ledger(entity_type, serializer)
        register_in_pocket = _pop_register_in_pocket(entity_type, serializer)
        old_values = snapshot_values(instance, entity_type)
        old_client_id = getattr(instance, 'client_id', None)
        old_project_id = getattr(instance, 'project_id', None)
        instance = serializer.save()
        _sync_pocket(
            entity_type, instance, user,
            register_in_pocket=register_in_pocket,
        )
        if entity_type == EntityType.POCKET:
            _sync_from_pocket(instance, mirror_ledger, user, is_create=False)
            for parent, parent_was_paid in pocket_parents:
                _complete_linked_income(parent, parent_was_paid, user)
        if (
            entity_type == EntityType.INCOME
            and instance.kind == IncomeRecord.Kind.EXPECTED
            and instance.client_id != old_client_id
        ):
            _cascade_client_to_liquid_children(instance, user)
        if (
            entity_type in (EntityType.INCOME, EntityType.HOSTING)
            and instance.project_id != old_project_id
        ):
            if (
                entity_type == EntityType.INCOME
                and instance.kind == IncomeRecord.Kind.EXPECTED
            ):
                # Single-PATCH parity with bulk_assign_project: the liquids
                # that settle this income follow its project too.
                _cascade_project_to_liquid_children(instance, user)
            _sync_project_to_draft_cuentas(instance, user)
        if expected and instance.kind == IncomeRecord.Kind.LIQUID and not serializer.context.get('settlement'):
            _complete_linked_income(expected, was_paid, user)
        if previous_expected and previous_expected.pk != instance.expected_income_id:
            from content.services.accounting_settlement_service import _sync_linked_collection_accounts
            _sync_linked_collection_accounts(previous_expected, user)
    changes = compute_changes(
        entity_type, old_values, snapshot_values(instance, entity_type),
    )
    if changes:
        change_log = log_accounting_change(
            entity_type=entity_type,
            object_id=instance.pk,
            object_repr=object_repr(entity_type, instance),
            action=Action.UPDATED,
            changes=changes,
            actor=user,
            movement_direction=(
                instance.direction
                if entity_type == EntityType.POCKET
                else None
            ),
        )
        if notify:
            _notify(change_log)
    return instance


def _complete_linked_income(income, was_paid, user):
    from content.services.accounting_settlement_service import _sync_linked_collection_accounts
    from content.services.income_completion_notice_service import schedule_completion_notice

    _sync_linked_collection_accounts(income, user)
    deselect_receivable_if_closed(income, user)
    schedule_completion_notice(income, was_paid=was_paid)


def _refresh_hosting_snapshot(record):
    """Point the billing snapshot at the record's (new) client.

    Reassigning the FK leaves the snapshot holding the PREVIOUS client's
    contact data, and ``billing_email`` prefers the override — a stale
    ``client_email`` routes the cuenta de cobro to the wrong inbox. Mutates
    the instance and returns the changed field names for update_fields;
    unlinking keeps the snapshot (it is the historical billing record).

    ``project_name`` is deliberately NOT in this set: it is what the client
    bought, not how they are billed. Refreshing it from the profile would
    erase the brand on every reassignment — the bug the split fixed.
    """
    if record.client_id is None:
        return []
    from content.services.collection_account_create_service import (
        customer_snapshot_defaults,
    )

    defaults = customer_snapshot_defaults(record.client)
    updates = {
        'client_name': defaults['name'] or '',
        'client_email': defaults['email'] or '',
        'client_contact_name': defaults['contact_name'] or '',
        'client_identification': defaults['identification'] or '',
    }
    changed = []
    for field, value in updates.items():
        if getattr(record, field) != value:
            setattr(record, field, value)
            changed.append(field)
    return changed


def _cascade_client_to_liquid_children(income, user):
    """Carry an expected income's client to the liquids that settle it.

    Settlement inherits the client only at creation time; when the link is
    fixed later (bulk completion of legacy rows, or an edit), the money
    already collected would stay under the old client — or "Sin cliente" —
    and every per-client total would split one deal across two buckets.
    One audit row per child, same as bulk_assign_client.
    """
    for child in income.liquid_records.select_related('client__user'):
        if child.client_id == income.client_id:
            continue
        old_values = snapshot_values(child, EntityType.INCOME)
        child.client = income.client
        child.save(update_fields=['client', 'updated_at'])
        changes = compute_changes(
            EntityType.INCOME, old_values,
            snapshot_values(child, EntityType.INCOME),
        )
        if changes:
            log_accounting_change(
                entity_type=EntityType.INCOME,
                object_id=child.pk,
                object_repr=object_repr(EntityType.INCOME, child),
                action=Action.UPDATED,
                changes=changes,
                actor=user,
            )


def missing_record_ids(entity_type, record_ids):
    """Ids in ``record_ids`` with no row behind them, sorted.

    Kept apart from :func:`bulk_assign_client`, which stays lenient: that one
    is also called from ``collection_account_create_service`` with a pk it has
    already fetched and locked, and has no business refusing it. Deciding what
    to do about a vanished id belongs to the caller that has a user in front
    of it.
    """
    existing = set(
        ENTITY_MODELS[entity_type]
        .objects.filter(pk__in=record_ids)
        .values_list('pk', flat=True),
    )
    return sorted(set(record_ids) - existing)


@historical_write
@transaction.atomic
def bulk_assign_client(entity_type, record_ids, client, user, *, strict_ids=False):
    """Assign (or clear, with ``client=None``) the client of several records.

    The completion tool for rows created before the client link existed,
    shared by incomes and hostings. One audit row per record on purpose:
    the history is per record, and a single aggregate entry would make an
    individual timeline lie. Rows already pointing at the target client are
    skipped, so re-running the same assignment writes nothing.

    A project that no longer belongs to the new client is cleared in the
    same write — the bulk mirror of the single-record serializer rule: a
    record must never point at someone else's project, and the operator
    re-picks explicitly if the move was intentional.

    ``strict_ids=True`` requires the whole requested scope. The default
    ignores ids absent before discovery; discovered rows remain mandatory
    through the current locking reads.
    """
    model = ENTITY_MODELS[entity_type]
    if entity_type in (EntityType.INCOME, EntityType.HOSTING):
        from accounts.services.billing_locks import lock_billing_rows
        if not strict_ids:
            record_ids = list(model.objects.filter(pk__in=record_ids).values_list('pk', flat=True))
        locked = lock_billing_rows(
            income_ids=record_ids if entity_type == EntityType.INCOME else [],
            hosting_ids=record_ids if entity_type == EntityType.HOSTING else [],
            include_income_children=True, include_origin_documents=True,
        )
        selected = locked.incomes if entity_type == EntityType.INCOME else locked.hostings
        records = [row for pk, row in selected.items() if pk in record_ids]
    else:
        records = list(model.objects.select_related('client__user', 'project').filter(pk__in=record_ids))
    updated = []
    for record in records:
        if record.client_id == (client.pk if client else None):
            continue
        old_values = snapshot_values(record, entity_type)
        from accounts.services.billing_reassignment import validate_financial_reassignment
        validate_financial_reassignment(record, {'client': client})
        record.client = client
        update_fields = ['client', 'updated_at']
        project_cleared = False
        if record.project_id is not None and (
            client is None or record.project.client_id != client.user_id
        ):
            record.project = None
            update_fields.append('project')
            project_cleared = True
        if entity_type == EntityType.HOSTING:
            update_fields += _refresh_hosting_snapshot(record)
        record.save(update_fields=update_fields)
        changes = compute_changes(
            entity_type, old_values, snapshot_values(record, entity_type),
        )
        if changes:
            log_accounting_change(
                entity_type=entity_type,
                object_id=record.pk,
                object_repr=object_repr(entity_type, record),
                action=Action.UPDATED,
                changes=changes,
                actor=user,
            )
        if (
            entity_type == EntityType.INCOME
            and record.kind == IncomeRecord.Kind.EXPECTED
        ):
            _cascade_client_to_liquid_children(record, user)
            if project_cleared:
                # The children follow the parent's client AND its cleared
                # project: a liquid child must not keep pointing at the
                # previous client's project either.
                _cascade_project_to_liquid_children(record, user)
        if project_cleared:
            # Same rule for the record's own draft cuenta: it must not keep
            # pointing at the previous client's project.
            _sync_project_to_draft_cuentas(record, user)
        updated.append(record)
    return updated


def bulk_assign_income_client(income_ids, client, user):
    """Incomes flavour of :func:`bulk_assign_client` (kept for its callers)."""
    return bulk_assign_client(EntityType.INCOME, income_ids, client, user)


def _cascade_project_to_liquid_children(income, user):
    """Carry an expected income's project to the liquids that settle it.

    Same rationale as :func:`_cascade_client_to_liquid_children`: settlement
    inherits at creation time only, so a project assigned later would leave
    the collected money under "Sin proyecto" and split one deal across two
    per-project buckets. One audit row per child.
    """
    for child in income.liquid_records.select_related('project'):
        if child.project_id == income.project_id:
            continue
        old_values = snapshot_values(child, EntityType.INCOME)
        child.project = income.project
        child.save(update_fields=['project', 'updated_at'])
        changes = compute_changes(
            EntityType.INCOME, old_values,
            snapshot_values(child, EntityType.INCOME),
        )
        if changes:
            log_accounting_change(
                entity_type=EntityType.INCOME,
                object_id=child.pk,
                object_repr=object_repr(EntityType.INCOME, child),
                action=Action.UPDATED,
                changes=changes,
                actor=user,
            )
        # A liquid can carry its own cuenta (expected AND liquid incomes are
        # cuenta-eligible), so the draft follows its record here too.
        _sync_project_to_draft_cuentas(child, user)


def _sync_project_to_draft_cuentas(record, user):
    """Carry an income/hosting's project to its DRAFT cuentas de cobro.

    A draft inherits the project once, at creation; when the record's project
    is fixed later the draft keeps the stale value, and issue time reads
    ``document.project`` for both the frozen ``customer_project_name``
    snapshot and the numbering fallback (``resolve_client_user``) — a stale
    draft freezes a blank project line into the emitted PDF and can land in
    the wrong per-client series. Issued/paid/cancelled cuentas are facts and
    are never rewritten. One audit row per document, same as the cascades.
    """
    drafts = record.collection_documents.filter(
        commercial_status=Document.CommercialStatus.DRAFT,
    ).exclude(project_id=record.project_id)
    for document in drafts.select_for_update().order_by('pk'):
        old_values = snapshot_values(document, EntityType.COLLECTION_ACCOUNT)
        from accounts.services.billing_reassignment import validate_document_reassignment
        validate_document_reassignment(document, changes={'project': record.project}, lock=True)
        document.project = record.project
        document.save(update_fields=['project', 'updated_at'])
        log_entity_diff(
            EntityType.COLLECTION_ACCOUNT, document, old_values, user,
        )


@historical_write
@transaction.atomic
def bulk_assign_project(entity_type, record_ids, project, user):
    """Assign (or clear, with ``project=None``) the project of several
    records — the completion tool for rows created before their project
    existed, and the project mirror of :func:`bulk_assign_client`.

    One audit row per record; rows already pointing at the target are
    skipped so a re-run writes nothing. No hosting snapshot refresh — the
    project never touches the billing snapshot. Ownership (every record's
    client must own the project) is the caller's pre-check: the ids arrive
    validated and the service stays mechanical.
    """
    model = ENTITY_MODELS[entity_type]
    if entity_type in (EntityType.INCOME, EntityType.HOSTING):
        from accounts.services.billing_locks import lock_billing_rows
        from content.serializers.accounting import validate_project_client_match
        locked = lock_billing_rows(
            income_ids=record_ids if entity_type == EntityType.INCOME else [],
            hosting_ids=record_ids if entity_type == EntityType.HOSTING else [],
            project_ids=[project.pk if project else None],
            include_income_children=True, include_origin_documents=True,
        )
        project = locked.projects.get(project.pk) if project else None
        selected = locked.incomes if entity_type == EntityType.INCOME else locked.hostings
        records = [row for pk, row in selected.items() if pk in record_ids]
        for record in records:
            validate_project_client_match(project, record.client)
    else:
        records = list(model.objects.select_related('project').filter(pk__in=record_ids))
    target_id = project.pk if project else None
    updated = []
    for record in records:
        if record.project_id == target_id:
            continue
        old_values = snapshot_values(record, entity_type)
        from accounts.services.billing_reassignment import validate_financial_reassignment
        validate_financial_reassignment(record, {'project': project})
        record.project = project
        record.save(update_fields=['project', 'updated_at'])
        changes = compute_changes(
            entity_type, old_values, snapshot_values(record, entity_type),
        )
        if changes:
            log_accounting_change(
                entity_type=entity_type,
                object_id=record.pk,
                object_repr=object_repr(entity_type, record),
                action=Action.UPDATED,
                changes=changes,
                actor=user,
            )
        if (
            entity_type == EntityType.INCOME
            and record.kind == IncomeRecord.Kind.EXPECTED
        ):
            _cascade_project_to_liquid_children(record, user)
        _sync_project_to_draft_cuentas(record, user)
        updated.append(record)
    return updated


@transaction.atomic
def assign_project_to_documents(document_ids, project, user):
    """Documents flavour of :func:`bulk_assign_project` — cuentas included.

    Deliberately service-level: the generic document PATCH refuses non-draft
    cuentas (``collection_account_locked``), so an ISSUED cuenta with a
    missing project has no HTTP write path — this writer is how the
    assign-unlinked offer and the retroactive command fill it. It only moves
    the organisational FK: the frozen ``customer_project_name`` snapshot,
    the PDF, the client and the lifecycle are never touched (an issued
    document stays the fact it is). One audit row per document, entity-typed
    cuenta-vs-document the same way the folder cascade does.
    """
    from accounts.services.billing_locks import lock_billing_rows
    locked = lock_billing_rows(document_ids=document_ids, project_ids=[project.pk if project else None])
    project = locked.projects.get(project.pk) if project else None
    documents = list(
        Document.objects
        .annotate(
            thread_document_count=Count(
                'thread_item__thread__items', distinct=True,
            ),
        )
        .select_related(
            'project', 'client_user__profile', 'document_type',
            'thread_item__thread',
        )
        .filter(pk__in=document_ids),
    )
    target_id = project.pk if project else None
    updated = []
    for document in documents:
        current = locked.documents[document.pk]
        current.thread_document_count = document.thread_document_count
        document = current
        if document.project_id == target_id:
            continue
        entity_type = (
            EntityType.COLLECTION_ACCOUNT
            if getattr(document.document_type, 'code', None) == COLLECTION_ACCOUNT
            else EntityType.DOCUMENT
        )
        old_values = snapshot_values(document, entity_type)
        from accounts.services.billing_reassignment import validate_document_reassignment
        validate_document_reassignment(document, changes={'project': project}, lock=True)
        document.project = project
        document.save(update_fields=['project', 'updated_at'])
        if (
            entity_type == EntityType.COLLECTION_ACCOUNT
            and (
                document.issue_date
                or document.commercial_status == Document.CommercialStatus.CANCELLED
            )
        ):
            from content.services.generated_document_filing_service import (
                file_collection_account,
            )

            file_collection_account(document)
        elif document.is_generated_snapshot:
            from content.services.generated_document_filing_service import (
                file_proposal_snapshot,
            )

            file_proposal_snapshot(document)
        log_entity_diff(entity_type, document, old_values, user)
        updated.append(document)
    return updated


def _deletion_changes(entity_type, old_values):
    """Diff payload for a deletion: every non-empty field as old -> ''."""
    return [
        {'field': field, 'label': label, 'old': old_values[field], 'new': ''}
        for field, label in TRACKED_FIELDS[entity_type]
        if old_values[field] != ''
    ]


@historical_write
def delete_record(entity_type, instance, user):
    """Delete a record and its linked counterpart(s), audit and notify.

    A linked pocket movement and its income/expense are one money event:
    deleting either side hard-deletes the other (an orphan would silently
    diverge the pocket balance from the records). An abono movement spans
    several income children, so deleting it reverses the whole abono; the
    inverse direction — deleting one child of a shared movement — is
    rejected instead of cascading, because the movement's amount is the sum
    of its children and must not shrink over a partial delete.
    """
    if entity_type == EntityType.RECURRING and not instance.is_archived:
        raise ProposalActionError(
            'Un pago recurrente vigente no se puede eliminar definitivamente.',
            code='recurring_archive_required',
            hint='Archívalo primero para conservar una recuperación segura.',
        )

    deleted_id = instance.pk
    deleted_repr = object_repr(entity_type, instance)
    old_values = snapshot_values(instance, entity_type)
    changes = _deletion_changes(entity_type, old_values)
    movement_direction = (
        instance.direction if entity_type == EntityType.POCKET else None
    )

    linked_movement = None
    linked_records = []
    if entity_type in (EntityType.INCOME, EntityType.EXPENSE):
        linked_movement = instance.pocket_movement
        if (
            entity_type == EntityType.INCOME
            and linked_movement is not None
            and linked_movement.is_shared
        ):
            # One child of an abono cannot fall alone: the movement's amount
            # is the sum of its children, and shrinking the movement here
            # would rewrite a money event that DID happen. The abono
            # reverses as a unit, from the pocket side.
            raise ValueError(
                'Este ingreso hace parte de un abono que cubre varios '
                'ingresos. Para deshacerlo elimina el movimiento del '
                'bolsillo: se revertirá el abono completo.'
            )
    elif entity_type == EntityType.POCKET:
        # Capture before deleting: the record FKs are SET_NULL on delete.
        # An abono movement carries several income children — deleting the
        # movement undoes the whole abono, and each parent's payment state
        # reverts by derivation the moment its child rows disappear.
        linked_records = [
            (EntityType.INCOME, record)
            for record in instance.income_children
        ]
        expense = getattr(instance, 'expense_record', None)
        if expense is not None:
            linked_records.append((EntityType.EXPENSE, expense))

    affected_ids = {record.expected_income_id for _, record in linked_records
                    if isinstance(record, IncomeRecord) and record.expected_income_id}
    if entity_type == EntityType.INCOME and instance.expected_income_id:
        affected_ids.add(instance.expected_income_id)
    with transaction.atomic():
        from accounts.services.billing_locks import lock_billing_rows
        income_ids = affected_ids | {record.pk for kind, record in linked_records
                                     if kind == EntityType.INCOME}
        if entity_type == EntityType.INCOME:
            income_ids.add(instance.pk)
        locked = lock_billing_rows(income_ids=income_ids, include_income_children=True,
                                   include_origin_documents=True) if income_ids else None
        if entity_type == EntityType.POCKET:
            PocketMovement.objects.select_for_update().get(pk=instance.pk)
            discovered = sorted((record.pk, record.expected_income_id)
                                for kind, record in linked_records if kind == EntityType.INCOME)
            current = list(IncomeRecord.objects.filter(pocket_movement=instance)
                           .order_by('pk').values_list('pk', 'expected_income_id'))
            if discovered != current:
                from accounts.services.billing_access import BillingConflict
                raise BillingConflict()
        if linked_movement is not None:
            linked_movement = PocketMovement.objects.select_for_update().get(pk=linked_movement.pk)
            if entity_type == EntityType.INCOME and linked_movement.is_shared:
                raise ValueError('El reparto cambió. Elimina el movimiento para deshacer el abono completo.')
        instance.delete()
        if linked_movement is not None:
            _log_pocket_removal(linked_movement, user)
            linked_movement.delete()
        for linked_record_type, linked_record in linked_records:
            log_entity_removal(linked_record_type, linked_record, user)
            linked_record.delete()

        if locked:
            from content.services.accounting_settlement_service import _sync_linked_collection_accounts
            for income in locked.incomes.values():
                if income.kind == IncomeRecord.Kind.EXPECTED:
                    _sync_linked_collection_accounts(income, user)

    change_log = log_accounting_change(
        entity_type=entity_type,
        object_id=deleted_id,
        object_repr=deleted_repr,
        action=Action.DELETED,
        changes=changes,
        actor=user,
        movement_direction=movement_direction,
    )
    _notify(change_log)


# ── Income/Expense ↔ Pocket side effects ──

def _sync_pocket(entity_type, instance, user, *, register_in_pocket=None):
    if entity_type == EntityType.INCOME:
        _sync_movement(
            instance,
            wants_movement=(
                instance.kind == IncomeRecord.Kind.LIQUID
                and instance.destination == IncomeRecord.Destination.POCKET
            ),
            direction=PocketMovement.Direction.IN,
            source_ref=f'income:{instance.pk}',
            user=user,
        )
    elif entity_type == EntityType.EXPENSE:
        # The write serializer's `register_in_pocket` flag drives the
        # linkage (checked by default; unchecked covers paper adjustments
        # and personal expenses that never touched the company pocket).
        # A partial update without the flag preserves the current state,
        # so historical unlinked expenses never gain a movement silently.
        if register_in_pocket is None:
            wants_movement = instance.pocket_movement is not None
        else:
            wants_movement = register_in_pocket
        _sync_movement(
            instance,
            wants_movement=wants_movement,
            direction=PocketMovement.Direction.OUT,
            source_ref=f'expense:{instance.pk}',
            user=user,
        )


def _sync_movement(record, *, wants_movement, direction, source_ref, user):
    """Create/mirror/remove the linked pocket movement of a record.

    Linked movements are audited (the pocket ledger history stays complete)
    but do NOT send their own email — the income/expense email covers it.
    The concept and notes mirror the record verbatim (no prefix) so edits
    stay invertible from the pocket side.
    """
    movement = record.pocket_movement

    if movement is not None and movement.is_shared:
        # An abono movement mirrors no single child: letting the mirror run
        # would clobber its amount/concept with one child's values, and the
        # removal branch would delete the whole abono over one child's edit.
        # Defense in depth with _ensure_shared_child_update_allowed — a
        # future caller must not be able to desync movement.amount == Σ
        # children silently.
        if not wants_movement:
            raise ValueError(
                'Este ingreso hace parte de un abono; su destino y tipo no '
                'se pueden cambiar.'
            )
        return

    if wants_movement and movement is None:
        movement = PocketMovement.objects.create(
            concept=record.concept,
            movement_date=record.period_date,
            direction=direction,
            amount=record.total_amount,
            notes=record.notes,
            source_ref=source_ref,
            created_by=user if getattr(user, 'is_authenticated', False) else None,
        )
        record.pocket_movement = movement
        record.save(update_fields=['pocket_movement', 'updated_at'])
        log_accounting_change(
            entity_type=EntityType.POCKET,
            object_id=movement.pk,
            object_repr=movement.concept,
            action=Action.CREATED,
            changes=compute_changes(
                EntityType.POCKET, {},
                snapshot_values(movement, EntityType.POCKET),
            ),
            actor=user,
            movement_direction=movement.direction,
        )
    elif wants_movement and movement is not None:
        old_values = snapshot_values(movement, EntityType.POCKET)
        movement.concept = record.concept
        # The record only carries month granularity; a same-month period
        # keeps the exact day chosen on the pocket side.
        period = record.period_date
        if (movement.movement_date.year, movement.movement_date.month) != (
            period.year, period.month,
        ):
            movement.movement_date = period
        movement.amount = record.total_amount
        movement.notes = record.notes
        movement.save(update_fields=[
            'concept', 'movement_date', 'amount', 'notes', 'updated_at',
        ])
        changes = compute_changes(
            EntityType.POCKET, old_values,
            snapshot_values(movement, EntityType.POCKET),
        )
        if changes:
            log_accounting_change(
                entity_type=EntityType.POCKET,
                object_id=movement.pk,
                object_repr=movement.concept,
                action=Action.UPDATED,
                changes=changes,
                actor=user,
                movement_direction=movement.direction,
            )
    elif not wants_movement and movement is not None:
        _log_pocket_removal(movement, user)
        record.pocket_movement = None
        record.save(update_fields=['pocket_movement', 'updated_at'])
        movement.delete()


def _default_split(attribution, total):
    """Partner split applied to records mirrored from the pocket side."""
    if attribution == Ledger.GUSTAVO:
        return total, Decimal('0')
    if attribution == Ledger.CARLOS:
        return Decimal('0'), total
    return split_half(total)


def _sync_from_pocket(movement, mirror_ledger, user, *, is_create):
    """Create/mirror the income/expense record of a pocket movement.

    Counterpart of `_sync_movement`. Writes the record with plain ORM
    calls — never through create_record/update_record — so the two sync
    writers cannot re-enter each other. Setting `pocket_movement` at
    creation also keeps a later `_sync_movement` for that record in its
    idempotent mirror branch (no duplicate movements).
    Mirrored records are audited without their own email — the pocket
    email covers the user action.
    """
    linked = movement.linked_record

    if linked is None:
        if not is_create:
            # Historical movement created before the linkage existed.
            return
        # Pocket money is company money: mirrored records always live on
        # the company ledger so they count toward company utility. A
        # personal attribution means a partner draw — a company expense
        # fully assigned to that partner — never a personal-ledger record
        # (those would drain the pocket without touching the utility).
        attribution = mirror_ledger or Ledger.COMPANY
        gustavo, carlos = _default_split(attribution, movement.amount)
        common = {
            'concept': movement.concept,
            'period_date': movement.movement_date,
            'notes': movement.notes,
            'ledger': Ledger.COMPANY,
            'total_amount': movement.amount,
            'gustavo_amount': gustavo,
            'carlos_amount': carlos,
            'source_ref': f'pocket:{movement.pk}',
            'pocket_movement': movement,
            'created_by': (
                user if getattr(user, 'is_authenticated', False) else None
            ),
        }
        if movement.direction == PocketMovement.Direction.IN:
            record_type = EntityType.INCOME
            record = IncomeRecord.objects.create(
                kind=IncomeRecord.Kind.LIQUID,
                destination=IncomeRecord.Destination.POCKET,
                **common,
            )
        else:
            record_type = EntityType.EXPENSE
            record = ExpenseRecord.objects.create(
                category=(
                    ExpenseRecord.Category.BUSINESS
                    if attribution == Ledger.COMPANY
                    else ExpenseRecord.Category.PERSONAL
                ),
                **common,
            )
        log_accounting_change(
            entity_type=record_type,
            object_id=record.pk,
            object_repr=object_repr(record_type, record),
            action=Action.CREATED,
            changes=compute_changes(
                record_type, {}, snapshot_values(record, record_type),
            ),
            actor=user,
        )
        return

    record_type = (
        EntityType.INCOME
        if isinstance(linked, IncomeRecord)
        else EntityType.EXPENSE
    )
    old_values = snapshot_values(linked, record_type)
    linked.concept = movement.concept
    linked.notes = movement.notes
    update_fields = ['concept', 'notes', 'updated_at']
    if linked.period_date != movement.movement_date:
        linked.period_date = movement.movement_date
        update_fields.append('period_date')
    if record_type == EntityType.EXPENSE:
        current_attribution = linked.partner_attribution
    else:
        # Pocket IN mirrors are always company-ledger incomes; deriving an
        # attribution from a custom split would feed a personal value back
        # into the IN modal, which the serializer rejects.
        current_attribution = linked.ledger
    attribution = mirror_ledger or current_attribution
    if (
        movement.amount != linked.total_amount
        or attribution != current_attribution
        or linked.ledger != Ledger.COMPANY
    ):
        # The pocket modal has no split editor: amount/attribution edits
        # from the pocket side reset the split to the attribution default.
        # Custom splits are edited from the Ingresos/Gastos tabs. Legacy
        # personal-ledger mirrors are normalized to company on any edit.
        gustavo, carlos = _default_split(attribution, movement.amount)
        linked.ledger = Ledger.COMPANY
        linked.total_amount = movement.amount
        linked.gustavo_amount = gustavo
        linked.carlos_amount = carlos
        update_fields += [
            'ledger', 'total_amount', 'gustavo_amount', 'carlos_amount',
        ]
        if record_type == EntityType.EXPENSE:
            linked.category = (
                ExpenseRecord.Category.BUSINESS
                if attribution == Ledger.COMPANY
                else ExpenseRecord.Category.PERSONAL
            )
            update_fields.append('category')
    linked.save(update_fields=update_fields)
    changes = compute_changes(
        record_type, old_values, snapshot_values(linked, record_type),
    )
    if changes:
        log_accounting_change(
            entity_type=record_type,
            object_id=linked.pk,
            object_repr=object_repr(record_type, linked),
            action=Action.UPDATED,
            changes=changes,
            actor=user,
        )


def _log_pocket_removal(movement, user):
    old_values = snapshot_values(movement, EntityType.POCKET)
    log_accounting_change(
        entity_type=EntityType.POCKET,
        object_id=movement.pk,
        object_repr=movement.concept,
        action=Action.DELETED,
        changes=_deletion_changes(EntityType.POCKET, old_values),
        actor=user,
        movement_direction=movement.direction,
    )


def log_entity_removal(entity_type, record, user):
    """Silent DELETED audit row for a record deleted outside the pipeline.

    The deletion counterpart of ``log_entity_diff``: entities that never enter
    the generic create/update/delete pipeline (cuentas de cobro) still owe the
    trail a row saying they existed and who removed them. Call it BEFORE the
    delete — it reads the pk and the repr off the live instance.
    """
    old_values = snapshot_values(record, entity_type)
    log_accounting_change(
        entity_type=entity_type,
        object_id=record.pk,
        object_repr=object_repr(entity_type, record),
        action=Action.DELETED,
        changes=_deletion_changes(entity_type, old_values),
        actor=user,
    )


# ── Aggregations ──

def _sum(queryset, field):
    return queryset.aggregate(total=Sum(field))['total'] or Decimal('0')


_MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)
_ZERO_MONEY = Value(Decimal('0.00'), output_field=_MONEY_FIELD)


def collection_account_subqueries():
    """Annotations linking each income to its cuenta de cobro, if any.

    Same non-aggregate Subquery technique as paid_amount_subquery, for the
    same reason. Cancelled cuentas free their income (the create flow's
    duplicate guard uses the same exclude), so they never surface here.
    """
    base = (
        Document.objects.filter(
            income_record=OuterRef('pk'),
            document_type__code=COLLECTION_ACCOUNT,
        )
        .exclude(commercial_status=Document.CommercialStatus.CANCELLED)
        .order_by('-created_at')
    )
    return {
        'collection_account_id': Subquery(base.values('id')[:1]),
        'collection_account_number': Subquery(base.values('public_number')[:1]),
        'collection_account_status': Subquery(base.values('commercial_status')[:1]),
        'has_issued_collection_account': Exists(base.annotate(
            settlement_project_id=Coalesce('project_id', Value(0), output_field=BigIntegerField()),
        ).filter(
            commercial_status__in=('issued', 'paid'),
            client_user_id=OuterRef('client__user_id'),
            settlement_project_id=Coalesce(OuterRef('project_id'), Value(0), output_field=BigIntegerField()),
        )),
    }


def paid_amount_subquery():
    """Sum of the liquid income already fulfilling each expected record.

    A correlated scalar subquery rather than a Sum over the reverse FK on
    purpose: a join annotation is an aggregate, which pushes `.aggregate()`
    calls over the same queryset (`_income_meta`) onto Django's
    subquery-wrapping path and adds a GROUP BY that `.values()` callers
    can silently regroup. A Subquery is not an aggregate, so every existing
    query over an annotated queryset compiles exactly as it does today.

    The `kind=LIQUID` filter is load-bearing, not defensive: `limit_choices_to`
    constrains the FK's target, not its source, so a lost record may point at
    an expected parent and must never be counted as payment.

    Linked deductions count as credit too: the expected total stays gross,
    and the fee discounted at origin will never arrive as a liquid child.
    A second correlated subquery (same non-aggregate technique) keeps every
    `.aggregate()` caller compiling exactly as before.
    """
    liquid = (
        IncomeRecord.objects
        .filter(expected_income=OuterRef('pk'), kind=IncomeRecord.Kind.LIQUID)
        .values('expected_income')
        .annotate(total=Sum('total_amount'))
        .values('total')[:1]
    )
    deducted = (
        ExpenseRecord.objects
        .filter(source_income=OuterRef('pk'))
        .exclude(deduction_type='')
        .values('source_income')
        .annotate(total=Sum('total_amount'))
        .values('total')[:1]
    )
    return (
        Coalesce(
            Subquery(liquid, output_field=_MONEY_FIELD),
            _ZERO_MONEY,
            output_field=_MONEY_FIELD,
        )
        + Coalesce(
            Subquery(deducted, output_field=_MONEY_FIELD),
            _ZERO_MONEY,
            output_field=_MONEY_FIELD,
        )
    )


def receivable_queryset():
    """Open company projections available to the manual receivables board."""
    return (
        IncomeRecord.objects
        .filter(
            kind=IncomeRecord.Kind.EXPECTED,
            ledger=Ledger.COMPANY,
        )
        .annotate(
            paid_amount=paid_amount_subquery(),
            **collection_account_subqueries(),
        )
        .filter(total_amount__gt=F('paid_amount'))
        .select_related('client', 'client__user', 'project')
        .order_by('-is_receivable_candidate', '-period_date', '-created_at')
    )


def receivables_summary(queryset=None):
    """Manual forecast totals; the green original total feeds the KPI card."""
    queryset = queryset if queryset is not None else receivable_queryset()
    pending = Greatest(
        F('total_amount') - F('paid_amount'),
        _ZERO_MONEY,
        output_field=_MONEY_FIELD,
    )
    selected = Q(is_receivable_candidate=True)
    groups = {
        IncomeRecord.CollectionConfidence.HIGH: selected & Q(
            collection_confidence=IncomeRecord.CollectionConfidence.HIGH,
        ),
        IncomeRecord.CollectionConfidence.MEDIUM: selected & Q(
            collection_confidence=IncomeRecord.CollectionConfidence.MEDIUM,
        ),
        IncomeRecord.CollectionConfidence.LOW: selected & Q(
            collection_confidence=IncomeRecord.CollectionConfidence.LOW,
        ),
        'unclassified': selected & Q(collection_confidence=''),
    }
    aggregates = {
        'selected_count': Count('id', filter=selected),
        'selected_total': Sum('total_amount', filter=selected),
        'selected_paid': Sum('paid_amount', filter=selected),
        'selected_pending': Sum(pending, filter=selected),
    }
    for key, condition in groups.items():
        aggregates[f'{key}_count'] = Count('id', filter=condition)
        aggregates[f'{key}_total'] = Sum('total_amount', filter=condition)
        aggregates[f'{key}_paid'] = Sum('paid_amount', filter=condition)
        aggregates[f'{key}_pending'] = Sum(pending, filter=condition)
    totals = queryset.aggregate(**aggregates)

    def group_payload(key):
        return {
            'count': totals[f'{key}_count'] or 0,
            'total_amount': totals[f'{key}_total'] or Decimal('0'),
            'paid_amount': totals[f'{key}_paid'] or Decimal('0'),
            'pending_amount': totals[f'{key}_pending'] or Decimal('0'),
        }

    return {
        'high_total': totals['high_total'] or Decimal('0'),
        'high_count': totals['high_count'] or 0,
        'selected_count': totals['selected_count'] or 0,
        'selected_total': totals['selected_total'] or Decimal('0'),
        'paid_total': totals['selected_paid'] or Decimal('0'),
        'pending_total': totals['selected_pending'] or Decimal('0'),
        'by_confidence': {
            key: group_payload(key)
            for key in ('high', 'medium', 'low', 'unclassified')
        },
    }


def deselect_receivable_if_closed(income, user):
    """Remove a paid projection from the active forecast, retaining its colour."""
    if not income.is_receivable_candidate:
        return False
    still_open = (
        IncomeRecord.objects
        .filter(
            pk=income.pk,
            kind=IncomeRecord.Kind.EXPECTED,
            ledger=Ledger.COMPANY,
        )
        .annotate(paid_amount=paid_amount_subquery())
        .filter(total_amount__gt=F('paid_amount'))
        .exists()
    )
    if still_open:
        return False
    old_values = snapshot_values(income, EntityType.INCOME)
    income.is_receivable_candidate = False
    income.save(update_fields=['is_receivable_candidate', 'updated_at'])
    # Settlement already owns the operation's single email. Keep the field
    # change auditable without producing a second notification for one click.
    log_entity_diff(EntityType.INCOME, income, old_values, user)
    return True


def source_income_concept_subquery():
    """Concept of the income a deduction was discounted from.

    Annotated on expense lists so the origin renders without one query per
    deduction row (the serializer falls back to the relation elsewhere).
    """
    return Subquery(
        IncomeRecord.objects.filter(
            pk=OuterRef('source_income'),
        ).values('concept')[:1],
    )


def pocket_balance(as_of=None):
    """Current pocket balance: Sum(in) - Sum(out) up to `as_of`."""
    queryset = PocketMovement.objects.all()
    if as_of:
        queryset = queryset.filter(movement_date__lte=as_of)
    totals = queryset.aggregate(
        inflow=Sum('amount', filter=Q(direction=PocketMovement.Direction.IN)),
        outflow=Sum('amount', filter=Q(direction=PocketMovement.Direction.OUT)),
    )
    return (totals['inflow'] or Decimal('0')) - (totals['outflow'] or Decimal('0'))


def _split_sums(queryset):
    aggregate = queryset.aggregate(
        total=Sum('total_amount'),
        gustavo=Sum('gustavo_amount'),
        carlos=Sum('carlos_amount'),
    )
    total = aggregate['total'] or Decimal('0')
    gustavo = aggregate['gustavo'] or Decimal('0')
    carlos = aggregate['carlos'] or Decimal('0')
    return {
        'total': total,
        'gustavo': gustavo,
        'carlos': carlos,
        'company': total - gustavo - carlos,
    }


def _year_split_sums(year):
    """The company-ledger aggregates every year summary derives from.

    Personal-ledger records never count toward company totals.

    ``expenses`` counts only operational spending; income deductions (gateway
    and bank fees, withholdings) come apart in ``deductions``. The split
    drives an asymmetric utility rule: expected utility subtracts both (the
    gross projection minus its known fees), while liquid utility subtracts
    only operational spending — the liquid total is what physically arrived,
    already net of every fee, so subtracting deductions there would count
    the same loss twice.
    """
    company_expenses = ExpenseRecord.objects.filter(
        period_date__year=year, ledger=Ledger.COMPANY,
    )
    return {
        'expected': _split_sums(IncomeRecord.objects.filter(
            kind=IncomeRecord.Kind.EXPECTED, period_date__year=year,
            ledger=Ledger.COMPANY,
        )),
        'liquid': _split_sums(IncomeRecord.objects.filter(
            kind=IncomeRecord.Kind.LIQUID, period_date__year=year,
            ledger=Ledger.COMPANY,
        )),
        'expenses': _split_sums(company_expenses.operational()),
        'deductions': _split_sums(company_expenses.deductions()),
    }


def year_totals(year):
    """Public seam over the company-ledger year aggregates.

    Other services (e.g. the global panel dashboard) consume this instead
    of reaching into the private ``_year_split_sums`` helper.
    """
    sums = _year_split_sums(year)
    expected_total = sums['expected']['total']
    liquid_total = sums['liquid']['total']
    expenses_total = sums['expenses']['total']
    deductions_total = sums['deductions']['total']
    return {
        'expected_total': expected_total,
        'liquid_total': liquid_total,
        'expenses_total': expenses_total,
        'deductions_total': deductions_total,
        'expected_utility': expected_total - expenses_total - deductions_total,
        'liquid_utility': liquid_total - expenses_total,
    }


def _personal_sums(year):
    """Per-partner totals of their personal-ledger records."""
    result = {}
    for party in (Ledger.GUSTAVO, Ledger.CARLOS):
        result[str(party)] = {
            'expected': _sum(IncomeRecord.objects.filter(
                kind=IncomeRecord.Kind.EXPECTED, period_date__year=year,
                ledger=party,
            ), 'total_amount'),
            'liquid': _sum(IncomeRecord.objects.filter(
                kind=IncomeRecord.Kind.LIQUID, period_date__year=year,
                ledger=party,
            ), 'total_amount'),
            'expenses': _sum(ExpenseRecord.objects.filter(
                period_date__year=year, ledger=party,
            ).operational(), 'total_amount'),
        }
    return result


def _build_partner_totals(sums, personal):
    """Partner cards combine company participation + personal ledger.

    The `company` card is the company ledger itself (its full totals),
    not the per-row unassigned residue.
    """
    totals = {}
    for party in ('gustavo', 'carlos'):
        participation = {
            key: sums[key][party]
            for key in ('expected', 'liquid', 'expenses')
        }
        own = personal[party]
        totals[party] = {
            'expected': participation['expected'] + own['expected'],
            'liquid': participation['liquid'] + own['liquid'],
            'expenses': participation['expenses'] + own['expenses'],
            'net': (
                participation['liquid'] + own['liquid']
                - participation['expenses'] - own['expenses']
            ),
            'participation': participation,
            'personal': own,
        }
    totals['company'] = {
        'expected': sums['expected']['total'],
        'liquid': sums['liquid']['total'],
        'expenses': sums['expenses']['total'],
        'net': sums['liquid']['total'] - sums['expenses']['total'],
    }
    return totals


def partner_totals(year):
    """Expected/liquid income, expenses and net per partner + company."""
    return _build_partner_totals(_year_split_sums(year), _personal_sums(year))


def _totals_by_month(queryset, date_field, amount_field):
    rows = (
        queryset
        .order_by()  # clear Meta ordering so GROUP BY stays month-only
        .values_list(f'{date_field}__month')
        .annotate(total=Sum(amount_field))
    )
    return {month: (total or Decimal('0')) for month, total in rows}


def monthly_breakdown(year):
    """Twelve rows of expected/liquid/expenses/utility for the dashboard."""
    expected_by_month = _totals_by_month(
        IncomeRecord.objects.filter(
            kind=IncomeRecord.Kind.EXPECTED, period_date__year=year,
            ledger=Ledger.COMPANY,
        ),
        'period_date', 'total_amount',
    )
    liquid_by_month = _totals_by_month(
        IncomeRecord.objects.filter(
            kind=IncomeRecord.Kind.LIQUID, period_date__year=year,
            ledger=Ledger.COMPANY,
        ),
        'period_date', 'total_amount',
    )
    expenses_by_month = _totals_by_month(
        ExpenseRecord.objects.filter(
            period_date__year=year, ledger=Ledger.COMPANY,
        ).operational(),
        'period_date', 'total_amount',
    )
    deductions_by_month = _totals_by_month(
        ExpenseRecord.objects.filter(
            period_date__year=year, ledger=Ledger.COMPANY,
        ).deductions(),
        'period_date', 'total_amount',
    )

    breakdown = []
    for month in range(1, 13):
        month_date = date(year, month, 1)
        expected = expected_by_month.get(month, Decimal('0'))
        liquid = liquid_by_month.get(month, Decimal('0'))
        expenses = expenses_by_month.get(month, Decimal('0'))
        deductions = deductions_by_month.get(month, Decimal('0'))
        breakdown.append({
            'period': month_period(month_date),
            'label': month_label(month_date),
            'expected': expected,
            'liquid': liquid,
            'expenses': expenses,
            'deductions': deductions,
            # Asymmetric on purpose: expected is gross (minus known fees),
            # liquid already arrived net of them.
            'expected_utility': expected - expenses - deductions,
            'utility': liquid - expenses,
        })
    return breakdown


def recurring_monthly_cost(queryset=None):
    """Monthly COP cost of active, non-archived recurring payments."""
    if queryset is None:
        queryset = RecurringPayment.objects.filter(
            is_active=True, is_archived=False,
        )
    else:
        # Defense in depth for callers handing us an unscoped list/queryset:
        # the budget invariant belongs to the aggregation, not to one view.
        if hasattr(queryset, 'filter'):
            queryset = queryset.filter(is_active=True, is_archived=False)
        else:
            queryset = (
                payment for payment in queryset
                if payment.is_active and not payment.is_archived
            )
    return sum(
        (payment.monthly_cop_cost for payment in queryset),
        Decimal('0'),
    )


def latest_card_snapshots():
    """Newest snapshot per card name (single query, few rows per card)."""
    snapshots = []
    seen_cards = set()
    for snapshot in CardBalanceSnapshot.objects.order_by(
        'card_name', '-snapshot_date', '-created_at',
    ):
        if snapshot.card_name in seen_cards:
            continue
        seen_cards.add(snapshot.card_name)
        snapshots.append({
            'card_name': snapshot.card_name,
            'snapshot_date': snapshot.snapshot_date,
            'available_amount': snapshot.available_amount,
            'debt_amount': snapshot.debt_amount,
        })
    return snapshots


def expected_current_month():
    """Company income still pending to collect for the real current month.

    Nets out the liquid income already linked to each expected record: the
    card answers "what is left to come in", not "what was projected". The
    full projection stays in `expected_total` and `monthly_breakdown`, which
    is what makes the expected-vs-liquid comparison meaningful.

    Deliberately ignores the dashboard `year` selector: the card always
    reports the month we are actually living in, like `ads.current_month_total`.
    """
    today = today_bogota()
    month_date = date(today.year, today.month, 1)
    total = IncomeRecord.objects.filter(
        kind=IncomeRecord.Kind.EXPECTED,
        ledger=Ledger.COMPANY,
        period_date__year=today.year,
        period_date__month=today.month,
    ).aggregate(
        # Clamped per row: without this an overpaid record would cancel out
        # a genuinely pending sibling and understate the card.
        total=Sum(Greatest(
            F('total_amount') - paid_amount_subquery(), _ZERO_MONEY,
            output_field=_MONEY_FIELD,
        )),
    )['total'] or Decimal('0')
    return {
        'period': month_period(month_date),
        'label': month_label(month_date),
        'total': total,
    }


def card_debt_total():
    """Consolidated debt (latest snapshot per card) + catalog utilization.

    Debt sums every card that has a snapshot, matching the `Deuda total`
    chip on the cards tab. The cupo only comes from the active catalog, so
    a snapshot for a card missing from the catalog can push the percentage
    past 100 — that is real, not a rounding artifact.
    """
    snapshots = latest_card_snapshots()
    total = sum((snapshot['debt_amount'] for snapshot in snapshots), Decimal('0'))
    credit_limit_total = _sum(
        CreditCard.objects.filter(is_active=True), 'credit_limit',
    )
    utilization_pct = (
        round(float(total / credit_limit_total * 100), 1)
        if credit_limit_total > 0
        else None
    )
    return {
        'total': total,
        'card_count': len(snapshots),
        'credit_limit_total': credit_limit_total,
        'utilization_pct': utilization_pct,
    }


def dashboard_summary(year):
    """Single payload feeding the accounting dashboard."""
    sums = _year_split_sums(year)
    expected_total = sums['expected']['total']
    liquid_total = sums['liquid']['total']
    expenses_total = sums['expenses']['total']
    today = today_bogota()
    hostings = HostingRecord.objects.aggregate(
        active_count=Count('id', filter=Q(is_active=True)),
        monthly_income=Sum('monthly_value', filter=Q(is_active=True)),
        total_paid=Sum('total_paid'),
    )

    return {
        'year': year,
        'expected_total': expected_total,
        'liquid_total': liquid_total,
        'difference': liquid_total - expected_total,
        'expenses_total': expenses_total,
        'deductions_total': sums['deductions']['total'],
        'expected_utility': (
            expected_total - expenses_total - sums['deductions']['total']
        ),
        'liquid_utility': liquid_total - expenses_total,
        'pocket_balance': pocket_balance(),
        'partners': _build_partner_totals(sums, _personal_sums(year)),
        'monthly': monthly_breakdown(year),
        'recurring_monthly_cost': recurring_monthly_cost(),
        'ads': {
            'year_total': _sum(
                AdsSpendRecord.objects.filter(spend_date__year=year),
                'amount',
            ),
            'current_month_total': _sum(
                AdsSpendRecord.objects.filter(
                    spend_date__year=today.year,
                    spend_date__month=today.month,
                ),
                'amount',
            ),
        },
        'hostings': {
            'active_count': hostings['active_count'] or 0,
            'monthly_income': hostings['monthly_income'] or Decimal('0'),
            'total_paid': hostings['total_paid'] or Decimal('0'),
        },
        'latest_card_snapshots': latest_card_snapshots(),
        'expected_current_month': expected_current_month(),
        'receivables': receivables_summary(),
        'card_debt': card_debt_total(),
    }


def _describe(queryset):
    """count/total/avg/min/max of total_amount for a record set."""
    agg = queryset.aggregate(
        count=Count('id'),
        total=Sum('total_amount'),
        avg=Avg('total_amount'),
        min=Min('total_amount'),
        max=Max('total_amount'),
    )
    return {
        'count': agg['count'] or 0,
        'total': agg['total'] or Decimal('0'),
        'avg': agg['avg'] or Decimal('0'),
        'min': agg['min'] or Decimal('0'),
        'max': agg['max'] or Decimal('0'),
    }


def _top_concepts(queryset, limit=8):
    """Concepts ranked by summed amount (exact concept grouping)."""
    rows = (
        queryset.order_by()
        .values('concept')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-total')[:limit]
    )
    return [
        {'concept': row['concept'], 'total': row['total'], 'count': row['count']}
        for row in rows
    ]


def year_descriptive_stats(year):
    """Descriptive statistics feeding the income/expense analytics modals.

    Only aggregations the dashboard summary cannot answer live here (per
    record descriptives, concept rankings, category distribution); the
    monthly evolution series stay client-side on top of `monthly_breakdown`.
    Company ledger only, matching the dashboard's expected/liquid totals.
    """
    liquid = IncomeRecord.objects.filter(
        kind=IncomeRecord.Kind.LIQUID, ledger=Ledger.COMPANY,
        period_date__year=year,
    )
    expected = IncomeRecord.objects.filter(
        kind=IncomeRecord.Kind.EXPECTED, ledger=Ledger.COMPANY,
        period_date__year=year,
    )
    lost = IncomeRecord.objects.filter(
        kind=IncomeRecord.Kind.LOST, ledger=Ledger.COMPANY,
        period_date__year=year,
    )
    expenses = ExpenseRecord.objects.filter(
        ledger=Ledger.COMPANY, period_date__year=year,
    )
    category_labels = dict(ExpenseRecord.Category.choices)
    by_category = [
        {
            'category': row['category'],
            'label': category_labels.get(row['category'], row['category']),
            'total': row['total'],
            'count': row['count'],
        }
        for row in expenses.order_by()
        .values('category')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-total')
    ]
    return {
        'year': year,
        'income': {
            'liquid': _describe(liquid),
            'expected': _describe(expected),
            'lost_total': _sum(lost, 'total_amount'),
            'top_concepts': _top_concepts(liquid),
        },
        'expenses': {
            'summary': _describe(expenses),
            'by_category': by_category,
            'top_concepts': _top_concepts(expenses),
            'recurring_monthly_cost': recurring_monthly_cost(),
        },
    }


def ads_with_accumulated(queryset):
    """Records ordered chronologically with a running `accumulated` sum."""
    records = list(queryset.order_by('spend_date', 'created_at', 'id'))
    running = Decimal('0')
    for record in records:
        running += record.amount
        record.accumulated = running
    return records
