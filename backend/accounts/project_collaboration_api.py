"""Transport wrappers preserve session/CSRF and JWT as separate boundaries."""
from functools import wraps

from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from accounts.authentication import SessionJWTAuthentication


def endpoint(methods, *, channel='platform'):
    def decorate(function):
        authentication = SessionAuthentication if channel == 'panel' else SessionJWTAuthentication
        permission = IsAdminUser if channel == 'panel' else IsAuthenticated
        view = api_view(methods)(authentication_classes([authentication])(permission_classes([permission])(function)))

        @wraps(view)
        def response_wrapper(request, *args, **kwargs):
            response = view(request, *args, **kwargs)
            response['Cache-Control'] = 'no-store, max-age=0'
            response['Pragma'] = 'no-cache'
            return response
        return response_wrapper
    return decorate


def require_personal_session(request):
    if request.auth and request.auth.get('impersonated_by'):
        raise PermissionDenied('Inicia sesión con tu propia cuenta para registrar ideas o consultar credenciales.')
