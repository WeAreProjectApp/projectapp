"""Naming rules (NM*).

NM1 reports a name or title that differs from ``clean_spaces(value)``: leading,
trailing or repeated whitespace, tabs and line breaks included. There is one
finding per (model, pk, field) and no operator input: the fix saves the clean
value through the writer the Panel uses. The plan runs that writer's
validation first, so a refusal shows up as a blocker instead of a failed apply.

Values the system owns are left out: managed project/client roots (named after
what they represent), system folders, generated snapshots, collection
accounts, contract mirrors and retained rows.
"""
import copy

from django.core.exceptions import ValidationError as DjangoValidationError

from content.services.data_integrity.catalog import register_fixer, rule
from content.services.data_integrity.fixes import writers
from content.services.data_integrity.fixes.base import Fixer, change, retained_blockers
from content.services.data_integrity.hashing import clean_spaces
from content.services.data_integrity.scope import (
    COMM_FOLDER, DOCUMENT, FOLDER, PROFILE, PROJECT, PROPOSAL, THREAD, USER, client_label,
)
from content.services.data_integrity.types import RENAME, Finding, RecordRef, blocker

DIAGNOSTIC = 'content.webappdiagnostic'

# How each covered value reads in a sentence.
WHAT = {
    (PROFILE, 'company_name'): 'la empresa del cliente',
    (USER, 'first_name'): 'el nombre del cliente',
    (USER, 'last_name'): 'el apellido del cliente',
    (PROJECT, 'name'): 'el nombre del proyecto',
    (FOLDER, 'name'): 'el nombre de la carpeta',
    (DOCUMENT, 'title'): 'el título del documento',
    (PROPOSAL, 'title'): 'el título de la propuesta',
    (COMM_FOLDER, 'name'): 'el nombre de la carpeta de comunicaciones',
    (THREAD, 'title'): 'el título de la comunicación',
}


def has_extra_spaces(value):
    return bool(value) and value != clean_spaces(value)


# ── NM1 · detection ──────────────────────────────────────────────────────────

def _finding(subject, model, pk, field, value):
    clean = clean_spaces(value)
    what = WHAT[(model, field)]
    shown = f'{what[0].upper()}{what[1:]} «{value}»'
    return Finding(
        rule_id='NM1', subjects=(subject,),
        evidence={'model': model, 'pk': pk, 'field': field, 'value': value},
        message=(f'{shown} tiene espacios de más; quedaría «{clean}».' if clean
                 else f'{shown} sólo tiene espacios; se dejaría vacío si el panel lo permite.'),
        suggestion={'value': clean} if clean else {},
    )


def _client(**lookup):
    from accounts.models import UserProfile
    return UserProfile._base_manager.select_related('user').get(**lookup)


def _client_ref(profile_id):
    profile = _client(pk=profile_id)
    return RecordRef(PROFILE, profile.pk, client_label(profile))


def _client_findings(scope):
    """The company lives on the profile, first and last name on its user."""
    from accounts.models import UserProfile
    clients = UserProfile._base_manager.filter(role=UserProfile.ROLE_CLIENT).order_by('pk')
    for pk, company in scope.limit(clients, PROFILE).values_list('pk', 'company_name'):
        if has_extra_spaces(company):
            yield _finding(_client_ref(pk), PROFILE, pk, 'company_name', company)
    names = scope.limit(clients, USER, 'user_id').values_list('pk', 'user_id', 'user__first_name', 'user__last_name')
    for pk, user_id, first_name, last_name in names:
        for field, value in (('first_name', first_name), ('last_name', last_name)):
            if has_extra_spaces(value):
                yield _finding(_client_ref(pk), USER, user_id, field, value)


def _projects():
    from accounts.models import Project
    return Project._base_manager.all()


def _manual_folders():
    from content.models import DocumentFolder
    return DocumentFolder._base_manager.filter(
        managed_project__isnull=True, managed_client__isnull=True, system_key__isnull=True,
        retention_context__isnull=True)


def _plain_documents():
    from content.models import Document
    from content.services.contract_mirror_service import mirror_documents
    from content.services.document_type_codes import COLLECTION_ACCOUNT
    mirrors = mirror_documents(Document._base_manager.all()).values('pk')
    return (Document._base_manager.filter(retention_context__isnull=True, generated_file='')
            .exclude(document_type__code=COLLECTION_ACCOUNT).exclude(pk__in=mirrors))


def _proposals():
    from content.models import BusinessProposal
    return BusinessProposal._base_manager.all()


