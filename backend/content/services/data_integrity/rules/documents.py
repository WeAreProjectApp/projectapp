"""Document and document-folder rules (DC*).

DC4 groups sibling names with the shared duplicate normalizer. Its findings offer
``merge_folders`` (``survivor``/``duplicate`` params, fixer in
``fixes/merge_folders``) and ``rename`` (``folder``/``name`` params).

Documents the Panel never rewrites (generated proposal copies, the contract
template mirror, collection accounts) are reported instead of fixed, and the
helpers at the top are shared with ``rules/communications``.
"""
from collections import defaultdict

from django.db.models import F, Q

from content.services.data_integrity.catalog import register_fixer, rule
from content.services.data_integrity.fixes import writers
from content.services.data_integrity.fixes.base import Fixer, change, required_choice, retained_blockers
from content.services.data_integrity.hashing import normalized
from content.services.data_integrity.scope import DOCUMENT, DOCUMENT_THREAD, FOLDER, PROJECT, client_label
from content.services.data_integrity.types import (
    EXISTING_TOOL, MERGE_FOLDERS, RELINK, RENAME, REPORT_ONLY, SYNC_COPY, Finding, RecordRef, blocker,
)

NO_PROJECT = 'none'
NAME_MAX_LENGTH = 120
NAME_TAKEN = 'Ya hay otra carpeta con ese nombre en el mismo lugar; elige otro nombre.'


# ── Shared helpers ───────────────────────────────────────────────────────────

def folder_key(name):
    return normalized(name)


def _folder_label(folder):
    return folder.name


def user_label(user):
    """How the Panel names a client user: its client profile, else the account."""
    profile = getattr(user, 'profile', None)
    if profile is not None:
        return client_label(profile)
    return user.get_full_name() or user.email or f'Usuario {user.pk}'


def plural(count, one, many):
    return f'{count} {one if count == 1 else many}'


def projects_by_client(user_ids):
    """{client user id: [(project id, name)]}: the projects a record of that client may point at."""
    from accounts.models import Project
    found = defaultdict(list)
    rows = (Project._base_manager.filter(client_id__in=set(user_ids))
            .order_by('name', 'pk').values_list('pk', 'name', 'client_id'))
    for pk, name, client_id in rows:
        found[client_id].append((pk, name))
    return found


def project_input(label, projects):
    options = [{'value': NO_PROJECT, 'label': 'Sin proyecto'}]
    options += [{'value': pk, 'label': name} for pk, name in projects]
    return {'label': label, 'options': options, 'required': True}


def chosen_project(params, finding, label):
    """(project or None for «Sin proyecto», blockers) from the ``project`` param."""
    from accounts.models import Project
    value, blockers = required_choice(params, 'project', finding.inputs['project']['options'], label)
    if blockers or value == NO_PROJECT:
        return None, blockers
    project = Project._base_manager.filter(pk=value).first()
    if project is None:
        return None, [blocker('invalid_input', f'La opción elegida para {label} no es válida.')]
    return project, []


def new_name(params, label):
    """(trimmed name, blockers) from the required ``name`` param."""
    value = params.get('name')
    name = value.strip() if isinstance(value, str) else ''
    if not name:
        return None, [blocker('input_required', f'Falta escribir {label}.')]
    if len(name) > NAME_MAX_LENGTH:
        return None, [blocker('invalid_input', f'El nombre nuevo no puede pasar de {NAME_MAX_LENGTH} caracteres.')]
    return name, []


def _mirror_ids(document_ids):
    from content.models import Document
    from content.services.contract_mirror_service import mirror_documents
    if not document_ids:
        return set()
    return set(mirror_documents(Document._base_manager.filter(pk__in=document_ids)).values_list('pk', flat=True))


def _read_only_reason(document, mirrors, *, any_collection_account):
    """Why the Panel refuses to rewrite this document, or '' when it accepts."""
    from content.models import Document
    from content.services.document_type_codes import COLLECTION_ACCOUNT
    if document.pk in mirrors:
        return 'Es la plantilla de contrato, que es de sólo lectura: se revisa desde Contratos.'
    if document.is_generated_snapshot:
        return 'Es una copia generada de una propuesta y no se modifica: se revisa desde la propuesta.'
    if getattr(document.document_type, 'code', None) == COLLECTION_ACCOUNT and (
            any_collection_account or document.commercial_status != Document.CommercialStatus.DRAFT):
        return 'Es una cuenta de cobro: se corrige desde Contabilidad.'
    return ''


