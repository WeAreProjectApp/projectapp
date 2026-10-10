"""Accounting rules (AC*).

AC1 and AC2 relink incomes and hostings through the accounting writers
(``bulk_assign_project``/``bulk_assign_client``), which carry liquid children
and draft collection accounts along and write one AccountingChangeLog row per
record. AC5 recalculates a hosting's totals from its cycles and logs the diff.

Undo needs the same ledger trail, but the writers refuse the inconsistent
state an undo brings back (a record pointing at another client's project), and
a recalculation cannot produce stale totals. So these reverts write the
recorded ``before`` values through the history-tracked queryset, the way the
engine's exact restore does, and log the diff with ``log_entity_diff``; AC2
tries its writers first. Each record's accounting timeline stays truthful.
"""
from collections import defaultdict
from copy import copy
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q, Sum
from rest_framework.exceptions import APIException

from content.services.data_integrity.catalog import register_fixer, rule
from content.services.data_integrity.fixes.base import Fixer, change, ref, required_choice, retained_blockers
from content.services.data_integrity.fixes.writers import (
    financial_closure, relink_financial_client, relink_financial_project,
)
from content.services.data_integrity.hashing import normalized
from content.services.data_integrity.scope import (
    DOCUMENT, HOSTING, INCOME, PROFILE, PROJECT, RECURRING, client_label,
)
from content.services.data_integrity.snapshots import model_for, snapshot_many
from content.services.data_integrity.types import (
    EXISTING_TOOL, RELINK, REPORT_ONLY, SYNC_COPY, Finding, RecordRef, blocker,
)

CENT = Decimal('0.01')
NO_PROJECT = 'none'
SIDE_LABEL = 'qué lado se corrige'
PROJECT_LABEL = 'el proyecto que queda en el registro'
SIDE_OPTIONS = [
    {'value': 'project', 'label': 'El proyecto: dejar el registro sin proyecto o pasarlo a otro proyecto de su cliente'},
    {'value': 'client', 'label': 'El cliente: pasar el registro al dueño del proyecto'},
]
RELINK_FIELDS = {
    INCOME: ('project_id', 'client_id'),
    HOSTING: ('project_id', 'client_id', 'client_name', 'client_email', 'client_contact_name',
              'client_identification'),
    DOCUMENT: ('project_id',),
}
STATUS_LABELS = {'issued': 'emitida', 'paid': 'pagada'}


# ── Shared helpers ───────────────────────────────────────────────────────────

def _money(value):
    return str(Decimal(value or 0).quantize(CENT))


def _financial_models():
    from content.models import HostingRecord, IncomeRecord
    return {INCOME: IncomeRecord, HOSTING: HostingRecord}


def _record_label(row):
    if row._meta.label_lower == INCOME:
        return row.concept
    return row.client_name or row.domain_url or f'Hosting {row.pk}'


def _document_label(document):
    return document.public_number or document.title


def _row_label(row):
    return _document_label(row) if row._meta.label_lower == DOCUMENT else _record_label(row)


def _client_name(profile):
    return client_label(profile) if profile is not None else 'Sin cliente'


def _project_name(project):
    return project.name if project is not None else 'Sin proyecto'


def _client_user(record):
    return record.client.user_id if record.client_id else None


def _client_profile(user_id):
    """The client profile of a user, or None when the user is not a client."""
    from accounts.models import UserProfile
    return (UserProfile._base_manager.select_related('user')
            .filter(user_id=user_id, role=UserProfile.ROLE_CLIENT).first())


def _people(user_ids):
    """{user_id: (client profile or None, label)} for project owners."""
    from django.contrib.auth import get_user_model

    from accounts.models import UserProfile
    found = {}
    for profile in UserProfile._base_manager.filter(user_id__in=user_ids).select_related('user'):
        found[profile.user_id] = (profile if profile.role == UserProfile.ROLE_CLIENT else None, client_label(profile))
    for user in get_user_model()._base_manager.filter(pk__in=set(user_ids) - set(found)):
        found[user.pk] = (None, user.get_full_name() or user.email or user.get_username())
    return found