def _communication_folders():
    from content.models import CommunicationFolder
    return CommunicationFolder._base_manager.filter(retention_context__isnull=True)


def _manual_threads():
    from content.models import CommunicationThread
    return CommunicationThread._base_manager.filter(
        managed_project__isnull=True, managed_client__isnull=True, retention_context__isnull=True)


PLAIN = (
    (PROJECT, 'name', _projects), (FOLDER, 'name', _manual_folders), (DOCUMENT, 'title', _plain_documents),
    (PROPOSAL, 'title', _proposals), (COMM_FOLDER, 'name', _communication_folders), (THREAD, 'title', _manual_threads),
)


@rule(id='NM1', domain='naming', severity='low', fix_kinds=(RENAME,),
      title='Nombres con espacios de más',
      description='El nombre o el título de un cliente, proyecto, carpeta, documento, propuesta o comunicación tiene '
                  'espacios al inicio, al final o repetidos (también tabulaciones o saltos de línea). Se '
                  'guarda el mismo texto sin esos espacios, con las mismas validaciones del panel.')
def detect_extra_spaces(scope):
    yield from _client_findings(scope)
    for model_label, field, rows in PLAIN:
        for pk, value in scope.limit(rows(), model_label).order_by('pk').values_list('pk', field):
            if has_extra_spaces(value):
                subject = RecordRef(model_label, pk, clean_spaces(value) or f'#{pk}')
                yield _finding(subject, model_label, pk, field, value)


# ── NM1 · fix ────────────────────────────────────────────────────────────────

def _refused(clean, _detail):
    # Framework errors may be English or contain field names. Keep the operator
    # message in Spanish; the underlying panel validator still decides acceptance.
    return blocker('name_refused', f'El panel no acepta guardar «{clean}». Revisa si otro registro ya se llama '
                   'así o si su cliente, proyecto y carpeta son correctos.')


def _empty():
    return blocker('name_empty', 'Sin los espacios sobrantes quedaría vacío; escribe el nombre a mano.')


def _model_blockers(row, field, clean, *checks):
    """The validation a service runs before saving, on an unsaved copy."""
    if not clean:
        return [_empty()]
    candidate = copy.copy(row)
    setattr(candidate, field, clean)
    try:
        for check in checks:
            check(candidate)
        candidate.full_clean()
    except DjangoValidationError as error:
        return [_refused(clean, error.messages)]
    except ValueError as error:  # CommunicationError carries the message (or a message dict)
        return [_refused(clean, error.args[0] if error.args else '')]
    return []


def _side_changes(row, validated, field, label):
    """Columns the writer's validation fills besides the name, e.g. the client of
    a document or folder that only had a project."""
    columns = {item.name: item.attname for item in row._meta.concrete_fields}
    found = []
    for name, value in validated.items():
        attname, after = columns.get(name), getattr(value, 'pk', value)
        if name != field and attname and getattr(row, attname) != after:
            found.append(change(row, attname, getattr(row, attname), after, label))
    return found


def _row_plan(kind, row, field, clean, blockers, extra=()):
    label = clean or f'#{row.pk}'
    return {
        'closure': [(row._meta.label_lower, row.pk)],
        'changes': [change(row, field, getattr(row, field), clean, label), *extra],
        'blockers': blockers,
        'context': {'kind': kind, 'pk': row.pk, 'value': clean},
    }


def _serializer_plan(kind, row, field, clean, serializer_class):
    if not clean:
        return _row_plan(kind, row, field, clean, [_empty()])
    serializer = serializer_class(row, data={field: clean}, partial=True)
    if not serializer.is_valid():
        return _row_plan(kind, row, field, clean, [_refused(clean, serializer.errors)])
    return _row_plan(kind, row, field, clean, [], _side_changes(row, serializer.validated_data, field, clean))


def _client_plan(profile, changes, values, blockers=()):
    from content.models.web_app_diagnostic import WebAppDiagnostic
    closure = writers.client_identity_closure(profile)
    # ``sync_snapshot_for_profile`` rewrites the client's diagnostic copies too.
    closure += [(DIAGNOSTIC, pk) for pk in WebAppDiagnostic._base_manager.filter(client_id=profile.pk)
                .values_list('pk', flat=True)]
    copies = len(closure) - 2
    warnings = [{'code': 'client_copies_resync',
                 'message': 'Al guardar se actualizan también los datos del cliente copiados en sus '
                            f'propuestas y diagnósticos ({copies}).'}] if copies else []
    return {'closure': closure, 'changes': changes, 'blockers': list(blockers), 'warnings': warnings,
            'guards': {'profile': profile.pk, 'copies': [list(key) for key in sorted(closure)]},
            'context': {'kind': 'client', 'profile': profile.pk, 'values': values}}


