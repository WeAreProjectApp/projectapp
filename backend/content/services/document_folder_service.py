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
from content.services.entity_history import historical_write
import logging

from django.db import transaction

from content.models import AccountingChangeLog, Document, DocumentFolder
from content.services import accounting_service
from content.services.document_type_codes import COLLECTION_ACCOUNT

logger = logging.getLogger(__name__)

EntityType = AccountingChangeLog.EntityType

MODE_PROPAGATE = 'propagate'
MODE_FOLDER_ONLY = 'folder_only'
MODES = (MODE_PROPAGATE, MODE_FOLDER_ONLY)


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
    children_by_parent = {}
    for child in DocumentFolder.objects.filter(
        pk__in=folder.get_descendant_ids(),
    ).select_related('client_user__profile'):
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
    return reachable, pruned


def linked_sets(folder):
    """Lo que cuelga de la carpeta, agrupado por cómo lo trata la cascada."""
    owner_id = folder.client_user_id
    reachable, pruned = reachable_folders(folder)
    folder_ids = [folder.pk] + [child.pk for child in reachable]

    documents = list(
        Document.objects.filter(folder_id__in=folder_ids)
        .select_related('document_type', 'client_user__profile', 'project'),
    )
    move, blocked, foreign = [], [], []
    for document in documents:
        if _is_locked_account(document):
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
        'documents_move': move,
        'documents_blocked': blocked,
        'documents_foreign': foreign,
    }


def change_client_preview(folder, new_profile):
    """El impacto completo de mover ``folder`` a ``new_profile``, rotulado.

    Es la lista contra la que el operador confirma; el apply recibe de vuelta
    los ids como token, así que el plan que corre es el que se mostró.
    """
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
        'folder_ids': [f.pk for f in sets['folders_move']],
        'document_ids': [d.pk for d in sets['documents_move']],
        'totals': {
            'folders': len(sets['folders_move']),
            'documents': len(sets['documents_move']),
            'blocked': len(sets['documents_blocked']),
            'foreign': len(sets['documents_foreign']),
            'foreign_folders': len(sets['folders_foreign']),
        },
    }


def _reassign(entity_type, record, new_user, user):
    """Mueve un registro al nuevo cliente y desvincula un proyecto ajeno."""
    old_values = accounting_service.snapshot_values(record, entity_type)
    fields = ['client_user']
    from accounts.services.billing_reassignment import validate_document_reassignment
    changes = {'client_user': new_user}
    if record.project_id and record.project.client_id != new_user.pk:
        changes['project'] = None
    validate_document_reassignment(record, changes=changes, lock=True)
    record.client_user = new_user
    if record.project_id and record.project.client_id != new_user.pk:
        record.project = None
        fields.append('project')
    record.save(update_fields=[*fields, 'updated_at'])
    accounting_service.log_entity_diff(entity_type, record, old_values, user)


@historical_write
@transaction.atomic
def change_client_apply(folder, new_profile, mode, user):
    """Mueve la carpeta a ``new_profile`` y hace la cascada según ``mode``.

    Una sola transacción: una carpeta a medio mover parte en dos las cifras
    por cliente. Las filas de auditoría van adentro — un movimiento revertido
    no puede dejar un log diciendo que ocurrió — y ninguna notifica por correo.
    """
    sets = linked_sets(folder)
    # Lock the financial descendants before saving a folder. A draft account
    # must not be moved using an owner read before a competing project move.
    from accounts.services.billing_locks import lock_billing_rows
    account_ids = [doc.pk for doc in sets['documents_move']
                   if getattr(doc.document_type, 'code', None) == 'collection_account']
    locked = lock_billing_rows(document_ids=account_ids)
    sets['documents_move'] = [locked.documents.get(doc.pk, doc) for doc in sets['documents_move']]
    new_user = new_profile.user

    _reassign(EntityType.DOCUMENT_FOLDER, folder, new_user, user)

    moved = {'folders': 0, 'documents': 0}
    skipped = {
        'blocked': len(sets['documents_blocked']),
        'foreign': len(sets['documents_foreign']),
        'foreign_folders': len(sets['folders_foreign']),
    }

    if mode == MODE_PROPAGATE:
        for child in sets['folders_move']:
            _reassign(EntityType.DOCUMENT_FOLDER, child, new_user, user)
            moved['folders'] += 1
        for document in sets['documents_move']:
            _reassign(EntityType.DOCUMENT, document, new_user, user)
            moved['documents'] += 1

    logger.info(
        'Folder %s changed client to profile %s (mode=%s): moved=%s skipped=%s',
        folder.pk, new_profile.pk, mode, moved, skipped,
    )
    return {'moved': moved, 'skipped': skipped}