def _project_options(user_id):
    from accounts.models import Project
    options = [{'value': NO_PROJECT, 'label': 'Ninguno: dejarlo sin proyecto'}]
    if user_id is not None:
        options += [{'value': pk, 'label': name} for pk, name in
                    Project._base_manager.filter(client_id=user_id).order_by('name', 'pk').values_list('pk', 'name')]
    return options


def _closure_rows(closure):
    """{(label, pk): row} for the incomes, hostings and documents of a closure."""
    related = {INCOME: ('client__user', 'project'), HOSTING: ('client__user', 'project'),
               DOCUMENT: ('project', 'document_type')}
    by_label = defaultdict(list)
    for label, pk in closure:
        by_label[label].append(pk)
    rows = {}
    for label, pks in by_label.items():
        for row in model_for(label)._base_manager.filter(pk__in=pks).select_related(*related.get(label, ())):
            rows[(label, row.pk)] = row
    return rows


def _carried(record, rows):
    """The record plus the liquid children the writers carry along with it."""
    from content.models import IncomeRecord
    carried = [record]
    if record._meta.label_lower == INCOME and record.kind == IncomeRecord.Kind.EXPECTED:
        carried += [row for (label, _), row in sorted(rows.items())
                    if label == INCOME and row.expected_income_id == record.pk]
    return carried


def _drafts_of(records, rows):
    """Draft collection accounts of these records: the writers move them with their project."""
    owners = {(row._meta.label_lower, row.pk) for row in records}
    return [row for (label, _), row in sorted(rows.items()) if label == DOCUMENT
            and ((INCOME, row.income_record_id) in owners or (HOSTING, row.hosting_record_id) in owners)]


def _first_text(detail):
    if isinstance(detail, dict):
        detail = list(detail.values())
    if isinstance(detail, (list, tuple)):
        return next((text for text in (_first_text(item) for item in detail) if text), '')
    return str(detail or '')


def _billing_guard(record, steps, drafts):
    """A ``billing_guard`` blocker when the writers would refuse these changes.

    ``steps`` are the field changes of each writer call, in order; draft
    collection accounts are checked whenever a step moves the project, as
    ``_sync_project_to_draft_cuentas`` does.
    """
    from accounts.services.billing_reassignment import (
        validate_document_reassignment, validate_financial_reassignment,
    )
    current = copy(record)
    try:
        with transaction.atomic():
            for changes in steps:
                validate_financial_reassignment(current, changes)
                for name, value in changes.items():
                    setattr(current, name, value)
                if 'project' in changes:
                    target_id = changes['project'].pk if changes['project'] else None
                    for document in drafts:
                        if document.project_id != target_id:
                            validate_document_reassignment(document, changes={'project': changes['project']})
    except (APIException, DjangoValidationError) as error:
        detail = getattr(error, 'detail', None) or getattr(error, 'messages', None)
        message = _first_text(detail) or 'La facturación asociada impide este cambio.'
        return [blocker('billing_guard', message, [ref(record, _record_label(record))])]
    return []


def _cascade_guards(records, changes, rows):
    """Validate every row a mechanical cascade changes, including its billing context."""
    found = []
    for row in records:
        if all(getattr(row, f'{field}_id') == (value.pk if value else None)
               for field, value in changes.items()):
            continue
        client = changes.get('client', row.client)
        project = changes.get('project', row.project)
        if project is not None and client is not None and project.client_id != client.user_id:
            found.append(blocker('child_client_mismatch', 'Un pago vinculado quedaría en el proyecto de otro '
                                 'cliente. Corrige primero el cliente y el proyecto de ese pago.',
                                 [ref(row, _record_label(row))]))
            continue
        drafts = _drafts_of([row], rows) if 'project' in changes else []
        found += _billing_guard(row, [changes], drafts)
    return found


