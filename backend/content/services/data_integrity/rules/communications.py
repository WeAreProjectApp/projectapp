"""Communication rules (CM*): threads, their folders and secure links.

Thread writes go through ``communication_service.update_thread`` and folder
renames through ``save_folder``, the services the Panel uses. A project's or
client's root thread (``thread_kind != 'manual'``) is kept in sync by its
owner, so its findings are reported instead of fixed.
"""
from collections import defaultdict
from copy import copy
from datetime import timedelta

from django.db.models import F

from content.services.data_integrity.catalog import register_fixer, rule
from content.services.data_integrity.fixes import writers
from content.services.data_integrity.fixes.base import Fixer, change, required_choice, retained_blockers
from content.services.data_integrity.rules.documents import (
    NAME_TAKEN, NO_PROJECT, chosen_project, folder_key, new_name, project_input, projects_by_client, user_label,
)
from content.services.data_integrity.scope import COMM_FOLDER, PROJECT, SECURE_LINK, THREAD, client_label
from content.services.data_integrity.types import ARCHIVE, RELINK, RENAME, REPORT_ONLY, Finding, RecordRef, blocker

STALE_THREAD_DAYS = 30
ROOT = 'Raíz (sin carpeta)'


def _thread_error_blocker(errors):
    if 'project' in errors:
        return blocker('project_mismatch', 'El proyecto del hilo es de otro cliente: corrige antes ese hallazgo.')
    return blocker('writer_refused', 'Comunicaciones no acepta este cambio en el hilo; revisa su cliente y su '
                   'carpeta.')


def _thread_blockers(thread, **values):
    """``update_thread``'s own checks, run on a copy so a plan never writes."""
    from django.core.exceptions import ValidationError
    from content.services.communication_folder_service import validate_thread_folder
    from content.services.communication_service import CommunicationError
    proposed = copy(thread)
    for field, value in values.items():
        setattr(proposed, field, value)
    try:
        validate_thread_folder(proposed)
        proposed.full_clean()
    except CommunicationError:
        return [blocker('folder_mismatch', 'La carpeta del hilo es de otro cliente o proyecto: muévelo antes a la '
                        'raíz.')]
    except ValidationError as exc:
        return [_thread_error_blocker(exc.message_dict)]
    return []


# ── CM1 · thread linked to another client's project ──────────────────────────

@rule(id='CM1', domain='communications', severity='high', fix_kinds=(RELINK, REPORT_ONLY),
      title='Hilo de comunicaciones vinculado al proyecto de otro cliente',
      description='La conversación es con un cliente pero está vinculada a un proyecto de otro cliente. Se '
                  'vincula a un proyecto de su propio cliente o se deja sin proyecto. Si es la comunicación madre '
                  'de un proyecto o de un cliente, sólo se informa.')
def detect_thread_foreign_project(scope):
    from content.models import CommunicationThread
    threads = list(scope.limit(
        CommunicationThread._base_manager
        .filter(retention_context__isnull=True, project__isnull=False)
        .exclude(project__client_id=F('client__user_id'))
        .select_related('client__user', 'project__client__profile')
        .order_by('pk'), THREAD))
    projects = projects_by_client(thread.client.user_id for thread in threads)
    for thread in threads:
        project = thread.project
        finding = Finding(
            rule_id='CM1',
            subjects=(RecordRef(THREAD, thread.pk, thread.title), RecordRef(PROJECT, project.pk, project.name)),
            evidence={'thread': thread.pk, 'project': project.pk, 'client': thread.client_id},
            message=f'El hilo «{thread.title}» es con {client_label(thread.client)}, pero está vinculado al '
                    f'proyecto «{project.name}», que es de {user_label(project.client)}.',
        )
        if thread.thread_kind != 'manual':
            finding.fix_kinds = (REPORT_ONLY,)
            finding.message += (' Es la comunicación madre de su proyecto o cliente: se corrige desde ese proyecto '
                                'o cliente.')
        else:
            finding.fix_kinds = (RELINK,)
            finding.inputs = {'project': project_input('el proyecto del hilo', projects[thread.client.user_id])}
            finding.suggestion = {'project': NO_PROJECT}
        yield finding


def _folder_after_relink(thread, project):
    """``update_thread`` drops a folder tied to another project when only the project changes."""
    folder = thread.folder
    if folder is not None and folder.project_id and folder.project_id != getattr(project, 'pk', None):
        return None
    return folder