# ── DC1 · document linked to another client's project ────────────────────────

@rule(id='DC1', domain='documents', severity='high', fix_kinds=(RELINK, REPORT_ONLY),
      title='Documento vinculado al proyecto de otro cliente',
      description='Un documento de un cliente está vinculado a un proyecto de otro cliente, así que aparece en un '
                  'proyecto que no es suyo. Se vincula a un proyecto de su propio cliente o se deja sin proyecto. '
                  'Las cuentas de cobro, las copias generadas de propuestas y la plantilla de contrato sólo se '
                  'informan: se corrigen desde su propio módulo.')
def detect_document_foreign_project(scope):
    from content.models import Document
    documents = list(scope.limit(
        Document._base_manager
        .filter(retention_context__isnull=True, client_user__isnull=False, project__isnull=False)
        .exclude(project__client_id=F('client_user_id'))
        .select_related('folder', 'document_type', 'client_user__profile', 'project__client__profile')
        .order_by('pk'), DOCUMENT))
    mirrors = _mirror_ids([document.pk for document in documents])
    projects = projects_by_client(document.client_user_id for document in documents)
    for document in documents:
        project = document.project
        finding = Finding(
            rule_id='DC1',
            subjects=(RecordRef(DOCUMENT, document.pk, document.title), RecordRef(PROJECT, project.pk, project.name)),
            evidence={'document': document.pk, 'project': project.pk, 'client_user': document.client_user_id},
            message=f'«{document.title}» es de {user_label(document.client_user)}, pero está vinculado al proyecto '
                    f'«{project.name}», que es de {user_label(project.client)}.',
        )
        reason = _read_only_reason(document, mirrors, any_collection_account=True)
        if reason:
            finding.fix_kinds = (REPORT_ONLY,)
            finding.message = f'{finding.message} {reason}'
        else:
            own = projects[document.client_user_id]
            folder_project = document.folder.project_id if document.folder_id else None
            finding.fix_kinds = (RELINK,)
            finding.inputs = {'project': project_input('el proyecto del documento', own)}
            finding.suggestion = {'project': folder_project if folder_project in {pk for pk, _ in own} else NO_PROJECT}
        yield finding


def _reassignment_blockers(document, project):
    """The writer's own guard, without its locks."""
    from rest_framework.exceptions import ValidationError
    from accounts.services.billing_reassignment import validate_document_reassignment
    try:
        validate_document_reassignment(document, changes={'project': project})
    except ValidationError:
        return [blocker('invalid_target', 'Ese proyecto no se puede asignar a este documento: es de otro cliente '
                        'o el documento ya está asociado a un cobro.')]
    return []


class DocumentProjectFixer(Fixer):
    kind = RELINK
    fields = {DOCUMENT: ('project_id',)}

    def guards_changed(self, step):
        from accounts.models import Project
        wanted = {item['before'] for item in step['items']
                  if item['model'] == DOCUMENT and item['field'] == 'project_id' and item['before'] is not None}
        return Project._base_manager.filter(pk__in=wanted).count() != len(wanted)

    def plan(self, finding, params, *, actor):
        from content.models import Document
        document = Document._base_manager.select_related('project').get(pk=finding.evidence['document'])
        target, blockers = chosen_project(params, finding, 'el proyecto del documento')
        if blockers:
            return self.new_plan(params, closure=[(DOCUMENT, document.pk)], blockers=blockers)
        blockers = retained_blockers([document]) or _reassignment_blockers(document, target)
        return self.new_plan(
            params, closure=[(DOCUMENT, document.pk)], blockers=blockers,
            changes=[change(document, 'project', document.project.name,
                            target.name if target else 'Sin proyecto', document.title)],
            context={'document_id': document.pk, 'project': target},
        )

    def apply(self, plan, *, actor):
        writers.relink_documents_project([plan.context['document_id']], plan.context['project'], actor)

    def revert(self, step, *, actor):
        """Put the previous project back with the same ledger row the writer leaves.

        The writer refuses a project of another client by design, so it cannot
        restore the old value; the engine's exact restore would, but silently.
        """
        from accounts.models import Project
        from content.models import Document
        from content.services import accounting_service
        entity = accounting_service.EntityType.DOCUMENT
        for item in step['items']:
            if (item['model'], item['field']) != (DOCUMENT, 'project_id'):
                continue
            document = Document._base_manager.select_related('project', 'client_user__profile').get(pk=item['pk'])
            old_values = accounting_service.snapshot_values(document, entity)
            document.project = Project._base_manager.get(pk=item['before']) if item['before'] else None
            # The domain writer refuses the inconsistent old association; restore only the
            # recorded project inside the engine's savepoint and keep its accounting audit.
            document.save(update_fields=['project', 'updated_at'])
            accounting_service.log_entity_diff(entity, document, old_values, actor)