def _entity_type(row):
    from content.models import AccountingChangeLog
    from content.services.document_type_codes import COLLECTION_ACCOUNT
    types = AccountingChangeLog.EntityType
    label = row._meta.label_lower
    if label == INCOME:
        return types.INCOME
    if label == HOSTING:
        return types.HOSTING
    code = row.document_type.code if row.document_type_id else None
    return types.COLLECTION_ACCOUNT if code == COLLECTION_ACCOUNT else types.DOCUMENT


def _restore_logged(step, actor):
    """Write back every recorded value that still differs from ``before`` and log it.

    Same writes as the engine's exact restore (history-tracked queryset), plus
    one AccountingChangeLog row per record, so the undo shows in the record's
    accounting timeline like the fix did.
    """
    from content.services.accounting_service import log_entity_diff, snapshot_values
    keys = sorted({(item['model'], item['pk']) for item in step['items']})
    current = snapshot_many(keys)
    pending = defaultdict(dict)
    for item in step['items']:
        row = current[(item['model'], item['pk'])]
        if not item['guard'] and row is not None and row.get(item['field']) != item['before']:
            pending[(item['model'], item['pk'])][item['field']] = item['before']
    for (label, pk), values in sorted(pending.items()):
        model = model_for(label)
        row = model._base_manager.get(pk=pk)
        entity_type = _entity_type(row)
        old_values = snapshot_values(row, entity_type)
        model.objects.filter(pk=pk).update(**values)
        log_entity_diff(entity_type, model._base_manager.get(pk=pk), old_values, actor)


class _RelinkUndoGuard:
    """Blocks an undo when a project or client it would restore no longer exists."""

    def guards_changed(self, step):
        from accounts.models import Project, UserProfile
        wanted = {'project_id': set(), 'client_id': set()}
        for item in step['items']:
            if not item['guard'] and item['field'] in wanted and item['before'] is not None:
                wanted[item['field']].add(item['before'])
        return (Project._base_manager.filter(pk__in=wanted['project_id']).count() != len(wanted['project_id'])
                or UserProfile._base_manager.filter(pk__in=wanted['client_id']).count() != len(wanted['client_id']))


# ── AC1 · income or hosting on another client's project ─────────────────────

def _foreign_project_finding(label, row, owner):
    profile, owner_label = owner
    name = _record_label(row)
    noun = 'El ingreso' if label == INCOME else 'El hosting'
    subjects = [RecordRef(label, row.pk, name), RecordRef(PROJECT, row.project_id, row.project.name)]
    if row.client_id:
        subjects.append(RecordRef(PROFILE, row.client_id, client_label(row.client)))
        message = (f'{noun} «{name}» es de {client_label(row.client)}, pero su proyecto «{row.project.name}» '
                   f'es de {owner_label}.')
        suggestion = {}
    else:
        message = f'{noun} «{name}» no tiene cliente y su proyecto «{row.project.name}» es de {owner_label}.'
        suggestion = {'side': 'client'} if profile else {'side': 'project', 'project': NO_PROJECT}
    return Finding(
        rule_id='AC1', subjects=tuple(subjects),
        evidence={'model': label, 'record': row.pk, 'client': row.client_id, 'project': row.project_id,
                  'project_owner': row.project.client_id},
        message=message,
        inputs={
            'side': {'label': SIDE_LABEL, 'options': SIDE_OPTIONS, 'required': True},
            'project': {'label': f'{PROJECT_LABEL} (si se corrige el proyecto)',
                        'options': _project_options(_client_user(row)), 'required': False},
        },
        suggestion=suggestion,
    )


