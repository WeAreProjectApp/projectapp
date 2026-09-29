"""Reviewed folder repair: exact identities, stale-state refusal, one transaction."""

import hashlib
import json
from datetime import timedelta

from accounts.models import UserProfile
from content.models import AccountingChangeLog, Document, DocumentFolder, McpRequestLog
from content.models.document_folder import DocumentFolderMutationLock
from content.services.document_archive_service import archive_folder
from content.services.document_write_service import movement_blockers
from content.services.entity_history import history_operation
from django.db import transaction


class FolderRepairError(ValueError):
    pass


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def _snapshot(source_id, target_id, document_ids):
    folders = list(
        DocumentFolder.objects.filter(pk__in=[source_id, target_id])
        .order_by("pk")
        .values()
    )
    documents = list(
        Document.objects.filter(pk__in=document_ids).order_by("pk").values()
    )
    # Only hashes enter the manifest: no document content or private notes.
    return {
        "folders": [
            {"id": row["id"], "fingerprint": fingerprint(row)} for row in folders
        ],
        "documents": [
            {"id": row["id"], "fingerprint": fingerprint(row)} for row in documents
        ],
        "source_documents": list(
            Document.objects.filter(folder_id=source_id)
            .order_by("pk")
            .values_list("pk", flat=True)
        ),
        "target_documents": list(
            Document.objects.filter(folder_id=target_id)
            .order_by("pk")
            .values_list("pk", flat=True)
        ),
        "source_children": list(
            DocumentFolder.objects.filter(parent_id=source_id)
            .order_by("pk")
            .values_list("pk", flat=True)
        ),
    }


def _identities(source_id, target_id, client_profile_id):
    try:
        source = DocumentFolder.objects.get(pk=source_id)
        target = DocumentFolder.objects.get(pk=target_id)
        client = UserProfile.objects.clients().get(pk=client_profile_id)
    except (DocumentFolder.DoesNotExist, UserProfile.DoesNotExist) as exc:
        raise FolderRepairError(
            "La carpeta o el perfil de cliente ya no existe."
        ) from exc
    if (
        source_id == target_id
        or source.folder_kind != "manual"
        or source.is_system_managed
    ):
        raise FolderRepairError(
            "El origen debe ser una carpeta manual distinta del destino."
        )
    if source.client_user_id or source.project_id or source.parent_id:
        raise FolderRepairError(
            "La carpeta origen adquirió asociaciones; requiere revisión."
        )
    if (
        target.managed_client_id != client.user_id
        or target.client_user_id != client.user_id
        or target.parent_id
        or target.project_id
        or target.is_archived
        or target.is_system_managed
    ):
        raise FolderRepairError(
            "El destino no es la raíz activa del perfil de cliente indicado."
        )
    if source.name.strip().casefold() != target.name.strip().casefold():
        raise FolderRepairError("Los nombres de las carpetas no coinciden.")
    if DocumentFolder.objects.filter(parent=source).exists():
        raise FolderRepairError(
            "El origen tiene subcarpetas; no se puede archivar como carpeta vacía."
        )
    return source, target, client


def creation_evidence(folder, request_id):
    """Correlate one successful creation with the only folder born in its window."""
    if not request_id:
        return None
    lower, upper = (
        folder.created_at - timedelta(seconds=1),
        folder.created_at + timedelta(seconds=1),
    )
    events = McpRequestLog.objects.filter(
        connector__slug="documents",
        tool_name="create_folder",
        ok=True,
        created_at__range=(lower, upper),
    ).select_related("credential")
    rows = list(events)
    folders = list(
        DocumentFolder.objects.filter(created_at__range=(lower, upper)).values_list(
            "pk", flat=True
        )
    )
    if (
        len(rows) != 1
        or rows[0].request_id != request_id
        or folders != [folder.pk]
        or not rows[0].credential_id
        or not rows[0].credential.actor_id
    ):
        raise FolderRepairError(
            "La evidencia de creación no es unívoca; conserva el origen desconocido."
        )
    return {
        "request_id": request_id,
        "log_id": rows[0].pk,
        "actor_id": rows[0].credential.actor_id,
        "source": "mcp",
        "operation": "create_folder",
    }