register_fixer('DC1', DocumentProjectFixer())


# ── DC2 · unlinked document inside a linked folder ───────────────────────────

def _association_text(client_user, project):
    if client_user is not None and project is not None:
        return f'de {user_label(client_user)}, proyecto «{project.name}»'
    if client_user is not None:
        return f'de {user_label(client_user)}'
    return f'del proyecto «{project.name}»'


@rule(id='DC2', domain='documents', severity='medium', fix_kinds=(SYNC_COPY, REPORT_ONLY),
      title='Documento sin cliente ni proyecto en una carpeta que sí los tiene',
      description='El documento no dice de qué cliente ni de qué proyecto es, pero su carpeta sí, así que no '
                  'aparece en los filtros ni en el portal de ese cliente. Se le copian el cliente y el proyecto de '
                  'la carpeta. Las cuentas de cobro emitidas, las copias generadas y la plantilla de contrato sólo '
                  'se informan.')
def detect_unlinked_document_in_linked_folder(scope):
    from content.models import Document
    documents = list(scope.limit(
        Document._base_manager
        .filter(retention_context__isnull=True, is_archived=False, client_user__isnull=True,
                project__isnull=True, folder__isnull=False)
        .filter(Q(folder__client_user__isnull=False) | Q(folder__project__isnull=False))
        .select_related('document_type', 'folder__client_user__profile', 'folder__project')
        .order_by('pk'), DOCUMENT))
    mirrors = _mirror_ids([document.pk for document in documents])
    for document in documents:
        folder = document.folder
        finding = Finding(
            rule_id='DC2',
            subjects=(RecordRef(DOCUMENT, document.pk, document.title), RecordRef(FOLDER, folder.pk, folder.name)),
            evidence={'document': document.pk, 'folder': folder.pk, 'client_user': folder.client_user_id,
                      'project': folder.project_id},
            message=f'«{document.title}» no tiene cliente ni proyecto, pero su carpeta «{folder.name}» es '
                    f'{_association_text(folder.client_user, folder.project)}.',
        )
        reason = _read_only_reason(document, mirrors, any_collection_account=False)
        finding.fix_kinds = (REPORT_ONLY,) if reason else (SYNC_COPY,)
        if reason:
            finding.message = f'{finding.message} {reason}'
        yield finding


def _association_payload(document, folder):
    """The Panel PATCH that copies the folder's client and project to the document,
    or None when the folder's client has no client profile to name it with."""
    payload = {}
    if folder.client_user_id:
        profile = getattr(folder.client_user, 'profile', None)
        if profile is None or profile.role != profile.ROLE_CLIENT:
            return None
        payload['client'] = profile.pk
    if folder.project_id:
        payload['project'] = folder.project_id
    if document.client_name:
        # The serializer replaces the label whenever the client changes and
        # none is sent; a label someone typed survives the copy.
        payload['client_name'] = document.client_name
    return payload


def copy_folder_association(document_id, payload, actor):
    """Panel PATCH semantics: the document serializer resolves and validates the pair."""
    from content.models import Document
    from content.serializers.document import DocumentCreateUpdateSerializer
    serializer = DocumentCreateUpdateSerializer(Document._base_manager.get(pk=document_id), data=payload, partial=True)
    serializer.is_valid(raise_exception=True)
    return serializer.save(updated_by=actor)