@rule(id='AC1', domain='accounting', severity='high', fix_kinds=(RELINK,),
      title='Ingreso u hosting con el proyecto de otro cliente',
      description='El proyecto de un ingreso o de un hosting pertenece a un cliente distinto del suyo, así que '
                  'el dinero suma en dos clientes a la vez. Se corrige el proyecto (sin proyecto o uno del '
                  'cliente) o el cliente (el dueño del proyecto).')
def detect_foreign_project(scope):
    found = []
    for label, model in _financial_models().items():
        if scope.skips(label):
            continue
        rows = scope.limit(model._base_manager.filter(project__isnull=False, retention_context__isnull=True), label)
        mismatched = [pk for pk, client_user, owner in rows.values_list('pk', 'client__user_id', 'project__client_id')
                      if client_user != owner]
        found += [(label, row) for row in model._base_manager.filter(pk__in=mismatched)
                  .select_related('client__user', 'project').order_by('pk')]
    owners = _people({row.project.client_id for _, row in found})
    for label, row in found:
        yield _foreign_project_finding(label, row, owners[row.project.client_id])


class FinancialRelinkFixer(_RelinkUndoGuard, Fixer):
    kind = RELINK
    fields = RELINK_FIELDS

    def plan(self, finding, params, *, actor):
        from accounts.models import Project
        label, pk = finding.evidence['model'], finding.evidence['record']
        record = _financial_models()[label]._base_manager.select_related('client__user', 'project').get(pk=pk)
        closure = financial_closure(label, [pk])
        rows = _closure_rows(closure)
        side, missing = required_choice(params, 'side', SIDE_OPTIONS, SIDE_LABEL)
        blockers = retained_blockers(rows.values()) + missing
        context, changes, warnings = {'model': label, 'record': pk, 'side': side}, [], []
        if side == 'project':
            choice, missing = required_choice(params, 'project', _project_options(_client_user(record)),
                                              PROJECT_LABEL)
            blockers += missing
            if not missing:
                target = None if choice == NO_PROJECT else Project._base_manager.get(pk=choice)
                context['project'] = target.pk if target else None
                moved = _carried(record, rows)
                drafts = _drafts_of(moved, rows)
                changes = [change(row, 'project', _project_name(row.project), _project_name(target), _row_label(row))
                           for row in moved + drafts if row.project_id != context['project']]
                blockers += _cascade_guards(moved, {'project': target}, rows)
        elif side == 'client':
            owner = _client_profile(record.project.client_id)
            if owner is None:
                blockers.append(blocker('owner_not_client', 'El dueño del proyecto no tiene ficha de cliente: '
                                        'corrige el proyecto en su lugar.',
                                        [ref(record.project, record.project.name)]))
            else:
                context['client'] = owner.pk
                moved = _carried(record, rows)
                changes = [change(row, 'client', _client_name(row.client), client_label(owner), _row_label(row))
                           for row in moved if row.client_id != owner.pk]
                blockers += _cascade_guards(moved, {'client': owner}, rows)
                if label == HOSTING:
                    warnings.append('Los datos de facturación del hosting (nombre, correo, contacto e '
                                    'identificación) se reemplazan por los del nuevo cliente.')
        return self.new_plan(params, closure=closure, changes=changes, blockers=blockers, warnings=warnings,
                             context=context)

    def apply(self, plan, *, actor):
        from accounts.models import Project, UserProfile
        label, pk = plan.context['model'], plan.context['record']
        if plan.context['side'] == 'client':
            relink_financial_client(label, [pk], UserProfile._base_manager.get(pk=plan.context['client']), actor)
            return
        target = plan.context['project']
        relink_financial_project(label, [pk], Project._base_manager.get(pk=target) if target else None, actor)

    def revert(self, step, *, actor):
        # The writers refuse the foreign project an undo restores by definition.
        _restore_logged(step, actor)


register_fixer('AC1', FinancialRelinkFixer())


# ── AC2 · liquid income apart from its expected income ──────────────────────

