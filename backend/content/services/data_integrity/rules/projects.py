"""Project rules (PJ*).

PJ1 relinks loose records through the accounting writers; cuentas de cobro and
generated snapshots go to the assign-unlinked tool instead, because that writer
refiles them. PJ4 renames through the panel writer, whose Project signals
re-sync the managed root folder and thread, and PJ6 copies the legacy status
mirror. PJ2, PJ3 and PJ5 only report: leaving retention and provisioning roots
have their own audited tools and reviewed commands. PJ7 renumbers phases.
"""
from collections import defaultdict
from contextlib import contextmanager

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F, Q
from rest_framework.exceptions import APIException

from content.services.data_integrity.catalog import register_fixer, rule
from content.services.data_integrity.fixes import writers
from content.services.data_integrity.fixes.base import Fixer, change, ref, required_choice, retained_blockers
from content.services.data_integrity.hashing import clean_spaces, normalized
from content.services.data_integrity.scope import (
    DOCUMENT, FOLDER, HOSTING, INCOME, PHASE, PROFILE, PROJECT, THREAD, USER, client_label,
)
from content.services.data_integrity.snapshots import model_for
from content.services.data_integrity.types import (
    EXISTING_TOOL, RELINK, RENAME, REORDER, REPORT_ONLY, SYNC_COPY, Finding, RecordRef, blocker,
)

CONTEXT = 'content.projectretentioncontext'
ASSIGN_TOOL = 'assign_project_unlinked_records'
NO_PROJECT = 'Sin proyecto'


def _tool(name, arguments):
    return {'connector': 'projects', 'name': name, 'arguments': arguments}


def _active_projects(user_ids):
    """{client user id: [(pk, name)]}: projects whose state lets them receive records."""
    from accounts.models import Project
    from accounts.services.project_catalog_service import ACTIVE_PROJECT_EFFECTS
    found = defaultdict(list)
    rows = (Project._base_manager
            .filter(client_id__in=user_ids, current_state__operational_effect__in=ACTIVE_PROJECT_EFFECTS)
            .order_by('name', 'pk').values_list('client_id', 'pk', 'name'))
    for client_id, pk, name in rows:
        found[client_id].append((pk, name))
    return found


def _is_terminal(project):
    """The assign flow's refusal (``_project_is_terminal`` in panel_projects)."""
    from content.services.project_state_service import TERMINAL_EFFECTS
    state = project.current_state
    return bool(state and state.operational_effect in TERMINAL_EFFECTS)


def _owner_label(user):
    profile = getattr(user, 'profile', None)
    return client_label(profile) if profile is not None else (user.get_full_name() or user.email)


@contextmanager
def _writer_refusals():
    """A writer refusing the old state raises ValueError, so the engine's exact restore takes over."""
    try:
        yield
    except APIException as error:
        raise ValueError(str(error.detail)) from error


# ── PJ1 · records with a client and no project ───────────────────────────────

_RECORD_NOUNS = {INCOME: 'El ingreso', HOSTING: 'El hosting', DOCUMENT: 'El documento'}


def _record_text(row):
    label = row._meta.label_lower
    if label == INCOME:
        return row.concept
    if label == HOSTING:
        return row.domain_url or row.client_name
    return row.title


def _owned(queryset, scope, label, owner_field, owner_label):
    """Rows in the scope plus the scope owner's rows, as ``list_project_unlinked_records`` sees them."""
    if scope.is_all:
        return queryset
    return queryset.filter(Q(pk__in=scope.ids_for(label)) | Q(**{f'{owner_field}__in': scope.ids_for(owner_label)}))


def _unlinked_records(scope):
    """[(label, row, client user, owner label)] for every live record with a client and no project."""
    from content.models import Document, HostingRecord, IncomeRecord
    loose = {'project__isnull': True, 'retention_context__isnull': True}
    # A liquid child follows its expected income: relinking the parent cascades
    # to it, and a parent that already has a project is AC2's case. Reporting
    # both would put overlapping fixes in the same lot.
    incomes = (IncomeRecord._base_manager.filter(client__isnull=False, **loose)
               .exclude(Q(expected_income__client__isnull=False) | Q(expected_income__project__isnull=False)))
    hostings = HostingRecord._base_manager.filter(client__isnull=False, **loose)
    documents = Document._base_manager.filter(client_user__isnull=False, is_archived=False, **loose)
    found = []
    for label, queryset in ((INCOME, incomes), (HOSTING, hostings)):
        rows = _owned(queryset, scope, label, 'client_id', PROFILE).select_related('client__user').order_by('pk')
        found += [(label, row, row.client.user, client_label(row.client)) for row in rows]
    rows = (_owned(documents, scope, DOCUMENT, 'client_user_id', USER)
            .select_related('client_user__profile', 'document_type').order_by('pk'))
    found += [(DOCUMENT, row, row.client_user, _owner_label(row.client_user)) for row in rows]
    return found