class FolderAssociationFixer(Fixer):
    kind = SYNC_COPY
    fields = {DOCUMENT: ('client_user_id', 'project_id', 'client_name', 'updated_by_id', 'slug')}

    def plan(self, finding, params, *, actor):
        from accounts.services.proposal_client_service import build_client_display_name
        from content.models import Document
        from content.serializers.document import DocumentCreateUpdateSerializer
        document = (Document._base_manager.select_related('folder__client_user__profile', 'folder__project__client')
                    .get(pk=finding.evidence['document']))
        folder = document.folder
        payload = _association_payload(document, folder)
        if payload is None:
            return self.new_plan(params, closure=[(DOCUMENT, document.pk)], blockers=[blocker(
                'client_without_profile', 'El cliente de la carpeta no tiene ficha de cliente: asígnale el '
                'cliente al documento a mano.')])
        blockers = retained_blockers([document])
        serializer = DocumentCreateUpdateSerializer(document, data=payload, partial=True)
        if not blockers and not serializer.is_valid():
            blockers.append(blocker('folder_association_invalid', 'El proyecto de la carpeta es de otro cliente: '
                                    'corrige primero la carpeta.') if 'project' in serializer.errors else
                            blocker('writer_refused', 'Documentos no acepta copiar el cliente y el proyecto de la '
                                    'carpeta a este documento.'))
        client_user = folder.client_user if folder.client_user_id else folder.project.client
        changes = [change(document, 'client', 'Sin cliente', user_label(client_user), document.title)]
        if folder.project_id:
            changes.append(change(document, 'project', 'Sin proyecto', folder.project.name, document.title))
        profile = getattr(client_user, 'profile', None)
        if not document.client_name and profile is not None:
            changes.append(change(document, 'client_name', '', build_client_display_name(profile), document.title))
        return self.new_plan(params, closure=[(DOCUMENT, document.pk)], blockers=blockers, changes=changes,
                             context={'document_id': document.pk, 'payload': payload})

    def apply(self, plan, *, actor):
        copy_folder_association(plan.context['document_id'], plan.context['payload'], actor)


register_fixer('DC2', FolderAssociationFixer())


# ── DC3 · folder linked to another client's project ──────────────────────────

@rule(id='DC3', domain='documents', severity='high', fix_kinds=(EXISTING_TOOL, REPORT_ONLY),
      title='Carpeta vinculada al proyecto de otro cliente',
      description='Una carpeta de un cliente está vinculada a un proyecto de otro cliente, y lo que se crea dentro '
                  'hereda esa mezcla. Se corrige con «Cambiar cliente…» de la carpeta, que primero muestra qué '
                  'contenido se mueve.')
def detect_folder_foreign_project(scope):
    from content.models import DocumentFolder
    from content.services.contract_mirror_service import folder_contains_mirror
    folders = scope.limit(
        DocumentFolder._base_manager
        .filter(retention_context__isnull=True, managed_project__isnull=True, managed_client__isnull=True,
                client_user__isnull=False, project__isnull=False)
        .exclude(project__client_id=F('client_user_id'))
        .select_related('client_user__profile', 'project__client__profile')
        .order_by('pk'), FOLDER)
    for folder in folders:
        project = folder.project
        finding = Finding(
            rule_id='DC3',
            subjects=(RecordRef(FOLDER, folder.pk, folder.name), RecordRef(PROJECT, project.pk, project.name)),
            evidence={'folder': folder.pk, 'project': project.pk, 'client_user': folder.client_user_id},
            message=f'La carpeta «{folder.name}» es de {user_label(folder.client_user)}, pero está vinculada al '
                    f'proyecto «{project.name}», que es de {user_label(project.client)}.',
        )
        if folder.system_key:
            finding.fix_kinds = (REPORT_ONLY,)
            finding.message += ' El sistema administra esta carpeta, así que se revisa a mano.'
        elif folder_contains_mirror(folder):
            finding.fix_kinds = (REPORT_ONLY,)
            finding.message += ' Guarda la plantilla de contrato, que no cambia de cliente: se revisa a mano.'
        else:
            arguments = {'folder_id': folder.pk}
            profile = getattr(project.client, 'profile', None)
            if profile is not None and profile.role == profile.ROLE_CLIENT:
                arguments['query'] = {'client_profile_id': profile.pk}
            finding.fix_kinds = (EXISTING_TOOL,)
            finding.tool = {'connector': 'documents', 'name': 'preview_folder_client_change', 'arguments': arguments}
            finding.message += ' Se corrige con «Cambiar cliente…» de la carpeta, que primero muestra qué se mueve.'
        yield finding


