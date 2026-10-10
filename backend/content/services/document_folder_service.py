"""Cambio de cliente de una carpeta y su cascada sobre el contenido.

Una carpeta raíz lleva el nombre de un cliente desde siempre, así que
reasignarla no es editar un rótulo: arrastra la pregunta de qué pasa con lo
que guarda. Este es el único escritor autorizado para moverla — el impacto se
calcula primero (preview), el apply corre en una transacción con una fila de
auditoría por registro tocado, y hay dos cosas que nunca se reescriben:

- Una cuenta de cobro emitida es un hecho, no un puntero (mismo criterio que
  el cambio de cliente de un proyecto): se reporta y se queda como está.
- Lo que alguien asignó a mano a un TERCER cliente. La carpeta organiza, no es
  dueña: un documento puede pertenecer a otro cliente a propósito, y la
  propagación no está para deshacer esa decisión. Por eso una subcarpeta de
  otro cliente poda su rama entera — cambiar «Kore» por «Ana» no puede
  meterse en la subcarpeta de Néstor.

Modos (el operador elige cada vez; no hay default):
- ``propagate``: el contenido alcanzable sigue a la carpeta al nuevo cliente.
- ``folder_only``: sólo cambia la carpeta; el contenido se queda como está.
"""
import logging
from copy import copy

