"""Shared, bounded document write responses and organization capabilities."""

import hashlib
from functools import wraps

from content.services.contract_mirror_service import is_contract_mirror, mirror_markdown
from content.services.document_type_codes import COLLECTION_ACCOUNT
from rest_framework import serializers


def document_etag(document):
    stamp = document.updated_at.isoformat() if document.updated_at else ""
    return hashlib.sha256(f"document:{document.pk}:{stamp}".encode()).hexdigest()


def movement_blockers(document):
    if document.is_archived:
        return ["archived"]
    if document.is_generated_snapshot:
        return ["generated_snapshot"]
    if (
        document.document_type
        and document.document_type.code == COLLECTION_ACCOUNT
        and document.commercial_status != document.CommercialStatus.DRAFT
    ):
        return ["collection_account_locked"]
    return []


def document_capabilities(document):
    blockers = movement_blockers(document)
    mirror = is_contract_mirror(document)
    return {
        "editable": not blockers and not mirror,
        "movable": not blockers,
        "move_blockers": blockers,
    }


def document_write_payload(document, *, include_content=False):
    data = {
        "id": document.pk,
        "title": document.title,
        "folder_id": document.folder_id,
        "folder_name": document.folder.name if document.folder_id else None,
        "status": document.status,
        "etag": document_etag(document),
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        **document_capabilities(document),
    }
    if include_content:
        data["markdown"] = (
            (mirror_markdown() or "")
            if is_contract_mirror(document)
            else document.content_markdown
        )
    return data


def include_content_value(data, *, multipart=False):
    value = data.get("include_content", False)
    if multipart and value in ("true", "false"):
        value = value == "true"
    if not isinstance(value, bool):
        raise serializers.ValidationError({"include_content": "Debe ser true o false."})
    return value


def document_write_options(view):
    """Validate response controls before the first side effect, including uploads."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        request.include_document_content = include_content_value(
            request.data,
            multipart=request.content_type.startswith("multipart/"),
        )
        return view(request, *args, **kwargs)

    return wrapped


def write_response_data(document, request, **extra):
    return {
        **document_write_payload(
            document, include_content=request.include_document_content
        ),
        **extra,
    }


DOCUMENT_WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "title": {"type": "string"},
        "folder_id": {"type": ["integer", "null"]},
        "folder_name": {"type": ["string", "null"]},
        "status": {"type": "string"},
        "etag": {"type": "string"},
        "updated_at": {"type": ["string", "null"]},
        "editable": {"type": "boolean"},
        "movable": {"type": "boolean"},
        "move_blockers": {"type": "array", "items": {"type": "string"}},
        "markdown": {"type": "string", "description": "Sólo con include_content=true."},
    },
    "required": [
        "id",
        "title",
        "folder_id",
        "folder_name",
        "status",
        "etag",
        "updated_at",
        "editable",
    ],
}