# ── DC4 · duplicate sibling folders ──────────────────────────────────────────

@rule(id='DC4', domain='documents', severity='medium', fix_kinds=(MERGE_FOLDERS, RENAME), group=True,
      title='Carpetas hermanas con el mismo nombre',
      description='Dentro de una misma carpeta hay dos o más subcarpetas con el mismo nombre, así que los '
                  'documentos quedan repartidos. Se fusionan en una o se renombra una de ellas.')
def detect_duplicate_sibling_folders(scope):
    from content.models import DocumentFolder
    rows = (DocumentFolder._base_manager
            .filter(is_archived=False, retention_context__isnull=True, system_key__isnull=True)
            .order_by('pk'))
    groups = defaultdict(list)
    for folder in rows:
        groups[(folder.parent_id, folder_key(folder.name))].append(folder)
    for (parent_id, key), folders in sorted(groups.items(), key=lambda item: (item[0][0] or 0, item[0][1])):
        if len(folders) < 2 or not scope.touches(FOLDER, [folder.pk for folder in folders]):
            continue
        options = [{'value': folder.pk, 'label': f'{folder.name} (#{folder.pk})'} for folder in folders]
        yield Finding(
            rule_id='DC4',
            subjects=tuple(RecordRef(FOLDER, folder.pk, _folder_label(folder)) for folder in folders),
            evidence={'parent': parent_id, 'key': key, 'folders': [folder.pk for folder in folders]},
            message=f'Hay {len(folders)} carpetas llamadas «{folders[0].name}» en el mismo lugar.',
            inputs={
                'survivor': {'label': 'la carpeta que se conserva (fusionar)', 'options': options, 'required': False},
                'duplicate': {'label': 'la carpeta que se vacía y se archiva (fusionar)', 'options': options,
                              'required': False},
                'folder': {'label': 'la carpeta a renombrar (renombrar)', 'options': options, 'required': False},
                'name': {'label': 'el nombre nuevo (renombrar)', 'required': False},
            },
            suggestion={'survivor': folders[0].pk, 'duplicate': folders[1].pk},
        )


def _folder_serializer_blocker(errors):
    """One Spanish blocker for a folder-serializer refusal (DRF's own texts are English)."""
    from content.services.contract_mirror_service import CONTRACT_MIRROR_MESSAGE
    codes = {str(code) for code in errors.get('code', [])}
    if 'duplicate_folder_name' in codes:
        return blocker('name_collision', NAME_TAKEN)
    if 'managed_project_folder' in codes:
        return blocker('managed_root', 'Es la carpeta principal de un proyecto: su nombre cambia al renombrar '
                       'el proyecto.')
    if 'system_managed_folder' in codes:
        return blocker('system_managed', 'Esta carpeta la administra el sistema y no se puede renombrar.')
    if CONTRACT_MIRROR_MESSAGE in {str(detail) for detail in errors.get('detail', [])}:
        return blocker('contract_mirror', 'La carpeta guarda la plantilla de contrato, que es de sólo lectura, '
                       'y no se puede renombrar.')
    if 'project' in errors:
        return blocker('folder_association_invalid', 'El proyecto de la carpeta es de otro cliente: corrige '
                       'primero su cliente.')
    return blocker('writer_refused', 'Documentos no acepta este nombre para la carpeta.')


def _rename_blockers(folder, name):
    """DC4's own duplicate rule (it decides whether the finding is gone) plus the
    folder serializer's refusals, checked with ``is_valid`` and never saved."""
    from content.models import DocumentFolder
    from content.serializers.document_folder import DocumentFolderSerializer
    siblings = (DocumentFolder._base_manager
                .filter(parent_id=folder.parent_id, is_archived=False, retention_context__isnull=True,
                        system_key__isnull=True)
                .exclude(pk=folder.pk).values_list('name', flat=True))
    if any(folder_key(other) == folder_key(name) for other in siblings):
        return [blocker('name_collision', NAME_TAKEN)]
    serializer = DocumentFolderSerializer(folder, data={'name': name}, partial=True)
    return [] if serializer.is_valid() else [_folder_serializer_blocker(serializer.errors)]


