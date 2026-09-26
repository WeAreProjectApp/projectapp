"""Archivado y desarchivado del gestor de documentos (panel admin).

Archivar saca algo de circulación sin destruirlo. A diferencia de eliminar,
archivar una carpeta CON contenido está permitido: la operación cae en cascada
sobre cada subcarpeta y cada documento del subárbol.

Cada fila arrastrada guarda en `archived_via_folder` la carpeta que la archivó;
las filas archivadas por su cuenta dejan ese campo en NULL y no se tocan. Así,
desarchivar una carpeta restaura exactamente lo que ella arrastró — sin recorrer
el árbol, y sin resucitar lo que el usuario había archivado a propósito.

Ese FK (en vez de un enum 'manual'/'folder') es lo que mantiene correcto el
caso anidado: si una subcarpeta se archivó a mano y después se archiva su padre,
el subárbol de la subcarpeta sigue apuntando a ella, así que desarchivar el
padre lo deja intacto. También sobrevive a mover un documento de carpeta
mientras está archivado, porque el vínculo no depende de dónde vive hoy.

**Nada queda restaurado sin ubicación alcanzable.** Restaurar reabre la cadena
de carpetas contenedoras hasta la raíz — sólo la cadena, no el resto del
contenido de esas carpetas. La consecuencia es una carpeta con contenido activo
y archivado a la vez, y es preferible a lo que pasaba antes: un documento activo
dentro de una carpeta archivada no salía en ninguna de las dos vistas (ni en
Archivados, porque no está archivado; ni en el árbol, porque su carpeta no se
lista) y quedaba perdido. `ensure_active_target` cierra la otra mitad del
problema impidiendo que se creen huérfanos nuevos moviendo algo activo dentro
de una carpeta archivada.

El archivado es una herramienta del panel: el portal del cliente (`accounts/`)
no filtra por estos campos.
"""
from content.services.entity_history import historical_write
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from content.models import Document, DocumentFolder

_ARCHIVE_FIELDS = ['is_archived', 'archived_at', 'archived_via_folder']


class DocumentArchiveError(ValueError):
    """Operación de archivado rechazada por una regla de negocio."""


def _restore_chain(folder):
    """Desarchiva las carpetas que hacen visible a `folder`, `folder` incluida.

    Devuelve ``(restauradas, rota)``. Sólo toca las carpetas de la cadena: el
    resto del contenido de cada ancestro sigue archivado, que es justo lo que
    produce el estado mixto (carpeta activa con contenido archivado).

    `rota` es True cuando el ascenso por `parent` no llegó a una raíz — sólo
    pasa con un ciclo en los datos. `get_ancestors()` trunca en silencio al
    repetir un nodo, así que una cadena completa SIEMPRE termina en una carpeta
    con `parent_id` nulo: que la cabeza tenga padre es exactamente la señal.
    Con la cadena rota no se toca ninguna carpeta y el caller desengancha el
    elemento, que es lo único que garantiza que quede alcanzable.
    """
    if folder is None:
        return [], False

    chain = [*folder.get_ancestors(), folder]
    if chain[0].parent_id is not None:
        return [], True

    archived = [f for f in chain if f.is_archived]
    if archived:
        DocumentFolder.objects.filter(pk__in=[f.pk for f in archived]).update(
            is_archived=False, archived_at=None, archived_via_folder=None,
        )
        for f in archived:
            f.is_archived = False
            f.archived_at = None
            f.archived_via_folder = None
    return archived, False


def ensure_active_target(folder, *, moving_archived=False):
    """Rechaza mover algo ACTIVO dentro de una carpeta archivada.

    Un elemento activo dentro de una carpeta archivada no sale en ninguna de
    las dos vistas del panel: es exactamente el huérfano que la migración 0186
    tuvo que reparar. Mover algo YA archivado sí se permite — el servicio
    depende de ello, porque desarchivar restaura por procedencia y no por
    ubicación.

    Basta con mirar el contenedor directo: una vez que el invariante se cumple,
    una carpeta activa siempre tiene toda su cadena activa.
    """
    if folder is None or moving_archived or not folder.is_archived:
        return
    raise DocumentArchiveError(
        f'La carpeta «{folder.name}» está archivada y no admite contenido '
        'activo. Restáurala primero.'
    )


def _refuse_contract_mirror(documents):
    """The window onto the one contract never leaves the panel's main view."""
    from content.services.contract_mirror_service import CONTRACT_MIRROR_MESSAGE

    if documents.filter(contract_template__isnull=False).exists():
        raise DocumentArchiveError(CONTRACT_MIRROR_MESSAGE)


def archive_document(document):
    """Archiva un documento suelto. Devuelve True si cambió algo."""
    _refuse_contract_mirror(Document.objects.filter(pk=document.pk))
    if document.is_archived:
        return False
    document.is_archived = True
    document.archived_at = timezone.now()
    document.archived_via_folder = None
    document.save(update_fields=_ARCHIVE_FIELDS)
    return True