def _copy_steps(child, parent):
    """Field changes of each writer call that copies the parent's client and project.

    ``bulk_assign_client`` clears a project the new client does not own; the
    project call then sets the parent's.
    """
    steps, project = [], child.project
    if child.client_id != parent.client_id:
        step = {'client': parent.client}
        if project is not None and (parent.client is None or project.client_id != parent.client.user_id):
            step['project'], project = None, None
        steps.append(step)
    if (project.pk if project else None) != parent.project_id:
        steps.append({'project': parent.project})
    return steps


@rule(id='AC2', domain='accounting', severity='medium', fix_kinds=(SYNC_COPY,),
      title='Pago con otro cliente o proyecto que su ingreso esperado',
      description='Un pago recibido no tiene el mismo cliente o proyecto que el ingreso esperado que salda, '
                  'así que un mismo negocio queda repartido entre dos clientes o proyectos. Se copian del '
                  'ingreso esperado.')
def detect_liquid_apart_from_parent(scope):
    from content.models import IncomeRecord
    if scope.skips(INCOME):
        return
    rows = IncomeRecord._base_manager.filter(
        kind=IncomeRecord.Kind.LIQUID, expected_income__isnull=False,
        retention_context__isnull=True, expected_income__retention_context__isnull=True,
    )
    ids = scope.ids_for(INCOME)
    if ids is not None:
        rows = rows.filter(Q(pk__in=ids) | Q(expected_income_id__in=ids))
    fields = ('pk', 'concept', 'client_id', 'project_id', 'expected_income_id', 'expected_income__concept',
              'expected_income__client_id', 'expected_income__project_id')
    for pk, concept, client, project, parent, parent_concept, parent_client, parent_project in (
            rows.order_by('pk').values_list(*fields)):
        if (client, project) == (parent_client, parent_project):
            continue
        what = ('el cliente ni el proyecto' if client != parent_client and project != parent_project
                else 'el cliente' if client != parent_client else 'el proyecto')
        yield Finding(
            rule_id='AC2',
            subjects=(RecordRef(INCOME, pk, concept), RecordRef(INCOME, parent, parent_concept)),
            evidence={'income': pk, 'parent': parent, 'client': client, 'project': project,
                      'parent_client': parent_client, 'parent_project': parent_project},
            message=f'El pago «{concept}» no tiene {what} del ingreso esperado «{parent_concept}» que salda.',
        )