class FolderRenameFixer(Fixer):
    kind = RENAME
    # The serializer also derives a missing client from the folder's project on save.
    fields = {FOLDER: ('name', 'client_user_id', 'slug')}

    def plan(self, finding, params, *, actor):
        from content.models import DocumentFolder
        folder_id, blockers = required_choice(params, 'folder', finding.inputs['folder']['options'],
                                              'la carpeta a renombrar')
        name, name_blockers = new_name(params, 'el nombre nuevo de la carpeta')
        blockers += name_blockers
        if blockers:
            return self.new_plan(params, blockers=blockers)
        folder = DocumentFolder._base_manager.select_related('project__client__profile').get(pk=folder_id)
        blockers = retained_blockers([folder])
        if folder.system_key:
            blockers.append(blocker('system_managed', 'Esta carpeta la administra el sistema y no se puede '
                                    'renombrar.'))
        if folder.managed_project_id:
            blockers.append(blocker('managed_root', 'Es la carpeta principal de un proyecto: su nombre cambia al '
                                    'renombrar el proyecto.'))
        if folder.managed_client_id:
            blockers.append(blocker('managed_read_only', 'Es la carpeta principal de un cliente: su nombre se '
                                    'revisa desde la ficha del cliente.'))
        if not blockers:
            blockers = _rename_blockers(folder, name)
        changes = [change(folder, 'name', folder.name, name)]
        if folder.project_id and not folder.client_user_id:
            changes.append(change(folder, 'client_user', 'Sin cliente', user_label(folder.project.client)))
        return self.new_plan(params, closure=[(FOLDER, folder.pk)], blockers=blockers, changes=changes,
                             context={'folder_id': folder.pk, 'name': name})

    def apply(self, plan, *, actor):
        writers.rename_document_folder(plan.context['folder_id'], plan.context['name'])


register_fixer('DC4', FolderRenameFixer())


# ── DC6 · active content under an archived folder ────────────────────────────

def _nearest_archived(folders, folder_id):
    """The closest archived folder from ``folder_id`` up to its root (cycle-safe)."""
    seen = set()
    while folder_id is not None and folder_id not in seen and folder_id in folders:
        seen.add(folder_id)
        if folders[folder_id]['archived']:
            return folder_id
        folder_id = folders[folder_id]['parent']
    return None


@rule(id='DC6', domain='documents', severity='high', fix_kinds=(EXISTING_TOOL, REPORT_ONLY), group=True,
      title='Contenido activo dentro de una carpeta archivada',
      description='Hay documentos o carpetas activos dentro de una carpeta archivada: no aparecen ni en el árbol '
                  'ni en Archivados. Se corrige restaurando la carpeta archivada, que también reabre las carpetas '
                  'que la contienen.')