def _refiled_on_assign(document):
    """Cuentas and generated snapshots: ``assign_project_to_documents`` refiles their folders."""
    from content.services.document_type_codes import COLLECTION_ACCOUNT
    return getattr(document.document_type, 'code', None) == COLLECTION_ACCOUNT or document.is_generated_snapshot


def _unlinked_finding(label, row, user, owner, targets):
    text = _record_text(row)
    if label == DOCUMENT and row.is_contract_mirror:
        return Finding(
            rule_id='PJ1', subjects=(RecordRef(label, row.pk, text),),
            evidence={'model': label, 'id': row.pk, 'client_user': user.pk},
            message=f'La plantilla contractual «{text}» de {owner} no tiene proyecto. Es de sólo lectura: '
                    'revisa su asociación desde Contratos.', fix_kinds=(REPORT_ONLY,),
        )
    options = [{'value': pk, 'label': name} for pk, name in targets]
    only = targets[0][0] if len(targets) == 1 else None
    message = f'{_RECORD_NOUNS[label]} «{text}» de {owner} no tiene proyecto.'
    tool = None
    if label == DOCUMENT and _refiled_on_assign(row):
        fix_kinds = (EXISTING_TOOL,)
        tool = _tool(ASSIGN_TOOL, {'project_id': only, 'document_ids': [row.pk]} if only else {'document_ids': [row.pk]})
        message += (' Es una cuenta de cobro o un documento generado: se vincula con «Asignar registros sin '
                    'proyecto» del proyecto, que además lo guarda en su carpeta.')
    else:
        fix_kinds = (RELINK,) if targets else (REPORT_ONLY,)
    if not targets:
        message += ' El cliente no tiene proyectos activos: crea o reactiva el que corresponda y vuelve a revisar.'
    elif only:
        message += f' Se propone «{targets[0][1]}», su único proyecto activo.'
    else:
        message += f' Elige a cuál de sus {len(targets)} proyectos activos pertenece.'
    return Finding(
        rule_id='PJ1',
        subjects=(RecordRef(label, row.pk, text),),
        evidence={'model': label, 'id': row.pk, 'client_user': user.pk},
        message=message, fix_kinds=fix_kinds, tool=tool,
        inputs={'project': {'label': 'el proyecto al que se vincula', 'options': options, 'required': True}}
        if options else {},
        suggestion={'project': only} if only else {},
    )


@rule(id='PJ1', domain='projects', severity='medium', fix_kinds=(RELINK, EXISTING_TOOL, REPORT_ONLY),
      title='Registros con cliente pero sin proyecto',
      description='Ingresos, hostings y documentos que tienen cliente pero no proyecto, así que no aparecen en el '
                  'proyecto al que pertenecen. Se vinculan a un proyecto activo del mismo cliente.')
def detect_unlinked_records(scope):
    records = _unlinked_records(scope)
    targets = _active_projects({user.pk for _, _, user, _ in records})
    for label, row, user, owner in records:
        yield _unlinked_finding(label, row, user, owner, targets.get(user.pk, []))


