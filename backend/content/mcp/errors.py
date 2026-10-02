"""Preserve serializer error codes before JSON serialization loses ErrorDetail."""

import json
import logging


def normalize_error(payload, status_code=400):
    data = payload if isinstance(payload, dict) else {"detail": payload}
    errors = []

    def visit(value, path):
        if isinstance(value, dict):
            for name, child in value.items():
                visit(child, f"{path}.{name}" if path else name)
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(child, f"{path}.{index}" if isinstance(child, dict) else path)
        else:
            errors.append(
                {
                    "field": path or "non_field_errors",
                    "code": getattr(value, "code", "invalid"),
                    "message": str(value),
                }
            )

    for field, value in data.items():
        if field not in {
            "code",
            "message",
            "detail",
            "ok",
            "results",
            "hint",
            "matching_ids",
        }:
            visit(value, field)
    message = data.get("detail") or data.get("message")
    if message:
        if isinstance(message, (dict, list, tuple)):
            visit(message, "")
            message = "; ".join(row["message"] for row in errors)
        else:
            message = str(message)
    elif errors:
        message = "; ".join(f"{row['field']}: {row['message']}" for row in errors)
    else:
        message = "La operación del Panel fue rechazada."
    code = data.get("code")
    if isinstance(code, (list, tuple)):
        code = code[0] if code else None
    specific = {row["code"] for row in errors}
    if (
        not code
        and len(specific) == 1
        and specific <= {"unknown_field", "folder_cycle"}
    ):
        code = specific.pop()
    if code:
        code = str(code)
        if code not in {"unknown_field", "folder_cycle"}:
            code = code.upper()  # Existing Panel bridge error codes are public.
    else:
        code = {403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT"}.get(
            status_code, "VALIDATION_ERROR"
        )
    details = json.loads(json.dumps(data, ensure_ascii=False, default=str))
    if errors:
        details["errors"] = errors
    return str(message), code, details


def transport_exception_handler(exc, context):
    """Keep codes/messages on HTTP failures raised before tool dispatch, too."""
    from rest_framework.response import Response
    from rest_framework.views import exception_handler, set_rollback

    response = exception_handler(exc, context)
    if response is None:
        logging.getLogger(__name__).error("MCP transport failed code=INTERNAL_ERROR")
        set_rollback()
        response = Response(status=500)
        code, message = "INTERNAL_ERROR", "Error interno del servidor."
    else:
        message, code, _details = normalize_error(response.data, response.status_code)
        code = str(getattr(exc, "default_code", code)).upper()
    response.data = {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": code, "message": message},
    }
    return response