def _plan_company(evidence, clean):
    profile = _client(pk=evidence['pk'])
    return _client_plan(profile, [change(profile, 'company_name', profile.company_name, clean,
                                         client_label(profile))], {'company': clean})


def _plan_client_name(evidence, clean):
    """``update_client_profile`` takes one full name and splits it at the first space."""
    from accounts.services.proposal_client_service import _split_name
    profile = _client(user_id=evidence['pk'])
    user, label = profile.user, client_label(profile)
    target = {'first_name': clean_spaces(user.first_name), 'last_name': clean_spaces(user.last_name)}
    name = ' '.join(part for part in target.values() if part)
    split = _split_name(name)
    blockers = []
    if split != (target['first_name'], target['last_name']):
        blockers.append(blocker(
            'name_split_ambiguous',
            f'Sin los espacios sobrantes, «{name}» quedaría repartido como nombre «{split[0]}» y apellido '
            f'«{split[1]}», distinto de como está hoy. Corrígelo a mano desde la ficha del cliente.'))
    changes = [change(user, field, getattr(user, field), value, label)
               for field, value in target.items() if getattr(user, field) != value]
    return _client_plan(profile, changes, {'name': name}, blockers)


def _plan_project(evidence, clean):
    """A rename re-syncs the managed root folder and root thread (``post_save``), and
    the root re-sync re-points the root's subfolders of this project that name
    another client."""
    from accounts.models import Project
    from content.models import CommunicationThread, DocumentFolder
    from content.serializers.panel_projects import UpdatePanelProjectSerializer
    project = Project._base_manager.get(pk=evidence['pk'])
    plan = _serializer_plan('project', project, 'name', clean, UpdatePanelProjectSerializer)
    roots = writers.project_root_closure(project.pk)
    folders = list(DocumentFolder._base_manager.filter(pk__in=[pk for label, pk in roots if label == FOLDER]))
    threads = CommunicationThread._base_manager.filter(pk__in=[pk for label, pk in roots if label == THREAD])
    for row, field in [*((folder, 'name') for folder in folders), *((thread, 'title') for thread in threads)]:
        if getattr(row, field) != clean:
            plan['changes'].append(change(row, field, getattr(row, field), clean, clean))
    stale = [folder for root in folders for folder in DocumentFolder._base_manager.filter(
        pk__in=root.get_descendant_ids(), project_id=project.pk).exclude(client_user_id=project.client_id)]
    plan['changes'] += [change(folder, 'client_user_id', folder.client_user_id, project.client_id, folder.name)
                        for folder in stale]
    plan['closure'] += [*roots, *((FOLDER, folder.pk) for folder in stale)]
    plan['blockers'] += retained_blockers([*folders, *threads, *stale])
    return plan


def _plan_folder(evidence, clean):
    from content.models import DocumentFolder
    from content.serializers.document_folder import DocumentFolderSerializer
    folder = DocumentFolder._base_manager.get(pk=evidence['pk'])
    return _serializer_plan('folder', folder, 'name', clean, DocumentFolderSerializer)


def _plan_document(evidence, clean):
    from content.models import Document
    from content.serializers.document import DocumentCreateUpdateSerializer
    document = Document._base_manager.get(pk=evidence['pk'])
    return _serializer_plan('document', document, 'title', clean, DocumentCreateUpdateSerializer)


def _plan_proposal(evidence, clean):
    from content.models import BusinessProposal
    from content.serializers.proposal import ProposalCreateUpdateSerializer
    proposal = BusinessProposal._base_manager.get(pk=evidence['pk'])
    return _serializer_plan('proposal', proposal, 'title', clean, ProposalCreateUpdateSerializer)


def _rename_proposal(context, actor):
    from content.models import BusinessProposal
    from content.serializers.proposal import ProposalCreateUpdateSerializer
    proposal = BusinessProposal._base_manager.get(pk=context['pk'])
    serializer = ProposalCreateUpdateSerializer(proposal, data={'title': context['value']}, partial=True)
    serializer.is_valid(raise_exception=True)
    # The panel serializer validates the title; a narrow, history-tracked save avoids
    # full-save pricing snapshot cleanup and leaves client identity untouched.
    proposal.title = serializer.validated_data['title']
    proposal.save(update_fields=['title', 'updated_at'])


