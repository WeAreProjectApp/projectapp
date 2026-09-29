"""Atomic moves with the same serializer rules as the document editor."""

from content.mcp.errors import normalize_error
from content.models import Document, DocumentFolder
from content.serializers.document import DocumentCreateUpdateSerializer
from content.services.document_write_service import (
    document_write_payload,
    movement_blockers,
)
from django.db import DatabaseError, transaction


class DocumentMoveError(ValueError):
    def __init__(self, results):
        super().__init__("No se movió ningún documento: el lote contiene errores.")
        self.results = results


def _failure(pk, code, message, **details):
    return {'id': pk, 'status': 'failed', 'moved': False, 'code': code,
            'message': message, 'reason': details.pop('reason', message), **details}


@transaction.atomic
def move_documents(document_ids, folder_id, *, actor, include_content=False):
    if not actor or not actor.is_active or not actor.is_staff:
        raise DocumentMoveError([_failure(pk, "permission_denied", "No tienes permiso para mover documentos.") for pk in document_ids])
    documents = {
        doc.pk: doc
        for doc in Document.objects.select_for_update()
        .filter(
            pk__in=document_ids,
        )
        .order_by("pk")
    }
    target = None
    if folder_id is not None:
        target = DocumentFolder.objects.select_for_update().filter(pk=folder_id).first()
    target_error = None
    if folder_id is not None and target is None:
        target_error = ('folder_not_found', 'La carpeta destino no existe.')
    elif target and target.is_archived:
        target_error = ('folder_archived', 'La carpeta destino está archivada.')
    elif target and target.is_system_managed:
        target_error = ('folder_not_movable', 'La carpeta destino está administrada por el sistema.')
    results, validated = [], {}
    for pk in document_ids:
        document = documents.get(pk)
        blockers = movement_blockers(document) if document else []
        if document is None:
            results.append(_failure(pk, 'not_found', 'El documento no existe.'))
            continue
        if blockers:
            code = 'archived' if document.is_archived else 'not_movable'
            message = 'El documento está archivado.' if document.is_archived else 'El documento no admite movimientos.'
            results.append(_failure(pk, code, message, reason=', '.join(blockers), move_blockers=blockers))
            continue
        if target_error:
            results.append(_failure(pk, *target_error))
            continue
        serializer = DocumentCreateUpdateSerializer(
            document,
            data={"folder_id": folder_id},
            partial=True,
        )
        if not serializer.is_valid():
            message, _code, details = normalize_error(serializer.errors)
            results.append(_failure(pk, 'not_movable', message, reason=serializer.errors, errors=details.get('errors', [])))
            continue
        validated[pk] = serializer
        results.append({"id": pk, "status": "pending", "moved": False})
    if any(result["status"] == "failed" for result in results):
        for result in results:
            if result["status"] == "pending":
                result.update(
                    status="aborted",
                    code="batch_aborted",
                    message="Lote cancelado por errores en otros documentos.",
                    reason="Lote cancelado por errores en otros documentos.",
                )
        raise DocumentMoveError(results)
    try:
        with transaction.atomic():
            for result in results:
                document = documents[result["id"]]
                changed = document.folder_id != folder_id
                if changed:
                    document = validated[document.pk].save(updated_by=actor)
                result.update(
                    status="moved" if changed else "unchanged",
                    moved=changed,
                    document=document_write_payload(
                        document, include_content=include_content
                    ),
                )
    except DatabaseError as exc:
        failed_id = result["id"]
        for row in results:
            row.pop("document", None)
            row.update(
                status="failed" if row["id"] == failed_id else "aborted",
                moved=False,
                code="write_failed" if row["id"] == failed_id else "batch_aborted",
                message="No se pudo guardar el movimiento; no se modificó ningún documento.",
                reason="No se pudo guardar el movimiento; no se modificó ningún documento.",
            )
        raise DocumentMoveError(results) from exc
    return {"ok": True, "results": results}