class _ThreadAssociationUndoGuard:
    """A removed original project or folder cannot be restored by undo."""

    def guards_changed(self, step):
        from accounts.models import Project
        from content.models import CommunicationFolder
        for field, model in (('project_id', Project), ('folder_id', CommunicationFolder)):
            wanted = {item['before'] for item in step['items']
                      if item['model'] == THREAD and item['field'] == field and item['before'] is not None}
            if model._base_manager.filter(pk__in=wanted).count() != len(wanted):
                return True
        return False


class ThreadProjectFixer(_ThreadAssociationUndoGuard, Fixer):
    kind = RELINK
    fields = {THREAD: ('project_id', 'folder_id', 'updated_by_id')}

    def plan(self, finding, params, *, actor):
        from content.models import CommunicationThread
        thread = (CommunicationThread._base_manager.select_related('client', 'project', 'folder')
                  .get(pk=finding.evidence['thread']))
        target, blockers = chosen_project(params, finding, 'el proyecto del hilo')
        if blockers:
            return self.new_plan(params, closure=[(THREAD, thread.pk)], blockers=blockers)
        folder = _folder_after_relink(thread, target)
        blockers = retained_blockers([thread])
        if thread.status == CommunicationThread.Status.CLOSED:
            blockers.append(blocker('thread_closed', 'El hilo está cerrado: reábrelo antes de cambiarle el '
                                    'proyecto.'))
        if not blockers:
            blockers = _thread_blockers(thread, project=target, folder=folder)
        changes = [change(thread, 'project', thread.project.name, target.name if target else 'Sin proyecto')]
        if thread.folder_id and folder is None:
            changes.append(change(thread, 'folder', thread.folder.name, ROOT))
        return self.new_plan(params, closure=[(THREAD, thread.pk)], blockers=blockers, changes=changes,
                             context={'thread_id': thread.pk, 'project': target})

    def apply(self, plan, *, actor):
        writers.update_thread(plan.context['thread_id'], actor, project=plan.context['project'])


register_fixer('CM1', ThreadProjectFixer())


# ── CM2 · thread filed in another context's folder ───────────────────────────

@rule(id='CM2', domain='communications', severity='medium', fix_kinds=(RELINK, REPORT_ONLY),
      title='Hilo de comunicaciones en una carpeta de otro cliente o proyecto',
      description='La conversación está guardada en una carpeta de otro cliente o de otro proyecto, así que no '
                  'aparece donde se la busca. Se mueve a la raíz de las comunicaciones de su cliente. Una '
                  'comunicación madre dentro de una carpeta sólo se informa.')
def detect_misfiled_threads(scope):
    from content.models import CommunicationThread
    threads = scope.limit(
        CommunicationThread._base_manager.filter(retention_context__isnull=True, folder__isnull=False)
        .select_related('folder').order_by('pk'), THREAD)
    for thread in threads:
        folder = thread.folder
        managed = thread.thread_kind != 'manual'
        # The rule of ``validate_thread_folder``: same client, and the folder's project if it has one.
        foreign = (folder.client_id != thread.client_id
                   or bool(folder.project_id and folder.project_id != thread.project_id))
        if not (managed or foreign):
            continue
        finding = Finding(
            rule_id='CM2',
            subjects=(RecordRef(THREAD, thread.pk, thread.title), RecordRef(COMM_FOLDER, folder.pk, folder.name)),
            evidence={'thread': thread.pk, 'folder': folder.pk},
        )
        if managed:
            finding.fix_kinds = (REPORT_ONLY,)
            finding.message = (f'«{thread.title}» es la comunicación madre de su proyecto o cliente y debe quedar en '
                               f'la raíz, pero está dentro de la carpeta «{folder.name}».')
        else:
            finding.fix_kinds = (RELINK,)
            finding.message = (f'El hilo «{thread.title}» está en la carpeta «{folder.name}», que es de otro cliente '
                               'o proyecto. Se mueve a la raíz.')
        yield finding


