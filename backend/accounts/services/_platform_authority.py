"""Bind profile authority to verified Platform JWT requests without changing users."""
from contextvars import ContextVar
from functools import wraps

from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication

_jwt_actor_id = ContextVar('platform_jwt_actor_id', default=None)


def platform_role_authority(actor):
    """Return the bound profile decision, or None outside a verified JWT call."""
    actor_id = _jwt_actor_id.get()
    if actor_id is None:
        return None
    profile = getattr(actor, 'profile', None)
    return bool(actor.pk == actor_id and profile and profile.is_admin)


def platform_role_boundary(view):
    """Scope the authenticated JWT actor through nested services and error paths."""
    @wraps(view)
    def scoped(request, *args, **kwargs):
        if not isinstance(request, Request) or not isinstance(
            request.successful_authenticator, JWTAuthentication,
        ):
            return view(request, *args, **kwargs)
        token = _jwt_actor_id.set(request.user.pk)
        try:
            return view(request, *args, **kwargs)
        finally:
            _jwt_actor_id.reset(token)

    return scoped


def mcp_delivery_actor_is_bound(actor, context):
    """Require the facade's real usable projects credential to own its actor."""
    if context is None:
        # Existing trusted direct handlers retain their configured actor lookup.
        return True
    from content.mcp.context import McpExecutionContext
    from content.models import McpConnector, McpCredential

    if not isinstance(context, McpExecutionContext) or actor is None:
        return False
    connector, credential = context.connector, context.credential
    return bool(
        isinstance(connector, McpConnector) and connector.pk and not connector._state.adding
        and connector.is_active and connector.slug == 'projects'
        and isinstance(credential, McpCredential) and credential.pk and not credential._state.adding
        and context.actor and context.actor.pk == actor.pk
        and credential.actor_id == actor.pk and credential.connector_id == connector.pk
        and credential.is_usable
    )