class LiquidCopyFixer(_RelinkUndoGuard, Fixer):
    kind = SYNC_COPY
    fields = {INCOME: RELINK_FIELDS[INCOME], DOCUMENT: RELINK_FIELDS[DOCUMENT]}

    def plan(self, finding, params, *, actor):
        from content.models import IncomeRecord
        child = (IncomeRecord._base_manager
                 .select_related('client__user', 'project', 'expected_income__client__user', 'expected_income__project')
                 .get(pk=finding.evidence['income']))
        parent = child.expected_income
        closure = financial_closure(INCOME, [child.pk])
        rows = _closure_rows(closure)
        blockers = retained_blockers(rows.values())
        if parent.project_id and (parent.client_id is None or parent.project.client_id != parent.client.user_id):
            blockers.append(blocker('parent_inconsistent', 'El proyecto del ingreso esperado es de otro cliente: '
                                    'corrige primero ese ingreso.', [ref(parent, parent.concept)]))
        steps = _copy_steps(child, parent)
        drafts = _drafts_of([child], rows) if any('project' in step for step in steps) else []
        if not blockers:
            blockers += _billing_guard(child, steps, drafts)
        changes = []
        if child.client_id != parent.client_id:
            changes.append(change(child, 'client', _client_name(child.client), _client_name(parent.client),
                                  child.concept))
        if child.project_id != parent.project_id:
            changes.append(change(child, 'project', _project_name(child.project), _project_name(parent.project),
                                  child.concept))
        changes += [change(row, 'project', _project_name(row.project), _project_name(parent.project),
                           _document_label(row)) for row in drafts if row.project_id != parent.project_id]
        return self.new_plan(params, closure=closure, changes=changes, blockers=blockers,
                             context={'income': child.pk})

    def apply(self, plan, *, actor):
        from content.models import IncomeRecord
        child = IncomeRecord._base_manager.select_related('expected_income').get(pk=plan.context['income'])
        parent = child.expected_income
        if child.client_id != parent.client_id:
            relink_financial_client(INCOME, [child.pk], parent.client, actor)
            child.refresh_from_db()
        if child.project_id != parent.project_id:
            relink_financial_project(INCOME, [child.pk], parent.project, actor)

    def revert(self, step, *, actor):
        try:
            with transaction.atomic():
                self._revert_through_writers(step, actor)
        except (APIException, DjangoValidationError, ObjectDoesNotExist, ValueError):
            pass  # The writers refuse a pair they consider inconsistent; the logged restore takes over.
        _restore_logged(step, actor)

    def _revert_through_writers(self, step, actor):
        from accounts.models import Project, UserProfile
        from content.models import IncomeRecord
        pk = step['subjects'][0]['id']
        child = IncomeRecord._base_manager.get(pk=pk)
        before = {item['field']: item['before'] for item in step['items']
                  if (item['model'], item['pk']) == (INCOME, pk) and not item['guard']}
        client_id = before.get('client_id', child.client_id)
        project_id = before.get('project_id', child.project_id)
        if client_id != child.client_id:
            relink_financial_client(INCOME, [pk], UserProfile._base_manager.get(pk=client_id) if client_id else None, actor)
            child.refresh_from_db()
        if project_id != child.project_id:
            relink_financial_project(INCOME, [pk], Project._base_manager.get(pk=project_id) if project_id else None, actor)


register_fixer('AC2', LiquidCopyFixer())


# ── AC3 · repeated incomes ───────────────────────────────────────────────────

@rule(id='AC3', domain='accounting', severity='low', fix_kinds=(REPORT_ONLY,), group=True,
      title='Ingresos repetidos',
      description='Dos o más ingresos del mismo cliente tienen el mismo concepto y valor total: '
                  'probablemente se registró el mismo ingreso más de una vez. Se revisan y se corrigen a mano.')
def detect_repeated_incomes(scope):
    from accounts.models import UserProfile
    from content.models import IncomeRecord
    groups = defaultdict(list)
    rows = (IncomeRecord._base_manager.filter(client__isnull=False, retention_context__isnull=True).order_by('pk')
            .values_list('pk', 'client_id', 'concept', 'total_amount'))
    for pk, client_id, concept, total in rows:
        groups[(client_id, normalized(concept), _money(total))].append((pk, concept))
    repeated = {key: members for key, members in groups.items()
                if len(members) > 1 and scope.touches(INCOME, [pk for pk, _ in members])}
    clients = {profile.pk: profile for profile in UserProfile._base_manager.filter(
        pk__in={key[0] for key in repeated}).select_related('user')}
    for (client_id, concept_key, total), members in sorted(repeated.items()):
        yield Finding(
            rule_id='AC3',
            subjects=tuple(RecordRef(INCOME, pk, concept) for pk, concept in members),
            evidence={'client': client_id, 'concept': concept_key, 'total': total,
                      'incomes': [pk for pk, _ in members]},
            message=f'{len(members)} ingresos de {client_label(clients[client_id])} tienen el concepto '
                    f'«{members[0][1]}» y el valor {total}.',
        )


# ── AC4 · repeated recurring payments ────────────────────────────────────────

def _frequency_key(frequency, custom_months):
    return f'{frequency}:{custom_months}' if custom_months else frequency


@rule(id='AC4', domain='accounting', severity='low', fix_kinds=(REPORT_ONLY,), group=True, full_sweep_only=True,
      title='Pagos recurrentes repetidos',
      description='Dos o más pagos recurrentes sin archivar tienen el mismo nombre, moneda, precio y frecuencia: '
                  'probablemente es la misma suscripción registrada varias veces. Se revisan a mano y sólo '
                  'aparecen al revisar toda la base.')
