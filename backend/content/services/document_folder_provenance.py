"""Explicit, server-owned provenance for every folder creation entry point."""


def folder_creation_values(*, operation, source=None, actor=None, request=None):
    from content.mcp.context import current_mcp_context

    context = current_mcp_context()
    if source is None:
        if context:
            source, actor = "mcp", context.actor
        else:
            actor = actor or getattr(request, "user", None)
            source = "panel" if getattr(actor, "is_authenticated", False) else "system"
    return {
        "created_by": actor if getattr(actor, "is_authenticated", False) else None,
        "creation_source": source,
        "creation_operation": operation,
    }