class ThreadFolderFixer(_ThreadAssociationUndoGuard, Fixer):
    kind = RELINK
    fields = {THREAD: ('folder_id', 'updated_by_id')}

    def plan(self, finding, params, *, actor):
        from content.models import CommunicationThread
        thread = (CommunicationThread._base_manager.select_related('client', 'project', 'folder')
                  .get(pk=finding.evidence['thread']))
        blockers = retained_blockers([thread]) or _thread_blockers(thread, folder=None)
        return self.new_plan(
            params, closure=[(THREAD, thread.pk)], blockers=blockers,
            changes=[change(thread, 'folder', thread.folder.name if thread.folder_id else ROOT, ROOT)],
            context={'thread_id': thread.pk},
        )

    def apply(self, plan, *, actor):
        writers.update_thread(plan.context['thread_id'], actor, folder=None)


register_fixer('CM2', ThreadFolderFixer())


# ── CM3 · duplicate sibling communication folders ────────────────────────────

@rule(id='CM3', domain='communications', severity='low', fix_kinds=(RENAME,), group=True,
      title='Carpetas de comunicaciones hermanas con el mismo nombre',
      description='En el mismo cliente, proyecto y carpeta hay dos o más carpetas de comunicaciones con el mismo '
                  'nombre, así que las conversaciones quedan repartidas. Se renombra una de ellas.')
def detect_duplicate_communication_folders(scope):
    from content.models import CommunicationFolder
    groups = defaultdict(list)
    for folder in CommunicationFolder._base_manager.filter(retention_context__isnull=True).order_by('pk'):
        groups[(folder.client_id, folder.project_id, folder.parent_id, folder_key(folder.name))].append(folder)
    ordered = sorted(groups.items(), key=lambda item: tuple(value or 0 for value in item[0][:3]) + (item[0][3],))
    for (client_id, project_id, parent_id, key), folders in ordered:
        if len(folders) < 2 or not scope.touches(COMM_FOLDER, [folder.pk for folder in folders]):
            continue
        options = [{'value': folder.pk, 'label': f'{folder.name} (#{folder.pk})'} for folder in folders]
        yield Finding(
            rule_id='CM3',
            subjects=tuple(RecordRef(COMM_FOLDER, folder.pk, folder.name) for folder in folders),
            evidence={'client': client_id, 'project': project_id, 'parent': parent_id, 'key': key,
                      'folders': [folder.pk for folder in folders]},
            message=f'Hay {len(folders)} carpetas de comunicaciones llamadas «{folders[0].name}» en el mismo lugar.',
            inputs={'folder': {'label': 'la carpeta a renombrar', 'options': options, 'required': True},
                    'name': {'label': 'el nombre nuevo', 'required': True}},
            suggestion={'folder': folders[-1].pk},
        )


COMM_FOLDER_ERRORS = {
    'client': 'El cliente de la carpeta no es válido; corrígelo antes de renombrarla.',
    'project': 'El proyecto de la carpeta es de otro cliente; corrígelo antes de renombrarla.',
    'parent': 'La carpeta está dentro de otra de un cliente o proyecto distinto; corrígelo antes de renombrarla.',
}


def _communication_rename_blockers(folder, name):
    """CM3's own duplicate rule (``save_folder`` does not check names) plus the
    model validation ``save_folder`` runs, on a copy."""
    from django.core.exceptions import ValidationError
    from content.models import CommunicationFolder
    siblings = (CommunicationFolder._base_manager
                .filter(client_id=folder.client_id, project_id=folder.project_id, parent_id=folder.parent_id,
                        retention_context__isnull=True)
                .exclude(pk=folder.pk).values_list('name', flat=True))
    if any(folder_key(other) == folder_key(name) for other in siblings):
        return [blocker('name_collision', NAME_TAKEN)]
    proposed = copy(folder)
    proposed.name = name
    try:
        proposed.full_clean()
    except ValidationError as exc:
        field = next((key for key in COMM_FOLDER_ERRORS if key in exc.message_dict), None)
        return [blocker('writer_refused', COMM_FOLDER_ERRORS[field] if field else
                        'Comunicaciones no acepta este nombre para la carpeta.')]
    return []


class CommunicationFolderRenameFixer(Fixer):
    kind = RENAME
    fields = {COMM_FOLDER: ('name',)}

    def plan(self, finding, params, *, actor):
        from content.models import CommunicationFolder
        folder_id, blockers = required_choice(params, 'folder', finding.inputs['folder']['options'],
                                              'la carpeta a renombrar')
        name, name_blockers = new_name(params, 'el nombre nuevo de la carpeta')
        blockers += name_blockers
        if blockers:
            return self.new_plan(params, blockers=blockers)
        folder = CommunicationFolder._base_manager.get(pk=folder_id)
        blockers = retained_blockers([folder]) or _communication_rename_blockers(folder, name)
        return self.new_plan(params, closure=[(COMM_FOLDER, folder.pk)], blockers=blockers,
                             changes=[change(folder, 'name', folder.name, name)],
                             context={'folder_id': folder.pk, 'name': name})

    def apply(self, plan, *, actor):
        writers.rename_communication_folder(plan.context['folder_id'], plan.context['name'])