def _plan_communication_folder(evidence, clean):
    from content.models import CommunicationFolder
    folder = CommunicationFolder._base_manager.get(pk=evidence['pk'])
    return _row_plan('communication_folder', folder, 'name', clean, _model_blockers(folder, 'name', clean))


def _plan_thread(evidence, clean):
    """``update_thread`` refuses closed threads and re-validates the thread's folder."""
    from content.models import CommunicationThread
    from content.services.communication_folder_service import validate_thread_folder
    thread = CommunicationThread._base_manager.get(pk=evidence['pk'])
    if thread.status == CommunicationThread.Status.CLOSED:
        blockers = [blocker('thread_closed', 'La comunicación está cerrada: reábrela para poder corregir su título.')]
    else:
        blockers = _model_blockers(thread, 'title', clean, validate_thread_folder)
    return _row_plan('thread', thread, 'title', clean, blockers)


PLANNERS = {
    PROFILE: _plan_company, USER: _plan_client_name, PROJECT: _plan_project, FOLDER: _plan_folder,
    DOCUMENT: _plan_document, PROPOSAL: _plan_proposal,
    COMM_FOLDER: _plan_communication_folder, THREAD: _plan_thread,
}
WRITERS = {
    'client': lambda context, actor: writers.update_client_identity(context['profile'], **context['values']),
    'project': lambda context, actor: writers.rename_project(context['pk'], context['value'], actor),
    'folder': lambda context, actor: writers.rename_document_folder(context['pk'], context['value']),
    'document': lambda context, actor: writers.rename_document(context['pk'], context['value'], actor),
    'proposal': _rename_proposal,
    'communication_folder': lambda context, actor: writers.rename_communication_folder(
        context['pk'], context['value']),
    'thread': lambda context, actor: writers.update_thread(context['pk'], actor, title=context['value']),
}


class ExtraSpacesFixer(Fixer):
    kind = RENAME
    # Besides the name fields ``writers`` registers: who last edited a document
    # or thread, the client a document's validation fills from its project, and
    # the client copies ``sync_snapshot_for_profile`` keeps on diagnostics.
    fields = {
        DOCUMENT: ('updated_by_id', 'client_user_id', 'client_name', 'slug'),
        THREAD: ('updated_by_id',),
        PROPOSAL: ('title',),
        FOLDER: ('parent_id', 'project_id', 'archived_via_folder_id', 'slug'),
        DIAGNOSTIC: ('client_name', 'client_email', 'client_phone', 'client_company'),
    }

    def plan(self, finding, params, *, actor):
        evidence = finding.evidence
        return self.new_plan(params, **PLANNERS[evidence['model']](evidence, clean_spaces(evidence['value'])))

    def guards_changed(self, step):
        from accounts.models import UserProfile
        from content.models.web_app_diagnostic import WebAppDiagnostic
        guards = step.get('guards', {})
        if 'profile' not in guards:
            return False
        profile = UserProfile._base_manager.filter(pk=guards['profile']).first()
        if profile is None:
            return True
        closure = writers.client_identity_closure(profile)
        closure += [(DIAGNOSTIC, pk) for pk in WebAppDiagnostic._base_manager.filter(client_id=profile.pk)
                    .values_list('pk', flat=True)]
        return [list(key) for key in sorted(closure)] != guards['copies']

    def apply(self, plan, *, actor):
        WRITERS[plan.context['kind']](plan.context, actor)

    def revert(self, step, *, actor):
        """Client identity and project names go back through their writers, which
        re-sync the client copies and log the project change. The engine's exact
        restore then writes what a writer cannot express (trimmed edges, a full
        name it would split differently); other kinds rely on that restore alone."""
        subject = step['subjects'][0]
        before = {(item['model'], item['field']): item['before'] for item in step['items']
                  if item['model'] in (PROFILE, USER, PROJECT) and not item['guard']}
        if subject['model'] == PROJECT and (PROJECT, 'name') in before:
            writers.rename_project(subject['id'], before[(PROJECT, 'name')], actor)
        elif subject['model'] == PROFILE:
            values = {}
            if (PROFILE, 'company_name') in before:
                values['company'] = before[(PROFILE, 'company_name')]
            if {(USER, 'first_name'), (USER, 'last_name')} & set(before):
                user = _client(pk=subject['id']).user
                values['name'] = ' '.join((before.get((USER, 'first_name'), user.first_name),
                                           before.get((USER, 'last_name'), user.last_name)))
            if values:
                writers.update_client_identity(subject['id'], **values)


register_fixer('NM1', ExtraSpacesFixer())