def detect_repeated_recurring(scope):
    from content.models import RecurringPayment
    if not scope.is_all:
        return
    groups = defaultdict(list)
    rows = (RecurringPayment._base_manager.filter(is_archived=False).order_by('pk')
            .values_list('pk', 'name', 'currency', 'price', 'frequency', 'custom_months'))
    for pk, name, currency, price, frequency, custom_months in rows:
        groups[(normalized(name), currency, _money(price), _frequency_key(frequency, custom_months))].append((pk, name))
    for (key, currency, price, frequency), members in sorted(groups.items()):
        pks = [pk for pk, _ in members]
        if len(members) < 2 or not scope.touches(RECURRING, pks):
            continue
        yield Finding(
            rule_id='AC4',
            subjects=tuple(RecordRef(RECURRING, pk, name) for pk, name in members),
            evidence={'key': key, 'currency': currency, 'price': price, 'frequency': frequency, 'payments': pks},
            message=f'{len(members)} pagos recurrentes se llaman «{members[0][1]}» y cobran {price} {currency} '
                    'con la misma frecuencia.',
        )


# ── AC5 · hosting totals apart from their cycles ────────────────────────────

def _cycle_totals(cycles):
    """{hosting_id: (paid, cycles)} summed the way ``recalculate_hosting_totals`` sums them."""
    rows = (cycles.values('hosting_record_id').order_by()
            .annotate(paid=Sum('amount'), count=Sum('cycles_represented')))
    return {row['hosting_record_id']: (row['paid'] or Decimal('0'), row['count'] or 0) for row in rows}


@rule(id='AC5', domain='accounting', severity='medium', fix_kinds=(SYNC_COPY,),
      title='Totales del hosting que no cuadran con sus ciclos',
      description='El total pagado o la cantidad de ciclos de un hosting no coincide con la suma de sus ciclos '
                  'pagados. Se recalculan desde los ciclos y el cambio queda en el historial contable.')
def detect_hosting_totals(scope):
    from content.models import HostingCycle, HostingRecord
    if scope.skips(HOSTING):
        return
    cycles = HostingCycle._base_manager.filter(hosting_record__retention_context__isnull=True)
    ids = scope.ids_for(HOSTING)
    if ids is not None:
        cycles = cycles.filter(hosting_record_id__in=ids)
    totals = _cycle_totals(cycles)
    hostings = scope.limit(HostingRecord._base_manager.filter(retention_context__isnull=True), HOSTING)
    for hosting in hostings.order_by('pk'):
        paid, count = totals.get(hosting.pk, (Decimal('0'), 0))
        if hosting.total_paid == paid and hosting.cycles_count == count:
            continue
        name = _record_label(hosting)
        yield Finding(
            rule_id='AC5', subjects=(RecordRef(HOSTING, hosting.pk, name),),
            evidence={'hosting': hosting.pk, 'total_paid': _money(hosting.total_paid),
                      'cycles_count': hosting.cycles_count, 'cycles_paid': _money(paid), 'cycles': count},
            message=f'El hosting «{name}» registra {_money(hosting.total_paid)} pagados en {hosting.cycles_count} '
                    f'ciclos, pero sus ciclos suman {_money(paid)} en {count}.',
        )