register_fixer('CM3', CommunicationFolderRenameFixer())


# ── CM4 · old empty threads ──────────────────────────────────────────────────

@rule(id='CM4', domain='communications', severity='low', fix_kinds=(ARCHIVE,),
      title='Hilo de comunicaciones vacío y antiguo',
      description=f'Una conversación creada hace más de {STALE_THREAD_DAYS} días que nunca tuvo mensajes. Se '
                  'archiva: deja de verse en la lista y se puede restaurar.')
def detect_stale_empty_threads(scope):
    from django.utils import timezone
    from content.models import CommunicationThread
    threads = scope.limit(
        CommunicationThread._base_manager
        .filter(retention_context__isnull=True, is_archived=False, managed_project__isnull=True,
                managed_client__isnull=True, messages__isnull=True,
                created_at__lt=timezone.now() - timedelta(days=STALE_THREAD_DAYS))
        .order_by('pk'), THREAD)
    for thread in threads:
        yield Finding(
            rule_id='CM4',
            subjects=(RecordRef(THREAD, thread.pk, thread.title),),
            evidence={'thread': thread.pk},
            message=f'El hilo «{thread.title}» se creó hace más de {STALE_THREAD_DAYS} días y nunca tuvo mensajes.',
        )


class StaleThreadArchiver(Fixer):
    kind = ARCHIVE
    fields = {THREAD: ('is_archived', 'archived_at', 'updated_by_id')}

    def plan(self, finding, params, *, actor):
        from content.models import CommunicationThread
        thread = CommunicationThread._base_manager.get(pk=finding.evidence['thread'])
        blockers = retained_blockers([thread])
        if thread.thread_kind != 'manual':
            blockers.append(blocker('root_thread', 'Es la comunicación madre de su proyecto o cliente y no se '
                                    'archiva.'))
        return self.new_plan(params, closure=[(THREAD, thread.pk)], blockers=blockers,
                             changes=[change(thread, 'is_archived', False, True)],
                             context={'thread_id': thread.pk})

    def apply(self, plan, *, actor):
        from content.models import CommunicationThread
        from content.services import communication_service
        communication_service.archive_thread(CommunicationThread._base_manager.get(pk=plan.context['thread_id']),
                                             actor=actor)

    def revert(self, step, *, actor):
        from content.models import CommunicationThread
        from content.services import communication_service
        thread = CommunicationThread._base_manager.get(pk=step['subjects'][0]['id'])
        if thread.is_archived:
            communication_service.unarchive_thread(thread, actor=actor)


register_fixer('CM4', StaleThreadArchiver())


# ── CM5 · secure link linked to another client's project ─────────────────────

@rule(id='CM5', domain='communications', severity='medium', fix_kinds=(REPORT_ONLY,),
      title='Enlace seguro vinculado al proyecto de otro cliente',
      description='Un enlace seguro de un cliente está vinculado a un proyecto de otro cliente, así que aparece '
                  'en el proyecto equivocado. Se revisa a mano desde Enlaces seguros.')
def detect_secure_link_foreign_project(scope):
    from secure_links.models import SecureLink
    links = scope.limit(
        SecureLink._base_manager
        .filter(retention_context__isnull=True, client__isnull=False, project__isnull=False)
        .exclude(project__client_id=F('client__user_id'))
        .select_related('client__user', 'project__client__profile')
        .order_by('pk'), SECURE_LINK)
    for link in links:
        project = link.project
        yield Finding(
            rule_id='CM5',
            subjects=(RecordRef(SECURE_LINK, link.pk, link.title), RecordRef(PROJECT, project.pk, project.name)),
            evidence={'link': link.pk, 'project': project.pk, 'client': link.client_id},
            message=f'El enlace seguro «{link.title}» es de {client_label(link.client)}, pero está vinculado al '
                    f'proyecto «{project.name}», que es de {user_label(project.client)}.',
        )