def _as_pk(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _relink_target(params, options, client_user_id):
    """(project, blockers): the chosen project, refused the way the assign flow refuses it."""
    from accounts.models import Project
    value = params.get('project')
    if value in (None, ''):
        return None, [blocker('input_required', 'Falta elegir el proyecto.')]
    project = Project._base_manager.select_related('current_state').filter(pk=_as_pk(value)).first()
    if project is None:
        return None, [blocker('invalid_input', 'El proyecto elegido no existe.')]
    if project.client_id != client_user_id:
        return None, [blocker('invalid_input', f'«{project.name}» es de otro cliente; elige un proyecto de este '
                              'cliente.')]
    if _is_terminal(project):
        return None, [blocker('terminal_project', f'«{project.name}» está cerrado y no recibe registros nuevos; '
                              'cámbialo a un estado operativo antes de vincular.')]
    if project.pk not in {option['value'] for option in options}:
        return None, [blocker('invalid_input', f'«{project.name}» no está activo; elige uno de los proyectos '
                              'activos del cliente.')]
    return project, []


def _closure_rows(closure):
    by_label = defaultdict(list)
    for label, pk in closure:
        by_label[label].append(pk)
    rows = []
    for label, pks in sorted(by_label.items()):
        queryset = model_for(label)._base_manager.filter(pk__in=pks).order_by('pk')
        if label != PROJECT:
            queryset = queryset.select_related('project')
        rows.extend(queryset)
    return rows


def _billing_blockers(project, rows):
    """The refusals the billing guards of the accounting writers would raise."""
    from accounts.services.billing_reassignment import validate_document_reassignment, validate_financial_reassignment
    found = []
    # Cascades are mechanical: validate their children too, before the writer
    # can move them to a foreign project or bypass their billing associations.
    with transaction.atomic():
        for row in rows:
            row_label = row._meta.label_lower
            if row_label in (INCOME, HOSTING):
                if row.client_id and row.client.user_id != project.client_id:
                    found.append(blocker('child_client_mismatch', 'Un pago vinculado tiene otro cliente: '
                                         'corrige primero ese pago.', [ref(row, _record_text(row))]))
                    continue
                validator = validate_financial_reassignment
            else:
                validator = validate_document_reassignment
            try:
                validator(row, changes={'project': project})
            except (APIException, DjangoValidationError):
                found.append(blocker('billing_guard', 'La facturación asociada impide mover este registro. '
                                     'Revisa sus cuentas de cobro o la conciliación de hosting antes de vincularlo.',
                                     [ref(row, _record_text(row))]))
    return found


class UnlinkedRecordFixer(Fixer):
    kind = RELINK
    fields = {INCOME: ('project_id',), HOSTING: ('project_id',), DOCUMENT: ('project_id',)}

    def plan(self, finding, params, *, actor):
        label, pk = finding.evidence['model'], finding.evidence['id']
        options = finding.inputs.get('project', {}).get('options', [])
        project, blockers = _relink_target(params, options, finding.evidence['client_user'])
        if project is None:
            return self.new_plan(params, blockers=blockers)
        # Incomes cascade to their liquid children and both to their draft cuentas.
        closure = [(DOCUMENT, pk)] if label == DOCUMENT else writers.financial_closure(label, [pk])
        rows = _closure_rows(closure)
        blockers = retained_blockers(rows)
        if label != DOCUMENT:
            blockers += _billing_blockers(project, rows)
        return self.new_plan(
            params, closure=closure, blockers=blockers,
            changes=[change(row, 'project', row.project.name if row.project_id else NO_PROJECT, project.name,
                            _record_text(row)) for row in rows if row.project_id != project.pk],
            context={'model': label, 'id': pk, 'project_id': project.pk},
        )

    def apply(self, plan, *, actor):
        from accounts.models import Project
        project = Project._base_manager.get(pk=plan.context['project_id'])
        if plan.context['model'] == DOCUMENT:
            writers.relink_documents_project([plan.context['id']], project, actor)
        else:
            writers.relink_financial_project(plan.context['model'], [plan.context['id']], project, actor)

    def revert(self, step, *, actor):
        subject = step['subjects'][0]
        with _writer_refusals():
            if subject['model'] == DOCUMENT:
                writers.relink_documents_project([subject['id']], None, actor)
            else:
                writers.relink_financial_project(subject['model'], [subject['id']], None, actor)


register_fixer('PJ1', UnlinkedRecordFixer())


# ── PJ2 · retained rows that point at a project again ────────────────────────

def _project_attnames(model):
    from accounts.models import Project
    return [(field.name, field.attname) for field in model._meta.concrete_fields
            if field.is_relation and field.remote_field.model is Project]


def _category_label(label):
    from content.services.project_deletion_catalog import CATEGORIES
    return CATEGORIES.get(label, {}).get('label', label)


@rule(id='PJ2', domain='projects', severity='high', fix_kinds=(REPORT_ONLY,),
      title='Registro conservado que volvió a tener proyecto',
      description='Un registro que quedó de sólo consulta al eliminar su proyecto vuelve a apuntar a un proyecto. '
                  'Se cambió por fuera del traslado auditado, así que se revisa a mano.')
def detect_retained_with_project(scope):
    from accounts.models import Project
    from content.models import ProjectRetentionContext
    from content.services.retention_audit import retained_models
    found = []
    for model in retained_models():
        fields = _project_attnames(model)
        if not fields:
            continue
        linked = Q()
        for name, _ in fields:
            linked |= Q(**{f'{name}__isnull': False})
        label = model._meta.label_lower
        rows = (model._base_manager.filter(retention_context__isnull=False).filter(linked).order_by('pk')
                .values_list('pk', 'retention_context_id', *(attname for _, attname in fields)))
        for pk, context_id, *values in rows:
            projects = {name: value for (name, _), value in zip(fields, values) if value is not None}
            if scope.is_all or pk in scope.ids_for(label) or scope.ids_for(PROJECT) & set(projects.values()):
                found.append((label, pk, context_id, projects))
    names = dict(Project._base_manager.filter(pk__in={pid for *_, projects in found for pid in projects.values()})
                 .values_list('pk', 'name'))
    contexts = dict(ProjectRetentionContext._base_manager.filter(pk__in={row[2] for row in found})
                    .values_list('pk', 'project_name'))
    for label, pk, context_id, projects in found:
        project_ids = sorted(set(projects.values()))
        targets = ', '.join(f'«{names.get(pid, pid)}»' for pid in project_ids)
        yield Finding(
            rule_id='PJ2',
            subjects=(RecordRef(label, pk, f'{_category_label(label)} #{pk}'),
                      *(RecordRef(PROJECT, pid, names.get(pid, '')) for pid in project_ids)),
            evidence={'model': label, 'id': pk, 'context': context_id, 'projects': projects},
            message=f'Un registro de «{_category_label(label)}» (#{pk}) quedó de sólo consulta al eliminar '
                    f'«{contexts.get(context_id, context_id)}», pero apunta otra vez a {targets}. Se cambió por '
                    'fuera del traslado auditado: revisa a mano cuál de los dos datos es el correcto.',
        )


# ── PJ3 · retained rows the client's live project can adopt ──────────────────

# (model label, tool argument, client relation): what ``adopt_for_assignment`` takes.
_ADOPTABLE = (
    (INCOME, 'income_ids', 'client__user'),
    (HOSTING, 'hosting_ids', 'client__user'),
    (DOCUMENT, 'document_ids', 'client_user'),
    (THREAD, 'thread_ids', 'client__user'),
)
_ADOPTABLE_NOUNS = {INCOME: ('ingreso', 'ingresos'), HOSTING: ('hosting', 'hostings'),
                    DOCUMENT: ('documento', 'documentos'), THREAD: ('conversación', 'conversaciones')}


def _adoptable_by_context():
    """{context id: {label: [ids]}}: retained rows the assign flow accepts for the context's client."""
    pending = defaultdict(dict)
    for label, _, owner in _ADOPTABLE:
        rows = model_for(label)._base_manager.filter(retention_context__isnull=False, project__isnull=True,
                                                     **{owner: F('retention_context__client')})
        if label == DOCUMENT:
            rows = rows.filter(is_archived=False)
        for pk, context_id in rows.order_by('pk').values_list('pk', 'retention_context_id'):
            pending[context_id].setdefault(label, []).append(pk)
    return pending


def _retained_folders(context_ids):
    from content.models import CommunicationFolder, DocumentFolder
    counts = defaultdict(int)
    for model in (DocumentFolder, CommunicationFolder):
        for context_id in model._base_manager.filter(retention_context_id__in=context_ids).values_list(
                'retention_context_id', flat=True):
            counts[context_id] += 1
    return counts


def _counted(records):
    return ', '.join(f'{len(ids)} {_ADOPTABLE_NOUNS[label][len(ids) != 1]}' for label, ids in records.items())


def _empty_retained_containers(pending_contexts):
    """Use the cleanup tool's own read-only preview for contexts with no rows left to adopt."""
    from content.services.retained_containers import KINDS, preview_discard
    candidates, linked = set(), set()
    labels = {kind: model._meta.label_lower for kind, model, _, _ in KINDS}
    for _, model, _, _ in KINDS:
        rows = model._base_manager.filter(retention_context__isnull=False).exclude(
            retention_context_id__in=pending_contexts)
        candidates.update(rows.values_list('retention_context_id', flat=True))
        linked.update(rows.filter(project__isnull=False).values_list('retention_context_id', flat=True))
    found = {}
    for context_id in sorted(candidates - linked):
        impact = preview_discard(context_id)
        if not impact['blockers']:
            records = defaultdict(list)
            for item in impact['containers']:
                records[labels[item['kind']]].append(item['id'])
            found[context_id] = {label: sorted(pks) for label, pks in records.items()}
    return found


@rule(id='PJ3', domain='projects', severity='low', fix_kinds=(EXISTING_TOOL,),
      title='Datos conservados que ya pueden pasar a un proyecto',
      description='Quedan datos de un proyecto eliminado y el cliente ya tiene un proyecto activo. Se trasladan '
                  'con «Asignar registros sin proyecto» o, si sólo quedan carpetas o conversaciones vacías, se '
                  'revisan con la herramienta de limpieza de datos conservados.')
def detect_adoptable_retained(scope):
    from content.models import ProjectRetentionContext
    pending = _adoptable_by_context()
    empty = _empty_retained_containers(pending)
    contexts = {context.pk: context for context in ProjectRetentionContext._base_manager.filter(
        pk__in=set(pending) | set(empty))}
    targets = _active_projects({context.client_id for context in contexts.values()})
    folders = _retained_folders(list(contexts))
    arguments = {label: argument for label, argument, _ in _ADOPTABLE}
    for context_id in sorted(contexts):
        context = contexts[context_id]
        pending_records = pending.get(context_id, {})
        records = {label: pending_records[label] for label, _, _ in _ADOPTABLE if label in pending_records}
        records = records or empty.get(context_id, {})
        for project_id, name in targets.get(context.client_id, []):
            if not (scope.touches(PROJECT, [project_id])
                    or any(scope.touches(label, ids) for label, ids in records.items())):
                continue
            if context_id in empty:
                yield Finding(
                    rule_id='PJ3',
                    subjects=(RecordRef(CONTEXT, context_id, context.project_name), RecordRef(PROJECT, project_id, name),
                              *(RecordRef(label, pk) for label, pks in sorted(records.items()) for pk in pks)),
                    evidence={'context': context_id, 'project': project_id, 'records': records},
                    message=f'De «{context.project_name}» sólo quedan carpetas o conversaciones vacías, y su '
                            f'cliente ya tiene «{name}» activo. Revisa su retirada con la herramienta de limpieza '
                            'de datos conservados, que tiene su propia vista previa.',
                    tool=_tool('delete_empty_retained_containers', {'context_id': context_id}),
                )
                continue
            message = (f'De «{context.project_name}», un proyecto eliminado, quedan {_counted(records)} de sólo '
                       f'consulta, y el cliente ya tiene «{name}» activo. Trasládalos con «Asignar registros sin '
                       f'proyecto» de «{name}».')
            if folders[context_id] == 1:
                message += ' Después, revisa y retira su carpeta conservada si queda vacía.'
            elif folders[context_id]:
                message += (f' Después, sus {folders[context_id]} carpetas conservadas que queden vacías se '
                            'retiran con la herramienta de limpieza de carpetas conservadas.')
            yield Finding(
                rule_id='PJ3',
                subjects=(RecordRef(CONTEXT, context_id, context.project_name), RecordRef(PROJECT, project_id, name)),
                evidence={'context': context_id, 'project': project_id, 'records': records},
                message=message,
                tool=_tool(ASSIGN_TOOL, {'project_id': project_id,
                                         **{arguments[label]: ids for label, ids in records.items()}}),
            )


# ── PJ4 · same-named projects of one client ──────────────────────────────────

def _user_labels(user_ids):
    from django.contrib.auth import get_user_model
    users = get_user_model()._base_manager.filter(pk__in=user_ids).select_related('profile')
    return {user.pk: _owner_label(user) for user in users}


@rule(id='PJ4', domain='projects', severity='medium', fix_kinds=(RENAME,), group=True,
      title='Proyectos del mismo cliente con el mismo nombre',
      description='Un cliente tiene dos o más proyectos que se llaman igual, así que es fácil confundirlos al '
                  'asignar documentos, cobros o conversaciones. Se renombra uno de ellos.')
def detect_duplicate_project_names(scope):
    from accounts.models import Project
    groups = defaultdict(list)
    for pk, client_id, name in Project._base_manager.order_by('pk').values_list('pk', 'client_id', 'name'):
        key = normalized(name)
        if key:
            groups[(client_id, key)].append((pk, name))
    duplicated = {group: members for group, members in groups.items()
                  if len(members) > 1 and scope.touches(PROJECT, [pk for pk, _ in members])}
    owners = _user_labels({client_id for client_id, _ in duplicated})
    for (client_id, key), members in sorted(duplicated.items()):
        options = [{'value': pk, 'label': f'{name} (#{pk})'} for pk, name in members]
        yield Finding(
            rule_id='PJ4',
            subjects=tuple(RecordRef(PROJECT, pk, name) for pk, name in members),
            evidence={'client': client_id, 'key': key, 'projects': [pk for pk, _ in members]},
            message=f'{len(members)} proyectos de {owners.get(client_id, client_id)} se llaman «{members[0][1]}». '
                    'Renombra uno para distinguirlos.',
            inputs={
                'project': {'label': 'el proyecto a renombrar', 'options': options, 'required': True},
                'name': {'label': 'el nombre nuevo', 'required': True},
            },
        )


def _name_blockers(name, evidence, project_id):
    from accounts.models import Project
    limit = Project._meta.get_field('name').max_length
    if not name:
        return [blocker('input_required', 'Falta escribir el nombre nuevo.')]
    if len(name) > limit:
        return [blocker('invalid_input', f'El nombre nuevo no puede pasar de {limit} caracteres.')]
    key = normalized(name)
    if key == evidence['key']:
        return [blocker('invalid_input', 'El nombre nuevo se sigue leyendo igual que el de los otros proyectos; '
                        'elige uno distinto.')]
    others = Project._base_manager.filter(client_id=evidence['client']).exclude(pk=project_id)
    if any(normalized(other) == key for other in others.values_list('name', flat=True)):
        return [blocker('invalid_input', 'Otro proyecto de este cliente ya se llama así; elige un nombre distinto.')]
    return []


def _drifted_descendants(project):
    """Folders the root sync re-points to the project's client: only rows that drifted."""
    from content.models import DocumentFolder
    root = DocumentFolder._base_manager.filter(managed_project_id=project.pk).first()
    if root is None:
        return []
    rows = (DocumentFolder._base_manager.filter(pk__in=root.get_descendant_ids(), project_id=project.pk)
            .exclude(client_user_id=project.client_id).values_list('pk', flat=True))
    return [(FOLDER, pk) for pk in rows]


class DuplicateProjectNameFixer(Fixer):
    kind = RENAME
    # The rename's signals re-sync the managed root folder and thread.
    fields = {
        PROJECT: ('name',),
        FOLDER: ('name', 'client_user_id', 'parent_id', 'project_id', 'is_archived', 'archived_at',
                 'archived_via_folder_id', 'slug'),
        THREAD: ('title', 'project_id', 'client_id', 'is_archived', 'archived_at'),
    }

    def plan(self, finding, params, *, actor):
        from accounts.models import Project
        project_id, blockers = required_choice(params, 'project', finding.inputs['project']['options'],
                                               'el proyecto a renombrar')
        raw = params.get('name')
        name = clean_spaces(raw) if isinstance(raw, str) else ''
        blockers += _name_blockers(name, finding.evidence, project_id)
        if project_id is None:
            return self.new_plan(params, blockers=blockers)
        project = Project._base_manager.get(pk=project_id)
        roots = writers.project_root_closure(project.pk)
        descendants = _drifted_descendants(project)
        closure = [(PROJECT, project.pk), *roots, *descendants]
        blockers += retained_blockers(_closure_rows(closure))
        changes = [change(project, 'name', project.name, name, project.name)]
        for label, pk in roots:
            row = model_for(label)._base_manager.get(pk=pk)
            field = 'name' if label == FOLDER else 'title'
            changes.append(change(row, field, getattr(row, field), name))
        return self.new_plan(
            params, closure=closure,
            changes=changes, blockers=blockers, context={'project_id': project.pk, 'name': name},
        )

    def apply(self, plan, *, actor):
        writers.rename_project(plan.context['project_id'], plan.context['name'], actor)

    def revert(self, step, *, actor):
        for item in step['items']:
            if item['model'] == PROJECT and item['field'] == 'name':
                with _writer_refusals():
                    writers.rename_project(item['pk'], item['before'], actor)


register_fixer('PJ4', DuplicateProjectNameFixer())


# ── PJ5 · projects without their managed roots ───────────────────────────────

_ROOTS = (
    ('folder', 'carpeta principal de documentos', 'reconcile_project_folders'),
    ('thread', 'conversación principal', 'backfill_communication_root_threads'),
)


@rule(id='PJ5', domain='projects', severity='high', fix_kinds=(REPORT_ONLY,),
      title='Proyecto sin carpeta o sin conversación principal',
      description='Todo proyecto tiene una carpeta principal de documentos y una conversación principal que el '
                  'sistema mantiene. Si falta alguna, se crea en producción con los comandos de reconciliación.')
def detect_missing_project_roots(scope):
    from accounts.models import Project
    rows = (scope.limit(Project._base_manager.all(), PROJECT).order_by('pk')
            .values_list('pk', 'name', 'document_root_folder__id', 'communication_root_thread__id'))
    for pk, name, folder_id, thread_id in rows:
        present = {'folder': folder_id, 'thread': thread_id}
        missing = [(kind, label, command) for kind, label, command in _ROOTS if present[kind] is None]
        if not missing:
            continue
        yield Finding(
            rule_id='PJ5',
            subjects=(RecordRef(PROJECT, pk, name),),
            evidence={'project': pk, 'missing': [kind for kind, _, _ in missing]},
            message=f'«{name}» no tiene {" ni ".join(label for _, label, _ in missing)}. Se corrige en producción '
                    'con los comandos que reconstruyen las carpetas y conversaciones principales.',
        )


# ── PJ6 · legacy status mirror ───────────────────────────────────────────────

@rule(id='PJ6', domain='projects', severity='low', fix_kinds=(SYNC_COPY,),
      title='Estado heredado desactualizado',
      description='Cada proyecto guarda una copia de su estado en el formato anterior, que algunas pantallas todavía '
                  'leen. Si no coincide con el estado actual, se copia el valor que corresponde.')
def detect_legacy_status_drift(scope):
    from accounts.models import Project
    from content.services.project_state_service import LEGACY_STATUS_BY_EFFECT
    labels = dict(Project.STATUS_CHOICES)
    rows = (scope.limit(Project._base_manager.filter(current_state__isnull=False), PROJECT).order_by('pk')
            .values_list('pk', 'name', 'status', 'current_state_id', 'current_state__name',
                         'current_state__operational_effect'))
    for pk, name, status, state_id, state_name, effect in rows:
        expected = LEGACY_STATUS_BY_EFFECT.get(effect)
        if expected is None or status == expected:
            continue
        yield Finding(
            rule_id='PJ6',
            subjects=(RecordRef(PROJECT, pk, name),),
            evidence={'project': pk, 'state': state_id, 'effect': effect, 'status': status},
            message=f'«{name}» está en «{state_name}», pero su estado heredado dice «{labels.get(status, status)}»; '
                    f'debería decir «{labels[expected]}».',
        )


class LegacyStatusFixer(Fixer):
    kind = SYNC_COPY
    fields = {PROJECT: ('status',)}

    def plan(self, finding, params, *, actor):
        from accounts.models import Project
        from content.services.project_state_service import LEGACY_STATUS_BY_EFFECT
        project = Project._base_manager.select_related('current_state').get(pk=finding.evidence['project'])
        expected = LEGACY_STATUS_BY_EFFECT[project.current_state.operational_effect]
        labels = dict(Project.STATUS_CHOICES)
        return self.new_plan(
            params, closure=[(PROJECT, project.pk)],
            changes=[change(project, 'status', labels.get(project.status, 'Estado sin reconocer'),
                            labels[expected], project.name)],
            context={'project_id': project.pk, 'status': expected},
        )

    def apply(self, plan, *, actor):
        from accounts.models import Project
        # No writer owns the mirror alone: state transitions rewrite it with the
        # state. The history queryset update keeps the revision and deliberately
        # skips Project.save signals, which would re-sync the managed root folder
        # and thread over a field they never read.
        Project.objects.filter(pk=plan.context['project_id']).update(status=plan.context['status'])


register_fixer('PJ6', LegacyStatusFixer())


# ── PJ7 · commercial phase order ─────────────────────────────────────────────

def _live_phases(project_ids=None):
    from accounts.models import ProjectPhase
    rows = ProjectPhase._base_manager.filter(project__isnull=False, retention_context__isnull=True)
    if project_ids is not None:
        rows = rows.filter(project_id__in=project_ids)
    return rows.order_by('project_id', 'order', 'pk')


@rule(id='PJ7', domain='projects', severity='low', fix_kinds=(REORDER,),
      title='Fases con orden repetido o con huecos',
      description='Las fases comerciales de un proyecto deben ir numeradas 1, 2, 3… sin repetir ni saltar '
                  'posiciones. Se renumeran conservando el orden en que se ven hoy.')
def detect_phase_order(scope):
    from accounts.models import Project
    by_project = defaultdict(list)
    for phase_id, project_id, order in _live_phases(scope.ids_for(PROJECT)).values_list('pk', 'project_id', 'order'):
        by_project[project_id].append((phase_id, order))
    broken = {pk: rows for pk, rows in by_project.items()
              if [order for _, order in rows] != list(range(1, len(rows) + 1))}
    names = dict(Project._base_manager.filter(pk__in=broken).values_list('pk', 'name'))
    for project_id, rows in sorted(broken.items()):
        yield Finding(
            rule_id='PJ7',
            subjects=(RecordRef(PROJECT, project_id, names.get(project_id, '')),
                      *(RecordRef(PHASE, phase_id) for phase_id, _ in rows)),
            evidence={'project': project_id, 'orders': [[phase_id, order] for phase_id, order in rows]},
            message=f'Las fases de «{names.get(project_id, project_id)}» tienen el orden '
                    f'{", ".join(str(order) for _, order in rows)}; deberían ir del 1 al {len(rows)}.',
            suggestion={'orders': {str(phase_id): index for index, (phase_id, _) in enumerate(rows, start=1)}},
        )


class PhaseOrderFixer(Fixer):
    kind = REORDER
    fields = {PHASE: ('order',)}

    def plan(self, finding, params, *, actor):
        from accounts.models import Project, ProjectPhase
        project_id = finding.evidence['project']
        project = Project._base_manager.get(pk=project_id)
        phases = list(ProjectPhase._base_manager.filter(project_id=project_id)
                      .order_by('order', 'pk'))
        target = {phase.pk: index for index, phase in enumerate(phases, start=1)}
        blockers = retained_blockers(phases)
        return self.new_plan(
            params, closure=[(PHASE, phase.pk) for phase in phases], blockers=blockers,
            changes=[change(phase, 'order', phase.order, target[phase.pk], f'Fase {phase.pk}')
                     for phase in phases if phase.order != target[phase.pk]],
            guards={'project': project.pk,
                    'phases': sorted([[phase.pk, phase.business_proposal_id] for phase in phases])},
            context={'project': project, 'items': [{'id': pk, 'order': order} for pk, order in target.items()]},
        )

    def apply(self, plan, *, actor):
        from accounts.services.project_phases import reorder_phases
        reorder_phases(plan.context['project'], plan.context['items'])

    def guards_changed(self, step):
        from accounts.models import ProjectPhase
        guards = step.get('guards', {})
        if 'project' not in guards:
            return False
        phases = ProjectPhase._base_manager.filter(project_id=guards['project']).order_by('pk')
        current = [list(row) for row in phases.values_list('pk', 'business_proposal_id')]
        return current != guards['phases']

    def revert(self, step, *, actor):
        from accounts.models import Project
        from accounts.services.project_phases import reorder_phases
        project = Project._base_manager.get(pk=step['subjects'][0]['id'])
        orders = {item['pk']: item['before'] for item in step['items'] if item['field'] == 'order'}
        current = dict(project.phases.values_list('pk', 'order'))
        reorder_phases(project, [{'id': pk, 'order': orders.get(pk, order)} for pk, order in current.items()])


register_fixer('PJ7', PhaseOrderFixer())


def project_ref(project):
    return ref(project, project.name)
