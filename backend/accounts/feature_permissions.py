"""Attach availability after existing DRF permissions, at URL registration time.

Only the named Platform surfaces are bound. Panel/MCP domain writers keep their
own authorization. The inventory check requires every endpoint to be classified.
"""
from django.urls import URLResolver
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

from accounts.feature_catalog import API_FEATURES, CATALOG
from accounts.services import platform_features as service


class PlatformFeatureAvailable(BasePermission):
    def has_permission(self, request, view):
        match = request.resolver_match
        if not match or not request.user or not request.user.is_authenticated:
            return True  # Existing authentication/permissions own this decision.
        name = match.url_name
        key = API_FEATURES.get(name)
        dynamic = CATALOG['api_dynamic'].get(name)
        if dynamic:
            if dynamic == 'attachment':
                # Record authorization precedes classification of a shared download.
                from accounts.services.issue_evidence import attachment_for_actor
                item = attachment_for_actor(match.kwargs['attachment_id'], request.user)
                bug = item.bug_comment_id or (item.response_id and item.response.bug_report_id)
                key = 'platform.bugs' if bug else 'platform.change_requests'
            elif dynamic == 'kind':
                key = 'platform.bugs' if match.kwargs.get('kind') == 'bug' else 'platform.change_requests'
            else:
                return service.enabled(request.user, 'platform.bugs') or service.enabled(request.user, 'platform.change_requests')
        if key:
            service.require_feature(request.user, key)
        elif name not in CATALOG['api_exemptions']:
            raise PermissionDenied('Esta operación no tiene disponibilidad definida.')
        return True


def bind_feature_permissions(patterns):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            bind_feature_permissions(pattern.url_patterns)
            continue
        cls = getattr(pattern.callback, 'cls', None)
        if cls and PlatformFeatureAvailable not in cls.permission_classes:
            cls.permission_classes = [*cls.permission_classes, PlatformFeatureAvailable]

