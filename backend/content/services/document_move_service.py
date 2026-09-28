"""Atomic moves with the same serializer rules as the document editor."""

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


@transaction.atomic
def move_documents(document_ids, folder_id, *, actor, include_content=False):
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
        target_error = "La carpeta destino no existe."
    elif target and (target.is_archived or target.is_system_managed):
        target_error = (
            "La carpeta destino está archivada o administrada por el sistema."
        )
    results, validated = [], {}
    for pk in document_ids:
        document = documents.get(pk)
        blockers = movement_blockers(document) if document else ["not_found"]
        if target_error or blockers:
            results.append(
                {
                    "id": pk,
                    "status": "failed",
                    "moved": False,
                    "reason": target_error or ", ".join(blockers),
                }
            )
            continue
        serializer = DocumentCreateUpdateSerializer(
            document,
            data={"folder_id": folder_id},
            partial=True,
        )
        if not serializer.is_valid():
            results.append(
                {
                    "id": pk,
                    "status": "failed",
                    "moved": False,
                    "reason": serializer.errors,
                }
            )
            continue
        validated[pk] = serializer
        results.append({"id": pk, "status": "pending", "moved": False})
    if any(result["status"] == "failed" for result in results):
        for result in results:
            if result["status"] == "pending":
                result.update(
                    status="aborted",
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
                reason="No se pudo guardar el movimiento; no se modificó ningún documento.",
            )
        raise DocumentMoveError(results) from exc
    return {"ok": True, "results": results}