def prepare_repair(
    source_id, target_id, client_profile_id, document_ids, *, creation_request_id=None
):
    ids = sorted(document_ids)
    if (
        not ids
        or len(ids) != len(set(ids))
        or any(type(pk) is not int or pk <= 0 for pk in ids)
    ):
        raise FolderRepairError("Revisa la lista explícita de IDs de documentos.")
    source, target, client = _identities(source_id, target_id, client_profile_id)
    if source.is_archived:
        raise FolderRepairError("La carpeta origen ya está archivada.")
    snapshot = _snapshot(source_id, target_id, ids)
    if snapshot["source_documents"] != ids or snapshot["target_documents"]:
        raise FolderRepairError(
            "El origen debe contener exactamente los IDs revisados y el destino estar vacío."
        )
    for document in Document.objects.filter(pk__in=ids).select_related(
        "document_type", "project"
    ):
        if movement_blockers(document):
            raise FolderRepairError(
                f"El documento {document.pk} no admite movimientos."
            )
        if document.client_user_id not in (None, client.user_id) or (
            document.project_id and document.project.client_id != client.user_id
        ):
            raise FolderRepairError(
                f"El documento {document.pk} pertenece a otro cliente."
            )
    return {
        "version": 1,
        "source_folder_id": source.pk,
        "target_folder_id": target.pk,
        "client_profile_id": client.pk,
        "document_ids": ids,
        "expected": snapshot,
        "creation_evidence": creation_evidence(source, creation_request_id),
    }


@transaction.atomic
def apply_repair(manifest, *, expected_hash, actor, backup_ref):
    if fingerprint(manifest) != expected_hash:
        raise FolderRepairError("El hash no corresponde al manifiesto revisado.")
    if (
        manifest.get("version") != 1
        or not getattr(actor, "is_superuser", False)
        or not actor.is_active
    ):
        raise FolderRepairError(
            "La reparación requiere manifiesto vigente y un administrador activo."
        )
    if not backup_ref:
        raise FolderRepairError("Falta la referencia del respaldo previo.")
    source_id, target_id = manifest["source_folder_id"], manifest["target_folder_id"]
    ids = manifest["document_ids"]
    DocumentFolderMutationLock.objects.get_or_create(pk=1)
    DocumentFolderMutationLock.objects.select_for_update().get(pk=1)
    list(Document.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    list(
        DocumentFolder.objects.select_for_update()
        .filter(pk__in=[source_id, target_id])
        .order_by("pk")
    )
    source, target, _ = _identities(source_id, target_id, manifest["client_profile_id"])
    # A retry is a no-op only with our durable receipt and the expected placement.
    receipt = AccountingChangeLog.objects.filter(
        entity_type="document_folder", object_id=source_id, action="updated"
    )
    already_applied = any(
        {"field": "repair_manifest", "old": "", "new": expected_hash} in row.changes
        for row in receipt.only("changes")
    )
    if already_applied:
        if (
            source.is_archived
            and not source.documents.exists()
            and Document.objects.filter(pk__in=ids, folder=target).count() == len(ids)
        ):
            return {"changed": False, "document_ids": ids}
        raise FolderRepairError(
            "La reparación anterior cambió después; requiere una nueva revisión."
        )
    if _snapshot(source_id, target_id, ids) != manifest["expected"]:
        raise FolderRepairError(
            "El estado cambió desde la previsualización; no se modificó nada."
        )
    prepare_repair(source_id, target_id, manifest["client_profile_id"], ids)
    evidence = manifest.get("creation_evidence")
    if evidence and creation_evidence(source, evidence["request_id"]) != evidence:
        raise FolderRepairError("La evidencia de creación cambió; requiere revisión.")
    with history_operation(actor=actor, source="command:repair_document_folder"):
        for document in Document.objects.filter(pk__in=ids).order_by("pk"):
            # A repair restores placement only; it must not inherit client/project.
            document.folder = target
            document.updated_by = actor
            document.save(update_fields=["folder", "updated_by", "updated_at"])
        if source.documents.exists() or source.children.exists():
            raise FolderRepairError(
                "El origen dejó de estar vacío; se revierte la reparación."
            )
        if evidence and source.creation_source == "unknown":
            source.creation_source = evidence["source"]
            source.created_by_id = evidence["actor_id"]
            fields = ["creation_source", "created_by"]
            # This maintenance operation also supports deployed documents 3.0.0.
            if hasattr(source, "creation_operation"):
                source.creation_operation = evidence["operation"]
                fields.append("creation_operation")
            source.save(update_fields=fields)
        archive_folder(source)
        AccountingChangeLog.objects.create(
            entity_type="document_folder",
            object_id=source.pk,
            object_repr=source.name,
            action="updated",
            actor=actor,
            actor_username=actor.get_username(),
            changes=[
                {"field": "repair_manifest", "old": "", "new": expected_hash},
                {"field": "folder", "old": source.pk, "new": target.pk},
                {"field": "document_ids", "old": ids, "new": ids},
                {"field": "is_archived", "old": False, "new": True},
                {"field": "backup_ref", "old": "", "new": backup_ref},
                {"field": "creation_evidence", "old": None, "new": evidence},
            ],
        )
    return {"changed": True, "document_ids": ids}