@historical_write
@transaction.atomic
def unarchive_document(document):
    """Restaura un documento y reabre la cadena de carpetas que lo contiene.

    Devuelve ``{'changed': bool, 'restored_chain': [DocumentFolder],
    'moved_to_root': bool}``.

    Si su carpeta fue eliminada mientras estaba archivado, el FK ya quedó en
    NULL (on_delete=SET_NULL) y el documento reaparece en «Sin carpeta». Si la
    cadena está rota por un ciclo se lo manda ahí a propósito: una ubicación
    pobre es mejor que ninguna.
    """
    # Lock de fila (no-op en SQLite/tests, lock real en MySQL/prod): serializa
    # este unarchive con un archive_folder concurrente de un ancestro — la
    # carrera que deja un documento activo sepultado bajo carpeta archivada.
    Document.objects.select_for_update().filter(pk=document.pk).exists()

    if not document.is_archived:
        return {'changed': False, 'restored_chain': [], 'moved_to_root': False}

    restored, broken = _restore_chain(document.folder)
    fields = list(_ARCHIVE_FIELDS)
    if broken:
        document.folder = None
        fields.append('folder')

    document.is_archived = False
    document.archived_at = None
    document.archived_via_folder = None
    document.save(update_fields=fields)
    return {'changed': True, 'restored_chain': restored, 'moved_to_root': broken}


@historical_write
@transaction.atomic
def archive_folder(folder):
    """Archiva la carpeta, sus subcarpetas y todos sus documentos.

    Devuelve ``{'folders': n, 'documents': m}`` con lo que arrastró esta
    llamada. El filtro `is_archived=False` es la memoria de la cascada: lo que
    ya estaba archivado conserva su marca y su `archived_at` original, de modo
    que re-archivar no rejuvenece nada en la vista ordenada por antigüedad.
    """
    # Lock de fila antes de computar descendientes (ver unarchive_document).
    DocumentFolder.objects.select_for_update().filter(pk=folder.pk).exists()

    now = timezone.now()
    descendant_ids = folder.get_descendant_ids()
    scope_ids = {folder.pk} | descendant_ids
    # The bulk update below skips save(), so the check has to happen first.
    _refuse_contract_mirror(Document.objects.filter(folder_id__in=scope_ids))

    folders_count = DocumentFolder.objects.filter(
        pk__in=descendant_ids, is_archived=False,
    ).update(is_archived=True, archived_at=now, archived_via_folder=folder)

    documents_count = Document.objects.filter(
        folder_id__in=scope_ids, is_archived=False,
    ).update(is_archived=True, archived_at=now, archived_via_folder=folder)

    # La carpeta sobre la que se actuó siempre queda como archivada a mano.
    DocumentFolder.objects.filter(pk=folder.pk, is_archived=False).update(
        is_archived=True, archived_at=now, archived_via_folder=None,
    )
    folder.refresh_from_db()

    return {'folders': folders_count, 'documents': documents_count}


@historical_write
@transaction.atomic
def unarchive_folder(folder):
    """Restaura la carpeta, lo que su archivado arrastró, y su cadena de ancestros.

    Devuelve ``{'folders': n, 'documents': m, 'restored_chain': [...],
    'moved_to_root': bool}``. `folders`/`documents` siguen contando SÓLO la
    cascada propia; `restored_chain` son los ancestros que hubo que reabrir para
    que la carpeta tenga dónde vivir.

    El orden es seguro: un ancestro nunca puede llevar `archived_via_folder`
    apuntando a esta carpeta (haría falta un ciclo, que sale antes), así que
    ninguna fila se actualiza dos veces.
    """
    # Lock de fila antes de reabrir la cadena (ver unarchive_document).
    DocumentFolder.objects.select_for_update().filter(pk=folder.pk).exists()

    restored_chain, broken = _restore_chain(folder.parent)
    if broken:
        DocumentFolder.objects.filter(pk=folder.pk).update(parent=None)
        folder.parent_id = None

    folders_count = DocumentFolder.objects.filter(
        archived_via_folder=folder, is_archived=True,
    ).update(is_archived=False, archived_at=None, archived_via_folder=None)

    documents_count = Document.objects.filter(
        archived_via_folder=folder, is_archived=True,
    ).update(is_archived=False, archived_at=None, archived_via_folder=None)

    DocumentFolder.objects.filter(pk=folder.pk).update(
        is_archived=False, archived_at=None, archived_via_folder=None,
    )
    folder.refresh_from_db()

    return {
        'folders': folders_count,
        'documents': documents_count,
        'restored_chain': restored_chain,
        'moved_to_root': broken,
    }


def panel_counts():
    """Contadores del panel lateral del gestor. Dos queries, sin filtros de vista.

    Viven en el backend porque la lista viene filtrada por carpeta: el frontend
    no puede sumar lo que no cargó, y sumar el `document_count` de cada carpeta
    ignora los documentos sin carpeta y duplica los que sí la tienen.

    Deben reflejar EXACTAMENTE el queryset base de `list_documents` (hoy: todos
    los documentos, cuentas de cobro incluidas). Si esa lista alguna vez filtra
    por `document_type`, esto tiene que seguirla o los contadores vuelven a mentir.
    """
    documents = Document.objects.aggregate(
        active=Count('id', filter=Q(is_archived=False)),
        archived=Count('id', filter=Q(is_archived=True)),
        unfiled_active=Count('id', filter=Q(is_archived=False, folder__isnull=True)),
        unfiled_archived=Count('id', filter=Q(is_archived=True, folder__isnull=True)),
    )
    folders = DocumentFolder.objects.aggregate(
        active=Count('id', filter=Q(is_archived=False)),
        archived=Count('id', filter=Q(is_archived=True)),
    )
    return {'documents': documents, 'folders': folders}