from accounts.models import Project
from content.models import AccountingChangeLog, Document, DocumentFolder
from content.services import accounting_service
from content.services.document_ownership_planner import (
    OwnershipPlanError,
    portal_audience,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.services.entity_history import historical_write
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

EntityType = AccountingChangeLog.EntityType

MODE_PROPAGATE = 'propagate'
MODE_FOLDER_ONLY = 'folder_only'
MODES = (MODE_PROPAGATE, MODE_FOLDER_ONLY)


def document_portal_audience(document, state=None, *, lock=False):
    """Resolve the planner's audience for a current or hypothetical document."""
    from accounts.services.delivery_documents import PortalDocumentIndex

    candidate = copy(document)
    for field in ('client_user_id', 'project_id', 'is_client_visible', 'is_archived'):
        if state is not None and field in state:
            setattr(candidate, field, state[field])
    # A locking read resolves the current owner under MySQL REPEATABLE READ.
    projects = Project.objects.filter(pk=candidate.project_id)
    project = (projects.select_for_update() if lock else projects).first() if candidate.project_id else None
    candidate.project = project
    owner_id = project.client_id if project else candidate.client_user_id
    linked = (document.delivery_links.exists() or document.delivery_contracts.exists()
              or document.delivery_amendments.exists())
    delivery_audience = None
    if linked and owner_id is not None:
        owner = get_user_model().objects.get(pk=owner_id)
        if PortalDocumentIndex(owner, [candidate]).visible(candidate):
            delivery_audience = owner_id
    return portal_audience({
        'client_user_id': candidate.client_user_id, 'project_id': candidate.project_id,
        'project_client_user_id': project.client_id if project else None,
        'is_client_visible': candidate.is_client_visible, 'is_archived': candidate.is_archived,
        'is_collection_account': getattr(document.document_type, 'code', None) == COLLECTION_ACCOUNT,
        'delivery_linked': linked, 'delivery_audience': delivery_audience,
    })


def _reassignment_changes(record, new_user):
    changes = {'client_user': new_user}
    if record.project_id and record.project.client_id != new_user.pk:
        changes['project'] = None
    return changes


def _portal_changes(documents, new_user):
    changes = []
    for document in documents:
        after = {'client_user_id': new_user.pk, 'project_id': document.project_id}
        if 'project' in _reassignment_changes(document, new_user):
            after['project_id'] = None
        before_audience = document_portal_audience(document)
        after_audience = document_portal_audience(document, after)
        if after_audience is not None and after_audience != before_audience:
            changes.append({'document_id': document.pk, 'before_audience': before_audience,
                            'after_audience': after_audience})
    return changes


def _profile_payload(profile):
    from accounts.services.proposal_client_service import (
        build_client_display_name,
    )

    if profile is None:
        return None
    return {'profile_id': profile.pk, 'name': build_client_display_name(profile)}


def _is_locked_account(document):
    """Una cuenta de cobro que ya salió de borrador no se reescribe."""
    document_type = document.document_type
    if not document_type or document_type.code != COLLECTION_ACCOUNT:
        return False
    return document.commercial_status != Document.CommercialStatus.DRAFT


def reachable_folders(folder):
    """Las subcarpetas que la propagación alcanza, y las que podan su rama.

    Se baja por el árbol desde `folder`: una subcarpeta sin cliente propio, o
    con el mismo que la carpeta que se está moviendo, sigue el camino; una de
    otro cliente corta ahí — ella y todo lo que cuelga de ella son de alguien
    más.
    """
    owner_id = folder.client_user_id
    from content.services.contract_mirror_service import pinned_mirror_folder
    pinned_folder, _source = pinned_mirror_folder()
    descendants = list(DocumentFolder.objects.filter(
        pk__in=folder.get_descendant_ids(),
    ).select_related('client_user__profile'))
    scope_ids = {folder.pk, *(child.pk for child in descendants)}
    pinned_ids = (
        {pinned_folder.pk, *pinned_folder.get_descendant_ids()} & scope_ids
        if pinned_folder else set()
    )
    pinned = [child for child in descendants if child.pk in pinned_ids]
    if folder.pk in pinned_ids:
        pinned.append(folder)
    children_by_parent = {}
    for child in descendants:
        if child.pk not in pinned_ids:
            children_by_parent.setdefault(child.parent_id, []).append(child)

    reachable = []
    pruned = []
    pending = list(children_by_parent.get(folder.pk, []))
    while pending:
        child = pending.pop()
        if child.client_user_id is not None and child.client_user_id != owner_id:
            pruned.append(child)
            continue
        reachable.append(child)
        pending.extend(children_by_parent.get(child.pk, []))
    return reachable, pruned, sorted(pinned, key=lambda child: child.pk)


def linked_sets(folder):
    """Lo que cuelga de la carpeta, agrupado por cómo lo trata la cascada."""
    owner_id = folder.client_user_id
    from content.services.contract_mirror_service import mirror_documents
    reachable, pruned, pinned = reachable_folders(folder)
    folder_ids = [folder.pk] + [child.pk for child in reachable]
    pinned_ids = {child.pk for child in pinned}

    queryset = Document.objects.filter(
        folder_id__in=set(folder_ids) | pinned_ids,
    ).select_related('document_type', 'client_user__profile', 'project').order_by('pk')
    mirror_ids = set(mirror_documents(queryset).values_list('pk', flat=True))
    move, blocked, foreign, documents_pinned = [], [], [], []
    for document in queryset:
        if document.folder_id in pinned_ids or document.pk in mirror_ids:
            documents_pinned.append(document)
        elif _is_locked_account(document):
            blocked.append(document)
        elif (
            document.client_user_id is not None
            and document.client_user_id != owner_id
        ):
            foreign.append(document)
        else:
            move.append(document)
    return {
        'folders_move': reachable,
        'folders_foreign': pruned,
        'folders_pinned': pinned,
        'documents_move': move,
        'documents_blocked': blocked,
        'documents_foreign': foreign,
        'documents_pinned': documents_pinned,
    }


def _refuse_pinned_client_change(folder):
    from content.services.contract_mirror_service import (
        CONTRACT_MIRROR_FOLDER_PINNED,
        CONTRACT_MIRROR_FOLDER_PINNED_MESSAGE,
        pinned_mirror_folder,
    )
    pinned, _source = pinned_mirror_folder()
    if pinned and pinned.pk in {folder.pk, *(ancestor.pk for ancestor in folder.get_ancestors())}:
        raise ValidationError({
            'detail': CONTRACT_MIRROR_FOLDER_PINNED_MESSAGE,
            'code': CONTRACT_MIRROR_FOLDER_PINNED,
        }, code=CONTRACT_MIRROR_FOLDER_PINNED)


def change_client_preview(folder, new_profile):
    """El impacto completo de mover ``folder`` a ``new_profile``, rotulado.

    Es la lista contra la que el operador confirma; el apply recibe de vuelta
    los ids como token, así que el plan que corre es el que se mostró.
    """
    _refuse_pinned_client_change(folder)
    sets = linked_sets(folder)
    current_profile = getattr(folder.client_user, 'profile', None)

    def document_row(document, reason=''):
        row = {
            'id': document.pk,
            'title': document.title,
            'client_name': document.client_name or '',
        }
        if reason:
            row['reason'] = reason
        return row

    def folder_row(child):
        return {'id': child.pk, 'name': child.name}

    return {
        'folder': {'id': folder.pk, 'name': folder.name},
        'current_client': _profile_payload(current_profile),
        'new_client': _profile_payload(new_profile),
        'folders_move': [folder_row(f) for f in sets['folders_move']],
        'folders_foreign': [
            {
                **folder_row(f),
                'reason': 'Es de otro cliente: ni ella ni su contenido se tocan.',
            }
            for f in sets['folders_foreign']
        ],
        'documents_move': [document_row(d) for d in sets['documents_move']],
        'documents_blocked': [
            document_row(
                d,
                'Es una cuenta de cobro ya emitida: conserva su cliente.',
            )
            for d in sets['documents_blocked']
        ],
        'documents_foreign': [
            document_row(d, 'Está asignado a otro cliente: conserva el suyo.')
            for d in sets['documents_foreign']
        ],
        'folders_pinned': [
            {**folder_row(f), 'reason': 'Pertenece a la rama fijada de los espejos contractuales: conserva su cliente y proyecto.'}
            for f in sets['folders_pinned']
        ],
        'documents_pinned': [
            document_row(d, 'Es un espejo contractual o pertenece a su rama fijada: conserva su cliente y proyecto.')
            for d in sets['documents_pinned']
        ],
        'folder_ids': [f.pk for f in sets['folders_move']],
        'document_ids': [d.pk for d in sets['documents_move']],
        'portal_changes': _portal_changes(sets['documents_move'], new_profile.user),
        'totals': {
            'folders': len(sets['folders_move']),
            'documents': len(sets['documents_move']),
            'blocked': len(sets['documents_blocked']),
            'foreign': len(sets['documents_foreign']),
            'foreign_folders': len(sets['folders_foreign']),
            'pinned': len(sets['documents_pinned']),
            'pinned_folders': len(sets['folders_pinned']),
        },
    }


def _reassign(entity_type, record, new_user, user, *, hide_new_exposure=False):
    """Mueve un registro al nuevo cliente y desvincula un proyecto ajeno."""
    old_values = accounting_service.snapshot_values(record, entity_type)
    fields = ['client_user']
    from accounts.services.billing_reassignment import validate_document_reassignment
    changes = _reassignment_changes(record, new_user)
    validate_document_reassignment(record, changes=changes, lock=True)
    record.client_user = new_user
    if 'project' in changes:
        record.project = None
        fields.append('project')
    if hide_new_exposure:
        record.is_client_visible = False
        fields.append('is_client_visible')
    record.save(update_fields=[*fields, 'updated_at'])
    accounting_service.log_entity_diff(entity_type, record, old_values, user)


@historical_write
@transaction.atomic
def change_client_apply(folder, new_profile, mode, user, *, portal_policy=None):
    """Mueve la carpeta a ``new_profile`` y hace la cascada según ``mode``.

    Una sola transacción: una carpeta a medio mover parte en dos las cifras
    por cliente. Las filas de auditoría van adentro — un movimiento revertido
    no puede dejar un log diciendo que ocurrió — y ninguna notifica por correo.
    """
    _refuse_pinned_client_change(folder)
    sets = linked_sets(folder)
    # Lock the financial descendants before saving a folder. A draft account
    # must not be moved using an owner read before a competing project move.
    from accounts.services.billing_locks import lock_billing_rows
    account_ids = [doc.pk for doc in sets['documents_move']
                   if getattr(doc.document_type, 'code', None) == 'collection_account']
    locked = lock_billing_rows(document_ids=account_ids)
    sets['documents_move'] = [locked.documents.get(doc.pk, doc) for doc in sets['documents_move']]
    new_user = new_profile.user

    exposures = _portal_changes(sets['documents_move'], new_user) if mode == MODE_PROPAGATE and portal_policy else []
    if exposures and portal_policy == 'abort':
        raise OwnershipPlanError(
            'El cambio daría acceso a un nuevo cliente en el portal.', code='portal_exposure',
            blockers=[{'code': 'portal_exposure', 'message': 'El cambio daría acceso a un nuevo cliente en el portal.',
                       'resource_type': 'document', 'resource_id': row['document_id'], **row}
                      for row in exposures],
        )
    hidden_ids = {row['document_id'] for row in exposures} if portal_policy == 'hide_new_exposure' else set()

    _reassign(EntityType.DOCUMENT_FOLDER, folder, new_user, user)

    moved = {'folders': 0, 'documents': 0}
    skipped = {
        'blocked': len(sets['documents_blocked']),
        'foreign': len(sets['documents_foreign']),
        'foreign_folders': len(sets['folders_foreign']),
        'pinned': len(sets['documents_pinned']),
        'pinned_folders': len(sets['folders_pinned']),
    }

    if mode == MODE_PROPAGATE:
        for child in sets['folders_move']:
            _reassign(EntityType.DOCUMENT_FOLDER, child, new_user, user)
            moved['folders'] += 1
        for document in sets['documents_move']:
            _reassign(EntityType.DOCUMENT, document, new_user, user,
                      hide_new_exposure=document.pk in hidden_ids)
            moved['documents'] += 1

    logger.info(
        'Folder %s changed client to profile %s (mode=%s): moved=%s skipped=%s',
        folder.pk, new_profile.pk, mode, moved, skipped,
    )
    return {'moved': moved, 'skipped': skipped}