class HostingTotalsFixer(Fixer):
    kind = SYNC_COPY
    fields = {HOSTING: ('total_paid', 'cycles_count')}

    @staticmethod
    def _cycles(hosting_id):
        from content.models import HostingCycle
        return [[pk, _money(amount), count] for pk, amount, count in HostingCycle._base_manager.filter(
            hosting_record_id=hosting_id).order_by('pk').values_list('pk', 'amount', 'cycles_represented')]

    def plan(self, finding, params, *, actor):
        from content.models import HostingCycle, HostingRecord
        hosting = HostingRecord._base_manager.get(pk=finding.evidence['hosting'])
        paid, count = _cycle_totals(HostingCycle._base_manager.filter(hosting_record_id=hosting.pk)).get(
            hosting.pk, (Decimal('0'), 0))
        name = _record_label(hosting)
        changes = []
        if hosting.total_paid != paid:
            changes.append(change(hosting, 'total_paid', _money(hosting.total_paid), _money(paid), name))
        if hosting.cycles_count != count:
            changes.append(change(hosting, 'cycles_count', hosting.cycles_count, count, name))
        return self.new_plan(params, closure=[(HOSTING, hosting.pk)], changes=changes,
                             blockers=retained_blockers([hosting]), context={'hosting': hosting.pk},
                             guards={'hosting': hosting.pk, 'cycles': self._cycles(hosting.pk)})

    def guards_changed(self, step):
        guards = step.get('guards', {})
        return bool(guards) and self._cycles(guards['hosting']) != guards['cycles']

    def apply(self, plan, *, actor):
        from content.models import AccountingChangeLog, HostingRecord
        from content.services.accounting_service import log_entity_diff, snapshot_values
        from content.services.hosting_cycle_service import recalculate_hosting_totals
        entity_type = AccountingChangeLog.EntityType.HOSTING
        hosting = HostingRecord._base_manager.get(pk=plan.context['hosting'])
        old_values = snapshot_values(hosting, entity_type)
        recalculate_hosting_totals(hosting)
        hosting.refresh_from_db()
        log_entity_diff(entity_type, hosting, old_values, actor)

    def revert(self, step, *, actor):
        # Recalculating can only reach today's sums; the stale totals go back as recorded.
        _restore_logged(step, actor)


register_fixer('AC5', HostingTotalsFixer())


# ── AC8 · issued collection account without billing context ─────────────────

@rule(id='AC8', domain='accounting', severity='medium', fix_kinds=(EXISTING_TOOL,),
      title='Cuenta de cobro emitida sin contexto de facturación',
      description='Una cuenta de cobro emitida o pagada no dice a qué contrato, otrosí u hosting '
                  'corresponde. Se asocia con la herramienta de contexto de facturación, eligiendo la naturaleza '
                  'y el contrato.')
def detect_cuenta_without_context(scope):
    from content.models import Document
    from content.services.document_type_codes import COLLECTION_ACCOUNT
    statuses = (Document.CommercialStatus.ISSUED, Document.CommercialStatus.PAID)
    rows = scope.limit(Document._base_manager.filter(
        document_type__code=COLLECTION_ACCOUNT, commercial_status__in=statuses,
        retention_context__isnull=True, billing_context__isnull=True,
    ), DOCUMENT)
    for document in rows.select_related('project').order_by('pk'):
        name = _document_label(document)
        subjects = [RecordRef(DOCUMENT, document.pk, name)]
        arguments = {'account_id': document.pk}
        location = ''
        prerequisite = ''
        if document.project_id:
            subjects.append(RecordRef(PROJECT, document.project_id, document.project.name))
            arguments['project_id'] = document.project_id
            location = f' del proyecto «{document.project.name}»'
        else:
            prerequisite = ' Vincúlala primero a un proyecto para poder asociar su contexto de facturación.'
        yield Finding(
            rule_id='AC8',
            subjects=tuple(subjects),
            evidence={'document': document.pk, 'project': document.project_id,
                      'status': document.commercial_status},
            message=f'La cuenta de cobro «{name}»{location} está '
                    f'{STATUS_LABELS[document.commercial_status]}, pero no dice a qué contrato, otrosí u hosting '
                    f'corresponde.{prerequisite}',
            tool={'connector': 'projects', 'name': 'associate_collection_account_context',
                  'arguments': arguments},
        )