def detect_active_content_in_archived_folders(scope):
    from content.models import Document, DocumentFolder
    folders = {
        pk: {'parent': parent_id, 'archived': archived, 'retained': bool(retained), 'system': bool(system),
             'name': name}
        for pk, parent_id, archived, retained, system, name in DocumentFolder._base_manager.values_list(
            'pk', 'parent_id', 'is_archived', 'retention_context_id', 'system_key', 'name')
    }
    buried = defaultdict(lambda: ([], []))
    for pk, folder_id in (Document._base_manager
                          .filter(is_archived=False, folder__isnull=False, retention_context__isnull=True)
                          .order_by('pk').values_list('pk', 'folder_id')):
        ancestor = _nearest_archived(folders, folder_id)
        if ancestor is not None:
            buried[ancestor][0].append(pk)
    for pk in sorted(folders):
        row = folders[pk]
        if not row['archived'] and not row['retained'] and row['parent'] is not None:
            ancestor = _nearest_archived(folders, row['parent'])
            if ancestor is not None:
                buried[ancestor][1].append(pk)
    groups = [(ancestor, documents, children) for ancestor, (documents, children) in sorted(buried.items())
              if scope.touches(DOCUMENT, documents) or scope.touches(FOLDER, [ancestor, *children])]
    titles = dict(Document._base_manager.filter(pk__in=[pk for _, documents, _ in groups for pk in documents])
                  .values_list('pk', 'title'))
    for ancestor, document_ids, folder_ids in groups:
        archived = folders[ancestor]
        content = [plural(len(document_ids), 'documento activo', 'documentos activos')] if document_ids else []
        content += [plural(len(folder_ids), 'carpeta activa', 'carpetas activas')] if folder_ids else []
        finding = Finding(
            rule_id='DC6',
            subjects=(RecordRef(FOLDER, ancestor, archived['name']),
                      *(RecordRef(DOCUMENT, pk, titles.get(pk, '')) for pk in document_ids),
                      *(RecordRef(FOLDER, pk, folders[pk]['name']) for pk in folder_ids)),
            evidence={'ancestor': ancestor, 'documents': document_ids, 'folders': folder_ids},
            message=f'La carpeta archivada «{archived["name"]}» todavía contiene {" y ".join(content)}, que no se '
                    'ven ni en el árbol ni en Archivados.',
        )
        if archived['retained'] or archived['system']:
            finding.fix_kinds = (REPORT_ONLY,)
            finding.message += (' Esa carpeta no se restaura desde el gestor (la administra el sistema o es de un '
                                'proyecto eliminado): se revisa a mano.')
        else:
            finding.fix_kinds = (EXISTING_TOOL,)
            finding.tool = {'connector': 'documents', 'name': 'unarchive_folder', 'arguments': {'folder_id': ancestor}}
            finding.message += ' Se corrige restaurando esa carpeta.'
        yield finding


# ── DC8 · document threads ───────────────────────────────────────────────────

@rule(id='DC8', domain='documents', severity='low', fix_kinds=(REPORT_ONLY,),
      title='Hilo documental incompleto o con varios clientes',
      description='Un hilo documental reúne al menos dos documentos de un mismo cliente. Este tiene menos de dos '
                  'documentos o mezcla documentos de clientes distintos. Se revisa a mano.')
def detect_inconsistent_document_threads(scope):
    from django.contrib.auth import get_user_model
    from content.models import DocumentThread, DocumentThreadItem
    # A thread containing retained documents is conserved history, not a live
    # group whose cardinality or ownership can be repaired by this rule.
    retained = DocumentThreadItem._base_manager.filter(document__retention_context__isnull=False).values('thread_id')
    threads = scope.limit(DocumentThread._base_manager.exclude(pk__in=retained), DOCUMENT_THREAD)
    members = defaultdict(list)
    for thread_id, document_id, title, client_id in (
            DocumentThreadItem._base_manager.filter(thread__in=threads).order_by('thread_id', 'document_id')
            .values_list('thread_id', 'document_id', 'document__title', 'document__client_user_id')):
        members[thread_id].append((document_id, title, client_id))
    flagged = []
    for thread_id, title in threads.order_by('pk').values_list('pk', 'title'):
        items = members[thread_id]
        clients = sorted({client_id for _, _, client_id in items if client_id})
        if len(items) < 2 or len(clients) > 1:
            flagged.append((thread_id, title, items, clients))
    users = get_user_model()._base_manager.filter(
        pk__in={client_id for *_, clients in flagged for client_id in clients}).select_related('profile')
    labels = {user.pk: user_label(user) for user in users}
    for thread_id, title, items, clients in flagged:
        if len(items) < 2:
            count = 'no tiene documentos' if not items else 'tiene un solo documento'
            message = f'El hilo documental «{title}» {count}; un hilo reúne al menos dos.'
        else:
            message = (f'El hilo documental «{title}» mezcla documentos de {len(clients)} clientes: '
                       f'{", ".join(labels[client_id] for client_id in clients)}.')
        yield Finding(
            rule_id='DC8',
            subjects=(RecordRef(DOCUMENT_THREAD, thread_id, title),
                      *(RecordRef(DOCUMENT, document_id, document_title) for document_id, document_title, _ in items)),
            evidence={'thread': thread_id, 'documents': [document_id for document_id, _, _ in items],
                      'clients': clients},
            message=message,
        )
